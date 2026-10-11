"""Native Windows desktop UI for the Steam Library Organizer.

The window uses only Python's standard-library tkinter/ttk widgets.  It calls
the same Organizer service as the local web UI, but never starts an HTTP
server.  Reading, planning, writing, and restoring run on daemon worker
threads; all tkinter access stays on the main thread.
"""

from __future__ import annotations

import ctypes
import logging
import os
import queue
import threading
import time
import traceback
import tkinter as tk
import tkinter.font as tkfont
from collections import OrderedDict
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from steam_settings import app_data_dir, load_saved_steam_root, save_steam_root
from steam_web import Organizer


APP_TITLE = "Steam 游戏库整理"
LOGGER = logging.getLogger("steam_library_organizer.desktop")
MUTEX_NAME = r"Local\SteamLibraryOrganizer.Desktop.v1"

COLORS = {
    "bg": "#0c0f14",
    "panel": "#151a22",
    "panel_raised": "#1c222c",
    "panel_hover": "#242c38",
    "border": "#2a313d",
    "border_strong": "#3a4554",
    "text": "#f1f4f8",
    "muted": "#9da8b7",
    "accent": "#1684e8",
    "accent_hover": "#2494f5",
    "accent_soft": "#142b42",
    "good": "#56d17b",
    "good_soft": "#173224",
    "warn": "#efb24b",
    "warn_soft": "#382b18",
    "danger": "#ff7770",
    "danger_soft": "#402124",
}

MODE_DEFS = OrderedDict(
    [
        ("initial", ("首字母", "拼音 / A–Z")),
        ("genre", ("游戏类型", "同一游戏可进入多个类型")),
        ("form", ("条目形式", "游戏 / DLC / 工具")),
        ("developer", ("开发商", "按开发团队分组")),
        ("publisher", ("发行商", "按发行公司分组")),
        ("state", ("安装状态", "已安装 / 未安装")),
        ("recent", ("最近游玩", "按最后启动时间")),
        ("playtime", ("游玩时长", "按累计小时")),
    ]
)

MODE_TITLES = {key: value[0] for key, value in MODE_DEFS.items()}

LANGUAGES = OrderedDict(
    [
        ("简体中文", "schinese"),
        ("繁体中文", "tchinese"),
        ("English", "english"),
    ]
)

SCOPE_DEFS = OrderedDict(
    [
        ("library", ("游戏库", "推荐：Steam 库中可确认的条目")),
        ("games", ("仅游戏", "排除 DLC、工具和辅助内容")),
        ("all", ("全部本地记录", "包含资料缺失、工具与历史缓存")),
    ]
)


def configure_logging() -> Path:
    """Append diagnostics to LocalAppData and rotate bounded history."""

    log_path = app_data_dir() / "steam_desktop.log"

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
    LOGGER.info("%s 启动", APP_TITLE)
    return log_path


def _create_organizer() -> Organizer:
    """Create an organizer using the same saved root as the WebView2 shell."""

    saved_root = load_saved_steam_root(LOGGER)
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


class WindowsSingleInstance:
    """Per-user-session named mutex used to prevent concurrent writers."""

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


def enable_windows_dpi_awareness() -> None:
    """Opt in to crisp scaling without failing on older Windows releases."""

    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def enable_dark_title_bar(root: tk.Tk) -> None:
    """Ask DWM for a dark title bar; this is cosmetic and best-effort."""

    if os.name != "nt":
        return
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(enabled),
                ctypes.sizeof(enabled),
            )
            if result == 0:
                break
    except (AttributeError, OSError, tk.TclError):
        pass


def format_number(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def as_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


class ScrollableFrame(tk.Frame):
    """A vertically scrollable frame that keeps normal child widgets."""

    def __init__(self, master: tk.Misc, *, background: str) -> None:
        super().__init__(master, background=background)
        self.canvas = tk.Canvas(
            self,
            background=background,
            borderwidth=0,
            highlightthickness=0,
        )
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.interior = tk.Frame(self.canvas, background=background)
        self.window_id = self.canvas.create_window((0, 0), window=self.interior, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.interior.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_width)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _sync_scroll_region(self, _event: tk.Event[Any]) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_width(self, event: tk.Event[Any]) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _bind_wheel(self, _event: tk.Event[Any]) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_wheel(self, _event: tk.Event[Any]) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event[Any]) -> None:
        if self.canvas.bbox("all") is None:
            return
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def clear(self) -> None:
        for child in self.interior.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)


class SteamDesktopApp:
    """Main tkinter application controller."""

    def __init__(self, root: tk.Tk, organizer: Organizer | None = None) -> None:
        self.root = root
        self.organizer = organizer or _create_organizer()
        self._closed = False
        self._result_queue: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self._work_queue: queue.Queue[Any] = queue.Queue()
        self._poll_after: str | None = None
        self._periodic_after: str | None = None
        self.busy_task: str | None = None
        self._close_when_idle = False
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="steam-organizer-worker",
            daemon=True,
        )
        self._worker_thread.start()

        self.state_data: dict[str, Any] = {}
        self.steam_running: bool | None = None
        self.plan: list[dict[str, Any]] = []
        self.plan_id: str | None = None
        self.plan_summary: dict[str, Any] = {}
        self.plan_signature: tuple[Any, ...] | None = None
        self.plan_stale = True
        self.group_vars: dict[str, tk.BooleanVar] = {}

        self._configure_window()
        self._configure_styles()
        self._create_variables()
        self._build_ui()
        self.root.report_callback_exception = self._report_callback_exception
        self._render_empty_preview()
        self._update_scope_copy()
        self._update_controls()

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_after = self.root.after(60, self._drain_results)
        self.root.after(100, lambda: self.scan(refresh_metadata=False))
        self._periodic_after = self.root.after(20_000, self._periodic_scan)

    # ---------------------------------------------------------------- setup
    def _configure_window(self) -> None:
        self.root.title(APP_TITLE)
        self.root.geometry("1220x840")
        self.root.minsize(980, 680)
        self.root.configure(background=COLORS["bg"])
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        try:
            families = set(tkfont.families(self.root))
            family = "Microsoft YaHei UI" if "Microsoft YaHei UI" in families else "Segoe UI"
            tkfont.nametofont("TkDefaultFont").configure(family=family, size=10)
            tkfont.nametofont("TkTextFont").configure(family=family, size=10)
            tkfont.nametofont("TkHeadingFont").configure(family=family, size=10, weight="bold")
            self.font_family = family
        except tk.TclError:
            self.font_family = "Segoe UI"

        enable_dark_title_bar(self.root)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=COLORS["bg"])
        style.configure(
            "TLabel",
            background=COLORS["bg"],
            foreground=COLORS["text"],
            font=(self.font_family, 10),
        )
        style.configure(
            "Muted.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["muted"],
            font=(self.font_family, 9),
        )
        style.configure(
            "Panel.TLabel",
            background=COLORS["panel"],
            foreground=COLORS["text"],
        )
        style.configure(
            "PanelMuted.TLabel",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=(self.font_family, 9),
        )
        style.configure(
            "Section.TLabel",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=(self.font_family, 12, "bold"),
        )
        style.configure(
            "TButton",
            padding=(12, 8),
            background=COLORS["panel_raised"],
            foreground=COLORS["text"],
            bordercolor=COLORS["border"],
            focusthickness=2,
            focuscolor=COLORS["accent"],
        )
        style.map(
            "TButton",
            background=[("pressed", COLORS["panel"]), ("active", COLORS["panel_hover"])],
            foreground=[("disabled", "#606a78")],
        )
        style.configure(
            "Primary.TButton",
            padding=(16, 10),
            background=COLORS["accent"],
            foreground="#ffffff",
            bordercolor=COLORS["accent"],
            font=(self.font_family, 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("pressed", "#0f6fc4"), ("active", COLORS["accent_hover"]), ("disabled", "#273849")],
            foreground=[("disabled", "#7f8b99")],
        )
        style.configure(
            "Danger.TButton",
            background="#b84a46",
            foreground="#ffffff",
            bordercolor="#b84a46",
        )
        style.map("Danger.TButton", background=[("active", "#cc5852"), ("pressed", "#963b38")])
        style.configure(
            "TCheckbutton",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            padding=(2, 4),
            focuscolor=COLORS["accent"],
        )
        style.map(
            "TCheckbutton",
            background=[("active", COLORS["panel"])],
            foreground=[("disabled", COLORS["muted"])],
        )
        style.configure(
            "Scope.TRadiobutton",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            padding=(8, 6),
            font=(self.font_family, 9),
        )
        style.map(
            "Scope.TRadiobutton",
            background=[("active", COLORS["panel_raised"]), ("selected", COLORS["accent_soft"])],
            foreground=[("selected", "#b9dcff")],
        )
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["panel_raised"],
            background=COLORS["panel_raised"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["muted"],
            bordercolor=COLORS["border_strong"],
            padding=5,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLORS["panel_raised"])],
            foreground=[("readonly", COLORS["text"])],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=COLORS["panel_raised"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["muted"],
            bordercolor=COLORS["border_strong"],
            padding=5,
        )
        style.configure(
            "Horizontal.TProgressbar",
            background=COLORS["accent"],
            troughcolor=COLORS["panel_raised"],
            bordercolor=COLORS["panel_raised"],
            lightcolor=COLORS["accent"],
            darkcolor=COLORS["accent"],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["panel_raised"],
            troughcolor=COLORS["panel"],
            bordercolor=COLORS["panel"],
            arrowcolor=COLORS["muted"],
        )

    def _create_variables(self) -> None:
        self.account_var = tk.StringVar(value="正在读取本机 Steam 账号…")
        self.status_var = tk.StringVar(value="正在准备扫描")
        self.notice_var = tk.StringVar(value="扫描只读取本机数据，不会改动 Steam。")
        self.quality_var = tk.StringVar(value="等待扫描后显示数据质量说明。")
        self.scope_help_var = tk.StringVar(value=SCOPE_DEFS["library"][1])
        self.preview_summary_var = tk.StringVar(value="尚未生成预览")
        self.preview_warning_var = tk.StringVar(value="")
        self.restore_hint_var = tk.StringVar(value="写入前会自动备份，恢复也会保留恢复前状态。")

        self.stat_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar(value="—")
            for key in ("library", "games", "all", "unresolved", "installed")
        }
        self.stat_note_vars: dict[str, tk.StringVar] = {
            "library": tk.StringVar(value="推荐范围"),
            "games": tk.StringVar(value="排除辅助内容"),
            "all": tk.StringVar(value="完整本地并集"),
            "unresolved": tk.StringVar(value="资料不完整"),
            "installed": tk.StringVar(value="本机磁盘"),
        }
        self.scope_var = tk.StringVar(value="library")
        self.scope_text_vars = {
            key: tk.StringVar(value=title)
            for key, (title, _description) in SCOPE_DEFS.items()
        }
        self.language_var = tk.StringVar(value="简体中文")
        self.developer_min_var = tk.StringVar(value="3")
        self.mode_vars = {
            key: tk.BooleanVar(value=key in {"initial", "genre"})
            for key in MODE_DEFS
        }

    # -------------------------------------------------------------- builders
    def _panel(self, master: tk.Misc, **grid_options: Any) -> tk.Frame:
        frame = tk.Frame(
            master,
            background=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            borderwidth=0,
        )
        if grid_options:
            frame.grid(**grid_options)
        return frame

    def _build_ui(self) -> None:
        self._build_header()
        self._build_overview()
        self._build_workspace()
        self._build_log()
        self._build_footer()

    def _build_header(self) -> None:
        header = tk.Frame(self.root, background=COLORS["panel"], padx=22, pady=14)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_box = tk.Frame(header, background=COLORS["panel"])
        title_box.grid(row=0, column=0, sticky="w")
        tk.Label(
            title_box,
            text=APP_TITLE,
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=(self.font_family, 17, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            textvariable=self.account_var,
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=(self.font_family, 9),
        ).pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(header, background=COLORS["panel"])
        actions.grid(row=0, column=1, sticky="e")
        self.steam_pill = tk.Label(
            actions,
            text="检查 Steam…",
            background=COLORS["panel_raised"],
            foreground=COLORS["muted"],
            padx=11,
            pady=6,
            font=(self.font_family, 9, "bold"),
        )
        self.steam_pill.pack(side="left", padx=(0, 8))
        self.choose_root_button = ttk.Button(
            actions,
            text="选择 Steam 目录",
            command=self.choose_steam_root,
        )
        self.choose_root_button.pack(side="left", padx=(0, 8))
        self.reveal_button = ttk.Button(actions, text="打开配置目录", command=self.open_config_folder)
        self.reveal_button.pack(side="left", padx=(0, 8))
        self.scan_button = ttk.Button(actions, text="重新扫描", command=lambda: self.scan(refresh_metadata=True))
        self.scan_button.pack(side="left")

    def _build_overview(self) -> None:
        outer = tk.Frame(self.root, background=COLORS["bg"])
        outer.grid(row=1, column=0, sticky="ew", padx=20, pady=(16, 12))
        outer.grid_columnconfigure(0, weight=1)
        panel = self._panel(outer, row=0, column=0, sticky="ew")
        panel.grid_columnconfigure(0, weight=1)

        heading = tk.Frame(panel, background=COLORS["panel"])
        heading.grid(row=0, column=0, sticky="ew", padx=18, pady=(15, 10))
        heading.grid_columnconfigure(0, weight=1)
        tk.Label(
            heading,
            text="1  确认扫描范围",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=(self.font_family, 12, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            heading,
            text="这些数字来自当前电脑，会随 Steam 本地数据更新。",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=(self.font_family, 9),
        ).grid(row=0, column=1, sticky="e")

        cards = tk.Frame(panel, background=COLORS["panel"])
        cards.grid(row=1, column=0, sticky="ew", padx=14)
        for column in range(5):
            cards.grid_columnconfigure(column, weight=1, uniform="stats")
        definitions = [
            ("library", "游戏库范围"),
            ("games", "仅游戏"),
            ("all", "全部本地记录"),
            ("unresolved", "待识别"),
            ("installed", "本机已安装"),
        ]
        for column, (key, label) in enumerate(definitions):
            card = tk.Frame(
                cards,
                background=COLORS["panel_raised"],
                highlightbackground=COLORS["border"],
                highlightthickness=1,
                padx=12,
                pady=10,
            )
            card.grid(row=0, column=column, sticky="nsew", padx=4)
            tk.Label(
                card,
                text=label,
                background=COLORS["panel_raised"],
                foreground=COLORS["muted"],
                font=(self.font_family, 9),
            ).pack(anchor="w")
            tk.Label(
                card,
                textvariable=self.stat_vars[key],
                background=COLORS["panel_raised"],
                foreground=COLORS["text"],
                font=(self.font_family, 19, "bold"),
            ).pack(anchor="w", pady=(1, 0))
            tk.Label(
                card,
                textvariable=self.stat_note_vars[key],
                background=COLORS["panel_raised"],
                foreground=COLORS["muted"],
                font=(self.font_family, 8),
            ).pack(anchor="w")

        scope_row = tk.Frame(panel, background=COLORS["panel"])
        scope_row.grid(row=2, column=0, sticky="ew", padx=18, pady=(12, 5))
        tk.Label(
            scope_row,
            text="整理范围",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=(self.font_family, 9, "bold"),
        ).pack(side="left", padx=(0, 8))
        for key in SCOPE_DEFS:
            ttk.Radiobutton(
                scope_row,
                textvariable=self.scope_text_vars[key],
                variable=self.scope_var,
                value=key,
                style="Scope.TRadiobutton",
                command=self._settings_changed,
            ).pack(side="left", padx=(0, 5))
        ttk.Label(scope_row, textvariable=self.scope_help_var, style="PanelMuted.TLabel").pack(
            side="left", padx=(8, 0)
        )

        self.quality_label = tk.Label(
            panel,
            textvariable=self.quality_var,
            background=COLORS["accent_soft"],
            foreground="#b9dcff",
            justify="left",
            anchor="w",
            padx=12,
            pady=8,
            wraplength=1080,
            font=(self.font_family, 9),
        )
        self.quality_label.grid(row=3, column=0, sticky="ew", padx=18, pady=(5, 8))

        self.notice_label = tk.Label(
            panel,
            textvariable=self.notice_var,
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            justify="left",
            anchor="w",
            padx=2,
            pady=5,
            wraplength=1080,
            font=(self.font_family, 9),
        )
        self.notice_label.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 10))

    def _build_workspace(self) -> None:
        outer = tk.Frame(self.root, background=COLORS["bg"])
        outer.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 12))
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.grid(row=0, column=0, sticky="nsew")

        left = self._panel(panes)
        left.configure(width=350)
        right = self._panel(panes)
        panes.add(left, weight=0)
        panes.add(right, weight=1)

        self._build_rules(left)
        self._build_preview(right)

    def _build_rules(self, panel: tk.Frame) -> None:
        panel.grid_columnconfigure(0, weight=1)
        tk.Label(
            panel,
            text="2  选择分类方式",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=(self.font_family, 12, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 2))
        tk.Label(
            panel,
            text="一个游戏可以同时进入多个维度。默认方案为首字母 + 游戏类型。",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            justify="left",
            wraplength=310,
            font=(self.font_family, 9),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))

        language_row = tk.Frame(panel, background=COLORS["panel"])
        language_row.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        language_row.grid_columnconfigure(1, weight=1)
        tk.Label(
            language_row,
            text="名称语言",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=(self.font_family, 9),
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))
        language = ttk.Combobox(
            language_row,
            textvariable=self.language_var,
            values=list(LANGUAGES),
            state="readonly",
            width=16,
        )
        language.grid(row=0, column=1, sticky="ew")
        language.bind("<<ComboboxSelected>>", lambda _event: self._settings_changed())

        modes = tk.Frame(panel, background=COLORS["panel"])
        modes.grid(row=3, column=0, sticky="ew", padx=14)
        modes.grid_columnconfigure(0, weight=1)
        modes.grid_columnconfigure(1, weight=1)
        for index, (key, (title, subtitle)) in enumerate(MODE_DEFS.items()):
            cell = tk.Frame(modes, background=COLORS["panel"], padx=3, pady=2)
            cell.grid(row=index // 2, column=index % 2, sticky="ew")
            ttk.Checkbutton(
                cell,
                text=title,
                variable=self.mode_vars[key],
                command=self._settings_changed,
            ).pack(anchor="w")
            tk.Label(
                cell,
                text=subtitle,
                background=COLORS["panel"],
                foreground=COLORS["muted"],
                font=(self.font_family, 8),
            ).pack(anchor="w", padx=(24, 0))

        self.company_frame = tk.Frame(
            panel,
            background=COLORS["panel_raised"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=10,
            pady=8,
        )
        self.company_frame.grid(row=4, column=0, sticky="ew", padx=18, pady=(10, 0))
        self.company_frame.grid_columnconfigure(0, weight=1)
        tk.Label(
            self.company_frame,
            text="厂商独立分组门槛",
            background=COLORS["panel_raised"],
            foreground=COLORS["text"],
            font=(self.font_family, 9),
        ).grid(row=0, column=0, sticky="w")
        self.developer_spin = ttk.Spinbox(
            self.company_frame,
            from_=1,
            to=100,
            textvariable=self.developer_min_var,
            width=6,
            command=self._settings_changed,
        )
        self.developer_spin.grid(row=0, column=1, sticky="e")
        self.developer_spin.bind("<KeyRelease>", lambda _event: self._settings_changed())
        self.developer_spin.bind("<FocusOut>", lambda _event: self._normalize_threshold())
        tk.Label(
            self.company_frame,
            text="仅在选择开发商或发行商时生效",
            background=COLORS["panel_raised"],
            foreground=COLORS["muted"],
            font=(self.font_family, 8),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 0))

        self.plan_button = ttk.Button(
            panel,
            text="生成分类预览",
            style="Primary.TButton",
            command=self.generate_plan,
        )
        self.plan_button.grid(row=5, column=0, sticky="ew", padx=18, pady=(14, 12))

        separator = ttk.Separator(panel, orient="horizontal")
        separator.grid(row=6, column=0, sticky="ew", padx=18, pady=(2, 10))
        tk.Label(
            panel,
            text="安全与恢复",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=(self.font_family, 10, "bold"),
        ).grid(row=7, column=0, sticky="w", padx=18)
        tk.Label(
            panel,
            textvariable=self.restore_hint_var,
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            justify="left",
            wraplength=310,
            font=(self.font_family, 8),
        ).grid(row=8, column=0, sticky="ew", padx=18, pady=(4, 8))
        self.restore_button = ttk.Button(
            panel,
            text="恢复最近备份…",
            style="Danger.TButton",
            command=self.confirm_restore,
        )
        self.restore_button.grid(row=9, column=0, sticky="ew", padx=18, pady=(0, 16))

    def _build_preview(self, panel: tk.Frame) -> None:
        panel.grid_rowconfigure(3, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        heading = tk.Frame(panel, background=COLORS["panel"])
        heading.grid(row=0, column=0, sticky="ew", padx=18, pady=(15, 5))
        heading.grid_columnconfigure(0, weight=1)
        tk.Label(
            heading,
            text="3  审阅分类预览",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=(self.font_family, 12, "bold"),
        ).grid(row=0, column=0, sticky="w")
        actions = tk.Frame(heading, background=COLORS["panel"])
        actions.grid(row=0, column=1, sticky="e")
        self.select_none_button = ttk.Button(actions, text="全不选", command=lambda: self.select_all(False))
        self.select_none_button.pack(side="left", padx=(0, 6))
        self.select_all_button = ttk.Button(actions, text="全选", command=lambda: self.select_all(True))
        self.select_all_button.pack(side="left")

        tk.Label(
            panel,
            textvariable=self.preview_summary_var,
            background=COLORS["panel"],
            foreground="#b9dcff",
            anchor="w",
            font=(self.font_family, 9, "bold"),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 4))
        self.preview_warning_label = tk.Label(
            panel,
            textvariable=self.preview_warning_var,
            background=COLORS["warn_soft"],
            foreground="#f1ce94",
            justify="left",
            anchor="w",
            padx=10,
            pady=7,
            wraplength=730,
            font=(self.font_family, 8),
        )
        self.preview_warning_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 7))
        self.preview_warning_label.grid_remove()

        self.preview_scroll = ScrollableFrame(panel, background=COLORS["panel"])
        self.preview_scroll.grid(row=3, column=0, sticky="nsew", padx=(12, 8), pady=(0, 12))

    def _build_log(self) -> None:
        outer = tk.Frame(self.root, background=COLORS["bg"])
        outer.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 10))
        outer.grid_columnconfigure(0, weight=1)
        panel = self._panel(outer, row=0, column=0, sticky="ew")
        panel.grid_columnconfigure(0, weight=1)
        tk.Label(
            panel,
            text="运行记录",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=(self.font_family, 9, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))
        self.log_text = tk.Text(
            panel,
            height=5,
            background="#0e1218",
            foreground="#c8d0da",
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=7,
            wrap="word",
            font=("Consolas", 9),
            state="disabled",
        )
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=1, column=0, sticky="ew", padx=(10, 0), pady=(0, 10))
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 8), pady=(0, 10))
        self.log_text.tag_configure("good", foreground="#85e4a1")
        self.log_text.tag_configure("error", foreground="#ffaaa5")
        self.log_text.tag_configure("muted", foreground=COLORS["muted"])

    def _build_footer(self) -> None:
        footer = tk.Frame(self.root, background=COLORS["panel"], padx=20, pady=11)
        footer.grid(row=4, column=0, sticky="ew")
        footer.grid_columnconfigure(1, weight=1)
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=110)
        self.progress.grid(row=0, column=0, sticky="w", padx=(0, 12))
        tk.Label(
            footer,
            textvariable=self.status_var,
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            anchor="w",
            font=(self.font_family, 9),
        ).grid(row=0, column=1, sticky="ew")
        self.apply_button = ttk.Button(
            footer,
            text="备份并写入 Steam",
            style="Primary.TButton",
            command=self.confirm_apply,
        )
        self.apply_button.grid(row=0, column=2, sticky="e", padx=(14, 0))

    # -------------------------------------------------------------- feedback
    def _log(self, message: str, kind: str = "") -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n", kind or "muted")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        if kind == "error":
            LOGGER.error(message)
        else:
            LOGGER.info(message)

    def _notice(self, message: str, kind: str = "info") -> None:
        palette = {
            "info": (COLORS["panel"], COLORS["muted"]),
            "good": (COLORS["good_soft"], "#9ae9af"),
            "warning": (COLORS["warn_soft"], "#f1ce94"),
            "error": (COLORS["danger_soft"], "#ffb2ae"),
        }
        background, foreground = palette.get(kind, palette["info"])
        self.notice_var.set(message)
        self.notice_label.configure(background=background, foreground=foreground)

    def _report_callback_exception(
        self,
        exception_type: type[BaseException],
        value: BaseException,
        traceback_object: Any,
    ) -> None:
        details = "".join(
            traceback.format_exception(exception_type, value, traceback_object)
        )
        LOGGER.error("Tk 回调发生未处理异常\n%s", details)
        if hasattr(self, "notice_label"):
            self._notice(f"界面发生错误：{value}", "error")
        if hasattr(self, "log_text"):
            self._log(details.rstrip(), "error")
        try:
            messagebox.showerror(
                "Steam 游戏库整理遇到错误",
                f"界面操作失败：\n\n{value}\n\n详细信息已写入日志。",
                parent=self.root,
            )
        except tk.TclError:
            pass

    # ------------------------------------------------------------- threading
    def _worker_loop(self) -> None:
        """Run every Organizer call on one serial, daemon worker."""

        while True:
            job = self._work_queue.get()
            if job is None:
                return
            name, work, on_success, silent = job
            try:
                result = work()
                self._result_queue.put((name, True, result, "", on_success, silent))
            except Exception as exc:  # Worker boundary: report on the UI thread.
                details = traceback.format_exc()
                LOGGER.error("后台任务 %s 失败\n%s", name, details)
                self._result_queue.put((name, False, exc, details, on_success, silent))

    def _run_task(
        self,
        name: str,
        label: str,
        work: Callable[[], Any],
        on_success: Callable[[Any], None],
        *,
        silent: bool = False,
    ) -> bool:
        if self._closed:
            return False
        if self.busy_task:
            if not silent:
                self._notice("请等待当前操作完成。", "warning")
            return False

        self.busy_task = name
        self.progress.start(10)
        self.status_var.set(label)
        if not silent:
            self._notice(label, "info")
            self._log(label)
        self._update_controls()

        self._work_queue.put((name, work, on_success, silent))
        return True

    def _drain_results(self) -> None:
        if self._closed:
            return
        try:
            while True:
                name, ok, payload, details, callback, silent = self._result_queue.get_nowait()
                if self.busy_task == name:
                    self.busy_task = None
                self.progress.stop()
                if ok:
                    try:
                        callback(payload)
                    except Exception as exc:  # Keep rendering failures visible too.
                        self._notice(f"界面更新失败：{exc}", "error")
                        self._log(f"界面更新失败：{exc}", "error")
                        self._log(traceback.format_exc(), "error")
                else:
                    self._notice(f"操作失败：{payload}", "error")
                    self.status_var.set("操作失败，请查看窗口内提示")
                    self._log(f"{name} 失败：{payload}", "error")
                    if details:
                        self._log(details.rstrip(), "error")
                    try:
                        self.root.bell()
                    except tk.TclError:
                        pass
                self._update_controls()
        except queue.Empty:
            pass
        if self._close_when_idle and self.busy_task is None:
            self.root.after_idle(self.close)
            return
        self._poll_after = self.root.after(60, self._drain_results)

    def _periodic_scan(self) -> None:
        if self._closed:
            return
        if not self.busy_task:
            self.scan(refresh_metadata=False, silent=True)
        self._periodic_after = self.root.after(20_000, self._periodic_scan)

    # --------------------------------------------------------------- scanning
    def scan(self, *, refresh_metadata: bool, silent: bool = False) -> None:
        def work() -> dict[str, Any]:
            with self.organizer.lock:
                self.organizer.library.resolve_account()
                return self.organizer.state(refresh_metadata=refresh_metadata)

        self._run_task(
            "scan",
            "正在扫描本机 Steam 数据…",
            work,
            lambda data: self._scan_done(data, silent=silent),
            silent=silent,
        )

    def _scan_done(self, data: dict[str, Any], *, silent: bool) -> None:
        self._apply_state(data)
        total = as_int((data.get("scopes") or {}).get("library"), 0)
        metadata_error = str(data.get("appinfo_error") or "")
        if metadata_error:
            if not silent:
                self._notice("扫描完成，但 Steam 元数据读取失败；请点击“重新扫描”重试。", "warning")
                self._log(f"Steam 元数据读取失败：{metadata_error}", "error")
            self.status_var.set("元数据未就绪，暂不能生成分类预览")
        elif not silent:
            self._notice(f"扫描完成：游戏库范围内有 {format_number(total)} 个条目。", "good")
            self._log(f"扫描完成：游戏库 {format_number(total)} 个条目", "good")
            self.status_var.set("扫描完成，可以选择分类方式并生成预览")

    def _apply_state(self, data: dict[str, Any]) -> None:
        previous_account = self.state_data.get("account_id")
        self.state_data = data
        running = data.get("steam_running")
        self.steam_running = running if isinstance(running, bool) else None

        scopes = data.get("scopes") or data.get("counts") or {}
        counts = data.get("counts") or {}
        for key in ("library", "games", "all", "unresolved"):
            value = scopes.get(key, counts.get(key, 0))
            self.stat_vars[key].set(format_number(value))
        self.stat_vars["installed"].set(format_number(counts.get("installed", 0)))

        unresolved = as_int(scopes.get("unresolved", counts.get("unresolved", 0)))
        all_count = as_int(scopes.get("all", counts.get("all", counts.get("candidates", 0))))
        auxiliary = as_int(scopes.get("auxiliary", counts.get("auxiliary", 0)))
        local_only = as_int(scopes.get("local_only", counts.get("local_only", 0)))
        excluded = as_int(scopes.get("excluded", counts.get("excluded", 0)))
        self.stat_note_vars["unresolved"].set(
            f"占全部记录 {unresolved / all_count * 100:.1f}%" if all_count else "资料不完整"
        )
        sources = data.get("sources") or {}
        source_text = " · ".join(
            [
                f"本地配置 {format_number(sources.get('local', counts.get('local', 0)))}",
                f"库缓存 {format_number(sources.get('cached', counts.get('cached', 0)))}",
                f"已安装 {format_number(sources.get('installed', counts.get('installed', 0)))}",
            ]
        )
        quality_parts = [source_text]
        if unresolved:
            quality_parts.append(f"{format_number(unresolved)} 个资料不完整条目会从推荐范围排除")
        if auxiliary:
            quality_parts.append(f"检测到 {format_number(auxiliary)} 个 DLC、工具或辅助项")
        if local_only or excluded:
            quality_parts.append(
                f"另排除本地历史记录 {format_number(local_only)} 个、测试项 {format_number(excluded)} 个"
            )
        metadata_error = str(data.get("appinfo_error") or "")
        if metadata_error:
            quality_parts.append(
                "当前显示上次成功数据，请重新扫描"
                if data.get("appinfo_stale")
                else "Steam 元数据不可用，请重新扫描"
            )
            self.quality_label.configure(background=COLORS["warn_soft"], foreground="#f1ce94")
        else:
            self.quality_label.configure(background=COLORS["accent_soft"], foreground="#b9dcff")
        self.quality_var.set("。".join(part for part in quality_parts if part) + "。")

        for key, (title, _description) in SCOPE_DEFS.items():
            self.scope_text_vars[key].set(f"{title}  {format_number(scopes.get(key, counts.get(key, 0)))}")
        if self.scope_var.get() not in SCOPE_DEFS:
            self.scope_var.set(data.get("default_scope", "library"))
        self._update_scope_copy()

        account = data.get("steamid64") or data.get("account_id")
        root = data.get("steam_root") or "本机 Steam"
        self.account_var.set(f"{root}  ·  账号 {account}" if account else str(root))

        collections = data.get("collections") or []
        managed = sum(1 for item in collections if item.get("ours"))
        manual = max(0, len(collections) - managed)
        self.restore_hint_var.set(
            f"当前有 {format_number(managed)} 个自动分类；{format_number(manual)} 个其他分类不会被替换。"
        )

        if self.steam_running is True:
            self.steam_pill.configure(
                text="●  Steam 运行中 · 仅可预览",
                background=COLORS["warn_soft"],
                foreground="#f1ce94",
            )
        elif self.steam_running is False:
            self.steam_pill.configure(
                text="●  Steam 已退出 · 可写入",
                background=COLORS["good_soft"],
                foreground="#9ae9af",
            )
        else:
            self.steam_pill.configure(
                text="●  无法确认 Steam 状态",
                background=COLORS["danger_soft"],
                foreground="#ffb2ae",
            )
            if data.get("steam_check_error"):
                self._notice(str(data["steam_check_error"]), "error")

        if previous_account and previous_account != data.get("account_id") and self.plan:
            self._invalidate_plan("Steam 账号已变化，请重新生成预览。")
        self._update_controls()

    # --------------------------------------------------------------- settings
    def _selected_modes(self) -> list[str]:
        return [key for key in MODE_DEFS if self.mode_vars[key].get()]

    def _current_signature(self) -> tuple[Any, ...]:
        return (
            tuple(self._selected_modes()),
            LANGUAGES.get(self.language_var.get(), "schinese"),
            self.scope_var.get(),
            as_int(self.developer_min_var.get(), 3),
        )

    def _settings_changed(self) -> None:
        self._update_scope_copy()
        company_enabled = self.mode_vars["developer"].get() or self.mode_vars["publisher"].get()
        self._set_enabled(self.developer_spin, company_enabled)
        if self.plan:
            self.plan_stale = self.plan_signature != self._current_signature()
            if self.plan_stale:
                self.preview_warning_var.set("设置已改变，这份预览已过期。请重新生成后再写入。")
                self.preview_warning_label.grid()
            else:
                self._render_warnings()
        self._update_controls()

    def _normalize_threshold(self) -> None:
        value = min(100, max(1, as_int(self.developer_min_var.get(), 3)))
        self.developer_min_var.set(str(value))
        self._settings_changed()

    def _update_scope_copy(self) -> None:
        self.scope_help_var.set(SCOPE_DEFS.get(self.scope_var.get(), SCOPE_DEFS["library"])[1])

    # ------------------------------------------------------------------ plan
    def generate_plan(self) -> None:
        if self.state_data.get("appinfo_error"):
            self._notice("Steam 元数据当前不可用，请先重新扫描，成功后再生成预览。", "error")
            return
        modes = self._selected_modes()
        if not modes:
            self._notice("请至少选择一种分类方式。", "warning")
            return
        developer_min = min(100, max(1, as_int(self.developer_min_var.get(), 3)))
        self.developer_min_var.set(str(developer_min))
        language = LANGUAGES.get(self.language_var.get(), "schinese")
        scope = self.scope_var.get()
        signature = self._current_signature()

        def work() -> tuple[dict[str, Any], dict[str, Any], tuple[Any, ...]]:
            with self.organizer.lock:
                self.organizer.set_language(language)
                result = self.organizer.make_plan(modes, developer_min, scope)
                current_state = self.organizer.state()
                return result, current_state, signature

        self._run_task(
            "plan",
            "正在刷新元数据并生成分类预览…",
            work,
            self._plan_done,
        )

    def _plan_done(self, payload: tuple[dict[str, Any], dict[str, Any], tuple[Any, ...]]) -> None:
        result, current_state, signature = payload
        self._apply_state(current_state)
        self.plan = list(result.get("groups") or [])
        self.plan_id = result.get("plan_id")
        self.plan_summary = dict(result.get("summary") or {})
        self.plan_signature = signature
        self.plan_stale = signature != self._current_signature()
        self.group_vars = {
            str(group.get("id")): tk.BooleanVar(value=True)
            for group in self.plan
        }
        self._render_preview()
        groups = len(self.plan)
        unique = as_int(self.plan_summary.get("unique_apps"), 0)
        memberships = as_int(self.plan_summary.get("memberships"), 0)
        if self.plan_stale:
            self._notice("预览已生成，但设置在生成期间发生了变化；请重新生成。", "warning")
        else:
            self._notice(
                f"预览已生成：{format_number(groups)} 个分类，覆盖 {format_number(unique)} 个唯一条目。",
                "good",
            )
        self._log(
            f"预览完成：{format_number(groups)} 个分类，{format_number(unique)} 个唯一条目，"
            f"{format_number(memberships)} 次归属",
            "good",
        )
        self.status_var.set("请审阅并勾选要写入的分类")
        self._update_controls()

    def _render_empty_preview(self) -> None:
        self.preview_scroll.clear()
        empty = tk.Frame(self.preview_scroll.interior, background=COLORS["panel"], pady=70)
        empty.pack(fill="both", expand=True)
        tk.Label(
            empty,
            text="尚未生成分类预览",
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=(self.font_family, 12, "bold"),
        ).pack()
        tk.Label(
            empty,
            text="先确认扫描范围和分类方式，再点击“生成分类预览”。",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=(self.font_family, 9),
        ).pack(pady=(5, 0))

    def _render_preview(self) -> None:
        self.preview_scroll.clear()
        grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        for group in self.plan:
            mode = str(group.get("mode") or str(group.get("id", "other")).split(":", 1)[0])
            grouped.setdefault(mode, []).append(group)

        for mode, groups in grouped.items():
            section = tk.Frame(self.preview_scroll.interior, background=COLORS["panel"], padx=5, pady=4)
            section.pack(fill="x", padx=4, pady=(2, 8))
            header = tk.Frame(section, background=COLORS["panel"])
            header.pack(fill="x", padx=5, pady=(1, 5))
            tk.Label(
                header,
                text=MODE_TITLES.get(mode, mode),
                background=COLORS["panel"],
                foreground=COLORS["text"],
                font=(self.font_family, 10, "bold"),
            ).pack(side="left")
            mode_apps = {appid for group in groups for appid in group.get("appids", [])}
            tk.Label(
                header,
                text=f"{format_number(len(groups))} 个分类 · {format_number(len(mode_apps))} 个条目",
                background=COLORS["panel"],
                foreground=COLORS["muted"],
                font=(self.font_family, 8),
            ).pack(side="right")

            box = tk.Frame(
                section,
                background=COLORS["panel_raised"],
                highlightbackground=COLORS["border"],
                highlightthickness=1,
            )
            box.pack(fill="x")
            box.grid_columnconfigure(1, weight=1)
            for row_index, group in enumerate(groups):
                group_id = str(group.get("id"))
                variable = self.group_vars[group_id]
                row = tk.Frame(box, background=COLORS["panel_raised"], padx=8, pady=6)
                row.grid(row=row_index * 2, column=0, columnspan=3, sticky="ew")
                row.grid_columnconfigure(1, weight=1)
                check = ttk.Checkbutton(
                    row,
                    variable=variable,
                    command=self._selection_changed,
                )
                check.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 5))
                name = str(group.get("name") or group.get("bucket") or group_id)
                name_label = tk.Label(
                    row,
                    text=name,
                    background=COLORS["panel_raised"],
                    foreground=COLORS["text"],
                    anchor="w",
                    font=(self.font_family, 9),
                )
                name_label.grid(row=0, column=1, sticky="ew")
                sample = "、".join(str(item) for item in (group.get("sample") or []) if item)
                if len(sample) > 120:
                    sample = sample[:119] + "…"
                sample_label = tk.Label(
                    row,
                    text=f"示例：{sample}" if sample else "暂无可显示的名称示例",
                    background=COLORS["panel_raised"],
                    foreground=COLORS["muted"],
                    anchor="w",
                    font=(self.font_family, 8),
                )
                sample_label.grid(row=1, column=1, sticky="ew", pady=(2, 0))
                tk.Label(
                    row,
                    text=f"{format_number(group.get('count', len(group.get('appids', []))))} 项",
                    background=COLORS["panel_raised"],
                    foreground=COLORS["muted"],
                    font=(self.font_family, 8),
                ).grid(row=0, column=2, rowspan=2, sticky="e", padx=(10, 2))

                def toggle_from_label(
                    _event: tk.Event[Any],
                    var: tk.BooleanVar = variable,
                ) -> None:
                    var.set(not var.get())
                    self._selection_changed()

                name_label.bind("<Button-1>", toggle_from_label)
                sample_label.bind("<Button-1>", toggle_from_label)
                if row_index < len(groups) - 1:
                    ttk.Separator(box, orient="horizontal").grid(
                        row=row_index * 2 + 1,
                        column=0,
                        columnspan=3,
                        sticky="ew",
                        padx=10,
                    )

        self._render_warnings()
        self._selection_changed()

    def _render_warnings(self) -> None:
        if self.plan_stale:
            self.preview_warning_var.set("设置已改变，这份预览已过期。请重新生成后再写入。")
            self.preview_warning_label.grid()
            return
        warnings = self.plan_summary.get("warnings") or []
        texts = []
        for warning in warnings:
            if isinstance(warning, str):
                texts.append(warning)
            elif isinstance(warning, dict):
                text = warning.get("message") or warning.get("text") or warning.get("title")
                if text:
                    texts.append(str(text))
        self.preview_warning_var.set("  •  ".join(texts))
        if texts:
            self.preview_warning_label.grid()
        else:
            self.preview_warning_label.grid_remove()

    def select_all(self, selected: bool) -> None:
        for variable in self.group_vars.values():
            variable.set(selected)
        self._selection_changed()

    def _selected_groups(self) -> list[dict[str, Any]]:
        return [
            group
            for group in self.plan
            if self.group_vars.get(str(group.get("id")))
            and self.group_vars[str(group.get("id"))].get()
        ]

    def _selection_stats(self) -> tuple[int, int, int]:
        groups = self._selected_groups()
        appids = {appid for group in groups for appid in group.get("appids", [])}
        memberships = sum(as_int(group.get("count"), len(group.get("appids", []))) for group in groups)
        unique = len(appids)
        if len(groups) == len(self.plan) and not unique:
            unique = as_int(self.plan_summary.get("unique_apps"), 0)
        return len(groups), unique, memberships

    def _selection_changed(self) -> None:
        selected, unique, memberships = self._selection_stats()
        missing = as_int(self.plan_summary.get("missing_metadata"), 0)
        self.preview_summary_var.set(
            f"已选 {format_number(selected)} / {format_number(len(self.plan))} 个分类  ·  "
            f"{format_number(unique)} 个唯一条目  ·  {format_number(memberships)} 次归属  ·  "
            f"资料缺失 {format_number(missing)}"
        )
        self._update_controls()

    def _invalidate_plan(self, reason: str) -> None:
        self.plan_id = None
        self.plan_stale = True
        self.plan_signature = None
        if self.plan:
            self.preview_warning_var.set(reason)
            self.preview_warning_label.grid()
        self._update_controls()

    # --------------------------------------------------------------- actions
    def _write_block_reason(self) -> str:
        selected, _unique, _memberships = self._selection_stats()
        if self.busy_task:
            return "请等待当前操作完成"
        if not self.state_data:
            return "请先完成扫描"
        if self.state_data.get("appinfo_error"):
            return "Steam 元数据不可用，请重新扫描"
        if not self.plan or not self.plan_id:
            return "请先生成分类预览"
        if self.plan_stale:
            return "预览已过期，请重新生成"
        if selected == 0:
            return "请至少勾选一个分类"
        if self.steam_running is True:
            return "请先从 Steam 菜单完全退出"
        if self.steam_running is not False:
            return "无法确认 Steam 状态，请重新扫描"
        return ""

    def confirm_apply(self) -> None:
        reason = self._write_block_reason()
        if reason:
            self._notice(reason, "warning")
            return
        selected_groups = self._selected_groups()
        selected_ids = [str(group.get("id")) for group in selected_groups]
        group_count, unique, memberships = self._selection_stats()
        managed = as_int(self.plan_summary.get("existing_managed"), 0)
        preserved = as_int(self.plan_summary.get("manual_preserved"), 0)
        confirmed = messagebox.askyesno(
            "确认写入 Steam",
            "即将执行以下操作：\n\n"
            f"• 写入 {format_number(group_count)} 个收藏夹\n"
            f"• 覆盖 {format_number(unique)} 个唯一条目\n"
            f"• 共 {format_number(memberships)} 次分类归属\n"
            f"• 替换 {format_number(managed)} 个旧自动分类\n"
            f"• 保留 {format_number(preserved)} 个其他分类\n\n"
            "写入前会自动备份。确认继续吗？",
            icon="warning",
            parent=self.root,
        )
        if not confirmed:
            return
        plan_id = str(self.plan_id)

        def work() -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
            with self.organizer.lock:
                result = self.organizer.apply(plan_id, selected_ids)
                try:
                    current_state = self.organizer.state()
                    state_error = None
                except Exception as exc:
                    current_state = None
                    state_error = str(exc)
                    LOGGER.warning("写入成功，但后置状态刷新失败", exc_info=True)
                return result, current_state, state_error

        self._run_task(
            "apply",
            "正在创建备份并写入 Steam 收藏夹…",
            work,
            self._apply_done,
        )

    def _apply_done(
        self,
        payload: tuple[dict[str, Any], dict[str, Any] | None, str | None],
    ) -> None:
        result, current_state, state_error = payload
        if current_state is not None:
            self._apply_state(current_state)
        collections = result.get("collections", 0)
        apps = result.get("apps", 0)
        backup = str(result.get("backup") or "")
        self._invalidate_plan("这份预览已经成功写入。如需再次整理，请重新生成。")
        self._notice(
            f"写入完成：{format_number(collections)} 个分类、{format_number(apps)} 个条目。重新启动 Steam 后查看结果。",
            "good",
        )
        self._log(
            f"写入完成：{format_number(collections)} 个分类，{format_number(apps)} 个条目",
            "good",
        )
        if backup:
            self._log(f"写入前备份：{backup}", "good")
        if state_error:
            self._notice(
                f"写入已经成功，但刷新状态失败：{state_error}。请稍后重新扫描。",
                "warning",
            )
            self._log(f"写入后状态刷新失败：{state_error}", "error")
            self.status_var.set("写入成功；状态刷新失败，请重新扫描")
        else:
            self.status_var.set("写入完成；重新启动 Steam 后查看分类")

    def confirm_restore(self) -> None:
        if self.busy_task:
            self._notice("请等待当前操作完成。", "warning")
            return
        if self.steam_running is True:
            self._notice("请先从 Steam 菜单完全退出，再恢复备份。", "warning")
            return
        if self.steam_running is not False:
            self._notice("无法确认 Steam 状态，请重新扫描后再恢复。", "warning")
            return
        confirmed = messagebox.askyesno(
            "恢复最近备份",
            "将使用最近一次可恢复备份替换当前收藏夹。\n\n"
            "恢复前还会为当前状态创建一份安全备份，成功后需要重新启动 Steam。\n\n"
            "确认继续吗？",
            icon="warning",
            parent=self.root,
        )
        if not confirmed:
            return

        def work() -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
            with self.organizer.lock:
                result = self.organizer.restore()
                try:
                    current_state = self.organizer.state()
                    state_error = None
                except Exception as exc:
                    current_state = None
                    state_error = str(exc)
                    LOGGER.warning("恢复成功，但后置状态刷新失败", exc_info=True)
                return result, current_state, state_error

        self._run_task(
            "restore",
            "正在创建安全备份并恢复最近备份…",
            work,
            self._restore_done,
        )

    def _restore_done(
        self,
        payload: tuple[dict[str, Any], dict[str, Any] | None, str | None],
    ) -> None:
        result, current_state, state_error = payload
        if current_state is not None:
            self._apply_state(current_state)
        restored = str(result.get("restored") or "")
        safety_backup = str(result.get("safety_backup") or "")
        self._invalidate_plan("收藏夹已经恢复，原预览不再对应当前状态，请重新生成。")
        self._notice("最近备份已恢复。重新启动 Steam 后查看结果。", "good")
        if restored:
            self._log(f"已恢复备份：{restored}", "good")
        if safety_backup:
            self._log(f"恢复前安全备份：{safety_backup}", "good")
        if state_error:
            self._notice(
                f"恢复已经成功，但刷新状态失败：{state_error}。请稍后重新扫描。",
                "warning",
            )
            self._log(f"恢复后状态刷新失败：{state_error}", "error")
            self.status_var.set("恢复成功；状态刷新失败，请重新扫描")
        else:
            self.status_var.set("恢复完成；重新启动 Steam 后查看结果")

    def open_config_folder(self) -> None:
        def work() -> str:
            with self.organizer.lock:
                folder = Path(self.organizer.library.cloud_path()).parent
            if os.name != "nt" or not hasattr(os, "startfile"):
                raise RuntimeError("此功能仅支持 Windows")
            os.startfile(str(folder))  # type: ignore[attr-defined]
            return str(folder)

        self._run_task(
            "reveal",
            "正在打开 Steam 配置目录…",
            work,
            self._folder_opened,
        )

    def _folder_opened(self, folder: str) -> None:
        self._notice(f"已打开配置目录：{folder}", "good")
        self._log(f"已打开配置目录：{folder}", "good")
        self.status_var.set("配置目录已打开")

    def choose_steam_root(self) -> None:
        """Let fallback users recover when automatic Steam detection fails."""

        if self.busy_task:
            self._notice("请等待当前操作完成。", "warning")
            return

        current = Path(self.organizer.library.root)
        candidates = (current, current.parent, Path.home(), Path.cwd())
        initial = Path.cwd()
        for candidate in candidates:
            try:
                if candidate.is_dir():
                    initial = candidate
                    break
            except OSError:
                continue
        chosen = filedialog.askdirectory(
            parent=self.root,
            title="选择 Steam 安装目录",
            initialdir=str(initial),
            mustexist=True,
        )
        if not chosen:
            return

        def work() -> tuple[str, dict[str, Any]]:
            with self.organizer.lock:
                root = self.organizer.set_steam_root(chosen)
                state = self.organizer.state(refresh_metadata=True)
            save_steam_root(root)
            return str(root), state

        def on_success(payload: tuple[str, dict[str, Any]]) -> None:
            root, state = payload
            self._apply_state(state)
            self._invalidate_plan("Steam 安装目录已变化，请重新生成预览。")
            total = as_int((state.get("scopes") or {}).get("library"), 0)
            self._notice(
                f"Steam 目录已更新：游戏库范围内有 {format_number(total)} 个条目。",
                "good",
            )
            self._log(f"Steam 目录已切换为 {root}", "good")
            self.status_var.set("Steam 目录已更新，可以选择分类方式并生成预览")

        self._run_task(
            "choose_root",
            "正在验证并读取所选 Steam 目录…",
            work,
            on_success,
        )

    # -------------------------------------------------------------- controls
    @staticmethod
    def _set_enabled(widget: ttk.Widget, enabled: bool) -> None:
        if enabled:
            widget.state(["!disabled"])
        else:
            widget.state(["disabled"])

    def _update_controls(self) -> None:
        idle = self.busy_task is None
        has_state = bool(self.state_data)
        has_modes = bool(self._selected_modes())
        metadata_ready = has_state and not self.state_data.get("appinfo_error")
        company_enabled = self.mode_vars["developer"].get() or self.mode_vars["publisher"].get()

        self._set_enabled(self.choose_root_button, idle)
        self._set_enabled(self.scan_button, idle)
        self._set_enabled(self.reveal_button, idle and has_state)
        self._set_enabled(self.plan_button, idle and metadata_ready and has_modes)
        self._set_enabled(self.developer_spin, idle and company_enabled)
        self._set_enabled(self.select_all_button, idle and bool(self.plan))
        self._set_enabled(self.select_none_button, idle and bool(self.plan))
        self._set_enabled(
            self.restore_button,
            idle and has_state and self.steam_running is False,
        )

        reason = self._write_block_reason()
        self._set_enabled(self.apply_button, not reason)
        if self.busy_task == "plan":
            self.plan_button.configure(text="正在生成预览…")
        elif self.plan:
            self.plan_button.configure(text="重新生成分类预览")
        else:
            self.plan_button.configure(text="生成分类预览")

        if reason:
            self.status_var.set(reason if not self.busy_task else self.status_var.get())
        else:
            groups, unique, memberships = self._selection_stats()
            self.status_var.set(
                f"准备写入 {format_number(groups)} 个分类，覆盖 {format_number(unique)} 个唯一条目，"
                f"共 {format_number(memberships)} 次归属"
            )

    # ---------------------------------------------------------------- close
    def close(self) -> None:
        if self.busy_task:
            wait_and_close = messagebox.askyesno(
                "操作尚未完成",
                "当前后台操作仍在进行。为避免损坏 Steam 数据，不能强制中断。\n\n"
                "是否等待操作完成后自动关闭窗口？",
                icon="warning",
                parent=self.root,
            )
            if wait_and_close:
                self._close_when_idle = True
                self._notice("正在等待当前操作安全完成，完成后将自动关闭。", "warning")
                self.status_var.set("等待后台操作完成后关闭")
                LOGGER.info("用户请求在后台任务 %s 完成后关闭", self.busy_task)
            return

        self._closed = True
        self._work_queue.put(None)
        if self._poll_after:
            try:
                self.root.after_cancel(self._poll_after)
            except tk.TclError:
                pass
        if self._periodic_after:
            try:
                self.root.after_cancel(self._periodic_after)
            except tk.TclError:
                pass
        try:
            self.preview_scroll.canvas.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        LOGGER.info("%s 正常退出", APP_TITLE)
        self.root.destroy()


def _show_fatal_error(message: str, root: tk.Tk | None = None) -> None:
    temporary_root = None
    try:
        if root is None:
            temporary_root = tk.Tk()
            temporary_root.withdraw()
            root = temporary_root
        messagebox.showerror(
            "Steam 游戏库整理无法启动",
            message,
            parent=root,
        )
    except tk.TclError:
        pass
    finally:
        if temporary_root is not None:
            try:
                temporary_root.destroy()
            except tk.TclError:
                pass


def main(organizer: Organizer | None = None) -> None:
    root: tk.Tk | None = None
    mutex = WindowsSingleInstance()
    try:
        log_path = configure_logging()
    except Exception:
        log_path = None
    try:
        if not mutex.acquire():
            message = "程序已经在运行。请切换到现有窗口，避免两个实例同时修改 Steam 收藏夹。"
            if log_path:
                LOGGER.warning(message)
            _show_fatal_error(message)
            return

        enable_windows_dpi_awareness()
        root = tk.Tk()
        SteamDesktopApp(root, organizer=organizer)
        root.mainloop()
    except Exception as exc:
        details = traceback.format_exc()
        if log_path:
            LOGGER.critical("桌面程序发生致命错误\n%s", details)
        suffix = f"\n\n详细日志：{log_path}" if log_path else ""
        _show_fatal_error(f"{exc}{suffix}", root)
    finally:
        mutex.close()


if __name__ == "__main__":
    main()
