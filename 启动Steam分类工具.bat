@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0dist\onefile\SteamLibraryOrganizer.exe" (
  start "" "%~dp0dist\onefile\SteamLibraryOrganizer.exe"
  exit /b 0
)

if exist "%~dp0steam_modern.py" goto modern_source
if exist "%~dp0steam_desktop.py" goto legacy_source
goto missing_app

:modern_source

if exist "%~dp0.venv\Scripts\pythonw.exe" (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0steam_modern.py"
  exit /b 0
)

if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0steam_modern.py"
  exit /b %errorlevel%
)

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3.13-64 -V >nul 2>nul
  if not errorlevel 1 (
    where pyw.exe >nul 2>nul
    if not errorlevel 1 (
      start "" pyw.exe -3.13-64 "%~dp0steam_modern.py"
      exit /b 0
    )
    py.exe -3.13-64 "%~dp0steam_modern.py"
    exit /b %errorlevel%
  )
)

goto missing_python

:legacy_source

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3.13-64 -V >nul 2>nul
  if not errorlevel 1 (
    where pyw.exe >nul 2>nul
    if not errorlevel 1 (
      start "" pyw.exe -3.13-64 "%~dp0steam_desktop.py"
      exit /b 0
    )
    py.exe -3.13-64 "%~dp0steam_desktop.py"
    exit /b %errorlevel%
  )
)

:missing_python

echo CPython 3.13 x64 was not found. Install the python.org build or use SteamLibraryOrganizer.exe.
pause
exit /b 1

:missing_app
echo Steam Library Organizer files are incomplete. Reinstall or restore steam_modern.py.
pause
exit /b 1
