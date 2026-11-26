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



def test_legacy_default_short_profile_upgrades_in_memory_without_rewriting_user_config(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "config.yaml.default").read_text(encoding="utf-8")
    source = source.replace("version: 0.8.2", "version: 0.8.1")
    source = source.replace("max_input_duration_seconds: 165", "max_input_duration_seconds: 60")
    source = source.replace("peak_trim_threshold_seconds: 165", "peak_trim_threshold_seconds: 45")
    source = source.replace("auto_trim_min_seconds: 60", "auto_trim_min_seconds: 15")
    source = source.replace("auto_trim_max_seconds: 165", "auto_trim_max_seconds: 45")
    path = tmp_path / "config.yaml"
    path.write_text(source, encoding="utf-8")

    config = load_config(path)

    assert config.get("shorts", "max_input_duration_seconds") == 165
    assert config.get("shorts", "peak_trim_threshold_seconds") == 165
    assert config.get("shorts", "auto_trim_min_seconds") == 60
    assert config.get("shorts", "auto_trim_max_seconds") == 165
    assert "max_input_duration_seconds: 60" in path.read_text(encoding="utf-8")


def test_legacy_short_profile_keeps_user_customized_limits(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "config.yaml.default").read_text(encoding="utf-8")
    source = source.replace("version: 0.8.2", "version: 0.8.0")
    source = source.replace("max_input_duration_seconds: 165", "max_input_duration_seconds: 90")
    source = source.replace("peak_trim_threshold_seconds: 165", "peak_trim_threshold_seconds: 45")
    source = source.replace("auto_trim_min_seconds: 60", "auto_trim_min_seconds: 20")
    source = source.replace("auto_trim_max_seconds: 165", "auto_trim_max_seconds: 45")
    path = tmp_path / "config.yaml"
    path.write_text(source, encoding="utf-8")

    config = load_config(path)

    assert config.get("shorts", "max_input_duration_seconds") == 90
    assert config.get("shorts", "peak_trim_threshold_seconds") == 165
    assert config.get("shorts", "auto_trim_min_seconds") == 20
    assert config.get("shorts", "auto_trim_max_seconds") == 165


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
