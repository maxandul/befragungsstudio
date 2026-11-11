@echo off
setlocal
chcp 65001 >nul
title Befragungsstudio - Lokaler Start
echo =======================================================
echo   Befragungsstudio - Lokaler Start
echo =======================================================
echo.
echo [1/2] Oeffne Programmordner ...
cd /d "%~dp0"
if errorlevel 1 (
  echo FEHLER: Der Programmordner ist nicht erreichbar.
  pause
  exit /b 1
)
echo Ordner: %CD%
if not exist ".venv\Scripts\python.exe" (
  echo Bitte zuerst INSTALL.bat ausfuehren.
  pause
  exit /b 1
)
if not exist "run_web.py" (
  echo FEHLER: run_web.py fehlt. Bitte das aktualisierte ZIP vollstaendig entpacken.
  pause
  exit /b 1
)
echo.
echo [2/2] Starte Python und pruefe die Anwendung ...
echo Falls Python hier nicht reagiert, bitte diese letzte Meldung weitergeben.
".venv\Scripts\python.exe" -u -X faulthandler run_web.py --port 5051 --open-browser
set "STUDIO_EXIT=%ERRORLEVEL%"
echo.
if not "%STUDIO_EXIT%"=="0" (
  echo FEHLER: Start beendet mit Code %STUDIO_EXIT%.
  echo Bitte die Meldungen oben oder die Datei instance\start.log weitergeben.
) else (
  echo Befragungsstudio wurde beendet.
)
pause
exit /b %STUDIO_EXIT%
