"""Contrôles post-export non bloquants pour les Shorts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from studio.web.short_renderer import MediaError, probe_media, resolve_executable, run_command

_NUMBER = r"(-?\d+(?:\.\d+)?)"
_BLACK_RE = re.compile(rf"black_start:\s*{_NUMBER}\s+black_end:\s*{_NUMBER}\s+black_duration:\s*{_NUMBER}")
_FREEZE_RE = re.compile(rf"freeze_start:\s*{_NUMBER}.*?freeze_duration:\s*{_NUMBER}", re.DOTALL)
_SILENCE_RE = re.compile(rf"silence_start:\s*{_NUMBER}.*?silence_end:\s*{_NUMBER}\s*\|\s*silence_duration:\s*{_NUMBER}", re.DOTALL)
_ASS_TIME_RE = re.compile(r"^(\d+):(\d{2}):(\d{2})\.(\d{2})$")


def _ass_seconds(value: str) -> float | None:
    match = _ASS_TIME_RE.match(value.strip())
    if not match:
        return None
    hours, minutes, seconds, centiseconds = (int(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0


def parse_ffmpeg_diagnostics(log: str, duration: float) -> dict[str, list[dict[str, float]]]:
    """Parse blackdetect, freezedetect and silencedetect messages from FFmpeg."""
    limit = max(0.0, float(duration))
    black = []
    for start, end, span in _BLACK_RE.findall(log or ""):
        item = {"start": float(start), "end": float(end), "duration": float(span)}
        if item["start"] <= limit + 0.5 and item["duration"] > 0:
            black.append(item)

    frozen = []
    for start, span in _FREEZE_RE.findall(log or ""):
        begin, length = float(start), float(span)
        if begin <= limit + 0.5 and length > 0:
            frozen.append({"start": begin, "end": min(limit, begin + length), "duration": length})

    silent = []
    for start, end, span in _SILENCE_RE.findall(log or ""):
        item = {"start": float(start), "end": float(end), "duration": float(span)}
        if item["start"] <= limit + 0.5 and item["duration"] > 0:
            silent.append(item)

    return {"black": black, "freeze": frozen, "silence": silent}


def _check(checks: list[dict[str, str]], key: str, label: str, status: str, message: str) -> None:
    checks.append({"key": key, "label": label, "status": status, "message": message})


def _parse_ass_caption_events(ass_file: Path, duration: float) -> tuple[int, int, int]:
    """Return caption event count, out-of-range event count and overlong lines."""
    if not ass_file.is_file():
        return 0, 0, 0
    events = 0
    out_of_range = 0
    long_lines = 0
    for line in ass_file.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.startswith("Dialogue:") or ",Caption," not in line:
            continue
        fields = line.split(",", 9)
        if len(fields) < 10:
            continue
        start, end = _ass_seconds(fields[1]), _ass_seconds(fields[2])
        events += 1
        if start is None or end is None or start < -0.02 or end > duration + 0.25 or end <= start:
            out_of_range += 1
        text = re.sub(r"\{[^}]*\}", "", fields[9]).replace(r"\N", "\n")
        if any(len(part.strip()) > 24 for part in text.splitlines()):
            long_lines += 1
    return events, out_of_range, long_lines


def _word_timing_issues(words: Iterable[Any], duration: float) -> int:
    invalid = 0
    for word in words:
        try:
            start, end = float(word.start), float(word.end)
        except (AttributeError, TypeError, ValueError):
            invalid += 1
            continue
        if start < -0.02 or end <= start or end > duration + 0.25:
            invalid += 1
    return invalid


def analyze_export_quality(
    output_path: Path,
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    expected_duration: float | None = None,
    expected_width: int = 1080,
    expected_height: int = 1920,
    expect_audio: bool = True,
    ass_file: Path | None = None,
    caption_words: Iterable[Any] | None = None,
    caption_expected: bool = False,
) -> dict[str, Any]:
    """Check file structure and scan for likely export defects.

    The checks are diagnostic only: a warning never deletes or rejects the render.
    A failed FFmpeg analysis is reported as partial so the user can still review it.
    """
    output_path = Path(output_path)
    checks: list[dict[str, str]] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    fatal = False
    analysis_partial = False

    if not output_path.is_file():
        _check(checks, "file", "Fichier MP4", "fail", "Le fichier exporté est introuvable.")
        return {"status": "failed", "summary": "Export introuvable.", "checks": checks, "warnings": [checks[-1]["message"]], "metrics": metrics}

    try:
        size_bytes = output_path.stat().st_size
    except OSError:
        size_bytes = 0
    metrics["file_size_bytes"] = int(size_bytes)
    if size_bytes < 8_000:
        fatal = True
        message = "Le fichier exporté est anormalement petit et peut être incomplet."
        _check(checks, "file_size", "Taille du fichier", "fail", message)
        warnings.append(message)
    else:
        _check(checks, "file_size", "Taille du fichier", "pass", f"{size_bytes / 1024:.0f} Ko")

    try:
        info = probe_media(output_path, ffprobe, timeout=45)
    except (MediaError, OSError, ValueError) as exc:
        fatal = True
        message = f"Lecture du MP4 impossible : {str(exc)[:180]}"
        _check(checks, "probe", "Lecture du MP4", "fail", message)
        warnings.append(message)
        info = None

    if info is not None:
        duration = float(info.get("duration") or 0.0)
        metrics.update({
            "duration": round(duration, 3),
            "width": int(info.get("width") or 0),
            "height": int(info.get("height") or 0),
            "fps": round(float(info.get("fps") or 0.0), 3),
            "video_codec": str(info.get("video_codec") or "unknown"),
            "audio_codec": info.get("audio_codec"),
            "has_audio": bool(info.get("has_audio")),
        })
        if info.get("width") == expected_width and info.get("height") == expected_height:
            _check(checks, "resolution", "Format vertical", "pass", f"{expected_width} × {expected_height}")
        else:
            message = f"Résolution détectée : {info.get('width')} × {info.get('height')}, attendue : {expected_width} × {expected_height}."
            _check(checks, "resolution", "Format vertical", "warn", message)
            warnings.append(message)

        if expected_duration and duration > 0:
            tolerance = max(0.35, float(expected_duration) * 0.02)
            delta = duration - float(expected_duration)
            metrics["duration_delta"] = round(delta, 3)
            if abs(delta) <= tolerance:
                _check(checks, "duration", "Durée", "pass", f"{duration:.2f} s")
            else:
                message = f"Durée exportée : {duration:.2f} s au lieu de {float(expected_duration):.2f} s."
                _check(checks, "duration", "Durée", "warn", message)
                warnings.append(message)

        if expect_audio and not info.get("has_audio"):
            message = "La source avait une piste audio, mais le MP4 n'en contient pas."
            _check(checks, "audio", "Piste audio", "warn", message)
            warnings.append(message)
        elif info.get("has_audio"):
            _check(checks, "audio", "Piste audio", "pass", f"Piste détectée ({info.get('audio_codec') or 'codec inconnu'}).")
        else:
            _check(checks, "audio", "Piste audio", "info", "La source ne contient pas de piste audio.")

        if str(info.get("video_codec") or "").lower() not in {"h264", "avc1"}:
            message = f"Codec vidéo inhabituel : {info.get('video_codec') or 'inconnu'} (H.264 attendu)."
            _check(checks, "video_codec", "Codec vidéo", "warn", message)
            warnings.append(message)

        if caption_expected and ass_file:
            count, out_of_range, long_lines = _parse_ass_caption_events(Path(ass_file), duration)
            metrics["caption_events"] = count
            metrics["caption_events_out_of_range"] = out_of_range
            metrics["caption_lines_over_24_chars"] = long_lines
            if count == 0:
                message = "La transcription devait être sous-titrée, mais aucun événement Caption n'est présent dans le fichier ASS."
                _check(checks, "captions", "Sous-titres", "warn", message)
                warnings.append(message)
            elif out_of_range:
                message = f"{out_of_range} événement(s) de sous-titres débordent des limites du Short."
                _check(checks, "captions", "Horodatage des sous-titres", "warn", message)
                warnings.append(message)
            elif long_lines:
                message = f"{long_lines} ligne(s) de sous-titres dépassent 24 caractères et méritent une vérification visuelle."
                _check(checks, "captions", "Longueur des sous-titres", "warn", message)
                warnings.append(message)
            else:
                _check(checks, "captions", "Sous-titres", "pass", f"{count} événement(s), horodatages dans la durée du Short.")

        if caption_words is not None:
            invalid_words = _word_timing_issues(caption_words, duration)
            metrics["caption_word_timings_invalid"] = invalid_words
            if invalid_words:
                message = f"{invalid_words} segment(s) de transcription ont un horodatage invalide ou hors de la durée exportée."
                _check(checks, "caption_word_timings", "Horodatage de la transcription", "warn", message)
                warnings.append(message)

        try:
            ffmpeg_bin = resolve_executable(ffmpeg)
            filters = "blackdetect=d=1.2:pix_th=0.10,freezedetect=n=-60dB:d=2.5"
            command = [ffmpeg_bin, "-hide_banner", "-nostats", "-i", str(output_path.resolve()), "-vf", filters]
            if info.get("has_audio"):
                command.extend(["-af", "silencedetect=n=-50dB:d=4.0"])
            command.extend(["-f", "null", "-"])
            scan_timeout = max(30, min(90, int(duration * 1.5) + 20))
            scan = run_command(command, timeout=scan_timeout)
            diagnostics = parse_ffmpeg_diagnostics(scan.stderr or "", duration)
            metrics["black_segments"] = diagnostics["black"]
            metrics["freeze_segments"] = diagnostics["freeze"]
            metrics["silence_segments"] = diagnostics["silence"]

            if diagnostics["black"]:
                longest = max(item["duration"] for item in diagnostics["black"])
                message = f"Écran noir potentiel détecté ({longest:.1f} s au maximum)."
                _check(checks, "black_frames", "Écrans noirs", "warn", message)
                warnings.append(message)
            else:
                _check(checks, "black_frames", "Écrans noirs", "pass", "Aucun écran noir prolongé détecté.")

            if diagnostics["freeze"]:
                longest = max(item["duration"] for item in diagnostics["freeze"])
                message = f"Image potentiellement figée détectée ({longest:.1f} s au maximum)."
                _check(checks, "frozen_frames", "Images figées", "warn", message)
                warnings.append(message)
            else:
                _check(checks, "frozen_frames", "Images figées", "pass", "Aucun freeze prolongé détecté.")

            if diagnostics["silence"]:
                longest = max(item["duration"] for item in diagnostics["silence"])
                message = f"Plage de silence audio détectée ({longest:.1f} s au maximum). À vérifier selon le contenu du jeu."
                _check(checks, "audio_silence", "Silence audio", "warn", message)
                warnings.append(message)
            elif info.get("has_audio"):
                _check(checks, "audio_silence", "Silence audio", "pass", "Aucun silence supérieur à 4 secondes détecté.")
        except (MediaError, OSError, ValueError) as exc:
            analysis_partial = True
            message = f"Analyse détaillée image/son indisponible : {str(exc)[:160]}"
            _check(checks, "signal_scan", "Analyse image/son", "partial", message)

    status = "failed" if fatal else "review" if warnings else "partial" if analysis_partial else "passed"
    if status == "failed":
        summary = "Le fichier présente un problème structurel à vérifier avant publication."
    elif status == "review":
        summary = f"{len(warnings)} point(s) à vérifier avant publication."
    elif status == "partial":
        summary = "Contrôle structurel effectué, analyse détaillée partielle."
    else:
        summary = "Aucun défaut évident détecté par le contrôle automatique."
    return {"status": status, "summary": summary, "checks": checks, "warnings": warnings[:12], "metrics": metrics}
