# Third-Party Notices

This file lists third-party software and UI references associated with the
Steam Library Organizer v1.1.1 Windows x64 build. Exact Python package versions
are pinned in `requirements-lock.txt`; verbatim license texts are stored under
`THIRD_PARTY_LICENSES/` and must be shipped with the release archive.

These notices apply only to the identified third-party components. They do not
provide a license for this project's own source code. No project-level license
has been selected at the time of this notice; the repository is currently
source-available, not licensed as an OSI-approved open-source project.

## Bundled runtime components

### Collection particle field

Collection's square-particle background is independently authored Canvas2D/SVG code. Its visual reference is the user's supplied Code-Codex blinking-squares screenshot and the local reference project. No code, fonts, artwork or assets from that project are distributed. The earlier Newsreader font and landscape relief have been removed.

### Calm interface reference (unreleased source update)

The redesigned Calm theme refers to OKX's official [interface update](https://www.okx.com/en-us/learn/okx-interface-update) for black/white visual hierarchy and restrained bright-green accents. Its layout, CSS card artwork and interaction code are independently authored. No OKX code, brand mark, screenshot, font or other asset is bundled. See `docs/calm-interface.md`.

## Release build toolchain

The clean v1.1.0 environment also pins the following build packages. Most are
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

## Development-only UI checks

The Node.js test harness uses jsdom 26.1.0 (MIT), pinned with its dependency
graph in `package-lock.json`. These packages are development tools and are not
bundled in the Windows application or offline HTML preview.

## Historical TRACES appearance

The retired TRACES appearance was an original local HTML/CSS/SVG implementation
inspired by the geometric composition, coordinate lines and serif typography
of Arknights' 众生行记 event interface. Visual reference:
[UI / interaction / motion archive by 胖鱼鱼呀](https://www.bilibili.com/video/BV1WFkwBJEhR/).
No game artwork, characters, logos, screenshots, proprietary fonts, music or
video are bundled. Arknights belongs to its respective rights holders; this
community project is not affiliated with or endorsed by them.

## RELOAD appearance

The optional RELOAD appearance is an original CSS layout inspired by the
geometric typography and blue palette of Persona 3 Reload, with the user's
[video reference](https://www.bilibili.com/video/BV1Xntq6hEvK/) as visual direction.
The profile cutout is an AI-generated fan illustration of Makoto Yuki, generated at the user's request with a user-supplied menu screenshot as the style reference. It is not official artwork. No extracted game assets, proprietary fonts, or audio are bundled. Layout and water animation are original HTML/CSS/Canvas2D. Display text uses bundled Anton under SIL OFL 1.1; interface text uses local system fonts.

## Historical Uiverse interaction references

Earlier versions of the Steam Library Organizer included interaction ideas from
community components published by [Uiverse.io](https://uiverse.io/) and mirrored
in the [Uiverse Galaxy](https://github.com/uiverse-io/galaxy) repository.

The v1.1.0 redesign removes the decorative shine, grid, morphing checkbox, and
animated cards. The historical source attributions and license remain below.
The interface uses local system fonts and inline vector artwork. No third-party
JavaScript runtime is bundled.

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
# Barlow Condensed

The P5R-inspired appearance bundles Barlow Condensed Black Italic by Jeremy Tribby, licensed under the SIL Open Font License 1.1. Source: https://github.com/google/fonts/tree/main/ofl/barlowcondensed . The full license is included in `steam_ui/fonts/OFL-BarlowCondensed.txt`, `THIRD_PARTY_LICENSES/BarlowCondensed-OFL.txt`, and standalone exported HTML.

P5R visual inspiration: https://persona.atlus.com/p5r/ . Official title artwork, logos, music and game fonts are not bundled. The Joker profile is an AI-generated fan illustration, not an official game asset. Persona characters belong to their respective rights holders; this project is not affiliated with or endorsed by ATLUS/SEGA. The theme's layout, paper cuts and transitions are original HTML/CSS. Generation prompts and provenance are recorded in `docs/persona-art-prompts.md`.


## Anton display font

The RELOAD homepage uses upright Anton Regular by The Anton Project Authors, under SIL Open Font License 1.1. Downloaded from the Google Fonts official repository: https://github.com/google/fonts/tree/main/ofl/anton . The complete license is included in `steam_ui/fonts/OFL-Anton.txt`, `THIRD_PARTY_LICENSES/Anton-OFL.txt`, and embedded in the standalone HTML and desktop page. It is not a proprietary Persona game font.


P3R motion reference: John Persona, Pause Menu - Persona 3 Reload, https://www.youtube.com/watch?v=4d6x1CIgLSc . The recording was viewed to study circular scene reveals and underwater movement; no video, textures, models or code from the recording or third-party recreations are bundled. Local timing and implementation notes are in `docs/p3r-motion-reference.md`.
