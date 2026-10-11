"""Shared per-user settings for the desktop front ends.

The WebView2 and tkinter shells both use this module so switching the Steam
installation in either interface persists to the same UTF-8 JSON file.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path


_APP_DATA_DIRECTORY: Path | None = None


def app_data_dir() -> Path:
    """Return a writable per-user folder, falling back to the temp volume."""

    global _APP_DATA_DIRECTORY
    if _APP_DATA_DIRECTORY is not None:
        return _APP_DATA_DIRECTORY

    bases: list[Path] = []
    for value in (
        os.environ.get("LOCALAPPDATA"),
        tempfile.gettempdir(),
        str(Path.home() / "AppData" / "Local"),
    ):
        if value:
            candidate = Path(value)
            if candidate not in bases:
                bases.append(candidate)

    failures: list[str] = []
    for base in bases:
        folder = base / "SteamLibraryOrganizer"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=folder,
                prefix=".write-test-",
                delete=True,
            ):
                pass
            _APP_DATA_DIRECTORY = folder
            return folder
        except OSError as exc:
            failures.append(f"{folder}: {exc}")
    raise OSError("没有可写的应用数据目录：" + "; ".join(failures))


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def load_saved_steam_root(logger: logging.Logger | None = None) -> str | None:
    """Read the saved Steam root, returning ``None`` for missing/bad settings."""

    path = settings_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, json.JSONDecodeError):
        if logger is not None:
            logger.warning("无法读取设置文件：%s", path, exc_info=True)
        return None
    root = payload.get("steam_root") if isinstance(payload, dict) else None
    return root.strip() if isinstance(root, str) and root.strip() else None


def save_steam_root(root: str | os.PathLike[str]) -> None:
    """Atomically persist one normalized Steam installation path."""

    path = settings_path()
    temporary = path.with_suffix(".json.tmp")
    payload = json.dumps(
        {"steam_root": str(Path(root).resolve(strict=False))},
        ensure_ascii=False,
        indent=2,
    )
    try:
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
