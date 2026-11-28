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
from studio.web.highlights import HighlightScanner, select_distinct_highlight_candidates
from studio.web.best_of import build_best_of_plan, render_best_of_episode

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
    brand_enabled: bool, hook_text: str, context_text: str,
    auto_trim_enabled: bool = True, sfx_enabled: bool = True,
    captions_enabled: bool = False, caption_language: str = "config",
) -> dict:
    if layout == "smart":
        layout = "blur"
    if layout not in {"fill", "blur"}:
        raise HTTPException(status_code=400, detail="Le cadrage doit être 'fill' ou 'blur'.")
    if not 0 <= int(crop_x) <= 100 or not 0 <= int(crop_y) <= 100:
        raise HTTPException(status_code=400, detail="La position du cadrage doit être comprise entre 0 et 100.")
    if not 0 <= int(zoom_percent) <= 20:
        raise HTTPException(status_code=400, detail="Le zoom doit être compris entre 0 et 20 %.")
    normalized_caption_language = str(caption_language or "config").strip().lower()
    if normalized_caption_language not in {"config", "auto", "en", "fr", "es", "pt", "de"}:
        raise HTTPException(
            status_code=400,
            detail="Langue des sous-titres invalide. Choisis le réglage du Studio, auto, anglais, français, espagnol, portugais ou allemand.",
        )
    return {
        "layout": layout, "crop_x": int(crop_x), "crop_y": int(crop_y),
        "dynamic_zoom": bool(dynamic_zoom), "zoom_percent": int(zoom_percent),
        "brand_enabled": bool(brand_enabled),
        "auto_trim_enabled": bool(auto_trim_enabled), "sfx_enabled": bool(sfx_enabled),
        "captions_enabled": bool(captions_enabled),
        "caption_language": normalized_caption_language,
        "hook_text": str(hook_text or "").strip()[:100],
        "context_text": str(context_text or "").strip()[:150],
    }


def _require_whisper_ready(config: AppConfig, model_manager: ModelManager) -> None:
    """Reject an opt-in caption request before any upload or Twitch download is queued."""
    whisper_cli = config.path_for("executables", "whisper_cli")
    if not whisper_cli.is_file():
        raise HTTPException(
            status_code=409,
            detail="Installe d'abord le moteur whisper.cpp dans Paramètres pour générer les sous-titres.",
        )
    if not model_manager.status().get("valid"):
        raise HTTPException(
            status_code=409,
            detail="Télécharge d'abord le modèle Whisper large-v3-turbo (environ 1,6 Go) dans Paramètres.",
        )


def create_app(config_or_path: AppConfig | str | Path = "config.yaml") -> FastAPI:
    config = config_or_path if isinstance(config_or_path, AppConfig) else load_config(config_or_path)
    root = config.root
    inbox = config.path_for("paths", "inbox_shorts")
    outputs = config.path_for("paths", "output_shorts").parent
    static_dir = Path(__file__).parent / "static"
    inbox.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    store = Store(config.path_for("paths", "database"))
    store.recover_interrupted_best_of_jobs()
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
    app.state.best_of_lock = threading.Lock()
    app.state.runner = runner
    app.state.model_manager = model_manager
    app.state.update_service = update_service
    app.state.highlight_scanner = highlight_scanner
    app.state.project_root = root
    app.state.uvicorn_server = None
    def _best_of_job_payload(job: dict) -> dict:
        output_path_value = str(job.get("output_path") or "")
        output_path = Path(output_path_value) if output_path_value else None
        file_available = bool(output_path and output_path.is_file())
        output_url = job.get("output_url") if file_available else None
        message = str(job.get("message") or "")
        if job.get("status") == "completed" and not file_available:
            message = "Le rendu est terminé, mais le fichier exporté est introuvable sur ce PC."
        return {
            "id": job["id"],
            "status": job["status"],
            "progress": int(job.get("progress") or 0),
            "message": message,
            "date_key": job.get("date_key") or "",
            "clip_count": int(job.get("clip_count") or 0),
            "total_duration": float(job.get("total_duration") or 0),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            "output_url": output_url,
            "file_available": file_available,
            "error": job.get("error"),
            "result": job.get("result") or {},
        }


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
        batch_groups: dict[str, list[dict]] = {}
        for scan in scans:
            scan["candidates"] = store.list_highlight_candidates(scan["id"])
            batch_id = str(scan.get("metadata", {}).get("batch_id") or "")
            if batch_id:
                batch_groups.setdefault(batch_id, []).append(scan)

        for batch_id, members in batch_groups.items():
            expected_count = int(members[0].get("metadata", {}).get("batch_count") or 0)
            if expected_count <= 1 or len(members) != expected_count:
                continue
            members.sort(key=lambda item: int(item.get("metadata", {}).get("batch_index") or 0))
            candidates = []
            for member in members:
                for candidate in member.get("candidates", []):
                    candidates.append({**candidate, "scan_id": member["id"]})
            shortlist = select_distinct_highlight_candidates(candidates, max_candidates=30)
            terminal_statuses = {"completed", "error", "cancelled"}
            completed = sum(member["status"] == "completed" for member in members)
            errors = sum(member["status"] == "error" for member in members)
            cancelled = sum(member["status"] == "cancelled" for member in members)
            progress_values = [
                100.0 if member["status"] in terminal_statuses
                else max(0.0, min(100.0, float(member.get("progress") or 0.0)))
                for member in members
            ]
            summary = {
                "batch_id": batch_id,
                "total": len(members),
                "completed": completed,
                "errors": errors,
                "cancelled": cancelled,
                "queued": sum(member["status"] == "queued" for member in members),
                "running": sum(member["status"] in {"running", "cancelling"} for member in members),
                "progress": round(sum(progress_values) / len(progress_values)),
                "source_title": next((member.get("source_title") for member in members if member.get("source_title")), None),
                "source_url": members[0].get("source_url"),
                "streamer": members[0].get("streamer"),
                "scans": [
                    {
                        "id": member["id"],
                        "status": member["status"],
                        "progress": member.get("progress", 0),
                        "window_start": member.get("window_start"),
                        "window_end": member.get("window_end"),
                        "error": member.get("error"),
                        "message": member.get("message"),
                    }
                    for member in members
                ],
                "candidates": shortlist,
            }
            anchor = next((member for member in members if int(member.get("metadata", {}).get("batch_index") or 0) == 1), None)
            if anchor is not None:
                anchor["batch_summary"] = summary
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
        if len(clean) > 2000:
            raise HTTPException(status_code=400, detail="URL trop longue. Utilise une URL Twitch publique valide.")
        parsed = urlparse(clean)
        host = (parsed.hostname or "").lower()
        allowed_hosts = {"twitch.tv", "www.twitch.tv", "m.twitch.tv", "clips.twitch.tv"}
        if parsed.scheme != "https" or host not in allowed_hosts:
            raise HTTPException(status_code=400, detail="Utilise une URL Twitch publique de VOD ou de clip (https://www.twitch.tv/...).")
        if not ("/videos/" in parsed.path or "/clip/" in parsed.path or host == "clips.twitch.tv"):
            raise HTTPException(status_code=400, detail="Colle une URL de VOD Twitch ou de clip Twitch, pas une page de chaîne.")
        return clean

    def _parse_optional_seconds(value: str | None, field_name: str) -> float | None:
        """Parse seconds or a human-readable HH:MM:SS timecode."""
        if value is None or not str(value).strip():
            return None
        raw = str(value).strip()
        try:
            if ":" in raw:
                parts = raw.split(":")
                if len(parts) != 3:
                    raise ValueError("timecode must use HH:MM:SS")
                hours_text, minutes_text, seconds_text = parts
                if not hours_text.isdigit() or not minutes_text.isdigit():
                    raise ValueError("hours and minutes must be whole numbers")
                hours = int(hours_text)
                minutes = int(minutes_text)
                seconds = float(seconds_text)
                if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
                    raise ValueError("timecode component out of range")
                parsed = hours * 3600 + minutes * 60 + seconds
            else:
                parsed = float(raw)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} doit être un nombre de secondes ou un horaire au format HH:MM:SS.",
            ) from exc
        if not math.isfinite(parsed):
            raise HTTPException(status_code=400, detail=f"{field_name} doit être un nombre valide.")
        return parsed



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
    ) -> dict:
        if not rights_confirmed:
            raise HTTPException(status_code=400, detail="Confirme que tu disposes des droits ou autorisations nécessaires pour analyser cette source.")
        clean_url = _validate_twitch_source(url)
        start = _parse_optional_seconds(window_start, "Début")
        end = _parse_optional_seconds(window_end, "Fin")
        start, end = _validate_highlight_window(start, end)
        scan_id = uuid.uuid4().hex
        store.create_highlight_scan({
            "id": scan_id, "source_kind": "url", "source_url": clean_url,
            "streamer": streamer.strip()[:120], "message": "VOD/clip ajouté à la file d'analyse",
            "window_start": start, "window_end": end, "rights_confirmed": True,
            "metadata": {"note": note.strip()[:1000]},
        })
        highlight_scanner.submit(scan_id)
        return {"id": scan_id, "status": "queued", "message": "Source Twitch ajoutée à l'analyse des moments forts."}

    @app.post("/api/highlights/scan/url/batch", status_code=202)
    def scan_highlight_url_batch(
        url: Annotated[str, Form()],
        window_start: Annotated[str | None, Form()] = None,
        window_end: Annotated[str | None, Form()] = None,
        chunk_minutes: Annotated[str, Form()] = "60",
        streamer: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
        rights_confirmed: Annotated[bool, Form()] = False,
    ) -> dict:
        """Queue a long Twitch VOD range as independent scans of at most three hours."""
        if not rights_confirmed:
            raise HTTPException(status_code=400, detail="Confirme que tu disposes des droits ou autorisations nécessaires pour analyser cette source.")
        clean_url = _validate_twitch_source(url)
        from urllib.parse import urlparse
        if "/videos/" not in urlparse(clean_url).path:
            raise HTTPException(
                status_code=400,
                detail="Le découpage en lot est réservé aux VOD Twitch, pas aux clips courts.",
            )
        start = _parse_optional_seconds(window_start, "Début")
        end = _parse_optional_seconds(window_end, "Fin")
        if start is None or end is None:
            raise HTTPException(status_code=400, detail="Pour créer un lot, renseigne le début et la fin de la plage complète.")
        if start < 0 or end <= start:
            raise HTTPException(status_code=400, detail="La plage complète doit avoir un début positif et une fin supérieure au début.")
        try:
            chunk_size_minutes = int(chunk_minutes)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Choisis une durée de tranche valide.") from exc
        allowed_chunk_sizes = {30, 45, 60, 90, 120, 180}
        if chunk_size_minutes not in allowed_chunk_sizes:
            raise HTTPException(
                status_code=400,
                detail="La durée de tranche doit être de 30, 45, 60, 90, 120 ou 180 minutes.",
            )
        chunk_seconds = chunk_size_minutes * 60
        segment_count = math.ceil((end - start) / chunk_seconds)
        max_segments = 48
        if segment_count <= 0:
            raise HTTPException(status_code=400, detail="La plage complète est invalide.")
        if segment_count > max_segments:
            raise HTTPException(
                status_code=400,
                detail=f"Ce lot créerait {segment_count} analyses. La limite est de {max_segments} tranches par lot ; augmente la durée de chaque tranche.",
            )

        batch_id = uuid.uuid4().hex
        scans = []
        cursor = start
        for index in range(segment_count):
            segment_end = min(end, cursor + chunk_seconds)
            scans.append({
                "id": uuid.uuid4().hex,
                "source_kind": "url",
                "source_url": clean_url,
                "streamer": streamer.strip()[:120],
                "message": f"Tranche {index + 1}/{segment_count} ajoutée à la file d'analyse",
                "window_start": round(cursor, 3),
                "window_end": round(segment_end, 3),
                "rights_confirmed": True,
                "metadata": {
                    "note": note.strip()[:1000],
                    "batch_id": batch_id,
                    "batch_index": index + 1,
                    "batch_count": segment_count,
                    "batch_chunk_seconds": chunk_seconds,
                },
            })
            cursor = segment_end

        # Start before inserting the new queued rows. On its first start,
        # the scanner recovers queued rows from the database; doing this after
        # the batch insert would enqueue each new scan twice.
        highlight_scanner.start()
        store.create_highlight_scans(scans)
        for scan in scans:
            highlight_scanner.submit(scan["id"])
        return {
            "batch_id": batch_id,
            "count": segment_count,
            "message": f"{segment_count} tranches ajoutées à la file d'analyse.",
            "scans": [
                {
                    "id": scan["id"],
                    "index": scan["metadata"]["batch_index"],
                    "start": scan["window_start"],
                    "end": scan["window_end"],
                }
                for scan in scans
            ],
        }

    @app.post("/api/highlights/scan/upload", status_code=202)
    async def scan_highlight_upload(
        file: Annotated[UploadFile, File(...)],
        streamer: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
        rights_confirmed: Annotated[bool, Form()] = False,
        window_start: Annotated[str | None, Form()] = None,
        window_end: Annotated[str | None, Form()] = None,
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
            "rights_confirmed": True, "metadata": {"note": note.strip()[:1000], "file_size": written},
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
        max_short_seconds = float(config.get("shorts", "max_input_duration_seconds", default=165))
        if media_end <= media_start or media_end - media_start > max_short_seconds:
            raise HTTPException(status_code=409, detail="La durée du passage candidat est invalide pour un Short.")
        job_id = uuid.uuid4().hex
        options = {
            "layout": "blur", "crop_x": 80, "crop_y": 50, "dynamic_zoom": False, "zoom_percent": 0,
            "brand_enabled": False, "auto_trim_enabled": False, "sfx_enabled": True,
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
        if original.get("status") not in {"validated", "ready", "error", "rejected", "cancelled"}:
            raise HTTPException(status_code=409, detail="Ce job est encore en cours de traitement.")

        # A batch slot has one current attempt. If a retry was already created,
        # require subsequent retries to start from that newest job, avoiding
        # duplicate queue entries after a slow response or a repeated click.
        batch_id = original.get("batch_id")
        metadata = original.get("metadata") or {}
        try:
            batch_index = int(metadata.get("batch_index") or 0)
        except (TypeError, ValueError):
            batch_index = 0
        if batch_id and batch_index > 0:
            latest_attempt = None
            for candidate in store.list_batch_jobs(str(batch_id)):
                candidate_metadata = candidate.get("metadata") or {}
                try:
                    candidate_index = int(candidate_metadata.get("batch_index") or 0)
                except (TypeError, ValueError):
                    continue
                if candidate_index == batch_index:
                    latest_attempt = candidate
            if latest_attempt and latest_attempt["id"] != job_id:
                raise HTTPException(
                    status_code=409,
                    detail="Une tentative plus récente existe déjà pour ce clip. Relance la dernière tentative depuis le suivi du lot.",
                )

        source_value = original.get("source_path")
        source_path = Path(source_value) if source_value else None
        source_url = str(original.get("source_url") or "").strip()
        if source_path is not None and source_path.is_file():
            # Réutiliser le média déjà téléchargé : aucun transfert inutile.
            source_payload = {
                "source_kind": "upload",
                "source_path": str(source_path.resolve()),
                "source_url": source_url or None,
                "source_title": original.get("source_title") or source_path.stem,
            }
            message = "Nouveau rendu demandé à partir du média déjà importé"
            success_message = "Nouveau traitement lancé à partir du média déjà importé."
        elif source_url:
            # Si le téléchargement Twitch a échoué avant de conserver le fichier,
            # permettre une vraie nouvelle tentative depuis l'URL d'origine.
            source_payload = {
                "source_kind": "url",
                "source_url": _validate_twitch_source(source_url),
                "source_title": original.get("source_title") or "",
            }
            message = "Nouvelle tentative de téléchargement Twitch"
            success_message = "Nouvelle tentative de téléchargement Twitch ajoutée à la file."
        elif source_path is not None:
            raise HTTPException(status_code=409, detail="Le fichier source n'existe plus dans le dossier d'import.")
        else:
            raise HTTPException(status_code=409, detail="La source locale ou l'URL Twitch d'origine n'est plus disponible.")
        new_id = uuid.uuid4().hex
        metadata = dict(original.get("metadata") or {})
        # Les résultats du précédent rendu ne doivent pas être réutilisés comme
        # s'ils provenaient du nouveau traitement.
        for key in (
            "title", "description", "transcription_status", "transcription_timestamp_mode",
            "transcribed_words", "transcription_warning", "captions_enabled", "captions_path", "transcript",
        ):
            metadata.pop(key, None)
        store.create_job({
            "id": new_id,
            "kind": original.get("kind", "short"),
            "batch_id": original.get("batch_id"),
            **source_payload,
            "streamer": original.get("streamer", ""),
            "note": original.get("note", ""),
            "rights_confirmed": True,
            "message": message,
            "metadata": metadata,
        })
        runner.submit(new_id)
        return {"id": new_id, "status": "queued", "message": success_message}

    @app.post("/api/shorts/upload", status_code=202)
    async def upload_short(
        file: Annotated[UploadFile, File(...)],
        streamer: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
        rights_confirmed: Annotated[bool, Form()] = False,
        layout: Annotated[str, Form()] = "blur",
        crop_x: Annotated[int, Form()] = 80,
        crop_y: Annotated[int, Form()] = 50,
        dynamic_zoom: Annotated[bool, Form()] = False,
        zoom_percent: Annotated[int, Form()] = 8,
        brand_enabled: Annotated[bool, Form()] = False,
        auto_trim_enabled: Annotated[bool, Form()] = True,
        sfx_enabled: Annotated[bool, Form()] = True,
        captions_enabled: Annotated[bool, Form()] = False,
        caption_language: Annotated[str, Form()] = "config",
        hook_text: Annotated[str, Form()] = "",
        context_text: Annotated[str, Form()] = "",
    ) -> dict:
        if not rights_confirmed:
            raise HTTPException(status_code=400, detail="Confirme que tu disposes des droits ou autorisations nécessaires pour utiliser ce clip.")
        if captions_enabled:
            _require_whisper_ready(config, model_manager)
        options = _validate_edit_options(
            layout, crop_x, crop_y, dynamic_zoom, zoom_percent, brand_enabled,
            hook_text, context_text, auto_trim_enabled, sfx_enabled, captions_enabled,
            caption_language,
        )
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
        layout: Annotated[str, Form()] = "blur",
        crop_x: Annotated[int, Form()] = 80,
        crop_y: Annotated[int, Form()] = 50,
        dynamic_zoom: Annotated[bool, Form()] = False,
        zoom_percent: Annotated[int, Form()] = 8,
        brand_enabled: Annotated[bool, Form()] = False,
        auto_trim_enabled: Annotated[bool, Form()] = True,
        sfx_enabled: Annotated[bool, Form()] = True,
        captions_enabled: Annotated[bool, Form()] = False,
        caption_language: Annotated[str, Form()] = "config",
        hook_text: Annotated[str, Form()] = "",
        context_text: Annotated[str, Form()] = "",
    ) -> dict:
        if not rights_confirmed:
            raise HTTPException(status_code=400, detail="Confirme que tu disposes des droits ou autorisations nécessaires pour utiliser cette source.")
        clean_url = _validate_twitch_source(url)
        job_id = uuid.uuid4().hex
        if captions_enabled:
            _require_whisper_ready(config, model_manager)
        options = _validate_edit_options(
            layout, crop_x, crop_y, dynamic_zoom, zoom_percent, brand_enabled,
            hook_text, context_text, auto_trim_enabled, sfx_enabled, captions_enabled,
            caption_language,
        )
        store.create_job({
            "id": job_id, "source_kind": "url", "source_url": clean_url,
            "streamer": streamer.strip()[:120], "note": note.strip()[:1000],
            "rights_confirmed": rights_confirmed, "message": "URL ajoutée à la file d'attente",
            "metadata": {"options": options},
        })
        runner.submit(job_id)
        return {"id": job_id, "status": "queued", "message": "URL ajoutée à la file de traitement."}


    @app.post("/api/shorts/url/batch", status_code=202)
    def create_shorts_from_urls(
        urls: Annotated[str, Form()],
        streamer: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
        rights_confirmed: Annotated[bool, Form()] = False,
        layout: Annotated[str, Form()] = "blur",
        crop_x: Annotated[int, Form()] = 80,
        crop_y: Annotated[int, Form()] = 50,
        dynamic_zoom: Annotated[bool, Form()] = False,
        zoom_percent: Annotated[int, Form()] = 8,
        brand_enabled: Annotated[bool, Form()] = False,
        auto_trim_enabled: Annotated[bool, Form()] = True,
        sfx_enabled: Annotated[bool, Form()] = True,
        captions_enabled: Annotated[bool, Form()] = False,
        caption_language: Annotated[str, Form()] = "config",
        hook_text: Annotated[str, Form()] = "",
        context_text: Annotated[str, Form()] = "",
    ) -> dict:
        """Queue up to ten Twitch URLs and expose durable batch progress."""
        if not rights_confirmed:
            raise HTTPException(status_code=400, detail="Confirme que tu disposes des droits ou autorisations nécessaires pour utiliser ces sources.")
        raw_urls = [line.strip() for line in str(urls or "").splitlines() if line.strip()]
        unique_urls = list(dict.fromkeys(raw_urls))
        if not unique_urls:
            raise HTTPException(status_code=400, detail="Colle au moins une URL Twitch.")
        if len(unique_urls) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 URLs par lot. Divise ta liste en plusieurs lots.")
        if captions_enabled:
            _require_whisper_ready(config, model_manager)
        options = _validate_edit_options(
            layout, crop_x, crop_y, dynamic_zoom, zoom_percent, brand_enabled,
            hook_text, context_text, auto_trim_enabled, sfx_enabled, captions_enabled,
            caption_language,
        )
        validated_urls: list[str] = []
        rejected: list[dict[str, str]] = []
        clean_seen: set[str] = set()
        for raw_url in unique_urls:
            try:
                clean_url = _validate_twitch_source(raw_url)
                if clean_url not in clean_seen:
                    clean_seen.add(clean_url)
                    validated_urls.append(clean_url)
            except HTTPException as exc:
                rejected.append({"url": raw_url[:200], "reason": str(exc.detail)})
        if not validated_urls:
            reasons = "; ".join(item["reason"] for item in rejected[:3])
            raise HTTPException(status_code=400, detail=f"Aucune URL Twitch valide. {reasons}")

        batch_id = uuid.uuid4().hex
        created: list[dict[str, str]] = []
        for index, clean_url in enumerate(validated_urls, start=1):
            job_id = uuid.uuid4().hex
            store.create_job({
                "id": job_id,
                "batch_id": batch_id,
                "source_kind": "url",
                "source_url": clean_url,
                "streamer": streamer.strip()[:120],
                "note": note.strip()[:1000],
                "rights_confirmed": rights_confirmed,
                "message": "URL ajoutée au lot de traitement",
                "metadata": {
                    "options": options,
                    "batch_import": True,
                    "batch_index": index,
                    "batch_count": len(validated_urls),
                },
            })
            created.append({"id": job_id, "url": clean_url, "status": "queued"})
        # Persist the complete batch before submitting jobs, so its progress
        # endpoint can always return a consistent total.
        for job in created:
            runner.submit(job["id"])
        return {
            "batch_id": batch_id,
            "created_count": len(created),
            "rejected_count": len(rejected),
            "jobs": created,
            "rejected": rejected,
            "message": f"{len(created)} Short(s) ajouté(s) à la file." + (f" {len(rejected)} URL(s) ignorée(s)." if rejected else ""),
        }

    @app.get("/api/shorts/batches/{batch_id}")
    def get_short_batch_progress(batch_id: str) -> dict:
        """Return durable aggregate progress for a Twitch Short import batch."""
        if not re.fullmatch(r"[a-f0-9]{32}", batch_id):
            raise HTTPException(status_code=400, detail="Identifiant de lot invalide.")
        all_jobs = store.list_batch_jobs(batch_id)
        if not all_jobs:
            raise HTTPException(status_code=404, detail="Lot Twitch introuvable.")

        # A retry is a new durable job, but it still represents the same clip
        # in the original batch. Keep only the newest attempt for each slot so
        # totals and progress do not grow when a failed clip is retried.
        attempt_counts: dict[str, int] = {}
        latest_by_slot: dict[str, dict] = {}
        for job in all_jobs:
            metadata = job.get("metadata") or {}
            try:
                batch_index = int(metadata.get("batch_index") or 0)
            except (TypeError, ValueError):
                batch_index = 0
            slot = f"index:{batch_index}" if batch_index > 0 else f"job:{job['id']}"
            attempt_counts[slot] = attempt_counts.get(slot, 0) + 1
            latest_by_slot[slot] = job

        batch_entries = list(latest_by_slot.items())
        jobs = [job for _, job in batch_entries]
        attempts_by_job_id = {
            job["id"]: attempt_counts[slot] for slot, job in batch_entries
        }
        active_statuses = {"queued", "running", "cancelling"}
        terminal_statuses = {"ready", "validated", "rejected", "error", "cancelled"}
        failed_statuses = {"error"}
        total = len(jobs)
        active_count = sum(job["status"] in active_statuses for job in jobs)
        completed_count = sum(job["status"] in terminal_statuses for job in jobs)
        ready_count = sum(job["status"] == "ready" for job in jobs)
        validated_count = sum(job["status"] == "validated" for job in jobs)
        failed_count = sum(job["status"] in failed_statuses for job in jobs)
        cancelled_count = sum(job["status"] == "cancelled" for job in jobs)
        rejected_count = sum(job["status"] == "rejected" for job in jobs)
        progress_total = sum(
            100 if job["status"] in terminal_statuses
            else max(0, min(100, int(job.get("progress") or 0)))
            for job in jobs
        )
        status = (
            "running" if active_count
            else "completed_with_errors" if failed_count
            else "completed"
        )
        if active_count:
            message = f"{completed_count}/{total} traités · {ready_count} à valider · {failed_count} échec(s)"
        elif failed_count:
            message = f"Lot terminé · {ready_count} prêt(s) à valider · {failed_count} échec(s)"
        else:
            message = f"Lot terminé · {ready_count} prêt(s) à valider · {validated_count} validé(s)"
        if cancelled_count:
            message += f" · {cancelled_count} annulation(s)"
        return {
            "batch_id": batch_id,
            "status": status,
            "total": total,
            "completed_count": completed_count,
            "active_count": active_count,
            "ready_count": ready_count,
            "validated_count": validated_count,
            "failed_count": failed_count,
            "cancelled_count": cancelled_count,
            "rejected_count": rejected_count,
            "progress": round(progress_total / total),
            "message": message,
            "jobs": [
                {
                    "id": job["id"],
                    "status": job["status"],
                    "progress": int(job.get("progress") or 0),
                    "message": job.get("message") or "",
                    "title": job.get("source_title") or job.get("streamer") or job.get("source_url") or "Clip Twitch",
                    "error": job.get("error"),
                    "batch_index": (job.get("metadata") or {}).get("batch_index"),
                    "attempts": attempts_by_job_id[job["id"]],
                    "retryable": (
                        job["status"] in {"error", "cancelled", "rejected"}
                        and (
                            bool(job.get("source_url"))
                            or bool(job.get("source_path") and Path(str(job["source_path"])).is_file())
                        )
                    ),
                }
                for job in jobs
            ],
        }

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

    @app.post("/api/bestof/plan")
    def create_best_of_plan(payload: dict) -> dict:
        """Validate an ordered episode selection without modifying source clips."""
        clip_ids = payload.get("clip_ids") if isinstance(payload, dict) else None
        date_key = payload.get("date_key") if isinstance(payload, dict) else None
        if date_key is not None:
            date_key = str(date_key).strip()
            if len(date_key) != 10:
                raise HTTPException(status_code=400, detail="La date de l'épisode est invalide.")
        try:
            return build_best_of_plan(
                store.list_clips(200),
                clip_ids,
                date_key=date_key or None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


    @app.get("/api/bestof/jobs")
    def list_best_of_jobs(limit: int = 10) -> list[dict]:
        return [_best_of_job_payload(job) for job in store.list_best_of_jobs(limit)]

    @app.post("/api/bestof/render", status_code=202)
    def render_best_of(payload: dict) -> dict:
        """Queue a validated Daily Best Of render and persist its lifecycle."""
        clip_ids = payload.get("clip_ids") if isinstance(payload, dict) else None
        date_key = payload.get("date_key") if isinstance(payload, dict) else None
        if date_key is not None:
            date_key = str(date_key).strip()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_key):
                raise HTTPException(status_code=400, detail="La date de l'épisode est invalide.")
        retry_of_job_id = str(payload.get("retry_of_job_id") or "").strip() if isinstance(payload, dict) else ""
        if retry_of_job_id and not re.fullmatch(r"[a-f0-9]{32}", retry_of_job_id):
            raise HTTPException(status_code=400, detail="La référence de relance Best Of est invalide.")
        try:
            plan = build_best_of_plan(store.list_clips(200), clip_ids, date_key=date_key or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not plan.get("ready_for_render"):
            raise HTTPException(status_code=400, detail="La sélection doit durer entre 9 et 11 minutes.")
        with app.state.best_of_lock:
            active_job = store.get_active_best_of_job()
            if active_job is not None:
                active_id = str(active_job.get("id") or "")[:8]
                raise HTTPException(
                    status_code=409,
                    detail=f"Un rendu Daily Best Of est déjà en cours ({active_id}). Attends sa fin avant d'en lancer un autre.",
                )
            job_id = uuid.uuid4().hex
            date_folder = str(plan.get("date_key") or "episode")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_folder):
                date_folder = "episode"
            output_dir = outputs / "bestof" / date_folder
            output_path = output_dir / f"daily-best-of-{job_id[:8]}.mp4"
            stored_plan = {**plan, "retry_of_job_id": retry_of_job_id} if retry_of_job_id else plan
            store.create_best_of_job({
                "id": job_id,
                "status": "queued",
                "progress": 0,
                "message": "Épisode en attente de rendu",
                "date_key": plan.get("date_key"),
                "clip_count": plan.get("clip_count"),
                "total_duration": plan.get("total_duration"),
                "plan": stored_plan,
                "output_path": str(output_path),
            })

        def _run_best_of() -> None:
            store.update_best_of_job(
                job_id, status="running", progress=4,
                message="Préparation du Daily Best Of",
            )

            def _progress_callback(progress: int, message: str) -> None:
                store.update_best_of_job(
                    job_id, progress=progress, message=message,
                )

            try:
                ffmpeg_bin = str(config.get("executables", "ffmpeg", default="ffmpeg"))
                ffprobe_bin = str(config.get("executables", "ffprobe", default="ffprobe"))
                encoder_check = run_quiet(
                    [ffmpeg_bin, "-hide_banner", "-encoders"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=12, check=False,
                )
                encoder = (
                    "h264_amf"
                    if encoder_check.returncode == 0 and "h264_amf" in (encoder_check.stdout + encoder_check.stderr)
                    else "libx264"
                )
                result = render_best_of_episode(
                    plan, output_path, ffmpeg=ffmpeg_bin, ffprobe=ffprobe_bin,
                    encoder=encoder, progress_callback=_progress_callback,
                )
                relative = output_path.relative_to(outputs).as_posix()
                store.update_best_of_job(
                    job_id, status="completed", progress=100, message="Daily Best Of prêt",
                    output_url=f"/outputs/{relative}", result_json=result, error=None,
                )
            except Exception as exc:
                logger.exception("Échec du Daily Best Of %s", job_id)
                error_message = str(exc)[:500]
                store.update_best_of_job(
                    job_id, status="error", progress=100,
                    message="Le rendu Daily Best Of a échoué", error=error_message,
                )

        thread = threading.Thread(
            target=_run_best_of, name=f"bestof-{job_id[:8]}", daemon=True,
        )
        try:
            thread.start()
        except Exception as exc:
            logger.exception("Démarrage du Daily Best Of %s impossible", job_id)
            store.update_best_of_job(
                job_id, status="error", progress=100,
                message="Le rendu Daily Best Of n'a pas pu démarrer", error=str(exc)[:500],
            )
            raise HTTPException(status_code=500, detail="Le rendu Daily Best Of n'a pas pu démarrer.") from exc
        return {"id": job_id, "status": "queued", "message": "Rendu Daily Best Of lancé."}

    @app.post("/api/bestof/jobs/{job_id}/retry", status_code=202)
    def retry_best_of_job(job_id: str) -> dict:
        """Requeue an interrupted/failed episode from its stored source selection."""
        previous = store.get_best_of_job(job_id)
        if previous is None:
            raise HTTPException(status_code=404, detail="Rendu Daily Best Of introuvable.")
        if previous.get("status") != "error":
            raise HTTPException(
                status_code=409,
                detail="Seuls les rendus interrompus ou en erreur peuvent être relancés.",
            )
        previous_plan = previous.get("plan") or {}
        clip_ids = [
            str(clip.get("id") or "").strip()
            for clip in previous_plan.get("clips", [])
            if isinstance(clip, dict) and str(clip.get("id") or "").strip()
        ]
        if not clip_ids:
            raise HTTPException(
                status_code=409,
                detail="La sélection d'origine n'est plus disponible pour cette relance.",
            )
        already_retried = any(
            (candidate.get("plan") or {}).get("retry_of_job_id") == job_id
            and candidate.get("status") in {"queued", "running", "completed"}
            for candidate in store.list_best_of_jobs(50)
        )
        if already_retried:
            raise HTTPException(
                status_code=409,
                detail="Une relance de cet épisode est déjà en cours ou a déjà abouti.",
            )
        return render_best_of({
            "clip_ids": clip_ids,
            "date_key": previous.get("date_key") or previous_plan.get("date_key"),
            "retry_of_job_id": job_id,
        })

    @app.get("/api/bestof/jobs/{job_id}")
    def get_best_of_job(job_id: str) -> dict:
        job = store.get_best_of_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Rendu Daily Best Of introuvable.")
        return _best_of_job_payload(job)

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
