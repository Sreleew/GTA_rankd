"""Serveur FastAPI local et endpoints du tableau de bord."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from studio.config import AppConfig, load_config
from studio.process import run_quiet
from studio.web.store import Store
from studio.web.worker import JobRunner
from studio.web.transcribe import inspect_whisper_cli, probe_whisper_vulkan
from studio.web.model_manager import ModelManager
from studio.web.updater import UpdateService
from studio.web.highlights import HighlightScanner

logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def safe_upload_name(filename: str) -> str:
    original = (filename or "clip.mp4").replace("\\", "/").rsplit("/", 1)[-1]
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", Path(original).stem).strip("._") or "clip"
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Format non pris en charge. Utilise MP4, MOV, MKV, WEBM ou M4V.")
    return f"{stem[:80]}{suffix}"



def _validate_edit_options(
    layout: str, crop_x: int, crop_y: int, dynamic_zoom: bool, zoom_percent: int,
    captions_enabled: bool, brand_enabled: bool, hook_text: str, context_text: str,
    auto_trim_enabled: bool = True, sfx_enabled: bool = True,
    caption_voice_mode: str = "dominant",
) -> dict:
    if layout not in {"fill", "blur", "smart"}:
        raise HTTPException(status_code=400, detail="Le cadrage doit être 'smart', 'fill' ou 'blur'.")
    if not 0 <= int(crop_x) <= 100 or not 0 <= int(crop_y) <= 100:
        raise HTTPException(status_code=400, detail="La position du cadrage doit être comprise entre 0 et 100.")
    if not 0 <= int(zoom_percent) <= 20:
        raise HTTPException(status_code=400, detail="Le zoom doit être compris entre 0 et 20 %.")
    if caption_voice_mode not in {"all", "dominant"}:
        raise HTTPException(status_code=400, detail="Le mode de voix doit être 'all' ou 'dominant'.")
    return {
        "layout": layout, "crop_x": int(crop_x), "crop_y": int(crop_y),
        "dynamic_zoom": bool(dynamic_zoom), "zoom_percent": int(zoom_percent),
        "captions_enabled": bool(captions_enabled), "brand_enabled": bool(brand_enabled),
        "caption_voice_mode": caption_voice_mode,
        "auto_trim_enabled": bool(auto_trim_enabled), "sfx_enabled": bool(sfx_enabled),
        "hook_text": str(hook_text or "").strip()[:100],
        "context_text": str(context_text or "").strip()[:150],
    }


def create_app(config_or_path: AppConfig | str | Path = "config.yaml") -> FastAPI:
    config = config_or_path if isinstance(config_or_path, AppConfig) else load_config(config_or_path)
    root = config.root
    inbox = config.path_for("paths", "inbox_shorts")
    outputs = config.path_for("paths", "output_shorts").parent
    static_dir = Path(__file__).parent / "static"
    inbox.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    store = Store(config.path_for("paths", "database"))
    runner = JobRunner(config, store)
    runner.start()
    model_manager = ModelManager(config.path_for("transcription", "model_path"))
    update_service = UpdateService(root)
    highlight_scanner = HighlightScanner(config, store)
    highlight_scanner.start()
    whisper_diagnostic_cache: dict = {"checked_at": 0.0, "result": None}
    whisper_diagnostic_lock = threading.Lock()
    whisper_gpu_probe_lock = threading.Lock()
    ollama_verify_lock = threading.Lock()
    whisper_gpu_marker = config.path_for("paths", "database").parent / "whisper-vulkan-verification.json"

    app = FastAPI(title="GTA Ranked Studio", docs_url="/api/docs", redoc_url=None)
    app.state.config = config
    app.state.store = store
    app.state.runner = runner
    app.state.model_manager = model_manager
    app.state.update_service = update_service
    app.state.highlight_scanner = highlight_scanner
    app.state.project_root = root
    app.state.uvicorn_server = None

    @app.get("/api/health")
    def health() -> dict:
        version_file = root / "VERSION.txt"
        app_version = str(config.get("app", "version", default="0.3.2"))
        if version_file.is_file():
            for line in version_file.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.lower().startswith("version:"):
                    app_version = line.split(":", 1)[1].strip() or app_version
                    break
        ffmpeg = shutil.which(str(config.get("executables", "ffmpeg", default="ffmpeg")))
        ffprobe = shutil.which(str(config.get("executables", "ffprobe", default="ffprobe")))
        ollama = shutil.which("ollama")
        whisper = config.path_for("executables", "whisper_cli")
        amf = False
        if ffmpeg:
            try:
                result = run_quiet(
                    [ffmpeg, "-hide_banner", "-encoders"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8,
                    check=False,
                )
                amf = result.returncode == 0 and "h264_amf" in (result.stdout + result.stderr)
            except (OSError, subprocess.TimeoutExpired):
                amf = False
        return {
            "ok": True,
            "local_only": True,
            "ffmpeg": bool(ffmpeg),
            "ffprobe": bool(ffprobe),
            "amf": amf,
            "encoder_fallback": "libx264",
            "ollama_cli": bool(ollama),
            "whisper_cli": whisper.is_file(),
            "whisper_model": config.path_for("transcription", "model_path").is_file(),
            "app_version": app_version,
            "gpu": str(config.get("hardware", "gpu_model", default="GPU non configuré")),
        }

    @app.get("/api/updates/check")
    def check_for_updates() -> dict:
        try:
            return update_service.check()
        except Exception as exc:
            logger.warning("Vérification de mise à jour impossible : %s", exc)
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/updates/status")
    def updates_status() -> dict:
        return update_service.get_status()

    @app.post("/api/updates/install", status_code=202)
    def install_update() -> dict:
        server = getattr(app.state, "uvicorn_server", None)
        if server is None:
            raise HTTPException(status_code=503, detail="Le redémarrage automatique n'est pas disponible avec ce mode de lancement.")
        try:
            return update_service.start_install(server=server, parent_pid=os.getpid())
        except Exception as exc:
            logger.warning("Démarrage de la mise à jour impossible : %s", exc)
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/dashboard")
    def dashboard() -> dict:
        return store.get_dashboard()

    @app.get("/api/jobs")
    def jobs(limit: int = 50) -> list[dict]:
        return store.list_jobs(max(1, min(limit, 200)))

    @app.get("/api/highlights")
    def list_highlights(limit: int = 30) -> list[dict]:
        scans = store.list_highlight_scans(max(1, min(limit, 100)))
        for scan in scans:
            scan["candidates"] = store.list_highlight_candidates(scan["id"])
        return scans

    @app.post("/api/highlights/{scan_id}/cancel")
    def cancel_highlight_scan(scan_id: str) -> dict:
        scan = store.get_highlight_scan(scan_id)
        if scan is None:
            raise HTTPException(status_code=404, detail="Analyse introuvable.")
        if scan.get("status") not in {"queued", "running"}:
            raise HTTPException(status_code=409, detail="Cette analyse est déjà terminée ou annulée.")
        if not highlight_scanner.cancel(scan_id):
            raise HTTPException(status_code=409, detail="L'annulation n'a pas pu être lancée. Actualise la file.")
        return {"id": scan_id, "status": "cancelled" if scan.get("status") == "queued" else "cancelling", "message": "Annulation de l'analyse demandée."}

    def _validate_twitch_source(url: str) -> str:
        from urllib.parse import urlparse
        clean = str(url or "").strip()
        parsed = urlparse(clean)
        host = (parsed.hostname or "").lower()
        allowed_hosts = {"twitch.tv", "www.twitch.tv", "m.twitch.tv", "clips.twitch.tv"}
        if parsed.scheme != "https" or host not in allowed_hosts:
            raise HTTPException(status_code=400, detail="Utilise une URL Twitch publique de VOD ou de clip (https://www.twitch.tv/...).")
        if not ("/videos/" in parsed.path or "/clip/" in parsed.path or host == "clips.twitch.tv"):
            raise HTTPException(status_code=400, detail="Colle une URL de VOD Twitch ou de clip Twitch, pas une page de chaîne.")
        return clean

    def _parse_optional_seconds(value: str | None, field_name: str) -> float | None:
        if value is None or not str(value).strip():
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"{field_name} doit être un nombre de secondes.") from exc
        if not math.isfinite(parsed):
            raise HTTPException(status_code=400, detail=f"{field_name} doit être un nombre valide.")
        return parsed

    def _validate_webcam_zone(value: str) -> str:
        allowed = {"none", "top-left", "top-right", "bottom-left", "bottom-right"}
        zone = str(value or "none").strip().lower()
        if zone not in allowed:
            raise HTTPException(status_code=400, detail="Zone webcam invalide.")
        return zone

    def _validate_highlight_window(start: float | None, end: float | None) -> tuple[float | None, float | None]:
        if (start is None) != (end is None):
            raise HTTPException(status_code=400, detail="Renseigne le début ET la fin de la plage, ou laisse les deux vides pour analyser toute la source.")
        if start is not None and end is not None:
            if start < 0 or end <= start:
                raise HTTPException(status_code=400, detail="La plage doit avoir un début positif et une fin supérieure au début.")
            if end - start > 3 * 60 * 60:
                raise HTTPException(status_code=400, detail="La première version limite une analyse à 3 heures par passage.")
        return start, end

    @app.post("/api/highlights/scan/url", status_code=202)
    def scan_highlight_url(
        url: Annotated[str, Form()],
        streamer: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
        rights_confirmed: Annotated[bool, Form()] = False,
        window_start: Annotated[str | None, Form()] = None,
        window_end: Annotated[str | None, Form()] = None,
        webcam_zone: Annotated[str, Form()] = "none",
    ) -> dict:
        if not rights_confirmed:
            raise HTTPException(status_code=400, detail="Confirme que tu disposes des droits ou autorisations nécessaires pour analyser cette source.")
        clean_url = _validate_twitch_source(url)
        start = _parse_optional_seconds(window_start, "Début")
        end = _parse_optional_seconds(window_end, "Fin")
        start, end = _validate_highlight_window(start, end)
        webcam_zone = _validate_webcam_zone(webcam_zone)
        scan_id = uuid.uuid4().hex
        store.create_highlight_scan({
            "id": scan_id, "source_kind": "url", "source_url": clean_url,
            "streamer": streamer.strip()[:120], "message": "VOD/clip ajouté à la file d'analyse",
            "window_start": start, "window_end": end, "rights_confirmed": True,
            "metadata": {"note": note.strip()[:1000], "webcam_zone": webcam_zone},
        })
        highlight_scanner.submit(scan_id)
        return {"id": scan_id, "status": "queued", "message": "Source Twitch ajoutée à l'analyse des moments forts."}

    @app.post("/api/highlights/scan/upload", status_code=202)
    async def scan_highlight_upload(
        file: Annotated[UploadFile, File(...)],
        streamer: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
        rights_confirmed: Annotated[bool, Form()] = False,
        window_start: Annotated[str | None, Form()] = None,
        window_end: Annotated[str | None, Form()] = None,
        webcam_zone: Annotated[str, Form()] = "none",
    ) -> dict:
        if not rights_confirmed:
            raise HTTPException(status_code=400, detail="Confirme que tu disposes des droits ou autorisations nécessaires pour analyser cette vidéo.")
        start = _parse_optional_seconds(window_start, "Début")
        end = _parse_optional_seconds(window_end, "Fin")
        start, end = _validate_highlight_window(start, end)
        safe_name = safe_upload_name(file.filename or "vod.mp4")
        max_mb = int(config.get("web", "max_highlight_upload_mb", default=10240))
        max_bytes = max_mb * 1024 * 1024
        scan_id = uuid.uuid4().hex
        target_dir = inbox.parent / "highlights"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{scan_id}_{safe_name}"
        written = 0
        try:
            with target_path.open("wb") as destination:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux. Limite : {max_mb // 1024} Go.")
                    destination.write(chunk)
            if written <= 0:
                raise HTTPException(status_code=400, detail="Le fichier sélectionné est vide.")
        except Exception:
            target_path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        store.create_highlight_scan({
            "id": scan_id, "source_kind": "upload", "source_path": str(target_path.resolve()),
            "source_title": Path(safe_name).stem, "streamer": streamer.strip()[:120],
            "message": "VOD/clip ajouté à la file d'analyse", "window_start": start, "window_end": end,
            "rights_confirmed": True, "metadata": {"note": note.strip()[:1000], "file_size": written, "webcam_zone": webcam_zone},
        })
        highlight_scanner.submit(scan_id)
        return {"id": scan_id, "status": "queued", "message": "Fichier ajouté à l'analyse des moments forts."}

    @app.post("/api/highlights/{scan_id}/candidates/{candidate_id}/create-short", status_code=202)
    def create_short_from_highlight(scan_id: str, candidate_id: str) -> dict:
        scan = store.get_highlight_scan(scan_id)
        if scan is None:
            raise HTTPException(status_code=404, detail="Analyse introuvable.")
        if scan["status"] != "completed":
            raise HTTPException(status_code=409, detail="L'analyse doit être terminée avant de créer un Short.")
        candidate = store.get_highlight_candidate(scan_id, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Passage candidat introuvable.")
        if candidate.get("created_job_id"):
            existing = store.get_job(candidate["created_job_id"])
            if existing and existing.get("status") not in {"error", "rejected"}:
                return {"id": existing["id"], "status": existing["status"], "message": "Ce passage a déjà été envoyé dans la file Shorts."}
        source_value = scan.get("source_path")
        if not source_value or not Path(source_value).is_file():
            raise HTTPException(status_code=409, detail="Le média source n'est plus disponible sur ce PC.")
        media_start = float(candidate["media_start"])
        media_end = float(candidate["media_end"])
        if media_end <= media_start or media_end - media_start > 60:
            raise HTTPException(status_code=409, detail="La durée du passage candidat est invalide pour un Short.")
        job_id = uuid.uuid4().hex
        scan_metadata = scan.get("metadata") or {}
        options = {
            "layout": "smart", "crop_x": 72, "crop_y": 50, "dynamic_zoom": False, "zoom_percent": 0,
            "captions_enabled": True, "caption_voice_mode": "dominant",
            "brand_enabled": True, "auto_trim_enabled": False, "sfx_enabled": True,
            "hook_text": "", "context_text": "",
            "source_range": {"start": media_start, "end": media_end},
        }
        store.create_job({
            "id": job_id, "source_kind": "upload", "source_path": str(Path(source_value).resolve()),
            "source_url": scan.get("source_url"),
            "source_title": scan.get("source_title") or "Moment fort détecté",
            "streamer": scan.get("streamer", ""), "note": "",
            "rights_confirmed": True, "message": "Passage sélectionné : préparation du Short",
            "metadata": {
                "options": options,
                "highlight_scan_id": scan_id,
                "highlight_candidate_id": candidate_id,
                "highlight_score": candidate["score"],
                "highlight_start_time": candidate["start_time"],
                "highlight_end_time": candidate["end_time"],
                "highlight_reasons": candidate["reasons"],
            },
        })
        store.mark_highlight_candidate_created(scan_id, candidate_id, job_id)
        runner.submit(job_id)
        return {"id": job_id, "status": "queued", "message": "Passage envoyé dans la file de création de Shorts."}

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job introuvable.")
        if job.get("status") not in {"queued", "running"}:
            raise HTTPException(status_code=409, detail="Ce Short est déjà terminé ou annulé.")
        if not runner.cancel(job_id):
            raise HTTPException(status_code=409, detail="L'annulation n'a pas pu être lancée. Actualise la file.")
        return {"id": job_id, "status": "cancelled" if job.get("status") == "queued" else "cancelling", "message": "Annulation du Short demandée."}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job introuvable.")
        return job

    @app.post("/api/jobs/{job_id}/reprocess", status_code=202)
    def reprocess_job(job_id: str) -> dict:
        """Crée un nouveau job à partir du média local d'un job existant.

        Le hash source est volontairement omis : cela autorise un nouveau rendu
        du même média sans désactiver la protection anti-doublon des imports.
        """
        original = store.get_job(job_id)
        if original is None:
            raise HTTPException(status_code=404, detail="Job introuvable.")
        if original.get("status") not in {"validated", "ready", "error", "rejected"}:
            raise HTTPException(status_code=409, detail="Ce job est encore en cours de traitement.")
        source_value = original.get("source_path")
        if not source_value:
            raise HTTPException(status_code=409, detail="Le média local n'est pas disponible. Il faut réimporter la source.")
        source_path = Path(source_value)
        if not source_path.is_file():
            raise HTTPException(status_code=409, detail="Le fichier source n'existe plus dans le dossier d'import.")
        new_id = uuid.uuid4().hex
        metadata = dict(original.get("metadata") or {})
        # Les résultats du précédent rendu ne doivent pas être réutilisés comme
        # s'ils provenaient du nouveau traitement.
        for key in ("title", "description", "transcription_status", "captions_path", "transcript"):
            metadata.pop(key, None)
        store.create_job({
            "id": new_id,
            "kind": original.get("kind", "short"),
            "source_kind": "upload",
            "source_path": str(source_path.resolve()),
            "source_title": original.get("source_title") or source_path.stem,
            "streamer": original.get("streamer", ""),
            "note": original.get("note", ""),
            "rights_confirmed": True,
            "message": "Nouveau rendu demandé à partir du média existant",
            "metadata": metadata,
        })
        runner.submit(new_id)
        return {"id": new_id, "status": "queued", "message": "Nouveau traitement lancé à partir du média déjà importé."}

    @app.post("/api/shorts/upload", status_code=202)
    async def upload_short(
        file: Annotated[UploadFile, File(...)],
        streamer: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
        rights_confirmed: Annotated[bool, Form()] = False,
        layout: Annotated[str, Form()] = "smart",
        crop_x: Annotated[int, Form()] = 72,
        crop_y: Annotated[int, Form()] = 50,
        dynamic_zoom: Annotated[bool, Form()] = True,
        zoom_percent: Annotated[int, Form()] = 8,
        captions_enabled: Annotated[bool, Form()] = True,
        caption_voice_mode: Annotated[str, Form()] = "dominant",
        brand_enabled: Annotated[bool, Form()] = True,
        auto_trim_enabled: Annotated[bool, Form()] = True,
        sfx_enabled: Annotated[bool, Form()] = True,
        hook_text: Annotated[str, Form()] = "",
        context_text: Annotated[str, Form()] = "",
    ) -> dict:
        if not rights_confirmed:
            raise HTTPException(status_code=400, detail="Confirme que tu disposes des droits ou autorisations nécessaires pour utiliser ce clip.")
        options = _validate_edit_options(layout, crop_x, crop_y, dynamic_zoom, zoom_percent, captions_enabled, brand_enabled, hook_text, context_text, auto_trim_enabled, sfx_enabled, caption_voice_mode)
        safe_name = safe_upload_name(file.filename or "clip.mp4")
        max_mb = int(config.get("web", "max_upload_mb", default=2048))
        max_bytes = max_mb * 1024 * 1024
        job_id = uuid.uuid4().hex
        target_dir = inbox / "uploads"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{job_id}_{safe_name}"
        digest = hashlib.sha256()
        written = 0
        try:
            with target_path.open("wb") as destination:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux. Limite : {max_mb} Mo.")
                    digest.update(chunk)
                    destination.write(chunk)
        except Exception:
            target_path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        source_hash = digest.hexdigest()
        duplicate = store.find_duplicate_hash(source_hash)
        if duplicate:
            target_path.unlink(missing_ok=True)
            raise HTTPException(status_code=409, detail=f"Ce fichier a déjà été importé (job {duplicate['id'][:8]}).")
        store.create_job({
            "id": job_id, "source_kind": "upload", "source_path": str(target_path.resolve()),
            "source_hash": source_hash, "streamer": streamer.strip()[:120], "note": note.strip()[:1000],
            "rights_confirmed": rights_confirmed, "message": "Ajouté à la file d'attente",
            "metadata": {"options": options},
        })
        runner.submit(job_id)
        return {"id": job_id, "status": "queued", "message": "Clip ajouté à la file de traitement."}

    @app.post("/api/shorts/url", status_code=202)
    def create_short_from_url(
        url: Annotated[str, Form()],
        streamer: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
        rights_confirmed: Annotated[bool, Form()] = False,
        layout: Annotated[str, Form()] = "fill",
        crop_x: Annotated[int, Form()] = 50,
        crop_y: Annotated[int, Form()] = 50,
        dynamic_zoom: Annotated[bool, Form()] = True,
        zoom_percent: Annotated[int, Form()] = 8,
        captions_enabled: Annotated[bool, Form()] = True,
        caption_voice_mode: Annotated[str, Form()] = "dominant",
        brand_enabled: Annotated[bool, Form()] = True,
        auto_trim_enabled: Annotated[bool, Form()] = True,
        sfx_enabled: Annotated[bool, Form()] = True,
        hook_text: Annotated[str, Form()] = "",
        context_text: Annotated[str, Form()] = "",
    ) -> dict:
        if not rights_confirmed:
            raise HTTPException(status_code=400, detail="Confirme que tu disposes des droits ou autorisations nécessaires pour utiliser cette source.")
        clean_url = url.strip()
        if not clean_url.startswith(("https://", "http://")) or len(clean_url) > 2000:
            raise HTTPException(status_code=400, detail="URL invalide. Saisis une URL commençant par http:// ou https://.")
        job_id = uuid.uuid4().hex
        options = _validate_edit_options(layout, crop_x, crop_y, dynamic_zoom, zoom_percent, captions_enabled, brand_enabled, hook_text, context_text, auto_trim_enabled, sfx_enabled, caption_voice_mode)
        store.create_job({
            "id": job_id, "source_kind": "url", "source_url": clean_url,
            "streamer": streamer.strip()[:120], "note": note.strip()[:1000],
            "rights_confirmed": rights_confirmed, "message": "URL ajoutée à la file d'attente",
            "metadata": {"options": options},
        })
        runner.submit(job_id)
        return {"id": job_id, "status": "queued", "message": "URL ajoutée à la file de traitement."}

    def _whisper_gpu_fingerprint() -> dict | None:
        binary = config.path_for("executables", "whisper_cli")
        model = config.path_for("transcription", "model_path")
        try:
            binary_stat, model_stat = binary.stat(), model.stat()
        except OSError:
            return None
        if binary_stat.st_size <= 0 or model_stat.st_size < 1024 * 1024:
            return None
        return {"binary_path": str(binary), "binary_size": binary_stat.st_size, "binary_mtime_ns": binary_stat.st_mtime_ns,
                "model_path": str(model), "model_size": model_stat.st_size, "model_mtime_ns": model_stat.st_mtime_ns}

    def _load_whisper_gpu_marker() -> dict | None:
        try:
            marker = json.loads(whisper_gpu_marker.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(marker, dict) or marker.get("fingerprint") != _whisper_gpu_fingerprint():
            return None
        if marker.get("verified") is not True or not str(marker.get("backend", "")).startswith("Vulkan"):
            return None
        return marker

    def _write_whisper_gpu_marker(probe: dict) -> dict:
        fingerprint = _whisper_gpu_fingerprint()
        if not fingerprint:
            raise HTTPException(status_code=409, detail="Le binaire Whisper ou le modèle local est introuvable.")
        marker = {"verified": True, "fingerprint": fingerprint, "backend": str(probe.get("backend") or ""),
                  "gpu_model": str(probe.get("gpu_model") or config.get("hardware", "gpu_model", default="GPU Vulkan")),
                  "model_buffer_mb": float(probe.get("model_buffer_mb") or 0), "verified_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        whisper_gpu_marker.parent.mkdir(parents=True, exist_ok=True)
        temp_marker = whisper_gpu_marker.with_suffix(".tmp")
        temp_marker.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_marker, whisper_gpu_marker)
        return marker

    @app.get("/api/models/status")
    def models_status(refresh: bool = False) -> dict:
        model_state = model_manager.status()
        base_url = str(config.get("ollama", "base_url", default="http://127.0.0.1:11434"))
        ollama_running = False
        ollama_models: list[str] = []
        try:
            with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=2) as response:
                payload = response.read().decode("utf-8", errors="replace")
            import json
            ollama_payload = json.loads(payload)
            ollama_models = [str(item.get("name", "")) for item in ollama_payload.get("models", [])]
            ollama_running = True
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            pass
        ollama_model = str(config.get("ollama", "model", default="qwen2.5:7b-instruct"))
        with whisper_diagnostic_lock:
            if refresh or whisper_diagnostic_cache["result"] is None or time.monotonic() - whisper_diagnostic_cache["checked_at"] > 30:
                whisper_diagnostic_cache["result"] = inspect_whisper_cli(config.path_for("executables", "whisper_cli"))
                whisper_diagnostic_cache["checked_at"] = time.monotonic()
            whisper_diagnostic = dict(whisper_diagnostic_cache["result"])
        verified_marker = _load_whisper_gpu_marker()
        whisper_diagnostic["vulkan_verified"] = bool(verified_marker)
        whisper_diagnostic["vulkan_probe_available"] = bool(whisper_diagnostic.get("available") and config.path_for("transcription", "model_path").is_file())
        if verified_marker:
            whisper_diagnostic.update({
                "vulkan_detected": True,
                "devices": [f"{verified_marker['backend']} · {verified_marker['gpu_model']}"],
                "vulkan_backend": verified_marker["backend"],
                "gpu_model": verified_marker["gpu_model"],
                "model_buffer_mb": verified_marker["model_buffer_mb"],
                "verified_at": verified_marker["verified_at"],
                "message": f"{verified_marker['backend']} confirmé ; modèle alloué sur {verified_marker['gpu_model']}."
            })
        elif whisper_diagnostic.get("available") and not whisper_diagnostic.get("device_listing_supported"):
            whisper_diagnostic["message"] = "Build whisper.cpp exécutable et DTW compatible. Cette build Release ne propose pas --list-devices ; lance le test GPU pour vérifier le backend Vulkan."
        model_state.update({
            "whisper_cli_exists": bool(whisper_diagnostic.get("available")),
            "whisper_diagnostic": whisper_diagnostic,
            "ollama_running": ollama_running,
            "ollama_models": ollama_models,
            "ollama_model": ollama_model,
            "ollama_model_installed": any(name == ollama_model or name.startswith(ollama_model + ":") for name in ollama_models),
        })
        return model_state

    @app.post("/api/models/ollama/verify")
    def verify_ollama_model() -> dict:
        """Teste le serveur Ollama puis exécute une inférence Qwen courte en local."""
        if not ollama_verify_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Une vérification Ollama est déjà en cours.")
        started_at = time.monotonic()
        base_url = str(config.get("ollama", "base_url", default="http://127.0.0.1:11434")).rstrip("/")
        model_name = str(config.get("ollama", "model", default="qwen2.5:7b-instruct"))
        try:
            try:
                with urllib.request.urlopen(base_url + "/api/tags", timeout=5) as response:
                    tags_payload = json.loads(response.read().decode("utf-8", errors="replace"))
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Ollama ne répond pas sur {base_url}. Vérifie que l'application Ollama est démarrée. Détail : {exc}",
                ) from exc

            models = tags_payload.get("models", []) if isinstance(tags_payload, dict) else []
            installed_names = [str(item.get("name") or item.get("model") or "") for item in models if isinstance(item, dict)]
            model_installed = any(name == model_name or name.startswith(model_name + ":") for name in installed_names)
            if not model_installed:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ollama fonctionne, mais le modèle {model_name} n'est pas installé. Dans PowerShell, exécute : ollama pull {model_name}",
                )

            request_payload = {
                "model": model_name,
                "prompt": "Reply with exactly the single word OK. Do not add punctuation or anything else.",
                "stream": False,
                "keep_alive": "5m",
                "options": {"temperature": 0, "num_predict": 8, "num_ctx": 512},
            }
            request = urllib.request.Request(
                base_url + "/api/generate",
                data=json.dumps(request_payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            timeout_seconds = int(config.get("ollama", "verify_timeout_seconds", default=75))
            timeout_seconds = max(20, min(timeout_seconds, 120))
            try:
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    generation_payload = json.loads(response.read().decode("utf-8", errors="replace"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[-700:]
                raise HTTPException(status_code=502, detail=f"Ollama a refusé le test d'inférence ({exc.code}) : {detail or exc.reason}") from exc
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                raise HTTPException(
                    status_code=504,
                    detail=f"Ollama est joignable et Qwen est installé, mais le test d'inférence a échoué ou dépassé le délai de {timeout_seconds} s : {exc}",
                ) from exc

            if isinstance(generation_payload, dict) and generation_payload.get("error"):
                raise HTTPException(status_code=502, detail=f"Ollama n'a pas pu exécuter {model_name} : {generation_payload['error']}")
            generated_text = str(generation_payload.get("response", "") if isinstance(generation_payload, dict) else "").strip()
            if not generated_text:
                raise HTTPException(status_code=502, detail=f"Ollama a répondu, mais {model_name} n'a renvoyé aucun texte lors du test.")

            elapsed = round(time.monotonic() - started_at, 2)
            return {
                "verified": True,
                "ollama_running": True,
                "model_installed": True,
                "model": model_name,
                "elapsed_seconds": elapsed,
                "message": f"Ollama répond et {model_name} a réussi une inférence locale en {elapsed:.1f} s.",
            }
        finally:
            ollama_verify_lock.release()

    @app.post("/api/models/whisper/verify")
    def verify_whisper_gpu() -> dict:
        """Lance un vrai smoke-test Whisper/Vulkan puis mémorise le résultat lié au binaire courant."""
        if not whisper_gpu_probe_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Un test Vulkan est déjà en cours.")
        try:
            binary = config.path_for("executables", "whisper_cli")
            model = config.path_for("transcription", "model_path")
            expected_gpu = str(config.get("hardware", "gpu_model", default="GPU Vulkan"))
            if not binary.is_file():
                raise HTTPException(status_code=409, detail="whisper-cli.exe est introuvable. Installe d'abord le moteur Whisper.")
            if not model.is_file() or model.stat().st_size < 1024 * 1024:
                raise HTTPException(status_code=409, detail="Le modèle Whisper large-v3-turbo est absent ou incomplet.")
            probe = probe_whisper_vulkan(binary, model_path=model, expected_gpu=expected_gpu, timeout=150)
            if not probe.get("verified"):
                try:
                    whisper_gpu_marker.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Impossible de supprimer un ancien marqueur Vulkan invalide.")
                return {"verified": False, "message": probe.get("reason", "Le backend Vulkan n'a pas été confirmé."), "probe": probe}
            marker = _write_whisper_gpu_marker(probe)
            with whisper_diagnostic_lock:
                whisper_diagnostic_cache["result"] = None
                whisper_diagnostic_cache["checked_at"] = 0.0
            return {"verified": True, "message": f"{marker['backend']} confirmé ; {marker['gpu_model']} utilise le backend Vulkan et le modèle y est alloué.",
                    "backend": marker["backend"], "gpu_model": marker["gpu_model"], "model_buffer_mb": marker["model_buffer_mb"], "verified_at": marker["verified_at"]}
        finally:
            whisper_gpu_probe_lock.release()

    @app.post("/api/models/whisper/download", status_code=202)
    def download_whisper_model() -> dict:
        state = model_manager.start_whisper_download()
        if state.get("status") == "error":
            raise HTTPException(status_code=500, detail=state.get("message", "Téléchargement impossible."))
        return state

    @app.post("/api/models/whisper/cancel")
    def cancel_whisper_model_download() -> dict:
        return model_manager.cancel()

    @app.post("/api/jobs/{job_id}/validate")
    def validate_job(job_id: str) -> dict:
        validated = store.validate_job_and_add_to_clip_bank(job_id)
        if validated is not None:
            return {"id": job_id, "status": "validated"}
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job introuvable.")
        raise HTTPException(status_code=409, detail="Seuls les rendus prêts peuvent être validés.")

    @app.post("/api/jobs/{job_id}/reject")
    def reject_job(job_id: str) -> dict:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job introuvable.")
        if job["status"] not in {"ready", "error"}:
            raise HTTPException(status_code=409, detail="Ce job ne peut pas être rejeté dans son état actuel.")
        store.update_job(job_id, status="rejected", message="Short rejeté")
        return {"id": job_id, "status": "rejected"}

    @app.get("/api/clips")
    def clips(limit: int = 100) -> list[dict]:
        return store.list_clips(max(1, min(limit, 200)))

    @app.post("/api/shutdown")
    def shutdown() -> dict:
        """Arrête uniquement le serveur local lancé par le lanceur de bureau."""
        server = getattr(app.state, "uvicorn_server", None)
        if server is None:
            return {"ok": True, "message": "Aucun serveur Uvicorn contrôlable depuis cette session."}
        threading.Timer(0.35, lambda: setattr(server, "should_exit", True)).start()
        return {"ok": True, "message": "Arrêt du serveur demandé."}

    app.mount("/outputs", StaticFiles(directory=str(outputs), check_dir=True), name="outputs")
    app.mount("/static", StaticFiles(directory=str(static_dir), check_dir=True), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        # Force le navigateur à revalider le HTML afin qu'un ancien identifiant
        # de bouton ou une ancienne URL app.js ne reste pas bloqué dans le cache.
        return FileResponse(
            static_dir / "index.html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    return app
