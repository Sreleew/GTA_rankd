"""Tests de non-régression pour l'installation et le package Windows."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = ROOT / "installer" / "install.ps1"
INSTALL_BATCH = ROOT / "INSTALL.bat"
REPAIR_BATCH = ROOT / "REPAIR.bat"
CHECK_SCRIPT = ROOT / "installer" / "check-script.ps1"
APPLY_SCRIPT = ROOT / "installer" / "apply_update.ps1"
LEGACY_SCRIPT = ROOT / "installer" / "update_from_archive.ps1"
UPDATE_BATCH = ROOT / "UPDATE-FROM-ARCHIVE.bat"
RUNTIME_CHECK = ROOT / "installer" / "check_runtime.py"


def test_powershell_scripts_use_utf8_bom_and_windows_line_endings() -> None:
    for path in (INSTALL_SCRIPT, CHECK_SCRIPT, APPLY_SCRIPT, LEGACY_SCRIPT):
        raw = path.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf"), path.name
        text = raw.decode("utf-8-sig")
        assert "\r\n" in text
        assert "\n" not in text.replace("\r\n", "")


def test_batch_files_call_the_shared_syntax_check() -> None:
    for path in (INSTALL_BATCH, REPAIR_BATCH):
        text = path.read_text(encoding="utf-8")
        assert ' -File "%~dp0installer\\check-script.ps1"' in text
        assert ' -File "%~dp0installer\\install.ps1"' in text


def test_runtime_smoke_check_uses_only_production_packages() -> None:
    script = RUNTIME_CHECK.read_text(encoding="utf-8")
    assert "GTA_RS_RUNTIME_CHECK_OK" in script
    assert "studio.web.app" in script
    assert "studio.web.worker" in script
    assert "import pytest" not in script
    assert "import httpx" not in script
    assert "TestClient" not in script
    assert "watchdog" not in script


def test_user_installer_does_not_run_pytest_or_install_dev_extra() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "pip install --disable-pip-version-check --prefer-binary -e ." in script
    assert ".[dev]" not in script
    assert "-m pytest" not in script
    assert "Test-PipConsistency" in script
    assert "Test-PythonRuntime" in script
    assert '$output = & $PythonExe $checkScript 2>&1' in script
    assert 'Write-InstallLog "Smoke test runtime: $message"' in script
    assert "requirements.sha256" in script


def test_installation_updates_only_app_code_and_canonical_docs() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "foreach ($directoryName in @('studio', 'installer', 'docs'))" in script
    root_files = script.split("$rootFiles = @(", 1)[1].split(")", 1)[0]
    assert "NOTES-v0." not in root_files
    assert "VERIFICATION-v" not in root_files
    assert "README_M0.txt" not in root_files
    assert "'config.yaml'" not in root_files
    assert "Copy-ApplicationUpdate -From $SourceRoot -To $ProjectRoot" in script


def test_update_package_applies_rollback_and_replaces_docs_not_tests() -> None:
    script = APPLY_SCRIPT.read_text(encoding="utf-8-sig")
    assert r"work\updates\rollback-" in script
    assert "foreach ($directoryName in @('studio', 'installer', 'docs'))" in script
    assert "'tests'" not in script.split("$rootFiles = @(",1)[1].split(")",1)[0]


def test_old_install_migration_remains_available_but_has_no_release_note_list() -> None:
    script = LEGACY_SCRIPT.read_text(encoding="utf-8-sig")
    assert "$targetVersion -lt [version]'0.2.6'" in script
    assert "'config.yaml'" not in script.split("$rootFiles = @(",1)[1].split(")",1)[0]
    root_files = script.split("$rootFiles = @(",1)[1].split(")",1)[0]
    assert "NOTES-v0." not in root_files
    assert "VERIFICATION-v" not in root_files
    assert "foreach ($directoryName in @('studio', 'installer', 'docs'))" in script


def test_all_critical_powershell_scripts_are_syntax_checked() -> None:
    check = CHECK_SCRIPT.read_text(encoding="utf-8-sig")
    for filename in ("install.ps1", "apply_update.ps1", "update_from_archive.ps1"):
        assert filename in check



def test_powershell_scripts_have_balanced_quotes_on_all_runners() -> None:
    for script_path in (INSTALL_SCRIPT, CHECK_SCRIPT, APPLY_SCRIPT, LEGACY_SCRIPT):
        source = script_path.read_text(encoding="utf-8-sig")
        assert not any(char in source for char in "\u2018\u2019\u201c\u201d")
        in_block_comment = False
        for line_number, line in enumerate(source.splitlines(), start=1):
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
            assert quote is None, (
                f"Chaîne PowerShell non terminée dans {script_path.name}, "
                f"ligne {line_number}: {line}"
            )


def test_powershell_parser_accepts_all_scripts_on_windows() -> None:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("Windows PowerShell n'est pas disponible dans cet environnement de test.")
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(CHECK_SCRIPT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, timeout=30,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
