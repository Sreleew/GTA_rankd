"""Le contrôle runtime teste la sortie UTF-8 et les clients HTTP de FastAPI."""

from importlib.util import find_spec
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
ESSENTIAL_MODULES = ("fastapi", "httpx")
OPTIONAL_RUNTIME_MODULES = {
    "httpx2": "httpx2",
    "multipart": "python-multipart",
    "PIL": "Pillow",
    "pytest": "pytest",
    "typer": "typer",
    "uvicorn": "uvicorn",
    "watchdog": "watchdog",
    "yaml": "PyYAML",
    "yt_dlp": "yt-dlp",
}


def _write_import_shim(shim_dir: Path, module_name: str, distribution_name: str) -> None:
    """Ajoute un module de test minimal pour les dépendances absentes du runner."""
    module_path = shim_dir.joinpath(*module_name.split(".")).with_suffix(".py")
    module_path.parent.mkdir(parents=True, exist_ok=True)
    if module_name == "httpx2":
        module_path.write_text(
            "from httpx import *\nfrom httpx import __version__ as __version__\n",
            encoding="utf-8",
        )
    else:
        module_path.write_text("# module simulé pour test du script de diagnostic\n", encoding="utf-8")

    dist_info = shim_dir / f"{distribution_name.replace('-', '_')}-0.0.0.dist-info"
    dist_info.mkdir(exist_ok=True)
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {distribution_name}\nVersion: 0.0.0\n",
        encoding="utf-8",
    )


def test_installer_runtime_check(tmp_path: Path) -> None:
    missing_essentials = [name for name in ESSENTIAL_MODULES if find_spec(name) is None]
    if missing_essentials:
        pytest.skip("Dépendances essentielles absentes du runner : " + ", ".join(missing_essentials))

    env = os.environ.copy()
    shim_dir = tmp_path / "runtime-shims"
    shim_dir.mkdir()
    used_shim = False

    # Le runner de construction ne dispose pas toujours de toutes les dépendances.
    # Les shims servent uniquement à tester le contrôle d'import et l'encodage ;
    # FastAPI et HTTPX restent les véritables bibliothèques du TestClient.
    for module_name, distribution_name in OPTIONAL_RUNTIME_MODULES.items():
        if find_spec(module_name) is None:
            _write_import_shim(shim_dir, module_name, distribution_name)
            used_shim = True

    python_path_parts: list[str] = []
    if used_shim:
        python_path_parts.append(str(shim_dir))
    existing_python_path = env.get("PYTHONPATH")
    if existing_python_path:
        python_path_parts.append(existing_python_path)
    if python_path_parts:
        env["PYTHONPATH"] = os.pathsep.join(python_path_parts)

    script = ROOT / "installer" / "check_runtime.py"
    # Simule Windows avec une page de code historique : le script doit reconfigurer
    # ses sorties en UTF-8 avant d'écrire les messages accentués.
    env["PYTHONIOENCODING"] = "cp1252"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "FastAPI TestClient : OK" in result.stdout
    assert "GTA_RS_RUNTIME_CHECK_OK" in result.stdout
    assert "httpx2 :" in result.stdout
