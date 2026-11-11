@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo Puls-Neustart: bisherige Einstellungen und Daten der mitgelieferten Pulsreihen
echo werden nach einer Sicherung geloescht und aus den CSV-Dateien neu eingerichtet.
echo Andere Projekte bleiben erhalten. Bitte zuerst die App beenden.
echo.
if not exist ".venv\Scripts\python.exe" (
  echo Bitte zuerst INSTALL.bat ausfuehren.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -u seed_puls.py --reset-puls %*
set "STUDIO_SEED_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %STUDIO_SEED_EXIT%
