"""File de traitement locale : téléchargement, transcription et montage des Shorts."""

from __future__ import annotations

import hashlib
import json
import logging
import queue
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from studio.config import AppConfig
from studio.process import ProcessingCancelled, check_cancelled, set_current_cancel_event
from studio.web.metadata import generate_short_metadata
from studio.web.short_editor import (
    apply_thumbnail_overlay, create_ass_file, map_timestamp_through_segments, parse_srt,
    plan_speech_pause_edits, rebase_word_timings, rebase_word_timings_by_segments,
    select_excerpt_range, select_thumbnail_timestamp, write_srt_file,
)
from studio.web.short_renderer import MediaError, probe_media, render_vertical_short
from studio.web.export_quality import analyze_export_quality
from studio.web.store import Store
from studio.web.transcribe import (
    TranscriptionError,
    detect_audio_peak_timestamp,
    extract_audio_wav,
    transcribe_with_whisper_cpp,
)

logger = logging.getLogger(__name__)


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
                job["source_title"] = job.get("source_title") or str(info.get("title") or "")
                job["streamer"] = job.get("streamer") or str(info.get("uploader") or info.get("channel") or "")
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
            transcript_result: dict[str, Any] = {
                "status": "disabled", "reason": "Sous-titres désactivés dans les options.", "words": [], "text": ""
            }
            if source_info["has_audio"]:
                audio_path = temp_dir / "audio-16k.wav"
                try:
                    extract_audio_wav(
                        source_path, audio_path,
                        ffmpeg=str(self.config.get("executables", "ffmpeg", default="ffmpeg")),
                        start_seconds=trim_start if source_range else None,
                        duration_seconds=(trim_end - trim_start) if source_range else None,
                    )
                    local_peak = detect_audio_peak_timestamp(audio_path)
                    peak_timestamp = (trim_start + local_peak) if source_range and local_peak else (local_peak or peak_timestamp)
                    if bool(options.get("captions_enabled", True)):
                        self.store.update_job(job_id, progress=30, message="Transcription locale si le modèle est installé")
                        model_path = self.config.path_for("transcription", "model_path")
                        vad_model_raw = self.config.get("transcription", "vad_model_path", default="")
                        vad_model_path = self.config.root / str(vad_model_raw) if vad_model_raw else None
                        try:
                            transcript_result = transcribe_with_whisper_cpp(
                                audio_path,
                                whisper_cli=self.config.path_for("executables", "whisper_cli"),
                                model_path=model_path,
                                output_dir=temp_dir,
                                language=str(self.config.get("transcription", "language", default="en")),
                                threads=int(self.config.get("transcription", "threads", default=0)),
                                vad_model_path=vad_model_path,
                            )
                            if source_range and transcript_result.get("words"):
                                transcript_result["words"] = [
                                    type(word)(word.start + trim_start, word.end + trim_start, word.text)
                                    for word in transcript_result["words"]
                                ]
                        except TranscriptionError as exc:
                            transcript_result = {"status": "error", "reason": str(exc), "words": [], "text": ""}
                            logger.warning("Transcription ignorée pour le job %s : %s", job_id, exc)
                except TranscriptionError as exc:
                    logger.warning("Analyse audio ignorée pour le job %s : %s", job_id, exc)
                    transcript_result = {"status": "error", "reason": str(exc), "words": [], "text": ""}
            else:
                transcript_result = {"status": "no_audio", "reason": "La vidéo ne contient pas de piste audio.", "words": [], "text": ""}

            if not source_range:
                auto_trim_enabled = bool(options.get("auto_trim_enabled", self.config.get("shorts", "auto_trim_enabled", default=True)))
                trim_start, trim_end = 0.0, float(source_info["duration"])
            all_words = transcript_result.get("words", [])
            if auto_trim_enabled and not source_range:
                trim_start, trim_end = select_excerpt_range(
                    float(source_info["duration"]), peak_timestamp, all_words,
                    threshold_seconds=float(self.config.get("shorts", "peak_trim_threshold_seconds", default=45)),
                    lead_seconds=float(self.config.get("shorts", "peak_lead_seconds", default=1.5)),
                    tail_seconds=float(self.config.get("shorts", "payoff_tail_seconds", default=2.0)),
                    minimum_seconds=float(self.config.get("shorts", "auto_trim_min_seconds", default=15)),
                    maximum_seconds=float(self.config.get("shorts", "auto_trim_max_seconds", default=45)),
                )
            excerpt_duration = max(0.0, trim_end - trim_start)
            render_words = rebase_word_timings(all_words, trim_start, trim_end) if all_words else []
            render_peak_timestamp = max(0.0, peak_timestamp - trim_start)
            speaker_filter: dict[str, Any] = {"mode": str(options.get("caption_voice_mode", "dominant")), "status": "not_requested"}
            if render_words and speaker_filter["mode"] == "dominant":
                original_words = render_words
                speaker_audio_path = temp_dir / "speaker-audio.wav"
                try:
                    self.store.update_job(job_id, progress=43, message="Identification locale des voix du Short")
                    extract_audio_wav(
                        source_path,
                        speaker_audio_path,
                        ffmpeg=str(self.config.get("executables", "ffmpeg", default="ffmpeg")),
                        start_seconds=trim_start,
                        duration_seconds=trim_end - trim_start,
                    )
                    from studio.web.speakers import diarize_and_filter

                    render_words, speaker_filter = diarize_and_filter(speaker_audio_path, render_words)
                    logger.info("Filtrage des sous-titres pour le job %s : %s", job_id, speaker_filter)
                except ProcessingCancelled:
                    raise
                except Exception as exc:
                    render_words = original_words
                    speaker_filter = {
                        "mode": "dominant",
                        "status": "fallback_all_voices",
                        "reason": str(exc)[:500],
                    }
                    logger.warning("Filtrage des voix ignoré pour le job %s : %s", job_id, exc)
                finally:
                    speaker_audio_path.unlink(missing_ok=True)
            elif speaker_filter["mode"] != "dominant":
                speaker_filter["status"] = "all_voices"

            auto_pause_trim_enabled = bool(
                options.get(
                    "auto_pause_trim_enabled",
                    self.config.get("shorts", "auto_pause_trim_enabled", default=True),
                )
            ) and auto_trim_enabled and not source_range
            pause_plan = plan_speech_pause_edits(
                render_words,
                excerpt_duration,
                render_peak_timestamp,
                timestamp_mode=str(transcript_result.get("timestamp_mode") or ""),
                min_pause_seconds=float(self.config.get("shorts", "auto_pause_trim_min_pause_seconds", default=3.0)),
                keep_context_seconds=float(self.config.get("shorts", "auto_pause_trim_keep_seconds", default=0.55)),
                peak_guard_seconds=float(self.config.get("shorts", "auto_pause_trim_peak_guard_seconds", default=2.5)),
                max_removed_seconds=float(self.config.get("shorts", "auto_pause_trim_max_removed_seconds", default=6.0)),
                max_cuts=int(self.config.get("shorts", "auto_pause_trim_max_cuts", default=2)),
            ) if auto_pause_trim_enabled else plan_speech_pause_edits(
                [], excerpt_duration, render_peak_timestamp, timestamp_mode="disabled",
            )
            edit_segments = list(pause_plan.segments) if len(pause_plan.segments) > 1 else None
            if edit_segments:
                render_words = rebase_word_timings_by_segments(render_words, pause_plan.segments)
                render_peak_timestamp = map_timestamp_through_segments(
                    render_peak_timestamp, pause_plan.segments
                )
            render_duration = pause_plan.output_duration if edit_segments else excerpt_duration
            render_thumbnail_timestamp = select_thumbnail_timestamp(
                render_words, render_duration, preferred=render_peak_timestamp
            )
            render_transcript = " ".join(word.text for word in render_words).strip()
            if not render_transcript and trim_start == 0 and trim_end >= float(source_info["duration"]):
                render_transcript = transcript_result.get("text", "")

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

            if render_words:
                write_srt_file(output_dir / "captions.srt", render_words)
            captions_active = bool(options.get("captions_enabled", True)) and transcript_result.get("status") in {"completed", "completed_segment_fallback"}
            ass_path = temp_dir / "captions.ass"
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
            )
            shutil.copy2(ass_path, output_dir / "captions.ass")

            check_cancelled()
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
                layout=str(options.get("layout", self.config.get("shorts", "layout", default="fill"))),
                webcam_zone=str(options.get("webcam_zone", "none")),
                crop_x=int(options.get("crop_x", 50)),
                crop_y=int(options.get("crop_y", 50)),
                ass_file=ass_path,
                fonts_dir=self.config.path_for("paths", "fonts"),
                project_root=self.config.root,
                dynamic_zoom=bool(options.get("dynamic_zoom", True)),
                peak_timestamp=render_peak_timestamp,
                thumbnail_timestamp=render_thumbnail_timestamp,
                zoom_percent=int(options.get("zoom_percent", 8)),
                trim_start=trim_start,
                trim_duration=excerpt_duration,
                edit_segments=edit_segments,
                sound_effect_path=(self.config.root / "assets" / "sfx" / "soft_whoosh.wav")
                    if bool(options.get("sfx_enabled", True)) else None,
                sound_effect_offset=max(0.0, min(render_peak_timestamp, (trim_end - trim_start) - 0.12)),
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
                    ass_file=ass_path if captions_active else None,
                    caption_words=render_words if captions_active else None,
                    caption_expected=bool(render_words) and captions_active,
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
                "peak_timestamp": peak_timestamp,
                "render_peak_timestamp": render_peak_timestamp,
                "thumbnail_timestamp": result.get("thumbnail_timestamp"),
                "source_duration": source_info["duration"],
                "trim_start": trim_start,
                "trim_end": trim_end,
                "auto_trim_enabled": auto_trim_enabled,
                "smart_cutting": {
                    "enabled": auto_pause_trim_enabled,
                    "timestamp_mode": transcript_result.get("timestamp_mode"),
                    "removed_pause_count": len(pause_plan.removed_pauses),
                    "removed_pause_seconds": pause_plan.removed_duration,
                    "removed_pauses": [
                        {"start": round(trim_start + start, 3), "end": round(trim_start + end, 3)}
                        for start, end in pause_plan.removed_pauses
                    ],
                    "kept_segments": [
                        {"start": round(trim_start + start, 3), "end": round(trim_start + end, 3)}
                        for start, end in pause_plan.segments
                    ],
                },
                "transcription_status": transcript_result.get("status"),
                "transcription_timestamp_mode": transcript_result.get("timestamp_mode"),
                "transcription_message": transcript_result.get("reason"),
                "transcript": render_transcript,
                "speaker_filter": speaker_filter,
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
            "progress_hooks": [lambda _data: check_cancelled()],
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
