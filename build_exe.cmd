@echo off
rem Build a single-file exe. Everything stays ASCII on purpose: this file is
rem parsed with the OEM codepage, so Chinese literals here would get mangled.
rem The Chinese-named copy is produced without any non-ASCII literal below.
cd /d "%~dp0"
py -3.9 -m PyInstaller --noconfirm --onefile --windowed --name TypeAtCursor ^
  --distpath "%~dp0dist" --workpath "%TEMP%\tac_build" --specpath "%TEMP%\tac_build" ^
  "%~dp0type_at_cursor.pyw"
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "Copy-Item -LiteralPath 'dist\TypeAtCursor.exe' -Destination ('dist\' + [char]0x8F93 + [char]0x5165 + [char]0x5230 + [char]0x5149 + [char]0x6807 + '.exe') -Force"
if errorlevel 1 exit /b 1
echo Done. See the dist folder.
