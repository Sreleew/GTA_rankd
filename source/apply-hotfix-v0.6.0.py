from __future__ import annotations

import re
import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"Patch v0.6.0 impossible : {count} occurrence(s) du bloc « {label} » dans {path}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"Patch v0.6.0 impossible : bloc « {label} » absent dans {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def patch_speakers(root: Path) -> None:
    path = root / "studio/web/speakers.py"
    path.write_text(
        '''"""Filtrage prudent des sous-titres par diarisation locale des voix."""

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
''',
        encoding="utf-8",
    )

    tests = root / "tests/test_speakers.py"
    tests.write_text(
        '''from __future__ import annotations

from types import SimpleNamespace

from studio.web.short_editor import WordTiming
from studio.web.speakers import filter_dominant_speaker


def test_filter_keeps_words_assigned_to_a_clear_dominant_voice() -> None:
    words = [
        WordTiming(0.2, 0.6, "BRO"),
        WordTiming(0.7, 1.0, "WHAT"),
        WordTiming(3.2, 3.6, "HELLO"),
    ]
    segments = [
        SimpleNamespace(start=0.0, end=2.7, speaker="SPEAKER_00"),
        SimpleNamespace(start=3.0, end=3.8, speaker="SPEAKER_01"),
    ]
    filtered, report = filter_dominant_speaker(words, segments)

    assert [word.text for word in filtered] == ["BRO", "WHAT"]
    assert report["status"] == "dominant_filtered"
    assert report["selected_speaker"] == "SPEAKER_00"


def test_filter_falls_back_to_all_voices_when_dominance_is_ambiguous() -> None:
    words = [WordTiming(0.2, 0.6, "BRO"), WordTiming(0.7, 1.0, "WHAT")]
    segments = [
        {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 2.0, "speaker": "SPEAKER_01"},
    ]
    filtered, report = filter_dominant_speaker(words, segments)

    assert filtered == words
    assert report["status"] == "fallback_all_voices"


def test_filter_keeps_words_when_only_one_voice_is_present() -> None:
    words = [WordTiming(0.1, 0.5, "HELLO")]
    filtered, report = filter_dominant_speaker(
        words, [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
    )

    assert filtered == words
    assert report["status"] == "single_speaker"


def test_filter_falls_back_if_too_few_words_match_dominant_voice() -> None:
    words = [WordTiming(0.1, 0.2, "A"), WordTiming(4.0, 4.1, "B")]
    segments = [
        {"start": 0.0, "end": 3.0, "speaker": "SPEAKER_00"},
        {"start": 3.1, "end": 4.2, "speaker": "SPEAKER_01"},
    ]
    filtered, report = filter_dominant_speaker(words, segments)

    assert filtered == words
    assert report["status"] == "fallback_all_voices"
''',
        encoding="utf-8",
    )


def patch_worker(root: Path) -> None:
    worker = root / "studio/web/worker.py"
    replace_once(
        worker,
        '            render_words = rebase_word_timings(all_words, trim_start, trim_end) if all_words else []\n            render_peak_timestamp = max(0.0, peak_timestamp - trim_start)\n            render_transcript = " ".join(word.text for word in render_words).strip()\n',
        '''            render_words = rebase_word_timings(all_words, trim_start, trim_end) if all_words else []
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
            render_transcript = " ".join(word.text for word in render_words).strip()
''',
        "filtrage des mots avant les métadonnées et sous-titres",
    )
    replace_once(
        worker,
        '                timeout=int(self.config.get("ollama", "request_timeout_seconds", default=120)),\n                retries=int(self.config.get("ollama", "retries", default=2)),',
        '                timeout=min(20, max(5, int(self.config.get("ollama", "request_timeout_seconds", default=20)))),\n                retries=0,',
        "limitation du délai de génération des métadonnées",
    )
    replace_once(
        worker,
        '                "transcript": transcript_result.get("text", ""),\n                "generation_stage": "short_edit_v0.3.1",',
        '                "transcript": render_transcript,\n                "speaker_filter": speaker_filter,\n                "generation_stage": "short_edit_v0.6.0",',
        "stockage du transcript filtré et du résultat de diarisation",
    )


def patch_app(root: Path) -> None:
    app = root / "studio/web/app.py"
    replace_once(
        app,
        '    auto_trim_enabled: bool = True, sfx_enabled: bool = True,\n) -> dict:',
        '    auto_trim_enabled: bool = True, sfx_enabled: bool = True,\n    caption_voice_mode: str = "dominant",\n) -> dict:',
        "mode de voix dans la validation des options",
    )
    replace_once(
        app,
        '    if not 0 <= int(zoom_percent) <= 20:\n        raise HTTPException(status_code=400, detail="Le zoom doit être compris entre 0 et 20 %.")\n    return {',
        '''    if not 0 <= int(zoom_percent) <= 20:
        raise HTTPException(status_code=400, detail="Le zoom doit être compris entre 0 et 20 %.")
    if caption_voice_mode not in {"all", "dominant"}:
        raise HTTPException(status_code=400, detail="Le mode de voix doit être 'all' ou 'dominant'.")
    return {''',
        "validation du mode de voix",
    )
    replace_once(
        app,
        '        "captions_enabled": bool(captions_enabled), "brand_enabled": bool(brand_enabled),\n        "auto_trim_enabled": bool(auto_trim_enabled), "sfx_enabled": bool(sfx_enabled),',
        '        "captions_enabled": bool(captions_enabled), "brand_enabled": bool(brand_enabled),\n        "caption_voice_mode": caption_voice_mode,\n        "auto_trim_enabled": bool(auto_trim_enabled), "sfx_enabled": bool(sfx_enabled),',
        "sauvegarde du mode de voix",
    )

    form_field = '        captions_enabled: Annotated[bool, Form()] = True,\n'
    replace_all(
        app,
        form_field,
        form_field + '        caption_voice_mode: Annotated[str, Form()] = "dominant",\n',
        "champ mode de voix sur les formulaires",
    )
    call_old = "options = _validate_edit_options(layout, crop_x, crop_y, dynamic_zoom, zoom_percent, captions_enabled, brand_enabled, hook_text, context_text, auto_trim_enabled, sfx_enabled)"
    call_new = "options = _validate_edit_options(layout, crop_x, crop_y, dynamic_zoom, zoom_percent, captions_enabled, brand_enabled, hook_text, context_text, auto_trim_enabled, sfx_enabled, caption_voice_mode)"
    replace_all(app, call_old, call_new, "transmission du mode de voix")

    replace_once(
        app,
        '        webcam_zone = str(scan_metadata.get("webcam_zone", "none"))\n        if webcam_zone not in {"none", "top-left", "top-right", "bottom-left", "bottom-right"}:\n            webcam_zone = "none"\n        options = {\n            "layout": "blur", "crop_x": 50, "crop_y": 50, "dynamic_zoom": False, "zoom_percent": 0,\n            "captions_enabled": True, "brand_enabled": True, "auto_trim_enabled": False, "sfx_enabled": True,\n            "hook_text": "", "context_text": "",',
        '        options = {\n            "layout": "blur", "crop_x": 50, "crop_y": 50, "dynamic_zoom": False, "zoom_percent": 0,\n            "captions_enabled": True, "caption_voice_mode": "dominant",\n            "brand_enabled": True, "auto_trim_enabled": False, "sfx_enabled": True,\n            "hook_text": "", "context_text": "",',
        "mode voix dominante pour les candidats Moments forts",
    )
    replace_once(
        app,
        '            "streamer": scan.get("streamer", ""), "note": f"Moment fort détecté automatiquement · {candidate[\\'score\\']}/100",',
        '            "streamer": scan.get("streamer", ""), "note": "",',
        "suppression du score automatique dans la note éditoriale",
    )

    html = root / "studio/web/static/index.html"
    html_text = html.read_text(encoding="utf-8-sig")
    old_label = '<label><input type="checkbox" name="captions_enabled" checked data-option-checkbox> Sous-titres anglais (mot à mot si DTW disponible)</label>'
    new_label = old_label + '\\n                  <label>Voix à sous-titrer <select name="caption_voice_mode"><option value="dominant" selected>Voix dominante uniquement (bêta)</option><option value="all">Toutes les voix</option></select><small>Si les voix sont difficiles à distinguer, toutes les paroles sont conservées.</small></label>'
    if new_label not in html_text:
        count = html_text.count(old_label)
        if count != 2:
            raise SystemExit(f"Patch v0.6.0 impossible : {count} sélecteur(s) de sous-titres dans index.html")
        html_text = html_text.replace(old_label, new_label)
    html.write_text(html_text, encoding="utf-8")


def patch_metadata(root: Path) -> None:
    path = root / "studio/web/metadata.py"
    replace_once(
        path,
        '''def _limit_words(value: str, maximum: int) -> str:
    words = str(value or "").split()
    return " ".join(words[:maximum]).strip()


def _fallback_metadata(''',
        '''def _limit_words(value: str, maximum: int) -> str:
    words = str(value or "").split()
    return " ".join(words[:maximum]).strip()


def _fallback_hook(transcript: str) -> str:
    """Choose a short, factual teaser from the actual spoken words."""
    words = re.findall(r"[A-Za-z0-9’']+", str(transcript or ""))
    if not words:
        return "WAIT FOR THE REACTION"
    cues = {
        "what", "wait", "bro", "no", "oh", "why", "look", "listen",
        "insane", "crazy", "actually", "help", "stop", "how", "you",
    }
    cue_index = next((i for i, word in enumerate(words) if word.lower() in cues), 0)
    start = max(0, cue_index - 2)
    chosen = words[start:start + 6]
    if len(chosen) < 3:
        chosen = words[:6]
    return " ".join(chosen).upper()


def _fallback_metadata(''',
        "ajout du hook de secours fondé sur la transcription",
    )
    replace_once(
        path,
        '    note_text = note.strip()\n    context = _limit_words(custom_context or note_text, 10)\n    hook = _limit_words(custom_hook or "WAIT FOR IT...", 8)\n    if note_text and not custom_hook:\n        hook = _limit_words(note_text, 8)',
        '    note_text = note.strip()\n    context = _limit_words(custom_context, 10)\n    hook = _limit_words(custom_hook or _fallback_hook(transcript), 6)',
        "fallback hook sans score ni note automatique",
    )
    replace_once(
        path,
        '    prompt_rules = "You are an English-language GTA VI short-form video editor. Never invent facts, names, events, locations, mechanics or reactions. Use only the transcript and the metadata below. Return valid JSON only. hook_text must be at most 8 words; context_card at most 10 words; title at most 60 characters; thumbnail_text at most 4 words; hashtags at most 3. description must contain 2 short lines, then a credit line."',
        '    prompt_rules = "You are an expert English-language short-form gaming editor. Create one strong, specific curiosity hook for the FIRST 2.6 seconds only. Keep it to 3-6 words, use only facts supported by the transcript, create an open loop without revealing the payoff, and never invent a reaction. Do not use generic labels such as Moment detected, 100/100, WAIT FOR IT, or GTA VI MOMENT. Never invent facts, names, events, locations or mechanics. Return valid JSON only. context_card must be empty unless the user supplied a custom context. hook_text at most 6 words; context_card at most 10 words; title at most 60 characters; thumbnail_text at most 4 words; hashtags at most 3. description: 2 short lines, then a credit line."',
        "prompt de hook éditorial plus court et non générique",
    )
    replace_once(
        path,
        '            context = _limit_words(custom_context or str(data.get("context_card", fallback["context_card"])), 10)',
        '            context = _limit_words(custom_context, 10)',
        "suppression du doublon de contexte généré par le LLM",
    )
    replace_once(
        path,
        '            hook = _limit_words(custom_hook or str(data.get("hook_text", fallback["hook_text"])), 8)',
        '            hook = _limit_words(custom_hook or str(data.get("hook_text", fallback["hook_text"])), 6)',
        "limitation du hook à six mots",
    )


def patch_highlight_download(root: Path) -> None:
    highlights = root / "studio/web/highlights.py"
    replace_once(
        highlights,
        '            "format": "bv*+ba/best",\n            "merge_output_format": "mp4",\n            "noplaylist": True,\n            "quiet": True,\n            "no_warnings": True,\n            "restrictfilenames": True,\n            "concurrent_fragment_downloads": 4,\n            "retries": 5,\n            "fragment_retries": 5,',
        '            "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/best",\n            "merge_output_format": "mp4",\n            "noplaylist": True,\n            "quiet": True,\n            "no_warnings": True,\n            "restrictfilenames": True,\n            "continuedl": True,\n            "concurrent_fragment_downloads": 4,\n            "retries": 8,\n            "fragment_retries": 8,\n            "file_access_retries": 5,\n            "skip_unavailable_fragments": True,',
        "optimisation du téléchargement Twitch",
    )
    worker = root / "studio/web/worker.py"
    replace_once(
        worker,
        '            "format": "bv*+ba/best",\n            "merge_output_format": "mp4",\n            "noplaylist": True,\n            "quiet": True,\n            "no_warnings": True,\n            "restrictfilenames": True,',
        '            "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/best",\n            "merge_output_format": "mp4",\n            "noplaylist": True,\n            "quiet": True,\n            "no_warnings": True,\n            "restrictfilenames": True,\n            "continuedl": True,\n            "concurrent_fragment_downloads": 4,\n            "retries": 8,\n            "fragment_retries": 8,\n            "file_access_retries": 5,',
        "optimisation du téléchargement des URL de Shorts",
    )


def patch_model_resume(root: Path) -> None:
    path = root / "studio/web/model_manager.py"
    text = path.read_text(encoding="utf-8-sig")
    start = text.index("    def _download_whisper(self) -> None:")
    end = text.index("\n    def ", start + 8)
    replacement = '''    def _download_whisper(self) -> None:
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
                    match = re.match(r"bytes\\s+(\\d+)-(\\d+)/(\\d+|\\*)", content_range, re.IGNORECASE)
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
'''
    if replacement not in text[start:end]:
        text = text[:start] + replacement + text[end:]
        # re is needed for parsing Content-Range.
        if "\nimport re\n" not in text:
            text = text.replace("import logging\n", "import logging\nimport re\n", 1)
        path.write_text(text, encoding="utf-8")
    # Reflect an existing partial download in the immediate status shown to the user.
    start_method = text.index("    def start_whisper_download(")
    end_method = text.index("\n    def ", start_method + 8)
    block = text[start_method:end_method]
    old_state = '''            self._state = {
                "status": "downloading", "progress": 0, "downloaded_bytes": 0,
                "total_bytes": 0, "message": "Connexion à Hugging Face...",
            }'''
    new_state = '''            partial = self.whisper_model_path.with_suffix(self.whisper_model_path.suffix + ".part")
            partial_bytes = partial.stat().st_size if partial.is_file() else 0
            self._state = {
                "status": "downloading", "progress": 0, "downloaded_bytes": partial_bytes,
                "total_bytes": 0,
                "message": f"Reprise possible : {partial_bytes / (1024 ** 3):.2f} Go déjà reçus" if partial_bytes else "Connexion à Hugging Face...",
            }'''
    if new_state not in block:
        if old_state not in block:
            raise SystemExit("Bloc d'état du téléchargement Whisper introuvable.")
        block = block.replace(old_state, new_state, 1)
        text = path.read_text(encoding="utf-8-sig")
        start_method = text.index("    def start_whisper_download(")
        end_method = text.index("\n    def ", start_method + 8)
        path.write_text(text[:start_method] + block + text[end_method:], encoding="utf-8")


def patch_tests(root: Path) -> None:
    tests = root / "tests/test_speakers.py"
    if not tests.is_file():
        raise SystemExit("Les tests de diarisation ne sont pas présents.")

    test_model = root / "tests/test_model_manager.py"
    existing = test_model.read_text(encoding="utf-8-sig")
    if "test_model_manager_resumes_partial_download_with_http_range" not in existing:
        existing += '''

def test_model_manager_resumes_partial_download_with_http_range(tmp_path: Path, monkeypatch):
    from studio.web import model_manager

    model = tmp_path / "ggml-large-v3-turbo.bin"
    partial = model.with_suffix(model.suffix + ".part")
    partial.write_bytes(b"a" * 64)
    manager = ModelManager(model)
    monkeypatch.setattr(model_manager, "MIN_WHISPER_MODEL_BYTES", 1)
    captured = {}

    class FakeResponse:
        status = 206
        headers = {"Content-Length": "64", "Content-Range": "bytes 64-127/128"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return self.status

        def read(self, size=-1):
            if captured.get("read"):
                return b""
            captured["read"] = True
            return b"b" * 64

    def fake_urlopen(request, timeout=0):
        captured["range"] = request.headers.get("Range")
        return FakeResponse()

    monkeypatch.setattr(model_manager.urllib.request, "urlopen", fake_urlopen)
    manager._download_whisper()

    assert captured["range"] == "bytes=64-"
    assert model.read_bytes() == b"a" * 64 + b"b" * 64
    assert not partial.exists()
    assert manager.status()["status"] == "ready"
'''
        test_model.write_text(existing, encoding="utf-8")

    test_metadata = root / "tests/test_metadata.py"
    replace_once(
        test_metadata,
        'def test_custom_hook_and_context_override_fallback() -> None:\n',
        '''def test_fallback_hook_uses_transcript_and_does_not_create_score_context() -> None:
    from studio.web.metadata import _fallback_metadata

    metadata = _fallback_metadata(
        streamer="Streamer",
        note="Moment fort détecté automatiquement · 100/100",
        source_url="",
        transcript="oh my days God bless the United States what just happened",
        custom_hook="",
        custom_context="",
    )

    assert metadata["hook_text"]
    assert len(metadata["hook_text"].split()) <= 6
    assert metadata["context_card"] == ""
    assert "100/100" not in metadata["hook_text"]


def test_custom_hook_and_context_override_fallback() -> None:
''',
        "test du hook transcript et absence de carte de score",
    )


def patch_release_docs(root: Path) -> None:
    for relative in (
        "installer/apply_update.ps1",
        "installer/update_from_archive.ps1",
        "installer/install.ps1",
    ):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        entry = "'NOTES-v0.6.0.txt', 'VERIFICATION-v0.6.0.md'"
        if entry not in text:
            anchor = "'NOTES-v0.5.1.txt', 'VERIFICATION-v0.5.1.md'"
            if anchor not in text:
                raise SystemExit(f"Liste de fichiers root absente dans {relative}")
            text = text.replace(anchor, anchor + ", " + entry, 1)
        path.write_text(text, encoding="utf-8-sig", newline="\r\n")

    (root / "VERSION.txt").write_text("GTA Ranked Studio\nVersion: 0.6.0\n", encoding="utf-8")
    replace_once(root / "pyproject.toml", 'version = "0.5.1"', 'version = "0.6.0"', "version pyproject.toml")
    replace_once(root / "config.yaml.default", "  version: 0.5.1", "  version: 0.6.0", "version config.yaml.default")

    (root / "NOTES-v0.6.0.txt").write_text(
        """GTA Ranked Studio v0.6.0

Sous-titrage des voix :
- Nouveau mode « Voix dominante uniquement (bêta) » pour les Shorts issus d'une VOD ou d'un clip.
- Le moteur local de diarisation est installé à la demande lors de la première utilisation.
- Si les voix sont trop proches ou si le filtrage est incertain, toutes les paroles sont conservées.
- Le mode « Toutes les voix » reste disponible.

Hooks et montage :
- Un hook court, spécifique et fondé sur la transcription apparaît au début du Short.
- Le score de détection n'est plus affiché comme hook ou carte de contexte.
- La carte de contexte reste masquée sauf saisie personnalisée.
- La génération de métadonnées Ollama est limitée à une tentative courte, avec fallback local.

Téléchargements :
- Les VOD Twitch utilisent une qualité maximale de 1080p pour les Shorts 1080 × 1920.
- Téléchargements HLS plus robustes avec davantage de tentatives et de fragments concurrents.
- Le téléchargement du modèle Whisper reprend une partie .part existante quand le serveur supporte HTTP Range.

Les vidéos, modèles déjà installés, projets, réglages et données locales sont préservés.
Le moteur de diarisation tiers est bêta, CPU-only et installé séparément à la première utilisation. L'identification automatique de la voix du streamer n'est pas garantie ; en cas de doute, toutes les voix sont conservées.
""",
        encoding="utf-8",
    )
    (root / "VERIFICATION-v0.6.0.md").write_text(
        """# Vérification v0.6.0

- Tests unitaires de sélection d'une voix dominante, de fallback prudent et du cas mono-voix.
- Le moteur diarize est chargé et installé uniquement à la demande.
- Le pipeline extrait l'audio du Short final et non l'intégralité de la VOD pour la diarisation.
- Les erreurs d'installation ou d'analyse des voix ne bloquent pas le rendu : les sous-titres de toutes les voix sont restaurés.
- Le hook utilise un maximum de six mots et la carte de contexte ne s'affiche que si elle est personnalisée.
- Les délais Ollama sont plafonnés à 20 secondes avec un seul essai.
- Le gestionnaire du modèle Whisper conserve les téléchargements partiels et reprend via HTTP Range quand le serveur l'autorise.
- Téléchargement Twitch plafonné à 1080p avec tentatives et fragments concurrents supplémentaires.
""",
        encoding="utf-8",
    )

    for relative in ("README.md", "docs/UPDATES.md"):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        marker = "## v0.6.0 : diarisation, hooks et téléchargements"
        if marker not in text:
            text += """

## v0.6.0 : diarisation, hooks et téléchargements

Le mode « Voix dominante uniquement (bêta) » identifie les intervenants sur l'audio du Short final et ne conserve les mots de la voix dominante que si l'écart entre locuteurs est suffisamment clair. Le moteur CPU local est installé à la demande ; en cas d'incertitude, toutes les voix restent sous-titrées. Les hooks sont raccourcis et fondés sur la transcription, la carte de contexte est désactivée par défaut, et la génération de métadonnées est limitée à 20 secondes. Les téléchargements Twitch sont limités à 1080p avec davantage de fragments concurrents et de tentatives. Les téléchargements du modèle Whisper reprennent les fichiers partiels lorsque le serveur accepte HTTP Range.
"""
        path.write_text(text, encoding="utf-8")

    readme = root / "README.md"
    content = readme.read_text(encoding="utf-8-sig")
    content = content.replace("Dernière version stable : **0.5.1**.", "Dernière version stable : **0.6.0**.")
    readme.write_text(content, encoding="utf-8")


def apply(root: Path) -> None:
    root = root.resolve()
    patch_speakers(root)
    patch_worker(root)
    patch_app(root)
    patch_metadata(root)
    patch_highlight_download(root)
    patch_model_resume(root)
    patch_tests(root)
    patch_release_docs(root)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.6.0.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
