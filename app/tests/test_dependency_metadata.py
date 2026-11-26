"""La séparation runtime/dev reste cohérente entre pyproject et requirements."""
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_requirements_file_matches_only_production_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    runtime = {item.strip().lower() for item in project["dependencies"]}
    requirements = {
        line.strip().lower()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert requirements == runtime


def test_test_clients_and_pytest_are_development_only() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dev = {item.split(">=")[0].split("<")[0].strip().lower() for item in project["optional-dependencies"]["dev"]}
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert {"pytest", "httpx2", "ruff", "pip-audit"} <= dev
    assert any(item.startswith("ruff>=") for item in project["optional-dependencies"]["dev"])
    assert any(item.startswith("pip-audit>=") for item in project["optional-dependencies"]["dev"])
    assert "httpx" not in dev
    assert "pytest" not in requirements
    assert "httpx" not in requirements
    assert "httpx2" not in requirements
    assert "watchdog" not in requirements
