"""Vérifie les invariants d'installation, de compatibilité et de dépendances."""
from pathlib import Path
import tomllib
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_and_development_dependency_groups_are_separate() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = {line.lower() for line in metadata["project"]["dependencies"]}
    dev = {line.lower() for line in metadata["project"]["optional-dependencies"]["dev"]}
    requirements = {
        line.strip().lower()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert requirements == runtime
    assert all(line not in requirements for line in dev)
    assert any(line.startswith("pytest") for line in dev)


def test_default_configuration_contains_only_the_short_workflow() -> None:
    config = yaml.safe_load((ROOT / "config.yaml.default").read_text(encoding="utf-8"))
    paths = config["paths"]
    assert "inbox_shorts" in paths and "output_shorts" in paths
    assert not {"inbox_bestof", "inbox_urls", "output_bestof", "output_log_csv"} & set(paths)
    assert "timezone" not in config["app"]
    assert "yt_dlp" not in config["executables"]
    assert "bestof" not in config
    assert "scoring" not in config
    assert (ROOT / "prompts" / "short_metadata.default.txt").is_file()
    assert not (ROOT / "prompts" / "bestof_metadata.default.txt").exists()

    assert "output_language" not in config["app"]
    assert not {
        "gpu_vendor", "video_encoder",
        "video_encoder_fallback", "transcription_backend", "ollama_backend",
    } & set(config["hardware"])
    assert not {"model_name", "word_timestamps", "vad_enabled"} & set(config["transcription"])
    assert not {
        "channel_name", "primary_color", "secondary_color",
        "text_color", "day_badge_enabled",
    } & set(config["branding"])
    assert not {
        "default_crop_y", "brand_overlay_enabled", "hook_max_words",
        "hook_duration_seconds", "context_max_words", "context_duration_seconds",
        "punch_in_enabled", "punch_in_percent",
    } & set(config["shorts"])
    assert not {"amf_quality", "software_crf", "preset"} & set(config["encoding"])


def test_user_data_is_not_part_of_the_runtime_dependency_manifest() -> None:
    manifest = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert all(term not in manifest for term in ("sqlite", "whisper model", "ollama model", "pytest", "httpx"))


def test_update_marker_and_legacy_compatibility_remain_available() -> None:
    installer = (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8-sig")
    legacy = (ROOT / "installer" / "update_from_archive.ps1").read_text(encoding="utf-8-sig")
    assert "install-location.txt" in installer
    assert "Copy-ApplicationUpdate" in installer
    assert "$targetVersion -lt [version]'0.2.6'" in legacy
    assert "if ($targetVersion -gt $sourceVersion)" in legacy
    assert "if ($targetVersion -ge $sourceVersion)" not in legacy
    assert "reapplication de cette version en mode reparation" in legacy
    assert "UPDATE-FROM-ARCHIVE.bat" in legacy or (ROOT / "UPDATE-FROM-ARCHIVE.bat").is_file()


def test_user_install_does_not_install_dev_tools_or_run_the_full_test_suite() -> None:
    installer = (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8-sig")
    assert "pip install --disable-pip-version-check --prefer-binary -e ." in installer
    assert ".[dev]" not in installer
    assert "-m pytest" not in installer
    assert "Test-PipConsistency" in installer
    assert "Test-PythonRuntime" in installer
    assert "requirements.sha256" in installer
    assert "pyproject.toml" in installer.split("function Get-DependencyFingerprint",1)[1].split("function ",1)[0]


def test_application_update_preserves_user_data_and_updates_canonical_docs() -> None:
    installer = (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8-sig")
    updater = (ROOT / "installer" / "apply_update.ps1").read_text(encoding="utf-8-sig")
    for script in (installer, updater):
        assert "'config.yaml'" not in script.split("$rootFiles = @(",1)[1].split(")",1)[0]
        assert "prompts actifs" in script or "prompts" in script
    assert "foreach ($directoryName in @('studio', 'installer', 'docs'))" in installer
    assert "foreach ($directoryName in @('studio', 'installer', 'docs'))" in updater
    assert r"work\updates\rollback-" in updater


def test_update_adds_default_whoosh_asset_without_overwriting_existing_asset() -> None:
    installer = (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8-sig")
    updater = (ROOT / "installer" / "update_from_archive.ps1").read_text(encoding="utf-8-sig")
    assert r"assets\sfx\soft_whoosh.wav" in installer
    assert r"assets\sfx\soft_whoosh.wav" in updater
    assert "-not (Test-Path -LiteralPath $targetWhoosh" in installer
    assert "-not (Test-Path -LiteralPath $targetWhoosh" in updater
