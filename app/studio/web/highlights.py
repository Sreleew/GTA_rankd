"""Local highlight scanning for long GTA VODs and Twitch clips."""
from __future__ import annotations

import array
from bisect import bisect_left, bisect_right
import logging
import math
import queue
import re
import shutil
import threading
import time
import wave
from pathlib import Path
from typing import Any, Callable

from studio.config import AppConfig
from studio.process import ProcessingCancelled, check_cancelled, set_current_cancel_event
from studio.web.short_editor import WordTiming
from studio.web.short_renderer import MediaError, probe_media, probe_timeout_for_file
from studio.web.store import Store
from studio.web.transcribe import TranscriptionError, extract_audio_wav, transcribe_with_whisper_cpp

logger = logging.getLogger(__name__)

MAX_SCAN_SECONDS = 3 * 60 * 60
TRANSCRIPTION_CHUNK_SECONDS = 5 * 60
CANDIDATE_SECONDS = 35.0
MIN_CANDIDATE_SCORE = 80.0
REACTION_CUES = {
    "bro", "bruh", "no", "what", "wow", "whoa", "holy", "shit", "fuck", "damn",
    "crazy", "insane", "run", "dead", "killed", "kill", "shoot", "police", "help",
    "oh", "god", "wait", "yo", "nah", "clutch", "nice", "wtf", "omg", "sick",
    "actually", "seriously", "impossible", "screaming", "laughing",
}


def build_twitch_download_ranges(start_seconds: float, end_seconds: float):
    """Build yt-dlp's Python API callback for one precise VOD time range."""
    try:
        from yt_dlp.utils import download_range_func
    except ImportError as exc:
        raise MediaError("yt-dlp ne fournit pas l'API de découpage nécessaire.") from exc
    return download_range_func(None, [(float(start_seconds), float(end_seconds))])


def _format_section_time(seconds: float) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def _words_for_window(words: list[WordTiming], start: float, end: float) -> list[WordTiming]:
    return [word for word in words if word.end > start and word.start < end]


class _IntervalIndex:
    """Efficiently retrieve intervals that overlap a query time range.

    Audio windows and Whisper word timings are normally chronological. For
    sorted inputs, prefix maximum end times allow bisect-based lookup while
    still handling unusually long intervals that start before the query.
    Unsorted inputs retain the original linear behavior and ordering.
    """

    __slots__ = ("_items", "_start", "_end", "_starts", "_prefix_max_ends", "_ordered")

    def __init__(
        self,
        items: list[Any],
        *,
        start_key: Callable[[Any], float],
        end_key: Callable[[Any], float],
    ) -> None:
        self._items = items
        self._start = start_key
        self._end = end_key
        self._ordered = all(
            start_key(items[index - 1]) <= start_key(items[index])
            for index in range(1, len(items))
        )
        self._starts: list[float] = []
        self._prefix_max_ends: list[float] = []
        if self._ordered:
            maximum_end = float("-inf")
            for item in items:
                self._starts.append(float(start_key(item)))
                maximum_end = max(maximum_end, float(end_key(item)))
                self._prefix_max_ends.append(maximum_end)

    def overlapping(self, start: float, end: float) -> list[Any]:
        if end <= start or not self._items:
            return []
        if not self._ordered:
            return [
                item for item in self._items
                if self._end(item) > start and self._start(item) < end
            ]

        first = bisect_right(self._prefix_max_ends, start)
        last = bisect_left(self._starts, end)
        return [
            item for item in self._items[first:last]
            if self._end(item) > start
        ]


def read_audio_energy(wav_path: Path, *, window_seconds: float = 2.0) -> list[dict[str, float]]:
    """Read a mono 16 kHz PCM WAV incrementally and return RMS windows."""
    windows: list[dict[str, float]] = []
    with wave.open(str(wav_path), "rb") as audio:
        rate = audio.getframerate()
        channels = audio.getnchannels()
        width = audio.getsampwidth()
        if rate <= 0 or width != 2:
            raise MediaError("Le WAV d'analyse doit être en PCM 16 bits.")
        frames_per_window = max(1, int(rate * window_seconds))
        start_frame = 0
        while True:
            check_cancelled()
            raw = audio.readframes(frames_per_window)
            if not raw:
                break
            samples = array.array("h")
            samples.frombytes(raw)
            if channels > 1:
                samples = array.array("h", samples[::channels])
            if not samples:
                break
            square_sum = sum(int(value) * int(value) for value in samples)
            rms = math.sqrt(square_sum / len(samples)) / 32768.0
            duration = len(samples) / rate
            windows.append({
                "start": start_frame / rate,
                "end": start_frame / rate + duration,
                "rms": float(rms),
            })
            start_frame += len(raw) // (width * channels)
    return windows


def _opening_retention_score(
    start: float,
    end: float,
    audio_windows: list[dict[str, float]],
    words: list[WordTiming],
    *,
    baseline_rms: float,
    audio_span: float,
    audio_index: _IntervalIndex | None = None,
    words_index: _IntervalIndex | None = None,
) -> float:
    """Estimate whether a candidate gives the viewer a reason to stay quickly."""
    opening_end = min(end, start + 5.0)
    opening_duration = max(0.1, opening_end - start)
    opening_audio = []
    opening_audio_windows = (
        audio_index.overlapping(start, opening_end)
        if audio_index is not None else audio_windows
    )
    for item in opening_audio_windows:
        overlap = max(0.0, min(opening_end, float(item["end"])) - max(start, float(item["start"])))
        if overlap > 0:
            opening_audio.append((float(item["rms"]), overlap))

    if opening_audio:
        total_overlap = sum(weight for _, weight in opening_audio)
        opening_rms = sum(value * weight for value, weight in opening_audio) / max(total_overlap, 0.001)
        opening_audio_score = max(0.0, min(1.0, (opening_rms - baseline_rms) / audio_span))
    else:
        opening_audio_score = 0.0

    # With no transcript, use the audio-only indicator rather than treating
    # the unavailable speech signals as negative evidence.
    opening_words = (
        words_index.overlapping(start, opening_end)
        if words_index is not None else _words_for_window(words, start, opening_end)
    )
    if not opening_words:
        return opening_audio_score

    speech_density = len(opening_words) / opening_duration
    opening_speech_score = max(0.0, min(1.0, speech_density / 1.0))
    cue_count = sum(
        1
        for word in opening_words
        for token in re.findall(r"[a-z']+", word.text.lower())
        if token in REACTION_CUES
    )
    opening_reaction_score = max(0.0, min(1.0, cue_count / 2.0))
    return 0.45 * opening_audio_score + 0.40 * opening_speech_score + 0.15 * opening_reaction_score


def score_highlight_candidates(
    duration: float,
    audio_windows: list[dict[str, float]],
    words: list[WordTiming],
    *,
    candidate_seconds: float | None = None,
    max_candidates: int | None = None,
) -> list[dict[str, Any]]:
    """Rank variable-length excerpts and keep only distinct, non-overlapping moments.

    The default scan evaluates several useful Short lengths. Supplying
    candidate_seconds keeps the deterministic single-length mode used by tests
    and callers that need a fixed duration.
    """
    duration = max(0.0, float(duration))
    if duration <= 0 or (max_candidates is not None and max_candidates <= 0):
        return []

    if candidate_seconds is not None:
        clip_lengths = [min(max(1.0, float(candidate_seconds)), duration)]
    else:
        clip_lengths = sorted({min(value, duration) for value in (60.0, 90.0, 120.0, 150.0, 165.0) if value <= duration})
        if not clip_lengths:
            clip_lengths = [duration]

    rms_values = [float(item["rms"]) for item in audio_windows if item.get("rms", 0) >= 0]
    if rms_values:
        sorted_rms = sorted(rms_values)
        p50 = sorted_rms[int((len(sorted_rms) - 1) * 0.50)]
        p98 = sorted_rms[int((len(sorted_rms) - 1) * 0.98)]
    else:
        p50 = p98 = 0.0
    audio_span = max(0.0001, p98 - p50)
    audio_index = _IntervalIndex(
        audio_windows,
        start_key=lambda item: float(item["start"]),
        end_key=lambda item: float(item["end"]),
    )
    words_index = _IntervalIndex(
        words,
        start_key=lambda word: float(word.start),
        end_key=lambda word: float(word.end),
    )

    ranked: list[dict[str, Any]] = []
    for clip_length in clip_lengths:
        if duration <= clip_length + 0.01:
            starts = [0.0]
        else:
            hop = max(4.0, min(10.0, clip_length / 4.0))
            starts = []
            current = 0.0
            while current + clip_length <= duration + 0.01:
                starts.append(current)
                current += hop
            last_start = max(0.0, duration - clip_length)
            if not starts or last_start - starts[-1] > 0.5:
                starts.append(last_start)

        for start in starts:
            end = min(duration, start + clip_length)
            local_items = audio_index.overlapping(start, end)
            local_audio = [float(item["rms"]) for item in local_items]
            local_audio.sort(reverse=True)
            top_count = max(1, min(5, len(local_audio)))
            peak_average = sum(local_audio[:top_count]) / top_count if local_audio else 0.0
            audio_score = max(0.0, min(1.0, (peak_average - p50) / audio_span))

            local_words = words_index.overlapping(start, end)
            speech_density = len(local_words) / max(1.0, end - start)
            speech_score = max(0.0, min(1.0, speech_density / 1.35))
            cue_count = 0
            for word in local_words:
                tokens = re.findall(r"[a-z']+", word.text.lower())
                cue_count += sum(1 for token in tokens if token in REACTION_CUES)
            reaction_score = max(0.0, min(1.0, cue_count / 3.0))
            opening_score = _opening_retention_score(
                start, end, audio_windows, words,
                baseline_rms=p50, audio_span=audio_span,
                audio_index=audio_index, words_index=words_index,
            )

            # Reward a clear build-up/payoff rather than only sustained loudness.
            # The peak is located inside the candidate, then compared with the
            # audio immediately before it. Reaction words near that peak add evidence.
            payoff_score = 0.0
            if len(local_items) >= 3:
                peak_index = max(range(len(local_items)), key=lambda i: float(local_items[i]["rms"]))
                peak_item = local_items[peak_index]
                peak_start = float(peak_item["start"])
                preceding = [
                    float(item["rms"]) for item in local_items[:peak_index]
                    if peak_start - float(item["start"]) <= 12.0
                ]
                if preceding:
                    pre_peak_rms = sorted(preceding)[len(preceding) // 2]
                    peak_rms = float(peak_item["rms"])
                    contrast_score = max(0.0, min(1.0, (peak_rms - pre_peak_rms) / audio_span))
                else:
                    contrast_score = 0.0
                nearby_words = words_index.overlapping(
                    max(start, peak_start - 3.0), min(end, peak_start + 8.0),
                )
                nearby_cues = sum(
                    1 for word in nearby_words
                    for token in re.findall(r"[a-z']+", word.text.lower())
                    if token in REACTION_CUES
                )
                reaction_payoff = max(0.0, min(1.0, nearby_cues / 2.0))
                payoff_score = max(contrast_score, reaction_payoff * 0.85)

            # Whisper may be unavailable or fail for a source. In that case,
            # audio is the only usable evidence and must not be capped at 55/100.
            if words:
                base_score = 0.55 * audio_score + 0.25 * speech_score + 0.20 * reaction_score
            else:
                base_score = audio_score
            enriched_score = 0.90 * base_score + 0.10 * payoff_score
            score = 100.0 * (0.90 * enriched_score + 0.10 * opening_score)
            reasons: list[str] = []
            if audio_score >= 0.55:
                reasons.append("Pic d'énergie audio")
            if speech_score >= 0.55:
                reasons.append("Dialogue soutenu")
            if reaction_score > 0:
                reasons.append("Mots de réaction détectés")
            if opening_score >= 0.65:
                reasons.append("Accroche immédiate")
            if payoff_score >= 0.55:
                reasons.append("Montée en tension / payoff détecté")
            elif opening_score < 0.25:
                reasons.append("Démarrage calme")
            if not reasons:
                reasons.append("Activité audio repérée")

            if score <= MIN_CANDIDATE_SCORE:
                continue
            transcript = " ".join(word.text.strip() for word in local_words).strip()
            ranked.append({
                "start_time": round(start, 3),
                "end_time": round(end, 3),
                "score": round(score, 1),
                "audio_score": round(audio_score, 3),
                "speech_score": round(speech_score, 3),
                "reaction_score": round(reaction_score, 3),
                "opening_score": round(opening_score, 3),
                "payoff_score": round(payoff_score, 3),
                "reasons": reasons,
                "transcript": transcript[:700],
            })

    ranked.sort(key=lambda item: item["score"], reverse=True)
    selected: list[dict[str, Any]] = []
    selected_transcripts: list[set[str]] = []
    minimum_gap = 6.0
    minimum_transcript_tokens = 8
    transcript_similarity_threshold = 0.82
    for candidate in ranked:
        start = float(candidate["start_time"])
        end = float(candidate["end_time"])
        overlaps = any(
            start < float(chosen["end_time"]) + minimum_gap
            and end + minimum_gap > float(chosen["start_time"])
            for chosen in selected
        )
        if overlaps:
            continue

        # Long VODs can contain repeated catchphrases or near-identical
        # reactions far apart in time. Avoid filling the shortlist with the
        # same spoken moment, while leaving short/audio-only transcripts alone.
        tokens = {
            token for token in re.findall(r"[a-z0-9']+", str(candidate.get("transcript", "")).lower())
            if token not in REACTION_CUES
        }
        if len(tokens) >= minimum_transcript_tokens:
            duplicate = False
            for previous_tokens in selected_transcripts:
                if len(previous_tokens) < minimum_transcript_tokens:
                    continue
                similarity = len(tokens & previous_tokens) / len(tokens | previous_tokens)
                if similarity >= transcript_similarity_threshold:
                    duplicate = True
                    break
            if duplicate:
                continue
        else:
            tokens = set()

        selected.append(candidate)
        selected_transcripts.append(tokens)
        if max_candidates is not None and len(selected) >= max_candidates:
            break

    for index, candidate in enumerate(selected, start=1):
        candidate["rank"] = index
    return selected

def write_wav_chunk(
    source: wave.Wave_read,
    output_path: Path,
    *,
    start_frame: int,
    frame_count: int,
    params: Any,
) -> Path:
    """Write an exact WAV chunk with a correct frame count in its header."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source.setpos(max(0, int(start_frame)))
    raw = source.readframes(max(0, int(frame_count)))
    actual_frames = len(raw) // max(1, params.sampwidth * params.nchannels)
    with wave.open(str(output_path), "wb") as chunk:
        chunk.setparams((params.nchannels, params.sampwidth, params.framerate, actual_frames, params.comptype, params.compname))
        chunk.writeframes(raw)
    return output_path


class HighlightScanner:
    """Background scanner for local VODs and Twitch VOD/clip URLs."""

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
            self.store.recover_interrupted_highlight_scans()
            for scan in self.store.list_highlight_scans(100):
                if scan["status"] == "queued":
                    self._queue.put(scan["id"])
            threading.Thread(target=self._run, name="gta-highlight-scanner", daemon=True).start()

    def submit(self, scan_id: str) -> None:
        self.start()
        self._queue.put(scan_id)

    def cancel(self, scan_id: str) -> bool:
        with self._lock:
            scan = self.store.get_highlight_scan(scan_id)
            if not scan or scan.get("status") not in {"queued", "running"}:
                return False
            event = self._cancel_events.get(scan_id)
            if scan["status"] == "queued":
                if event is not None:
                    event.set()
                self.store.update_highlight_scan(scan_id, status="cancelled", message="Analyse annulée avant démarrage", error=None)
                return True
            if event is None:
                return False
            event.set()
            self.store.update_highlight_scan(scan_id, status="cancelling", message="Arrêt de l'analyse en cours…")
            return True

    def _process(self, scan_id: str) -> None:
        event = threading.Event()
        with self._lock:
            self._cancel_events[scan_id] = event
        set_current_cancel_event(event)
        try:
            check_cancelled()
            self._process_job(scan_id)
        finally:
            set_current_cancel_event(None)
            with self._lock:
                self._cancel_events.pop(scan_id, None)

    def _run(self) -> None:
        while True:
            scan_id = self._queue.get()
            try:
                self._process(scan_id)
            except Exception:
                logger.exception("Analyse des moments forts échouée pour %s", scan_id)
                self.store.update_highlight_scan(
                    scan_id, status="error", progress=0,
                    message="Échec de l'analyse", error="Erreur interne. Consulte le journal local.",
                )
            finally:
                self._queue.task_done()

    def _process_job(self, scan_id: str) -> None:
        with self._lock:
            scan = self.store.get_highlight_scan(scan_id)
            if not scan or scan["status"] not in {"queued", "running"}:
                return
            self.store.update_highlight_scan(
                scan_id, status="running", progress=3, message="Préparation de la source", error=None,
            )
        source_path = Path(scan["source_path"]) if scan.get("source_path") else None
        base_offset = 0.0
        source_duration_hint: float | None = None
        temp_dir: Path | None = None
        transcription_available = False
        try:
            check_cancelled()
            if source_path is None and scan.get("source_url"):
                self.store.update_highlight_scan(scan_id, progress=8, message="Téléchargement de la source Twitch")
                source_path, info = self._download(scan_id, scan)
                base_offset = float(scan.get("window_start") or 0.0) if scan.get("window_end") is not None else 0.0
                try:
                    source_duration_hint = float(info.get("duration") or 0.0) or None
                except (TypeError, ValueError):
                    source_duration_hint = None
                self.store.update_highlight_scan(
                    scan_id,
                    source_path=str(source_path.resolve()),
                    source_title=str(info.get("title") or scan.get("source_title") or "Twitch source"),
                    streamer=str(info.get("uploader") or info.get("channel") or scan.get("streamer") or ""),
                )
                scan = self.store.get_highlight_scan(scan_id) or scan
                scan["source_path"] = str(source_path)
            if source_path is None or not source_path.is_file():
                raise MediaError("Fichier source introuvable.")

            probe_timeout = probe_timeout_for_file(source_path)
            self.store.update_highlight_scan(
                scan_id, progress=18,
                message=f"Inspection de la vidéo (délai maximal : {probe_timeout // 60} min)",
            )
            media = probe_media(
                source_path,
                str(self.config.get("executables", "ffprobe", default="ffprobe")),
                timeout=probe_timeout,
            )
            source_duration = float(media["duration"])
            requested_start = float(scan.get("window_start") or 0.0)
            requested_end = scan.get("window_end")
            if requested_end is None:
                local_start = 0.0
                local_end = source_duration
                base_offset = 0.0
            elif scan.get("source_kind") == "url":
                # yt-dlp has already downloaded the requested VOD section.
                local_start = 0.0
                local_end = source_duration
            else:
                local_start = requested_start
                local_end = float(requested_end)
            analysis_duration = local_end - local_start
            if analysis_duration <= 0:
                raise MediaError("La plage de temps sélectionnée est invalide.")
            if analysis_duration > MAX_SCAN_SECONDS:
                raise MediaError("La première version limite une analyse à 3 heures. Sélectionne une plage plus courte.")
            if local_end > source_duration + 0.25:
                raise MediaError("La fin de la plage dépasse la durée de la vidéo.")

            check_cancelled()
            self.store.update_highlight_scan(
                scan_id, source_duration=source_duration_hint or (source_duration + base_offset),
                progress=20, message=f"Analyse audio sur {analysis_duration / 60:.1f} minutes",
            )
            temp_dir = self.config.path_for("paths", "temp") / "highlights" / scan_id
            temp_dir.mkdir(parents=True, exist_ok=True)
            audio_path = temp_dir / "analysis-audio.wav"
            extract_audio_wav(
                source_path, audio_path,
                ffmpeg=str(self.config.get("executables", "ffmpeg", default="ffmpeg")),
                timeout=max(600, int(analysis_duration * 5)),
                start_seconds=local_start,
                duration_seconds=analysis_duration,
            )
            audio_windows = read_audio_energy(audio_path)
            self.store.update_highlight_scan(scan_id, progress=28, message="Analyse des niveaux audio terminée")

            words: list[WordTiming] = []
            model_path = self.config.path_for("transcription", "model_path")
            whisper_cli = self.config.path_for("executables", "whisper_cli")
            vad_raw = self.config.get("transcription", "vad_model_path", default="")
            vad_model = self.config.root / str(vad_raw) if vad_raw else None
            transcription_available = model_path.is_file() and whisper_cli.is_file()
            if transcription_available:
                with wave.open(str(audio_path), "rb") as audio:
                    params = audio.getparams()
                    total_frames = audio.getnframes()
                    chunk_frames = TRANSCRIPTION_CHUNK_SECONDS * params.framerate
                    chunk_count = max(1, math.ceil(total_frames / chunk_frames))
                    for index in range(chunk_count):
                        check_cancelled()
                        frame_start = min(total_frames, index * chunk_frames)
                        frame_count = min(chunk_frames, total_frames - frame_start)
                        if frame_count <= 0:
                            continue
                        chunk_path = temp_dir / f"audio-{index:04d}.wav"
                        write_wav_chunk(audio, chunk_path, start_frame=frame_start, frame_count=frame_count, params=params)
                        chunk_output = temp_dir / f"whisper-{index:04d}"
                        try:
                            result = transcribe_with_whisper_cpp(
                                chunk_path,
                                whisper_cli=whisper_cli,
                                model_path=model_path,
                                output_dir=chunk_output,
                                language=str(self.config.get("transcription", "language", default="en")),
                                threads=int(self.config.get("transcription", "threads", default=0)),
                                vad_model_path=vad_model,
                                timeout=1800,
                            )
                            offset = local_start + (index * TRANSCRIPTION_CHUNK_SECONDS)
                            words.extend(
                                WordTiming(word.start + offset, word.end + offset, word.text)
                                for word in result.get("words", [])
                            )
                        except TranscriptionError as exc:
                            logger.warning("Whisper chunk %s échoué pour le scan %s : %s", index, scan_id, exc)
                        finally:
                            chunk_path.unlink(missing_ok=True)
                        progress = 28 + int(48 * (index + 1) / chunk_count)
                        self.store.update_highlight_scan(
                            scan_id, progress=progress,
                            message=f"Transcription Whisper : segment {index + 1}/{chunk_count}",
                        )
            else:
                self.store.update_highlight_scan(
                    scan_id, progress=75,
                    message="Whisper absent : classement basé uniquement sur l'énergie audio",
                )

            candidates = score_highlight_candidates(analysis_duration, audio_windows, words)
            stored_candidates = []
            for candidate in candidates:
                media_start = local_start + candidate["start_time"]
                media_end = local_start + candidate["end_time"]
                stored_candidates.append({
                    **candidate,
                    "start_time": round(base_offset + media_start, 3),
                    "end_time": round(base_offset + media_end, 3),
                    "media_start": round(media_start, 3),
                    "media_end": round(media_end, 3),
                })
            self.store.save_highlight_candidates(scan_id, stored_candidates)
            audio_path.unlink(missing_ok=True)
            self.store.update_highlight_scan(
                scan_id, status="completed", progress=100,
                message=f"Analyse terminée : {len(stored_candidates)} passage(s) candidat(s)",
                metadata_json={
                    "analysis_duration": analysis_duration,
                    "base_offset": base_offset,
                    "transcription_available": transcription_available,
                    "transcription_used": bool(words),
                    "transcribed_words": len(words),
                    "scoring_method": "audio_energy + speech_density + reaction_cues + opening_retention",
                    "limitations": "Classement heuristique audio/texte. Pas encore d'analyse visuelle du gameplay.",
                },
            )
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except ProcessingCancelled:
            logger.info("Analyse des moments forts %s annulée par l'utilisateur", scan_id)
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)
            current = self.store.get_highlight_scan(scan_id) or {}
            self.store.update_highlight_scan(
                scan_id, status="cancelled", progress=int(current.get("progress") or 0),
                message="Analyse annulée", error=None,
            )
        except Exception as exc:
            logger.exception("Analyse du scan %s échouée", scan_id)
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)
            self.store.update_highlight_scan(
                scan_id, status="error", progress=0, message="Échec de l'analyse", error=str(exc)[:2500],
            )

    def _download(self, scan_id: str, scan: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise MediaError("yt-dlp n'est pas installé. Répare les dépendances depuis l'installation.") from exc
        download_dir = self.config.path_for("paths", "temp") / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        last_progress_update = {"at": 0.0, "percent": -1}

        def progress_hook(data: dict[str, Any]) -> None:
            check_cancelled()
            if data.get("status") != "downloading":
                return
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes") or 0
            fragment_index = data.get("fragment_index")
            fragment_count = data.get("fragment_count")
            if total:
                percent = int(max(0, min(100, downloaded * 100 / total)))
            elif fragment_index is not None and fragment_count:
                percent = int(max(0, min(100, int(fragment_index) * 100 / int(fragment_count))) )
            else:
                percent = -1
            now = time.monotonic()
            if percent >= 0 and (percent >= last_progress_update["percent"] + 2 or now - last_progress_update["at"] >= 5):
                last_progress_update.update(at=now, percent=percent)
                self.store.update_highlight_scan(
                    scan_id, progress=8 + int(percent * 0.10),
                    message=f"Téléchargement Twitch : {percent}%",
                )

        options: dict[str, Any] = {
            "outtmpl": str(download_dir / f"highlight-{scan_id}.%(ext)s"),
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
            "skip_unavailable_fragments": True,
            "progress_hooks": [progress_hook],
        }
        start = scan.get("window_start")
        end = scan.get("window_end")
        try:
            # Fetch metadata first so a multi-hour VOD is never downloaded in
            # full by accident when the user has not selected a time window.
            with YoutubeDL({**options, "skip_download": True}) as probe_downloader:
                info = probe_downloader.extract_info(str(scan["source_url"]), download=False)
            source_duration = float(info.get("duration") or 0.0)
            if start is None and end is None and source_duration > MAX_SCAN_SECONDS:
                raise MediaError(
                    f"Cette VOD dure {source_duration / 3600:.1f} h. Pour éviter un téléchargement massif, "
                    "renseigne un début et une fin (plage maximale : 3 h)."
                )
            if start is not None and end is not None:
                if source_duration and float(end) > source_duration:
                    raise MediaError("La fin de la plage dépasse la durée de la VOD Twitch.")
                options["download_ranges"] = build_twitch_download_ranges(float(start), float(end))
                options["force_keyframes_at_cuts"] = True
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(str(scan["source_url"]), download=True)
                downloaded = Path(downloader.prepare_filename(info))
            if not downloaded.is_file():
                candidates = sorted(
                    download_dir.glob(f"highlight-{scan_id}.*"),
                    key=lambda path: path.stat().st_mtime,
                    reverse=True,
                )
                downloaded = next(
                    (path for path in candidates if path.is_file() and path.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}),
                    downloaded,
                )
            if not downloaded.is_file():
                raise MediaError("yt-dlp a terminé sans produire de fichier vidéo exploitable.")
            return downloaded, info
        except ProcessingCancelled:
            raise
        except Exception as exc:
            check_cancelled()
            raise MediaError(f"Téléchargement Twitch impossible : {exc}") from exc
