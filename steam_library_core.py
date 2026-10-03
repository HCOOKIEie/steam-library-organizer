"""Core logic for the Steam Library Organizer.

Everything here is offline and local: Steam's own client caches are used to
decide which apps to group and what to call them, so the resulting collections
match what the Steam library actually shows (including Simplified Chinese
titles). No API key is required.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import html
import json
import os
import re
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import steam_appinfo

STEAM_DEFAULT = r"D:\steam"
ACCOUNT_BASE = 76561197960265728
WRITE_LOCK_TIMEOUT_SECONDS = 10.0
AUTO_PREFIX = "user-collections.org-"
# Earlier versions of this tool wrote ids under this prefix; they are cleaned up
# too so the library never shows two generations of automatic collections.
LEGACY_PREFIXES = ("user-collections.auto-",)
MANAGED_PREFIXES = (AUTO_PREFIX,) + LEGACY_PREFIXES

_WRITE_LOCK_STATE = threading.local()


class SteamError(RuntimeError):
    """Raised for recoverable Steam-related failures."""


def _normalise_steam_root(root: str | os.PathLike[str]) -> Path:
    """Return an absolute Steam root path suitable for validation."""
    if not isinstance(root, (str, os.PathLike)):
        raise SteamError("Steam 安装目录格式无效")
    raw = os.fspath(root).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        raw = raw[1:-1].strip()
    if not raw:
        raise SteamError("Steam 安装目录不能为空")
    expanded = os.path.expandvars(os.path.expanduser(raw))
    try:
        return Path(expanded).resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise SteamError(f"Steam 安装目录无法解析：{raw}") from exc


def validate_steam_root(root: str | os.PathLike[str]) -> Path:
    """Validate and normalize a Steam installation usable by this tool.

    Merely finding a directory named ``Steam`` is not sufficient.  The
    organizer needs the client executable, account registry, app metadata,
    library folder and per-user data before it can safely scan or write.
    """
    candidate = _normalise_steam_root(root)
    if not candidate.is_dir():
        raise SteamError(f"Steam 安装目录不存在：{candidate}")

    required_files = (
        candidate / "steam.exe",
        candidate / "config" / "loginusers.vdf",
        candidate / "appcache" / "appinfo.vdf",
    )
    required_directories = (
        candidate / "steamapps",
        candidate / "userdata",
    )
    missing = [
        str(path.relative_to(candidate))
        for path in required_files
        if not path.is_file()
    ]
    missing.extend(
        str(path.relative_to(candidate))
        for path in required_directories
        if not path.is_dir()
    )
    if missing:
        raise SteamError(
            f"目录不是可用的 Steam 安装目录：{candidate}；缺少 "
            + "、".join(missing)
        )
    return candidate


def _registry_steam_roots() -> list[Path]:
    """Read Steam install candidates from the Windows registry."""
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:  # pragma: no cover - only possible off Windows
        return []

    roots: list[Path] = []
    locations = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Valve\Steam"),
    )
    views = tuple(
        dict.fromkeys(
            (
                0,
                getattr(winreg, "KEY_WOW64_32KEY", 0),
                getattr(winreg, "KEY_WOW64_64KEY", 0),
            )
        )
    )
    for hive, key_name in locations:
        for view in views:
            try:
                with winreg.OpenKey(
                    hive,
                    key_name,
                    0,
                    winreg.KEY_READ | view,
                ) as key:
                    for value_name in ("SteamPath", "InstallPath", "SteamExe"):
                        try:
                            value, _value_type = winreg.QueryValueEx(key, value_name)
                        except OSError:
                            continue
                        if not isinstance(value, str) or not value.strip():
                            continue
                        path = Path(os.path.expandvars(value.strip().strip('"')))
                        if value_name == "SteamExe" or path.name.lower() == "steam.exe":
                            path = path.parent
                        roots.append(path)
            except OSError:
                continue
    return roots


def _common_steam_roots() -> list[Path]:
    """Return conventional Windows install locations, legacy fallback last."""
    roots: list[Path] = []
    for variable in ("ProgramFiles(x86)", "ProgramW6432", "ProgramFiles"):
        base = os.environ.get(variable)
        if base:
            roots.append(Path(base) / "Steam")
    system_drive = os.environ.get("SystemDrive") or "C:"
    roots.extend(
        (
            Path(system_drive + os.sep) / "Program Files (x86)" / "Steam",
            Path(system_drive + os.sep) / "Program Files" / "Steam",
            Path(STEAM_DEFAULT),
        )
    )
    return roots


def detect_steam_root() -> Path:
    """Find the first strictly valid Steam root on Windows.

    Registry locations are authoritative and therefore checked first, followed
    by conventional install folders and the historical ``D:\\steam`` default.
    Invalid or incomplete candidates are skipped rather than accepted.
    """
    checked: list[Path] = []
    seen: set[str] = set()
    for raw_candidate in (*_registry_steam_roots(), *_common_steam_roots()):
        try:
            candidate = _normalise_steam_root(raw_candidate)
        except SteamError:
            continue
        identity = os.path.normcase(str(candidate))
        if identity in seen:
            continue
        seen.add(identity)
        checked.append(candidate)
        try:
            return validate_steam_root(candidate)
        except SteamError:
            continue
    detail = "、".join(str(path) for path in checked) or "未发现候选目录"
    raise SteamError(
        "未找到可用的 Steam 安装目录。请确认 Steam 已安装并至少登录过一次。"
        f"已检查：{detail}"
    )


def _write_lock_identity(scope: str | Path) -> str:
    """Return one stable kernel/file-lock identity for a Steam installation."""
    path = Path(scope)
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        resolved = Path(os.path.abspath(os.fspath(path)))
    normalized = os.path.normcase(str(resolved))
    return hashlib.sha256(normalized.encode("utf-8", errors="surrogatepass")).hexdigest()


@contextmanager
def _exclusive_write_lock(
    scope: str | Path,
    timeout: float = WRITE_LOCK_TIMEOUT_SECONDS,
):
    """Serialize collection writes across processes and remain thread-reentrant.

    The lock is keyed by Steam root rather than the currently selected account.
    This deliberately serializes all account collection writes under one Steam
    installation, including the account re-resolution performed while applying
    a saved plan. Windows uses a kernel mutex, which is released automatically
    when a process terminates. A flock-backed lock file is used elsewhere so
    tests and non-Windows development keep the same safety contract.
    """
    identity = _write_lock_identity(scope)
    held = getattr(_WRITE_LOCK_STATE, "held", None)
    if held is None:
        held = {}
        _WRITE_LOCK_STATE.held = held
    depth = held.get(identity, 0)
    if depth:
        held[identity] = depth + 1
        try:
            yield
        finally:
            if held[identity] == 1:
                held.pop(identity, None)
            else:
                held[identity] -= 1
        return

    try:
        timeout_seconds = max(0.0, float(timeout))
    except (TypeError, ValueError) as exc:
        raise SteamError("跨进程写入锁超时时间无效") from exc

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        create_mutex.restype = wintypes.HANDLE
        wait_for_single_object = kernel32.WaitForSingleObject
        wait_for_single_object.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        wait_for_single_object.restype = wintypes.DWORD
        release_mutex = kernel32.ReleaseMutex
        release_mutex.argtypes = (wintypes.HANDLE,)
        release_mutex.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL

        name = rf"Local\SteamLibraryOrganizer.CloudWrite.v1.{identity}"
        handle = create_mutex(None, False, name)
        if not handle:
            error = ctypes.WinError(ctypes.get_last_error())
            raise SteamError(f"无法创建跨进程写入锁：{error}") from error

        wait_ms = min(int(timeout_seconds * 1000), 0xFFFFFFFE)
        acquired = False
        try:
            wait_result = wait_for_single_object(handle, wait_ms)
            if wait_result in (0x00000000, 0x00000080):  # signalled / abandoned
                acquired = True
            elif wait_result == 0x00000102:  # timeout
                raise SteamError(
                    "另一个 Steam 分类工具进程正在写入或恢复，请等待其完成后重试"
                )
            else:
                error = ctypes.WinError(ctypes.get_last_error())
                raise SteamError(f"无法取得跨进程写入锁：{error}") from error

            held[identity] = 1
            try:
                yield
            finally:
                held.pop(identity, None)
        finally:
            if acquired:
                release_mutex(handle)
            close_handle(handle)
        return

    # Portable development/test fallback. The lock file is intentionally kept:
    # deleting a lock file can split waiters across different inodes.
    import fcntl

    lock_path = Path(tempfile.gettempdir()) / f"steam-library-organizer-{identity}.lock"
    try:
        stream = lock_path.open("a+b")
    except OSError as exc:
        raise SteamError(f"无法创建跨进程写入锁：{exc}") from exc
    deadline = time.monotonic() + timeout_seconds
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SteamError(
                        "另一个 Steam 分类工具进程正在写入或恢复，请等待其完成后重试"
                    )
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        held[identity] = 1
        try:
            yield
        finally:
            held.pop(identity, None)
    finally:
        if acquired:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def _is_managed(key: str) -> bool:
    return any(key.startswith(prefix) for prefix in MANAGED_PREFIXES)

GENRE_NAMES = {
    "1": "动作",
    "2": "策略",
    "3": "角色扮演",
    "4": "休闲",
    "9": "竞速",
    "18": "体育",
    "23": "独立",
    "25": "冒险",
    "28": "模拟",
    "29": "大型多人在线",
    "37": "免费开玩",
    "51": "动画与建模",
    "52": "音频制作",
    "53": "设计与插画",
    "54": "教育",
    "55": "照片编辑",
    "56": "软件培训",
    "57": "实用工具",
    "58": "视频制作",
    "59": "网页发布",
    "60": "游戏开发",
    "70": "抢先体验",
}

FORM_NAMES = {
    "game": "游戏",
    "dlc": "追加内容",
    "tool": "工具",
    "demo": "试玩",
    "music": "原声带",
    "video": "视频",
    "application": "软件",
    "config": "配置",
    "hardware": "硬件",
    "series": "合集",
    "mod": "模组",
    "beta": "测试版",
}

MODE_LABELS = {
    "initial": "首字母",
    "genre": "种类",
    "form": "形式",
    "developer": "开发商",
    "publisher": "发行商",
    "state": "状态",
    "recent": "最近游玩",
    "playtime": "时长",
}

SCOPES = ("library", "games", "all")
LIBRARY_FORMS = frozenset({"game", "application", "music", "series"})
GAME_FORMS = frozenset({"game"})
# Valve's Spacewar is an SDK/test app, not a user library title.
EXCLUDED_LIBRARY_APPIDS = frozenset({480})

# Steam does not store purchase dates locally, so "入库时间" is answered with
# the closest honest signal: the last time the client saw the app launched.


def _read_vdf_value(text: str, key: str) -> str | None:
    match = re.search(r'"' + re.escape(key) + r'"\s+"([^"]*)"', text)
    return match.group(1) if match else None


def initial_for(name: str) -> str:
    """A-Z bucket for a display name; Chinese titles use their pinyin initial."""
    for char in (name or "").strip():
        if char.isascii() and char.isalpha():
            return char.upper()
        if char.isascii() and char.isdigit():
            return "#"
        if "\u4e00" <= char <= "\u9fff":
            try:
                from pypinyin import lazy_pinyin
            except ImportError:
                return "中文"
            for syllable in lazy_pinyin(name.strip(), errors="ignore"):
                if syllable and syllable[0].isalpha():
                    return syllable[0].upper()
            return "中文"
    return "#"


def _tidy(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", str(text or ""))
    text = unicodedata.normalize("NFC", html.unescape(text))
    return re.sub(r"\s+", " ", text).strip()


class SteamLibrary:
    """Reads Steam's local state and writes library collections."""

    def __init__(self, root: str | Path = STEAM_DEFAULT, language: str = "schinese"):
        self.root = Path(root)
        self.language = language
        self.write_lock_timeout = WRITE_LOCK_TIMEOUT_SECONDS
        self._appinfo: dict[int, dict] | None = None
        self._appinfo_fingerprint: tuple[str, int | None, int | None, str] | None = None
        self._appinfo_attempt_fingerprint: tuple[str, int | None, int | None, str] | None = None
        self.appinfo_error: str | None = None
        self.steamid64: str | None = None
        self.account_id: str | None = None

    # ---------------------------------------------------------------- account
    def resolve_account(self) -> str:
        login = self.root / "config" / "loginusers.vdf"
        if not login.exists():
            raise SteamError(f"找不到 loginusers.vdf：{login}")
        text = login.read_text(encoding="utf-8", errors="ignore")
        blocks = re.findall(r'"(7656119\d{10})"\s*\{(.*?)\n\t\}', text, re.S)
        if not blocks:
            raise SteamError("loginusers.vdf 中没有找到账号记录")
        chosen = None
        for steamid, body in blocks:
            if re.search(r'"AutoLogin"\s+"1"', body) or re.search(r'"MostRecent"\s+"1"', body):
                chosen = steamid
                break
        self.steamid64 = chosen or blocks[0][0]
        self.account_id = str(int(self.steamid64) - ACCOUNT_BASE)
        return self.account_id

    @property
    def config_dir(self) -> Path:
        if not self.account_id:
            self.resolve_account()
        return self.root / "userdata" / str(self.account_id) / "config"

    @contextmanager
    def write_lock(self):
        """Hold the cross-process mutation lock for this Steam installation."""
        with _exclusive_write_lock(self.root, self.write_lock_timeout):
            yield

    # ------------------------------------------------------------------ state
    def local_appids(self) -> set[int]:
        """Apps Steam records local state for (played, installed, configured)."""
        path = self.config_dir / "localconfig.vdf"
        if not path.exists():
            return set()
        text = path.read_text(encoding="utf-8", errors="ignore")
        pos = text.find('"apps"')
        if pos < 0:
            return set()
        # Keep this broad local-state source compatible with the historical
        # candidate set; low system appids are still available through the
        # stronger library cache, install manifests, or an API session.
        return {int(m) for m in re.findall(r'(?m)^\t{5}"(\d{3,7})"\s*$', text[pos:])}

    def cached_appids(self) -> set[int]:
        """Apps the client has library cache entries for - includes shared games."""
        folder = self.config_dir / "librarycache"
        if not folder.is_dir():
            return set()
        found = set()
        for entry in folder.glob("*.json"):
            if entry.stem.isdigit():
                found.add(int(entry.stem))
        return found

    def installed_appids(self) -> set[int]:
        found = set()
        for folder in self.library_folders():
            for manifest in (folder / "steamapps").glob("appmanifest_*.acf"):
                text = manifest.read_text(encoding="utf-8", errors="ignore")
                appid = _read_vdf_value(text, "appid")
                if appid and appid.isdigit():
                    found.add(int(appid))
        return found

    def library_folders(self) -> list[Path]:
        folders = [self.root]
        manifest = self.root / "steamapps" / "libraryfolders.vdf"
        if manifest.exists():
            text = manifest.read_text(encoding="utf-8", errors="ignore")
            for raw in re.findall(r'"path"\s+"([^"]+)"', text):
                candidate = Path(raw.replace("\\\\", "\\"))
                if candidate not in folders:
                    folders.append(candidate)
        return folders

    def playtime(self) -> dict[int, int]:
        """Minutes played per app, from localconfig."""
        path = self.config_dir / "localconfig.vdf"
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8", errors="ignore")
        pos = text.find('"apps"')
        if pos < 0:
            return {}
        out: dict[int, int] = {}
        for match in re.finditer(
            r'(?m)^\t{5}"(\d+)"\s*$\n\t{5}\{(.*?)\n\t{5}\}',
            text[pos:],
            re.S,
        ):
            appid = int(match.group(1))
            minutes = _read_vdf_value(match.group(2), "Playtime")
            if minutes and minutes.isdigit():
                out[appid] = int(minutes)
        return out

    def last_played(self) -> dict[int, int]:
        """Unix timestamp of the last launch, per app, from localconfig."""
        path = self.config_dir / "localconfig.vdf"
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8", errors="ignore")
        pos = text.find('"apps"')
        if pos < 0:
            return {}
        out: dict[int, int] = {}
        for match in re.finditer(
            r'(?m)^\t{5}"(\d+)"\s*$\n\t{5}\{(.*?)\n\t{5}\}',
            text[pos:],
            re.S,
        ):
            stamp = _read_vdf_value(match.group(2), "LastPlayed")
            if stamp and stamp.isdigit() and int(stamp) > 0:
                out[int(match.group(1))] = int(stamp)
        return out

    def _appinfo_source_fingerprint(self) -> tuple[str, int | None, int | None, str]:
        source = self.root / "appcache" / "appinfo.vdf"
        try:
            source_stat = source.stat()
        except OSError:
            return (str(source.resolve()), None, None, self.language)
        return (
            str(source.resolve()),
            source_stat.st_size,
            source_stat.st_mtime_ns,
            self.language,
        )

    def appinfo(self, refresh: bool = False) -> dict[int, dict]:
        """Return metadata, refreshing when appinfo.vdf changes.

        A failed refresh never replaces already parsed metadata. The failed
        source fingerprint is remembered so ordinary catalog reads do not keep
        retrying the same broken file; callers can still force a retry with
        ``refresh=True``.
        """
        fingerprint = self._appinfo_source_fingerprint()
        if (
            not refresh
            and self._appinfo is not None
            and self._appinfo_attempt_fingerprint == fingerprint
        ):
            return self._appinfo

        previous = self._appinfo
        try:
            loaded = steam_appinfo.load_cached(self.root, self.language)
        except Exception as exc:
            self._appinfo_attempt_fingerprint = fingerprint
            self.appinfo_error = f"{type(exc).__name__}: {exc}"
            if previous is None:
                self._appinfo = {}
            return self._appinfo or {}

        self._appinfo = loaded
        self._appinfo_fingerprint = fingerprint
        self._appinfo_attempt_fingerprint = fingerprint
        self.appinfo_error = None
        return loaded

    def refresh_appinfo(self) -> dict[int, dict]:
        """Explicitly retry appinfo parsing even for an unchanged fingerprint."""
        return self.appinfo(refresh=True)

    def owned_games(self, api_key: str, timeout: int = 25) -> list[dict]:
        """Optional: exact owned-game list from Steam's official Web API."""
        if not api_key.strip():
            raise SteamError("未填写 API Key")
        if not self.steamid64:
            self.resolve_account()
        query = urllib.parse.urlencode(
            {
                "key": api_key.strip(),
                "steamid": self.steamid64,
                "format": "json",
                "include_appinfo": 1,
                "include_played_free_games": 1,
            }
        )
        url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?" + query
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise SteamError(f"HTTP {exc.code} {exc.reason}")
        except urllib.error.URLError as exc:
            raise SteamError(f"无法连接 Steam：{exc.reason}")
        except TimeoutError:
            raise SteamError("请求超时")
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise SteamError("Steam 接口返回了无法解析的数据") from exc
        if not isinstance(payload, dict):
            raise SteamError("Steam 接口返回格式异常")
        response_data = payload.get("response") or {}
        if not isinstance(response_data, dict):
            raise SteamError("Steam 接口返回格式异常")
        games = response_data.get("games") or []
        if not isinstance(games, list):
            raise SteamError("Steam 接口返回的游戏列表格式异常")
        if not games:
            raise SteamError("接口没有返回游戏，请检查隐私设置或 API Key")
        return games

    # --------------------------------------------------------------- catalog
    def source_appids(self, extra_appids: set[int] | None = None) -> dict[str, set[int]]:
        """Return local evidence separately instead of conflating it with ownership."""
        extra: set[int] = set()
        for value in extra_appids or set():
            try:
                appid = int(value)
            except (TypeError, ValueError):
                continue
            if appid > 0:
                extra.add(appid)
        return {
            "local": self.local_appids(),
            "cached": self.cached_appids(),
            "installed": self.installed_appids(),
            "session": extra,
        }

    def scoped_appids(
        self,
        extra_appids: set[int] | None = None,
        external_games: dict[int, dict] | None = None,
    ) -> dict[str, set[int]]:
        """Build the three user-facing candidate scopes.

        ``library`` deliberately omits helpers, tools, demos, betas and records
        without usable appinfo metadata. ``games`` is stricter still. ``all``
        preserves the historical union for diagnostics and advanced users.
        """
        sources = self.source_appids(extra_appids)
        all_ids = {appid for values in sources.values() for appid in values if appid > 0}
        strong_ids = sources["cached"] | sources["installed"] | sources["session"]
        external: dict[int, dict] = {}
        for raw_id, game in (external_games or {}).items():
            try:
                appid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if isinstance(game, dict):
                external[appid] = game
        info = self.appinfo()
        unresolved: set[int] = set()
        library: set[int] = set()
        games: set[int] = set()
        auxiliary: set[int] = set()
        local_only: set[int] = set()
        for appid in all_ids:
            meta = info.get(appid) or {}
            form = str(meta.get("type") or "").lower()
            name = _tidy(meta.get("name") or meta.get("name_en") or "")
            remote_name = _tidy((external.get(appid) or {}).get("name") or "")
            if appid in sources["session"] and remote_name and (not form or not name):
                # GetOwnedGames only returns playable library apps. It is a
                # stronger signal than a missing/stale local appinfo record.
                form = "game"
                name = name or remote_name
            if not form or not name:
                unresolved.add(appid)
                continue
            if form in LIBRARY_FORMS:
                if appid in strong_ids and appid not in EXCLUDED_LIBRARY_APPIDS:
                    library.add(appid)
                    if form in GAME_FORMS:
                        games.add(appid)
                elif appid not in EXCLUDED_LIBRARY_APPIDS:
                    local_only.add(appid)
            else:
                auxiliary.add(appid)
        return {
            "library": library,
            "games": games,
            "all": all_ids,
            "unresolved": unresolved,
            "auxiliary": auxiliary,
            "local_only": local_only,
            "excluded": all_ids & EXCLUDED_LIBRARY_APPIDS,
        }

    def candidates(
        self,
        extra_appids: set[int] | None = None,
        scope: str = "library",
        *,
        external_games: dict[int, dict] | None = None,
    ) -> set[int]:
        if scope not in SCOPES:
            raise SteamError(f"未知条目范围：{scope}")
        return self.scoped_appids(extra_appids, external_games)[scope]

    def catalog(
        self,
        extra_appids: set[int] | None = None,
        scope: str = "library",
        external_games: dict[int, dict] | None = None,
    ) -> dict[int, dict]:
        """Merge metadata and activity for one explicit candidate scope."""
        external: dict[int, dict] = {}
        for raw_id, raw_game in (external_games or {}).items():
            try:
                appid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if appid > 0 and isinstance(raw_game, dict):
                external[appid] = raw_game
        combined_extra = set(extra_appids or set()) | set(external)

        info = self.appinfo()
        playtime = self.playtime()
        last_played = self.last_played()
        installed = self.installed_appids()
        local_ids = self.local_appids()
        cached_ids = self.cached_appids()
        known = local_ids | cached_ids
        out: dict[int, dict] = {}
        for appid in sorted(
            self.candidates(combined_extra, scope, external_games=external)
        ):
            meta = info.get(appid) or {}
            remote = external.get(appid) or {}
            name = _tidy(
                meta.get("name")
                or remote.get("name")
                or meta.get("name_en")
                or ""
            )
            form = str(meta.get("type") or "").lower()
            if not form and remote.get("name"):
                form = "game"

            remote_playtime = remote.get("playtime_forever")
            remote_last_played = remote.get("rtime_last_played")
            playtime_values = [playtime[appid]] if appid in playtime else []
            last_played_values = [last_played[appid]] if appid in last_played else []
            if isinstance(remote_playtime, (int, float)) and remote_playtime >= 0:
                playtime_values.append(int(remote_playtime))
            if isinstance(remote_last_played, (int, float)) and remote_last_played >= 0:
                last_played_values.append(int(remote_last_played))

            developers = [
                value
                for value in (_tidy(v) for v in (meta.get("developers") or []))
                if value
            ]
            publishers = [
                value
                for value in (_tidy(v) for v in (meta.get("publishers") or []))
                if value
            ]
            developer = _tidy(meta.get("developer") or "")
            publisher = _tidy(meta.get("publisher") or "")
            if developer and developer not in developers:
                developers.insert(0, developer)
            if publisher and publisher not in publishers:
                publishers.insert(0, publisher)

            out[appid] = {
                "appid": appid,
                "name": name or f"App {appid}",
                "named": bool(name),
                "form": form,
                "genres": [str(value) for value in (meta.get("genres") or [])],
                "primary_genre": str(meta.get("primary_genre") or ""),
                "developer": developers[0] if developers else developer,
                "publisher": publishers[0] if publishers else publisher,
                "developers": developers,
                "publishers": publishers,
                "release_date": meta.get("release_date") or "",
                "installed": appid in installed,
                "known_locally": appid in known,
                "sources": {
                    "local": appid in local_ids,
                    "cached": appid in cached_ids,
                    "installed": appid in installed,
                    "session": appid in combined_extra,
                },
                "playtime": max(playtime_values, default=0),
                "playtime_known": bool(playtime_values),
                "last_played": max(last_played_values, default=0),
                "last_played_known": bool(last_played_values),
            }
        return out

    # ---------------------------------------------------------------- groups
    def build_groups(
        self,
        modes: list[str],
        extra_appids: set[int] | None = None,
        developer_min: int = 2,
        *,
        scope: str = "library",
        catalog: dict[int, dict] | None = None,
    ) -> list[dict]:
        catalog = catalog if catalog is not None else self.catalog(extra_appids, scope)
        groups: dict[tuple[str, str], list[int]] = {}

        # Companies are only worth their own collection when they own several
        # games; the long tail is folded into one bucket so the left bar stays
        # usable instead of sprouting hundreds of one-game entries.
        company_counts: dict[str, dict[str, int]] = {}
        for mode in ("developer", "publisher"):
            if mode not in modes:
                continue
            tally: dict[str, int] = {}
            for item in catalog.values():
                name = item[mode]
                if name:
                    tally[name] = tally.get(name, 0) + 1
            company_counts[mode] = tally

        for appid, item in catalog.items():
            for mode in modes:
                for bucket in self._buckets(mode, item):
                    if mode in company_counts:
                        tally = company_counts[mode]
                        if bucket not in tally or tally.get(bucket, 0) < developer_min:
                            bucket = "其他" + MODE_LABELS[mode]
                    groups.setdefault((mode, bucket), []).append(appid)

        result = []
        for (mode, bucket), appids in sorted(groups.items()):
            result.append(
                {
                    "id": mode + ":" + bucket,
                    "mode": mode,
                    "bucket": bucket,
                    "name": f"{MODE_LABELS.get(mode, mode)} · {bucket}",
                    "appids": sorted(set(appids)),
                    "count": len(set(appids)),
                }
            )
        return result

    @staticmethod
    def _bucket(mode: str, item: dict) -> str | None:
        """Compatibility helper returning the first bucket for a mode."""
        buckets = SteamLibrary._buckets(mode, item)
        return buckets[0] if buckets else None

    @staticmethod
    def _buckets(mode: str, item: dict) -> list[str]:
        if mode == "initial":
            if not item["named"]:
                return ["资料缺失"]
            initial = initial_for(item["name"])
            return ["数字/符号" if initial == "#" else initial]
        if mode == "genre":
            if not item.get("named") or not item.get("form"):
                return ["资料缺失"]
            if item.get("form") != "game":
                return ["非游戏内容"]
            genres = [GENRE_NAMES.get(str(g)) for g in item["genres"]]
            genres = list(dict.fromkeys(g for g in genres if g))
            if not genres:
                return ["未分类题材"]
            return genres
        if mode == "form":
            form = FORM_NAMES.get(item["form"])
            return [form or ("其他" if item["named"] else "资料缺失")]
        if mode == "developer":
            return [item["developer"] or ("未标注开发商" if item["named"] else "资料缺失")]
        if mode == "publisher":
            return [item["publisher"] or ("未标注发行商" if item["named"] else "资料缺失")]
        if mode == "state":
            return ["已安装" if item["installed"] else "未安装"]
        if mode == "recent":
            if not item.get("last_played_known", True):
                return ["游玩记录未知"]
            stamp = item.get("last_played") or 0
            if not stamp:
                return ["从未启动"]
            days = max(0, (time.time() - stamp) / 86400)
            if days <= 30:
                return ["最近一个月"]
            if days <= 180:
                return ["最近半年"]
            if days <= 365:
                return ["最近一年"]
            return ["一年以上未玩"]
        if mode == "playtime":
            if not item.get("playtime_known", True):
                return ["游玩时长未知"]
            hours = item["playtime"] / 60
            if hours >= 100:
                return ["100 小时以上"]
            if hours >= 20:
                return ["20-100 小时"]
            if hours >= 1:
                return ["1-20 小时"]
            return ["几乎没玩"]
        return []

    # ----------------------------------------------------------------- write
    def cloud_path(self) -> Path:
        return self.config_dir / "cloudstorage" / "cloud-storage-namespace-1.json"

    def current_collections(self) -> list[dict]:
        path = self.cloud_path()
        if not path.exists():
            return []
        try:
            records = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SteamError(f"Steam 收藏夹文件无法读取：{exc}") from exc
        if not isinstance(records, list):
            raise SteamError("Steam 收藏夹文件格式异常")
        out = []
        for record in records:
            if not (isinstance(record, list) and len(record) == 2):
                continue
            key, meta = record
            if (
                isinstance(key, str)
                and key.startswith("user-collections.")
                and isinstance(meta, dict)
            ):
                try:
                    value = json.loads(meta.get("value") or "{}")
                except Exception:
                    continue
                if not isinstance(value, dict):
                    continue
                added = value.get("added")
                out.append(
                    {
                        "key": key,
                        "id": value.get("id", ""),
                        "name": value.get("name", ""),
                        "count": len(added) if isinstance(added, list) else 0,
                        "ours": _is_managed(key),
                    }
                )
        return out

    def _backup_bytes(self, payload: bytes, label: str = "") -> Path:
        path = self.cloud_path()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        middle = f".{label}" if label else ""
        for attempt in range(100):
            extra = f"-{attempt}" if attempt else ""
            backup = path.with_name(
                f"{path.name}{middle}.{stamp}{extra}.bak"
            )
            try:
                with backup.open("xb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                return backup
            except FileExistsError:
                continue
        raise SteamError("无法创建唯一的 Steam 收藏夹备份文件")

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=path.name + ".",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _backup_kind(self, entry: Path) -> str | None:
        path = self.cloud_path()
        stamp = r"\d{8}-\d{6}(?:-\d{6})?(?:-\d+)?"
        normal = re.compile(re.escape(path.name) + rf"\.{stamp}\.bak$")
        pre_restore = re.compile(
            re.escape(path.name) + rf"\.pre-restore\.{stamp}\.bak$"
        )
        if normal.fullmatch(entry.name):
            return "normal"
        if pre_restore.fullmatch(entry.name):
            return "pre-restore"
        return None

    def _tool_backups(self) -> list[Path]:
        path = self.cloud_path()
        return sorted(
            (
                entry
                for entry in path.parent.glob(path.name + ".*.bak")
                if self._backup_kind(entry) is not None
            ),
            key=lambda entry: (entry.stat().st_mtime_ns, entry.name),
        )

    def _normal_backups(self) -> list[Path]:
        return [entry for entry in self._tool_backups() if self._backup_kind(entry) == "normal"]

    def _restore_candidates(self) -> list[Path]:
        # The newest pre-restore snapshot is deliberately eligible: invoking
        # restore again then undoes the previous restore.
        return self._tool_backups()

    def apply_groups(self, groups: list[dict], keep_backups: int = 5) -> dict:
        """Apply groups while serializing all collection writers."""
        with self.write_lock():
            return self._apply_groups_locked(groups, keep_backups)

    def _apply_groups_locked(self, groups: list[dict], keep_backups: int) -> dict:
        path = self.cloud_path()
        if not path.exists():
            raise SteamError(f"找不到 Steam 收藏夹文件：{path}")
        original = path.read_bytes()
        try:
            records = json.loads(original.decode("utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise SteamError(f"Steam 收藏夹文件无法读取：{exc}") from exc
        if not isinstance(records, list):
            raise SteamError("Steam 收藏夹文件格式异常")

        prepared: list[tuple[str, list[int]]] = []
        seen_names: set[str] = set()
        for group in groups:
            if not isinstance(group, dict):
                raise SteamError("分类计划格式异常")
            name = str(group.get("name") or "").strip()
            raw_appids = group.get("appids")
            if not name or not isinstance(raw_appids, list):
                raise SteamError("分类计划缺少名称或 AppID")
            if name in seen_names:
                raise SteamError(f"分类计划包含重复名称：{name}")
            try:
                appids = sorted({int(value) for value in raw_appids if int(value) > 0})
            except (TypeError, ValueError) as exc:
                raise SteamError(f"分类 {name} 包含无效 AppID") from exc
            if not appids:
                continue
            seen_names.add(name)
            prepared.append((name, appids))

        if not prepared:
            raise SteamError("分类计划中没有可写入的条目")

        backup = self._backup_bytes(original)

        records = [
            record
            for record in records
            if not (
                isinstance(record, list)
                and len(record) == 2
                and isinstance(record[0], str)
                and _is_managed(record[0])
            )
        ]
        now = int(time.time())
        written = 0
        for name, appids in prepared:
            digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]
            collection_id = "org-" + digest
            key = "user-collections." + collection_id
            value = json.dumps(
                {
                    "id": collection_id,
                    "name": name,
                    "added": appids,
                    "removed": [],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            records.append(
                [
                    key,
                    {
                        "key": key,
                        "value": value,
                        "timestamp": now,
                        "version": "366",
                    },
                ]
            )
            written += 1

        encoded = json.dumps(
            records,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            self._atomic_write(path, encoded)
        except Exception:
            # The just-created backup is byte-for-byte the still-current file
            # when replacement fails, so keeping it only creates a no-op
            # restore candidate.
            try:
                backup.unlink()
            except OSError:
                pass
            raise
        self._prune_backups(keep_backups)
        return {
            "backup": str(backup),
            "collections": written,
            "apps": len({appid for _, appids in prepared for appid in appids}),
        }

    def _prune_backups(self, keep: int) -> None:
        normal = self._normal_backups()
        pre_restore = [
            entry
            for entry in self._tool_backups()
            if self._backup_kind(entry) == "pre-restore"
        ]
        keep = max(0, int(keep))
        stale_normal = normal if keep == 0 else normal[:-keep]
        # Undo snapshots have their own one-level retention and never consume
        # slots from the ordinary rolling backup history.
        stale_pre_restore = pre_restore[:-1]
        for stale in (*stale_normal, *stale_pre_restore):
            try:
                stale.unlink()
            except OSError:
                pass

    def restore_latest(self, keep_backups: int = 5) -> dict[str, str | None]:
        """Restore the latest useful backup under the collection write lock."""
        with self.write_lock():
            return self._restore_latest_locked(keep_backups)

    def _restore_latest_locked(self, keep_backups: int) -> dict[str, str | None]:
        backups = self._restore_candidates()
        if not backups:
            raise SteamError("没有可用的备份")

        path = self.cloud_path()
        current = path.read_bytes() if path.exists() else None
        current_parsed = None
        if current is not None:
            try:
                candidate_current = json.loads(current.decode("utf-8-sig"))
                if isinstance(candidate_current, list):
                    current_parsed = candidate_current
            except (UnicodeError, json.JSONDecodeError):
                pass

        latest = None
        restored = None
        for candidate in reversed(backups):
            try:
                candidate_bytes = candidate.read_bytes()
                candidate_parsed = json.loads(candidate_bytes.decode("utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if not isinstance(candidate_parsed, list):
                continue
            if current is not None:
                same_content = (
                    candidate_parsed == current_parsed
                    if current_parsed is not None
                    else candidate_bytes == current
                )
                if same_content:
                    continue
            latest = candidate
            restored = candidate_bytes
            break

        if latest is None or restored is None:
            raise SteamError("没有与当前收藏夹不同的有效备份")

        safety_backup = None
        if path.exists():
            safety_backup = self._backup_bytes(current or b"", "pre-restore")
        try:
            self._atomic_write(path, restored)
        except Exception:
            if safety_backup is not None:
                try:
                    safety_backup.unlink()
                except OSError:
                    pass
            raise

        # A consumed undo snapshot is replaced by the fresh safety snapshot,
        # keeping the undo/redo chain intentionally one level deep.
        if self._backup_kind(latest) == "pre-restore":
            try:
                latest.unlink()
            except OSError:
                pass
        self._prune_backups(keep_backups)
        return {
            "restored": str(latest),
            "safety_backup": str(safety_backup) if safety_backup is not None else None,
        }
