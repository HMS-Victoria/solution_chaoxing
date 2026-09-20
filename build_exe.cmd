@echo off
setlocal
set "PIP_CACHE_DIR=%~dp0build\pip-cache"
cd /d "%~dp0"
rem ASCII only. BUILD_PYTHON optionally selects a Python 3.9.13 x64 executable.
if exist ".venv-build\Scripts\python.exe" goto ready
if defined BUILD_PYTHON (
  "%BUILD_PYTHON%" -m venv .venv-build
) else (
  py -3.9 -m venv .venv-build
)
if errorlevel 1 exit /b 1
:ready
".venv-build\Scripts\python.exe" -c "import sys,struct; assert sys.version_info[:3] == (3,9,13) and struct.calcsize('P') == 8, 'Python 3.9.13 x64 required'"
if errorlevel 1 exit /b 1
".venv-build\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 exit /b 1
".venv-build\Scripts\python.exe" build_release.py
exit /b %errorlevel%
