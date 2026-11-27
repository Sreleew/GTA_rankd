[CmdletBinding()]
param([string]$PythonVersion = "3.11")
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
Push-Location $repoRoot
try {
    if (-not (Test-Path $venvPython)) {
        Write-Host "Création de l'environnement virtuel Python $PythonVersion..."
        & py "-$PythonVersion" -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Impossible de créer .venv avec Python $PythonVersion." }
    }
    Write-Host "Installation du projet en mode éditable et des outils de développement..."
    & $venvPython -m pip install --disable-pip-version-check --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Mise à jour de pip échouée." }
    & $venvPython -m pip install --disable-pip-version-check -e "app[dev]"
    if ($LASTEXITCODE -ne 0) { throw "Installation du projet et des dépendances dev échouée." }
    & $venvPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Des dépendances Python sont incohérentes." }
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Write-Host "FFmpeg : disponible." }
    else { Write-Warning "FFmpeg absent du PATH. Les tests de rendu et l'application en auront besoin." }
    if (Get-Command node -ErrorAction SilentlyContinue) { Write-Host "Node.js : disponible." }
    else { Write-Warning "Node.js absent du PATH. Le contrôle JavaScript sera indisponible." }
    Write-Host ""
    Write-Host "Environnement prêt et conservé dans .venv."
    Write-Host "Tests ciblés : .\scripts\test-quick.ps1 -Target shorts"
}
finally { Pop-Location }
