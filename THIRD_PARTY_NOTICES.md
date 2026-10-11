# Third-Party Notices

This file lists third-party software and UI references associated with the
Steam Library Organizer v1.0.2 Windows x64 build. Exact Python package versions
are pinned in `requirements-lock.txt`; verbatim license texts are stored under
`THIRD_PARTY_LICENSES/` and must be shipped with the release archive.

These notices apply only to the identified third-party components. They do not
provide a license for this project's own source code. No project-level license
has been selected at the time of this notice; the repository is currently
source-available, not licensed as an OSI-approved open-source project.

## Bundled runtime components

| Component | Version | License | Source / full text |
| --- | ---: | --- | --- |
| CPython | 3.13.2 x64 | PSF License Version 2 and bundled notices | [Python](https://www.python.org/) · `THIRD_PARTY_LICENSES/CPython-3.13.2.txt` |
| pypinyin | 0.55.0 | MIT | [Source](https://github.com/mozillazg/python-pinyin) · `THIRD_PARTY_LICENSES/pypinyin-0.55.0.txt` |
| pywebview | 6.2.1 | BSD-3-Clause | [Source](https://github.com/r0x0r/pywebview) · `THIRD_PARTY_LICENSES/pywebview-6.2.1.txt` |
| pythonnet | 3.2.0 | MIT | [Source](https://github.com/pythonnet/pythonnet) · `THIRD_PARTY_LICENSES/pythonnet-3.2.0.txt` |
| clr-loader | 0.3.1 | MIT | [Source](https://github.com/pythonnet/clr-loader) · `THIRD_PARTY_LICENSES/clr-loader-0.3.1.txt` |
| cffi | 2.1.1 | MIT-0 | [Source](https://github.com/python-cffi/cffi) · `THIRD_PARTY_LICENSES/cffi-2.1.1.txt` |
| pycparser | 3.11 | BSD-3-Clause | [Source](https://github.com/eliben/pycparser) · `THIRD_PARTY_LICENSES/pycparser-3.11.txt` |
| proxy_tools | 0.1.0 | BSD (upstream source notice) | [Source](https://github.com/jtushman/proxy_tools) · `THIRD_PARTY_LICENSES/proxy-tools-0.1.0.txt` |
| bottle | 0.13.4 | MIT | [Source](https://github.com/bottlepy/bottle) · `THIRD_PARTY_LICENSES/bottle-0.13.4.txt` |
| typing_extensions | 4.16.0 | PSF-2.0 | [Source](https://github.com/python/typing_extensions) · `THIRD_PARTY_LICENSES/typing-extensions-4.16.0.txt` |
| Microsoft.Web.WebView2 SDK files | 1.0.3856.49 | BSD-3-Clause plus notices | [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/) · `THIRD_PARTY_LICENSES/Microsoft.Web.WebView2-SDK-1.0.3856.49.txt` |

The SDK DLLs and loader above are bundled by pywebview. The Microsoft Edge
WebView2 **Runtime** is not redistributed by this project and remains a
separately installed Microsoft component. `proxy_tools` labels itself BSD in
its source header and upstream license, despite its package metadata reporting
MIT; this distribution retains the verbatim upstream license.

## Release build toolchain

The clean v1.0.2 environment also pins the following build packages. Most are
not application runtime imports; PyInstaller's bootloader and runtime hooks are
incorporated into the generated executable under the exception and licenses in
the listed files.

| Component | Version | Declared license | Full text |
| --- | ---: | --- | --- |
| PyInstaller | 6.22.2 | GPL-2.0-or-later with Bootloader Exception; runtime hooks Apache-2.0 | `THIRD_PARTY_LICENSES/PyInstaller-6.22.2.txt` |
| pyinstaller-hooks-contrib | 2026.8 | GPL-2.0-or-later with Bootloader Exception; runtime hooks Apache-2.0 | `THIRD_PARTY_LICENSES/pyinstaller-hooks-contrib-2026.8.txt` |
| altgraph | 0.17.5 | MIT | `THIRD_PARTY_LICENSES/altgraph-0.17.5.txt` |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | `THIRD_PARTY_LICENSES/packaging-26.3.txt` |
| pefile | 2024.8.26 | MIT | `THIRD_PARTY_LICENSES/pefile-2024.8.26.txt` |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | `THIRD_PARTY_LICENSES/pywin32-ctypes-0.2.3.txt` |
| setuptools | 84.0.0 | MIT and bundled notices | `THIRD_PARTY_LICENSES/setuptools-84.0.0.txt` |

## Uiverse interaction references

The Steam Library Organizer interface includes adapted interaction ideas from
community components published by [Uiverse.io](https://uiverse.io/) and mirrored
in the [Uiverse Galaxy](https://github.com/uiverse-io/galaxy) repository.

The components were redrawn to use this application's visual tokens,
accessibility semantics, reduced-motion behavior, and desktop layout. No
third-party JavaScript runtime is bundled.

## Referenced components

- Primary action highlight — “wise-goat-75” by iZOXVL / Armando VL
  - https://uiverse.io/iZOXVL/wise-goat-75
  - https://github.com/uiverse-io/galaxy/blob/main/Buttons/iZOXVL_wise-goat-75.html
- Selectable scope cards — “ordinary-stingray-85” by csozidev / Csőke Zalán
  - https://uiverse.io/csozidev/ordinary-stingray-85
  - https://github.com/uiverse-io/galaxy/blob/main/Radio-buttons/csozidev_ordinary-stingray-85.html
- Checkbox morph — “calm-cat-84” by SelfMadeSystem
  - https://uiverse.io/SelfMadeSystem/calm-cat-84
  - https://github.com/uiverse-io/galaxy/blob/main/Checkboxes/SelfMadeSystem_calm-cat-84.html
- Loading indicator — “serious-turkey-52” by Abraham Calsin
  - https://uiverse.io/abrahamcalsin/serious-turkey-52
  - https://github.com/uiverse-io/galaxy/blob/main/loaders/abrahamcalsin_serious-turkey-52.html
- Layered statistic cards — “cuddly-catfish-6” by Tiagoadag
  - https://uiverse.io/Tiagoadag/cuddly-catfish-6
  - https://github.com/uiverse-io/galaxy/blob/main/Cards/Tiagoadag_cuddly-catfish-6.html
- Status notification reveal — “gentle-octopus-87” by Alex Ruiz
  - https://uiverse.io/alexruix/gentle-octopus-87
  - https://github.com/uiverse-io/galaxy/blob/main/Notifications/alexruix_gentle-octopus-87.html
- Subtle grid pattern — “short-warthog-33” by kennyotsu / kotsu
  - https://uiverse.io/kennyotsu/short-warthog-33
  - https://github.com/uiverse-io/galaxy/blob/main/Patterns/kennyotsu_short-warthog-33.html

## Uiverse Galaxy license

The same license is also retained as
`THIRD_PARTY_LICENSES/Uiverse-Galaxy-MIT.txt` for release packaging.

MIT License

Copyright (c) 2023 Uiverse.io

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
