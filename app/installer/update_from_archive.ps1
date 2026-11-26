#requires -Version 5.1
<#
  GTA Ranked Studio - mise a jour incrementale depuis une archive extraite.
  Compatible avec une installation 0.2.6 et les versions 0.2.x precedentes.
  Les donnees utilisateur et l'environnement Python ne sont jamais remplaces.
#>
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$backupRoot = $null
$targetRoot = $null

function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host ("==> {0}" -f $Message) -ForegroundColor Cyan
}

function Get-AppVersion {
    param([Parameter(Mandatory = $true)][string]$Root)
    $versionFile = Join-Path $Root 'VERSION.txt'
    if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf)) {
        throw "VERSION.txt est absent dans : $Root"
    }
    # Read explicitly as UTF-8 and remove a possible BOM. Get-Content's
    # default encoding differs between Windows PowerShell and PowerShell 7.
    $text = [System.IO.File]::ReadAllText($versionFile, [System.Text.Encoding]::UTF8)
    $text = $text.TrimStart([char]0xFEFF)
    $match = [regex]::Match($text, '(?im)^\s*Version\s*:\s*(\d+\.\d+\.\d+(?:\.\d+)?)\s*$')
    if (-not $match.Success) {
        throw "Version illisible dans : $versionFile"
    }
    return [version]$match.Groups[1].Value
}

function Copy-CodeDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$From,
        [Parameter(Mandatory = $true)][string]$To,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Backup
    )
    $sourceDirectory = Join-Path $From $Name
    if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) {
        throw "Dossier de code absent dans l'archive : $Name"
    }
    $destinationDirectory = Join-Path $To $Name
    if (Test-Path -LiteralPath $destinationDirectory -PathType Container) {
        $backupDirectory = Join-Path $Backup $Name
        New-Item -ItemType Directory -Path (Split-Path -Parent $backupDirectory) -Force | Out-Null
        Copy-Item -LiteralPath $destinationDirectory -Destination $Backup -Recurse -Force
        Remove-Item -LiteralPath $destinationDirectory -Recurse -Force
    }
    Copy-Item -LiteralPath $sourceDirectory -Destination $To -Recurse -Force
    Write-Host "Mis a jour : $Name" -ForegroundColor Green
}

try {
    $sourceItem = Get-Item -LiteralPath (Join-Path $PSScriptRoot '..') -ErrorAction Stop
    if (-not $sourceItem.PSIsContainer) {
        throw "Le dossier de l'archive extraite est introuvable."
    }
    $sourceRoot = $sourceItem.FullName
    $sourceVersion = Get-AppVersion -Root $sourceRoot
    if ($sourceVersion -lt [version]'0.3.3') {
        throw "Cette archive doit etre en version 0.3.3 ou plus recente (version detectee : $sourceVersion)."
    }

    $localAppData = [Environment]::GetFolderPath('LocalApplicationData')
    $pointer = Join-Path $localAppData 'GTA Ranked Studio\install-location.txt'
    if (Test-Path -LiteralPath $pointer -PathType Leaf) {
        $remembered = (Get-Content -LiteralPath $pointer -Raw -ErrorAction SilentlyContinue).Trim().Trim([char]0xFEFF)
        if (-not [string]::IsNullOrWhiteSpace($remembered) -and (Test-Path -LiteralPath $remembered -PathType Container)) {
            $rememberedVersion = Get-AppVersion -Root $remembered
            if ($rememberedVersion -lt $sourceVersion) {
                $targetRoot = (Get-Item -LiteralPath $remembered).FullName
                Write-Host "Installation existante detectee : version $rememberedVersion" -ForegroundColor Green
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($targetRoot)) {
        Write-Host "Colle le chemin du dossier gta-ranked-studio deja installe (v0.2.x)." -ForegroundColor Yellow
        Write-Host 'Exemple : C:\Outils\GTA Ranked Studio\gta-ranked-studio-installable-v0.2.6\gta-ranked-studio' -ForegroundColor Gray
        $targetInput = Read-Host 'Dossier existant'
        $targetInput = $targetInput.Trim().Trim('"')
        if ([string]::IsNullOrWhiteSpace($targetInput)) {
            throw 'Aucun dossier cible renseigne.'
        }
        if (-not (Test-Path -LiteralPath $targetInput -PathType Container)) {
            throw "Dossier introuvable : $targetInput"
        }
        $targetRoot = (Get-Item -LiteralPath $targetInput -ErrorAction Stop).FullName
    }

    if ($sourceRoot -ieq $targetRoot) {
        throw "Le dossier source et le dossier cible sont identiques. Extrais d'abord le ZIP dans un autre dossier."
    }
    $targetVersion = Get-AppVersion -Root $targetRoot
    if ($targetVersion -ge $sourceVersion) {
        throw "La cible est deja en version $targetVersion. Aucune mise a jour necessaire."
    }
    if ($targetVersion -lt [version]'0.2.6') {
        throw "Cette mise a jour attend une installation 0.2.6 ou plus recente. Version detectee : $targetVersion."
    }

    foreach ($relativeFile in @('config.yaml', '.venv\Scripts\python.exe', 'studio\web\app.py')) {
        if (-not (Test-Path -LiteralPath (Join-Path $targetRoot $relativeFile) -PathType Leaf)) {
            throw "Le dossier cible n'est pas une installation complete : $relativeFile est absent."
        }
    }

    Write-Host "Source : $sourceRoot"
    Write-Host "Cible  : $targetRoot"
    Write-Host ''
    Write-Host 'Donnees preservees : .venv, config.yaml, prompts actifs, data, inbox, out, models, logs, work et tools (ainsi que assets).'  -ForegroundColor Green

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupRoot = Join-Path $targetRoot ("work\updates\backup-{0}-from-{1}" -f $stamp, $targetVersion)
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

    Write-Step 'Sauvegarde du code actuellement installe'
    foreach ($directoryName in @('studio', 'installer', 'docs')) {
        $sourceDirectory = Join-Path $sourceRoot $directoryName
        if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) {
            throw "Dossier de code absent de l'archive : $directoryName"
        }
        $destinationDirectory = Join-Path $targetRoot $directoryName
        if (Test-Path -LiteralPath $destinationDirectory -PathType Container) {
            Copy-Item -LiteralPath $destinationDirectory -Destination $backupRoot -Recurse -Force
        }
    }

    Write-Step 'Mise a jour du code'
    foreach ($directoryName in @('studio', 'installer', 'docs')) {
        $destinationDirectory = Join-Path $targetRoot $directoryName
        if (Test-Path -LiteralPath $destinationDirectory -PathType Container) {
            Remove-Item -LiteralPath $destinationDirectory -Recurse -Force
        }
        Copy-Item -LiteralPath (Join-Path $sourceRoot $directoryName) -Destination $targetRoot -Recurse -Force
    }

    $rootFiles = @(
        'INSTALL.bat', 'UPDATE-FROM-ARCHIVE.bat', 'REPAIR.bat',
        'START-STUDIO.bat', 'START-STUDIO.vbs', 'STOP-STUDIO.bat',
        'pyproject.toml', 'requirements.txt', '.gitignore', 'README.md',
        'GUIDE_INSTALLATION_FR.md', 'LIRE-MOI-DABORD.txt',
        'config.yaml.default', 'VERSION.txt'
    )
    foreach ($fileName in $rootFiles) {
        $sourceFile = Join-Path $sourceRoot $fileName
        if (Test-Path -LiteralPath $sourceFile -PathType Leaf) {
            Copy-Item -LiteralPath $sourceFile -Destination (Join-Path $targetRoot $fileName) -Force
        }
    }

    # Ajoute les nouveaux assets fournis par l'application sans remplacer un asset utilisateur existant.
    $targetSfxDirectory = Join-Path $targetRoot 'assets\sfx'
    New-Item -ItemType Directory -Path $targetSfxDirectory -Force | Out-Null
    $sourceWhoosh = Join-Path $sourceRoot 'assets\sfx\soft_whoosh.wav'
    $targetWhoosh = Join-Path $targetSfxDirectory 'soft_whoosh.wav'
    if ((Test-Path -LiteralPath $sourceWhoosh -PathType Leaf) -and -not (Test-Path -LiteralPath $targetWhoosh -PathType Leaf)) {
        Copy-Item -LiteralPath $sourceWhoosh -Destination $targetWhoosh
        Write-Host 'Effet whoosh original ajoute.' -ForegroundColor Green
    }

    # Met a jour uniquement les prompts par defaut. Les fichiers actifs sont personnels.
    $sourcePrompts = Join-Path $sourceRoot 'prompts'
    $targetPrompts = Join-Path $targetRoot 'prompts'
    New-Item -ItemType Directory -Path $targetPrompts -Force | Out-Null
    Get-ChildItem -LiteralPath $sourcePrompts -Filter '*.default.txt' -File | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $targetPrompts $_.Name) -Force
    }

    Write-Step 'Verification de syntaxe PowerShell'
    $powershell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if (-not (Test-Path -LiteralPath $powershell -PathType Leaf)) {
        $powershellCommand = Get-Command -Name 'powershell.exe' -CommandType Application -ErrorAction SilentlyContinue
        if (-not $powershellCommand) { throw 'Windows PowerShell 5.1 est introuvable.' }
        $powershell = $powershellCommand.Source
    }
    $checkScript = Join-Path $targetRoot 'installer\check-script.ps1'
    & $powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File $checkScript
    if ($LASTEXITCODE -ne 0) {
        throw 'La verification de syntaxe PowerShell a echoue. La sauvegarde du code est conservee.'
    }

    New-Item -ItemType Directory -Path (Split-Path -Parent $pointer) -Force | Out-Null
    Set-Content -LiteralPath $pointer -Value $targetRoot -Encoding UTF8

    Write-Step 'Verification runtime et diagnostic'
    $installScript = Join-Path $targetRoot 'installer\install.ps1'
    & $powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File $installScript
    $installExitCode = $LASTEXITCODE
    if ($installExitCode -ne 0) {
        throw "L'installateur a retourne le code $installExitCode. La sauvegarde du code est conservee dans $backupRoot."
    }

    Write-Host ''
    Write-Host 'MISE A JOUR TERMINEE.' -ForegroundColor Green
    Write-Host "Application mise a jour dans : $targetRoot" -ForegroundColor Green
    Write-Host "Sauvegarde du code precedent : $backupRoot" -ForegroundColor Gray
    Write-Host 'Le .venv, la configuration et toutes les donnees utilisateur ont ete conserves.' -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ''
    Write-Host 'MISE A JOUR INTERROMPUE' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    if (-not [string]::IsNullOrWhiteSpace($backupRoot) -and (Test-Path -LiteralPath $backupRoot -PathType Container)) {
        Write-Host "Sauvegarde disponible : $backupRoot" -ForegroundColor Yellow
    }
    Write-Host 'Aucun dossier utilisateur (data, inbox, out, models, logs) n a ete supprime.' -ForegroundColor Yellow
    exit 1
}
