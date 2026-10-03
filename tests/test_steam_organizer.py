from __future__ import annotations

from contextlib import contextmanager
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from steam_appinfo import AppInfoError, _summarise
from steam_library_core import (
    SteamError,
    SteamLibrary,
    detect_steam_root,
    validate_steam_root,
)
from steam_web import PLAN_TTL_SECONDS, Organizer, steam_running


def collection_record(key: str, name: str, appids: list[int]) -> list:
    value = json.dumps(
        {"id": key.rsplit("-", 1)[-1], "name": name, "added": appids, "removed": []},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return [key, {"key": key, "value": value, "timestamp": 1, "version": "366"}]


def make_steam_root(base: Path, steamid: str = "76561198000000001") -> Path:
    root = base
    (root / "config").mkdir(parents=True)
    (root / "appcache").mkdir()
    (root / "steamapps").mkdir()
    (root / "userdata").mkdir()
    (root / "steam.exe").write_bytes(b"")
    (root / "appcache" / "appinfo.vdf").write_bytes(b"appinfo")
    (root / "config" / "loginusers.vdf").write_text(
        '"users"\n{\n'
        f'\t"{steamid}"\n\t{{\n\t\t"MostRecent"\t\t"1"\n\t}}\n'
        '}\n',
        encoding="utf-8",
    )
    return root


class SteamRootTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)

    def test_validation_requires_complete_steam_layout(self):
        root = make_steam_root(self.base / "valid")
        self.assertEqual(validate_steam_root(root), root.resolve())

        (root / "appcache" / "appinfo.vdf").unlink()
        with self.assertRaisesRegex(SteamError, r"appcache[\\/]appinfo\.vdf"):
            validate_steam_root(root)

    def test_detection_prefers_valid_registry_candidate(self):
        invalid = self.base / "invalid-registry"
        invalid.mkdir()
        registry = make_steam_root(self.base / "registry")
        common = make_steam_root(self.base / "common")
        with mock.patch(
            "steam_library_core._registry_steam_roots",
            return_value=[invalid, registry],
        ), mock.patch(
            "steam_library_core._common_steam_roots",
            return_value=[common],
        ):
            self.assertEqual(detect_steam_root(), registry.resolve())

    def test_detection_uses_common_and_legacy_fallback_candidates(self):
        invalid = self.base / "invalid-common"
        invalid.mkdir()
        fallback = make_steam_root(self.base / "legacy-fallback")
        with mock.patch(
            "steam_library_core._registry_steam_roots",
            return_value=[],
        ), mock.patch(
            "steam_library_core._common_steam_roots",
            return_value=[invalid, fallback],
        ):
            self.assertEqual(detect_steam_root(), fallback.resolve())

    def test_detection_rejects_all_incomplete_candidates(self):
        incomplete = self.base / "incomplete"
        incomplete.mkdir()
        with mock.patch(
            "steam_library_core._registry_steam_roots",
            return_value=[incomplete],
        ), mock.patch(
            "steam_library_core._common_steam_roots",
            return_value=[],
        ):
            with self.assertRaisesRegex(SteamError, "未找到可用"):
                detect_steam_root()

    def test_organizer_uses_auto_detected_root(self):
        detected = make_steam_root(self.base / "detected")
        with mock.patch("steam_web.detect_steam_root", return_value=detected.resolve()):
            organizer = Organizer()
        self.assertEqual(organizer.library.root, detected.resolve())

    def test_organizer_switches_root_and_discards_old_account_state(self):
        first = make_steam_root(self.base / "first", "76561198000000001")
        second = make_steam_root(self.base / "second", "76561198000000002")
        organizer = Organizer(first)
        organizer.plan = [{"id": "old"}]
        organizer.selected = {"old"}
        organizer.plans["old"] = {"plan_id": "old"}
        organizer.session_games = {1: {"appid": 1, "name": "Old account"}}

        selected = organizer.set_steam_root(second)

        self.assertEqual(Path(selected), second.resolve())
        self.assertEqual(organizer.library.root, second.resolve())
        self.assertEqual(organizer.library.steamid64, "76561198000000002")
        self.assertFalse(organizer.plan)
        self.assertFalse(organizer.selected)
        self.assertFalse(organizer.plans)
        self.assertFalse(organizer.session_games)

    def test_failed_switch_keeps_current_library_and_plans(self):
        first = make_steam_root(self.base / "first")
        organizer = Organizer(first)
        organizer.plan = [{"id": "keep"}]
        organizer.plans["keep"] = {"plan_id": "keep"}

        with self.assertRaises(SteamError):
            organizer.set_steam_root(self.base / "missing")

        self.assertEqual(organizer.library.root, first.resolve())
        self.assertEqual(organizer.plan, [{"id": "keep"}])
        self.assertIn("keep", organizer.plans)


class ScopeTests(unittest.TestCase):
    def make_library(self) -> SteamLibrary:
        library = SteamLibrary("unused")
        library.local_appids = lambda: {5, 6, 8, 480}
        library.cached_appids = lambda: {1, 2, 3, 7, 480}
        library.installed_appids = lambda: {4}
        library._appinfo = {
            1: {"name": "Game", "type": "Game"},
            2: {"name": "Application", "type": "Application"},
            3: {"name": "Music", "type": "Music"},
            4: {"name": "Series", "type": "Series"},
            5: {"name": "Tool", "type": "Tool"},
            7: {"name": "Beta", "type": "Beta"},
            8: {"name": "Local History", "type": "Game"},
            480: {"name": "Spacewar", "type": "Game"},
        }
        return library

    def test_scopes_separate_library_games_auxiliary_and_unresolved(self):
        scopes = self.make_library().scoped_appids()
        self.assertEqual(scopes["library"], {1, 2, 3, 4})
        self.assertEqual(scopes["games"], {1})
        self.assertEqual(scopes["all"], {1, 2, 3, 4, 5, 6, 7, 8, 480})
        self.assertEqual(scopes["unresolved"], {6})
        self.assertEqual(scopes["auxiliary"], {5, 7})
        self.assertEqual(scopes["local_only"], {8})
        self.assertEqual(scopes["excluded"], {480})

    def test_default_catalog_uses_library_scope(self):
        library = self.make_library()
        library.playtime = lambda: {}
        library.last_played = lambda: {}
        catalog = library.catalog()
        self.assertEqual(set(catalog), {1, 2, 3, 4})

    def test_session_owned_name_resolves_missing_appinfo_as_game(self):
        library = SteamLibrary("unused")
        library.local_appids = lambda: set()
        library.cached_appids = lambda: set()
        library.installed_appids = lambda: set()
        library.playtime = lambda: {}
        library.last_played = lambda: {}
        library._appinfo = {}
        remote = {99: {"appid": 99, "name": "API Owned Game"}}
        scopes = library.scoped_appids({99}, remote)
        self.assertEqual(scopes["library"], {99})
        self.assertEqual(scopes["games"], {99})
        self.assertNotIn(99, scopes["unresolved"])
        catalog = library.catalog({99}, "library", external_games=remote)
        self.assertEqual(catalog[99]["name"], "API Owned Game")
        self.assertEqual(catalog[99]["form"], "game")


class GroupingTests(unittest.TestCase):
    def test_genres_are_multi_label_and_correctly_mapped(self):
        item = {
            "appid": 10,
            "name": "Racing Sports Free Game",
            "named": True,
            "form": "game",
            "genres": ["9", "18", "37", "9"],
            "developer": "Studio",
            "publisher": "Publisher",
            "installed": False,
            "playtime": 0,
            "last_played": 0,
        }
        library = SteamLibrary("unused")
        groups = library.build_groups(["genre"], catalog={10: item})
        by_bucket = {group["bucket"]: group for group in groups}
        self.assertEqual(set(by_bucket), {"竞速", "体育", "免费开玩"})
        self.assertTrue(all(group["appids"] == [10] for group in groups))

    def test_non_game_content_does_not_enter_game_genres(self):
        item = {
            "appid": 11,
            "name": "Soundtrack",
            "named": True,
            "form": "music",
            "genres": ["1", "2"],
            "developer": "Studio",
            "publisher": "Publisher",
            "installed": False,
            "playtime": 0,
            "last_played": 0,
        }
        groups = SteamLibrary("unused").build_groups(
            ["genre"], catalog={11: item}
        )
        self.assertEqual([(group["bucket"], group["appids"]) for group in groups], [("非游戏内容", [11])])

    def test_missing_metadata_is_not_labeled_as_non_game_content(self):
        item = {
            "appid": 12,
            "name": "App 12",
            "named": False,
            "form": "",
            "genres": [],
            "developer": "",
            "publisher": "",
            "installed": False,
            "playtime": 0,
            "last_played": 0,
        }
        groups = SteamLibrary("unused").build_groups(
            ["genre"], catalog={12: item}
        )
        self.assertEqual(
            [(group["bucket"], group["appids"]) for group in groups],
            [("资料缺失", [12])],
        )

    def test_appinfo_summary_keeps_localized_name_primary_genre_and_companies(self):
        summary = _summarise(
            10,
            {
                "common": {
                    "name": "English",
                    "name_localized": {"schinese": "中文名"},
                    "type": "Game",
                    "primary_genre": 9,
                    "genres": {"0": 23, "1": 9, "2": 18},
                    "steam_release_date": 123,
                    "associations": {
                        "0": {"type": "developer", "name": "Dev A"},
                        "1": {"type": "developer", "name": "Dev B"},
                        "2": {"type": "publisher", "name": "Pub A"},
                    },
                },
                "extended": {"developer": "Dev A", "publisher": "Pub A"},
            },
            "schinese",
        )
        self.assertEqual(summary["name"], "中文名")
        self.assertEqual(summary["genres"], ["9", "23", "18"])
        self.assertEqual(summary["developers"], ["Dev A", "Dev B"])
        self.assertEqual(summary["publishers"], ["Pub A"])
        self.assertEqual(summary["release_date"], 123)


class CloudWriteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.library = SteamLibrary(Path(self.temporary.name))
        self.library.account_id = "42"
        self.cloud = self.library.cloud_path()
        self.cloud.parent.mkdir(parents=True)

    def test_apply_preserves_manual_and_replaces_only_managed(self):
        manual = collection_record("user-collections.manual-1", "手工收藏", [1])
        old_managed = collection_record("user-collections.auto-old", "旧自动", [2])
        unrelated = ["some-other-record", {"value": "untouched"}]
        self.cloud.write_text(
            json.dumps([manual, old_managed, unrelated], ensure_ascii=False),
            encoding="utf-8",
        )

        result = self.library.apply_groups(
            [{"id": "genre:竞速", "name": "种类 · 竞速", "appids": [10, 10, 20]}]
        )

        records = json.loads(self.cloud.read_text(encoding="utf-8"))
        self.assertIn(manual, records)
        self.assertIn(unrelated, records)
        self.assertFalse(any(record[0] == "user-collections.auto-old" for record in records))
        generated = [record for record in records if record[0].startswith("user-collections.org-")]
        self.assertEqual(len(generated), 1)
        generated_value = json.loads(generated[0][1]["value"])
        self.assertEqual(generated_value["added"], [10, 20])
        self.assertEqual(generated[0][0], "user-collections." + generated_value["id"])
        self.assertTrue(generated_value["id"].startswith("org-"))
        self.assertEqual(result["apps"], 2)
        self.assertTrue(Path(result["backup"]).is_file())
        self.assertFalse(list(self.cloud.parent.glob("*.tmp")))

    def test_restore_backs_up_current_file_before_atomic_replace(self):
        current = json.dumps([["current", {"value": "now"}]]).encode()
        restored = json.dumps([["restored", {"value": "then"}]]).encode()
        self.cloud.write_bytes(current)
        source_backup = self.cloud.with_name(
            self.cloud.name + ".20260101-010101.bak"
        )
        source_backup.write_bytes(restored)

        selected = self.library.restore_latest()

        self.assertEqual(Path(selected["restored"]), source_backup)
        self.assertEqual(self.cloud.read_bytes(), restored)
        safety = list(self.cloud.parent.glob(self.cloud.name + ".pre-restore.*.bak"))
        self.assertEqual(len(safety), 1)
        self.assertEqual(safety[0].read_bytes(), current)
        self.assertEqual(Path(selected["safety_backup"]), safety[0])

    def test_second_restore_uses_pre_restore_snapshot_as_undo(self):
        current = json.dumps([["current", {"value": "now"}]]).encode()
        restored = json.dumps([["restored", {"value": "then"}]]).encode()
        self.cloud.write_bytes(current)
        source_backup = self.cloud.with_name(
            self.cloud.name + ".20260101-010101.bak"
        )
        source_backup.write_bytes(restored)

        first = self.library.restore_latest()
        self.assertEqual(self.cloud.read_bytes(), restored)
        second = self.library.restore_latest()

        self.assertEqual(Path(first["restored"]), source_backup)
        self.assertIn(".pre-restore.", Path(second["restored"]).name)
        self.assertEqual(self.cloud.read_bytes(), current)
        self.assertIsNotNone(second["safety_backup"])
        self.assertFalse(Path(second["restored"]).exists())
        remaining_undo = list(
            self.cloud.parent.glob(self.cloud.name + ".pre-restore.*.bak")
        )
        self.assertEqual(remaining_undo, [Path(second["safety_backup"])])
        self.assertEqual(remaining_undo[0].read_bytes(), restored)

    def test_pruning_only_deletes_tool_named_backups(self):
        tool_normal = self.cloud.with_name(
            self.cloud.name + ".20260101-010101.bak"
        )
        tool_pre_restore = self.cloud.with_name(
            self.cloud.name + ".pre-restore.20260101-010102-123456.bak"
        )
        foreign_same_prefix = self.cloud.with_name(self.cloud.name + ".manual.bak")
        foreign_extra_suffix = self.cloud.with_name(
            self.cloud.name + ".20260101-010103.copy.bak"
        )
        for path in (
            tool_normal,
            tool_pre_restore,
            foreign_same_prefix,
            foreign_extra_suffix,
        ):
            path.write_bytes(b"[]")

        self.library._prune_backups(0)

        self.assertFalse(tool_normal.exists())
        self.assertTrue(tool_pre_restore.exists())
        self.assertTrue(foreign_same_prefix.exists())
        self.assertTrue(foreign_extra_suffix.exists())
        self.assertEqual(self.library._restore_candidates(), [tool_pre_restore])

    def test_normal_and_pre_restore_retention_are_independent(self):
        normals = [
            self.cloud.with_name(self.cloud.name + f".2026010{i}-010101.bak")
            for i in range(1, 5)
        ]
        undo = [
            self.cloud.with_name(
                self.cloud.name + f".pre-restore.2026010{i}-010101-123456.bak"
            )
            for i in range(1, 4)
        ]
        for order, path in enumerate([*normals, *undo], start=1):
            path.write_bytes(b"[]")
            os.utime(path, ns=(order, order))

        self.library._prune_backups(2)

        self.assertEqual(self.library._normal_backups(), normals[-2:])
        remaining_undo = [
            path
            for path in self.library._tool_backups()
            if self.library._backup_kind(path) == "pre-restore"
        ]
        self.assertEqual(remaining_undo, undo[-1:])

    def test_restore_skips_invalid_and_noop_candidates(self):
        current = [["current", {"value": "now"}]]
        different = [["older", {"value": "then"}]]
        self.cloud.write_text(json.dumps(current), encoding="utf-8")
        useful = self.cloud.with_name(self.cloud.name + ".20260101-010101.bak")
        noop = self.cloud.with_name(self.cloud.name + ".20260102-010101.bak")
        invalid = self.cloud.with_name(self.cloud.name + ".20260103-010101.bak")
        useful.write_text(json.dumps(different), encoding="utf-8")
        noop.write_text(json.dumps(current, indent=2), encoding="utf-8")
        invalid.write_text("not json", encoding="utf-8")
        for order, path in enumerate((useful, noop, invalid), start=1):
            os.utime(path, ns=(order, order))

        result = self.library.restore_latest()

        self.assertEqual(Path(result["restored"]), useful)
        self.assertEqual(json.loads(self.cloud.read_text(encoding="utf-8")), different)

    def test_failed_apply_removes_just_created_noop_backup(self):
        self.cloud.write_text("[]", encoding="utf-8")
        group = [{"id": "state:installed", "name": "状态 · 已安装", "appids": [1]}]
        with mock.patch.object(
            self.library,
            "_atomic_write",
            side_effect=OSError("replace failed"),
        ):
            with self.assertRaises(OSError):
                self.library.apply_groups(group)
        self.assertEqual(self.library._normal_backups(), [])

    def test_failed_restore_removes_just_created_safety_backup(self):
        current = json.dumps([["current", {"value": "now"}]]).encode()
        restored = json.dumps([["restored", {"value": "then"}]]).encode()
        self.cloud.write_bytes(current)
        source_backup = self.cloud.with_name(
            self.cloud.name + ".20260101-010101.bak"
        )
        source_backup.write_bytes(restored)
        with mock.patch.object(
            self.library,
            "_atomic_write",
            side_effect=OSError("replace failed"),
        ):
            with self.assertRaises(OSError):
                self.library.restore_latest()
        self.assertEqual(
            list(self.cloud.parent.glob(self.cloud.name + ".pre-restore.*.bak")),
            [],
        )
        self.assertTrue(source_backup.exists())

    def test_current_collections_skips_malformed_inner_values(self):
        records = [
            ["user-collections.bad-list", {"value": "[]"}],
            [
                "user-collections.bad-added",
                {
                    "value": json.dumps(
                        {"id": "bad-added", "name": "Bad Added", "added": {"1": True}}
                    )
                },
            ],
            ["user-collections.bad-json", {"value": "{"}],
        ]
        self.cloud.write_text(json.dumps(records), encoding="utf-8")

        collections = self.library.current_collections()

        self.assertEqual(len(collections), 1)
        self.assertEqual(collections[0]["id"], "bad-added")
        self.assertEqual(collections[0]["count"], 0)

    def test_backups_do_not_collide_within_one_second(self):
        self.cloud.write_text("[]", encoding="utf-8")
        group = [{"id": "state:installed", "name": "状态 · 已安装", "appids": [1]}]
        first = self.library.apply_groups(group)["backup"]
        second = self.library.apply_groups(group)["backup"]
        self.assertNotEqual(first, second)
        self.assertTrue(Path(first).exists())
        self.assertTrue(Path(second).exists())

    def test_core_write_lock_is_reentrant(self):
        self.cloud.write_text("[]", encoding="utf-8")
        group = [{"id": "state:installed", "name": "状态 · 已安装", "appids": [1]}]
        self.library.write_lock_timeout = 0.1
        with self.library.write_lock():
            result = self.library.apply_groups(group)
        self.assertEqual(result["collections"], 1)

    def test_cross_process_lock_blocks_apply_and_restore_before_backup(self):
        self.cloud.write_text("[]", encoding="utf-8")
        useful = self.cloud.with_name(
            self.cloud.name + ".20260101-010101-123456.bak"
        )
        useful.write_text(
            json.dumps([["restored", {"value": "then"}]]),
            encoding="utf-8",
        )
        before = self.cloud.read_bytes()
        backups_before = set(self.cloud.parent.glob(self.cloud.name + ".*.bak"))
        project_dir = Path(__file__).resolve().parents[1]
        child_code = (
            "import sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, sys.argv[2])\n"
            "from steam_library_core import _exclusive_write_lock\n"
            "with _exclusive_write_lock(Path(sys.argv[1]), 5):\n"
            "    print('locked', flush=True)\n"
            "    sys.stdin.readline()\n"
        )
        child = subprocess.Popen(
            [sys.executable, "-c", child_code, str(self.library.root), str(project_dir)],
            cwd=project_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            ready = child.stdout.readline().strip()
            if ready != "locked":
                stderr = child.stderr.read()
                self.fail(f"锁辅助进程启动失败：{ready!r} {stderr}")
            self.library.write_lock_timeout = 0.15
            group = [
                {"id": "state:installed", "name": "状态 · 已安装", "appids": [1]}
            ]
            with self.assertRaisesRegex(SteamError, "另一个 Steam 分类工具进程"):
                self.library.apply_groups(group)
            with self.assertRaisesRegex(SteamError, "另一个 Steam 分类工具进程"):
                self.library.restore_latest()
            self.assertEqual(self.cloud.read_bytes(), before)
            self.assertEqual(
                set(self.cloud.parent.glob(self.cloud.name + ".*.bak")),
                backups_before,
            )
        finally:
            if child.stdin:
                try:
                    child.stdin.write("release\n")
                    child.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
            try:
                child.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate()


class AppInfoMemoryCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "appcache" / "appinfo.vdf"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"a")

    def test_cache_invalidates_on_size_and_mtime_changes(self):
        library = SteamLibrary(self.root)
        with mock.patch(
            "steam_library_core.steam_appinfo.load_cached",
            side_effect=[{1: {"name": "one"}}, {2: {"name": "two"}}, {3: {"name": "three"}}],
        ) as loader:
            self.assertEqual(set(library.appinfo()), {1})
            self.assertEqual(set(library.appinfo()), {1})
            self.assertEqual(loader.call_count, 1)

            self.source.write_bytes(b"bb")
            self.assertEqual(set(library.appinfo()), {2})
            self.assertEqual(loader.call_count, 2)

            source_stat = self.source.stat()
            os.utime(
                self.source,
                ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns + 1_000_000_000),
            )
            self.assertEqual(set(library.appinfo()), {3})
            self.assertEqual(loader.call_count, 3)

    def test_failed_refresh_keeps_last_known_good_and_does_not_spin(self):
        library = SteamLibrary(self.root)
        with mock.patch(
            "steam_library_core.steam_appinfo.load_cached",
            return_value={1: {"name": "good"}},
        ) as loader:
            good = library.appinfo()
            self.assertEqual(set(good), {1})

            self.source.write_bytes(b"changed")
            loader.side_effect = AppInfoError("broken")
            self.assertIs(library.appinfo(), good)
            self.assertIn("broken", library.appinfo_error)
            calls_after_failure = loader.call_count
            self.assertIs(library.appinfo(), good)
            self.assertEqual(loader.call_count, calls_after_failure)

            loader.side_effect = None
            loader.return_value = {2: {"name": "recovered"}}
            self.assertEqual(set(library.refresh_appinfo()), {2})
            self.assertIsNone(library.appinfo_error)


class FakeWebLibrary:
    def __init__(self):
        self.root = Path("fake")
        self.language = "schinese"
        self.account_id = "123"
        self.applied = None
        self.restored = False
        self.catalog_calls = 0
        self.catalog_arguments = None
        self.appinfo_error = None
        self.write_lock_depth = 0
        self.apply_lock_depth = 0
        self.restore_lock_depth = 0

    @contextmanager
    def write_lock(self):
        self.write_lock_depth += 1
        try:
            yield
        finally:
            self.write_lock_depth -= 1

    def appinfo(self, refresh=False):
        return {1: {}, 2: {}}

    def catalog(self, extra_appids, scope, external_games=None):
        self.catalog_calls += 1
        self.catalog_arguments = (set(extra_appids), scope, dict(external_games or {}))
        return {
            1: {
                "appid": 1,
                "name": "One",
                "named": True,
                "form": "game",
                "genres": ["1"],
                "developer": "Studio",
                "publisher": "Publisher",
                "installed": True,
                "playtime": 60,
                "last_played": 1,
            },
            2: {
                "appid": 2,
                "name": "Two",
                "named": True,
                "form": "game",
                "genres": ["9"],
                "developer": "Studio",
                "publisher": "Publisher",
                "installed": False,
                "playtime": 0,
                "last_played": 0,
            },
        }

    def build_groups(self, modes, **kwargs):
        self.received_catalog = kwargs["catalog"]
        return [
            {
                "id": "genre:动作",
                "mode": "genre",
                "bucket": "动作",
                "name": "种类 · 动作",
                "appids": [1, 2],
                "count": 2,
            }
        ]

    def current_collections(self):
        return [{"ours": True}, {"ours": False}]

    def resolve_account(self):
        return self.account_id

    def scoped_appids(self, extra_appids, external_games=None):
        return {
            "library": {1, 2},
            "games": {1, 2},
            "all": {1, 2},
            "unresolved": set(),
            "auxiliary": set(),
            "local_only": set(),
            "excluded": set(),
        }

    def apply_groups(self, groups):
        self.apply_lock_depth = self.write_lock_depth
        self.applied = groups
        return {"backup": "backup", "collections": len(groups), "apps": 2}

    def restore_latest(self):
        self.restore_lock_depth = self.write_lock_depth
        self.restored = True
        return {"restored": "backup", "safety_backup": "pre-restore-backup"}


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.organizer = Organizer()
        self.fake = FakeWebLibrary()
        self.organizer.library = self.fake

    def test_plan_is_bounded_immutable_and_catalog_is_built_once(self):
        response = self.organizer.make_plan(["genre"], 3, "library")
        self.assertEqual(self.fake.catalog_calls, 1)
        self.assertIn("plan_id", response)
        self.assertEqual(response["summary"]["groups"], 1)
        self.assertEqual(response["summary"]["unique_apps"], 2)
        self.assertEqual(response["summary"]["memberships"], 2)
        self.assertEqual(response["summary"]["existing_managed"], 1)
        self.assertEqual(response["summary"]["manual_preserved"], 1)

        response["groups"][0]["appids"].append(999)
        with mock.patch("steam_web.steam_running", return_value=False):
            self.organizer.apply(response["plan_id"], ["genre:动作"])
        self.assertEqual(self.fake.applied[0]["appids"], [1, 2])

        for _ in range(10):
            self.organizer.make_plan(["genre"], 3, "library")
        self.assertLessEqual(len(self.organizer.plans), 8)

    def test_apply_requires_matching_plan_id(self):
        with mock.patch("steam_web.steam_running", return_value=False):
            with self.assertRaises(SteamError):
                self.organizer.apply("missing", ["genre:动作"])

    def test_apply_and_restore_are_blocked_while_steam_runs(self):
        response = self.organizer.make_plan(["genre"], 3, "library")
        with mock.patch("steam_web.steam_running", return_value=True):
            with self.assertRaises(SteamError):
                self.organizer.apply(response["plan_id"], ["genre:动作"])
            with self.assertRaises(SteamError):
                self.organizer.restore()
        self.assertIsNone(self.fake.applied)
        self.assertFalse(self.fake.restored)

    def test_write_lock_covers_steam_check_and_core_mutation(self):
        response = self.organizer.make_plan(["genre"], 3, "library")
        expected_fingerprint = self.organizer.plans[response["plan_id"]][
            "source_fingerprint"
        ]
        check_depths = []
        fingerprint_depths = []

        def steam_is_stopped():
            check_depths.append(self.fake.write_lock_depth)
            return False

        def current_fingerprint():
            fingerprint_depths.append(self.fake.write_lock_depth)
            return expected_fingerprint

        with mock.patch("steam_web.steam_running", side_effect=steam_is_stopped), mock.patch.object(
            self.organizer,
            "_source_fingerprint",
            side_effect=current_fingerprint,
        ):
            self.organizer.apply(response["plan_id"], ["genre:动作"])
            self.organizer.restore()

        self.assertEqual(check_depths, [1, 1])
        self.assertEqual(fingerprint_depths, [1])
        self.assertEqual(self.fake.apply_lock_depth, 1)
        self.assertEqual(self.fake.restore_lock_depth, 1)
        self.assertEqual(self.fake.write_lock_depth, 0)

    def test_restore_reports_the_pre_restore_safety_backup(self):
        self.organizer.make_plan(["genre"], 3, "library")
        with mock.patch("steam_web.steam_running", return_value=False):
            result = self.organizer.restore()
        self.assertEqual(result["restored"], "backup")
        self.assertEqual(result["safety_backup"], "pre-restore-backup")
        self.assertTrue(self.fake.restored)
        self.assertFalse(self.organizer.plans)

    def test_successful_apply_consumes_all_plans(self):
        response = self.organizer.make_plan(["genre"], 3, "library")
        with mock.patch("steam_web.steam_running", return_value=False):
            self.organizer.apply(response["plan_id"], ["genre:动作"])
        self.assertFalse(self.organizer.plans)

    def test_expired_plan_is_rejected(self):
        response = self.organizer.make_plan(["genre"], 3, "library")
        self.organizer.plans[response["plan_id"]]["created"] = (
            time.time() - PLAN_TTL_SECONDS - 1
        )
        with mock.patch("steam_web.steam_running", return_value=False):
            with self.assertRaisesRegex(SteamError, "超过 30 分钟"):
                self.organizer.apply(response["plan_id"], ["genre:动作"])

    def test_plan_is_rejected_when_steam_sources_change(self):
        with mock.patch.object(
            self.organizer,
            "_source_fingerprint",
            side_effect=["before", "before", "after"],
        ):
            response = self.organizer.make_plan(["genre"], 3, "library")
            with mock.patch("steam_web.steam_running", return_value=False):
                with self.assertRaisesRegex(SteamError, "库数据已变化"):
                    self.organizer.apply(response["plan_id"], ["genre:动作"])
        self.assertFalse(self.organizer.plans)

    def test_plan_is_rejected_if_sources_change_during_scan(self):
        with mock.patch.object(
            self.organizer,
            "_source_fingerprint",
            side_effect=["before", "after"],
        ):
            with self.assertRaisesRegex(SteamError, "扫描期间"):
                self.organizer.make_plan(["genre"], 3, "library")

    def test_plan_is_rejected_when_metadata_refresh_failed(self):
        self.fake.appinfo_error = "broken metadata"
        with self.assertRaisesRegex(SteamError, "元数据刷新失败"):
            self.organizer.make_plan(["genre"], 3, "library")
        self.assertEqual(self.fake.catalog_calls, 0)

    def test_owned_games_remain_in_session_and_reach_catalog(self):
        count = self.organizer.set_owned_games(
            [{"appid": 99, "name": "Owned", "playtime_forever": 12}]
        )
        self.assertEqual(count, 1)
        self.organizer.make_plan(["genre"], 3, "library")
        extra, scope, external = self.fake.catalog_arguments
        self.assertEqual(extra, {99})
        self.assertEqual(scope, "library")
        self.assertEqual(external[99]["name"], "Owned")


class ProcessCheckTests(unittest.TestCase):
    def test_windows_tasklist_is_started_without_a_console_window(self):
        completed = mock.Mock(returncode=0, stdout="INFO: No tasks", stderr="")
        with mock.patch("steam_web.os.name", "nt"), mock.patch(
            "steam_web.subprocess.run", return_value=completed
        ) as runner:
            self.assertFalse(steam_running())

        self.assertEqual(
            runner.call_args.kwargs["creationflags"],
            getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )


if __name__ == "__main__":
    unittest.main()
