# Third-Party License Files

This directory contains the license texts associated with the dependencies and referenced UI components used for the v1.0.1 Windows x64 build. Exact Python package versions are pinned in `../requirements-lock.txt`.

## Bundled runtime components

| Component | Version | License file |
| --- | ---: | --- |
| CPython | 3.13.2 x64 | `CPython-3.13.2.txt` |
| pypinyin | 0.55.0 | `pypinyin-0.55.0.txt` |
| pywebview | 6.2.1 | `pywebview-6.2.1.txt` |
| pythonnet | 3.2.0 | `pythonnet-3.2.0.txt` |
| clr-loader | 0.3.1 | `clr-loader-0.3.1.txt` |
| cffi | 2.1.1 | `cffi-2.1.1.txt` |
| pycparser | 3.11 | `pycparser-3.11.txt` |
| proxy_tools | 0.1.0 | `proxy-tools-0.1.0.txt` |
| bottle | 0.13.4 | `bottle-0.13.4.txt` |
| typing_extensions | 4.16.0 | `typing-extensions-4.16.0.txt` |
| Microsoft.Web.WebView2 SDK files | 1.0.3856.49 | `Microsoft.Web.WebView2-SDK-1.0.3856.49.txt` |

The WebView2 SDK version above is the version embedded by pywebview 6.2.1. The Microsoft Edge WebView2 **Runtime** itself is not shipped in this repository or release archive; it is a separately installed Microsoft component.

`proxy_tools` 0.1.0 advertises `MIT` in its package metadata, but its source header and upstream `LICENSE.txt` identify the code as BSD licensed. The verbatim upstream license is retained here instead of silently substituting the metadata label.

## Build toolchain

These packages are pinned in the release build environment. Most are not imported by the application at runtime; PyInstaller's bootloader and runtime hooks are incorporated into the generated EXE under the exceptions and licenses in the listed files.

| Component | Version | License file |
| --- | ---: | --- |
| PyInstaller | 6.22.2 | `PyInstaller-6.22.2.txt` |
| pyinstaller-hooks-contrib | 2026.8 | `pyinstaller-hooks-contrib-2026.8.txt` |
| altgraph | 0.17.5 | `altgraph-0.17.5.txt` |
| packaging | 26.3 | `packaging-26.3.txt` |
| pefile | 2024.8.26 | `pefile-2024.8.26.txt` |
| pywin32-ctypes | 0.2.3 | `pywin32-ctypes-0.2.3.txt` |
| setuptools | 84.0.0 | `setuptools-84.0.0.txt` |

## UI references

The complete Uiverse Galaxy license used by the referenced interaction examples is in `Uiverse-Galaxy-MIT.txt`. Individual references and authors are listed in `../THIRD_PARTY_NOTICES.md`.

These third-party licenses apply only to their respective components. They do not grant a license to the Steam Library Organizer project's own source code. No project-level license has been selected at the time of this notice; the repository is currently source-available, not licensed as an OSI-approved open-source project.
