@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo ============================================================
echo GTA RANKED STUDIO - MISE A JOUR SANS PERTE DE DONNEES
echo ============================================================
echo.
where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo ERREUR : Windows PowerShell est introuvable.
  pause
  exit /b 2
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\check-script.ps1"
if errorlevel 1 (
  echo ERREUR : le controle syntaxique PowerShell a echoue. Aucune mise a jour n'a ete appliquee.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\update_from_archive.ps1"
set "UPDATE_EXIT=%ERRORLEVEL%"
echo.
if not "%UPDATE_EXIT%"=="0" echo La mise a jour n'est pas terminee. Consulte le message ci-dessus.
echo.
pause
exit /b %UPDATE_EXIT%
