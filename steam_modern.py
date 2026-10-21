"""Modern desktop shell for Steam Library Organizer.

The application keeps all Steam operations in Python and renders the existing
HTML/CSS/JavaScript interface inside a native Windows WebView2 window.  Static
assets are inlined and passed to pywebview as HTML, so the production desktop
entry point does not start an HTTP server or open the user's browser.

If pywebview or WebView2 cannot start, the bundled tkinter desktop interface
is launched as an offline compatibility fallback.
"""

from __future__ import annotations

import ctypes
import base64
import importlib
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, TypeVar

from steam_library_core import SteamError
from steam_settings import (
    app_data_dir as _shared_app_data_dir,
    load_saved_steam_root as _shared_load_saved_steam_root,
    save_steam_root as _shared_save_steam_root,
    settings_path as _shared_settings_path,
)
from steam_web import Organizer


APP_TITLE = "Steam 游戏库整理"
APP_VERSION = "1.1.0"
MUTEX_NAME = r"Local\SteamLibraryOrganizer.Desktop.v1"
LOGGER = logging.getLogger("steam_library_organizer.modern")
T = TypeVar("T")


def _app_data_dir() -> Path:
    """Compatibility wrapper for the shared writable per-user folder."""

    return _shared_app_data_dir()


def configure_logging() -> Path:
    """Configure a bounded UTF-8 log that also works in windowed builds."""

    log_path = _app_data_dir() / "steam_modern.log"
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    if not LOGGER.handlers:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s")
        )
        LOGGER.addHandler(handler)
    handler = LOGGER.handlers[0]
    webview_logger = logging.getLogger("pywebview")
    webview_logger.setLevel(logging.INFO)
    webview_logger.propagate = False
    if handler not in webview_logger.handlers:
        webview_logger.addHandler(handler)
    LOGGER.info("%s 启动（WebView2 桌面版）", APP_TITLE)
    return log_path


class WindowsSingleInstance:
    """Per-user-session mutex shared with the tkinter desktop entry point."""

    ERROR_ALREADY_EXISTS = 183

    def __init__(self, name: str = MUTEX_NAME) -> None:
        self.name = name
        self.handle: int | None = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        create_mutex.restype = ctypes.c_void_p
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (ctypes.c_void_p,)
        close_handle.restype = ctypes.c_bool

        ctypes.set_last_error(0)
        handle = create_mutex(None, False, self.name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == self.ERROR_ALREADY_EXISTS:
            close_handle(handle)
            return False
        self.handle = int(handle)
        return True

    def close(self) -> None:
        if not self.handle or os.name != "nt":
            return
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = (ctypes.c_void_p,)
            close_handle.restype = ctypes.c_bool
            close_handle(ctypes.c_void_p(self.handle))
        finally:
            self.handle = None


def _show_native_error(title: str, message: str) -> None:
    """Display a last-resort message without depending on a GUI toolkit."""

    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
            return
        except (AttributeError, OSError):
            pass
    try:
        print(f"{title}: {message}", file=sys.stderr)
    except Exception:
        pass


def _dialog_start_directory(preferred: Path) -> Path:
    """Return an existing folder suitable for a native folder picker."""

    candidates = [preferred, preferred.parent]
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "USERPROFILE"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value))
    candidates.extend((Path.home(), Path.cwd()))
    for candidate in candidates:
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    return Path.cwd()


def _webview2_runtime_version() -> str:
    """Fail fast when the Evergreen WebView2 Runtime is unavailable."""

    if os.name != "nt":
        raise RuntimeError("WebView2 桌面界面仅支持 Windows")
    try:
        import clr
        from webview.util import interop_dll_path

        clr.AddReference(interop_dll_path("Microsoft.Web.WebView2.Core.dll"))
        from Microsoft.Web.WebView2.Core import CoreWebView2Environment

        version = str(CoreWebView2Environment.GetAvailableBrowserVersionString() or "").strip()
    except Exception as exc:
        raise RuntimeError("未检测到可用的 Microsoft Edge WebView2 Runtime") from exc
    if not version:
        raise RuntimeError("未检测到可用的 Microsoft Edge WebView2 Runtime")
    return version


def _enable_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        # Per-monitor-v2 awareness keeps both the WinForms host and CSS pixels
        # crisp when the window moves between displays with different scaling.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass


def _resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parent


def _safe_ui_asset(ui_root: Path, relative: str) -> Path:
    """Resolve one local UI asset without allowing traversal outside steam_ui."""

    candidate = (ui_root / relative).resolve()
    try:
        candidate.relative_to(ui_root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"前端资源路径越界：{relative}") from exc
    if not candidate.is_file():
        raise RuntimeError(f"缺少前端资源：{candidate}")
    return candidate


_STYLE_LINK_RE = re.compile(
    r"<link\b(?=[^>]*\brel=[\"']stylesheet[\"'])(?=[^>]*\bhref=[\"']([^\"']+)[\"'])[^>]*>",
    re.IGNORECASE,
)
_SCRIPT_SRC_RE = re.compile(
    r"<script\b(?=[^>]*\bsrc=[\"']([^\"']+)[\"'])[^>]*>\s*</script>",
    re.IGNORECASE,
)


def _is_local_asset(reference: str) -> bool:
    lowered = reference.strip().lower()
    return bool(lowered) and not (
        lowered.startswith(("http://", "https://", "//", "data:", "javascript:"))
        or ":" in lowered.split("/", 1)[0]
    )


def _escape_inline_script(source: str) -> str:
    # HTML parsers terminate a script element even when </script> appears in a
    # JavaScript string or comment. Escaping the slash preserves JS semantics.
    return re.sub(r"</script", r"<\\/script", source, flags=re.IGNORECASE)


_FETCH_COMPATIBILITY_SHIM = r"""
(() => {
  let readyResolve;
  const ready = new Promise((resolve) => { readyResolve = resolve; });

  const markReady = () => {
    if (window.pywebview?.api) readyResolve(window.pywebview.api);
  };
  window.addEventListener('pywebviewready', markReady, { once: true });
  markReady();

  window.__STEAM_ORGANIZER_DESKTOP__ = true;
  window.steamOrganizerBridgeReady = ready;

  function parseBody(options) {
    if (options?.body == null || options.body === '') return {};
    if (typeof options.body === 'string') return JSON.parse(options.body);
    if (typeof options.body === 'object') return options.body;
    throw new Error('请求内容格式无效');
  }

  function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data ?? {}), {
      status,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    });
  }

  // Backwards compatibility for the existing web front end. New code may call
  // window.pywebview.api directly; no network request is made in either case.
  window.fetch = async (input, options = {}) => {
    const value = typeof input === 'string' ? input : input?.url;
    if (!value || !value.startsWith('/api/')) {
      throw new Error('桌面版不允许外部网络请求');
    }

    const api = await ready;
    const url = new URL(value, 'https://steam-organizer.local/');
    const payload = parseBody(options);
    switch (url.pathname) {
      case '/api/state':
        return jsonResponse(await api.get_state(url.searchParams.get('refresh') === '1'));
      case '/api/plan':
        return jsonResponse(await api.make_plan(payload));
      case '/api/apply':
        return jsonResponse(await api.apply(payload));
      case '/api/restore':
        return jsonResponse(await api.restore());
      case '/api/reveal':
        return jsonResponse(await api.reveal_folder());
      default:
        return jsonResponse({ error: `未知的桌面接口：${url.pathname}` }, 404);
    }
  };
})();
"""


def load_ui_html() -> str:
    """Load and inline local CSS/JS so pywebview needs no HTTP server."""

    ui_root = _resource_root() / "steam_ui"
    index_path = _safe_ui_asset(ui_root, "index.html")
    html = index_path.read_text(encoding="utf-8")

    def inline_style(match: re.Match[str]) -> str:
        reference = match.group(1)
        if not _is_local_asset(reference):
            return match.group(0)
        css = _safe_ui_asset(ui_root, reference).read_text(encoding="utf-8")
        font_licenses = {"p5r.css": "fonts/OFL-BarlowCondensed.txt", "p3r.css": "fonts/OFL-Anton.txt"}
        if reference in font_licenses:
            license_text = _safe_ui_asset(ui_root, font_licenses[reference]).read_text(encoding="utf-8")
            css = "/* Font license (also applies to this embedded copy):\n" + license_text.replace("*/", "* /") + "\n*/\n" + css
        # The desktop document has no base URL. Embed the local font and the
        # two generated character cutouts, using the same traversal guard.
        def inline_binary(asset_match: re.Match[str]) -> str:
            asset_reference = asset_match.group(1)
            mime = {".ttf": "font/ttf", ".webp": "image/webp"}.get(Path(asset_reference).suffix.lower())
            if not _is_local_asset(asset_reference) or not mime:
                return asset_match.group(0)
            payload = _safe_ui_asset(ui_root, asset_reference).read_bytes()
            return 'url("data:' + mime + ';base64,' + base64.b64encode(payload).decode("ascii") + '")'
        css = re.sub(r"url\(['\"]?([^)'\"\s]+\.(?:ttf|webp))['\"]?\)", inline_binary, css)
        css = re.sub(r"</style", r"<\\/style", css, flags=re.IGNORECASE)
        return f'<style data-source="{reference}">\n{css}\n</style>'

    def inline_script(match: re.Match[str]) -> str:
        reference = match.group(1)
        if not _is_local_asset(reference):
            return match.group(0)
        script = _safe_ui_asset(ui_root, reference).read_text(encoding="utf-8")
        return (
            f'<script data-source="{reference}">\n'
            f'{_escape_inline_script(script)}\n</script>'
        )

    html = _STYLE_LINK_RE.sub(inline_style, html)
    html = _SCRIPT_SRC_RE.sub(inline_script, html)
    shim = f"<script>\n{_escape_inline_script(_FETCH_COMPATIBILITY_SHIM)}\n</script>"
    if "</head>" not in html.lower():
        raise RuntimeError("前端 index.html 缺少 </head>")
    html = re.sub(r"</head>", f"{shim}\n</head>", html, count=1, flags=re.IGNORECASE)
    return html


def _settings_path() -> Path:
    return _shared_settings_path()


def _load_saved_steam_root() -> str | None:
    return _shared_load_saved_steam_root(LOGGER)


def _save_steam_root(root: str | Path) -> None:
    _shared_save_steam_root(root)


def _create_organizer() -> Organizer:
    saved_root = _load_saved_steam_root()
    if saved_root:
        try:
            return Organizer(saved_root)
        except Exception:
            LOGGER.warning(
                "已保存的 Steam 目录不再可用，将重新自动检测：%s",
                saved_root,
                exc_info=True,
            )
    return Organizer()


class DesktopApi:
    """Small, validated API exposed to the trusted local JavaScript page.

    pywebview invokes exposed methods on worker threads. Organizer's lock keeps
    scan/plan/write operations serialized, while the WebView UI remains
    responsive and can animate its loading states.
    """

    def __init__(self, organizer: Organizer, log_path: Path) -> None:
        self._organizer = organizer
        self._log_path = log_path
        self._window: Any = None
        self._activity_lock = threading.Lock()
        self._mutation_count = 0

    def _attach_window(self, window: Any) -> None:
        self._window = window

    def set_theme(self, theme: str) -> None:
        """Match the native Windows title bar to the local page's appearance."""
        if theme not in ("light", "dark"):
            raise RuntimeError("未知界面主题")
        if self._window is not None:
            _set_native_title_bar_theme(self._window, dark=theme == "dark")

    def _run(self, label: str, operation: Callable[[], T]) -> T:
        try:
            return operation()
        except SteamError as exc:
            LOGGER.warning("%s失败：%s", label, exc)
            raise RuntimeError(str(exc)) from None
        except Exception as exc:
            LOGGER.exception("%s发生未预期错误", label)
            raise RuntimeError(f"{label}失败：{exc}") from None

    def _change_mutation_count(self, delta: int) -> None:
        with self._activity_lock:
            self._mutation_count = max(0, self._mutation_count + delta)

    def _is_mutation_active(self) -> bool:
        with self._activity_lock:
            return self._mutation_count > 0

    def get_state(self, refresh_metadata: bool = False) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            with self._organizer.lock:
                self._organizer.library.resolve_account()
                return self._organizer.state(refresh_metadata=bool(refresh_metadata))

        return self._run("扫描 Steam", operation)

    def make_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise RuntimeError("预览参数必须是对象")

        def operation() -> dict[str, Any]:
            modes = payload.get("modes") or []
            try:
                developer_min = int(payload.get("developer_min") or 3)
            except (TypeError, ValueError) as exc:
                raise SteamError("厂商最少游戏数必须是整数") from exc
            language = str(payload.get("language") or "schinese")
            scope = str(payload.get("scope") or "library")
            with self._organizer.lock:
                self._organizer.set_language(language)
                return self._organizer.make_plan(modes, developer_min, scope)

        return self._run("生成分类预览", operation)

    def apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise RuntimeError("写入参数必须是对象")

        def operation() -> dict[str, Any]:
            self._change_mutation_count(1)
            try:
                with self._organizer.lock:
                    result = self._organizer.apply(
                        payload.get("plan_id") or "",
                        payload.get("selected") or [],
                    )
                    response = dict(result)
                    try:
                        response["state"] = self._organizer.state()
                    except Exception as exc:
                        LOGGER.exception("写入已完成，但刷新状态失败")
                        response["state_error"] = f"{type(exc).__name__}: {exc}"
                    return response
            finally:
                self._change_mutation_count(-1)

        return self._run("备份并写入 Steam", operation)

    def restore(self) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            self._change_mutation_count(1)
            try:
                with self._organizer.lock:
                    result = self._organizer.restore()
                    response: dict[str, Any] = dict(result)
                    try:
                        response["state"] = self._organizer.state()
                    except Exception as exc:
                        LOGGER.exception("恢复已完成，但刷新状态失败")
                        response["state_error"] = f"{type(exc).__name__}: {exc}"
                    return response
            finally:
                self._change_mutation_count(-1)

        return self._run("恢复 Steam 备份", operation)

    def reveal_folder(self) -> dict[str, str]:
        def operation() -> dict[str, str]:
            with self._organizer.lock:
                folder = self._organizer.library.cloud_path().parent
            if os.name == "nt":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            else:  # pragma: no cover - product target is Windows
                subprocess.Popen(["xdg-open", str(folder)])
            return {"opened": str(folder)}

        return self._run("打开 Steam 配置目录", operation)

    def choose_steam_root(self) -> dict[str, Any] | None:
        if self._window is None:
            raise RuntimeError("桌面窗口尚未就绪")

        def operation() -> dict[str, Any] | None:
            import webview

            current = Path(self._organizer.library.root)
            initial = _dialog_start_directory(current)
            selected = self._window.create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=str(initial),
            )
            if not selected:
                return None
            if isinstance(selected, str):
                chosen = selected
            else:
                chosen = str(selected[0])

            with self._organizer.lock:
                setter = getattr(self._organizer, "set_steam_root", None)
                if not callable(setter):
                    raise SteamError("当前核心版本不支持切换 Steam 目录")
                root = setter(chosen)
                state = self._organizer.state(refresh_metadata=True)
            _save_steam_root(root)
            LOGGER.info("Steam 目录已切换为 %s", root)
            return state

        return self._run("选择 Steam 安装目录", operation)

    def open_log_file(self) -> dict[str, str]:
        def operation() -> dict[str, str]:
            self._log_path.touch(exist_ok=True)
            if os.name == "nt":
                os.startfile(str(self._log_path))  # type: ignore[attr-defined]
            else:  # pragma: no cover - product target is Windows
                subprocess.Popen(["xdg-open", str(self._log_path)])
            return {"opened": str(self._log_path)}

        return self._run("打开运行日志", operation)


def _set_native_title_bar_theme(window: Any, dark: bool = False) -> None:
    """Best-effort matching title bar with native resize/snap behavior."""

    if os.name != "nt":
        return
    try:
        native_handle = window.native.Handle
        hwnd = int(native_handle.ToInt64())
        enabled = ctypes.c_int(int(dark))
        for attribute in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                attribute,
                ctypes.byref(enabled),
                ctypes.sizeof(enabled),
            )
            if result == 0:
                break
    except Exception:
        LOGGER.debug("无法设置原生标题栏主题", exc_info=True)


def _run_webview(log_path: Path) -> None:
    import webview

    webview2_version = _webview2_runtime_version()
    LOGGER.info("检测到 WebView2 Runtime %s", webview2_version)
    organizer = _create_organizer()
    api = DesktopApi(organizer, log_path)
    html = load_ui_html()

    webview.settings["ALLOW_DOWNLOADS"] = False
    webview.settings["ALLOW_FILE_URLS"] = False
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
    webview.settings["REMOTE_DEBUGGING_PORT"] = None
    webview.settings["SHOW_DEFAULT_MENUS"] = False

    window = webview.create_window(
        APP_TITLE,
        html=html,
        js_api=api,
        width=1220,
        height=840,
        min_size=(980, 680),
        resizable=True,
        background_color="#f8f9fb",
        text_select=True,
        zoomable=False,
        draggable=False,
    )
    api._attach_window(window)

    def on_closing() -> bool:
        if not api._is_mutation_active():
            return True
        LOGGER.warning("写入或恢复进行中，拒绝关闭窗口")

        def notify() -> None:
            try:
                window.run_js(
                    "window.dispatchEvent(new CustomEvent('steam-organizer-close-blocked'));"
                )
            except Exception:
                LOGGER.debug("无法发送关闭阻止提示", exc_info=True)

        threading.Thread(target=notify, daemon=True).start()
        return False

    window.events.closing += on_closing
    storage_path = _app_data_dir() / "WebView2"
    storage_path.mkdir(parents=True, exist_ok=True)
    webview.start(
        gui="edgechromium",
        debug=False,
        private_mode=False,
        storage_path=str(storage_path),
    )


def _run_tk_fallback(reason: BaseException) -> None:
    LOGGER.error(
        "WebView2 桌面版无法启动，改用内置 tkinter 回退界面：%s",
        reason,
        exc_info=True,
    )
    tkinter_main = importlib.import_module("steam_desktop").main
    tkinter_main(organizer=_create_organizer())


def main() -> None:
    mutex = WindowsSingleInstance()
    mutex_owned = False
    log_path: Path | None = None
    try:
        try:
            log_path = configure_logging()
        except Exception:
            try:
                log_path = _app_data_dir() / "steam_modern.log"
            except Exception:
                log_path = Path(tempfile.gettempdir()) / "SteamLibraryOrganizer.log"

        if not mutex.acquire():
            _show_native_error(
                APP_TITLE,
                "程序已经在运行。请切换到现有窗口，避免两个实例同时修改 Steam 收藏夹。",
            )
            return
        mutex_owned = True
        _enable_dpi_awareness()

        try:
            _run_webview(log_path)
            return
        except Exception as exc:
            # Release before invoking steam_desktop.main(), which acquires the
            # same named mutex for its own lifetime.
            mutex.close()
            mutex_owned = False
            _run_tk_fallback(exc)
    except Exception as exc:
        details = traceback.format_exc()
        try:
            LOGGER.critical("桌面程序发生致命错误\n%s", details)
        except Exception:
            pass
        _show_native_error(
            f"{APP_TITLE}无法启动",
            f"{exc}\n\n详细日志：{log_path}" if log_path else str(exc),
        )
    finally:
        if mutex_owned:
            mutex.close()


if __name__ == "__main__":
    main()
