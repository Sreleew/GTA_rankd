[CmdletBinding()]
param([switch]$SecurityAudit)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$appRoot = Join-Path $repoRoot "app"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonPrefix = @()
if (-not (Test-Path $python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py"; $pythonPrefix = @("-3.11") }
    else { $python = "python" }
}
$createdConfig = $false
Push-Location $appRoot
try {
    if (-not (Test-Path "config.yaml")) { Copy-Item "config.yaml.default" "config.yaml"; $createdConfig = $true }
    & $python @pythonPrefix -m compileall -q studio installer tests
    if ($LASTEXITCODE -ne 0) { throw "La compilation Python a échoué." }
    & $python @pythonPrefix -m pytest -q -c pyproject.toml
    if ($LASTEXITCODE -ne 0) { throw "La suite complète de tests a échoué." }
    if (Get-Command node -ErrorAction SilentlyContinue) {
        node --check studio/web/static/app.js
        if ($LASTEXITCODE -ne 0) { throw "Le contrôle syntaxique JavaScript a échoué." }
    } else { Write-Warning "Node.js absent : contrôle JavaScript ignoré." }
    & $python @pythonPrefix -m ruff check studio installer tests ..\tools
    if ($LASTEXITCODE -ne 0) { throw "Ruff a détecté des problèmes." }
    if ($SecurityAudit) {
        & $python @pythonPrefix -m pip_audit -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "L'audit de sécurité des dépendances a échoué." }
    }
    Write-Host "Suite complète terminée avec succès."
}
finally {
    if ($createdConfig) { Remove-Item "config.yaml" -Force -ErrorAction SilentlyContinue }
    Pop-Location
}
