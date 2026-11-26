"""Vérifie les invariants de cohérence qui protègent les releases."""
from pathlib import Path
import os
import tomllib

import yaml

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent


def test_all_project_version_sources_are_synchronized() -> None:
    root_version = (REPO / "VERSION.txt").read_text(encoding="utf-8-sig")
    app_version = (APP / "VERSION.txt").read_text(encoding="utf-8-sig")
    import re
    def value(text: str) -> str:
        matches = re.findall(r"(?im)^Version:\s*(\d+(?:\.\d+){2,3})\s*$", text)
        assert len(matches) == 1
        return matches[0]
    root = value(root_version)
    assert value(app_version) == root
    pyproject = tomllib.loads((APP / "pyproject.toml").read_text(encoding="utf-8"))
    config = yaml.safe_load((APP / "config.yaml.default").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == root
    assert str(config["app"]["version"]) == root
    assert (REPO / f"NOTES-v{root}.txt").read_bytes() == (APP / f"NOTES-v{root}.txt").read_bytes()


def test_canonical_documentation_is_not_duplicated_inside_app() -> None:
    for relative in (
        "docs/CONTINUATION.md", "docs/UPDATES.md",
        "docs/implementation-plan-v0.7.8.md", "tools/check_project_memory.py",
        "README_M0.txt", "prompts/bestof_metadata.default.txt",
    ):
        assert not (APP / relative).exists()
    assert (REPO / "docs/CONTINUATION.md").is_file()
    assert (REPO / "docs/PROJECT-MAP.md").is_file()
    assert not (REPO / "docs/implementation-plan-v0.7.8.md").exists()
    assert {note.name for note in APP.glob("NOTES-v*.txt")} == {"NOTES-v0.8.4.txt"}
    assert not list(APP.glob("VERIFICATION-v*.md"))


def test_project_memory_checker_passes_for_the_repository_root() -> None:
    import subprocess
    import sys

    checker = REPO / "tools" / "check_project_memory.py"
    result = subprocess.run(
        [sys.executable, str(checker), "--root", str(REPO)],
        cwd=REPO,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "Cohérence du dépôt GTA Ranked Studio : OK." in result.stdout


def test_only_the_short_creation_pipeline_is_in_the_default_config() -> None:
    config = yaml.safe_load((APP / "config.yaml.default").read_text(encoding="utf-8"))
    assert "shorts" in config
    assert "bestof" not in config
    assert "scoring" not in config
    assert not {"inbox_bestof", "inbox_urls", "output_bestof", "output_log_csv"} & set(config["paths"])

def test_runtime_smoke_check_runs_from_installer_path(tmp_path) -> None:
    import subprocess
    import sys

    checker = APP / "installer" / "check_runtime.py"
    result = subprocess.run(
        [sys.executable, str(checker)],
        cwd=tmp_path,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "GTA_RS_RUNTIME_CHECK_OK" in result.stdout
