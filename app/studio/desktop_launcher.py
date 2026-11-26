"""Lanceur Windows sans console pour ouvrir GTA Ranked Studio dans Chrome."""

from __future__ import annotations

import logging
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from studio.config import load_config
from studio.logging_setup import configure_logging
from studio.web.app import create_app

logger = logging.getLogger(__name__)


def _open_chrome(url: str) -> None:
    """Ouvre Chrome s'il est installé, sinon le navigateur Windows par défaut."""
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                subprocess.Popen([str(candidate), url], close_fds=True)
                return
            except OSError:
                logger.exception("Impossible de lancer Chrome depuis %s", candidate)
    webbrowser.open(url)


def main() -> int:
    """Démarre le serveur, attend qu'il réponde, puis ouvre le navigateur."""
    project_root = Path.cwd()
    config_path = project_root / "config.yaml"
    try:
        config = load_config(config_path)
        configure_logging(config, console=False)
        host = str(config.get("web", "host", default="127.0.0.1"))
        port = int(config.get("web", "port", default=8765))
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Le lanceur de bureau n'accepte que localhost pour préserver la confidentialité.")

        app = create_app(config)
        url = f"http://127.0.0.1:{port}"
        server_config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=False,
            log_config=None,
        )
        server = uvicorn.Server(server_config)
        app.state.uvicorn_server = server
        server_thread = threading.Thread(target=server.run, name="gta-ranked-web", daemon=False)
        server_thread.start()

        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if server.started:
                _open_chrome(url)
                logger.info("GTA Ranked Studio est ouvert sur %s", url)
                server_thread.join()
                return 0
            if not server_thread.is_alive():
                raise RuntimeError(f"Le serveur local n'a pas démarré. Le port {port} est peut-être déjà utilisé.")
            time.sleep(0.15)

        server.should_exit = True
        raise TimeoutError("Le serveur local n'a pas répondu après 25 secondes. Consulte logs/studio.log.")
    except Exception:
        # Le lanceur utilise pythonw.exe : les erreurs doivent être écrites dans le journal.
        try:
            if config_path.is_file():
                config = load_config(config_path)
                configure_logging(config, console=False)
            logger.exception("Échec du lancement de GTA Ranked Studio")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
