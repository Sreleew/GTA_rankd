[CmdletBinding()]
param([ValidateSet("shorts", "twitch", "bestof", "web")][string]$Target = "shorts")
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
    switch ($Target) {
        "shorts" {
            & $python @pythonPrefix -m pytest -q -c pyproject.toml tests/test_short_editor.py tests/test_render_integration.py tests/test_transcribe.py tests/test_speakers.py
            if ($LASTEXITCODE -ne 0) { throw "Les tests ciblés Shorts ont échoué." }
        }
        "twitch" {
            & $python @pythonPrefix -m pytest -q -c pyproject.toml tests/test_web.py -k "twitch or shorts_url or batch"
            if ($LASTEXITCODE -ne 0) { throw "Les tests API Twitch ont échoué." }
            & $python @pythonPrefix -m pytest -q -c pyproject.toml tests/test_twitch_download_ranges.py
            if ($LASTEXITCODE -ne 0) { throw "Les tests de téléchargement Twitch ont échoué." }
        }
        "bestof" {
            & $python @pythonPrefix -m pytest -q -c pyproject.toml tests/test_best_of.py
            if ($LASTEXITCODE -ne 0) { throw "Les tests du moteur Daily Best Of ont échoué." }
            & $python @pythonPrefix -m pytest -q -c pyproject.toml tests/test_web.py -k "best_of"
            if ($LASTEXITCODE -ne 0) { throw "Les tests API Daily Best Of ont échoué." }
        }
        "web" {
            & $python @pythonPrefix -m pytest -q -c pyproject.toml tests/test_web.py
            if ($LASTEXITCODE -ne 0) { throw "Les tests API et interface ont échoué." }
        }
    }
}
finally {
    if ($createdConfig) { Remove-Item "config.yaml" -Force -ErrorAction SilentlyContinue }
    Pop-Location
}
