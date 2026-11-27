"""Sélection et validation du plan de montage Daily Best Of."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

MIN_EPISODE_SECONDS = 9 * 60
MAX_EPISODE_SECONDS = 11 * 60
MAX_SELECTED_CLIPS = 50


def build_best_of_plan(
    clips: list[dict[str, Any]],
    clip_ids: list[str],
    *,
    date_key: str | None = None,
) -> dict[str, Any]:
    """Build an ordered, local-only episode plan from explicitly validated Shorts."""
    if not isinstance(clip_ids, list) or not clip_ids:
        raise ValueError("Sélectionne au moins un Short.")
    if len(clip_ids) > MAX_SELECTED_CLIPS:
        raise ValueError(f"Un épisode ne peut pas contenir plus de {MAX_SELECTED_CLIPS} Shorts.")
    normalized_ids = [str(value).strip() for value in clip_ids]
    if any(not value for value in normalized_ids):
        raise ValueError("La sélection contient un identifiant vide.")
    if len(set(normalized_ids)) != len(normalized_ids):
        raise ValueError("Un même Short ne peut apparaître qu'une seule fois dans l'épisode.")

    by_id = {str(clip.get("id") or clip.get("job_id") or ""): clip for clip in clips}
    missing = [clip_id for clip_id in normalized_ids if clip_id not in by_id]
    if missing:
        raise ValueError("Certains Shorts sélectionnés ne sont plus dans la bibliothèque. Actualise la page.")

    ordered: list[dict[str, Any]] = []
    total_duration = 0.0
    for clip_id in normalized_ids:
        clip = by_id[clip_id]
        if clip.get("status") != "validated":
            raise ValueError("Seuls les Shorts validés peuvent entrer dans un Daily Best Of.")
        if date_key and str(clip.get("date_key") or "") != date_key:
            raise ValueError("Tous les Shorts d'un Daily Best Of doivent appartenir à la date sélectionnée.")
        output_path = Path(str(clip.get("output_path") or ""))
        if not output_path.is_file():
            raise ValueError(f"Le rendu du Short {clip_id[:8]} est introuvable sur ce PC.")
        try:
            duration = float(clip.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration <= 0 or not math.isfinite(duration):
            raise ValueError(f"La durée du Short {clip_id[:8]} est invalide.")
        total_duration += duration
        ordered.append({
            "id": clip_id,
            "job_id": str(clip.get("job_id") or clip_id),
            "title": str(clip.get("source_title") or clip.get("streamer") or "GTA moment"),
            "streamer": str(clip.get("streamer") or ""),
            "duration": duration,
            "output_path": str(output_path.resolve()),
            "thumbnail_path": str(clip.get("thumbnail_path") or ""),
            "date_key": str(clip.get("date_key") or ""),
        })

    total_duration = round(total_duration, 2)
    return {
        "clips": ordered,
        "clip_count": len(ordered),
        "total_duration": total_duration,
        "formatted_duration": f"{int(total_duration // 60):02d}:{int(total_duration % 60):02d}",
        "target_min_seconds": MIN_EPISODE_SECONDS,
        "target_max_seconds": MAX_EPISODE_SECONDS,
        "ready_for_render": MIN_EPISODE_SECONDS <= total_duration <= MAX_EPISODE_SECONDS,
        "remaining_to_minimum": round(max(0.0, MIN_EPISODE_SECONDS - total_duration), 2),
        "over_maximum": round(max(0.0, total_duration - MAX_EPISODE_SECONDS), 2),
        "date_key": date_key or (ordered[0]["date_key"] if ordered else ""),
    }


def build_best_of_filter_graph(
    clip_count: int,
    audio_input_indices: list[int],
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    clip_durations: list[float] | None = None,
) -> str:
    """Build a 16:9 landscape canvas for vertical Shorts and concatenate them."""
    if clip_count < 1 or len(audio_input_indices) != clip_count:
        raise ValueError("Le plan vidéo Daily Best Of est invalide.")
    if clip_durations is not None and (
        len(clip_durations) != clip_count or any(
            float(value) <= 0 or not math.isfinite(float(value)) for value in clip_durations
        )
    ):
        raise ValueError("Les durées du Daily Best Of sont invalides.")
    if width < 2 or height < 2 or fps < 1:
        raise ValueError("Les paramètres de sortie sont invalides.")
    parts: list[str] = []
    concat_inputs: list[str] = []
    for index, audio_index in enumerate(audio_input_indices):
        parts.append(
            f"[{index}:v:0]split=2[bgsrc{index}][fgsrc{index}];"
            f"[bgsrc{index}]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=24:8,setsar=1[bg{index}];"
            f"[fgsrc{index}]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"setsar=1[fg{index}];"
            f"[bg{index}][fg{index}]overlay=(W-w)/2:(H-h)/2,"
            f"fps={fps},"
            + (
                f"trim=duration={float(clip_durations[index]):.3f},setpts=PTS-STARTPTS,"
                if clip_durations is not None else ""
            )
            + f"format=yuv420p,setsar=1[v{index}];"
            + f"[{audio_index}:a:0]aresample=48000,apad,"
            + (
                f"atrim=duration={float(clip_durations[index]):.3f},"
                if clip_durations is not None else ""
            )
            + f"asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:channel_layouts=stereo[a{index}]"
        )
        concat_inputs.extend([f"[v{index}]", f"[a{index}]"])
    parts.append(
        "".join(concat_inputs) + f"concat=n={clip_count}:v=1:a=1[outv][outa]"
    )
    return ";".join(parts)


def render_best_of_episode(
    plan: dict[str, Any],
    output_path: Path,
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    encoder: str = "h264_amf",
    progress_callback: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Render validated vertical Shorts into one 1920x1080 landscape episode."""
    from studio.web.short_renderer import MediaError, probe_media, resolve_executable, run_command

    clips = plan.get("clips") if isinstance(plan, dict) else None
    if not plan.get("ready_for_render") or not isinstance(clips, list) or not clips:
        raise ValueError("La sélection doit être vérifiée et durer entre 9 et 11 minutes.")
    if len(clips) > MAX_SELECTED_CLIPS:
        raise ValueError(f"Un épisode ne peut pas contenir plus de {MAX_SELECTED_CLIPS} Shorts.")
    if encoder not in {"h264_amf", "libx264"}:
        raise ValueError("Encodeur vidéo non pris en charge.")

    def report_progress(progress: int, message: str) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(max(0, min(99, int(progress))), message)
        except Exception:
            # An unavailable progress display must never interrupt a video render.
            logger.exception("Impossible de mettre à jour la progression du Daily Best Of.")

    report_progress(4, "Vérification des clips sources")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [resolve_executable(ffmpeg), "-hide_banner", "-y"]
    audio_input_indices: list[int] = []
    for index, clip in enumerate(clips):
        source = Path(str(clip.get("output_path") or ""))
        if not source.is_file():
            raise MediaError(f"Le rendu du Short {str(clip.get('id') or '')[:8]} est introuvable.")
        info = probe_media(source, ffprobe)
        if not info.get("width") or not info.get("height"):
            raise MediaError(f"Impossible de lire la vidéo du Short {str(clip.get('id') or '')[:8]}.")
        command.extend(["-i", str(source.resolve())])
        if info.get("has_audio"):
            audio_input_indices.append(len(audio_input_indices))
        else:
            audio_input_indices.append(-1)
        report_progress(
            5 + int(5 * (index + 1) / len(clips)),
            f"Vérification des sources · {index + 1}/{len(clips)}",
        )

    # Add explicit silent tracks for Shorts without audio. Keeping each source
    # as a separate input avoids concat-demuxer assumptions about stream layouts.
    source_input_count = len(clips)
    for index, clip in enumerate(clips):
        if audio_input_indices[index] < 0:
            duration = max(0.1, float(clip.get("duration") or 0.1))
            audio_input_indices[index] = source_input_count
            command.extend([
                "-f", "lavfi", "-t", f"{duration:.3f}",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            ])
            source_input_count += 1
        else:
            audio_input_indices[index] = index

    graph = build_best_of_filter_graph(
        len(clips), audio_input_indices,
        clip_durations=[float(clip.get("duration") or 0.0) for clip in clips],
    )
    total_duration = sum(float(clip.get("duration") or 0.0) for clip in clips)
    command.extend([
        "-filter_complex", graph,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", encoder, "-b:v", "12M",
        "-r", "30", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-max_muxing_queue_size", "2048",
    ])
    if progress_callback is not None:
        command.extend(["-progress", "pipe:1", "-stats_period", "1", "-nostats"])
    command.append(str(output_path.resolve()))

    def encoding_progress(elapsed_seconds: float) -> None:
        if total_duration <= 0:
            return
        ratio = max(0.0, min(1.0, elapsed_seconds / total_duration))
        report_progress(10 + int(round(ratio * 83)), f"Encodage 16:9 · {10 + int(round(ratio * 83))}%")

    try:
        if progress_callback is None:
            run_command(command, timeout=3600)
        else:
            run_command(command, timeout=3600, progress_callback=encoding_progress)
    except MediaError as exc:
        detail = str(exc).casefold()
        if encoder != "h264_amf" or not any(
            marker in detail for marker in ("amf", "encoder", "device", "initializing output stream")
        ):
            raise
        # Some Windows systems expose AMF in FFmpeg but cannot initialize the
        # driver at runtime. Retry once with the CPU encoder rather than losing
        # the whole episode.
        report_progress(10, "Encodeur AMD indisponible · reprise CPU")
        command[command.index("-c:v") + 1] = "libx264"
        bitrate_index = command.index("-b:v")
        command[bitrate_index:bitrate_index + 2] = ["-preset", "veryfast", "-crf", "20"]
        if progress_callback is None:
            run_command(command, timeout=3600)
        else:
            run_command(command, timeout=3600, progress_callback=encoding_progress)
    report_progress(95, "Vérification du fichier exporté")
    result = probe_media(output_path, ffprobe, timeout=90)
    if int(result.get("width") or 0) != 1920 or int(result.get("height") or 0) != 1080:
        raise MediaError("Le fichier Daily Best Of exporté n'est pas au format 1920 × 1080.")
    if not result.get("has_audio"):
        raise MediaError("La vidéo finale ne contient aucune piste audio.")
    return {
        "output_path": str(output_path.resolve()),
        "duration": round(float(result.get("duration") or 0.0), 2),
        "width": 1920,
        "height": 1080,
        "clip_count": len(clips),
        "file_size_bytes": output_path.stat().st_size,
    }
