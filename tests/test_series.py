from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from steam_appinfo import _summarise
from steam_library_core import SteamLibrary
from steam_series import series_for
from steam_web import Organizer
from tests.test_steam_organizer import make_steam_root


def game(name, **extra):
    return {"name": name, "named": True, "form": "game", **extra}


class SeriesTests(unittest.TestCase):
    def test_localized_aliases_trademarks_and_numbered_releases(self):
        for name, expected in [
            ("Persona 3 Reload", "女神异闻录"), ("女神异闻录５ 皇家版", "女神异闻录"),
            ("PERSONA5 ROYAL", "女神异闻录"), ("Resident Evil 4", "生化危机"),
            ("生化危機 2", "生化危机"), ("DARK SOULS™ III", "黑暗之魂"),
            ("FINAL FANTASY® VII REMAKE", "最终幻想"), ("Like a Dragon: Infinite Wealth", "如龙"),
            ("Portal 2", "传送门"), ("Hades II", "哈迪斯"), ("真·女神转生 V", "真·女神转生"),
            ("Armored Core VI Fires of Rubicon", "装甲核心"),
        ]:
            with self.subTest(name=name):
                self.assertEqual(series_for(game(name)), [expected])

    def test_unknowns_and_similar_names_are_not_guessed(self):
        for name in ["Portal Knights", "Hades' Star", "文明模拟器", "战神之怒", "Personality Test",
                     "Ysland", "My Portal 2", "Island 1", "Island 2"]:
            with self.subTest(name=name):
                self.assertEqual(series_for(game(name)), ["未识别系列"])

    def test_metadata_retains_unknown_series_but_not_a_publisher_catalog(self):
        self.assertEqual(series_for(game("Unlisted Game", franchises=["My Saga", "Other Saga", "My Saga"])), ["My Saga", "Other Saga"])
        self.assertEqual(series_for(game("Unlisted Game", franchises=["Studio"], developers=["Studio"])), ["未识别系列"])
        self.assertEqual(series_for(game("Unlisted Game", franchises=["PUBLISHER"], publisher="Publisher")), ["未识别系列"])
        self.assertEqual(series_for(game("Unlisted Game", franchises=["Persona"])), ["女神异闻录"])
        self.assertEqual(series_for(game("Portal Knights", franchises=["Portal Knights"])), ["Portal Knights"])
        self.assertEqual(series_for(game("Unlisted Game", franchises=["EA Play", "WB Games", "My Saga", "my saga"])), ["My Saga"])

    def test_english_name_fallback_and_specific_title_override_broad_brand(self):
        self.assertEqual(series_for(game("全新中文译名", name_en="The Witcher 3: Wild Hunt")), ["巫师"])
        self.assertEqual(series_for(game("Persona 5 Royal", franchises=["ATLUS"])), ["女神异闻录"])

    def test_non_games_and_missing_metadata_stay_separate(self):
        self.assertEqual(series_for(game("Persona 5 OST", form="music")), ["非游戏内容"])
        self.assertEqual(series_for(game("Resident Evil Demo", form="demo")), ["非游戏内容"])
        self.assertEqual(series_for(game("App 10", form="", named=False)), ["资料缺失"])

    def test_parser_catalog_preview_and_reviewed_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            organizer = Organizer(make_steam_root(Path(temporary) / "Steam"))
            lib = organizer.library
            metadata = {}
            for appid, title, localized, series in [
                (101, "Persona 3 Reload", "女神异闻录３ Reload", "Persona"),
                (102, "Persona 5 Royal", "女神异闻录５ 皇家版", "Persona"),
                (103, "Unlisted Adventure", "中文冒险", "Unlisted Saga"),
            ]:
                metadata[appid] = _summarise(appid, {"common": {
                    "name": title, "name_localized": {"schinese": localized}, "type": "Game",
                    "associations": {"0": {"type": "franchise", "name": series},
                                     "1": {"type": "developer", "name": "Studio"}},
                }}, "schinese")
            self.assertEqual(metadata[103]["franchises"], ["Unlisted Saga"])
            cloud = lib.cloud_path()
            cloud.parent.mkdir(parents=True)
            cloud.write_bytes(b'[]')
            with mock.patch.object(lib, "appinfo", return_value=metadata), \
                 mock.patch.object(lib, "cached_appids", return_value=set(metadata)), \
                 mock.patch.object(organizer, "_ensure_steam_stopped"):
                catalog = lib.catalog()
                self.assertEqual(catalog[103]["name_en"], "Unlisted Adventure")
                self.assertEqual(catalog[103]["franchises"], ["Unlisted Saga"])
                preview = organizer.make_plan(["series"], 3)
                by_bucket = {g["bucket"]: g for g in preview["groups"]}
                self.assertEqual(by_bucket["女神异闻录"]["appids"], [101, 102])
                self.assertEqual(by_bucket["Unlisted Saga"]["appids"], [103])
                self.assertEqual(cloud.read_bytes(), b'[]', "Preview must not write Steam collections")
                organizer.apply(preview["plan_id"], [by_bucket["女神异闻录"]["id"]])
                collections = lib.current_collections()
                self.assertEqual([(c["name"], c["count"]) for c in collections], [("系列 · 女神异闻录", 2)])


if __name__ == "__main__":
    unittest.main()
