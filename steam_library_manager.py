"""Account-scoped folders, order, labels and personal playtime notes.

Editing this workspace never changes Steam data. Publishing is a separate,
reviewed transaction and only owns the slo-manual collection namespace.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import time
import uuid
from pathlib import Path

from steam_library_core import SteamError, SteamLibrary
from steam_nonsteam import _read, _digest, parse_shortcuts
from steam_settings import app_data_dir

PREFIX = "user-collections.slo-manual-"


def _label(value, maximum=60):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum or any(ord(c) < 32 for c in value):
        raise SteamError(f"名称不能为空，最多 {maximum} 个字")
    return value.strip()


def _encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


class LibraryManager:
    def __init__(self, organizer, storage: Path | None = None):
        self.organizer = organizer
        self.storage = storage
        self.games = {}
        self.account = None
        self.publish_plan = None

    @property
    def library(self):
        return self.organizer.library

    def _location(self):
        account = self.library.resolve_account()
        identity = str(self.library.root.resolve()).casefold() + ":" + str(account)
        token = hashlib.sha256(identity.encode()).hexdigest()[:24]
        base = self.storage if self.storage is not None else app_data_dir() / "library-workspaces"
        return token, base / (token + ".json")

    def _document(self, path):
        raw = _read(path)
        return self._decode(raw, path), _digest(raw)

    @staticmethod
    def _decode(raw, path):
        if raw is None:
            return {"version": 1, "folders": [], "items": {}, "order": []}
        try:
            doc = json.loads(raw)
            if doc.get("version") != 1 or not isinstance(doc["folders"], list) or not isinstance(doc["items"], dict) or not isinstance(doc["order"], list):
                raise ValueError()
            folder_ids, names = set(), set()
            for folder in doc["folders"]:
                if not isinstance(folder["id"], str) or not folder["id"] or folder["id"] in folder_ids:
                    raise ValueError()
                name = _label(folder["name"])
                if name.casefold() in names:
                    raise ValueError()
                folder_ids.add(folder["id"])
                names.add(name.casefold())
            if any(not isinstance(key, str) for key in doc["order"]) or len(set(doc["order"])) != len(doc["order"]):
                raise ValueError()
            for key, item in doc["items"].items():
                if not isinstance(key, str) or not isinstance(item, dict) or item.get("folder", "") not in folder_ids | {""}:
                    raise ValueError()
                tags = item.get("tags", [])
                if not isinstance(tags, list) or len(tags) > 50 or any(_label(tag) != tag for tag in tags):
                    raise ValueError()
                minutes = item.get("minutes")
                if minutes is not None and (type(minutes) is not int or not 0 <= minutes <= 60000000):
                    raise ValueError()
            return doc
        except (ValueError, TypeError, KeyError, AttributeError, SteamError) as exc:
            raise SteamError("游戏管理数据损坏，未覆盖文件。请检查：" + str(path)) from exc

    def _load_games(self):
        catalog = self.library.catalog(self.organizer.session_appids, "library", external_games=self.organizer.session_games)
        games = {}
        for appid, item in catalog.items():
            key = "steam:" + str(appid)
            games[key] = {"id": key, "appid": int(appid), "name": item["name"], "source": "Steam",
                          "form": item.get("form", "game"),
                          "installed": bool(item.get("installed")),
                          "steam_minutes": item.get("playtime") if item.get("playtime_known") else None}
        entries, _ = parse_shortcuts(_read(self.library.config_dir / "shortcuts.vdf"))
        for item in entries:
            appid = item.get("appid", 0)
            if not appid:
                continue
            key = "local:" + str(appid)
            if key in games:
                raise SteamError("非 Steam 游戏有重复 AppID，请先在 Steam 中检查")
            games[key] = {"id": key, "appid": appid, "name": item.get("appname") or "未命名游戏",
                          "source": "非 Steam", "installed": None, "steam_minutes": None}
        self.games = games

    def _view(self, doc, revision, account, path):
        order = [key for key in doc["order"] if key in self.games]
        order += sorted(self.games.keys() - set(order), key=lambda key: (self.games[key]["name"].casefold(), key))
        games = []
        for key in order:
            note = doc["items"].get(key, {})
            games.append({**self.games[key], "folder": note.get("folder", ""), "tags": note.get("tags", []), "minutes": note.get("minutes")})
        try:
            receipt = json.loads(_read(path.with_suffix(".undo.json")) or b"{}")
            can_undo = isinstance(receipt, dict) and receipt.get("after") == revision
        except (ValueError, OSError, SteamError):
            can_undo = False
        return {"account": account, "revision": revision, "folders": copy.deepcopy(doc["folders"]),
                "games": games, "can_undo": can_undo}

    def load(self, payload=None):
        account, path = self._location()
        self._load_games()
        self.account = account
        doc, revision = self._document(path)
        return self._view(doc, revision, account, path)

    def cover(self, payload):
        # Resolve metadata only; image bytes go straight from Steam's CDN to
        # the renderer. No Steam or local workspace writes are involved.
        from steam_artwork import _steam_assets
        self._checked(payload)
        game = self.games.get(payload.get("id"))
        if not game or game["source"] != "Steam":
            return {"url": None}
        assets, _ = _steam_assets(game["appid"])
        self._checked(payload)
        urls = assets.get("cover", [])
        return {"url": urls[0].replace("shared.fastly.steamstatic.com", "shared.akamai.steamstatic.com") if urls else None}

    def _checked(self, payload):
        if not isinstance(payload, dict):
            raise SteamError("请求必须是对象")
        account, path = self._location()
        if payload.get("account") != account or self.account != account:
            raise SteamError("Steam 账号或目录已改变，请刷新列表")
        doc, revision = self._document(path)
        if payload.get("revision") != revision:
            raise SteamError("列表已在其他窗口修改，请刷新后重试")
        return account, path, doc, revision

    def edit(self, payload):
        with self.library.write_lock():
            account, path, doc, revision = self._checked(payload)
            before = copy.deepcopy(doc)
            action = payload.get("action")
            folder = payload.get("folder", "")
            folders = {item["id"]: item for item in doc["folders"]}
            order = self._view(doc, revision, account, path)["games"]
            # Keep temporarily unavailable entries in saved order as well.
            saved_ids = set(doc["order"])
            doc["order"] += [x["id"] for x in order if x["id"] not in saved_ids]
            if action in {"create_folder", "rename_folder"}:
                name = _label(payload.get("name"))
                if any(x["name"].casefold() == name.casefold() and x["id"] != folder for x in doc["folders"]):
                    raise SteamError("已有同名文件夹")
                if action == "create_folder":
                    if len(folders) >= 200:
                        raise SteamError("最多创建 200 个文件夹")
                    doc["folders"].append({"id": uuid.uuid4().hex, "name": name})
                elif folder in folders:
                    folders[folder]["name"] = name
                else:
                    raise SteamError("文件夹已不存在，请刷新")
            elif action == "delete_folder":
                if folder not in folders:
                    raise SteamError("文件夹已不存在，请刷新")
                doc["folders"] = [x for x in doc["folders"] if x["id"] != folder]
                for item in doc["items"].values():
                    if item.get("folder") == folder:
                        item["folder"] = ""
            elif action == "undo":
                raw = _read(path.with_suffix(".undo.json"))
                try:
                    saved = json.loads(raw or b"{}")
                    if saved["after"] != revision:
                        raise ValueError()
                    # Validate the stored document through the same decoder.
                    doc = saved["before"]
                    if not isinstance(doc, dict) or doc.get("version") != 1:
                        raise ValueError()
                except (ValueError, TypeError, KeyError) as exc:
                    raise SteamError("没有可撤销的修改") from exc
            else:
                selected = payload.get("ids")
                if not isinstance(selected, list) or not selected or any(not isinstance(key, str) or key not in self.games for key in selected) or len(set(selected)) != len(selected):
                    raise SteamError("请重新选择游戏")
                picked = set(selected)
                selected = [key for key in doc["order"] if key in picked]
                if action == "move":
                    if folder and folder not in folders:
                        raise SteamError("目标文件夹不存在")
                    for key in selected:
                        doc["items"].setdefault(key, {})["folder"] = folder
                    # Newly dropped games append to the target folder's order.
                    doc["order"] = [key for key in doc["order"] if key not in picked] + selected
                elif action == "reorder":
                    target = payload.get("before")
                    if target is not None and (target not in self.games or target in picked):
                        raise SteamError("排序目标无效")
                    rest = [key for key in doc["order"] if key not in picked]
                    index = rest.index(target) if target is not None else len(rest)
                    doc["order"] = rest[:index] + selected + rest[index:]
                elif action in {"add_tag", "remove_tag"}:
                    tag = _label(payload.get("tag"))
                    for key in selected:
                        tags = doc["items"].setdefault(key, {}).setdefault("tags", [])
                        if action == "add_tag" and tag not in tags:
                            if len(tags) >= 50:
                                raise SteamError("每个游戏最多 50 个标签")
                            tags.append(tag)
                        elif action == "remove_tag" and tag in tags:
                            tags.remove(tag)
                elif action == "playtime":
                    if len(selected) != 1:
                        raise SteamError("请只选择一个游戏修改时长")
                    hours = payload.get("hours")
                    if hours is not None and (type(hours) not in (float, int) or not math.isfinite(hours) or not 0 <= hours <= 1000000):
                        raise SteamError("请输入 0 到 1000000 之间的小时数")
                    doc["items"].setdefault(selected[0], {})["minutes"] = None if hours is None else round(hours * 60)
                else:
                    raise SteamError("未知操作")
            # A nonce prevents stale requests from becoming valid after undo.
            doc["change"] = uuid.uuid4().hex
            encoded = _encode(doc)
            self._decode(encoded, path)
            after = _digest(encoded)
            undo_path = path.with_suffix(".undo.json")
            previous_receipt = _read(undo_path)
            self.library._atomic_write(undo_path, _encode({"before": before, "after": after}))
            try:
                self.library._atomic_write(path, encoded)
            except OSError:
                if previous_receipt is not None:
                    self.library._atomic_write(undo_path, previous_receipt)
                else:
                    undo_path.unlink(missing_ok=True)
                raise
            self.publish_plan = None
            return self._view(doc, after, account, path)

    def _groups(self, doc):
        groups = []
        for folder in doc["folders"]:
            apps = sorted({g["appid"] for key, g in self.games.items() if doc["items"].get(key, {}).get("folder") == folder["id"]})
            groups.append({"id": "folder-" + folder["id"], "name": folder["name"], "appids": apps})
        tags = {}
        for key, game in self.games.items():
            for tag in doc["items"].get(key, {}).get("tags", []):
                tags.setdefault(tag, set()).add(game["appid"])
        for tag, appids in sorted(tags.items()):
            groups.append({"id": "tag-" + hashlib.sha256(tag.encode()).hexdigest()[:24], "name": "标签 · " + tag, "appids": sorted(appids)})
        return groups

    def preview(self, payload):
        account, path, doc, revision = self._checked(payload)
        source = self._source()
        self._load_games()
        groups = self._groups(doc)
        cloud = _read(self.library.cloud_path())
        if cloud is None:
            raise SteamError("找不到 Steam 分类文件，请先打开一次 Steam 游戏库")
        records = self._records(cloud)
        if source != self._source():
            raise SteamError("Steam 数据正在变化，请稍后重试")
        self.publish_plan = {"id": uuid.uuid4().hex, "account": account, "revision": revision,
                             "hash": _digest(cloud), "source": source, "groups": groups,
                             "created": time.monotonic()}
        return {"plan_id": self.publish_plan["id"], "groups": groups,
                "replaced": sum(self._owned(record) for record in records)}

    def _source(self):
        return (self.organizer._source_fingerprint(), _digest(_read(self.library.config_dir / "shortcuts.vdf")))

    @staticmethod
    def _owned(record):
        return isinstance(record, list) and len(record) == 2 and isinstance(record[0], str) and record[0].startswith(PREFIX)

    @staticmethod
    def _records(raw):
        try:
            records = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(records, list):
                raise ValueError()
            return records
        except (ValueError, UnicodeError) as exc:
            raise SteamError("Steam 分类文件格式错误，未修改") from exc

    def publish(self, payload):
        with self.library.write_lock():
            account, _, _, revision = self._checked(payload)
            plan = self.publish_plan
            if not plan or payload.get("plan_id") != plan["id"] or account != plan["account"] or revision != plan["revision"] or time.monotonic() - plan["created"] > 1800:
                raise SteamError("同步预览已失效，请重新预览")
            self.organizer._ensure_steam_stopped()
            path = self.library.cloud_path()
            raw = _read(path)
            if _digest(raw) != plan["hash"] or self._source() != plan["source"]:
                raise SteamError("Steam 数据已改变，请重新预览")
            records = [r for r in self._records(raw) if not self._owned(r)]
            for group in plan["groups"]:
                key = PREFIX + group["id"]
                value = {"id": key.split(".", 1)[1], "name": group["name"], "added": group["appids"], "removed": []}
                records.append([key, {"key": key, "value": json.dumps(value, ensure_ascii=False), "timestamp": int(time.time()), "version": "366"}])
            backup = self.library._backup_bytes(raw)
            self.organizer._ensure_steam_stopped()
            if self._location()[0] != account or _digest(_read(path)) != plan["hash"] or self._source() != plan["source"]:
                raise SteamError("Steam 数据已改变，未写入，请重新预览")
            try:
                self.library._atomic_write(path, _encode(records))
            except OSError:
                # A failed replace must not create a no-op "latest backup".
                if _digest(_read(path)) == plan["hash"]:
                    backup.unlink(missing_ok=True)
                raise
            self.publish_plan = None
            self.organizer._clear_plans()
            return {"collections": len(plan["groups"]), "backup": str(backup)}
