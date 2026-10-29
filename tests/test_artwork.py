import base64
import json
import tempfile
import struct
import zlib
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
import unittest
from pathlib import Path
from unittest import mock

from steam_artwork import KINDS, _allowed_url, _image, _steam_assets
from steam_artwork import _Redirect, _download_image
from steam_library_core import SteamError, SteamLibrary
from steam_web import Organizer
from steam_web import Handler, CSRF_TOKEN
from steam_modern import DesktopApi
from tests.test_steam_organizer import make_steam_root


PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aYbkAAAAASUVORK5CYII=')


class ArtworkTests(unittest.TestCase):
    def local_image(self, name, width, height):
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
        image = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
        image += chunk(b'IDAT', zlib.compress((b'\0' + b'\x11\x22\x33\xff' * width) * height)) + chunk(b'IEND', b'')
        path = self.base / 'Game' / name
        path.write_bytes(image)
        return path

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        cache = mock.patch('steam_artwork._cache_root', return_value=self.base / 'cache')
        cache.start()
        self.addCleanup(cache.stop)
        self.org = Organizer(make_steam_root(self.base / 'Steam'))
        patch = mock.patch('steam_web.steam_running', return_value=False)
        patch.start()
        self.addCleanup(patch.stop)
        folder = self.base / 'Game'
        folder.mkdir()
        (folder / 'Example.exe').write_bytes(b'MZfixture')
        scan = self.org.local_games.scan({'roots': [str(folder)], 'automatic': False})
        imported = self.org.local_games.apply({'plan_id': scan['plan_id'], 'selected': [scan['candidates'][0]['id']]})
        self.game_id = imported['appids'][0]
        self.manager = self.org.artwork
        data = self.manager.load()
        self.payload = {k: data[k] for k in ('account', 'revision')}
        self.payload['game_id'] = self.game_id
        self.grid = self.org.library.config_dir / 'grid'

    def prepare(self):
        with mock.patch('steam_artwork._json', return_value={'items': [{'id': 123, 'name': 'Example', 'type': 'app'}]}):
            search = self.manager.search(self.payload)
        options = {k: [f'https://shared.fastly.steamstatic.com/steam/apps/123/{k}.png'] for k in KINDS}
        with mock.patch('steam_artwork._steam_assets', return_value=(options, [])), mock.patch('steam_artwork._fetch', return_value=PNG):
            preview = self.manager.preview({**self.payload, 'match_id': search['matches'][0]['id']})
        return {**self.payload, 'plan_id': preview['plan_id'], 'selected': list(KINDS)}, preview

    def test_preview_never_writes_steam_and_apply_uses_short_appid_names(self):
        before = (self.org.library.config_dir / 'shortcuts.vdf').read_bytes()
        payload, preview = self.prepare()
        self.assertFalse(self.grid.exists())
        self.assertEqual(set(preview['images']), set(KINDS))
        self.assertTrue(preview['images']['hero']['preview'].startswith('data:image/png;base64,'))
        result = self.manager.apply(payload)
        self.assertEqual(len(result['saved']), 4)
        self.assertEqual({p.name for p in self.grid.iterdir()}, {
            f'{self.game_id}p.png', f'{self.game_id}.png', f'{self.game_id}_hero.png',
            f'{self.game_id}_logo.png', f'{self.game_id}.json'})
        position = json.loads((self.grid / f'{self.game_id}.json').read_bytes())
        self.assertEqual(position['logoPosition']['pinnedPosition'], 'BottomLeft')
        self.assertEqual((self.org.library.config_dir / 'shortcuts.vdf').read_bytes(), before)
        self.manager.undo(self.payload)
        self.assertEqual(list(self.grid.iterdir()), [])

    def test_existing_art_is_preserved_and_replacement_undo_restores_exact_bytes(self):
        self.grid.mkdir()
        old = self.grid / f'{self.game_id}p.jpg'
        old.write_bytes(b'my custom cover')
        position = self.grid / f'{self.game_id}.json'
        position.write_bytes(b'{"custom placement":true}')
        payload, _ = self.prepare()
        result = self.manager.apply(payload)
        self.assertEqual(result['skipped'], ['cover'])
        self.assertEqual(old.read_bytes(), b'my custom cover')
        self.assertEqual(position.read_bytes(), b'{"custom placement":true}')
        self.manager.undo(self.payload)
        payload, _ = self.prepare()
        self.manager.apply({**payload, 'replace': True})
        self.assertFalse(old.exists())
        self.assertEqual((self.grid / f'{self.game_id}p.png').read_bytes(), PNG)
        self.manager.undo(self.payload)
        self.assertEqual(old.read_bytes(), b'my custom cover')
        self.assertEqual(position.read_bytes(), b'{"custom placement":true}')

    def test_steam_running_stale_shortcuts_and_external_grid_changes_block_writes(self):
        payload, _ = self.prepare()
        with mock.patch('steam_web.steam_running', return_value=True):
            with self.assertRaisesRegex(SteamError, 'Steam 正在运行'):
                self.manager.apply(payload)
        self.assertFalse(self.grid.exists())
        self.grid.mkdir()
        (self.grid / f'{self.game_id}p.jpg').write_bytes(b'new cover')
        with self.assertRaisesRegex(SteamError, '图片已变化'):
            self.manager.apply(payload)
        payload, _ = self.prepare()
        path = self.org.library.config_dir / 'shortcuts.vdf'
        path.write_bytes(path.read_bytes().replace(b'Example', b'Changed'))
        with self.assertRaisesRegex(SteamError, '账号或快捷方式已变化'):
            self.manager.apply(payload)
        self.assertEqual((self.grid / f'{self.game_id}p.jpg').read_bytes(), b'new cover')

    def test_failed_partial_write_rolls_back_every_preceding_image(self):
        self.grid.mkdir()
        original = self.grid / f'{self.game_id}p.jpg'
        original.write_bytes(b'old custom art')
        payload, _ = self.prepare()
        writer = SteamLibrary._atomic_write
        def fail_hero(path, data):
            if Path(path).name == f'{self.game_id}_hero.png':
                raise OSError('disk full')
            return writer(path, data)
        with mock.patch.object(SteamLibrary, '_atomic_write', side_effect=fail_hero):
            with self.assertRaises(OSError):
                self.manager.apply({**payload, 'replace': True})
        self.assertEqual(original.read_bytes(), b'old custom art')
        self.assertEqual({p.name for p in self.grid.iterdir()}, {original.name})
        with self.assertRaisesRegex(SteamError, '没有可撤销'):
            self.manager.undo(self.payload)

    def test_undo_refuses_to_overwrite_later_user_changes(self):
        payload, _ = self.prepare()
        self.manager.apply(payload)
        path = self.grid / f'{self.game_id}_hero.png'
        path.write_bytes(b'new manual background')
        with self.assertRaisesRegex(SteamError, '又被修改'):
            self.manager.undo(self.payload)
        self.assertEqual(path.read_bytes(), b'new manual background')

    def test_ambiguous_and_non_exact_names_never_auto_apply(self):
        for rows in ([{'id': 1, 'name': 'Example II', 'type': 'app'}],
                     [{'id': 1, 'name': 'Example', 'type': 'app'}, {'id': 2, 'name': 'Example', 'type': 'app'}]):
            with mock.patch('steam_artwork._json', return_value={'items': rows}), mock.patch.object(self.manager, 'preview') as preview:
                result = self.manager.auto(self.payload)
                self.assertIn(result['status'], ('unmatched', 'ambiguous'))
                preview.assert_not_called()
        self.assertFalse(self.grid.exists())

    def test_auto_exact_match_saves_art_without_using_a_model(self):
        options = {k: [f'https://shared.fastly.steamstatic.com/steam/apps/123/{k}.png'] for k in KINDS}
        with mock.patch('steam_artwork._json', return_value={'items': [{'id': 123, 'name': 'Example', 'type': 'app'}]}), \
             mock.patch('steam_artwork._steam_assets', return_value=(options, [])), mock.patch('steam_artwork._fetch', return_value=PNG):
            result = self.manager.auto(self.payload)
        self.assertEqual(result['status'], 'matched')
        self.assertEqual(len(result['saved']), 4)
        self.assertEqual(self.manager.auto(self.payload)['status'], 'complete')

    def test_local_art_auto_uses_game_directory_without_network_and_undoes(self):
        for name, width, height in [('cover.png', 600, 900), ('hero.png', 1200, 400), ('logo.png', 400, 100), ('banner.png', 920, 430)]:
            self.local_image(name, width, height)
        with mock.patch('steam_artwork._json', side_effect=AssertionError('No network for local art')):
            result = self.manager.auto(self.payload)
        self.assertEqual(result['provider'], 'local')
        self.assertEqual(set(result['saved']), set(KINDS))
        self.manager.undo(self.payload)
        self.assertEqual(list(self.grid.iterdir()), [])

    def test_local_art_ambiguity_manual_selection_and_source_change(self):
        self.local_image('poster-a.png', 600, 900)
        alternative = self.local_image('poster-b.png', 300, 450)
        with mock.patch('steam_artwork._json', return_value={'items': []}):
            self.assertEqual(self.manager.auto(self.payload)['status'], 'unmatched')
        self.assertFalse(self.grid.exists())
        search = self.manager.search({**self.payload, 'provider': 'local', 'folder': str(self.base / 'Game')})
        request = {**self.payload, 'match_id': search['matches'][0]['id']}
        preview = self.manager.preview({**request, 'local_selection': {'cover': 1}})
        self.assertEqual(preview['images']['cover']['width'], 300)
        self.assertEqual(len(preview['local_choices']['cover']), 2)
        with self.assertRaisesRegex(SteamError, '选择无效'):
            self.manager.preview({**request, 'local_selection': {'cover': 99}})
        alternative.write_bytes(PNG)
        with self.assertRaisesRegex(SteamError, '发生变化'):
            self.manager.preview({**request, 'local_selection': {'cover': 1}})
        self.assertFalse(self.grid.exists())

    def test_local_art_no_icon_upscaling_or_arbitrary_path_in_preview(self):
        self.local_image('icon.png', 256, 256)
        result = self.manager.search({**self.payload, 'provider': 'local'})
        self.assertEqual(result['matches'], [])
        self.assertIn('程序图标', result['message'])
        with self.assertRaises(SteamError):
            self.manager.search({**self.payload, 'provider': 'local', 'folder': str(Path(self.base.anchor))})

    def test_sgdb_key_is_not_retained_and_only_static_game_assets_are_requested(self):
        key = 'a' * 32
        with mock.patch('steam_artwork._json', return_value={'data': [{'id': 99, 'name': 'Example'}]}):
            search = self.manager.search({**self.payload, 'provider': 'sgdb', 'api_key': key})
        self.assertNotIn(key, json.dumps(self.manager.matches))
        with mock.patch('steam_artwork._json', return_value={'data': [{'url': 'https://cdn2.steamgriddb.com/image.png'}]}) as query, \
             mock.patch('steam_artwork._fetch', return_value=PNG):
            preview = self.manager.preview({**self.payload, 'match_id': search['matches'][0]['id'], 'api_key': key})
        self.assertEqual(len(preview['images']), 4)
        self.assertEqual(len(query.call_args_list), 4)
        self.assertTrue(all('types=static' in call.args[0] for call in query.call_args_list))
        self.assertNotIn(key, json.dumps({p: {k: v for k, v in data.items() if k != 'assets'} for p, data in self.manager.plans.items()}))

    def test_download_detects_an_image_changed_during_network_lookup(self):
        with mock.patch('steam_artwork._json', return_value={'items': [{'id': 123, 'name': 'Example', 'type': 'app'}]}):
            match = self.manager.search(self.payload)['matches'][0]
        def changed_art(_):
            self.grid.mkdir()
            (self.grid / f'{self.game_id}p.jpg').write_bytes(b'new custom art')
            return {k: ['https://cdn2.steamgriddb.com/image.png'] for k in KINDS}, []
        with mock.patch('steam_artwork._steam_assets', side_effect=changed_art), mock.patch('steam_artwork._fetch', return_value=PNG):
            with self.assertRaisesRegex(SteamError, '下载图片期间原图发生变化'):
                self.manager.preview({**self.payload, 'match_id': match['id']})
        self.assertEqual((self.grid / f'{self.game_id}p.jpg').read_bytes(), b'new custom art')

    def test_redirect_drops_api_credentials_and_rejects_unrelated_domains(self):
        request = urllib.request.Request('https://www.steamgriddb.com/api/v2/grids/game/1', headers={'Authorization': 'Bearer private-key'})
        redirected = _Redirect().redirect_request(request, None, 302, '', {}, 'https://cdn2.steamgriddb.com/image.png')
        self.assertIsNone(redirected.get_header('Authorization'))
        with self.assertRaises(SteamError):
            _Redirect().redirect_request(request, None, 302, '', {}, 'https://attacker.test/image.png')

    def test_image_download_uses_official_mirror_then_verified_cache(self):
        url = 'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/123/cover.png'
        with mock.patch('steam_artwork._fetch', side_effect=[SteamError('连接失败'), PNG]) as download:
            image = _download_image(url)
        self.assertEqual(download.call_count, 2)
        self.assertIn('shared.akamai.steamstatic.com', image['url'])
        with mock.patch('steam_artwork._fetch') as download:
            cached = _download_image(url)
        download.assert_not_called()
        self.assertEqual(cached['data'], PNG)
        with self.assertRaises(SteamError):
            _download_image('http://localhost/cover.png')

    def test_forged_match_plan_selection_and_cross_account_payloads_rejected(self):
        with self.assertRaisesRegex(SteamError, '搜索结果已失效'):
            self.manager.preview({**self.payload, 'match_id': 'not-issued', 'url': 'file:///etc/passwd'})
        payload, _ = self.prepare()
        with self.assertRaisesRegex(SteamError, '请选择预览'):
            self.manager.apply({**payload, 'selected': ['../../other']})
        with self.assertRaisesRegex(SteamError, '账号或快捷方式已变化'):
            self.manager.apply({**payload, 'account': 'other'})
        self.manager.plans[payload['plan_id']]['created'] -= 1801
        with self.assertRaisesRegex(SteamError, '图片预览已失效'):
            self.manager.apply(payload)
        self.assertFalse(self.grid.exists())

    def test_hashed_localized_steam_paths_are_used_instead_of_guessed_old_paths(self):
        common = {'library_assets_full': {field: {'image': {'schinese': f'hash/{name}.png'}}
                  for field, name in [('library_capsule', 'cover'), ('library_hero', 'hero'), ('library_logo', 'logo'), ('library_header', 'wide')]}}
        with mock.patch('steam_artwork._json', return_value={'data': {'123': {'common': common}}}):
            result, _ = _steam_assets(123)
        self.assertTrue(all('/123/hash/' in urls[0] for urls in result.values()))

    def test_ssrf_svg_invalid_dimensions_and_unvalidated_keys_are_rejected(self):
        for url in ('file:///tmp/art.png', 'http://localhost/art.png', 'https://127.0.0.1/a',
                    'https://shared.fastly.steamstatic.com.attacker.test/a', 'https://user:pass@store.steampowered.com/a'):
            self.assertFalse(_allowed_url(url))
        for content in (b'<svg/>', b'<html>error</html>', PNG[:-1], b'MZexecutable'):
            with self.assertRaises(SteamError):
                _image(content)
        self.assertEqual(_image(PNG)['width'], 1)
        with self.assertRaisesRegex(SteamError, '密钥格式'):
            self.manager.search({**self.payload, 'api_key': 'bad\nkey'})

    def test_desktop_bridge_restricts_actions_and_releases_mutation_guard(self):
        api = DesktopApi(self.org, self.base / 'test.log')
        self.assertEqual(len(api.manage_artwork('load', {})['games']), 1)
        with self.assertRaisesRegex(RuntimeError, '请求无效'):
            api.manage_artwork('__dict__', {})
        with mock.patch.object(self.manager, 'auto', side_effect=SteamError('Steam 正在运行')):
            with self.assertRaises(RuntimeError):
                api.manage_artwork('auto', self.payload)
        self.assertFalse(api._is_mutation_active())

    def test_http_artwork_routes_require_csrf_and_use_the_same_backed_up_writer(self):
        payload, _ = self.prepare()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def post(action, data, token=CSRF_TOKEN):
            req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/artwork/{action}',
                data=json.dumps(data).encode(), headers={'Content-Type': 'application/json', 'X-Steam-Organizer-Token': token})
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.load(response)
        try:
            with mock.patch('steam_web.ORGANIZER', self.org):
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    post('load', {}, token='wrong')
                self.assertEqual(denied.exception.code, 403)
                self.assertEqual(len(post('load', {})['games']), 1)
                result = post('apply', payload)
                self.assertEqual(len(result['saved']), 4)
                post('undo', self.payload)
                self.assertEqual(list(self.grid.iterdir()), [])
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
