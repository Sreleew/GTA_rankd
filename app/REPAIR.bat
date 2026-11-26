@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
echo Reparation / mise a jour incrementale de GTA Ranked Studio...
echo Les clips, la base, les modeles et l'environnement Python sont conserves.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\check-script.ps1"
if errorlevel 1 (
  echo Les scripts PowerShell n'ont pas passe la verification de syntaxe.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install.ps1"
set "REPAIR_EXIT=%ERRORLEVEL%"
echo.
if not "%REPAIR_EXIT%"=="0" echo Reparation incomplete. Consulte logs\install.log.
pause
exit /b %REPAIR_EXIT%
