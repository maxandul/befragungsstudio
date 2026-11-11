@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
py -3 -c "import sys; assert sys.version_info >= (3,11)" >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 oder neuer mit Python Launcher wird benoetigt.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Installation fehlgeschlagen. Bitte die Meldung oben pruefen.
  pause
  exit /b 1
)
echo Installation abgeschlossen. Bitte START.bat ausfuehren.
pause
