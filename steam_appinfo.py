"""Offline reader for Steam's local ``appinfo.vdf`` cache.

``appinfo.vdf`` is the client-side database Steam itself uses to render app
names, types, genres and store metadata. Reading it means the organizer can
group games by exactly the name the user sees in the Steam library - including
Simplified Chinese titles such as "艾尔登法环" - with no network requests.

Binary VDF layout (version 29):

    uint32 magic ("DV\\x07"), uint32 universe, uint64 string_table_offset

    record (repeated until string_table_offset):
        uint32 appid
        uint32 size            # bytes that follow
        uint32 info_state
        uint32 last_updated
        uint64 pics_token
        uint8  sha1[20]
        uint32 change_number
        uint8  sha1_2[20]
        binary VDF (size - 60 bytes)

    binary VDF stream:
        uint8 type, [uint32 string_table_index | cstring key], value
        type 0x00 object, 0x01 string, 0x02 int32, 0x03 float32,
       0x04 uint32, 0x05 wide string, 0x06 colour, 0x07 uint64, 0x08 end
"""

from __future__ import annotations

import json
import os
import struct
import sys
import time
from pathlib import Path

MAGIC_V29 = 0x07564429
HEADER_SIZE = 68  # appid + size + 60 bytes of hashes/flags before the VDF
CACHE_SCHEMA = 2


class AppInfoError(RuntimeError):
    """Raised when the local appinfo cache cannot be used."""


def _read_cstring(buf: bytes, pos: int) -> tuple[str, int]:
    end = buf.index(b"\x00", pos)
    return buf[pos:end].decode("utf-8", "replace"), end + 1


def _read_wstring(buf: bytes, pos: int) -> tuple[str, int]:
    end = pos
    while True:
        end = buf.index(b"\x00\x00", end)
        if end % 2 == pos % 2:
            break
        end += 1
    return buf[pos:end].decode("utf-16-le", "replace"), end + 2


def _parse_contents(
    buf: bytes,
    pos: int,
    table: list[str] | None,
    depth: int = 0,
) -> tuple[dict, int]:
    """Parse object contents up to the closing 0x08 token."""
    if depth > 24:
        raise ValueError("binary VDF nested too deep")
    out: dict = {}
    while True:
        if pos >= len(buf):
            raise ValueError("unexpected end of binary VDF")
        kind = buf[pos]
        pos += 1
        if kind == 0x08:
            return out, pos
        if table is None:
            key, pos = _read_cstring(buf, pos)
        else:
            index = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
            if index >= len(table):
                raise ValueError(f"string table index {index} out of range")
            key = table[index]

        if kind == 0x00:
            value, pos = _parse_contents(buf, pos, table, depth + 1)
        elif kind == 0x01:
            value, pos = _read_cstring(buf, pos)
        elif kind == 0x02:
            value = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
        elif kind == 0x03:
            value = struct.unpack_from("<f", buf, pos)[0]
            pos += 4
        elif kind == 0x04:
            value = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
        elif kind == 0x05:
            value, pos = _read_wstring(buf, pos)
        elif kind == 0x06:
            value = buf[pos : pos + 4].hex()
            pos += 4
        elif kind == 0x07:
            value = struct.unpack_from("<Q", buf, pos)[0]
            pos += 8
        else:
            raise ValueError(f"unsupported binary VDF type 0x{kind:02x}")
        out[key] = value


def _parse_root(buf: bytes, pos: int, table: list[str] | None) -> tuple[dict, int]:
    """Parse the outermost object, which begins with a type-0 token and key."""
    if buf[pos] != 0x00:
        raise ValueError(f"expected object at {pos}")
    pos += 1
    if table is None:
        _, pos = _read_cstring(buf, pos)
    else:
        pos += 4
    return _parse_contents(buf, pos, table)


def _string_table(buf: bytes, offset: int) -> list[str]:
    blob = buf[offset + 4 :]
    return [part.decode("utf-8", "replace") for part in blob.split(b"\x00")]


def _load(path: Path) -> tuple[bytes, list[str]]:
    buf = path.read_bytes()
    if len(buf) < 16:
        raise AppInfoError("appinfo.vdf is too small to be valid")
    magic = struct.unpack_from("<I", buf, 0)[0]
    if magic != MAGIC_V29:
        raise AppInfoError(
            f"unsupported appinfo version 0x{magic:08x}; expected 0x{MAGIC_V29:08x}"
        )
    table_offset = struct.unpack_from("<Q", buf, 8)[0]
    if not 0 < table_offset < len(buf):
        raise AppInfoError("appinfo.vdf string table offset is out of range")
    return buf, _string_table(buf, table_offset)


def iter_records(path: Path):
    """Yield ``(appid, data)`` for every cached app. Malformed records stop the scan."""
    buf, table = _load(path)
    table_offset = struct.unpack_from("<Q", buf, 8)[0]
    pos = 16
    while pos + HEADER_SIZE <= table_offset:
        appid = struct.unpack_from("<I", buf, pos)[0]
        size = struct.unpack_from("<I", buf, pos + 4)[0]
        if appid == 0 or size < 60:
            break
        end = pos + 8 + size
        if end > table_offset:
            break
        try:
            data, _ = _parse_root(buf, pos + HEADER_SIZE, table)
        except (ValueError, IndexError, struct.error):
            pos = end
            continue
        yield appid, data
        pos = end


def _summarise(appid: int, data: dict, language: str) -> dict:
    common = data.get("common") if isinstance(data.get("common"), dict) else {}
    extended = data.get("extended") if isinstance(data.get("extended"), dict) else {}
    localized = common.get("name_localized") if isinstance(common.get("name_localized"), dict) else {}
    genres = common.get("genres") if isinstance(common.get("genres"), dict) else {}
    release = common.get("release_date") if isinstance(common.get("release_date"), dict) else {}

    developers: list[str] = []
    publishers: list[str] = []
    associations = common.get("associations")
    if isinstance(associations, dict):
        for association in associations.values():
            if not isinstance(association, dict):
                continue
            kind = str(association.get("type") or "").lower()
            value = str(association.get("name") or "").strip()
            if kind == "developer" and value and value not in developers:
                developers.append(value)
            elif kind == "publisher" and value and value not in publishers:
                publishers.append(value)

    # ``extended`` is present on older records and is still a useful fallback,
    # while ``common.associations`` carries all companies on modern records.
    extended_developer = str(extended.get("developer") or "").strip()
    extended_publisher = str(extended.get("publisher") or "").strip()
    if extended_developer and extended_developer not in developers:
        developers.insert(0, extended_developer)
    if extended_publisher and extended_publisher not in publishers:
        publishers.insert(0, extended_publisher)

    genre_ids = [str(value) for value in genres.values() if value]
    primary_genre = common.get("primary_genre")
    if primary_genre:
        primary_genre = str(primary_genre)
        if primary_genre in genre_ids:
            genre_ids.remove(primary_genre)
        genre_ids.insert(0, primary_genre)

    name = localized.get(language) or common.get("name") or ""
    return {
        "appid": appid,
        "name": name,
        "name_en": common.get("name") or "",
        "localized": bool(localized.get(language)),
        "type": common.get("type") or "",
        "genres": genre_ids,
        "primary_genre": str(primary_genre or ""),
        "developer": developers[0] if developers else "",
        "publisher": publishers[0] if publishers else "",
        "developers": developers,
        "publishers": publishers,
        "release_date": release.get("date") or common.get("steam_release_date") or "",
    }


def load_apps(steam_root: str | Path, language: str = "schinese") -> dict[int, dict]:
    """Parse the whole cache. Returns ``{appid: {...}}`` with localized names."""
    path = Path(steam_root) / "appcache" / "appinfo.vdf"
    if not path.exists():
        raise AppInfoError(f"appinfo.vdf not found: {path}")
    apps: dict[int, dict] = {}
    for appid, data in iter_records(path):
        apps[appid] = _summarise(appid, data, language)
    if not apps:
        raise AppInfoError("appinfo.vdf contained no readable app records")
    return apps


def load_cached(
    steam_root: str | Path,
    language: str = "schinese",
    cache_path: str | Path | None = None,
) -> dict[int, dict]:
    """Like :func:`load_apps` but reuses a JSON cache keyed on the vdf mtime."""
    steam_root = Path(steam_root)
    source = steam_root / "appcache" / "appinfo.vdf"
    if not source.exists():
        raise AppInfoError(f"appinfo.vdf not found: {source}")
    source_stat = source.stat()
    stamp = (
        f"{source.resolve()}:{source_stat.st_size}:"
        f"{source_stat.st_mtime_ns}:{language}:v{CACHE_SCHEMA}"
    )
    if cache_path is None:
        if getattr(sys, "frozen", False):
            # A packaged desktop app runs from a temporary/read-only bundle.
            # Keep the generated cache in the user's normal app-data folder.
            local_data = Path(os.environ.get("LOCALAPPDATA") or Path.home())
            cache_path = local_data / "SteamLibraryOrganizer" / "steam_appinfo_cache.json"
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        else:
            cache_path = Path(__file__).with_name("steam_appinfo_cache.json")
    cache_path = Path(cache_path)
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("schema") == CACHE_SCHEMA and cached.get("stamp") == stamp:
                return {int(k): v for k, v in cached["apps"].items()}
        except Exception:
            pass
    apps = load_apps(steam_root, language)
    payload = {
        "schema": CACHE_SCHEMA,
        "stamp": stamp,
        "generated": int(time.time()),
        "apps": apps,
    }
    try:
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except OSError:
        # Metadata parsing remains usable when the project directory is
        # read-only; the JSON cache is only a performance optimisation.
        pass
    return apps


if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else r"D:\steam"
    catalog = load_apps(root)
    print(f"apps parsed: {len(catalog)}")
    for probe in (5, 7, 105600, 1245620, 1229490):
        info = catalog.get(probe)
        print(probe, info)
