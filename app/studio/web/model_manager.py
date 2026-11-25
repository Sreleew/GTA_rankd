"""Téléchargement explicite des modèles locaux depuis leurs dépôts officiels."""

from __future__ import annotations

import logging
import re
import threading
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

WHISPER_MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin?download=true"
MIN_WHISPER_MODEL_BYTES = 1024 * 1024 * 1024


class ModelManager:
    def __init__(self, whisper_model_path: Path) -> None:
        self.whisper_model_path = Path(whisper_model_path).resolve()
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        model_valid = self._model_is_valid()
        self._state: dict[str, Any] = {
            "status": "ready" if model_valid else ("invalid" if self.whisper_model_path.is_file() else "not_installed"),
            "progress": 100 if model_valid else 0,
            "downloaded_bytes": self.whisper_model_path.stat().st_size if self.whisper_model_path.is_file() else 0,
            "total_bytes": 0,
            "message": "Modèle Whisper installé et taille cohérente." if model_valid else (
                "Le fichier du modèle semble incomplet ou invalide." if self.whisper_model_path.is_file()
                else "Modèle Whisper non installé."
            ),
        }

    def _model_is_valid(self) -> bool:
        # Le modèle large-v3-turbo fait environ 1,6 Go. Un fichier de quelques
        # octets ou une page HTML téléchargée par erreur ne doit pas être marqué prêt.
        try:
            return self.whisper_model_path.is_file() and self.whisper_model_path.stat().st_size >= MIN_WHISPER_MODEL_BYTES
        except OSError:
            return False

    def status(self) -> dict[str, Any]:
        with self._lock:
            state = dict(self._state)
        state["path"] = str(self.whisper_model_path)
        state["exists"] = self.whisper_model_path.is_file()
        state["valid"] = self._model_is_valid()
        if state["exists"]:
            state["size_bytes"] = self.whisper_model_path.stat().st_size
        return state

    def start_whisper_download(self) -> dict[str, Any]:
        with self._lock:
            if self._model_is_valid():
                self._state.update(status="ready", progress=100, message="Le modèle Whisper est déjà installé.")
                return dict(self._state)
            if self.whisper_model_path.exists():
                self.whisper_model_path.unlink(missing_ok=True)
            if self._thread and self._thread.is_alive():
                return dict(self._state)
            self._cancel.clear()
            partial = self.whisper_model_path.with_suffix(self.whisper_model_path.suffix + ".part")
            partial_bytes = partial.stat().st_size if partial.is_file() else 0
            self._state = {
                "status": "downloading", "progress": 0, "downloaded_bytes": partial_bytes,
                "total_bytes": 0,
                "message": f"Reprise possible : {partial_bytes / (1024 ** 3):.2f} Go déjà reçus" if partial_bytes else "Connexion à Hugging Face...",
            }
            self._thread = threading.Thread(target=self._download_whisper, name="gta-whisper-model-download", daemon=True)
            self._thread.start()
            return dict(self._state)

    def cancel(self) -> dict[str, Any]:
        self._cancel.set()
        with self._lock:
            if self._state.get("status") == "downloading":
                self._state["message"] = "Annulation demandée..."
        return self.status()

    def _set_state(self, **values: Any) -> None:
        with self._lock:
            self._state.update(values)

    def _download_whisper(self) -> None:
        target = self.whisper_model_path
        partial = target.with_suffix(target.suffix + ".part")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            offset = partial.stat().st_size if partial.is_file() else 0
            headers = {
                "User-Agent": "GTA-Ranked-Studio/0.6.0",
                "Accept": "application/octet-stream",
            }
            if offset:
                headers["Range"] = f"bytes={offset}-"
            request = urllib.request.Request(WHISPER_MODEL_URL, headers=headers)
            with urllib.request.urlopen(request, timeout=90) as response:
                status = getattr(response, "status", None) or response.getcode()
                content_range = str(response.headers.get("Content-Range") or "")
                if offset and status == 206:
                    match = re.match(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", content_range, re.IGNORECASE)
                    if not match or int(match.group(1)) != offset:
                        raise RuntimeError("Le serveur a renvoyé une plage de reprise incohérente.")
                    total = int(match.group(3)) if match.group(3) != "*" else offset + int(response.headers.get("Content-Length") or 0)
                    mode = "ab"
                else:
                    # A server that ignores Range returns 200: restart cleanly.
                    offset = 0
                    total = int(response.headers.get("Content-Length") or 0)
                    mode = "wb"
                downloaded = offset
                self._set_state(
                    total_bytes=total,
                    downloaded_bytes=downloaded,
                    progress=min(99, int(downloaded * 100 / total)) if total else 0,
                    message=("Reprise du téléchargement Whisper..." if offset else "Téléchargement du modèle Whisper large-v3-turbo..."),
                )
                with partial.open(mode) as destination:
                    while True:
                        if self._cancel.is_set():
                            raise InterruptedError("Téléchargement annulé. La partie déjà reçue sera conservée pour la reprise.")
                        chunk = response.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        destination.write(chunk)
                        downloaded += len(chunk)
                        progress = min(99, int(downloaded * 100 / total)) if total else 0
                        self._set_state(
                            downloaded_bytes=downloaded,
                            total_bytes=total,
                            progress=progress,
                            message=f"Téléchargement Whisper : {downloaded / (1024 ** 3):.2f} Go reçus",
                        )
            actual_size = partial.stat().st_size
            if total and actual_size != total:
                raise RuntimeError(
                    f"Téléchargement incomplet : {actual_size} octets reçus sur {total}. "
                    "La prochaine tentative reprendra au dernier octet reçu."
                )
            if actual_size < MIN_WHISPER_MODEL_BYTES:
                raise RuntimeError("Le fichier téléchargé est anormalement petit. Le modèle n'a pas été installé.")
            partial.replace(target)
            self._set_state(
                status="ready",
                progress=100,
                downloaded_bytes=target.stat().st_size,
                total_bytes=target.stat().st_size,
                message="Modèle Whisper installé. Les sous-titres peuvent être activés.",
            )
        except InterruptedError as exc:
            downloaded = partial.stat().st_size if partial.is_file() else 0
            self._set_state(
                status="cancelled",
                progress=0,
                downloaded_bytes=downloaded,
                message=str(exc),
            )
        except Exception as exc:
            logger.exception("Téléchargement du modèle Whisper impossible")
            downloaded = partial.stat().st_size if partial.is_file() else 0
            self._set_state(
                status="error",
                progress=0,
                downloaded_bytes=downloaded,
                message=f"Téléchargement impossible : {exc}. La partie reçue est conservée pour la reprise.",
            )
