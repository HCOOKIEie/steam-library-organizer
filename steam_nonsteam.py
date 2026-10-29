"""Local game discovery and lossless, reversible non-Steam shortcut imports.

Discovery never launches executables. Only a reviewed, server-held candidate
set can be imported. Existing binary VDF entries are retained byte for byte.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import stat
import struct
import subprocess
import threading
import time
import zlib
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path

from steam_library_core import SteamError, SteamLibrary

MAX_BYTES = 16 * 1024 * 1024
PLAN_TTL = 30 * 60
MAX_SCAN_ENTRIES = 500000
KNOWN_GAMES = {
    "yuanshen.exe": "原神", "genshinimpact.exe": "原神（国际服）",
    "starrail.exe": "崩坏：星穹铁道", "zenlesszonezero.exe": "绝区零",
    "bh3.exe": "崩坏3", "honkaiimpact3.exe": "崩坏3",
    "wuthering waves.exe": "鸣潮", "wuthering waves launcher.exe": "鸣潮",
    "endfield.exe": "明日方舟：终末地",
    "starsector.exe": "远行星号", "overwatch.exe": "守望先锋",
    "valorant.exe": "无畏契约", "valorant-win64-shipping.exe": "无畏契约",
    "deltaforceclient.exe": "三角洲行动", "deltaforceclient-win64-shipping.exe": "三角洲行动",
    "delta_force_launcher.exe": "三角洲行动",
    "exefile.exe": "EVE Online", "eve.exe": "EVE Online",
    "zenless zone zero cloud.exe": "云·绝区零",
}
SKIP_DIRS = {"windows", "$recycle.bin", "system volume information", "node_modules",
             ".git", "__pycache__", "redist", "_commonredist", "directx", "dotnet",
             "cache", "logs", "crashdumps", "temp", "steamapps", "plugins", "resources",
             "swiftshader", "locales", "sdk", "editor"}
SKIP_DIRS.update({"mods", "screenshots", "saves", "jre", "jre8", "java", "engine",
                 "deriveddatacache", "intermediate", "saved", "webcache", "webcaches",
                 "icreate", "tenprotect", "dependency_shared(999998)", "webview2rt",
                 "node", "python", ".venv", ".venv-release", "venv", "site-packages",
                 "anaconda", "comfyui", "comfy-desktop", "android-sdk", "gradle",
                 "windowsapps", "wpsystem", "appdata", "programdata", "users",
                 "program files", "program files (x86)", "downloads", "download"})
BAD_EXE = re.compile(r"unins|uninstall|setup|install|crash|report|helper|updat|repair|patch|"
                     r"vc_redist|vcredist|dxsetup|unitycrash|cef|webview|diagnostic|benchmark|"
                     r"easyanticheat|battleye|anticheat|cheat|oopz|uuremote|uu-remote|"
                     r"overlay|webengine|errorhandler|service|worker|safemode|resourcehacker|"
                     r"^7z|^unrar|^elevat|^binmay|^deploy-application|^eos|unrealversionselector", re.I)
BAD_EXE = re.compile(BAD_EXE.pattern + r"|卸载|安装|更新|崩溃|gpu_detect|tinydl|teniodl|"
                     r"ffmpeg|ffprobe|recorder|obs-|minibrowser|browser|assistant|"
                     r"unrealeditor|unityhub|godot.*editor|^unreal.*process|^javaw?$|"
                     r"^python|^node$|^cmd$|^powershell$|^explorer$", re.I)
GAME_NAMES = {"原神", "崩坏：星穹铁道", "崩坏:星穹铁道", "绝区零", "崩坏3", "鸣潮", "明日方舟：终末地"}
LAUNCHER_GAMES = {
    "nap_cn": "绝区零", "nap_global": "绝区零（国际服）", "zzz": "绝区零",
    "hk4e_cn": "原神", "hk4e_global": "原神（国际服）", "genshin": "原神",
    "hkrpg_cn": "崩坏：星穹铁道", "hkrpg_global": "崩坏：星穹铁道（国际服）",
    "bh3_cn": "崩坏3", "endfield": "明日方舟：终末地",
}
PLATFORM_EXES = {"epicgameslauncher.exe", "battle.net.exe", "battle.net launcher.exe",
                 "riotclientservices.exe", "wegame.exe", "wegameapp.exe", "redlauncher.exe",
                 "ubisoftconnect.exe", "upc.exe", "galaxyclient.exe"}
PLATFORM_EXES.update({"ealauncher.exe", "eadesktop.exe", "eaconnect_microsoft.exe", "eaegslauncher.exe",
                      "eaegsproxy.exe", "eagep.exe", "ealocalhostsvc.exe", "easteamlauncher.exe",
                      "easteamproxy.exe", "getgametoken.exe", "igoproxy32.exe", "igoproxy64.exe",
                      "link2ea.exe", "originlegacycompatibility.exe", "policyproxy32.exe", "policyproxy64.exe"})


def _known_title(path: Path, name: str = "", args: str = "") -> str | None:
    if path.name.casefold() in {"launcher.exe", "hoyoplay.exe"}:
        match = re.search(r'--game(?:=|\s+)["\']?([\w-]+)', args, re.I)
        if match:
            return LAUNCHER_GAMES.get(match.group(1).casefold())
        # A launcher without a game target is a platform, not an installed game.
        return None
    return KNOWN_GAMES.get(path.name.casefold())


def _title_key(name: str) -> str:
    return re.sub(r"[\s._:：·()（）\-]+", "", name).casefold()


def _install_root(path: Path) -> Path:
    for parent in path.parents:
        if parent.name.casefold() == "binaries":
            project = parent.parent
            outer = project.parent
            return outer if (outer / "Engine").is_dir() or (outer / (project.name + ".exe")).is_file() else project
    return path.parent


def _game_key(item: dict) -> str:
    path = Path(item.get("exe", "").strip().strip('"'))
    args = item.get("args", item.get("launchoptions", ""))
    if _package_target(path, args):
        return "package:" + args.casefold()
    title = _known_title(path, item.get("name", item.get("appname", "")),
                         item.get("args", item.get("launchoptions", "")))
    if title:
        return "known:" + _title_key(title)
    root = _install_root(path)
    if root != path.parent or (root / "Engine").is_dir() or (root / path.stem / "Binaries").is_dir():
        return "unreal:" + _identity(str(root))
    # Exact command identity remains the fallback: names alone must never merge
    # unrelated games or two targets of a shared launcher.
    args = item.get("args", item.get("launchoptions", ""))
    shared = re.search(r"launcher|retroarch|pcsx2|rpcs3|yuzu|ryujinx|dosbox|scummvm", path.stem, re.I)
    return "command:" + _identity(str(path), args if shared else "")


def _group_candidates(items: list[dict]) -> tuple[list[dict], int]:
    groups = {}
    for item in items:
        groups.setdefault(_game_key(item), []).append(item)
    result = []
    for group in groups.values():
        # Preserve the user's shortcut and its launch arguments ahead of a raw
        # game binary, and a packaged launcher ahead of Unreal's internal EXE.
        group.sort(key=lambda x: (not x.get("existing", False),
                                  x["source"] != "桌面 / 开始菜单",
                                  x["source"] != "游戏平台记录",
                                  "-shipping" in Path(x["exe"]).stem.casefold(),
                                  len(Path(x["exe"]).parts), x["exe"].casefold(), x["args"]))
        existing = any(x.get("existing", False) for x in group)
        for item in group:
            item["existing"] = existing
        primary = dict(group[0])
        if len(group) > 1:
            primary["alternatives"] = group
        result.append(primary)
    result.sort(key=lambda x: (x["confidence"] != "recognized", x["name"].casefold()))
    return result, len(items) - len(result)


def _digest(data: bytes | None) -> str:
    return hashlib.sha256(b"missing" if data is None else b"file\0" + data).hexdigest()


def _identity(exe: str, args: str = "") -> str:
    return os.path.normcase(os.path.normpath(exe.strip().strip('"'))).casefold() + "\0" + args.strip()


def _is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _read(path: Path, limit: int = MAX_BYTES) -> bytes | None:
    if _is_link(path):
        raise SteamError("快捷方式文件不能是符号链接")
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except FileNotFoundError:
        return None
    if len(data) > limit:
        raise SteamError("Steam 快捷方式文件过大，未进行修改")
    return data


def parse_shortcuts(data: bytes | None) -> tuple[list[dict], int]:
    """Validate binary KeyValues; return entries and root terminator offset.

    Values unknown to us are retained in the original byte stream. Unsupported
    wire types fail closed rather than rebuilding (and losing) Steam fields.
    """
    if data is None:
        return [], 11
    if not data or len(data) > MAX_BYTES:
        raise SteamError("Steam 快捷方式文件为空或无效，未进行修改")
    pos = 0

    def take(n):
        nonlocal pos
        if pos + n > len(data):
            raise ValueError("truncated")
        result = data[pos:pos + n]
        pos += n
        return result

    def string():
        nonlocal pos
        end = data.index(b"\0", pos)
        result = data[pos:end].decode("utf-8", errors="surrogateescape")
        pos = end + 1
        return result

    def object_value(depth=0):
        nonlocal pos
        if depth > 16:
            raise ValueError("nesting")
        fields = {}
        while True:
            offset = pos
            kind = take(1)[0]
            if kind == 8:
                return fields, offset
            key = string()
            if key in fields:
                raise ValueError("duplicate key")
            if kind == 0:
                value, _ = object_value(depth + 1)
            elif kind == 1:
                value = string()
            elif kind == 2:
                value = struct.unpack("<I", take(4))[0]
            elif kind in (3, 4, 6):
                value = take(4)
            elif kind in (7, 10):
                value = take(8)
            else:
                raise ValueError("unsupported type")
            fields[key] = value

    try:
        if take(1) != b"\x00" or string() != "shortcuts":
            raise ValueError("root")
        values, end = object_value()
        if take(1) != b"\x08" or pos != len(data):
            raise ValueError("trailing bytes")
        entries = []
        for key, value in values.items():
            if not key.isascii() or not key.isdigit() or not isinstance(value, dict):
                raise ValueError("entry")
            item = {k.casefold(): v for k, v in value.items()}
            if len(item) != len(value) or ("appid" in item and not isinstance(item["appid"], int)):
                raise ValueError("ambiguous fields")
            if not isinstance(item.get("exe", ""), str) or not isinstance(item.get("launchoptions", ""), str):
                raise ValueError("launch fields")
            entries.append({**item, "index": int(key)})
        return entries, end
    except (ValueError, IndexError, struct.error, UnicodeError) as exc:
        raise SteamError("无法完整读取 Steam 快捷方式文件，已停止以保留原数据") from exc


def _string_field(key, value):
    return b"\x01" + key.encode() + b"\0" + value.encode("utf-8") + b"\0"


def _int_field(key, value):
    return b"\x02" + key.encode() + b"\0" + struct.pack("<I", value)


def encode_shortcut(index: int, item: dict, appid: int, category: str) -> bytes:
    result = b"\x00" + str(index).encode() + b"\0" + _int_field("appid", appid)
    for key, value in (("AppName", item["name"]), ("Exe", '"' + item["exe"] + '"'),
                       ("StartDir", '"' + item["start_dir"] + '"'), ("icon", ""),
                       ("ShortcutPath", ""), ("LaunchOptions", item["args"])):
        result += _string_field(key, value)
    for key, value in (("IsHidden", 0), ("AllowDesktopConfig", 1), ("AllowOverlay", 1),
                       ("OpenVR", 0), ("Devkit", 0), ("DevkitOverrideAppID", 0), ("LastPlayTime", 0)):
        result += _int_field(key, value)
    result += _string_field("DevkitGameID", "") + _string_field("FlatpakAppID", "")
    return result + b"\x00tags\0" + (_string_field("0", category) if category else b"") + b"\x08\x08"


def _package_target(path: Path, args: str) -> bool:
    system_explorer = Path(os.environ.get("WINDIR", "C:/Windows")) / "explorer.exe"
    return (os.name == "nt" and _identity(str(path)) == _identity(str(system_explorer))
            and bool(re.fullmatch(r"shell:AppsFolder\\[A-Za-z0-9_.-]+![A-Za-z0-9_.-]+", args)))


def _exe_ok(path: Path, *, packaged=False) -> bool:
    try:
        if path.suffix.lower() != ".exe" or BAD_EXE.search(path.name) or not path.is_file():
            return False
        if path.stem.casefold() in {"cmd", "powershell", "pwsh", "wscript", "cscript", "explorer"} and not packaged:
            return False
        with path.open("rb") as stream:
            return stream.read(2) == b"MZ"
    except OSError:
        return False


def _signature(path: Path):
    info = path.stat()
    return (info.st_size, info.st_mtime_ns)


def _game_evidence(path: Path, siblings: set[str] | None = None) -> tuple[str, str] | None:
    known = KNOWN_GAMES.get(path.name.casefold())
    if known:
        return known, "已识别游戏"
    if BAD_EXE.search(path.name) or path.name.casefold() in PLATFORM_EXES:
        return None
    if path.name.casefold() in {"hyp.exe", "games.exe"} and any("launcher" in p.casefold() for p in path.parts[:-1]):
        return None
    if siblings is None:
        try:
            with os.scandir(path.parent) as entries:
                siblings = {entry.name.casefold() for entry in entries}
        except OSError:
            return None
    if (path.stem + "_Data").casefold() in siblings and (path.parent / (path.stem + "_Data")).is_dir():
        return path.stem, "Unity 游戏目录"
    if path.name.lower().endswith("-shipping.exe") and "binaries" in {p.lower() for p in path.parts}:
        return re.sub(r"-(Win64|Win32|WinGDK)-Shipping$", "", path.stem, flags=re.I), "Unreal 游戏目录"
    if (path.stem + ".pck").casefold() in siblings:
        return path.stem, "Godot 游戏目录"
    if {"renpy", "game"} <= siblings:
        return path.parent.name, "Ren’Py 游戏目录"
    if "www" in siblings and (path.parent / "www" / "data" / "System.json").is_file():
        return path.parent.name, "RPG Maker 游戏目录"
    if path.stem.casefold() in siblings and (path.parent / path.stem / "Binaries").is_dir():
        return path.stem, "Unreal 游戏目录"
    if siblings & {"data.win", "gameinfo.txt"}:
        return path.stem, "游戏运行文件"
    if "microsoftgame.config" in siblings:
        try:
            document = ET.fromstring(_read(path.parent / "MicrosoftGame.config", 128 * 1024) or b"")
            executable = next((x for x in document.findall("./ExecutableList/Executable")
                               if (path.parent / x.get("Name", "")).resolve() == path.resolve()), None)
            visual = document.find("ShellVisuals")
            if executable is not None:
                title = visual.get("DefaultDisplayName", path.stem) if visual is not None else path.stem
                return title if not title.startswith("ms-resource:") else path.stem, "Xbox 游戏安装记录"
        except (OSError, ValueError, ET.ParseError, SteamError):
            pass
    return None


def _game_location(path: Path) -> bool:
    return any(re.search(r"games?|游戏|mihoyo|hoyoplay|biligame|hypergryph|kuro|鸣潮|原神|崩坏|绝区零|starsector|eve online|valorant|overwatch|delta force", part, re.I)
               for part in path.parts[:-1])


def _registry_locations() -> list[Path]:
    if os.name != "nt":
        return []
    import winreg
    roots = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for key_name in (r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                         r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
            try:
                with winreg.OpenKey(hive, key_name) as parent:
                    for index in range(min(winreg.QueryInfoKey(parent)[0], 3000)):
                        try:
                            with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as child:
                                location, _ = winreg.QueryValueEx(child, "InstallLocation")
                                if isinstance(location, str) and location.strip():
                                    roots.append(Path(os.path.expandvars(location.strip().strip('"'))))
                        except OSError:
                            continue
            except OSError:
                continue
    return roots


def _shortcut_targets() -> tuple[list[dict], list[str]]:
    """Resolve .lnk through Windows Shell without executing their targets."""
    if os.name != "nt":
        return [], []
    script = r'''
    $ErrorActionPreference = 'Stop'
    [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
    $shell = New-Object -ComObject WScript.Shell
    $folders = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('CommonDesktopDirectory'),
      [Environment]::GetFolderPath('StartMenu'), [Environment]::GetFolderPath('CommonStartMenu')) | Select-Object -Unique
    $items = @(foreach ($folder in $folders) {
      if ($folder -and (Test-Path -LiteralPath $folder)) {
        Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1000 | ForEach-Object {
          try { $s = $shell.CreateShortcut($_.FullName)
            [pscustomobject]@{ name=$_.BaseName; exe=$s.TargetPath; args=$s.Arguments; start_dir=$s.WorkingDirectory }
          } catch {}
        }
      }
    })
    ConvertTo-Json -InputObject $items -Compress
    '''
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                capture_output=True, timeout=12, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise ValueError("shell")
        return json.loads(result.stdout.decode("utf-8-sig")), []
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return [], ["部分桌面或开始菜单快捷方式无法读取，可手动选择游戏文件夹。"]


GAME_FOLDERS = {"game", "games", "游戏", "单机", "单机游戏", "网游", "二游", "xdgame",
                "gog games", "epic games", "biligame", "mihoyo", "hoyoplay", "mihoyo launcher",
                "hypergryph launcher", "wegameapps", "tencent games", "xboxgames"}


def _drive_roots() -> list[Path]:
    if os.name != "nt":
        return []
    import ctypes
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    # Local fixed/removable disks only; never probe disconnected network shares.
    return [Path(f"{chr(65+i)}:/") for i in range(26) if mask & (1 << i)
            and ctypes.windll.kernel32.GetDriveTypeW(f"{chr(65+i)}:\\") in (2, 3)]


def _common_game_locations() -> list[Path]:
    roots = []
    for drive in _drive_roots():
        try:
            for path in drive.iterdir():
                if not path.is_dir() or _is_link(path):
                    continue
                lowered = path.name.casefold()
                if lowered in {"program files", "program files (x86)"}:
                    # Games may live under a publisher directory, even without
                    # an uninstall record. Each child gets only a shallow probe.
                    roots.extend(p for p in path.iterdir() if p.is_dir() and not _is_link(p))
                elif lowered not in SKIP_DIRS and not lowered.startswith(("$", ".")):
                    roots.append(path)
        except OSError:
            continue
    return sorted(roots, key=lambda p: (p.name.casefold() not in GAME_FOLDERS, str(p).casefold()))


def _platform_entries() -> list[dict]:
    """Read Epic install manifests, not the client's download/cache inventory."""
    if os.name != "nt":
        return []
    folder = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Epic/EpicGamesLauncher/Data/Manifests"
    entries = []
    try:
        for manifest in list(folder.glob("*.item"))[:1000]:
            try:
                data = json.loads(_read(manifest, 512 * 1024) or b"{}")
                if not isinstance(data, dict) or data.get("bIsIncompleteInstall") or not data.get("bIsApplication", True):
                    continue
                root = Path(data["InstallLocation"])
                path = (root / data["LaunchExecutable"]).resolve()
                if not root.is_absolute() or not path.is_relative_to(root.resolve()) or not _exe_ok(path):
                    continue
                entries.append({"name": str(data.get("DisplayName") or path.stem), "exe": str(path),
                                "args": str(data.get("LaunchCommand") or ""), "start_dir": str(path.parent)})
            except (OSError, ValueError, KeyError, TypeError, SteamError):
                continue
    except OSError:
        pass
    return entries + _packaged_game_entries()


def _packaged_game_entries() -> list[dict]:
    """Use Windows' registered game entry, not a protected Xbox game binary."""
    if os.name != "nt":
        return []
    script = r'''
    $ErrorActionPreference = 'Stop'
    [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
    $games = @(Get-AppxPackage | Where-Object {
      $_.InstallLocation -and (Test-Path -LiteralPath (Join-Path $_.InstallLocation 'MicrosoftGame.config'))
    } | Select-Object InstallLocation,PackageFamilyName)
    $apps = @(Get-StartApps | Select-Object Name,AppID)
    [pscustomobject]@{ games=$games; apps=$apps } | ConvertTo-Json -Depth 4 -Compress
    '''
    try:
        response = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                  capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        if response.returncode:
            return []
        data = json.loads(response.stdout.decode("utf-8-sig"))
        entries = []
        explorer = Path(os.environ.get("WINDIR", "C:/Windows")) / "explorer.exe"
        for game in data.get("games", [])[:1000]:
            prefix = game.get("PackageFamilyName", "") + "!"
            if prefix == "!":
                continue
            for app in data.get("apps", [])[:5000]:
                app_id = app.get("AppID", "")
                args = "shell:AppsFolder\\" + app_id
                if app_id.startswith(prefix) and _package_target(explorer, args):
                    entries.append({"name": app.get("Name") or app_id, "exe": str(explorer), "args": args,
                                    "start_dir": str(explorer.parent), "confirmed": True})
        return entries
    except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired):
        return []


def discover_games(roots: list[str], automatic: bool, cancel: threading.Event, excluded: list[Path]) -> dict:
    candidates, warnings = {}, []
    deadline = time.monotonic() + 60
    scanned = 0
    limited = False
    scanned_roots = []
    incomplete_roots = set()
    excluded = [p.resolve() for p in excluded]

    def add(path, source, name=None, args="", start_dir="", confirmed=False):
        try:
            path = Path(path).resolve()
            if any(path.is_relative_to(p) for p in excluded) or not _exe_ok(path, packaged=_package_target(path, args)):
                return
            if any(c in args for c in ("\0", "\r", "\n")) or len(args) > 4096:
                return
            known = _known_title(path, name or "", args)
            if path.name.casefold() in PLATFORM_EXES or (path.name.casefold() in {"launcher.exe", "hoyoplay.exe"}
                                                       and not known and not args and source != "指定目录"):
                return
            if path.name.casefold() in {"hyp.exe", "games.exe"} and any("launcher" in p.casefold() for p in path.parts[:-1]):
                return
            evidence = _game_evidence(path)
            key = _identity(str(path), args)
            # A desktop shortcut preserves launcher arguments and working directory.
            if key in candidates:
                return
            title = known or name or (evidence[0] if evidence else path.stem)
            working = Path(start_dir).resolve() if start_dir else path.parent
            if not working.is_dir():
                working = path.parent
            recognized = bool(confirmed or known)
            candidates[key] = {"id": secrets.token_urlsafe(12), "name": title[:160], "exe": str(path),
                               "args": args, "start_dir": str(working), "source": source,
                               "confidence": "recognized" if recognized else "review",
                               "reason": "Windows 已注册的游戏" if _package_target(path, args) else "游戏快捷方式（保留启动参数）" if confirmed else evidence[1] if evidence else "请确认这是游戏启动程序",
                               "signature": _signature(path)}
        except (OSError, ValueError):
            return

    locations = [(Path(root), True) for root in roots]
    manual_roots = {os.path.normcase(str(Path(root).resolve())) for root in roots}
    if automatic:
        shortcuts, shortcut_warnings = _shortcut_targets()
        warnings.extend(shortcut_warnings)
        for item in shortcuts:
            if cancel.is_set():
                break
            if not isinstance(item, dict) or not item.get("exe"):
                continue
            path = Path(item["exe"])
            if re.search(r"cheat|远程|加速器|修改器|oopz", item.get("name", ""), re.I):
                continue
            # Unknown shortcuts remain review-only, never selected automatically.
            if _game_evidence(path) or _game_location(path) or _known_title(path, item.get("name", ""), item.get("args") or ""):
                confirmed = item.get("name") in GAME_NAMES and bool(item.get("args"))
                add(path, "桌面 / 开始菜单", item.get("name"), item.get("args") or "", item.get("start_dir") or "", confirmed)
        registered = _registry_locations()
        locations += [(p, True) for p in registered if _game_location(p / "game.exe")]
        locations += [(p, p.name.casefold() in GAME_FOLDERS or bool(re.search(
            r"starsector|eve online|valorant|overwatch|delta force", p.name, re.I))) for p in _common_game_locations()]
        locations += [(p, False) for p in registered if not _game_location(p / "game.exe")]
        for item in _platform_entries():
            if cancel.is_set():
                break
            add(item["exe"], "游戏平台记录", item["name"], item["args"], item["start_dir"], item.get("confirmed", False))
    visited = {}
    pending, probes = deque(), deque()
    for root, explicit in locations:
        if cancel.is_set():
            break
        if not root.is_dir():
            if os.path.normcase(str(root.resolve())) in manual_roots:
                warnings.append(f"目录不可用：{root}")
            continue
        manual = os.path.normcase(str(root.resolve())) in manual_roots
        if not manual and re.search(r"cheat|修改器|加速器|mod manager", str(root), re.I):
            continue
        # Broken uninstall metadata sometimes points at an entire drive.
        if not root.parts or root == Path(root.anchor):
            warnings.append(f"跳过磁盘根目录，请选择具体游戏文件夹：{root}")
            continue
        resolved = root.resolve()
        system_root = Path(os.environ.get("WINDIR", "C:/Windows")).resolve()
        if not manual and (resolved.is_relative_to(system_root) or root.name.casefold() in SKIP_DIRS):
            continue
        if _is_link(root) or any(resolved.is_relative_to(p) for p in excluded):
            continue
        if not manual and ((root / ".git").is_dir() or (root / "node_modules").is_dir()):
            continue
        (pending if explicit else probes).append({"root": root, "explicit": explicit, "manual": manual,
                                                 "folders": deque([(root, 0)]), "scanned": 0})
    # Visit directories breadth-first and rotate between roots: one large game
    # or software installation must not exhaust the budget before later disks.
    while (pending or probes) and not cancel.is_set():
        if scanned > MAX_SCAN_ENTRIES or time.monotonic() > deadline or len(candidates) >= 1000:
            limited = True
            break
        state = (pending if pending else probes).popleft()
        root, explicit, manual = state["root"], state["explicit"], state["manual"]
        folder, depth = state["folders"].popleft()
        try:
            resolved = folder.resolve()
            identity = os.path.normcase(str(resolved))
            remaining = (9 if explicit else 3) - depth
            if visited.get(identity, -1) >= remaining or any(resolved.is_relative_to(p) for p in excluded):
                if state["folders"]:
                    (pending if explicit else probes).append(state)
                continue
            visited[identity] = remaining
            if depth == 0:
                scanned_roots.append(str(root))
            children, executables, sibling_names = [], [], set()
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        scanned += 1
                        if scanned > MAX_SCAN_ENTRIES or time.monotonic() > deadline or len(candidates) >= 1000:
                            limited = True
                            break
                        if cancel.is_set():
                            break
                        if state["scanned"] > (10000 if explicit else 1200):
                            incomplete_roots.add(str(root))
                            if explicit and len(warnings) < 20:
                                warnings.append(f"仅扫描了部分内容：{root}。可添加其游戏子文件夹继续扫描。")
                            state["folders"].clear()
                            break
                        sibling_names.add(entry.name.casefold())
                        if not entry.name.casefold().endswith(".exe") and not entry.is_dir(follow_symlinks=False):
                            continue
                        info = entry.stat(follow_symlinks=False)
                        if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                            continue  # Never follow junctions into unrelated trees.
                        if stat.S_ISDIR(info.st_mode):
                            if entry.name.casefold() not in SKIP_DIRS and not entry.name.startswith((".", "$")):
                                children.append(Path(entry.path))
                                state["scanned"] += 1
                        elif entry.name.lower().endswith(".exe"):
                            executables.append(Path(entry.path))
                            state["scanned"] += 1
                for path in executables:
                    evidence = _game_evidence(path, sibling_names)
                    if manual or evidence or (root.name.casefold() in GAME_FOLDERS and depth <= 2):
                        add(path, "指定目录" if manual else "安装目录")
                    if evidence:
                        state["explicit"] = explicit = True
            except OSError:
                if len(warnings) < 20:
                    warnings.append(f"无法读取：{folder}")
            if not limited and state["scanned"] <= (10000 if explicit else 1200):
                # A game can use a nested publisher/project/Binaries layout.
                for child in sorted(children, key=lambda p: p.name.casefold()):
                    if depth < (9 if explicit else 3):
                        state["folders"].append((child, depth + 1))
                    else:
                        incomplete_roots.add(str(root))
            if state["folders"]:
                (pending if explicit else probes).append(state)
        except OSError:
            if len(warnings) < 20:
                warnings.append(f"无法读取：{folder}")
    if limited:
        warnings.append("已到单次扫描上限；可选择更具体的游戏文件夹继续扫描。")
    grouped, merged = _group_candidates(list(candidates.values()))
    return {"candidates": grouped, "merged": merged, "locations": scanned_roots,
            "partial_roots": len(incomplete_roots), "incomplete_locations": sorted(incomplete_roots), "warnings": warnings[:25],
            "cancelled": cancel.is_set(), "limited": limited, "scanned": scanned}


class LocalGameImporter:
    def __init__(self, library: SteamLibrary, ensure_stopped):
        self.library = library
        self.ensure_stopped = ensure_stopped
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.plan = None

    def _path(self):
        self.library.resolve_account()
        return self.library.config_dir / "shortcuts.vdf"

    def scan(self, payload):
        if not isinstance(payload, dict):
            raise SteamError("扫描参数必须是对象")
        roots = payload.get("roots", [])
        automatic = payload.get("automatic", True)
        if not isinstance(automatic, bool) or not isinstance(roots, list) or len(roots) > 12 or any(
            not isinstance(p, str) or not p.strip() or not Path(p).is_absolute() for p in roots
        ):
            raise SteamError("请选择有效的绝对目录，最多 12 个")
        if not automatic and not roots:
            raise SteamError("请先选择游戏文件夹")
        if not self.lock.acquire(blocking=False):
            raise SteamError("正在扫描或导入，请等待完成")
        try:
            self.cancel.clear()
            self.plan = None
            path = self._path()
            original = _read(path)
            existing, _ = parse_shortcuts(original)
            identities = {_identity(x.get("exe", ""), x.get("launchoptions", "")) for x in existing}
            game_keys = {_game_key(x) for x in existing}
            excluded = [self.library.root] + [p / "steamapps" for p in self.library.library_folders()]
            result = discover_games(roots, automatic, self.cancel, excluded)
            variants = []
            for group in result["candidates"]:
                entries = group.get("alternatives", [group])
                already_added = any(_identity(x["exe"], x["args"]) in identities or _game_key(x) in game_keys for x in entries)
                group["existing"] = already_added
                for item in entries:
                    item["existing"] = already_added
                    variants.append(item)
            if result["cancelled"]:
                return {**result, "candidates": [], "plan_id": None}
            self.plan = {"id": secrets.token_urlsafe(20), "path": str(path), "fingerprint": _digest(original),
                         "created": time.monotonic(), "items": {x["id"]: x for x in variants}}
            def public(item):
                return {k: [public(x) for x in v] if k == "alternatives" else v
                        for k, v in item.items() if k != "signature"}
            return {**result, "plan_id": self.plan["id"], "account_id": self.library.account_id,
                    "candidates": [public(x) for x in result["candidates"]]}
        finally:
            self.lock.release()

    def apply(self, payload):
        if not isinstance(payload, dict):
            raise SteamError("导入参数必须是对象")
        selected = payload.get("selected")
        category = payload.get("category", "本机游戏")
        names = payload.get("names", {})
        if not isinstance(names, dict) or len(names) > 1000 or any(
            not isinstance(k, str) or not isinstance(v, str) or not v.strip() or len(v) > 160 or
            any(c in v for c in "\0\r\n") for k, v in names.items()
        ):
            raise SteamError("游戏名称不能为空，且最多 160 个字符")
        if not isinstance(selected, list) or not selected or len(selected) > 1000 or any(not isinstance(x, str) for x in selected):
            raise SteamError("请至少选择一个游戏")
        if not isinstance(category, str) or len(category) > 80 or any(c in category for c in "\0\r\n"):
            raise SteamError("分类名称无效")
        with self.lock, self.library.write_lock():
            self.ensure_stopped()
            plan = self.plan
            if not plan or payload.get("plan_id") != plan["id"] or time.monotonic() - plan["created"] > PLAN_TTL:
                raise SteamError("扫描结果已失效，请重新扫描")
            path = self._path()
            original = _read(path)
            if str(path) != plan["path"] or _digest(original) != plan["fingerprint"]:
                raise SteamError("Steam 账号或快捷方式已变化，请重新扫描")
            if any(x not in plan["items"] for x in selected):
                raise SteamError("所选游戏不属于本次扫描")
            entries, end = parse_shortcuts(original)
            identities = {_identity(x.get("exe", ""), x.get("launchoptions", "")) for x in entries}
            game_keys = {_game_key(x) for x in entries}
            appids = {x.get("appid") for x in entries}
            index = max((x["index"] for x in entries), default=-1) + 1
            added, skipped, encoded = 0, 0, b""
            imported_appids = []
            for key in dict.fromkeys(selected):
                item = dict(plan["items"][key])
                item["name"] = names.get(key, item["name"]).strip()
                identity = _identity(item["exe"], item["args"])
                game_key = _game_key(item)
                if identity in identities or game_key in game_keys:
                    skipped += 1
                    continue
                exe = Path(item["exe"])
                if not _exe_ok(exe, packaged=_package_target(exe, item["args"])) or _signature(exe) != item["signature"] or not Path(item["start_dir"]).is_dir():
                    raise SteamError(f"启动程序已变化或不存在：{item['name']}。请重新扫描")
                appid = zlib.crc32(('"' + item["exe"] + '"' + item["name"]).encode("utf-8")) | 0x80000000
                while appid in appids:
                    appid = ((appid + 1) & 0xFFFFFFFF) | 0x80000000
                encoded += encode_shortcut(index, item, appid, category.strip())
                identities.add(identity)
                game_keys.add(game_key)
                appids.add(appid)
                index += 1
                added += 1
                imported_appids.append(str(appid))
            if not added:
                raise SteamError("所选游戏已在 Steam 中，无需重复导入")
            base = original if original is not None else b"\x00shortcuts\0\x08\x08"
            updated = base[:end] + encoded + base[end:]
            parse_shortcuts(updated)
            backup_dir = path.parent / "nonsteam-organizer-backups"
            if _is_link(backup_dir):
                raise SteamError("备份目录不能是符号链接")
            backup_dir.mkdir(exist_ok=True)
            receipt = backup_dir / (f"{time.time_ns()}-{secrets.token_hex(4)}.json")
            snapshot = {"version": 1, "account_id": self.library.account_id,
                        "before": None if original is None else base64.b64encode(original).decode("ascii"),
                        "before_sha": _digest(original), "after_sha": _digest(updated), "added": added}
            SteamLibrary._atomic_write(receipt, json.dumps(snapshot).encode("utf-8"))
            self.ensure_stopped()
            if _digest(_read(path)) != plan["fingerprint"]:
                raise SteamError("写入前快捷方式发生变化，请重新扫描")
            SteamLibrary._atomic_write(path, updated)
            self.plan = None
            return {"added": added, "skipped": skipped, "backup": str(receipt), "account_id": self.library.account_id,
                    "appids": imported_appids}

    def undo(self):
        with self.lock, self.library.write_lock():
            self.ensure_stopped()
            path = self._path()
            backups = path.parent / "nonsteam-organizer-backups"
            if _is_link(backups):
                raise SteamError("备份目录不能是符号链接")
            records = sorted(backups.glob("*.json"), reverse=True)
            current = _read(path)
            chosen = None
            for receipt in records:
                try:
                    raw = _read(receipt, MAX_BYTES * 2)
                    data = json.loads(raw or b"")
                    if isinstance(data, dict) and data.get("version") == 1 and data.get("account_id") == self.library.account_id and data.get("after_sha") == _digest(current):
                        chosen = (receipt, data)
                        break
                except (ValueError, OSError, SteamError):
                    continue
            if not chosen:
                raise SteamError("没有可撤销的导入，或 Steam 快捷方式已被修改；为保留新改动，未恢复旧文件")
            receipt, data = chosen
            try:
                before = None if data["before"] is None else base64.b64decode(data["before"], validate=True)
                if _digest(before) != data["before_sha"]:
                    raise ValueError("hash")
                parse_shortcuts(before)
            except (ValueError, KeyError, TypeError) as exc:
                raise SteamError("备份校验失败，未修改 Steam") from exc
            # Save the current file before restoring; a matching receipt ensures
            # intervening edits can never be silently overwritten.
            safety = receipt.with_suffix(".pre-undo.vdf")
            SteamLibrary._atomic_write(safety, current)
            self.ensure_stopped()
            if _digest(_read(path)) != _digest(current):
                raise SteamError("恢复前快捷方式已变化，未修改 Steam")
            if before is None:
                path.unlink()
            else:
                SteamLibrary._atomic_write(path, before)
            self.plan = None
            return {"restored": str(receipt), "safety_backup": str(safety)}
