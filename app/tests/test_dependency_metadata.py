"""Verifie que les dependances d installation couvrent les tests de l API."""

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_httpx_and_httpx2_are_declared_in_development_dependencies() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev_dependencies = metadata["project"]["optional-dependencies"]["dev"]
    assert any(item.lower().startswith("httpx>=") for item in dev_dependencies)
    assert any(item.lower().startswith("httpx2>=") for item in dev_dependencies)


def test_requirements_file_includes_http_clients_for_manual_test_installations() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert any(item.strip().lower().startswith("httpx>=") for item in requirements)
    assert any(item.strip().lower().startswith("httpx2>=") for item in requirements)
