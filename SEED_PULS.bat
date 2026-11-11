@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo Bitte zuerst Befragungsstudio beenden.
echo Der Seed ergaenzt lokale Exportdaten und erstellt vorher eine Datenbanksicherung.
echo.
if not exist ".venv\Scripts\python.exe" (
  echo Bitte zuerst INSTALL.bat ausfuehren.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -u seed_puls.py %*
set "STUDIO_SEED_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %STUDIO_SEED_EXIT%
