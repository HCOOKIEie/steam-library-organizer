from __future__ import annotations

import base64
import json
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from steam_library_core import SteamError, SteamLibrary
from steam_nonsteam import LocalGameImporter, discover_games, parse_shortcuts, _digest, _platform_entries
from tests.test_steam_organizer import make_steam_root
from steam_web import Organizer, Handler, CSRF_TOKEN
from steam_modern import DesktopApi


class NonSteamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.library = SteamLibrary(make_steam_root(self.base / 'Steam'))
        self.stopped = mock.Mock()
        self.importer = LocalGameImporter(self.library, self.stopped)
        self.path = self.library.config_dir / 'shortcuts.vdf'
        self.games = self.base / '中文 游戏目录'
        self.games.mkdir()
        self.exe = self.games / 'YuanShen.exe'
        self.exe.write_bytes(b'MZ' + b'fixture' * 30)
        platform_entries = mock.patch('steam_nonsteam._platform_entries', return_value=[])
        platform_entries.start()
        self.addCleanup(platform_entries.stop)

    def scan(self):
        return self.importer.scan({'roots': [str(self.games)], 'automatic': False})

    def apply(self, scan=None, **extra):
        scan = scan or self.scan()
        return self.importer.apply({'plan_id': scan['plan_id'], 'selected': [x['id'] for x in scan['candidates']], **extra})

    def test_absent_file_import_rename_and_exact_undo(self):
        scan = self.scan()
        self.assertFalse(self.path.exists())
        result = self.apply(scan, names={scan['candidates'][0]['id']: '原神 · 国服'})
        entries, _ = parse_shortcuts(self.path.read_bytes())
        self.assertEqual(entries[0]['appname'], '原神 · 国服')
        self.assertEqual(entries[0]['exe'], f'"{self.exe.resolve()}"')
        self.assertEqual(entries[0]['startdir'], f'"{self.games.resolve()}"')
        self.assertEqual(entries[0]['tags'], {'0': '本机游戏'})
        self.assertGreaterEqual(entries[0]['appid'], 0x80000000)
        snapshot = json.loads(Path(result['backup']).read_text())
        self.assertIsNone(snapshot['before'])
        undo = self.importer.undo()
        self.assertFalse(self.path.exists())
        self.assertTrue(Path(undo['safety_backup']).is_file())

    def test_existing_unknown_fields_and_sparse_indices_preserved_byte_for_byte(self):
        original = (b'\x00shortcuts\0\x009\0\x02appid\0\x01\x00\x00\x80'
                    b'\x01AppName\0Old\0\x01Exe\0"D:\\old.exe"\0'
                    b'\x00tags\0\x010\0My category\0\x08'
                    b'\x07future_field\0abcdefgh\x08\x08\x08')
        self.path.write_bytes(original)
        _, end = parse_shortcuts(original)
        self.apply()
        updated = self.path.read_bytes()
        self.assertEqual(updated[:end], original[:end])
        entries, _ = parse_shortcuts(updated)
        self.assertEqual([x['index'] for x in entries], [9, 10])
        self.assertEqual(entries[0]['future_field'], b'abcdefgh')
        self.importer.undo()
        self.assertEqual(self.path.read_bytes(), original)

    def test_duplicate_import_is_skipped_and_replay_rejected(self):
        scan = self.scan()
        self.apply(scan)
        original = self.path.read_bytes()
        with self.assertRaisesRegex(SteamError, '失效'):
            self.apply(scan)
        scan = self.scan()
        self.assertTrue(scan['candidates'][0]['existing'])
        with self.assertRaisesRegex(SteamError, '无需重复'):
            self.apply(scan)
        self.assertEqual(self.path.read_bytes(), original)

    def test_changed_steam_file_blocks_import_and_undo(self):
        scan = self.scan()
        self.path.write_bytes(b'\x00shortcuts\0\x08\x08')
        with self.assertRaisesRegex(SteamError, '变化'):
            self.apply(scan)
        self.apply()
        data = self.path.read_bytes().replace('原神'.encode(), '测试'.encode())
        self.path.write_bytes(data)
        with self.assertRaisesRegex(SteamError, '已被修改'):
            self.importer.undo()
        self.assertEqual(self.path.read_bytes(), data)

    def test_changed_executable_blocks_entire_batch(self):
        scan = self.scan()
        self.exe.write_bytes(b'MZchanged')
        with self.assertRaisesRegex(SteamError, '启动程序已变化'):
            self.apply(scan)
        self.assertFalse(self.path.exists())

    def test_running_steam_blocks_import_and_restore(self):
        scan = self.scan()
        self.stopped.side_effect = SteamError('Steam 正在运行')
        with self.assertRaisesRegex(SteamError, '正在运行'):
            self.apply(scan)
        with self.assertRaisesRegex(SteamError, '正在运行'):
            self.importer.undo()
        self.assertFalse(self.path.exists())

    def test_account_change_and_expired_plan_block_writes(self):
        scan = self.scan()
        with mock.patch.object(self.importer, '_path', return_value=self.path.parent / 'other.vdf'):
            with self.assertRaisesRegex(SteamError, '账号或快捷方式已变化'):
                self.apply(scan)
        self.importer.plan['created'] -= 1801
        with self.assertRaisesRegex(SteamError, '失效'):
            self.apply(scan)
        self.assertFalse(self.path.exists())

    def test_forged_selection_and_invalid_names(self):
        scan = self.scan()
        with self.assertRaisesRegex(SteamError, '不属于'):
            self.importer.apply({'plan_id': scan['plan_id'], 'selected': ['outside']})
        with self.assertRaisesRegex(SteamError, '名称不能为空'):
            self.apply(scan, names={scan['candidates'][0]['id']: 'bad\0name'})
        with self.assertRaisesRegex(SteamError, '分类名称无效'):
            self.apply(scan, category='bad\0tag')
        self.assertFalse(self.path.exists())

    def test_malformed_or_unknown_binary_vdf_is_never_overwritten(self):
        for data in (b'', b'\x00shortcuts\0\x005\0\x09new\0\x08\x08\x08', b'\x00shortcuts\0\x08\x08extra'):
            self.path.write_bytes(data)
            with self.assertRaises(SteamError):
                self.scan()
            self.assertEqual(self.path.read_bytes(), data)

    def test_backup_or_replace_failure_preserves_original(self):
        original = b'\x00shortcuts\0\x08\x08'
        self.path.write_bytes(original)
        scan = self.scan()
        with mock.patch.object(SteamLibrary, '_atomic_write', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.apply(scan)
        self.assertEqual(self.path.read_bytes(), original)
        writer = SteamLibrary._atomic_write
        def fail_target(path, data):
            if path == self.path:
                raise OSError('file locked')
            return writer(path, data)
        with mock.patch.object(SteamLibrary, '_atomic_write', side_effect=fail_target):
            with self.assertRaises(OSError):
                self.apply(scan)
        self.assertEqual(self.path.read_bytes(), original)
        with self.assertRaisesRegex(SteamError, '没有可撤销'):
            self.importer.undo()

    def test_scanner_filters_installers_steam_paths_and_non_executables(self):
        (self.games / 'unins000.exe').write_bytes(b'MZtest')
        (self.games / 'notgame.exe').write_bytes(b'text')
        (self.games / 'setup.exe').write_bytes(b'MZtest')
        nested = self.games / 'steamapps'
        nested.mkdir()
        (nested / 'Another.exe').write_bytes(b'MZtest')
        result = self.scan()
        self.assertEqual([x['name'] for x in result['candidates']], ['原神'])
        self.assertNotIn('signature', result['candidates'][0])

    def test_shortcut_arguments_and_working_directory_are_preserved(self):
        item = {'name': '原神 shortcut', 'exe': str(self.exe), 'args': '--channel "CN"', 'start_dir': str(self.base)}
        with mock.patch('steam_nonsteam._shortcut_targets', return_value=([item], [])), mock.patch('steam_nonsteam._registry_locations', return_value=[]), mock.patch('steam_nonsteam._common_game_locations', return_value=[]):
            # Avoid discovering any real machine directories in this unit test.
            result = discover_games([], True, threading.Event(), [])
        self.assertEqual(result['candidates'][0]['args'], '--channel "CN"')
        self.assertEqual(result['candidates'][0]['start_dir'], str(self.base.resolve()))
        with mock.patch('steam_nonsteam.discover_games', return_value=result):
            scan = self.scan()
        self.apply(scan)
        entry = parse_shortcuts(self.path.read_bytes())[0][0]
        self.assertEqual(entry['launchoptions'], '--channel "CN"')

    def test_scan_cancellation_cannot_be_imported(self):
        with mock.patch('steam_nonsteam.discover_games', return_value={'candidates': [], 'cancelled': True}):
            result = self.scan()
        self.assertIsNone(result['plan_id'])
        self.assertIsNone(self.importer.plan)

    def test_unknown_game_candidates_are_not_recommended(self):
        (self.games / 'OddGame.exe').write_bytes(b'MZgame')
        scan = self.scan()
        odd = next(x for x in scan['candidates'] if x['name'] == 'OddGame')
        self.assertEqual(odd['confidence'], 'review')

    def test_launcher_shortcuts_for_different_games_keep_arguments(self):
        launcher = self.games / 'launcher.exe'
        launcher.write_bytes(b'MZlauncher')
        links = [{'name': name, 'exe': str(launcher), 'args': args, 'start_dir': str(self.games)}
                 for name, args in [('原神', '--game genshin'), ('绝区零', '--game zzz'), ('米哈游启动器', '')]]
        with mock.patch('steam_nonsteam._shortcut_targets', return_value=(links, [])), mock.patch('steam_nonsteam._registry_locations', return_value=[]), mock.patch('steam_nonsteam._common_game_locations', return_value=[]):
            result = discover_games([], True, threading.Event(), [])
        self.assertEqual(sum(x['confidence'] == 'recognized' for x in result['candidates']), 2)
        with mock.patch('steam_nonsteam.discover_games', return_value=result):
            self.apply()
        entries, _ = parse_shortcuts(self.path.read_bytes())
        self.assertEqual({x['launchoptions'] for x in entries}, {'--game genshin', '--game zzz'})
        self.assertEqual(len({x['appid'] for x in entries}), 2)

    def test_launcher_and_game_binary_merge_but_variant_can_be_selected(self):
        launcher = self.games / 'launcher.exe'
        launcher.write_bytes(b'MZlauncher')
        links = [{'name': '原神', 'exe': str(launcher), 'args': '--game=hk4e_cn --reason=4', 'start_dir': str(self.games)}]
        with mock.patch('steam_nonsteam._shortcut_targets', return_value=(links, [])), mock.patch('steam_nonsteam._registry_locations', return_value=[]), mock.patch('steam_nonsteam._common_game_locations', return_value=[self.games]):
            result = discover_games([], True, threading.Event(), [])
        self.assertEqual(len(result['candidates']), 1)
        game = result['candidates'][0]
        self.assertEqual(len(game['alternatives']), 2)
        self.assertEqual(game['exe'], str(launcher.resolve()))
        with mock.patch('steam_nonsteam.discover_games', return_value=result):
            scan = self.scan()
        self.assertNotIn('signature', scan['candidates'][0]['alternatives'][0])
        direct = next(x for x in scan['candidates'][0]['alternatives'] if x['exe'] == str(self.exe.resolve()))
        applied = self.importer.apply({'plan_id': scan['plan_id'], 'selected': [direct['id']]})
        self.assertEqual(applied['added'], 1)
        self.assertEqual(parse_shortcuts(self.path.read_bytes())[0][0]['exe'], f'"{self.exe.resolve()}"')
        # A launcher shortcut must now be reported as the same already-added game.
        with mock.patch('steam_nonsteam._shortcut_targets', return_value=(links, [])), mock.patch('steam_nonsteam._registry_locations', return_value=[]), mock.patch('steam_nonsteam._common_game_locations', return_value=[]):
            scan = self.importer.scan({'roots': [], 'automatic': True})
        self.assertEqual(len(scan['candidates']), 1)
        self.assertTrue(scan['candidates'][0]['existing'])
        with self.assertRaisesRegex(SteamError, '无需重复'):
            self.apply(scan)

    def test_duplicate_variants_in_one_forged_batch_only_add_one_game(self):
        links = [{'name': '原神', 'exe': str(self.exe), 'args': arg, 'start_dir': str(self.games)}
                 for arg in ('', '--channel CN')]
        with mock.patch('steam_nonsteam._shortcut_targets', return_value=(links, [])), mock.patch('steam_nonsteam._registry_locations', return_value=[]), mock.patch('steam_nonsteam._common_game_locations', return_value=[]):
            scan = self.importer.scan({'roots': [], 'automatic': True})
        self.assertEqual(len(scan['candidates']), 1)
        ids = [x['id'] for x in scan['candidates'][0]['alternatives']]
        result = self.importer.apply({'plan_id': scan['plan_id'], 'selected': ids})
        self.assertEqual((result['added'], result['skipped']), (1, 1))

    def test_unreal_bootstrap_and_shipping_binary_are_one_game(self):
        root = self.base / 'Games' / 'Example'
        binary = root / 'Example' / 'Binaries' / 'WinGDK'
        binary.mkdir(parents=True)
        (root / 'Engine').mkdir()
        (root / 'Example.exe').write_bytes(b'MZbootstrap')
        (binary / 'Example-WinGDK-Shipping.exe').write_bytes(b'MZgame')
        result = discover_games([str(root)], False, threading.Event(), [])
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(len(result['candidates'][0]['alternatives']), 2)
        self.assertEqual(result['candidates'][0]['exe'], str((root / 'Example.exe').resolve()))

    def test_same_display_name_does_not_merge_unrelated_games(self):
        from steam_nonsteam import _group_candidates
        items = [{'id': str(i), 'name': 'Game', 'exe': str(self.base / str(i) / 'Game.exe'), 'args': '',
                  'source': '安装目录', 'confidence': 'review'} for i in range(2)]
        self.assertEqual(len(_group_candidates(items)[0]), 2)

    def test_unknown_games_using_one_launcher_keep_distinct_game_arguments(self):
        launcher = self.games / 'launcher.exe'
        launcher.write_bytes(b'MZlauncher')
        links = [{'name': 'Custom Game', 'exe': str(launcher), 'args': f'--game {code}', 'start_dir': str(self.games)}
                 for code in ('first', 'second')]
        with mock.patch('steam_nonsteam._shortcut_targets', return_value=(links, [])), mock.patch('steam_nonsteam._registry_locations', return_value=[]), mock.patch('steam_nonsteam._common_game_locations', return_value=[]):
            result = discover_games([], True, threading.Event(), [])
        self.assertEqual(len(result['candidates']), 2)
        self.assertEqual({x['args'] for x in result['candidates']}, {'--game first', '--game second'})
        self.assertTrue(all(x['confidence'] == 'review' for x in result['candidates']))

    def test_common_locations_find_singular_game_and_direct_install_folders(self):
        from steam_nonsteam import _common_game_locations
        drive = self.base / 'disk'
        game = drive / 'Game' / 'Standalone'
        game.mkdir(parents=True)
        (game / 'Standalone.exe').write_bytes(b'MZgame')
        (game / 'Standalone_Data').mkdir()
        other = drive / 'OddTitle'
        other.mkdir()
        (other / 'OddTitle.exe').write_bytes(b'MZgodot')
        (other / 'OddTitle.pck').write_bytes(b'godot')
        app = drive / 'PlainApp'
        app.mkdir()
        (app / 'PlainApp.exe').write_bytes(b'MZapp')
        with mock.patch('steam_nonsteam._drive_roots', return_value=[drive]):
            roots = _common_game_locations()
        self.assertIn(drive / 'Game', roots)
        self.assertIn(other, roots)
        with mock.patch('steam_nonsteam._shortcut_targets', return_value=([], [])), mock.patch('steam_nonsteam._registry_locations', return_value=[]), mock.patch('steam_nonsteam._common_game_locations', return_value=roots):
            result = discover_games([], True, threading.Event(), [])
        self.assertEqual({x['name'] for x in result['candidates']}, {'Standalone', 'OddTitle'})

    def test_many_data_files_do_not_hide_game_executable_or_next_root(self):
        crowded = self.games / 'bin64'
        crowded.mkdir()
        for index in range(1300):
            (crowded / f'{index}.data').touch()
        (crowded / 'exefile.exe').write_bytes(b'MZEVE')
        with mock.patch('steam_nonsteam._shortcut_targets', return_value=([], [])), mock.patch('steam_nonsteam._registry_locations', return_value=[]), mock.patch('steam_nonsteam._common_game_locations', return_value=[self.games]):
            result = discover_games([], True, threading.Event(), [])
        self.assertEqual({x['name'] for x in result['candidates']}, {'原神', 'EVE Online'})

    def test_epic_manifest_filters_non_games_and_preserves_arguments(self):
        manifests = self.base / 'programdata' / 'Epic' / 'EpicGamesLauncher' / 'Data' / 'Manifests'
        manifests.mkdir(parents=True)
        game = {'DisplayName': 'Example', 'InstallLocation': str(self.games), 'LaunchExecutable': self.exe.name,
                'LaunchCommand': '--locale zh', 'bIsApplication': True, 'bIsIncompleteInstall': False}
        (manifests / 'game.item').write_text(json.dumps(game))
        (manifests / 'editor.item').write_text(json.dumps({**game, 'bIsApplication': False}))
        (manifests / 'download.item').write_text(json.dumps({**game, 'bIsIncompleteInstall': True}))
        (manifests / 'corrupt.item').write_text('{bad')
        with mock.patch.dict('os.environ', {'PROGRAMDATA': str(self.base / 'programdata')}), mock.patch('steam_nonsteam._packaged_game_entries', return_value=[]):
            result = _platform_entries()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['args'], '--locale zh')

    def test_registered_xbox_games_use_distinct_validated_app_ids(self):
        from steam_nonsteam import _packaged_game_entries, _game_key, _package_target
        data = {'games': [{'PackageFamilyName': 'Vendor.Game_one'}, {'PackageFamilyName': 'Vendor.Other_two'}],
                'apps': [{'Name': 'First Game', 'AppID': 'Vendor.Game_one!Main'},
                         {'Name': 'Second Game', 'AppID': 'Vendor.Other_two!Main'},
                         {'Name': 'Bad', 'AppID': 'Vendor.Game_one!Main & calc.exe'}]}
        response = mock.Mock(returncode=0, stdout=json.dumps(data).encode())
        with mock.patch('steam_nonsteam.subprocess.run', return_value=response):
            games = _packaged_game_entries()
        self.assertEqual(len(games), 2)
        self.assertNotEqual(_game_key(games[0]), _game_key(games[1]))
        self.assertTrue(_package_target(Path(games[0]['exe']), games[0]['args']))
        self.assertFalse(_package_target(self.exe, games[0]['args']))

    def test_packaged_game_batch_import_preserves_system_launch_commands(self):
        system = self.base / 'Windows'
        system.mkdir()
        explorer = system / 'explorer.exe'
        explorer.write_bytes(b'MZsystemhost')
        entries = [{'name': f'Xbox Game {i}', 'exe': str(explorer),
                    'args': f'shell:AppsFolder\\Vendor.Game_{i}!Main', 'start_dir': str(system), 'confirmed': True}
                   for i in range(2)]
        with mock.patch.dict('os.environ', {'WINDIR': str(system)}), \
             mock.patch('steam_nonsteam._platform_entries', return_value=entries), \
             mock.patch('steam_nonsteam._shortcut_targets', return_value=([], [])), \
             mock.patch('steam_nonsteam._registry_locations', return_value=[]), \
             mock.patch('steam_nonsteam._common_game_locations', return_value=[]):
            scan = self.importer.scan({'roots': [], 'automatic': True})
            self.assertEqual(len(scan['candidates']), 2)
            result = self.apply(scan)
            self.assertEqual(result['added'], 2)
            self.assertEqual({x['launchoptions'] for x in parse_shortcuts(self.path.read_bytes())[0]},
                             {x['args'] for x in entries})

    def test_desktop_bridge_tracks_writes_and_surfaces_steam_guard(self):
        organizer = Organizer(self.library.root)
        api = DesktopApi(organizer, self.base / 'log.txt')
        scan = api.scan_local_games({'roots': [str(self.games)], 'automatic': False})
        with mock.patch('steam_web.steam_running', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'Steam 正在运行'):
                api.import_local_games({'plan_id': scan['plan_id'], 'selected': [scan['candidates'][0]['id']]})
        self.assertFalse(api._is_mutation_active())
        with mock.patch('steam_web.steam_running', return_value=False):
            result = api.import_local_games({'plan_id': scan['plan_id'], 'selected': [scan['candidates'][0]['id']]})
            self.assertEqual(result['added'], 1)
            api.undo_local_import()
        self.assertFalse(self.path.exists())
        self.assertFalse(api._is_mutation_active())

    def test_http_import_routes_require_csrf_and_preserve_transaction(self):
        organizer = Organizer(self.library.root)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def post(route, payload, token=CSRF_TOKEN):
            request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/local-games/{route}',
                data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'X-Steam-Organizer-Token': token})
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.load(response)
        try:
            with mock.patch('steam_web.ORGANIZER', organizer), mock.patch('steam_web.steam_running', return_value=False):
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    post('scan', {}, token='wrong')
                self.assertEqual(denied.exception.code, 403)
                scan = post('scan', {'roots': [str(self.games)], 'automatic': False})
                result = post('import', {'plan_id': scan['plan_id'], 'selected': [scan['candidates'][0]['id']]})
                self.assertEqual(result['added'], 1)
                self.assertTrue(self.path.exists())
                post('undo', {})
                self.assertFalse(self.path.exists())
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)

    def test_corrupted_backup_is_rejected(self):
        result = self.apply()
        data = self.path.read_bytes()
        receipt = Path(result['backup'])
        record = json.loads(receipt.read_text())
        record['before'] = base64.b64encode(b'bad').decode()
        receipt.write_text(json.dumps(record))
        with self.assertRaisesRegex(SteamError, '校验失败'):
            self.importer.undo()
        self.assertEqual(self.path.read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
