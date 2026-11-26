@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo ============================================================
echo GTA RANKED STUDIO - INSTALLATION / MISE A JOUR
echo ============================================================
echo.
echo Python 3.11 et FFmpeg sont detectes avant installation.
echo Les dependances deja presentes et les donnees utilisateur sont conservees.
echo.
where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo ERREUR : Windows PowerShell est introuvable.
  echo Windows 10/11 doit inclure powershell.exe.
  echo.
  pause
  exit /b 2
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\check-script.ps1"
if errorlevel 1 (
  echo Les scripts PowerShell n'ont pas passe la verification de syntaxe.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\install.ps1"
set "INSTALL_EXIT=%ERRORLEVEL%"
echo.
if not "%INSTALL_EXIT%"=="0" (
  echo L'installation n'est pas terminee. Consulte logs\install.log si disponible.
) else (
  echo GTA Ranked Studio est installe ou mis a jour.
)
echo.
pause
exit /b %INSTALL_EXIT%
