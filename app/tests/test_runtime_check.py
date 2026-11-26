"""Teste le smoke test runtime de l'installation sans les dépendances dev."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_installer_runtime_smoke_check(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    result = subprocess.run(
        [sys.executable, str(ROOT / "installer" / "check_runtime.py")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env, timeout=45,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "Imports de l'application : OK" in result.stdout
    assert "GTA_RS_RUNTIME_CHECK_OK" in result.stdout
    assert "httpx" not in result.stdout.lower()
