@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo GTA Ranked Studio n'est pas installe.
  echo Lance d'abord INSTALL.bat.
  pause
  exit /b 1
)
start "" wscript.exe "%~dp0START-STUDIO.vbs"
exit /b 0
