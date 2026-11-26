@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8765/api/shutdown' -TimeoutSec 3; Write-Host $r.message -ForegroundColor Green } catch { Write-Host 'Aucun serveur GTA Ranked Studio actif sur le port 8765.' -ForegroundColor Yellow }"
echo.
pause
