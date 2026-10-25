"""Validate actual Python strings in PyInstaller manifests, including wrapped paths."""
from __future__ import annotations

import argparse
import ast
import ntpath
import re
from pathlib import Path


def validate_manifest(text: str, venv: str) -> None:
    allowed = ntpath.normcase(ntpath.normpath(venv)).rstrip('\\') + '\\'
    # AST constants join pprint-wrapped adjacent strings without executing
    # version-resource constructor calls found in EXE manifests.
    for node in ast.walk(ast.parse(text, mode='eval')):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        item = node.value
        normalized = ntpath.normcase(ntpath.normpath(item))
        if re.search(r'anaconda|miniconda|appdata\\roaming\\python|\\\.codex\\|codex-runtimes', normalized):
            raise ValueError('Contaminated environment path in build manifest')
        if 'site-packages' in normalized and not normalized.startswith(allowed):
            raise ValueError('site-packages outside the release environment')
        if re.search(r'\\(?:\.venv|venv|env)[^\\]*\\', normalized) and not normalized.startswith(allowed):
            raise ValueError('Another virtual environment in build manifest')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work_root', type=Path)
    parser.add_argument('venv')
    args = parser.parse_args()
    manifests = list(args.work_root.rglob('*.toc'))
    if not manifests:
        raise ValueError('No PyInstaller manifests were generated')
    for manifest in manifests:
        try:
            validate_manifest(manifest.read_text(encoding='utf-8'), args.venv)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(f'{manifest.name}: {exc}') from exc
    print(f'Validated environment paths in {len(manifests)} PyInstaller manifests.')


if __name__ == '__main__':
    main()
