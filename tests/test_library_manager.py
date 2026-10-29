from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from steam_library_core import SteamError, SteamLibrary
from steam_library_manager import LibraryManager, PREFIX
from steam_web import Organizer
from steam_modern import DesktopApi
from tests.test_steam_organizer import make_steam_root


class LibraryManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.organizer = Organizer(make_steam_root(self.base / 'Steam'))
        self.lib = self.organizer.library
        self.manager = LibraryManager(self.organizer, self.base / 'workspace')
        self.organizer.game_manager = self.manager
        self.catalog = {
            1: {'name': 'Alpha', 'playtime': 120, 'playtime_known': True, 'installed': True},
            2: {'name': 'Beta'}, 3: {'name': 'Gamma'}, 4: {'name': 'Delta'},
        }
        self.lib.catalog = mock.Mock(side_effect=lambda *a, **k: copy.deepcopy(self.catalog))
        self.organizer._ensure_steam_stopped = mock.Mock()
        self.organizer._source_fingerprint = mock.Mock(return_value='stable')
        self.cloud = self.lib.cloud_path()
        self.cloud.parent.mkdir(parents=True)
        self.records = [['other-record', {'x': 1}], ['user-collections.org-auto', {'value': 'keep auto'}], ['user-collections.user-fav', {'value': 'keep manual'}]]
        self.cloud.write_bytes(json.dumps(self.records).encode())
        self.original = self.cloud.read_bytes()
        self.data = self.manager.load()

    def payload(self, **kwargs):
        return {'account': self.data['account'], 'revision': self.data['revision'], **kwargs}

    def edit(self, action, **kwargs):
        self.data = self.manager.edit(self.payload(action=action, **kwargs))
        return self.data

    def folder(self, name='常玩'):
        self.edit('create_folder', name=name)
        return self.data['folders'][-1]['id']

    def game(self, id='steam:1'):
        return next(x for x in self.data['games'] if x['id'] == id)

    def order(self):
        return [g['id'] for g in self.data['games']]

    def test_move_appends_in_original_order_and_persists_across_restart(self):
        folder = self.folder()
        self.edit('move', ids=['steam:3'], folder=folder)
        self.edit('move', ids=['steam:2', 'steam:1'], folder=folder)
        self.assertEqual(self.order(), ['steam:4', 'steam:3', 'steam:1', 'steam:2'])
        manager = LibraryManager(self.organizer, self.base / 'workspace')
        self.assertEqual(manager.load()['games'], self.data['games'])
        self.assertEqual(self.cloud.read_bytes(), self.original)
        self.organizer._ensure_steam_stopped.assert_not_called()

    def test_carousel_cover_resolves_only_loaded_account_games_without_writing(self):
        url = 'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1/cover.jpg'
        with mock.patch('steam_artwork._steam_assets', return_value=({'cover': [url]}, [])) as source:
            result = self.manager.cover(self.payload(id='steam:1'))
            self.assertIn('shared.akamai.steamstatic.com', result['url'])
            source.assert_called_once_with(1)
        self.assertEqual(self.cloud.read_bytes(), self.original)
        self.assertEqual(self.manager.cover(self.payload(id='steam:999')), {'url': None})
        with self.assertRaises(SteamError):
            self.manager.cover({**self.payload(id='steam:1'), 'account': 'other'})

    def test_bulk_tags_remove_and_time_leave_steam_record_untouched(self):
        self.edit('add_tag', ids=['steam:1', 'steam:2'], tag='待通关')
        self.edit('add_tag', ids=['steam:1'], tag='待通关')
        self.assertEqual(self.game()['tags'], ['待通关'])
        self.edit('remove_tag', ids=['steam:2'], tag='待通关')
        self.assertEqual(self.game('steam:2')['tags'], [])
        self.edit('playtime', ids=['steam:1'], hours=3.5)
        self.assertEqual(self.game()['minutes'], 210)
        self.assertEqual(self.game()['steam_minutes'], 120)
        self.edit('playtime', ids=['steam:1'], hours=None)
        self.assertIsNone(self.game()['minutes'])
        self.assertEqual(self.cloud.read_bytes(), self.original)

    def test_reorder_multi_selection_and_bottom(self):
        self.edit('reorder', ids=['steam:3', 'steam:2'], before='steam:1')
        self.assertEqual(self.order(), ['steam:2', 'steam:3', 'steam:1', 'steam:4'])
        self.edit('reorder', ids=['steam:2'], before=None)
        self.assertEqual(self.order(), ['steam:3', 'steam:1', 'steam:4', 'steam:2'])

    def test_rename_delete_folder_returns_games_to_unfiled_and_undo(self):
        folder = self.folder()
        self.edit('move', ids=['steam:1'], folder=folder)
        self.edit('rename_folder', folder=folder, name='休闲')
        self.edit('delete_folder', folder=folder)
        self.assertEqual(self.game()['folder'], '')
        self.edit('undo')
        self.assertEqual(self.game()['folder'], folder)
        self.assertEqual(self.data['folders'][0]['name'], '休闲')
        self.edit('undo')
        self.assertEqual(self.game()['folder'], '')

    def test_conflict_and_account_switch_block_stale_edits(self):
        payload = self.payload(action='create_folder', name='Old')
        self.folder()
        with self.assertRaisesRegex(SteamError, '其他窗口'):
            self.manager.edit(payload)
        payload = self.payload(action='create_folder', name='Other')
        self.organizer.library = SteamLibrary(make_steam_root(self.base / 'Second', '76561198000000002'))
        with self.assertRaisesRegex(SteamError, '账号或目录'):
            self.manager.edit(payload)

    def test_invalid_input_does_not_save(self):
        self.folder('Unique')
        _, path = self.manager._location()
        original = path.read_bytes()
        for args in [
            {'action': 'create_folder', 'name': 'unique'},
            {'action': 'add_tag', 'ids': ['steam:1'], 'tag': ''},
            {'action': 'move', 'ids': ['steam:999'], 'folder': ''},
            {'action': 'move', 'ids': ['steam:1'], 'folder': 'fake'},
            {'action': 'reorder', 'ids': ['steam:1'], 'before': 'steam:1'},
            {'action': 'playtime', 'ids': ['steam:1'], 'hours': float('nan')},
            {'action': 'playtime', 'ids': ['steam:1'], 'hours': True},
            {'action': 'playtime', 'ids': ['steam:1'], 'hours': -2},
            {'action': 'playtime', 'ids': ['steam:1', 'steam:2'], 'hours': 10},
        ]:
            with self.subTest(args=args), self.assertRaises(SteamError):
                self.manager.edit(self.payload(**args))
            self.assertEqual(path.read_bytes(), original)

    def test_unknown_games_retained_when_temporarily_missing(self):
        self.edit('add_tag', ids=['steam:1'], tag='保留')
        del self.catalog[1]
        self.data = self.manager.load()
        self.edit('create_folder', name='新的')
        self.catalog[1] = {'name': 'Alpha'}
        self.data = self.manager.load()
        self.assertEqual(self.game()['tags'], ['保留'])

    def test_corrupt_document_and_undo_fail_without_overwrite(self):
        self.folder()
        _, path = self.manager._location()
        path.with_suffix('.undo.json').write_text(json.dumps({'after': self.data['revision'], 'before': {'version': 1}}))
        original = path.read_bytes()
        with self.assertRaises(SteamError):
            self.edit('undo')
        self.assertEqual(path.read_bytes(), original)
        path.write_bytes(b'bad-json')
        with self.assertRaisesRegex(SteamError, '数据损坏'):
            self.manager.load()
        self.assertEqual(path.read_bytes(), b'bad-json')

    def test_failed_save_preserves_data_and_undo(self):
        self.folder()
        _, path = self.manager._location()
        original = path.read_bytes()
        receipt = path.with_suffix('.undo.json').read_bytes()
        write = self.lib._atomic_write
        def fail(destination, data):
            if destination == path:
                raise OSError('disk full')
            return write(destination, data)
        with mock.patch.object(self.lib, '_atomic_write', side_effect=fail):
            with self.assertRaises(OSError):
                self.edit('create_folder', name='Fail')
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(path.with_suffix('.undo.json').read_bytes(), receipt)

    def test_publish_owned_namespace_only_and_backup_exact_original(self):
        folder = self.folder()
        self.edit('move', ids=['steam:1'], folder=folder)
        self.edit('add_tag', ids=['steam:1', 'steam:2'], tag='待玩')
        plan = self.manager.preview(self.payload())
        result = self.manager.publish(self.payload(plan_id=plan['plan_id']))
        records = json.loads(self.cloud.read_bytes())
        self.assertEqual(records[:3], self.records)
        self.assertEqual(result['collections'], 2)
        self.assertEqual(Path(result['backup']).read_bytes(), self.original)
        exported = [json.loads(r[1]['value']) for r in records if r[0].startswith(PREFIX)]
        self.assertEqual(exported[0]['added'], [1])
        self.assertEqual(exported[1]['added'], [1, 2])
        with self.assertRaises(SteamError):
            self.manager.publish(self.payload(plan_id=plan['plan_id']))
        self.edit('delete_folder', folder=folder)
        self.edit('remove_tag', ids=['steam:1', 'steam:2'], tag='待玩')
        plan = self.manager.preview(self.payload())
        self.assertEqual(plan['replaced'], 2)
        self.manager.publish(self.payload(plan_id=plan['plan_id']))
        self.assertEqual(json.loads(self.cloud.read_bytes()), self.records)

    def test_publish_blocks_running_steam_stale_disk_expired_or_edited_plan(self):
        self.folder()
        plan = self.manager.preview(self.payload())
        self.organizer._ensure_steam_stopped.side_effect = SteamError('Steam 仍在运行')
        with self.assertRaisesRegex(SteamError, '运行'):
            self.manager.publish(self.payload(plan_id=plan['plan_id']))
        self.organizer._ensure_steam_stopped.side_effect = None
        self.manager.publish_plan['created'] -= 1801
        with self.assertRaisesRegex(SteamError, '失效'):
            self.manager.publish(self.payload(plan_id=plan['plan_id']))
        plan = self.manager.preview(self.payload())
        self.cloud.write_bytes(self.original + b' ')
        with self.assertRaisesRegex(SteamError, '已改变'):
            self.manager.publish(self.payload(plan_id=plan['plan_id']))
        self.assertEqual(self.cloud.read_bytes(), self.original + b' ')
        plan = self.manager.preview(self.payload())
        self.folder('Another')
        with self.assertRaisesRegex(SteamError, '失效'):
            self.manager.publish(self.payload(plan_id=plan['plan_id']))

    def test_nonsteam_shortcut_in_management_and_export(self):
        self.lib.config_dir.joinpath('shortcuts.vdf').write_bytes(
            b'\x00shortcuts\0\x000\0\x02appid\0\x01\x00\x00\x80\x01AppName\0Local Game\0\x08\x08\x08')
        self.data = self.manager.load()
        local = self.game('local:2147483649')
        self.assertEqual(local['source'], '非 Steam')
        folder = self.folder()
        self.edit('move', ids=[local['id']], folder=folder)
        plan = self.manager.preview(self.payload())
        self.assertEqual(plan['groups'][0]['appids'], [2147483649])

    def test_publish_failure_keeps_original_and_plan_for_retry(self):
        self.folder()
        plan = self.manager.preview(self.payload())
        with mock.patch.object(self.lib, '_atomic_write', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.manager.publish(self.payload(plan_id=plan['plan_id']))
        self.assertEqual(self.cloud.read_bytes(), self.original)
        self.assertEqual(self.lib._normal_backups(), [])
        self.manager.publish(self.payload(plan_id=plan['plan_id']))
        self.assertEqual(len(self.lib._normal_backups()), 1)

    def test_automatic_classification_preserves_manual_manager_namespace(self):
        self.folder()
        plan = self.manager.preview(self.payload())
        self.manager.publish(self.payload(plan_id=plan['plan_id']))
        manual = [r for r in json.loads(self.cloud.read_bytes()) if r[0].startswith(PREFIX)]
        self.lib.apply_groups([{'name': '类型 · 动作', 'appids': [1, 2]}])
        self.assertEqual([r for r in json.loads(self.cloud.read_bytes()) if r[0].startswith(PREFIX)], manual)

    def test_desktop_bridge_uses_whitelist_and_releases_activity(self):
        api = DesktopApi(self.organizer, self.base / 'test.log')
        self.assertEqual(api.manage_library('load', {})['games'], self.data['games'])
        with self.assertRaises(RuntimeError):
            api.manage_library('__init__', {})
        with self.assertRaises(RuntimeError):
            api.manage_library('edit', self.payload(action='unknown'))
        self.assertFalse(api._is_mutation_active())


if __name__ == '__main__':
    unittest.main()
