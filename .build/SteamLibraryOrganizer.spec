# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(PROJECT_ROOT / "steam_modern.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[(str(PROJECT_ROOT / "steam_ui"), "steam_ui")],
    hiddenimports=[
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        "webview.platforms.win32",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "cefpython3",
        "gi",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "_tkinter",
        "tkinter",
        "steam_desktop",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
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
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
