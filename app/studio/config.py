"""Chargement et validation de la configuration YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Erreur de lecture ou de validation de config.yaml."""


@dataclass(frozen=True)
class AppConfig:
    """Configuration chargée et associée à la racine du projet."""

    data: dict[str, Any]
    path: Path

    @property
    def root(self) -> Path:
        return self.path.parent

    def get(self, *keys: str, default: Any = None) -> Any:
        value: Any = self.data
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def path_for(self, *keys: str) -> Path:
        value = self.get(*keys)
        if value is None:
            raise ConfigError(f"Clé de chemin absente dans config.yaml : {'.'.join(keys)}")
        path = Path(str(value)).expanduser()
        if not path.is_absolute():
            path = self.root / path
        return path.resolve()


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    """Charge le YAML et vérifie les sections obligatoires du projet."""

    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigError(f"Fichier de configuration introuvable : {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML invalide dans {config_path} : {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Impossible de lire {config_path} : {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("La racine de config.yaml doit être un objet YAML.")

    required_sections = ("app", "hardware", "paths", "executables", "encoding", "transcription", "ollama")
    missing = [section for section in required_sections if not isinstance(raw.get(section), dict)]
    if missing:
        raise ConfigError("Sections absentes ou invalides dans config.yaml : " + ", ".join(missing))

    return AppConfig(data=raw, path=config_path)
