# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller recipe for the Windows desktop release.

The primary UI is WebView2/WinForms. The tkinter compatibility shell is also
bundled so Windows editions without a working WebView2 Runtime still have a
local, functional desktop interface.
"""

import os
from pathlib import Path


SPEC_DIR = Path(SPECPATH).resolve()
PROJECT_ROOT = SPEC_DIR.parent
BUILD_MODE = os.environ.get("SLO_BUILD_MODE", "onefile").strip().lower()
VERSION_FILE = Path(
    os.environ.get(
        "SLO_VERSION_FILE",
        str(PROJECT_ROOT / "scripts" / "SteamLibraryOrganizer.version.txt"),
    )
).resolve()

if BUILD_MODE not in {"onefile", "onedir"}:
    raise ValueError("SLO_BUILD_MODE must be 'onefile' or 'onedir'")

ENTRY_POINT = PROJECT_ROOT / "steam_modern.py"
UI_ROOT = PROJECT_ROOT / "steam_ui"
UI_FILES = ("index.html", "styles.css", "p3r.css", "traces.css", "theme-bootstrap.js", "appearance.js", "app.js")

required_paths = [ENTRY_POINT, VERSION_FILE]
required_paths.extend(UI_ROOT / name for name in UI_FILES)
missing_paths = [str(path) for path in required_paths if not path.is_file()]
if missing_paths:
    raise FileNotFoundError("Missing release input(s): " + ", ".join(missing_paths))

a = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[(str(UI_ROOT / name), "steam_ui") for name in UI_FILES],
    hiddenimports=[
        # pywebview chooses its Windows backend dynamically.
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        "webview.platforms.win32",
        # Imported dynamically only if WebView2 cannot start.
        "steam_desktop",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Alternative renderers/platforms are not used by this Windows build.
        "cefpython3",
        "gi",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "webview.platforms.android",
        "webview.platforms.cef",
        "webview.platforms.cocoa",
        "webview.platforms.gtk",
        "webview.platforms.mshtml",
        "webview.platforms.qt",
    ],
    noarchive=False,
    optimize=1,
)

# pywebview's generic hook collects Android and legacy MSHTML assets that this
# Edge Chromium build never loads. Keep all three WebView2 loader directories:
# pywebview 6.2.1 enumerates them during startup even on an x64 process before
# Windows selects the native x64 loader.
def is_foreign_webview_asset(entry):
    destination = str(entry[0]).replace("\\", "/").lower()
    return (
        destination.endswith("webview/lib/pywebview-android.jar")
        or destination.endswith("webview/lib/webbrowserinterop.x86.dll")
    )


a.datas = [entry for entry in a.datas if not is_foreign_webview_asset(entry)]
a.binaries = [entry for entry in a.binaries if not is_foreign_webview_asset(entry)]
pyz = PYZ(a.pure)

common_exe_options = dict(
    name="SteamLibraryOrganizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    # target_arch only affects macOS. The release script validates the PE
    # machine field is AMD64 after every Windows build.
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(VERSION_FILE),
)

if BUILD_MODE == "onefile":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        **common_exe_options,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        **common_exe_options,
    )
    bundle = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="SteamLibraryOrganizer",
    )
