"""Protège les garde-fous CI, les chemins de validation et l'approbation de release."""
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[2]


def read_workflow(path: str) -> dict:
    return yaml.load((REPO / path).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_ci_uses_current_actions_and_cancels_superseded_runs() -> None:
    for path in (".github/workflows/audit-source.yml", ".github/workflows/windows-smoke.yml"):
        workflow = read_workflow(path)
        assert workflow["concurrency"]["cancel-in-progress"] == "true"
        assert "${{ github.ref }}" in workflow["concurrency"]["group"]
        uses = [step.get("uses", "") for step in workflow["jobs"][next(iter(workflow["jobs"]))]["steps"]]
        assert "actions/checkout@v7" in uses
        assert "actions/setup-python@v7" in uses
        assert "actions/setup-node@v7" in uses
        assert "actions/upload-artifact@v7" in uses
        assert ".release-approval" not in str(workflow["on"].get("push", {}).get("paths", []))


def test_full_development_dependencies_are_installed_only_in_ci() -> None:
    audit = read_workflow(".github/workflows/audit-source.yml")
    windows = read_workflow(".github/workflows/windows-smoke.yml")
    release = read_workflow(".github/workflows/release.yml")
    for workflow in (audit, windows, release):
        steps = workflow["jobs"][next(iter(workflow["jobs"]))]["steps"]
        script = "\n".join(step.get("run", "") for step in steps)
        assert "[dev]" in script
        assert "ruff check" in script
        assert "pip-audit" in script
        assert "verify_release_package.py" in script


def test_stable_release_remains_explicitly_approved_and_non_overwriting() -> None:
    workflow = read_workflow(".github/workflows/release.yml")
    triggers = workflow["on"]
    assert set(triggers) == {"push", "workflow_dispatch"}
    assert triggers["push"]["branches"] == ["main"]
    assert triggers["push"]["paths"] == [".release-approval"]
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert inputs["confirm_publish"]["type"] == "boolean"
    assert inputs["confirm_publish"]["required"] == "true"
    assert inputs["confirm_publish"]["default"] == "false"
    script = "\n".join(step.get("run", "") for step in workflow["jobs"]["release"]["steps"])
    assert "git ls-remote" in script
    assert ".release-approval" in script
    assert "verify_release_package.py" in script


def test_canonical_docs_are_embedded_from_root_once() -> None:
    builder = (REPO / "app" / "installer" / "build_release_package.py").read_text(encoding="utf-8")
    release = read_workflow(".github/workflows/release.yml")
    assert "CANONICAL_DOCS" in builder
    assert "implementation-plan-v0.7.8" not in builder
    steps = release["jobs"]["release"]["steps"]
    text = "\n".join(step.get("run", "") for step in steps)
    assert "cp docs/CONTINUATION.md" not in text
    assert "app/docs" not in text
