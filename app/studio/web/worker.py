"""File de traitement locale : téléchargement et montage des Shorts."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import queue
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from studio.config import AppConfig
from studio.process import ProcessingCancelled, check_cancelled, set_current_cancel_event
from studio.web.metadata import generate_short_metadata
from studio.web.short_editor import (
    apply_thumbnail_overlay, create_ass_file, infer_hook_style,
    select_thumbnail_timestamp, select_excerpt_range,
)
from studio.web.short_renderer import MediaError, create_hook_sound_effect, probe_media, render_vertical_short
from studio.web.export_quality import analyze_export_quality
from studio.web.store import Store
from studio.web.transcribe import (
    TranscriptionError,
    analyze_audio_peaks,
    extract_audio_wav,
)

logger = logging.getLogger(__name__)


def _download_metrics_suffix(data: dict[str, Any]) -> str:
    """Format optional yt-dlp transfer speed and ETA for the live job message."""
    metrics: list[str] = []
    try:
        speed = float(data.get("speed"))
    except (TypeError, ValueError, OverflowError):
        speed = 0.0
    if speed > 0 and math.isfinite(speed):
        if speed >= 1024 * 1024:
            metrics.append(f"{speed / (1024 * 1024):.1f} MiB/s")
        elif speed >= 1024:
            metrics.append(f"{speed / 1024:.0f} KiB/s")
        else:
            metrics.append(f"{speed:.0f} B/s")

    try:
        eta = float(data.get("eta"))
    except (TypeError, ValueError, OverflowError):
        eta = -1.0
    if math.isfinite(eta) and 0 <= eta <= 365 * 24 * 60 * 60:
        seconds = int(round(eta))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        formatted_eta = (
            f"{hours:d}:{minutes:02d}:{seconds:02d}"
            if hours else f"{minutes:02d}:{seconds:02d}"
        )
        metrics.append(f"reste {formatted_eta}")

    return " · " + " · ".join(metrics) if metrics else ""


def _download_size_suffix(data: dict[str, Any]) -> str:
    """Format downloaded and total bytes as a compact progress suffix."""
    try:
        downloaded = max(0, int(data.get("downloaded_bytes") or 0))
        total = max(0, int(data.get("total_bytes") or data.get("total_bytes_estimate") or 0))
    except (TypeError, ValueError, OverflowError):
        return ""
    if downloaded <= 0:
        return ""
    mib = 1024 * 1024
    if total > 0:
        return f" · {downloaded / mib:.1f}/{total / mib:.1f} MiB"
    return f" · {downloaded / mib:.1f} MiB"


def _metadata_text(info: dict[str, Any], *keys: str) -> str:
    """Return the first useful yt-dlp metadata value without leaking null-like text."""
    for key in keys:
        value = info.get(key)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned[:240]
    return ""


def extract_twitch_source_metadata(info: dict[str, Any]) -> tuple[str, str]:
    """Extract the clip/VOD title and the broadcaster, not the clip creator.

    Twitch clip metadata can distinguish the broadcaster (channel) from the
    account that created the clip (uploader/creator). Prefer channel fields.
    """
    title = _metadata_text(info, "title", "fulltitle", "alt_title")
    if not title:
        source_id = _metadata_text(info, "display_id", "id")
        title = f"Twitch source {source_id}" if source_id else "Source Twitch"

    streamer = _metadata_text(
        info, "channel", "channel_name", "broadcaster_name", "uploader", "uploader_id"
    )
    return title, streamer


def _needs_audio_analysis(
    has_audio: bool,
    duration: float,
    *,
    dynamic_zoom: bool,
    auto_trim: bool,
    trim_threshold_seconds: float = 45.0,
) -> bool:
    """Avoid extracting a full WAV when neither zoom nor long-source trimming needs it."""
    return bool(has_audio and (
        dynamic_zoom or (auto_trim and float(duration) > max(0.0, trim_threshold_seconds))
    ))


def safe_slug(value: str, fallback: str = "gta-clip") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-_")
    return cleaned[:70] or fallback


class JobRunner:
    def __init__(self, config: AppConfig, store: Store) -> None:
        self.config = config
        self.store = store
        self._queue: queue.Queue[str] = queue.Queue()
        self._started = False
        self._lock = threading.Lock()
        self._cancel_events: dict[str, threading.Event] = {}

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self.store.recover_interrupted_jobs()
            for job in self.store.list_jobs(500):
                if job["status"] == "queued":
                    self._queue.put(job["id"])
            thread = threading.Thread(target=self._run, name="gta-ranked-worker", daemon=True)
            thread.start()

    def submit(self, job_id: str) -> None:
        self.start()
        self._queue.put(job_id)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self.store.get_job(job_id)
            if not job or job.get("status") not in {"queued", "running"}:
                return False
            event = self._cancel_events.get(job_id)
            if job["status"] == "queued":
                if event is not None:
                    event.set()
                self.store.update_job(job_id, status="cancelled", message="Traitement annulé avant démarrage", error=None)
                return True
            if event is None:
                return False
            event.set()
            self.store.update_job(job_id, status="cancelling", message="Arrêt du traitement en cours…")
            return True

    def _process(self, job_id: str) -> None:
        event = threading.Event()
        with self._lock:
            self._cancel_events[job_id] = event
        set_current_cancel_event(event)
        try:
            check_cancelled()
            self._process_job(job_id)
        finally:
            set_current_cancel_event(None)
            with self._lock:
                self._cancel_events.pop(job_id, None)

    def _run(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._process(job_id)
            except Exception:
                logger.exception("Erreur inattendue pour le job %s", job_id)
                self.store.update_job(
                    job_id, status="error", progress=0,
                    message="Le traitement a échoué", error="Erreur interne. Consulte le journal local.",
                )
            finally:
                self._queue.task_done()

    def _process_job(self, job_id: str) -> None:
        with self._lock:
            job = self.store.get_job(job_id)
            if not job or job["status"] not in {"queued", "running"}:
                return
            self.store.update_job(job_id, status="running", progress=5, message="Préparation du clip", error=None)
        try:
            check_cancelled()
            source_path = Path(job["source_path"]) if job.get("source_path") else None
            source_url = job.get("source_url") or ""
            if source_path is None and source_url:
                self.store.update_job(job_id, progress=10, message="Téléchargement de la source")
                source_path, info = self._download(job_id, source_url)
                extracted_title, extracted_streamer = extract_twitch_source_metadata(info)
                job["source_title"] = job.get("source_title") or extracted_title
                job["streamer"] = job.get("streamer") or extracted_streamer
                job["source_path"] = str(source_path)
                source_hash = self._hash_file(source_path)
                duplicate = self.store.find_duplicate_hash(source_hash)
                if duplicate and duplicate["id"] != job_id:
                    raise MediaError(f"Cette vidéo a déjà été importée dans le job {duplicate['id'][:8]}.")
                job["source_hash"] = source_hash
                self.store.update_job(
                    job_id, source_path=str(source_path), source_title=job["source_title"],
                    streamer=job["streamer"], source_hash=source_hash,
                )
            if source_path is None or not source_path.is_file():
                raise MediaError("Fichier source introuvable après import.")

            options = (job.get("metadata") or {}).get("options", {})
            date_key = datetime.now().astimezone().strftime("%Y-%m-%d")
            slug = safe_slug(job.get("source_title") or job.get("streamer") or source_path.stem)
            output_dir = self.config.path_for("paths", "output_shorts") / date_key / f"{slug}-{job_id[:8]}"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "video.mp4"
            thumbnail_path = output_dir / "thumbnail.jpg"
            meta_path = output_dir / "meta.json"
            title_path = output_dir / "title.txt"
            description_path = output_dir / "description.txt"
            temp_dir = self.config.path_for("paths", "temp") / job_id
            temp_dir.mkdir(parents=True, exist_ok=True)

            self.store.update_job(job_id, progress=20, message="Analyse de la vidéo et de l'audio")
            source_info = probe_media(
                source_path, str(self.config.get("executables", "ffprobe", default="ffprobe"))
            )
            source_range = options.get("source_range") if isinstance(options, dict) else None
            if source_range:
                trim_start = max(0.0, float(source_range.get("start", 0.0)))
                trim_end = min(float(source_info["duration"]), float(source_range.get("end", source_info["duration"])))
                if trim_end <= trim_start or trim_end - trim_start > float(self.config.get("shorts", "max_input_duration_seconds", default=60)):
                    raise MediaError("La plage sélectionnée doit durer entre 0 et 60 secondes.")
                peak_timestamp = trim_start + (trim_end - trim_start) / 2
                auto_trim_enabled = False
            else:
                trim_start, trim_end = 0.0, float(source_info["duration"])
                peak_timestamp = source_info["duration"] / 2
                auto_trim_enabled = bool(options.get(
                    "auto_trim_enabled",
                    self.config.get("shorts", "auto_trim_enabled", default=True),
                ))
            dynamic_zoom_enabled = bool(options.get(
                "dynamic_zoom", self.config.get("shorts", "dynamic_zoom", default=True)
            ))
            audio_analysis_needed = _needs_audio_analysis(
                source_info["has_audio"],
                float(source_info["duration"]),
                dynamic_zoom=dynamic_zoom_enabled,
                auto_trim=auto_trim_enabled,
                trim_threshold_seconds=float(self.config.get(
                    "shorts", "peak_trim_threshold_seconds", default=45
                )),
            )
            audio_peak_timestamps: list[float] = []
            if audio_analysis_needed:
                audio_path = temp_dir / "audio-16k.wav"
                try:
                    extract_audio_wav(
                        source_path, audio_path,
                        ffmpeg=str(self.config.get("executables", "ffmpeg", default="ffmpeg")),
                        start_seconds=trim_start if source_range else None,
                        duration_seconds=(trim_end - trim_start) if source_range else None,
                    )
                    local_peak, audio_peak_timestamps = analyze_audio_peaks(audio_path)
                    peak_timestamp = (trim_start + local_peak) if source_range and local_peak else (local_peak or peak_timestamp)
                    if source_range:
                        audio_peak_timestamps = [trim_start + item for item in audio_peak_timestamps]

                except TranscriptionError as exc:
                    logger.warning("Analyse audio ignorée pour le job %s : %s", job_id, exc)

            if not source_range:
                trim_start, trim_end = 0.0, float(source_info["duration"])
            render_words: list[Any] = []
            render_peak_timestamp = max(0.0, peak_timestamp - trim_start)
            render_zoom_timestamps = [
                round(item - trim_start, 3)
                for item in audio_peak_timestamps
                if trim_start <= item <= trim_end
            ]
            if not render_zoom_timestamps:
                render_zoom_timestamps = [render_peak_timestamp]
            render_thumbnail_timestamp = select_thumbnail_timestamp(
                [], trim_end - trim_start, preferred=render_peak_timestamp
            )
            render_transcript = ""

            self.store.update_job(job_id, progress=48, message="Préparation du montage vertical")
            prompt_path = self.config.path_for("paths", "prompts") / "short_metadata.txt"
            metadata = generate_short_metadata(
                streamer=job.get("streamer", ""),
                note=job.get("note", ""),
                source_url=source_url,
                source_title=job.get("source_title", ""),
                transcript=render_transcript,
                custom_hook=str(options.get("hook_text", "")),
                custom_context=str(options.get("context_text", "")),
                ollama_base_url=str(self.config.get("ollama", "base_url", default="http://127.0.0.1:11434")),
                ollama_model=str(self.config.get("ollama", "model", default="qwen2.5:7b-instruct")),
                prompt_path=prompt_path,
                timeout=min(8, max(3, int(self.config.get("ollama", "request_timeout_seconds", default=8)))),
                retries=0,
            )
            check_cancelled()

            captions_active = False
            ass_path = temp_dir / "overlay.ass"
            create_ass_file(
                ass_path,
                words=render_words,
                hook_text=str(metadata.get("hook_text", "")),
                context_text=str(metadata.get("context_card", "")),
                handle=str(self.config.get("branding", "handle", default="@GTARankedStudio")),
                badge_text="GTA",
                width=int(self.config.get("encoding", "width_short", default=1080)),
                height=int(self.config.get("encoding", "height_short", default=1920)),
                font_name=str(self.config.get("branding", "font_name", default="Arial")),
                captions_enabled=captions_active,
                brand_enabled=bool(options.get("brand_enabled", True)),
                layout=str(options.get("layout", self.config.get("shorts", "layout", default="smart"))),
            )
            shutil.copy2(ass_path, output_dir / "overlay.ass")

            check_cancelled()
            hook_text = str(metadata.get("hook_text", ""))
            hook_context = str(metadata.get("context_card", ""))
            hook_sound_style = infer_hook_style(hook_text, hook_context)
            hook_sound_path = temp_dir / "hook-sound.wav"
            if bool(options.get("sfx_enabled", True)):
                create_hook_sound_effect(hook_sound_path, hook_sound_style)
            self.store.update_job(job_id, progress=60, message="Rendu vertical 9:16 plein écran et finitions")
            result = render_vertical_short(
                source_path, output_path, thumbnail_path,
                ffmpeg=str(self.config.get("executables", "ffmpeg", default="ffmpeg")),
                ffprobe=str(self.config.get("executables", "ffprobe", default="ffprobe")),
                preferred_encoder=str(self.config.get("encoding", "video_codec", default="h264_amf")),
                fallback_encoder=str(self.config.get("encoding", "fallback_video_codec", default="libx264")),
                max_duration=float(self.config.get("shorts", "max_input_duration_seconds", default=60)),
                bitrate=str(self.config.get("encoding", "amf_bitrate", default="12M")),
                loudness_lufs=int(self.config.get("encoding", "short_loudness_lufs", default=-14)),
                width=int(self.config.get("encoding", "width_short", default=1080)),
                height=int(self.config.get("encoding", "height_short", default=1920)),
                layout=str(options.get("layout", self.config.get("shorts", "layout", default="smart"))),
                crop_x=int(options.get("crop_x", self.config.get("shorts", "default_crop_x", default=80))),
                crop_y=int(options.get("crop_y", 50)),
                ass_file=ass_path,
                fonts_dir=self.config.path_for("paths", "fonts"),
                project_root=self.config.root,
                dynamic_zoom=dynamic_zoom_enabled,
                peak_timestamp=render_peak_timestamp,
                zoom_timestamps=render_zoom_timestamps,
                thumbnail_timestamp=render_thumbnail_timestamp,
                zoom_percent=int(options.get("zoom_percent", 8)),
                trim_start=trim_start,
                trim_duration=trim_end - trim_start,
                sound_effect_path=hook_sound_path if bool(options.get("sfx_enabled", True)) else None,
                sound_effect_offset=min(0.12, max(0.0, (trim_end - trim_start) - 0.12)),
                sound_effect_volume=float(self.config.get("shorts", "sfx_volume", default=0.14)),
            )
            check_cancelled()
            self.store.update_job(job_id, progress=88, message="Contrôle qualité de l'export")
            try:
                quality_report = analyze_export_quality(
                    output_path,
                    ffmpeg=str(self.config.get("executables", "ffmpeg", default="ffmpeg")),
                    ffprobe=str(self.config.get("executables", "ffprobe", default="ffprobe")),
                    expected_duration=float(result["duration"]),
                    expected_width=int(result["output_width"]),
                    expected_height=int(result["output_height"]),
                    expect_audio=bool(result.get("has_audio", source_info["has_audio"])),
                    ass_file=None,
                    caption_words=None,
                    caption_expected=False,
                )
            except ProcessingCancelled:
                raise
            except Exception as exc:
                logger.exception("Le contrôle qualité a échoué pour le job %s", job_id)
                quality_report = {
                    "status": "partial",
                    "summary": "Contrôle qualité indisponible, vérification manuelle recommandée.",
                    "checks": [],
                    "warnings": [str(exc)[:180]],
                    "metrics": {},
                }
            check_cancelled()
            metadata["quality_report"] = quality_report

            if thumbnail_path.is_file():
                custom_font = self.config.root / str(self.config.get("branding", "font_file", default="assets/fonts/Anton-Regular.ttf"))
                apply_thumbnail_overlay(
                    thumbnail_path,
                    str(metadata.get("thumbnail_text") or metadata.get("title") or "GTA MOMENT"),
                    font_path=custom_font if custom_font.is_file() else None,
                    streamer=str(job.get("streamer", "")),
                    game_label=str(metadata.get("game_keyword") or "GTA"),
                )
            metadata.update({
                "streamer": job.get("streamer", ""),
                "source_url": source_url,
                "source_title": job.get("source_title", ""),
                "note": job.get("note", ""),
                "duration": result["duration"],
                "encoder_used": result["encoder_used"],
                "output_width": result["output_width"],
                "output_height": result["output_height"],
                "layout": result["layout"],
                "sound_effect_used": result.get("sound_effect_used", False),
                "hook_sound_style": hook_sound_style if bool(options.get("sfx_enabled", True)) else None,
                "peak_timestamp": peak_timestamp,
                "render_peak_timestamp": render_peak_timestamp,
                "render_zoom_timestamps": render_zoom_timestamps,
                "thumbnail_timestamp": result.get("thumbnail_timestamp"),
                "source_duration": source_info["duration"],
                "trim_start": trim_start,
                "trim_end": trim_end,
                "auto_trim_enabled": auto_trim_enabled,
                "generation_stage": "short_edit_v0.6.0",
                "options": options,
            })
            self.store.update_job(job_id, progress=92, message="Écriture des métadonnées et de la miniature")
            title_path.write_text(str(metadata.get("title", "GTA Short")) + "\n", encoding="utf-8")
            description_path.write_text(str(metadata.get("description", "")) + "\n", encoding="utf-8")
            publication_text = str(metadata.get("title", "GTA Short")) + "\n\n" + str(metadata.get("description", "")) + "\n"
            (output_dir / "publication.txt").write_text(publication_text, encoding="utf-8")
            meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
            self.store.update_job(
                job_id, status="ready", progress=100, message="Short prêt pour validation",
                duration=result["duration"], output_path=str(output_path),
                thumbnail_path=str(thumbnail_path) if thumbnail_path.is_file() else None,
                metadata_json=metadata,
            )
        except ProcessingCancelled:
            logger.info("Traitement du job %s annulé par l'utilisateur", job_id)
            current = self.store.get_job(job_id) or {}
            self.store.update_job(
                job_id, status="cancelled", progress=int(current.get("progress") or 0),
                message="Traitement annulé", error=None,
            )
        except Exception as exc:
            logger.exception("Le traitement du job %s a échoué", job_id)
            self.store.update_job(
                job_id, status="error", progress=0, message="Échec du traitement", error=str(exc)[:2500]
            )

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                check_cancelled()
                digest.update(chunk)
        return digest.hexdigest()

    def _download(self, job_id: str, url: str) -> tuple[Path, dict[str, Any]]:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise MediaError("yt-dlp n'est pas installé. Relance INSTALL.bat pour réparer les dépendances.") from exc
        download_dir = self.config.path_for("paths", "temp") / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(download_dir / f"{job_id}.%(ext)s")
        last_progress_at: float | None = None
        last_download_percent: int | None = None

        def report_download_progress(data: dict[str, Any]) -> None:
            nonlocal last_progress_at, last_download_percent
            check_cancelled()
            status = str(data.get("status") or "")
            if status == "finished":
                self.store.update_job(
                    job_id,
                    progress=19,
                    message="Téléchargement terminé · préparation du Short",
                )
                last_download_percent = 100
                return
            if status != "downloading":
                return

            try:
                downloaded = max(0, int(data.get("downloaded_bytes") or 0))
                total = max(0, int(data.get("total_bytes") or data.get("total_bytes_estimate") or 0))
            except (TypeError, ValueError, OverflowError):
                downloaded, total = 0, 0

            metrics_suffix = _download_size_suffix(data) + _download_metrics_suffix(data)
            now = time.monotonic()
            if total > 0:
                percent = min(100, max(0, downloaded * 100 // total))
                if last_download_percent is not None:
                    percent = max(last_download_percent, percent)
                progress = 10 + int(round(percent * 0.09))
                message = f"Téléchargement de la source · {percent} %{metrics_suffix}"
                should_update = (
                    last_progress_at is None
                    or now - last_progress_at >= 1.0
                    or (
                        percent - (last_download_percent or 0) >= 5
                        and now - last_progress_at >= 0.4
                    )
                    or percent >= 100
                )
            else:
                progress = 10 + int(round((last_download_percent or 0) * 0.09))
                message = "Téléchargement de la source…" + metrics_suffix
                should_update = last_progress_at is None or now - last_progress_at >= 1.25

            if should_update:
                self.store.update_job(job_id, progress=progress, message=message)
                last_progress_at = now
                if total > 0:
                    last_download_percent = percent

        options = {
            "outtmpl": output_template,
            "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
            "continuedl": True,
            "concurrent_fragment_downloads": 4,
            "retries": 8,
            "fragment_retries": 8,
            "file_access_retries": 5,
            "progress_hooks": [report_download_progress],
        }
        try:
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True)
                downloaded = Path(downloader.prepare_filename(info))
            if not downloaded.is_file():
                candidates = sorted(download_dir.glob(f"{job_id}.*"), key=lambda path: path.stat().st_mtime, reverse=True)
                downloaded = next((path for path in candidates if path.is_file() and path.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}), downloaded)
            if not downloaded.is_file():
                raise MediaError("yt-dlp a terminé sans produire de fichier vidéo exploitable.")
            return downloaded, info
        except ProcessingCancelled:
            raise
        except Exception as exc:
            check_cancelled()
            raise MediaError(f"Téléchargement impossible : {exc}") from exc
