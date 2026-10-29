"""Name-based artwork lookup and reversible Steam custom-grid writes. No ML."""
from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import re
import secrets
import struct
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict, deque
from pathlib import Path

from steam_library_core import SteamError, SteamLibrary
from steam_nonsteam import _digest, _is_link, _known_title, _read, _install_root, parse_shortcuts
from steam_settings import app_data_dir

KINDS = {"cover": "竖版封面", "hero": "背景", "logo": "徽标", "wide": "横版封面"}
SUFFIXES = {"cover": "p", "hero": "_hero", "logo": "_logo", "wide": ""}
EXTENSIONS = ("png", "jpg", "jpeg", "webp", "tga")
MAX_IMAGE = 8 * 1024 * 1024
TTL = 30 * 60
ALIASES = {
    "明日方舟：终末地": ["Arknights: Endfield"], "绝区零": ["Zenless Zone Zero"],
    "云·绝区零": ["Zenless Zone Zero"], "原神": ["Genshin Impact"],
    "原神（国际服）": ["Genshin Impact"], "崩坏：星穹铁道": ["Honkai: Star Rail"],
    "崩坏3": ["Honkai Impact 3rd"], "鸣潮": ["Wuthering Waves"],
    "无畏契约": ["VALORANT"], "三角洲行动": ["Delta Force"],
    "远行星号": ["Starsector"], "守望先锋": ["Overwatch"],
}


def _normal(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def _allowed_url(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").casefold()
        port = parsed.port
    except (ValueError, AttributeError):
        return False
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and port in (None, 443) and (host in {
                "api.steampowered.com", "store.steampowered.com", "api.steamcmd.net",
                "www.steamgriddb.com", "cdn2.steamgriddb.com", "cdn.steamgriddb.com",
            } or host.endswith(".steamstatic.com")))


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed_url(newurl):
            raise SteamError("图片来源重定向到不支持的网站")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urllib.parse.urlsplit(req.full_url).hostname != urllib.parse.urlsplit(newurl).hostname:
            redirected.remove_header("Authorization")
        return redirected


def _fetch(url, *, key="", limit=MAX_IMAGE):
    if not _allowed_url(url):
        raise SteamError("不支持的图片来源")
    headers = {"User-Agent": "SteamLibraryOrganizer/1.1.2", "Accept": "application/json,image/png,image/jpeg"}
    if key:
        if urllib.parse.urlsplit(url).hostname != "www.steamgriddb.com":
            raise SteamError("图库密钥不能发送到其他网站")
        headers["Authorization"] = "Bearer " + key
    try:
        with urllib.request.build_opener(_Redirect()).open(urllib.request.Request(url, headers=headers), timeout=10) as response:
            data = response.read(limit + 1)
            if len(data) > limit:
                raise SteamError("图片或图库响应过大")
            return data
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403) and key:
            raise SteamError("SteamGridDB 密钥无效或没有访问权限") from None
        if exc.code == 429:
            raise SteamError("图库请求过于频繁，请稍后再试") from None
        raise SteamError(f"图片来源返回 HTTP {exc.code}") from None
    except (OSError, ValueError) as exc:
        raise SteamError("连接图片来源失败，请检查网络后重试") from exc


def _json(url, key=""):
    try:
        return json.loads(_fetch(url, key=key, limit=2 * 1024 * 1024))
    except (ValueError, UnicodeError):
        raise SteamError("图库返回了无法读取的数据") from None


def _image(data):
    """Accept bounded static PNG/JPEG only, never HTML/SVG or executable data."""
    if not isinstance(data, bytes):
        raise SteamError("图片数据不存在")
    width = height = 0
    if len(data) > MAX_IMAGE:
        raise SteamError("单张图片不能超过 8 MB")
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 45 and data[12:16] == b"IHDR":
        if not data.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82") or b"acTL" in data:
            raise SteamError("只支持完整的静态 PNG 图片")
        width, height = struct.unpack(">II", data[16:24])
        extension, mime = "png", "image/png"
    elif data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
        offset = 2
        while offset + 4 <= len(data):
            if data[offset] != 255:
                break
            marker = data[offset + 1]
            offset += 2
            if marker == 255:
                offset -= 1
                continue
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            size = int.from_bytes(data[offset:offset + 2], "big")
            if size < 2 or offset + size > len(data):
                break
            if marker in (0xC0, 0xC1, 0xC2) and size >= 8:
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                break
            offset += size
        extension, mime = "jpg", "image/jpeg"
    else:
        raise SteamError("只支持 PNG 和 JPG 图片")
    if not (0 < width <= 8192 and 0 < height <= 8192 and width * height <= 32_000_000):
        raise SteamError("图片尺寸无效或过大")
    return {"extension": extension, "mime": mime, "width": width, "height": height}


def _data_url(data, mime):
    return "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")


def _local_candidates(entry, folder=""):
    """Bounded read-only scan of one game's images, never execute/unpack files."""
    if not isinstance(folder, str) or len(folder) > 1024:
        raise SteamError("图片文件夹路径无效")
    exe = Path(str(entry.get("exe") or "").strip('"'))
    root = Path(folder.strip().strip('"')) if folder.strip() else _install_root(exe)
    if not root.is_absolute() or root == Path(root.anchor) or _is_link(root) or not root.is_dir():
        if not folder.strip():
            return {}, [], False
        raise SteamError("请选择具体的游戏或图片文件夹")
    root = root.resolve()
    if any(part.casefold() in {"windows", "system32", "syswow64"} for part in root.parts):
        if not folder.strip():
            return {}, [], False
        raise SteamError("不能在系统目录搜索游戏图片")
    # An automatically located executable must exist. For shared launchers,
    # require a user-selected game-specific image folder instead of guessing.
    if not folder.strip() and (not exe.is_file() or exe.name.casefold() in {"launcher.exe", "riotclientservices.exe", "explorer.exe", "wegame.exe"}):
        return {}, [str(root)], False
    skip = {"paks", "engine", "logs", "saved", "binaries", "shadercache", "node_modules", ".git", "localization", "crashreportclient"}
    cues = {"cover": r"cover|capsule|poster|portrait|竖版|海报|封面", "hero": r"hero|background|wallpaper|背景|壁纸",
            "wide": r"header|banner|landscape|横版|横幅", "logo": r"(?:^|[^a-z])logo(?:[^a-z]|$)|徽标|标志"}
    options = {kind: [] for kind in KINDS}
    queue, count, consumed = deque([(root, 0)]), 0, 0
    deadline, limited = time.monotonic() + 5, False
    while queue:
        directory, depth = queue.popleft()
        try:
            with os.scandir(directory) as entries:
                for node in entries:
                    count += 1
                    if count > 15000 or consumed > 64 * 1024 * 1024 or time.monotonic() > deadline:
                        limited = True
                        break
                    path = Path(node.path)
                    if _is_link(path):
                        continue
                    if node.is_dir(follow_symlinks=False):
                        if depth < 5 and node.name.casefold() not in skip:
                            queue.append((path, depth + 1))
                        continue
                    if path.suffix.casefold() not in {".png", ".jpg", ".jpeg"}:
                        continue
                    size = node.stat(follow_symlinks=False).st_size
                    if not 0 < size <= MAX_IMAGE:
                        continue
                    consumed += size
                    try:
                        data = _read(path, MAX_IMAGE)
                        info = _image(data)
                    except (SteamError, OSError):
                        continue
                    width, height = info["width"], info["height"]
                    ratio = width / height
                    roles = []
                    if width >= 300 and height >= 450 and .5 <= ratio <= .85:
                        roles.append("cover")
                    if width >= 960 and height >= 300 and 2.5 <= ratio <= 4:
                        roles.append("hero")
                    if width >= 460 and height >= 215 and 1.6 <= ratio <= 2.5:
                        roles.append("wide")
                    if path.suffix.casefold() == ".png" and width >= 200 and height >= 40 and re.search(cues["logo"], path.stem, re.I):
                        roles.append("logo")
                    for kind in roles:
                        explicit = bool(re.search(cues[kind], path.stem, re.I))
                        options[kind].append({"path": str(path), "sha": _digest(data),
                                              "width": width, "height": height, "explicit": explicit})
        except OSError:
            continue
        if limited:
            break
    for kind, items in options.items():
        items.sort(key=lambda x: (not x["explicit"], -x["width"] * x["height"], x["path"].casefold()))
        options[kind] = items[:6]
    return {k: v for k, v in options.items() if v}, [str(root)], limited


def _cache_root():
    return app_data_dir() / "artwork-cache"


def _download_image(url):
    """Reuse verified image bytes; allow the two official Steam CDN hosts."""
    if not _allowed_url(url):
        raise SteamError("不支持的图片来源")
    cache = _cache_root()
    path = cache / (_digest(url.encode()) + ".img")
    if not _is_link(cache):
        try:
            if time.time() - path.stat().st_mtime < 7 * 86400:
                data = _read(path, MAX_IMAGE)
                return {**_image(data), "data": data, "url": url}
        except (OSError, SteamError):
            pass
    sources = [url]
    parsed = urllib.parse.urlsplit(url)
    if parsed.hostname == "shared.fastly.steamstatic.com":
        sources.append(urllib.parse.urlunsplit(parsed._replace(netloc="shared.akamai.steamstatic.com")))
    last_error = None
    for source in sources:
        try:
            data = _fetch(source)
            info = _image(data)
        except SteamError as exc:
            last_error = exc
            continue
        if not _is_link(cache):
            try:
                cache.mkdir(exist_ok=True)
                # Cache only this app's hash-named files, with a 128 MB ceiling.
                size = sum(p.stat().st_size for p in cache.glob("*.img") if p.is_file())
                previous = path.stat().st_size if path.is_file() else 0
                if size - previous + len(data) <= 128 * 1024 * 1024:
                    SteamLibrary._atomic_write(path, data)
            except OSError:
                pass  # Caching is optional; inability to cache never loses art.
        return {**info, "data": data, "url": source}
    raise last_error or SteamError("图片来源没有返回可用图片")


def _asset_url(appid, path):
    if not isinstance(path, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+\.(png|jpg|jpeg)", path) or ".." in path:
        return None
    return f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/{path}"


def _steam_assets(appid):
    """Resolve current hash-based Steam CDN paths, including localized logos."""
    result = {kind: [] for kind in KINDS}
    warning = []
    # SteamCMD.net is a public read-only metadata mirror; image bytes remain on
    # Steam's CDN. Its full appinfo includes logos not exposed by StoreBrowse.
    try:
        common = _json(f"https://api.steamcmd.net/v1/info/{appid}")["data"][str(appid)]["common"]
        full = common.get("library_assets_full", {})
        for kind, field in (("cover", "library_capsule"), ("hero", "library_hero"),
                            ("logo", "library_logo"), ("wide", "library_header")):
            asset = full.get(field, {})
            for scale in ("image2x", "image"):
                variants = asset.get(scale, {})
                for language in ("schinese", "english"):
                    url = _asset_url(appid, variants.get(language))
                    if url:
                        result[kind].append(url)
                        break
    except (SteamError, KeyError, TypeError, AttributeError):
        warning.append("完整图片地址暂不可用，已尝试 Steam 商店资源。")
    if not all(result.values()):
        query = {"ids": [{"appid": appid}], "context": {"language": "schinese", "country_code": "CN"},
                 "data_request": {"include_assets": True}}
        try:
            data = _json("https://api.steampowered.com/IStoreBrowseService/GetItems/v1/?" +
                         urllib.parse.urlencode({"input_json": json.dumps(query)}))
            item = next(x for x in data["response"]["store_items"] if x.get("appid") == appid and x.get("success") == 1)
            assets = item.get("assets", {})
            for kind, fields in (("cover", ("library_capsule_2x", "library_capsule")),
                                 ("hero", ("library_hero_2x", "library_hero")),
                                 ("logo", ("library_logo",)), ("wide", ("header_2x", "header"))):
                if not result[kind]:
                    result[kind] = [u for f in fields if (u := _asset_url(appid, assets.get(f)))]
        except (SteamError, KeyError, TypeError, StopIteration):
            pass
    for kind, filename in (("cover", "library_600x900.jpg"), ("hero", "library_hero.jpg"),
                           ("logo", "logo.png"), ("wide", "header.jpg")):
        if not result[kind]:
            result[kind] = [f"https://shared.fastly.steamstatic.com/steam/apps/{appid}/{filename}"]
    return result, warning


class ArtworkManager:
    def __init__(self, organizer):
        self.organizer = organizer
        self.matches = OrderedDict()
        self.plans = OrderedDict()

    @property
    def library(self):
        return self.organizer.library

    def _snapshot(self):
        self.library.resolve_account()
        config = self.library.config_dir.resolve()
        raw = _read(config / "shortcuts.vdf")
        entries = parse_shortcuts(raw)[0]
        games = {}
        for item in entries:
            appid = item.get("appid")
            if isinstance(appid, int) and 0 < appid <= 0xFFFFFFFF:
                key = str(appid)
                if key in games:
                    raise SteamError("Steam 快捷方式存在重复编号，请先在 Steam 中检查")
                games[key] = item
        return {"account": _digest(str(config).encode()), "revision": _digest(raw), "config": config, "games": games}

    def _context(self, payload, game=True):
        if not isinstance(payload, dict):
            raise SteamError("封面请求无效")
        snap = self._snapshot()
        if any(payload.get(k) != snap[k] for k in ("account", "revision")):
            raise SteamError("Steam 账号或快捷方式已变化，请刷新游戏列表")
        if game and str(payload.get("game_id")) not in snap["games"]:
            raise SteamError("请选择已导入 Steam 的游戏")
        return snap

    @staticmethod
    def _grid(config):
        folder = config / "grid"
        if _is_link(folder):
            raise SteamError("Steam 图片目录不能是符号链接或目录联接")
        return folder

    def _paths(self, snap, game_id, kind):
        grid = self._grid(snap["config"])
        return [grid / f"{game_id}{SUFFIXES[kind]}.{ext}" for ext in EXTENSIONS]

    def _states(self, snap, game_id):
        paths = [p for kind in KINDS for p in self._paths(snap, game_id, kind)]
        paths.append(self._grid(snap["config"]) / f"{game_id}.json")
        return {p.name: _digest(_read(p, 32 * 1024 * 1024)) for p in paths}

    def load(self, payload=None):
        snap = self._snapshot()
        games = [{"id": key, "name": str(item.get("appname") or key),
                  "present": {kind: any(p.is_file() for p in self._paths(snap, key, kind)) for kind in KINDS}}
                 for key, item in snap["games"].items()]
        return {"account": snap["account"], "revision": snap["revision"],
                "games": sorted(games, key=lambda x: x["name"].casefold())}

    def current(self, payload):
        snap = self._context(payload)
        result = {}
        for kind in KINDS:
            for path in self._paths(snap, str(payload["game_id"]), kind):
                if path.is_file() and path.suffix in (".png", ".jpg", ".jpeg"):
                    try:
                        data = _read(path, MAX_IMAGE)
                        info = _image(data)
                        result[kind] = _data_url(data, info["mime"])
                    except SteamError:
                        pass
                    break
        return {"images": result}

    @staticmethod
    def _key(payload):
        key = payload.get("api_key", "")
        if not isinstance(key, str) or (key and not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key)):
            raise SteamError("SteamGridDB 密钥格式不正确")
        return key

    def search(self, payload):
        snap = self._context(payload)
        entry = snap["games"][str(payload["game_id"])]
        name = str(entry.get("appname") or "")
        canonical = _known_title(Path(entry.get("exe", "").strip('"')), name, entry.get("launchoptions", ""))
        query = payload.get("query", "")
        if not isinstance(query, str) or len(query) > 160 or any(c in query for c in "\0\r\n"):
            raise SteamError("搜索名称无效")
        terms = [query.strip()] if query.strip() else list(dict.fromkeys(ALIASES.get(canonical or name, []) + [name]))[:3]
        provider = payload.get("provider", "steam")
        if provider == "local":
            options, locations, limited = _local_candidates(entry, payload.get("folder", ""))
            self._context(payload)
            if not options:
                return {"matches": [], "message": "未找到可用的 PNG/JPG 图片。可指定启动器的图片目录；程序图标和封装资源不作为封面。", "locations": locations, "limited": limited}
            token = secrets.token_urlsafe(18)
            self.matches[token] = {"name": name, "provider": "local", "options": options,
                "game_id": str(payload["game_id"]), "account": snap["account"], "revision": snap["revision"], "created": time.monotonic()}
            while len(self.matches) > 100:
                self.matches.popitem(last=False)
            return {"matches": [{"id": token, "name": name + " · 本地图片", "exact": False, "provider": "local"}],
                    "locations": locations, "limited": limited, "message": "已找到本地图片，点击结果预览并确认。"}
        key = self._key(payload)
        if provider not in ("steam", "sgdb") or (provider == "sgdb" and not key):
            raise SteamError("使用 SteamGridDB 需要在图库设置中填写 API 密钥")
        found = {}
        for term in terms:
            if not term:
                continue
            if provider == "steam":
                data = _json("https://store.steampowered.com/api/storesearch/?" + urllib.parse.urlencode({"term": term, "l": "english", "cc": "US"}))
                rows = data.get("items", [])
            else:
                rows = _json("https://www.steamgriddb.com/api/v2/search/autocomplete/" + urllib.parse.quote(term, safe=""), key).get("data", [])
            for row in rows[:15]:
                remote_id, title = row.get("id"), row.get("name")
                if not isinstance(remote_id, int) or remote_id <= 0 or not isinstance(title, str):
                    continue
                if provider == "steam" and row.get("type") != "app":
                    continue
                found[remote_id] = {"remote_id": remote_id, "name": title[:180], "provider": provider,
                                    "exact": _normal(title) in {_normal(t) for t in terms}}
            if any(x["exact"] for x in found.values()):
                break
        matches = []
        for item in sorted(found.values(), key=lambda x: (not x["exact"], x["name"]))[:10]:
            token = secrets.token_urlsafe(18)
            self.matches[token] = {**item, "game_id": str(payload["game_id"]), "account": snap["account"],
                                   "revision": snap["revision"], "created": time.monotonic()}
            matches.append({"id": token, "name": item["name"], "exact": item["exact"], "provider": provider,
                            "source_url": f"https://store.steampowered.com/app/{item['remote_id']}/" if provider == "steam" else f"https://www.steamgriddb.com/game/{item['remote_id']}"})
        while len(self.matches) > 100:
            self.matches.popitem(last=False)
        return {"matches": matches}

    def preview(self, payload):
        snap = self._context(payload)
        before = self._states(snap, payload["game_id"])
        match = self.matches.get(payload.get("match_id"))
        if not match or time.monotonic() - match["created"] > TTL or any(match[k] != payload.get(k) for k in ("game_id", "account", "revision")):
            raise SteamError("搜索结果已失效，请重新搜索")
        warnings = []
        local_choices = {}
        if match["provider"] == "local":
            selection = payload.get("local_selection", {})
            if not isinstance(selection, dict) or any(k not in match["options"] for k in selection):
                raise SteamError("本地图片选择无效")
            assets = {}
            for kind, candidates in match["options"].items():
                index = selection.get(kind, 0)
                if type(index) is not int or not 0 <= index < len(candidates):
                    raise SteamError("本地图片选择无效")
                candidate = candidates[index]
                path = Path(candidate["path"])
                if _is_link(path):
                    raise SteamError("本地图片路径发生变化，请重新搜索")
                data = _read(path, MAX_IMAGE)
                if _digest(data) != candidate["sha"]:
                    raise SteamError("本地图片发生变化，请重新搜索")
                assets[kind] = {**_image(data), "data": data, "url": ""}
                local_choices[kind] = [{"name": Path(c["path"]).name, "width": c["width"], "height": c["height"]} for c in candidates]
        elif match["provider"] == "steam":
            options, warnings = _steam_assets(match["remote_id"])
        else:
            key = self._key(payload)
            if not key:
                raise SteamError("请填写 SteamGridDB API 密钥")
            options = {}
            for kind, endpoint in (("cover", "grids"), ("wide", "grids"), ("hero", "heroes"), ("logo", "logos")):
                query = {"types": "static", "nsfw": "false", "humor": "false", "epilepsy": "false"}
                if kind in ("cover", "wide"):
                    query["dimensions"] = "600x900" if kind == "cover" else "920x430,460x215"
                data = _json(f"https://www.steamgriddb.com/api/v2/{endpoint}/game/{match['remote_id']}?" + urllib.parse.urlencode(query), key)
                options[kind] = [x["url"] for x in data.get("data", [])[:3] if isinstance(x.get("url"), str) and _allowed_url(x["url"])]
        def download(kind):
            last_error = "来源暂无此类图片"
            for url in options.get(kind, [])[:3]:
                try:
                    return kind, _download_image(url), None
                except SteamError as exc:
                    last_error = str(exc)
            return kind, None, last_error
        downloads = []
        if match["provider"] != "local":
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                downloads = list(pool.map(download, KINDS))
                assets = {kind: image for kind, image, _ in downloads if image}
            warnings.extend(f"{KINDS[kind]}：{message}" for kind, _, message in downloads if message)
        self._context(payload)
        if self._states(snap, payload["game_id"]) != before:
            raise SteamError("下载图片期间原图发生变化，请重新预览")
        if not assets:
            detail = "；".join(dict.fromkeys(message for _, _, message in downloads if message))
            raise SteamError("图片下载未完成：" + detail)
        plan_id = secrets.token_urlsafe(20)
        self.plans[plan_id] = {"assets": assets, "match": match, "before": before, "created": time.monotonic()}
        while len(self.plans) > 4:
            self.plans.popitem(last=False)
        return {"plan_id": plan_id, "name": match["name"], "provider": match["provider"], "warnings": warnings,
                "local_choices": local_choices,
                "images": {kind: {"preview": _data_url(image["data"], image["mime"]), "width": image["width"],
                                  "height": image["height"], "source_url": image["url"]} for kind, image in assets.items()}}

    @staticmethod
    def _valid_filename(name):
        return isinstance(name, str) and bool(re.fullmatch(r"[0-9]{1,10}(?:p|_hero|_logo)?\.(?:png|jpg|jpeg|webp|tga|json)", name))

    def _commit(self, snap, changes, kind="apply"):
        grid = self._grid(snap["config"])
        backup = snap["config"] / "artwork-organizer-backups"
        if _is_link(backup) or any(not self._valid_filename(name) for name in changes):
            raise SteamError("封面备份路径无效")
        if sum(len(c["before"] or b"") for c in changes.values()) > 40 * 1024 * 1024:
            raise SteamError("本次原图备份超过 40 MB，请减少替换的图片数量")
        for name, change in changes.items():
            if _read(grid / name, 32 * 1024 * 1024) != change["before"]:
                raise SteamError("Steam 图片已变化，请重新预览")
        current = self._snapshot()
        if any(current[k] != snap[k] for k in ("account", "revision")):
            raise SteamError("Steam 账号或快捷方式已变化，请刷新游戏列表")
        backup.mkdir(exist_ok=True)
        grid.mkdir(exist_ok=True)
        receipt = backup / f"{time.time_ns()}-{secrets.token_hex(4)}.json"
        record = {"version": 1, "account": snap["account"], "kind": kind, "state": "pending", "changes": {
            name: {"before": None if c["before"] is None else base64.b64encode(c["before"]).decode(),
                   "before_sha": _digest(c["before"]), "after_sha": _digest(c["after"])} for name, c in changes.items()}}
        SteamLibrary._atomic_write(receipt, json.dumps(record).encode())
        written = []
        try:
            for name, change in changes.items():
                self.organizer._ensure_steam_stopped()
                current = self._snapshot()
                if any(current[k] != snap[k] for k in ("account", "revision")):
                    raise SteamError("Steam 账号或快捷方式已变化，请刷新游戏列表")
                path = grid / name
                if _read(path, 32 * 1024 * 1024) != change["before"]:
                    raise SteamError("Steam 图片已变化，请重新预览")
                if change["after"] is None:
                    path.unlink(missing_ok=True)
                else:
                    SteamLibrary._atomic_write(path, change["after"])
                written.append(name)
            record["state"] = "committed"
            SteamLibrary._atomic_write(receipt, json.dumps(record).encode())
        except Exception:
            for name in reversed(written):
                path, change = grid / name, changes[name]
                if _read(path, 32 * 1024 * 1024) != change["after"]:
                    raise SteamError(f"写入未完成，图片又被修改；原图备份位于：{receipt}") from None
                if change["before"] is None:
                    path.unlink(missing_ok=True)
                else:
                    SteamLibrary._atomic_write(path, change["before"])
            raise
        return str(receipt)

    def apply(self, payload):
        snap = self._context(payload)
        plan = self.plans.get(payload.get("plan_id"))
        if not plan or time.monotonic() - plan["created"] > TTL or any(plan["match"][k] != payload.get(k) for k in ("account", "revision", "game_id")):
            raise SteamError("图片预览已失效，请重新匹配")
        selected, replace = payload.get("selected"), payload.get("replace", False)
        if not isinstance(selected, list) or not selected or any(x not in plan["assets"] for x in selected) or not isinstance(replace, bool):
            raise SteamError("请选择预览中的图片")
        with self.library.write_lock():
            self.organizer._ensure_steam_stopped()
            snap = self._context(payload)
            if self._states(snap, payload["game_id"]) != plan["before"]:
                raise SteamError("Steam 图片已变化，请重新预览")
            changes, saved, skipped = {}, [], []
            grid = self._grid(snap["config"])
            for kind in dict.fromkeys(selected):
                paths = self._paths(snap, payload["game_id"], kind)
                existing = [p for p in paths if p.is_file()]
                if existing and not replace:
                    skipped.append(kind)
                    continue
                image = plan["assets"][kind]
                destination = f"{payload['game_id']}{SUFFIXES[kind]}.{image['extension']}"
                for path in existing:
                    changes[path.name] = {"before": _read(path, 32 * 1024 * 1024), "after": None}
                changes[destination] = {"before": _read(grid / destination, 32 * 1024 * 1024), "after": image["data"]}
                saved.append(kind)
            if "logo" in saved:
                name = f"{payload['game_id']}.json"
                if not (grid / name).exists():
                    changes[name] = {"before": None, "after": json.dumps({"nVersion": 1, "logoPosition": {
                        "pinnedPosition": "BottomLeft", "nWidthPct": 50, "nHeightPct": 50, "nVersion": 1}}).encode()}
            if not changes:
                return {"saved": [], "skipped": skipped, "backup": None}
            receipt = self._commit(snap, changes)
            self.plans.pop(payload["plan_id"], None)
            return {"saved": saved, "skipped": skipped, "backup": receipt}

    def auto(self, payload):
        snap = self._context(payload)
        if all(any(p.is_file() for p in self._paths(snap, payload["game_id"], kind)) for kind in KINDS):
            return {"status": "complete", "saved": []}
        self.organizer._ensure_steam_stopped()
        # Only unique, explicitly named artwork in this game's own directory
        # qualifies for automatic use. Ambiguous/local-folder choices need review.
        entry = snap["games"][str(payload["game_id"])]
        candidates, _, _ = _local_candidates(entry)
        local = {kind: [specific[0]] for kind, items in candidates.items()
                 if len(specific := [x for x in items if x["explicit"]]) == 1
                 and not any(p.is_file() for p in self._paths(snap, payload["game_id"], kind))}
        if local:
            token = secrets.token_urlsafe(18)
            self.matches[token] = {"name": str(entry.get("appname") or ""), "provider": "local", "options": local,
                "game_id": str(payload["game_id"]), "account": snap["account"], "revision": snap["revision"], "created": time.monotonic()}
            preview = self.preview({**payload, "match_id": token})
            result = self.apply({**payload, "plan_id": preview["plan_id"], "selected": list(preview["images"]), "replace": False})
            return {**result, "status": "matched", "provider": "local", "match_name": entry.get("appname")}
        search_payload = {**payload, "query": "", "provider": "steam"}
        choices = self.search(search_payload)["matches"]
        exact = [x for x in choices if x["exact"]]
        if not exact and self._key(payload):
            search_payload["provider"] = "sgdb"
            exact = [x for x in self.search(search_payload)["matches"] if x["exact"]]
        if len(exact) != 1:
            if exact:
                reason, label, message = "ambiguous", "有多个同名结果", "找到多个同名游戏，请搜索后选择对应版本。"
            elif not self._key(payload) and not choices:
                reason, label, message = "source_unavailable", "Steam 无同名条目", "Steam 图库未找到此游戏。可在“图片来源”填写 SteamGridDB 密钥，再自动补图。"
            elif not self._key(payload):
                reason, label, message = "no_exact_match", "未找到同名游戏", "Steam 只返回了相似名称，请搜索确认；也可配置 SteamGridDB 后重试。"
            else:
                reason, label, message = "no_exact_match", "图库未找到同名游戏", "Steam 和 SteamGridDB 均未找到唯一同名结果，可输入英文名搜索确认。"
            return {"status": "unmatched" if not exact else "ambiguous", "saved": [],
                    "reason": reason, "label": label, "message": message}
        preview = self.preview({**payload, "match_id": exact[0]["id"]})
        result = self.apply({**payload, "plan_id": preview["plan_id"], "selected": list(preview["images"]), "replace": False})
        return {**result, "status": "matched", "match_name": preview["name"]}

    def undo(self, payload):
        with self.library.write_lock():
            self.organizer._ensure_steam_stopped()
            snap = self._context(payload, game=False)
            backup = snap["config"] / "artwork-organizer-backups"
            if _is_link(backup):
                raise SteamError("封面备份路径无效")
            for receipt in sorted(backup.glob("*.json"), reverse=True):
                try:
                    record = json.loads(_read(receipt, 64 * 1024 * 1024) or b"{}")
                except (ValueError, OSError, SteamError):
                    continue
                if not isinstance(record, dict):
                    continue
                if record.get("version") != 1 or record.get("account") != snap["account"] or record.get("state") != "committed" or record.get("kind") != "apply":
                    continue
                changes = {}
                stored_changes = record.get("changes", {})
                if not isinstance(stored_changes, dict):
                    raise SteamError("封面备份格式无效")
                for name, item in stored_changes.items():
                    if not self._valid_filename(name):
                        raise SteamError("封面备份路径无效")
                    current = _read(self._grid(snap["config"]) / name, 32 * 1024 * 1024)
                    if not isinstance(item, dict) or not all(k in item for k in ("after_sha", "before_sha", "before")):
                        raise SteamError("封面备份格式无效")
                    if _digest(current) != item["after_sha"]:
                        raise SteamError("图片在写入后又被修改，未撤销；请保留当前图片或手动恢复备份")
                    try:
                        before = None if item["before"] is None else base64.b64decode(item["before"], validate=True)
                    except (ValueError, TypeError):
                        raise SteamError("封面备份校验失败") from None
                    if _digest(before) != item["before_sha"]:
                        raise SteamError("封面备份校验失败")
                    changes[name] = {"before": current, "after": before}
                if not changes:
                    raise SteamError("封面备份没有图片记录")
                safety = self._commit(snap, changes, kind="undo")
                record["state"] = "undone"
                SteamLibrary._atomic_write(receipt, json.dumps(record).encode())
                return {"restored": len(changes), "backup": safety}
            raise SteamError("没有可撤销的封面写入")
