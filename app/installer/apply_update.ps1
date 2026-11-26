﻿#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [Parameter(Mandatory=$true)][string]$ArchivePath,
    [Parameter(Mandatory=$true)][string]$ExpectedVersion,
    [Parameter(Mandatory=$true)][int]$ParentPid,
    [Parameter(Mandatory=$true)][string]$LogPath
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$backupRoot = $null
$stagingRoot = $null
$backedDirectories = @()
$backedFiles = @()
$replacedDirectories = @()
$replacedFiles = @()
$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$ArchivePath = [System.IO.Path]::GetFullPath($ArchivePath)
$LogPath = [System.IO.Path]::GetFullPath($LogPath)

function Write-UpdateLog {
    param([Parameter(Mandatory=$true)][string]$Message)
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    try {
        $parent = Split-Path -Parent $LogPath
        if (-not [string]::IsNullOrWhiteSpace($parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    }
    catch {
        Write-Output ('LOG-WRITE-ERROR: ' + $_.Exception.Message)
        throw
    }
}

function Get-PackageVersion {
    param([Parameter(Mandatory=$true)][string]$Folder)
    $versionFile = Join-Path $Folder 'VERSION.txt'
    if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf)) {
        throw "VERSION.txt absent du paquet : $versionFile"
    }
    $text = [System.IO.File]::ReadAllText($versionFile, [System.Text.Encoding]::UTF8).TrimStart([char]0xFEFF)
    $match = [regex]::Match($text, '(?im)^\s*Version\s*:\s*(\d+(?:\.\d+){2,3})\s*$')
    if (-not $match.Success) { throw 'Le numéro de version du paquet est illisible.' }
    return $match.Groups[1].Value
}

try {
    Write-UpdateLog '=== GTA Ranked Studio updater ==='
    Write-UpdateLog "PowerShell version: $($PSVersionTable.PSVersion)"
    Write-UpdateLog "ProjectRoot: $ProjectRoot"
    Write-UpdateLog "ArchivePath: $ArchivePath"
    Write-UpdateLog "ExpectedVersion: $ExpectedVersion"
    Write-UpdateLog "ParentPid: $ParentPid"

    if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) { throw "Installation introuvable : $ProjectRoot" }
    if (-not (Test-Path -LiteralPath $ArchivePath -PathType Leaf)) { throw "Archive de mise à jour introuvable : $ArchivePath" }
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'config.yaml') -PathType Leaf)) { throw 'config.yaml est absent : ce dossier ne semble pas être une installation GTA Ranked Studio.' }

    # Attendre la fermeture du serveur/lanceur. Une ligne de progression est écrite toutes les 5 secondes.
    $deadline = (Get-Date).AddSeconds(120)
    $lastWaitLog = Get-Date
    while (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) {
            throw "Le processus GTA Ranked Studio ($ParentPid) est toujours actif après 120 secondes. Aucun fichier applicatif n'a été remplacé."
        }
        if (((Get-Date) - $lastWaitLog).TotalSeconds -ge 5) {
            Write-UpdateLog "En attente de la fermeture de GTA Ranked Studio (PID $ParentPid)..."
            $lastWaitLog = Get-Date
        }
        Start-Sleep -Milliseconds 500
    }
    Write-UpdateLog 'Le processus GTA Ranked Studio est fermé.'

    $stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("GTA-Ranked-Studio-update-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
    Write-UpdateLog "Extraction de l'archive vers $stagingRoot"
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $stagingRoot -Force
    $packageRoot = Join-Path $stagingRoot 'gta-ranked-studio'
    if (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) { throw 'Structure du paquet invalide : dossier gta-ranked-studio absent.' }

    $packageVersion = Get-PackageVersion -Folder $packageRoot
    if ($packageVersion -ne $ExpectedVersion) { throw "Version attendue $ExpectedVersion, version du paquet $packageVersion." }
    foreach ($directoryName in @('studio', 'installer', 'docs')) {
        if (-not (Test-Path -LiteralPath (Join-Path $packageRoot $directoryName) -PathType Container)) {
            throw "Le paquet est incomplet : dossier $directoryName absent."
        }
    }
    Write-UpdateLog "Archive valide : version $packageVersion."

    $backupRoot = Join-Path $ProjectRoot ("work\updates\rollback-{0}-to-{1}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'), $packageVersion)
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    Write-UpdateLog "Sauvegarde des fichiers applicatifs vers $backupRoot"

    $rootFiles = @(
        'INSTALL.bat', 'UPDATE-FROM-ARCHIVE.bat', 'REPAIR.bat',
        'START-STUDIO.bat', 'START-STUDIO.vbs', 'STOP-STUDIO.bat',
        'pyproject.toml', 'requirements.txt', '.gitignore', 'README.md',
        'GUIDE_INSTALLATION_FR.md', 'LIRE-MOI-DABORD.txt',
        'config.yaml.default', 'VERSION.txt'
    )

    foreach ($directoryName in @('studio', 'installer', 'docs')) {
        $target = Join-Path $ProjectRoot $directoryName
        if (Test-Path -LiteralPath $target -PathType Container) {
            Copy-Item -LiteralPath $target -Destination $backupRoot -Recurse -Force
            $backedDirectories += $directoryName
        }
    }
    foreach ($fileName in $rootFiles) {
        $target = Join-Path $ProjectRoot $fileName
        if (Test-Path -LiteralPath $target -PathType Leaf) {
            Copy-Item -LiteralPath $target -Destination $backupRoot -Force
            $backedFiles += $fileName
        }
    }

    Write-UpdateLog 'Installation des nouveaux fichiers applicatifs.'
    foreach ($directoryName in @('studio', 'installer', 'docs')) {
        $target = Join-Path $ProjectRoot $directoryName
        $replacedDirectories += $directoryName
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        Copy-Item -LiteralPath (Join-Path $packageRoot $directoryName) -Destination $ProjectRoot -Recurse -Force
        Write-UpdateLog "Dossier remplacé : $directoryName"
    }
    foreach ($fileName in $rootFiles) {
        $source = Join-Path $packageRoot $fileName
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            $replacedFiles += $fileName
            Copy-Item -LiteralPath $source -Destination (Join-Path $ProjectRoot $fileName) -Force
        }
    }

    # Comparer les deux sources de dépendances : requirements.txt et pyproject.toml.
    $oldRequirements = Join-Path $backupRoot 'requirements.txt'
    $newRequirements = Join-Path $ProjectRoot 'requirements.txt'
    $oldProject = Join-Path $backupRoot 'pyproject.toml'
    $newProject = Join-Path $ProjectRoot 'pyproject.toml'
    $venvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw 'Environnement Python absent après mise à jour : .venv\Scripts\python.exe est introuvable.'
    }
    if (-not (Test-Path -LiteralPath $newRequirements -PathType Leaf) -or -not (Test-Path -LiteralPath $newProject -PathType Leaf)) {
        throw 'Manifestes de dépendances absents après mise à jour.'
    }

    $requirementsChanged = $true
    if ((Test-Path -LiteralPath $oldRequirements -PathType Leaf) -and (Test-Path -LiteralPath $oldProject -PathType Leaf)) {
        $oldHash = (Get-FileHash -LiteralPath $oldRequirements -Algorithm SHA256).Hash
        $newHash = (Get-FileHash -LiteralPath $newRequirements -Algorithm SHA256).Hash
        $oldProjectHash = (Get-FileHash -LiteralPath $oldProject -Algorithm SHA256).Hash
        $newProjectHash = (Get-FileHash -LiteralPath $newProject -Algorithm SHA256).Hash
        $requirementsChanged = ($oldHash -ne $newHash) -or ($oldProjectHash -ne $newProjectHash)
    }

    if ($requirementsChanged) {
        Write-UpdateLog 'Les manifestes Python ont changé : mise à jour de l’environnement runtime.'
        & $venvPython -m pip install --disable-pip-version-check --prefer-binary -e $ProjectRoot 2>&1 | ForEach-Object { Write-UpdateLog ([string]$_) }
        if ($LASTEXITCODE -ne 0) {
            throw "La mise à jour des dépendances Python a échoué (code $LASTEXITCODE)."
        }
    }
    else {
        Write-UpdateLog 'Manifestes Python inchangés : aucune installation pip nécessaire.'
    }

    & $venvPython -m pip check 2>&1 | ForEach-Object { Write-UpdateLog ([string]$_) }
    if ($LASTEXITCODE -ne 0) {
        throw 'pip check a détecté une incohérence après la mise à jour.'
    }

    $runtimeCheck = Join-Path $ProjectRoot 'installer\check_runtime.py'
    if (-not (Test-Path -LiteralPath $runtimeCheck -PathType Leaf)) {
        throw 'Le smoke test runtime est absent après mise à jour.'
    }
    Write-UpdateLog 'Contrôle runtime des modules applicatifs après mise à jour.'
    & $venvPython $runtimeCheck 2>&1 | ForEach-Object { Write-UpdateLog ([string]$_) }
    if ($LASTEXITCODE -ne 0) {
        throw 'Le contrôle runtime après mise à jour a échoué.'
    }

    # Les prompts par défaut sont actualisés sans écraser les prompts actifs.
    $sourcePrompts = Join-Path $packageRoot 'prompts'
    $targetPrompts = Join-Path $ProjectRoot 'prompts'
    New-Item -ItemType Directory -Path $targetPrompts -Force | Out-Null
    if (Test-Path -LiteralPath $sourcePrompts -PathType Container) {
        Get-ChildItem -LiteralPath $sourcePrompts -Filter '*.default.txt' -File | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $targetPrompts -Force
        }
    }

    $sourceWhoosh = Join-Path $packageRoot 'assets\sfx\soft_whoosh.wav'
    $targetWhoosh = Join-Path $ProjectRoot 'assets\sfx\soft_whoosh.wav'
    if ((Test-Path -LiteralPath $sourceWhoosh -PathType Leaf) -and -not (Test-Path -LiteralPath $targetWhoosh)) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $targetWhoosh) -Force | Out-Null
        Copy-Item -LiteralPath $sourceWhoosh -Destination $targetWhoosh
    }

    $installedVersion = Get-PackageVersion -Folder $ProjectRoot
    if ($installedVersion -ne $ExpectedVersion) { throw "Contrôle final échoué : version installée $installedVersion." }
    Write-UpdateLog "Mise à jour vers $installedVersion réussie."
    Write-UpdateLog 'Redémarrage de GTA Ranked Studio.'
    $launcher = Join-Path $ProjectRoot 'START-STUDIO.bat'
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'START-STUDIO.bat est absent après mise à jour.' }
    Start-Process -FilePath $env:ComSpec -ArgumentList @('/c', ('"' + $launcher + '"')) -WorkingDirectory $ProjectRoot
    Write-UpdateLog 'Commande de redémarrage envoyée.'
}
catch {
    $message = $_.Exception.Message
    try { Write-UpdateLog "ERREUR : $message" } catch { Write-Output ('UPDATE-ERROR: ' + $message) }
    try { Write-UpdateLog 'Tentative de restauration de la version précédente.' } catch {}
    try {
        foreach ($directoryName in $replacedDirectories) {
            $target = Join-Path $ProjectRoot $directoryName
            if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
            if ($backedDirectories -contains $directoryName) {
                Copy-Item -LiteralPath (Join-Path $backupRoot $directoryName) -Destination $ProjectRoot -Recurse -Force
            }
        }
        foreach ($fileName in $replacedFiles) {
            $target = Join-Path $ProjectRoot $fileName
            if (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target -Force }
            if ($backedFiles -contains $fileName) {
                Copy-Item -LiteralPath (Join-Path $backupRoot $fileName) -Destination $target -Force
            }
        }
        Write-UpdateLog 'Restauration terminée.'
        $oldLauncher = Join-Path $ProjectRoot 'START-STUDIO.bat'
        if (Test-Path -LiteralPath $oldLauncher -PathType Leaf) {
            Start-Process -FilePath $env:ComSpec -ArgumentList @('/c', ('"' + $oldLauncher + '"')) -WorkingDirectory $ProjectRoot
        }
    }
    catch {
        try { Write-UpdateLog "ERREUR RESTAURATION : $($_.Exception.Message)" } catch {}
    }
    Write-Output "Échec de la mise à jour : $message"
    exit 1
}
finally {
    if ($stagingRoot -and (Test-Path -LiteralPath $stagingRoot)) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
