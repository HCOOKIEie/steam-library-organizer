"""Verify both frozen layouts against source and record release integrity."""
import argparse
import ast
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pefile
from PyInstaller.archive.readers import CArchiveReader


def verify(version):
    root = Path(__file__).resolve().parent.parent
    release = root / 'dist/release'
    exe = release / f'SteamLibraryOrganizer-{version}-win-x64.exe'
    bundle = root / 'dist/onedir/SteamLibraryOrganizer'
    archive = CArchiveReader(str(exe))
    entries = {name.replace('\\', '/'): name for name in archive.toc}
    spec = ast.parse((root / 'scripts/SteamLibraryOrganizer.spec').read_text(encoding='utf-8'))
    assets = next(ast.literal_eval(n.value) for n in spec.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'UI_FILES' for t in n.targets))
    for name in assets:
        key = 'steam_ui/' + name
        data = (root / key).read_bytes()
        assert archive.extract(entries[key]) == data, 'Onefile differs: ' + name
        assert (bundle / '_internal' / key).read_bytes() == data, 'Onedir differs: ' + name
    runtime = ['python313.dll', 'VCRUNTIME140.dll', '_tkinter.pyd',
               'webview/lib/Microsoft.Web.WebView2.Core.dll',
               'webview/lib/Microsoft.Web.WebView2.WinForms.dll']
    runtime += [f'webview/lib/runtimes/win-{arch}/native/WebView2Loader.dll'
                for arch in ('x64', 'x86', 'arm64')]
    for name in runtime:
        assert name in entries and (bundle / '_internal' / name).is_file(), name
    major, minor, patch = map(int, version.split('.'))
    for path in (exe, bundle / 'SteamLibraryOrganizer.exe'):
        pe = pefile.PE(str(path))
        try:
            assert pe.FILE_HEADER.Machine == 0x8664
            info = pe.VS_FIXEDFILEINFO[0]
            assert (info.FileVersionMS, info.FileVersionLS) == (major << 16 | minor, patch << 16)
        finally:
            pe.close()
    assert exe.read_bytes() == (root / 'dist/onefile/SteamLibraryOrganizer.exe').read_bytes()
    with zipfile.ZipFile(release / f'SteamLibraryOrganizer-{version}-win-x64-portable.zip') as z:
        assert z.testzip() is None
        names = {name.replace('\\', '/'): name for name in z.namelist()}
        for name in assets:
            assert z.read(names['_internal/steam_ui/' + name]) == (root / 'steam_ui' / name).read_bytes(), name
        assert z.read(names['SteamLibraryOrganizer.exe']) == (bundle / 'SteamLibraryOrganizer.exe').read_bytes()
        for name in ('README.md', 'THIRD_PARTY_NOTICES.md'):
            assert z.read(names[name]) == (root / name).read_bytes(), name
        for path in (root / 'THIRD_PARTY_LICENSES').iterdir():
            if path.is_file():
                assert z.read(names['THIRD_PARTY_LICENSES/' + path.name]) == path.read_bytes(), path.name
    with zipfile.ZipFile(release / f'SteamLibraryOrganizer-{version}-third-party-licenses.zip') as z:
        assert z.testzip() is None
        for path in (root / 'THIRD_PARTY_LICENSES').iterdir():
            if path.is_file():
                assert z.read('THIRD_PARTY_LICENSES/' + path.name) == path.read_bytes(), path.name
    report = dict(version=version, verified_utc=datetime.now(timezone.utc).isoformat(),
                  ui_assets_exactly_match_source=len(assets), runtime_files_checked_in_both_layouts=len(runtime),
                  portable_zip_crc='PASS', licenses='PASS', pe_architecture_and_version=f'AMD64; {version}.0',
                  gui_smoke_test='Not performed by this artifact integrity checker.')
    (release / 'BUILD-VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    lines = [hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name for p in sorted(release.iterdir())
             if p.is_file() and p.name != 'SHA256SUMS.txt']
    (release / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    verify(parser.parse_args().version)
