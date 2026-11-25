from pathlib import Path

import pytest

from studio.config import ConfigError, load_config


def test_loads_project_config():
    project_root = Path(__file__).resolve().parents[1]
    config = load_config(project_root / "config.yaml")

    assert config.get("app", "name") == "gta-ranked-studio"
    assert config.get("hardware", "gpu_vram_gb") == 16
    assert config.get("transcription", "backend") == "vulkan"
    assert config.path_for("paths", "inbox_shorts").name == "shorts"


def test_missing_config_raises_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="introuvable"):
        load_config(tmp_path / "missing.yaml")


def test_invalid_yaml_root_raises_error(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("- item\n- item2\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="racine"):
        load_config(bad_config)


def test_missing_required_section_raises_error(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("app: {}\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="Sections absentes"):
        load_config(bad_config)
