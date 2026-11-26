"""Filtrage prudent des sous-titres par diarisation locale des voix."""

from __future__ import annotations

import importlib
import logging
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from studio.process import run_quiet
from studio.web.short_editor import WordTiming

logger = logging.getLogger(__name__)
DIARIZATION_PACKAGE = "diarize==0.1.2"


class SpeakerFilterError(RuntimeError):
    """Erreur récupérable du moteur local de séparation des voix."""


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _load_engine() -> Any:
    try:
        return importlib.import_module("diarize")
    except ImportError:
        logger.info("Installation à la demande du moteur local de diarisation %s", DIARIZATION_PACKAGE)
        try:
            result = run_quiet(
                [
                    sys.executable, "-m", "pip", "install",
                    "--disable-pip-version-check", "--prefer-binary",
                    DIARIZATION_PACKAGE,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1800,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SpeakerFilterError(
                f"Installation du moteur de voix impossible : {exc}"
            ) from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "erreur pip inconnue").strip()[-900:]
            raise SpeakerFilterError(f"Installation du moteur de voix échouée : {detail}")
        importlib.invalidate_caches()
        try:
            return importlib.import_module("diarize")
        except ImportError as exc:
            raise SpeakerFilterError(
                "Le moteur de voix a été installé mais ne peut pas être chargé. "
                "Relance l'installation des dépendances."
            ) from exc


def filter_dominant_speaker(
    words: list[WordTiming],
    segments: Iterable[Any],
    *,
    minimum_share: float = 0.62,
    minimum_ratio: float = 1.45,
    minimum_speech_seconds: float = 2.0,
) -> tuple[list[WordTiming], dict[str, Any]]:
    """Keep words assigned to a clearly dominant voice; otherwise keep everything.

    Speaker diarization does not know which voice is the streamer. This conservative
    heuristic only selects a speaker when the duration gap is strong enough.
    """
    valid: list[tuple[float, float, str]] = []
    durations: dict[str, float] = {}
    for segment in segments:
        try:
            start = float(_value(segment, "start", 0.0))
            end = float(_value(segment, "end", 0.0))
            speaker = str(_value(segment, "speaker", "") or "").strip()
        except (TypeError, ValueError):
            continue
        if not speaker or not math.isfinite(start) or not math.isfinite(end) or end <= start:
            continue
        valid.append((max(0.0, start), max(0.0, end), speaker))
        durations[speaker] = durations.get(speaker, 0.0) + max(0.0, end - start)

    base = {
        "mode": "dominant",
        "status": "fallback_all_voices",
        "speaker_count": len(durations),
        "selected_speaker": None,
        "dominant_share": 0.0,
        "dominance_ratio": 0.0,
        "words_before": len(words),
        "words_after": len(words),
    }
    if not words:
        return words, {**base, "status": "no_words"}
    if not durations:
        return words, {**base, "reason": "Aucun segment vocal exploitable."}
    if len(durations) == 1:
        only_speaker = next(iter(durations))
        return words, {
            **base,
            "status": "single_speaker",
            "selected_speaker": only_speaker,
            "dominant_share": 1.0,
            "dominance_ratio": 99.0,
        }

    ranked = sorted(durations.items(), key=lambda pair: pair[1], reverse=True)
    selected, selected_duration = ranked[0]
    second_duration = ranked[1][1]
    total_duration = sum(durations.values())
    share = selected_duration / max(0.001, total_duration)
    ratio = selected_duration / max(0.001, second_duration)
    if selected_duration < minimum_speech_seconds or share < minimum_share or ratio < minimum_ratio:
        return words, {
            **base,
            "reason": "Plusieurs voix sont trop proches pour choisir sans risque.",
            "dominant_share": round(share, 3),
            "dominance_ratio": round(ratio, 3),
        }

    filtered: list[WordTiming] = []
    for word in words:
        word_start = max(0.0, float(word.start))
        word_end = max(word_start, float(word.end))
        word_duration = max(0.04, word_end - word_start)
        overlaps: dict[str, float] = {}
        for start, end, speaker in valid:
            overlap = max(0.0, min(word_end, end) - max(word_start, start))
            if overlap:
                overlaps[speaker] = overlaps.get(speaker, 0.0) + overlap
        selected_overlap = overlaps.get(selected, 0.0)
        best_overlap = max(overlaps.values(), default=0.0)
        if selected_overlap >= max(0.06, word_duration * 0.40) and selected_overlap >= best_overlap * 0.80:
            filtered.append(word)

    minimum_kept = max(2, math.ceil(len(words) * 0.22))
    if len(filtered) < minimum_kept:
        return words, {
            **base,
            "reason": "Trop peu de mots peuvent être attribués à la voix dominante.",
            "dominant_share": round(share, 3),
            "dominance_ratio": round(ratio, 3),
        }

    return filtered, {
        **base,
        "status": "dominant_filtered",
        "selected_speaker": selected,
        "dominant_share": round(share, 3),
        "dominance_ratio": round(ratio, 3),
        "words_after": len(filtered),
    }


def diarize_and_filter(
    audio_path: Path,
    words: list[WordTiming],
) -> tuple[list[WordTiming], dict[str, Any]]:
    """Run the optional CPU diarizer on the final Short audio only."""
    if not audio_path.is_file():
        raise SpeakerFilterError(f"Audio de diarisation introuvable : {audio_path}")
    engine = _load_engine()
    diarize = getattr(engine, "diarize", None)
    if not callable(diarize):
        raise SpeakerFilterError("L'API du moteur de diarisation n'est pas disponible.")
    try:
        result = diarize(str(audio_path))
        segments = getattr(result, "segments", None)
        if segments is None:
            raise SpeakerFilterError("Le moteur n'a renvoyé aucun segment de voix.")
        filtered, report = filter_dominant_speaker(words, segments)
        report["engine"] = "diarize-0.1.2"
        return filtered, report
    except SpeakerFilterError:
        raise
    except Exception as exc:
        raise SpeakerFilterError(f"Analyse des voix impossible : {exc}") from exc
