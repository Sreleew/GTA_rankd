﻿#requires -Version 5.1
<#
  GTA Ranked Studio - installateur Windows, incremental et reutilisable.
  - Reutilise le .venv existant et les paquets deja installes.
  - N'installe Python ou FFmpeg que s'ils sont absents.
  - Preserve les clips, bases SQLite, modeles, prompts et reglages.
  - Apres la premiere installation reussie, les futures archives peuvent etre
    extraites n'importe ou : le script mettra a jour l'installation existante.
#>

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$SourceRoot = $null
$ProjectRoot = $null
$InstallLog = $null
$GlobalInstallDir = $null
$InstallPointer = $null

function Write-InstallLog {
    param([string]$Message)
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    if (-not [string]::IsNullOrWhiteSpace($script:InstallLog)) {
        try {
            Add-Content -LiteralPath $script:InstallLog -Value $line -Encoding UTF8
        }
        catch {
            Write-Warning "Impossible d'ecrire le journal d'installation : $($_.Exception.Message)"
        }
    }
}

function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host ("==> {0}" -f $Message) -ForegroundColor Cyan
    Write-InstallLog $Message
}

function Refresh-ProcessPath {
    $sources = @(
        [string]$env:Path,
        [string][Environment]::GetEnvironmentVariable('Path', 'Machine'),
        [string][Environment]::GetEnvironmentVariable('Path', 'User')
    )
    $entries = New-Object 'System.Collections.Generic.List[string]'
    foreach ($source in $sources) {
        if (-not [string]::IsNullOrWhiteSpace($source)) {
            foreach ($entry in ($source -split ';')) {
                $clean = $entry.Trim().Trim('"')
                if (-not [string]::IsNullOrWhiteSpace($clean) -and -not $entries.Contains($clean)) {
                    [void]$entries.Add($clean)
                }
            }
        }
    }
    $env:Path = $entries -join ';'
}

function Test-Python311 {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [string[]]$Prefix = @()
    )
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        return $false
    }
    $arguments = @()
    if ($Prefix -and $Prefix.Count -gt 0) {
        $arguments += $Prefix
    }
    $versionCheckScript = Join-Path $ProjectRoot 'installer\check_python.py'
    if (-not (Test-Path -LiteralPath $versionCheckScript -PathType Leaf)) {
        return $false
    }
    $arguments += $versionCheckScript
    & $Executable @arguments *> $null
    return ($LASTEXITCODE -eq 0)
}

function Get-Python311 {
    Refresh-ProcessPath

    $launcher = Get-Command -Name 'py.exe' -CommandType Application -ErrorAction SilentlyContinue
    if ($launcher -and (Test-Python311 -Executable $launcher.Source -Prefix @('-3.11'))) {
        return @{ Exe = $launcher.Source; Prefix = @('-3.11') }
    }

    $python = Get-Command -Name 'python.exe' -CommandType Application -ErrorAction SilentlyContinue
    if ($python -and (Test-Python311 -Executable $python.Source)) {
        return @{ Exe = $python.Source; Prefix = @() }
    }

    $localAppData = [Environment]::GetFolderPath('LocalApplicationData')
    $fallbacks = @(
        (Join-Path $localAppData 'Programs\Python\Launcher\py.exe'),
        (Join-Path $env:WINDIR 'py.exe'),
        (Join-Path $localAppData 'Programs\Python\Python311\python.exe')
    )
    foreach ($candidate in $fallbacks) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        if ([IO.Path]::GetFileName($candidate) -ieq 'py.exe') {
            if (Test-Python311 -Executable $candidate -Prefix @('-3.11')) {
                return @{ Exe = $candidate; Prefix = @('-3.11') }
            }
        }
        elseif (Test-Python311 -Executable $candidate) {
            return @{ Exe = $candidate; Prefix = @() }
        }
    }
    return $null
}

function Ensure-WinGet {
    $winget = Get-Command -Name 'winget.exe' -CommandType Application -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'WinGet est introuvable. Installe App Installer depuis le Microsoft Store, puis relance INSTALL.bat. Tu peux aussi installer manuellement Python 3.11 64 bits et FFmpeg.'
    }
    return $winget.Source
}

function Ensure-Ffmpeg {
    Refresh-ProcessPath
    $ffmpeg = Get-Command -Name 'ffmpeg.exe' -CommandType Application -ErrorAction SilentlyContinue
    $ffprobe = Get-Command -Name 'ffprobe.exe' -CommandType Application -ErrorAction SilentlyContinue
    if ($ffmpeg -and $ffprobe) {
        Write-InstallLog "FFmpeg deja disponible : $($ffmpeg.Source)"
        return @{ Ffmpeg = $ffmpeg.Source; Ffprobe = $ffprobe.Source; InstalledNow = $false }
    }

    Write-Step 'FFmpeg absent : installation une seule fois via WinGet'
    $winget = Ensure-WinGet
    & $winget install --exact --id Gyan.FFmpeg --source winget --silent --accept-package-agreements --accept-source-agreements
    $wingetExitCode = $LASTEXITCODE
    Write-InstallLog "WinGet FFmpeg exit code: $wingetExitCode"

    Refresh-ProcessPath
    $ffmpeg = Get-Command -Name 'ffmpeg.exe' -CommandType Application -ErrorAction SilentlyContinue
    $ffprobe = Get-Command -Name 'ffprobe.exe' -CommandType Application -ErrorAction SilentlyContinue

    if (-not ($ffmpeg -and $ffprobe)) {
        $localAppData = [Environment]::GetFolderPath('LocalApplicationData')
        $packagesRoot = Join-Path $localAppData 'Microsoft\WinGet\Packages'
        if (Test-Path -LiteralPath $packagesRoot -PathType Container) {
            $candidate = Get-ChildItem -LiteralPath $packagesRoot -Filter 'ffmpeg.exe' -File -Recurse -ErrorAction SilentlyContinue |
                Where-Object { Test-Path -LiteralPath (Join-Path $_.Directory.FullName 'ffprobe.exe') } |
                Select-Object -First 1
            if ($candidate) {
                $binDir = $candidate.Directory.FullName
                $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
                $userEntries = @()
                if (-not [string]::IsNullOrWhiteSpace($userPath)) {
                    $userEntries = @($userPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
                }
                if ($userEntries -notcontains $binDir) {
                    $userEntries += $binDir
                    [Environment]::SetEnvironmentVariable('Path', ($userEntries -join ';'), 'User')
                }
                Refresh-ProcessPath
                $ffmpeg = Get-Command -Name 'ffmpeg.exe' -CommandType Application -ErrorAction SilentlyContinue
                $ffprobe = Get-Command -Name 'ffprobe.exe' -CommandType Application -ErrorAction SilentlyContinue
            }
        }
    }

    if (-not ($ffmpeg -and $ffprobe)) {
        throw "FFmpeg et FFprobe restent introuvables apres WinGet (code $wingetExitCode). Redemarre Windows puis relance INSTALL.bat."
    }
    return @{ Ffmpeg = $ffmpeg.Source; Ffprobe = $ffprobe.Source; InstalledNow = $true }
}

function Copy-ApplicationUpdate {
    param(
        [Parameter(Mandatory = $true)][string]$From,
        [Parameter(Mandatory = $true)][string]$To
    )

    $fromItem = Get-Item -LiteralPath $From -ErrorAction Stop
    $toItem = Get-Item -LiteralPath $To -ErrorAction SilentlyContinue
    if ($toItem -and $fromItem.FullName -ieq $toItem.FullName) {
        return
    }

    New-Item -ItemType Directory -Path $To -Force | Out-Null
    Write-Host "Mise a jour de l'installation existante : $To" -ForegroundColor Yellow
    Write-InstallLog "Mise a jour depuis $From vers $To"

    # Seuls les dossiers de code sont remplaces. Les dossiers utilisateur
    # (.venv, data, inbox, out, models, work, logs, tools, assets, prompts)
    # ne sont jamais supprimes pendant une mise a jour.
    foreach ($directoryName in @('studio', 'installer', 'docs')) {
        $sourceDirectory = Join-Path $From $directoryName
        if (Test-Path -LiteralPath $sourceDirectory -PathType Container) {
            $destinationDirectory = Join-Path $To $directoryName
            if (Test-Path -LiteralPath $destinationDirectory) {
                Remove-Item -LiteralPath $destinationDirectory -Recurse -Force
            }
            Copy-Item -LiteralPath $sourceDirectory -Destination $To -Recurse -Force
        }
    }

    $rootFiles = @(
        'INSTALL.bat', 'UPDATE-FROM-ARCHIVE.bat', 'REPAIR.bat',
        'START-STUDIO.bat', 'START-STUDIO.vbs', 'STOP-STUDIO.bat',
        'pyproject.toml', 'requirements.txt', '.gitignore',
        'README.md', 'GUIDE_INSTALLATION_FR.md', 'LIRE-MOI-DABORD.txt',
        'config.yaml.default', 'VERSION.txt'
    )
    foreach ($fileName in $rootFiles) {
        $sourceFile = Join-Path $From $fileName
        if (Test-Path -LiteralPath $sourceFile -PathType Leaf) {
            Copy-Item -LiteralPath $sourceFile -Destination (Join-Path $To $fileName) -Force
        }
    }

    # Les fichiers de prompt par defaut sont mis a jour, mais les prompts actifs
    # et personnalisables restent inchanges.
    $sourcePrompts = Join-Path $From 'prompts'
    $destinationPrompts = Join-Path $To 'prompts'
    New-Item -ItemType Directory -Path $destinationPrompts -Force | Out-Null
    if (Test-Path -LiteralPath $sourcePrompts -PathType Container) {
        Get-ChildItem -LiteralPath $sourcePrompts -Filter '*.default.txt' -File | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $destinationPrompts $_.Name) -Force
        }
    }

    $sfxDirectory = Join-Path $To 'assets\sfx'
    New-Item -ItemType Directory -Path $sfxDirectory -Force | Out-Null
    $sourceWhoosh = Join-Path $From 'assets\sfx\soft_whoosh.wav'
    $targetWhoosh = Join-Path $sfxDirectory 'soft_whoosh.wav'
    if ((Test-Path -LiteralPath $sourceWhoosh -PathType Leaf) -and -not (Test-Path -LiteralPath $targetWhoosh -PathType Leaf)) {
        Copy-Item -LiteralPath $sourceWhoosh -Destination $targetWhoosh
        Write-InstallLog 'Effet whoosh original ajoute.'
    }

    $fontsDirectory = Join-Path $To 'assets\fonts'
    New-Item -ItemType Directory -Path $fontsDirectory -Force | Out-Null
    $sourceFontsReadme = Join-Path $From 'assets\fonts\README.txt'
    $targetFontsReadme = Join-Path $fontsDirectory 'README.txt'
    if ((Test-Path -LiteralPath $sourceFontsReadme -PathType Leaf) -and -not (Test-Path -LiteralPath $targetFontsReadme)) {
        Copy-Item -LiteralPath $sourceFontsReadme -Destination $targetFontsReadme
    }
}

function Initialize-ProjectFiles {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'config.yaml') -PathType Leaf)) {
        $template = Join-Path $ProjectRoot 'config.yaml.default'
        if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
            throw 'Le fichier de configuration manque : config.yaml.default est introuvable.'
        }
        Copy-Item -LiteralPath $template -Destination (Join-Path $ProjectRoot 'config.yaml')
        Write-InstallLog 'Configuration initiale creee depuis config.yaml.default.'
    }

    $promptsDirectory = Join-Path $ProjectRoot 'prompts'
    New-Item -ItemType Directory -Path $promptsDirectory -Force | Out-Null
    foreach ($defaultPrompt in (Get-ChildItem -LiteralPath $promptsDirectory -Filter '*.default.txt' -File -ErrorAction SilentlyContinue)) {
        $activeName = $defaultPrompt.Name -replace '\.default\.txt$', '.txt'
        $activePath = Join-Path $promptsDirectory $activeName
        if (-not (Test-Path -LiteralPath $activePath -PathType Leaf)) {
            Copy-Item -LiteralPath $defaultPrompt.FullName -Destination $activePath
        }
    }

    foreach ($relativeDirectory in @(
        'logs', 'data', 'inbox\shorts', 'out\shorts', 'models\whisper', 'tools\whisper.cpp', 'work\tmp',
        '.install-state', 'assets\fonts'
    )) {
        New-Item -ItemType Directory -Path (Join-Path $ProjectRoot $relativeDirectory) -Force | Out-Null
    }
}

function Get-DependencyFingerprint {
    $requirementsFile = Join-Path $ProjectRoot 'requirements.txt'
    $pyprojectFile = Join-Path $ProjectRoot 'pyproject.toml'
    foreach ($manifest in @($requirementsFile, $pyprojectFile)) {
        if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
            throw "Manifeste de dependances absent : $manifest"
        }
    }
    $requirementsHash = (Get-FileHash -LiteralPath $requirementsFile -Algorithm SHA256).Hash
    $pyprojectHash = (Get-FileHash -LiteralPath $pyprojectFile -Algorithm SHA256).Hash
    return ($requirementsHash + ':' + $pyprojectHash).ToLowerInvariant()
}

function Test-PythonRuntime {
    param([Parameter(Mandatory = $true)][string]$PythonExe)
    $checkScript = Join-Path $ProjectRoot 'installer\check_runtime.py'
    if (-not (Test-Path -LiteralPath $checkScript -PathType Leaf)) {
        Write-InstallLog 'Le script de verification Python check_runtime.py est absent.'
        return $false
    }
    $output = & $PythonExe $checkScript 2>&1
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) {
        $message = [string]$line
        Write-Host $message
        Write-InstallLog "Smoke test runtime: $message"
    }
    return ($exitCode -eq 0)
}

function Test-PipConsistency {
    param([Parameter(Mandatory = $true)][string]$PythonExe)
    & $PythonExe -m pip check
    return ($LASTEXITCODE -eq 0)
}

function Install-OrReuseDependencies {
    param([Parameter(Mandatory = $true)][string]$PythonExe)

    $fingerprint = Get-DependencyFingerprint
    $stampPath = Join-Path $ProjectRoot '.install-state\requirements.sha256'
    $oldFingerprint = ''
    if (Test-Path -LiteralPath $stampPath -PathType Leaf) {
        $oldFingerprint = (Get-Content -LiteralPath $stampPath -Raw -ErrorAction SilentlyContinue).Trim()
    }

    if ($oldFingerprint -eq $fingerprint) {
        Write-Step 'Verification des dependances runtime existantes'
        if ((Test-PipConsistency -PythonExe $PythonExe) -and (Test-PythonRuntime -PythonExe $PythonExe)) {
            Write-Host 'Environnement runtime deja present et verifie : aucun telechargement Python.' -ForegroundColor Green
            Write-InstallLog 'Dependances runtime reutilisees : empreinte, pip check et imports valides.'
            return
        }
    }

    Write-Step 'Installation incrementale des dependances runtime'
    Write-Host 'Seules les dependances de production sont installees. Les outils pytest restent dans la CI.' -ForegroundColor Gray
    $cacheResult = & $PythonExe -m pip cache dir 2>$null
    if ($LASTEXITCODE -eq 0 -and $cacheResult) {
        Write-InstallLog "Cache pip reutilise : $($cacheResult | Select-Object -Last 1)"
    }

    & $PythonExe -m pip install --disable-pip-version-check --prefer-binary -e .
    if ($LASTEXITCODE -ne 0) {
        throw 'Installation des dependances runtime echouee. Verifie la connexion Internet et consulte logs\install.log.'
    }
    if (-not (Test-PipConsistency -PythonExe $PythonExe)) {
        throw 'pip check detecte des dependances Python incoherentes. Consulte logs\install.log.'
    }
    if (-not (Test-PythonRuntime -PythonExe $PythonExe)) {
        throw 'Le smoke test runtime a echoue apres installation. Consulte logs\install.log.'
    }

    Set-Content -LiteralPath $stampPath -Value $fingerprint -Encoding ASCII
    Write-InstallLog 'Dependances runtime verifiees et empreinte enregistree.'
}

function New-DesktopShortcut {
    param([Parameter(Mandatory = $true)][string]$Root)
    $desktop = [Environment]::GetFolderPath('DesktopDirectory')
    if ([string]::IsNullOrWhiteSpace($desktop)) {
        $desktop = Join-Path $env:USERPROFILE 'Desktop'
    }
    New-Item -ItemType Directory -Path $desktop -Force | Out-Null

    $startVbs = Join-Path $Root 'START-STUDIO.vbs'
    $iconFile = Join-Path $Root 'assets\gta-ranked-studio.ico'
    $shortcutPath = Join-Path $desktop 'GTA Ranked Studio.lnk'

    try {
        $wsh = New-Object -ComObject WScript.Shell
        $shortcut = $wsh.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\wscript.exe'
        $shortcut.Arguments = '"' + $startVbs + '"'
        $shortcut.WorkingDirectory = $Root
        if (Test-Path -LiteralPath $iconFile -PathType Leaf) {
            $shortcut.IconLocation = $iconFile
        }
        $shortcut.Description = 'Ouvrir GTA Ranked Studio sur ce PC'
        $shortcut.Save()
        return $shortcutPath
    }
    catch {
        $fallback = Join-Path $desktop 'GTA Ranked Studio.bat'
        $pythonw = Join-Path $Root '.venv\Scripts\pythonw.exe'
        $rootForBatch = $Root.Replace('"', '""')
        $pythonwForBatch = $pythonw.Replace('"', '""')
        $launcherLines = @(
            '@echo off',
            'setlocal',
            ('cd /d "' + $rootForBatch + '"'),
            ('start "" "' + $pythonwForBatch + '" -m studio.desktop_launcher')
        )
        Set-Content -LiteralPath $fallback -Value $launcherLines -Encoding ASCII
        Write-Warning "Le raccourci .lnk n'a pas pu etre cree. Un raccourci .bat est disponible : $fallback"
        Write-InstallLog "Creation .lnk impossible : $($_.Exception.Message)"
        return $fallback
    }
}

try {
    $installerDirectory = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($installerDirectory)) {
        $installerDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    $sourceItem = Get-Item -LiteralPath (Join-Path $installerDirectory '..') -ErrorAction Stop
    if (-not $sourceItem.PSIsContainer) {
        throw 'Le dossier parent de installer/ est introuvable.'
    }
    $SourceRoot = $sourceItem.FullName
    $ProjectRoot = $SourceRoot

    $localAppData = [Environment]::GetFolderPath('LocalApplicationData')
    $GlobalInstallDir = Join-Path $localAppData 'GTA Ranked Studio'
    $InstallPointer = Join-Path $GlobalInstallDir 'install-location.txt'
    if (Test-Path -LiteralPath $InstallPointer -PathType Leaf) {
        $existingLocation = (Get-Content -LiteralPath $InstallPointer -Raw -ErrorAction SilentlyContinue).Trim()
        if (-not [string]::IsNullOrWhiteSpace($existingLocation) -and (Test-Path -LiteralPath $existingLocation -PathType Container)) {
            $existingItem = Get-Item -LiteralPath $existingLocation -ErrorAction Stop
            if (Test-Path -LiteralPath (Join-Path $existingItem.FullName 'config.yaml') -PathType Leaf) {
                $ProjectRoot = $existingItem.FullName
            }
        }
    }

    if ($ProjectRoot -ine $SourceRoot) {
        Copy-ApplicationUpdate -From $SourceRoot -To $ProjectRoot
    }

    Set-Location -LiteralPath $ProjectRoot
    $logDirectory = Join-Path $ProjectRoot 'logs'
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $InstallLog = Join-Path $logDirectory 'install.log'
    Write-InstallLog "Debut installation. Source: $SourceRoot | Installation: $ProjectRoot"

    Write-Host '============================================================' -ForegroundColor Yellow
    Write-Host 'GTA RANKED STUDIO - INSTALLATION / MISE A JOUR' -ForegroundColor Yellow
    Write-Host '============================================================' -ForegroundColor Yellow
    Write-Host "Dossier de l'application : $ProjectRoot"
    if ($ProjectRoot -ieq $SourceRoot) {
        Write-Host 'Premiere installation ou installation dans le dossier courant.' -ForegroundColor Gray
    }
    else {
        Write-Host 'Installation existante detectee : les donnees et dependances sont conservees.' -ForegroundColor Green
    }

    Initialize-ProjectFiles

    Write-Step 'Verification de Python 3.11 (64 bits)'
    $pythonInfo = Get-Python311
    if (-not $pythonInfo) {
        Write-Host 'Python 3.11 est absent. Installation via WinGet...' -ForegroundColor Yellow
        $winget = Ensure-WinGet
        & $winget install --exact --id Python.Python.3.11 --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
        $pythonExitCode = $LASTEXITCODE
        Write-InstallLog "WinGet Python exit code: $pythonExitCode"
        if ($pythonExitCode -ne 0) {
            throw "L'installation de Python 3.11 par WinGet a echoue (code $pythonExitCode). Installe Python 3.11 64 bits depuis python.org puis relance INSTALL.bat."
        }
        $pythonInfo = Get-Python311
    }
    if (-not $pythonInfo) {
        throw 'Python 3.11 64 bits est installe mais non detectable. Ferme puis rouvre ta session Windows et relance INSTALL.bat.'
    }
    Write-Host "Python detecte : $($pythonInfo.Exe)" -ForegroundColor Green
    Write-InstallLog "Python detecte: $($pythonInfo.Exe)"

    Write-Step 'Verification de FFmpeg et FFprobe'
    $media = Ensure-Ffmpeg
    Write-Host "FFmpeg : $($media.Ffmpeg)" -ForegroundColor Green
    Write-Host "FFprobe : $($media.Ffprobe)" -ForegroundColor Green

    Write-Step "Creation ou reutilisation de l environnement Python"
    $venvPath = Join-Path $ProjectRoot '.venv'
    $venvPython = Join-Path $venvPath 'Scripts\python.exe'
    $venvPythonw = Join-Path $venvPath 'Scripts\pythonw.exe'
    $validVenv = $false
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        $venvVersionCheck = Join-Path $ProjectRoot 'installer\check_python.py'
        & $venvPython $venvVersionCheck *> $null
        $validVenv = ($LASTEXITCODE -eq 0) -and (Test-Path -LiteralPath $venvPythonw -PathType Leaf)
    }
    if (-not $validVenv) {
        if (Test-Path -LiteralPath $venvPath) {
            Write-Host 'Environnement Python absent ou incompatible : recreation du seul .venv.' -ForegroundColor Yellow
            Remove-Item -LiteralPath $venvPath -Recurse -Force
        }
        $venvArguments = @()
        if ($pythonInfo.Prefix -and $pythonInfo.Prefix.Count -gt 0) {
            $venvArguments += $pythonInfo.Prefix
        }
        $venvArguments += @('-m', 'venv', $venvPath)
        & $pythonInfo.Exe @venvArguments
        if ($LASTEXITCODE -ne 0) {
            throw 'Impossible de creer l environnement Python (.venv).'
        }
    }
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf) -or -not (Test-Path -LiteralPath $venvPythonw -PathType Leaf)) {
        throw 'L environnement Python est incomplet : python.exe ou pythonw.exe est absent.'
    }

    Install-OrReuseDependencies -PythonExe $venvPython

    Write-Step 'Diagnostic local'
    & $venvPython -m studio doctor
    $doctorExitCode = $LASTEXITCODE
    if ($doctorExitCode -ne 0) {
        Write-Warning 'Le diagnostic signale un composant a verifier. Le rapport est dans logs\doctor-report.json.'
    }

    Write-Step 'Creation ou mise a jour du raccourci Bureau'
    $shortcutPath = New-DesktopShortcut -Root $ProjectRoot

    $report = [ordered]@{
        installed_at = (Get-Date).ToString('o')
        project_root = $ProjectRoot
        source_root = $SourceRoot
        python = $pythonInfo.Exe
        python_version = '3.11 x64'
        ffmpeg = $media.Ffmpeg
        ffprobe = $media.Ffprobe
        shortcut = $shortcutPath
        dependencies_reused = (Test-Path -LiteralPath (Join-Path $ProjectRoot '.install-state\requirements.sha256'))
        runtime_check_passed = $true
        doctor_exit_code = $doctorExitCode
    }
    $reportPath = Join-Path $ProjectRoot 'logs\installation-report.json'
    $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $reportPath -Encoding UTF8

    New-Item -ItemType Directory -Path $GlobalInstallDir -Force | Out-Null
    Set-Content -LiteralPath $InstallPointer -Value $ProjectRoot -Encoding UTF8
    Write-InstallLog 'Installation terminee avec succes. Emplacement enregistre pour les prochaines mises a jour.'

    Write-Host ''
    Write-Host 'INSTALLATION TERMINEE.' -ForegroundColor Green
    Write-Host "Raccourci : $shortcutPath"
    Write-Host "Rapport : $reportPath"
    Write-Host 'Les prochaines mises a jour reutiliseront ce dossier, le .venv et tes donnees.' -ForegroundColor Green
    Write-Host 'Double-clique sur GTA Ranked Studio sur le Bureau pour ouvrir le site.' -ForegroundColor Green
    exit 0
}
catch {
    $message = $_.Exception.Message
    Write-Host ''
    Write-Host 'INSTALLATION INTERROMPUE' -ForegroundColor Red
    Write-Host $message -ForegroundColor Red
    Write-Host 'Aucun dossier utilisateur (data, inbox, out, models, logs) n a ete supprime.' -ForegroundColor Yellow
    if (-not [string]::IsNullOrWhiteSpace($InstallLog)) {
        Write-InstallLog "ECHEC: $message"
        Write-Host "Journal : $InstallLog"
    }
    exit 1
}
