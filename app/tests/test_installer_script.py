"""Tests de non-régression pour l'installateur Windows PowerShell."""

from pathlib import Path
import shutil
import subprocess

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = PROJECT_ROOT / "installer" / "install.ps1"
INSTALL_BATCH = PROJECT_ROOT / "INSTALL.bat"
REPAIR_BATCH = PROJECT_ROOT / "REPAIR.bat"
CHECK_SCRIPT = PROJECT_ROOT / "installer" / "check-script.ps1"
UPDATER_SCRIPT = PROJECT_ROOT / "installer" / "update_from_archive.ps1"
UPDATE_BATCH = PROJECT_ROOT / "UPDATE-FROM-ARCHIVE.bat"
RUNTIME_CHECK = PROJECT_ROOT / "installer" / "check_runtime.py"


def test_installer_uses_utf8_bom_and_windows_line_endings() -> None:
    raw = INSTALL_SCRIPT.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "PowerShell 5.1 attend le BOM UTF-8."
    text = raw.decode("utf-8-sig")
    assert "\r\n" in text, "Le script doit utiliser des fins de ligne Windows CRLF."
    assert "\n" not in text.replace("\r\n", ""), "Aucune fin de ligne isolée LF ne doit subsister."


def test_project_root_is_derived_from_script_location() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "$installerDirectory = $PSScriptRoot" in script
    assert "Join-Path $installerDirectory '..'" in script
    assert "$SourceRoot = $sourceItem.FullName" in script
    assert "GetFullPath" not in script


def test_batch_files_call_syntax_check_without_path_arguments() -> None:
    for batch_file in (INSTALL_BATCH, REPAIR_BATCH):
        text = batch_file.read_text(encoding="utf-8")
        assert ' -File "%~dp0installer\\check-script.ps1"' in text
        assert ' -File "%~dp0installer\\install.ps1"' in text
        assert "-ProjectRoot" not in text


def test_installer_uses_runtime_check_script_instead_of_python_c_quoting() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "installer\\check_runtime.py" in script
    assert "& $PythonExe $checkScript" in script
    assert " -c " not in script
    assert "-c'" not in script
    assert "Verification de FastAPI TestClient / HTTPX" not in script
    assert "print(\"FastAPI TestClient" not in script
    assert RUNTIME_CHECK.is_file()


def test_runtime_check_script_exercises_testclient() -> None:
    script = RUNTIME_CHECK.read_text(encoding="utf-8")
    assert "from fastapi.testclient import TestClient" in script
    assert "import httpx2" in script
    assert "import httpx" in script  # fallback for older Starlette versions
    assert "client.get(\"/health\")" in script
    assert "reconfigure(encoding=\"utf-8\", errors=\"replace\")" in script
    assert "GTA_RS_RUNTIME_CHECK_OK" in script
    assert "Using `httpx` with `starlette.testclient` is deprecated" in script


def test_installer_reuses_existing_virtualenv_and_dependency_stamp() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "requirements.sha256" in script
    assert "knownV025Fingerprint" in script
    assert "canMigrateV025Environment" in script
    assert "httpx2>=2.16.2,<3" in script
    assert "Test-PipConsistency" in script
    assert "Test-PythonRuntime" in script
    assert "requirements.sha256" in script
    assert "knownV025Fingerprint" in script
    assert "canMigrateV025Environment" in script
    assert "httpx2>=2.16.2,<3" in script
    assert "Dependances deja presentes et verifiees : aucun telechargement Python." in script
    assert "Remove-Item -LiteralPath $venvPath" in script  # uniquement si venv invalide
    assert "pip install --disable-pip-version-check --prefer-binary -e '.[dev]'" in script
    assert "--upgrade pip" not in script


def test_installer_updates_existing_location_without_removing_user_data() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "install-location.txt" in script
    assert "Copy-ApplicationUpdate -From $SourceRoot -To $ProjectRoot" in script
    assert "foreach ($directoryName in @('studio', 'installer', 'tests'))" in script
    assert "data, inbox, out, models, work, logs, tools, assets, prompts" in script
    assert "Set-Content -LiteralPath $InstallPointer" in script
    assert "New-Item -ItemType Directory -Path $GlobalInstallDir -Force" in script


def test_ffmpeg_is_not_reinstalled_when_both_binaries_exist() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "if ($ffmpeg -and $ffprobe)" in script
    assert "FFmpeg deja disponible" in script


def test_active_config_and_prompts_are_not_overwritten_in_update_archive() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'config.yaml')" in script
    assert "if (-not (Test-Path -LiteralPath $activePath -PathType Leaf))" in script


def test_powershell_parser_accepts_installer_on_windows() -> None:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("Windows PowerShell n'est pas disponible dans cet environnement de test.")
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(CHECK_SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_powershell_scripts_have_balanced_quotes() -> None:
    for script_path in (INSTALL_SCRIPT, CHECK_SCRIPT, UPDATER_SCRIPT):
        text = script_path.read_text(encoding="utf-8-sig")
        assert not any(char in text for char in "\u2018\u2019\u201c\u201d")
        in_block_comment = False
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if in_block_comment:
                if "#>" in line:
                    in_block_comment = False
                continue
            if stripped.startswith("<#"):
                if "#>" not in stripped[2:]:
                    in_block_comment = True
                continue
            quote = None
            index = 0
            while index < len(line):
                char = line[index]
                if quote == "'":
                    if char == "'":
                        if index + 1 < len(line) and line[index + 1] == "'":
                            index += 2
                            continue
                        quote = None
                elif quote == '"':
                    if char == "`":
                        index += 2
                        continue
                    if char == '"':
                        quote = None
                else:
                    if char == "#":
                        break
                    if char in ("'", '"'):
                        quote = char
                index += 1
            assert quote is None, f"Chaîne PowerShell non terminée dans {script_path.name}, ligne {line_number}: {line}"


def test_update_helper_uses_a_path_safe_windows_launcher() -> None:
    batch = UPDATE_BATCH.read_text(encoding="utf-8")
    script = UPDATER_SCRIPT.read_text(encoding="utf-8-sig")
    assert '-File "%~dp0installer\\check-script.ps1"' in batch
    assert '-File "%~dp0installer\\update_from_archive.ps1"' in batch
    assert "Get-Item -LiteralPath (Join-Path $PSScriptRoot '..')" in script
    assert "Read-Host 'Dossier existant'" in script
    assert "Get-AppVersion -Root $sourceRoot" in script
    assert "Get-AppVersion -Root $remembered" in script
    assert "$sourceVersion -lt [version]'0.3.3'" in script
    assert "$targetVersion -lt [version]'0.2.6'" in script
    assert "Set-Content -LiteralPath $pointer -Value $targetRoot -Encoding UTF8" in script
    assert "check-script.ps1" in script
    assert "install.ps1" in script


def test_update_helper_preserves_environment_configuration_prompts_and_user_data() -> None:
    script = UPDATER_SCRIPT.read_text(encoding="utf-8-sig")
    root_files = script.split("$rootFiles = @(", 1)[1].split(")", 1)[0]
    directory_list = script.split("foreach ($directoryName in @(", 1)[1].split("))", 1)[0]
    assert all(f"'{name}'" in directory_list for name in ("studio", "installer", "tests"))
    assert "'config.yaml'" not in root_files
    assert "'requirements.txt'" in root_files
    assert "'VERSION.txt'" in root_files
    assert "-Filter '*.default.txt'" in script
    assert ".venv, config.yaml, prompts actifs" in script
    assert "data, inbox, out, models, logs, work et tools" in script
    assert "Remove-Item -LiteralPath $destinationDirectory" in script
    assert "Remove-Item -LiteralPath $targetRoot" not in script


def test_update_helper_has_windows_compatible_encoding_and_line_endings() -> None:
    raw = UPDATER_SCRIPT.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert "\r\n" in text
    assert "\n" not in text.replace("\r\n", "")
    batch = UPDATE_BATCH.read_bytes()
    assert b"\n" not in batch.replace(b"\r\n", b"")


def test_v033_update_archive_includes_whisper_diagnostics() -> None:
    script = UPDATER_SCRIPT.read_text(encoding="utf-8-sig")
    assert "$sourceVersion -lt [version]'0.3.3'" in script
    assert "foreach ($directoryName in @('studio', 'installer', 'tests'))" in script
    assert "'VERSION.txt'" in script
    assert "'GUIDE_INSTALLATION_FR.md'" in script
    assert "Get-ChildItem -LiteralPath $sourcePrompts -Filter '*.default.txt'" in script
    assert "data, inbox, out, models, logs, work et tools (ainsi que assets)." in script


def test_install_script_updates_v032_release_notes_when_updating_from_archive() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "'NOTES-v0.3.2.txt'" in script
    assert "'VERIFICATION-v0.3.2.md'" in script
    assert "'NOTES-v0.2.6.txt'" not in script


def test_update_helper_accepts_four_component_version_numbers() -> None:
    script = UPDATER_SCRIPT.read_text(encoding="utf-8-sig")
    assert r"(\d+\.\d+\.\d+(?:\.\d+)?)" in script
