"""Vérifie que les versions futures se mettent à jour sans dupliquer les données."""

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_dependency_manifest_covers_project_runtime_and_dev_dependencies() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = metadata["project"].get("dependencies", []) + metadata["project"].get("optional-dependencies", {}).get("dev", [])
    requirement_lines = {
        line.strip().lower()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    for dependency in declared:
        assert dependency.strip().lower() in requirement_lines, (
            f"La dépendance {dependency} doit figurer à l'identique dans requirements.txt "
            "pour invalider correctement le cache si sa contrainte change."
        )


def test_default_configuration_and_prompts_exist_for_first_install() -> None:
    assert (ROOT / "config.yaml.default").is_file()
    assert (ROOT / "prompts" / "short_metadata.default.txt").is_file()
    assert (ROOT / "prompts" / "bestof_metadata.default.txt").is_file()


def test_local_user_data_is_not_part_of_the_dependency_manifest() -> None:
    manifest = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "sqlite" not in manifest
    assert "whisper model" not in manifest
    assert "ollama model" not in manifest


def test_update_marker_is_documented() -> None:
    script = (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8-sig")
    assert "install-location.txt" in script
    assert "Copy-ApplicationUpdate" in script


def test_v025_environment_is_migrated_incrementally_without_reinstalling_all_dependencies() -> None:
    import hashlib

    legacy_v025_fingerprint = "7baf73c0b67162ca6c5f30e6e3ba9341f32ea2010934120f4acd73cbcb1f21d0"
    actual_fingerprint = hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest()
    installer = (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8-sig")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()

    assert actual_fingerprint != legacy_v025_fingerprint
    assert legacy_v025_fingerprint in installer
    assert "knownV025Fingerprint" in installer
    assert "canMigrateV025Environment" in installer
    assert "httpx2>=2.16.2,<3" in requirements
    assert "pip install --disable-pip-version-check --prefer-binary 'httpx2>=2.16.2,<3'" in installer
    assert "if ($canSkipInstall)" in installer
    assert "aucun telechargement Python" in installer


def test_archive_update_helper_is_shipped_and_preserves_active_files() -> None:
    updater = (ROOT / "installer" / "update_from_archive.ps1").read_text(encoding="utf-8-sig")
    check_script = (ROOT / "installer" / "check-script.ps1").read_text(encoding="utf-8-sig")
    installer = (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8-sig")
    batch = (ROOT / "UPDATE-FROM-ARCHIVE.bat").read_text(encoding="utf-8")

    assert "update_from_archive.ps1" in check_script
    assert "UPDATE-FROM-ARCHIVE.bat" in installer
    assert "update_from_archive.ps1" in batch
    assert "'config.yaml'" not in updater.split("$rootFiles = @(", 1)[1].split(")", 1)[0]
    assert "*.default.txt" in updater
    assert "foreach ($directoryName in @('studio', 'installer', 'tests'))" in updater
    assert "install-location.txt" in updater



def test_update_adds_default_whoosh_asset_without_overwriting_existing_user_asset() -> None:
    updater = (ROOT / "installer" / "update_from_archive.ps1").read_text(encoding="utf-8-sig")
    installer = (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8-sig")
    assert "assets\\sfx\\soft_whoosh.wav" in updater
    assert "-not (Test-Path -LiteralPath $targetWhoosh -PathType Leaf)" in updater
    assert "assets\\sfx\\soft_whoosh.wav" in installer
    assert "-not (Test-Path -LiteralPath $targetWhoosh -PathType Leaf)" in installer
