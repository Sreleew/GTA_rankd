"""Intégration locale de whisper.cpp avec timestamps de tokens DTW."""

from __future__ import annotations

import array
import json
import logging
import math
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

from studio.process import run_quiet

from studio.web.short_editor import WordTiming, parse_srt

logger = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    """Erreur de transcription exploitable par le moteur de rendu."""


def _resolve_binary(value: str | Path) -> Path | None:
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return candidate.resolve()
    discovered = shutil.which(str(value))
    return Path(discovered).resolve() if discovered else None


def _binary_invocation(binary: Path) -> list[str]:
    """Construit la commande multiplateforme pour un exécutable ou un script Python.

    whisper-cli.exe reste lancé directement. Les scripts Python utilisés par les tests
    (et les éventuels wrappers locaux) sont lancés via l'interpréteur courant :
    Windows ne sait pas exécuter un script portant seulement un shebang Unix.
    """
    if binary.suffix.lower() == ".py":
        return [sys.executable, str(binary)]
    return [str(binary)]



def inspect_whisper_cli(binary_value: str | Path, *, timeout: int = 12) -> dict[str, Any]:
    """Vérifie le binaire et les options réellement exposées par cette build."""
    binary = _resolve_binary(binary_value)
    if binary is None:
        return {
            "available": False, "path": str(binary_value), "version": None,
            "dtw_supported": False, "device_listing_supported": False,
            "devices": [], "vulkan_detected": False,
            "message": "whisper-cli.exe introuvable dans tools/whisper.cpp.",
        }
    command = _binary_invocation(binary)
    try:
        result = run_quiet(
            [*command, "--help"], cwd=str(binary.parent), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "available": False, "path": str(binary), "version": None,
            "dtw_supported": False, "device_listing_supported": False,
            "devices": [], "vulkan_detected": False,
            "message": "whisper-cli ne répond pas à --help dans le délai imparti.",
        }
    except OSError as exc:
        return {
            "available": False, "path": str(binary), "version": None,
            "dtw_supported": False, "device_listing_supported": False,
            "devices": [], "vulkan_detected": False,
            "message": f"Impossible de lancer whisper-cli : {exc}",
        }

    help_text = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode not in (0, 1) or not help_text.strip():
        detail = help_text.strip()[-500:] or f"Code de sortie {result.returncode}"
        return {
            "available": False, "path": str(binary), "version": None,
            "dtw_supported": False, "device_listing_supported": False,
            "devices": [], "vulkan_detected": False,
            "message": f"Le binaire est présent mais son démarrage a échoué : {detail}",
        }

    # whisper.cpp désactive DTW si Flash Attention reste actif : -nfa est requis.
    dtw_supported = all(flag in help_text for flag in ("-dtw", "-ojf", "-nfa"))
    device_listing_supported = "--list-devices" in help_text
    devices: list[str] = []
    if device_listing_supported:
        try:
            device_result = run_quiet(
                [*command, "--list-devices"], cwd=str(binary.parent), capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
            )
            device_text = (device_result.stdout or "") + "\n" + (device_result.stderr or "")
            devices = [line.strip() for line in device_text.splitlines() if line.strip()]
        except (OSError, subprocess.TimeoutExpired):
            devices = []
    vulkan_detected = any("vulkan" in line.lower() for line in devices)
    version_match = re.search(r"(?:whisper\.cpp|whisper)\s+v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", help_text, re.IGNORECASE)
    version = version_match.group(1) if version_match else None
    return {
        "available": True, "path": str(binary), "version": version,
        "dtw_supported": dtw_supported,
        "device_listing_supported": device_listing_supported,
        "devices": devices[:12], "vulkan_detected": vulkan_detected,
        "message": "Moteur Whisper exécutable." + (
            " DTW disponible (Flash Attention désactivé pendant la transcription)."
            if dtw_supported
            else " DTW indisponible : le binaire doit exposer -dtw, -ojf et -nfa."
        ),
    }

def probe_whisper_vulkan(
    binary_value: str | Path,
    *,
    model_path: str | Path,
    expected_gpu: str = "GPU configuré",
    timeout: int = 150,
) -> dict[str, Any]:
    """Valide Vulkan par un vrai chargement du modèle, pas via --list-devices."""
    binary = _resolve_binary(binary_value)
    model = Path(model_path).expanduser().resolve()
    if binary is None:
        return {"verified": False, "reason": "whisper-cli.exe introuvable.", "backend": None, "gpu_model": expected_gpu}
    if not model.is_file() or model.stat().st_size < 1024 * 1024:
        return {"verified": False, "reason": f"Modèle Whisper absent ou invalide : {model}", "backend": None, "gpu_model": expected_gpu}
    try:
        with tempfile.TemporaryDirectory(prefix="gta-ranked-vulkan-probe-") as temp_dir:
            wav_path = Path(temp_dir) / "vulkan-smoke-test.wav"
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"\x00\x00" * 16000)
            result = run_quiet(
                [*_binary_invocation(binary), "-m", str(model), "-f", str(wav_path), "-l", "en", "-nt", "-t", "2"],
                cwd=str(binary.parent), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout, check=False,
            )
    except subprocess.TimeoutExpired:
        return {"verified": False, "reason": f"Le test Vulkan a dépassé {timeout} secondes pendant le chargement du modèle.", "backend": None, "gpu_model": expected_gpu}
    except OSError as exc:
        return {"verified": False, "reason": f"Impossible de lancer le test Whisper : {exc}", "backend": None, "gpu_model": expected_gpu}
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    backend_match = re.search(r"(?im)whisper_backend_init_gpu:\s+using\s+(Vulkan\d+)\s+backend", output)
    if not backend_match:
        detail = output.strip()[-1400:] or f"Code de sortie {result.returncode}"
        return {"verified": False, "reason": "Whisper n'a pas confirmé l'initialisation du backend GPU Vulkan. " + detail, "backend": None, "gpu_model": expected_gpu}
    backend = backend_match.group(1)
    allocation_pattern = rf"(?im)whisper_model_load:\s+{re.escape(backend)}\s+total size\s*=\s*([0-9.]+)\s*MB"
    allocation_match = re.search(allocation_pattern, output)
    if not allocation_match:
        detail = output.strip()[-1400:] or f"Code de sortie {result.returncode}"
        return {"verified": False, "reason": f"Whisper a initialisé {backend}, mais le modèle n'a pas confirmé son allocation sur ce backend. " + detail, "backend": backend, "gpu_model": expected_gpu}
    if result.returncode != 0:
        detail = output.strip()[-1400:] or f"Code de sortie {result.returncode}"
        return {"verified": False, "reason": f"Le backend {backend} a été initialisé, mais le test Whisper s'est terminé en erreur. " + detail, "backend": backend, "gpu_model": expected_gpu, "model_buffer_mb": float(allocation_match.group(1))}
    return {"verified": True, "reason": f"{backend} initialisé ; modèle alloué sur le GPU ({float(allocation_match.group(1)):.1f} MB).", "backend": backend, "gpu_model": expected_gpu, "model_buffer_mb": float(allocation_match.group(1))}

def _parse_whisper_timestamp(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})[.,](\d{1,3})", value.strip())
    if not match:
        return None
    hours, minutes, seconds, milliseconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds.ljust(3, "0")) / 1000


def parse_whisper_json_words(path: Path) -> list[WordTiming]:
    """Convertit le JSON complet whisper.cpp avec -dtw en vrais mots horodatés.

    whisper.cpp expose les timestamps DTW par token en unités de 10 ms.
    Les tokens sont regroupés en mots en respectant les espaces de début de token.
    """
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Le JSON complet Whisper est absent ou illisible : %s", path)
        return []

    segments = payload.get("transcription") if isinstance(payload, dict) else None
    if not isinstance(segments, list):
        return []

    result: list[WordTiming] = []
    special_pattern = re.compile(r"^(?:\[[A-Z0-9_:/ .-]+\]|<\|[^>]+\|>)$")

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        tokens = segment.get("tokens")
        if not isinstance(tokens, list) or not tokens:
            continue

        segment_times = segment.get("timestamps") if isinstance(segment.get("timestamps"), dict) else {}
        segment_start = _parse_whisper_timestamp(segment_times.get("from")) or 0.0
        segment_end = _parse_whisper_timestamp(segment_times.get("to"))
        if segment_end is None:
            segment_end = segment_start + 1.0

        token_items: list[tuple[str, float]] = []
        for token in tokens:
            if not isinstance(token, dict):
                continue
            raw_text = str(token.get("text") or "")
            if not raw_text or special_pattern.fullmatch(raw_text.strip()):
                continue
            # DTW timestamps are stored in 10 ms units by whisper.cpp.
            raw_time = token.get("t_dtw")
            try:
                token_start = float(raw_time) / 100.0
            except (TypeError, ValueError):
                continue
            if not math.isfinite(token_start) or token_start < 0:
                continue
            token_items.append((raw_text, max(segment_start, token_start)))

        # Without DTW, recent whisper.cpp builds may leave t_dtw at zero for
        # every token. In that case the segment SRT is the honest fallback.
        if len(token_items) > 1:
            token_times = [item[1] for item in token_items]
            if max(token_times) - min(token_times) < 0.02:
                continue

        word_groups: list[tuple[str, float]] = []
        current_text = ""
        current_start: float | None = None
        for raw_text, token_start in token_items:
            text = raw_text
            starts_new_word = text[:1].isspace() or text.startswith(("Ġ", "▁"))
            if text.startswith(("Ġ", "▁")):
                text = text[1:]
            text = text.strip() if starts_new_word else text
            if not text:
                continue
            if starts_new_word and current_text.strip():
                word_groups.append((current_text.strip(), current_start if current_start is not None else segment_start))
                current_text = text
                current_start = token_start
            elif not current_text:
                current_text = text
                current_start = token_start
            else:
                current_text += text

        if current_text.strip():
            word_groups.append((current_text.strip(), current_start if current_start is not None else segment_start))

        for index, (text, start) in enumerate(word_groups):
            next_start = word_groups[index + 1][1] if index + 1 < len(word_groups) else segment_end
            end = min(segment_end, max(start + 0.06, next_start))
            if end <= start:
                end = start + 0.12
            result.append(WordTiming(round(start, 3), round(end, 3), text))

    result.sort(key=lambda item: (item.start, item.end))
    # Remove overlaps introduced by adjacent Whisper segments.
    normalized: list[WordTiming] = []
    for index, word in enumerate(result):
        end = word.end
        if index + 1 < len(result) and result[index + 1].start > word.start:
            end = min(end, result[index + 1].start)
        normalized.append(WordTiming(word.start, max(word.start + 0.04, end), word.text))
    return normalized


def extract_audio_wav(
    input_path: Path,
    wav_path: Path,
    *,
    ffmpeg: str = "ffmpeg",
    timeout: int = 180,
    start_seconds: float | None = None,
    duration_seconds: float | None = None,
) -> Path:
    ffmpeg_bin = _resolve_binary(ffmpeg) or (Path(shutil.which(ffmpeg)) if shutil.which(ffmpeg) else None)
    if ffmpeg_bin is None:
        raise TranscriptionError("FFmpeg est introuvable pour extraire l'audio.")
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    command = [str(ffmpeg_bin), "-hide_banner", "-loglevel", "error", "-y"]
    if start_seconds is not None:
        if start_seconds < 0:
            raise TranscriptionError("Le début de l'extrait audio ne peut pas être négatif.")
        if start_seconds > 0:
            command.extend(["-ss", f"{float(start_seconds):.3f}"])
    command.extend(["-i", str(input_path.resolve())])
    if duration_seconds is not None:
        if duration_seconds <= 0:
            raise TranscriptionError("La durée de l'extrait audio doit être positive.")
        command.extend(["-t", f"{float(duration_seconds):.3f}"])
    command.extend(["-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path.resolve())])
    result = run_quiet(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    if result.returncode != 0 or not wav_path.is_file() or wav_path.stat().st_size <= 44:
        detail = (result.stderr or "Aucune piste audio exploitable.").strip()
        raise TranscriptionError(detail[-1500:])
    return wav_path


def transcribe_with_whisper_cpp(
    audio_path: Path,
    *,
    whisper_cli: str | Path,
    model_path: Path,
    output_dir: Path,
    language: str = "en",
    threads: int = 0,
    vad_model_path: Path | None = None,
    timeout: int = 1800,
    dtw_model_preset: str = "large.v3.turbo",
) -> dict[str, Any]:
    binary = _resolve_binary(whisper_cli)
    if binary is None:
        return {"status": "unavailable", "reason": "whisper-cli.exe introuvable", "words": [], "text": ""}
    if not model_path.is_file():
        return {
            "status": "model_missing",
            "reason": f"Modèle Whisper absent : {model_path}",
            "words": [],
            "text": "",
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_base = output_dir / "transcript"
    srt_path = output_base.with_suffix(".srt")
    json_path = output_base.with_suffix(".json")

    # Détecte le support DTW du binaire au lieu de supposer qu'il est présent.
    # Le préfixe fonctionne aussi sous Windows pour les wrappers de test .py.
    binary_command = _binary_invocation(binary)
    supports_dtw = False
    try:
        help_result = run_quiet(
            [*binary_command, "--help"], cwd=str(binary.parent), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=20, check=False,
        )
        help_text = (help_result.stdout or "") + "\n" + (help_result.stderr or "")
        supports_dtw = all(flag in help_text for flag in ("-dtw", "-ojf", "-nfa"))
    except (OSError, subprocess.TimeoutExpired):
        logger.info("Impossible de lire l'aide Whisper, utilisation du mode SRT standard.")

    command = [
        *binary_command, "-m", str(model_path.resolve()), "-f", str(audio_path.resolve()),
        "-l", language or "en", "-osrt", "-of", str(output_base), "-np",
    ]
    if supports_dtw:
        # whisper.cpp désactive lui-même DTW lorsque Flash Attention reste actif.
        command.extend(["-dtw", dtw_model_preset, "-ojf", "-nfa"])
    if threads > 0:
        command.extend(["-t", str(threads)])
    if vad_model_path and vad_model_path.is_file():
        command.extend(["--vad", "-vm", str(vad_model_path.resolve())])

    try:
        result = run_quiet(
            command, cwd=str(binary.parent), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TranscriptionError(f"Whisper a dépassé le délai de {timeout} secondes.") from exc
    except OSError as exc:
        raise TranscriptionError(f"Impossible de lancer whisper.cpp : {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Erreur whisper.cpp inconnue").strip()
        raise TranscriptionError(detail[-2500:])

    words = parse_whisper_json_words(json_path) if supports_dtw else []
    timestamp_mode = "word_dtw" if words else "segment_srt"
    if not words:
        words = parse_srt(srt_path)
    transcript_text = " ".join(word.text for word in words).strip()
    if not words:
        return {
            "status": "no_speech", "reason": "Aucune parole détectée.", "words": [], "text": "",
            "srt_path": str(srt_path) if srt_path.exists() else None,
            "timestamp_mode": timestamp_mode,
        }
    status = "completed" if timestamp_mode == "word_dtw" else "completed_segment_fallback"
    reason = (
        "Transcription locale terminée avec timestamps DTW par token regroupés en mots."
        if timestamp_mode == "word_dtw"
        else "Transcription locale terminée. Ce binaire ne fournit pas de timestamps DTW exploitables : captions par segment."
    )
    return {
        "status": status,
        "reason": reason,
        "words": words,
        "text": transcript_text,
        "srt_path": str(srt_path) if srt_path.exists() else None,
        "json_path": str(json_path) if json_path.exists() else None,
        "timestamp_mode": timestamp_mode,
    }


def detect_audio_peak_timestamps(
    wav_path: Path,
    window_seconds: float = 0.35,
    *,
    minimum_gap_seconds: float = 4.5,
    maximum_peaks: int = 5,
) -> list[float]:
    """Repère quelques accents audio nets, sans confondre bruit de fond et moments forts."""
    if not wav_path.is_file():
        return []
    try:
        with wave.open(str(wav_path), "rb") as audio:
            sample_rate = audio.getframerate()
            frames = audio.readframes(audio.getnframes())
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
        if sample_width != 2 or sample_rate <= 0:
            return []
        samples = array.array("h")
        samples.frombytes(frames)
        if channels > 1:
            samples = array.array("h", samples[::channels])
        window_size = max(1, int(sample_rate * window_seconds))
        hop_size = max(1, window_size // 2)
        measurements: list[tuple[float, float]] = []
        for start in range(0, len(samples), hop_size):
            chunk = samples[start:start + window_size]
            if len(chunk) < max(1, window_size // 3):
                continue
            square_sum = sum(int(value) * int(value) for value in chunk)
            rms = math.sqrt(square_sum / len(chunk)) / 32768.0
            center = (start + len(chunk) / 2) / sample_rate
            measurements.append((center, rms))
        if not measurements:
            return []
        levels = sorted(level for _, level in measurements)
        median_level = levels[len(levels) // 2]
        maximum_level = max(levels)
        # Avoid zooming on quiet room tone, compression noise or a uniformly loud mix.
        if maximum_level < 0.015 or maximum_level < median_level * 1.3:
            return []
        threshold = max(0.015, median_level * 1.65, maximum_level * 0.42)
        candidates: list[tuple[float, float]] = []
        for index, (center, level) in enumerate(measurements):
            before = measurements[index - 1][1] if index else -1.0
            after = measurements[index + 1][1] if index + 1 < len(measurements) else -1.0
            if level >= threshold and level >= before and level >= after:
                candidates.append((level, center))
        # Keep the strongest accents first, then restore chronological order.
        selected: list[tuple[float, float]] = []
        for candidate in sorted(candidates, reverse=True):
            if all(abs(candidate[1] - existing[1]) >= minimum_gap_seconds for existing in selected):
                selected.append(candidate)
                if len(selected) >= max(1, int(maximum_peaks)):
                    break
        return sorted(center for _, center in selected)
    except (OSError, wave.Error, ValueError):
        logger.exception("Impossible d'analyser les accents audio pour le cadrage dynamique.")
        return []


def detect_audio_peak_timestamp(wav_path: Path, window_seconds: float = 0.35) -> float:
    """Compatibilité historique : renvoie le centre du pic audio le plus fort."""
    peaks = detect_audio_peak_timestamps(wav_path, window_seconds, maximum_peaks=1)
    return peaks[0] if peaks else 0.0
