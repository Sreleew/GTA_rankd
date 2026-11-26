"""Rendu de Shorts verticaux avec FFmpeg, cadrage plein écran et finitions."""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from studio.process import run_quiet

logger = logging.getLogger(__name__)


class MediaError(RuntimeError):
    """Erreur lisible pendant l'analyse ou le rendu vidéo."""


def resolve_executable(name: str | Path) -> str:
    value = str(name)
    path = shutil.which(value)
    if path:
        return path
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    raise MediaError(f"Exécutable introuvable : {value}. Vérifie le PATH Windows.")


def run_command(
    args: Sequence[str], timeout: int | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    logger.info("Commande média : %s", " ".join(str(part) for part in args))
    try:
        result = run_quiet(
            list(args), capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False, cwd=str(cwd) if cwd else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"Commande interrompue après {timeout} secondes.") from exc
    except OSError as exc:
        raise MediaError(f"Impossible de lancer {args[0]} : {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Erreur FFmpeg inconnue").strip()
        raise MediaError(detail[-3500:])
    return result


def probe_timeout_for_file(input_path: Path) -> int:
    """Return a generous FFprobe timeout scaled to the downloaded media size.

    Twitch VOD downloads can be large or have container indexes that take much
    longer to inspect than a short clip. Keep a five-minute floor, add one
    minute per 256 MiB, and cap the wait at thirty minutes.
    """
    try:
        size_bytes = max(0, int(input_path.stat().st_size))
    except OSError:
        size_bytes = 0
    size_steps = size_bytes // (256 * 1024 * 1024)
    return min(30 * 60, max(5 * 60, 3 * 60 + int(size_steps) * 60))


def probe_media(
    input_path: Path,
    ffprobe: str = "ffprobe",
    *,
    timeout: int = 60,
) -> dict[str, Any]:
    ffprobe_bin = resolve_executable(ffprobe)
    result = run_command([
        ffprobe_bin, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(input_path.resolve())
    ], timeout=timeout)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError("FFprobe a renvoyé des métadonnées invalides.") from exc
    streams = data.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if video is None:
        raise MediaError("Le fichier ne contient aucune piste vidéo.")
    duration_raw = data.get("format", {}).get("duration") or video.get("duration")
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError) as exc:
        raise MediaError("Durée de la vidéo introuvable.") from exc
    if duration <= 0:
        raise MediaError("La durée de la vidéo doit être supérieure à zéro.")
    rate_raw = video.get("avg_frame_rate") or video.get("r_frame_rate") or "30/1"
    try:
        fps = float(Fraction(rate_raw))
    except (ValueError, ZeroDivisionError):
        fps = 30.0
    return {
        "duration": duration,
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "has_audio": audio is not None,
        "fps": fps,
        "video_codec": video.get("codec_name", "unknown"),
        "audio_codec": audio.get("codec_name") if audio else None,
    }


def _filter_path(path: Path | str, project_root: Path | None) -> str:
    value = Path(path)
    if project_root:
        try:
            value = value.resolve().relative_to(project_root.resolve())
        except ValueError:
            value = Path(path).resolve()
    text = value.as_posix()
    text = text.replace("\\\\", "/").replace("'", r"\\'").replace(":", r"\\:").replace(",", r"\\,")
    return f"'{text}'"


def build_filter_complex(
    width: int = 1080,
    height: int = 1920,
    blur: int = 28,
    *,
    layout: str = "blur",
    crop_x: int = 50,
    crop_y: int = 50,
    ass_file: Path | None = None,
    fonts_dir: Path | None = None,
    project_root: Path | None = None,
    dynamic_zoom: bool = False,
    peak_timestamp: float = 0.0,
    fps: int = 30,
    zoom_percent: int = 0,
    webcam_zone: str = "none",
    video_source: str = "[0:v]",
) -> str:
    """Build a vertical canvas while preserving the complete source frame.

    The legacy webcam_zone argument is accepted for compatibility with jobs
    created by v0.5.0, but no webcam crop or extraction is performed.
    """
    if width <= 0 or height <= 0:
        raise ValueError("Les dimensions de sortie doivent être positives.")
    if layout not in {"fill", "blur"}:
        raise ValueError("Le layout doit être 'fill' ou 'blur'.")

    crop_x = max(0, min(100, int(crop_x))) / 100
    crop_y = max(0, min(100, int(crop_y))) / 100
    if layout == "fill":
        base = (
            f"{video_source}scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:(in_w-out_w)*{crop_x:.3f}:(in_h-out_h)*{crop_y:.3f},setsar=1[base]"
        )
    else:
        base = (
            f"{video_source}split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur={blur}:10,setsar=1[bg];"
            f"[fgsrc]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"setsar=1[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]"
        )

    graph = base + ";"
    if dynamic_zoom and zoom_percent > 0:
        start = max(0.0, float(peak_timestamp) - 0.45)
        end = max(start + 0.25, float(peak_timestamp) + 0.85)
        zoom = 1.0 + max(0, min(20, int(zoom_percent))) / 100
        graph += (
            f"[base]zoompan=z='if(between(in_time,{start:.3f},{end:.3f}),"
            f"1+({zoom - 1.0:.3f})*sin(PI*(in_time-{start:.3f})/{max(0.25, end - start):.3f}),1.0)':"
            f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={fps},setsar=1[zoomed];"
        )
        current = "zoomed"
    else:
        current = "base"

    if ass_file:
        ass_option = f"ass=filename={_filter_path(ass_file, project_root)}"
        if fonts_dir:
            ass_option += f":fontsdir={_filter_path(fonts_dir, project_root)}"
        graph += f"[{current}]{ass_option},format=yuv420p[v]"
    else:
        graph += f"[{current}]format=yuv420p[v]"
    return graph

def build_render_command(
    ffmpeg: str,
    input_path: Path,
    output_path: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    bitrate: str = "12M",
    loudness_lufs: int = -14,
    has_audio: bool = True,
    encoder: str = "h264_amf",
    fps: int = 30,
    layout: str = "blur",
    crop_x: int = 50,
    crop_y: int = 50,
    ass_file: Path | None = None,
    fonts_dir: Path | None = None,
    project_root: Path | None = None,
    dynamic_zoom: bool = False,
    peak_timestamp: float = 0.0,
    zoom_percent: int = 0,
    webcam_zone: str = "none",
    duration: float | None = None,
    trim_start: float = 0.0,
    trim_duration: float | None = None,
    sound_effect_path: Path | None = None,
    sound_effect_offset: float = 0.0,
    sound_effect_volume: float = 0.14,
    edit_segments: Sequence[tuple[float, float]] | None = None,
) -> list[str]:
    normalized_segments: list[tuple[float, float]] = []
    if edit_segments:
        window_duration = float(trim_duration) if trim_duration is not None else max(
            end for _, end in edit_segments
        )
        previous_end = 0.0
        for raw_start, raw_end in edit_segments:
            start = float(raw_start)
            end = float(raw_end)
            if (
                not math.isfinite(start) or not math.isfinite(end)
                or start < 0 or end <= start
                or start < previous_end - 0.001
                or end > window_duration + 0.05
            ):
                raise ValueError("Les segments de montage doivent être croissants, non chevauchants et dans l'extrait source.")
            normalized_segments.append((start, end))
            previous_end = end
        if len(normalized_segments) < 2:
            normalized_segments = []

    edit_parts: list[str] = []
    video_source = "[0:v]"
    audio_source = "[0:a:0]"
    if normalized_segments:
        for index, (start, end) in enumerate(normalized_segments):
            edit_parts.append(
                f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[vseg{index}]"
            )
            if has_audio:
                audio_segment = (
                    f"[0:a:0]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS"
                )
                segment_duration = end - start
                # Short edge fades prevent clicks/pops at automatic jump cuts.
                # Keep the opening and final fade to the global audio envelope.
                if index > 0 and segment_duration > 0.12:
                    audio_segment += ",afade=t=in:st=0:d=0.04"
                if index < len(normalized_segments) - 1 and segment_duration > 0.12:
                    audio_segment += f",afade=t=out:st={segment_duration - 0.04:.3f}:d=0.04"
                edit_parts.append(f"{audio_segment}[aseg{index}]")
        concat_inputs = "".join(
            f"[vseg{index}]" + (f"[aseg{index}]" if has_audio else "")
            for index in range(len(normalized_segments))
        )
        edit_parts.append(
            f"{concat_inputs}concat=n={len(normalized_segments)}:v=1:a={1 if has_audio else 0}"
            + ("[vcut][acut]" if has_audio else "[vcut]")
        )
        video_source = "[vcut]"
        if has_audio:
            audio_source = "[acut]"

    filter_graph = build_filter_complex(
        width, height, layout=layout, crop_x=crop_x, crop_y=crop_y,
        ass_file=ass_file, fonts_dir=fonts_dir, project_root=project_root,
        dynamic_zoom=dynamic_zoom, peak_timestamp=peak_timestamp, fps=fps,
        zoom_percent=zoom_percent, video_source=video_source,
    )
    if edit_parts:
        filter_graph = ";".join(edit_parts) + ";" + filter_graph
    command = [resolve_executable(ffmpeg), "-hide_banner", "-y"]
    if trim_start > 0:
        command.extend(["-ss", f"{trim_start:.3f}"])
    command.extend(["-i", str(input_path.resolve())])
    sfx_file = Path(sound_effect_path).resolve() if sound_effect_path and Path(sound_effect_path).is_file() else None
    use_sfx = bool(has_audio and sfx_file)
    if use_sfx:
        command.extend(["-i", str(sfx_file)])
    source_window_duration = float(trim_duration) if trim_duration is not None else None
    if normalized_segments and source_window_duration is None:
        source_window_duration = max(end for _, end in normalized_segments)
    if source_window_duration is not None and source_window_duration > 0:
        command.extend(["-t", f"{source_window_duration:.3f}"])

    if use_sfx:
        offset_ms = max(0, int(max(0.0, float(sound_effect_offset)) * 1000))
        volume = max(0.01, min(0.35, float(sound_effect_volume)))
        audio_parts = [
            f"{audio_source}loudnorm=I={loudness_lufs}:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.12[main_audio]",
            f"[1:a:0]volume={volume:.3f},adelay={offset_ms}:all=1[sfx_audio]",
            "[main_audio][sfx_audio]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[a]",
        ]
        if duration and duration > 0.4:
            fade_start = max(0.12, duration - 0.18)
            audio_parts.append(f"[a]afade=t=out:st={fade_start:.3f}:d=0.18[aout]")
            audio_map = "[aout]"
        else:
            audio_map = "[a]"
        command.extend([
            "-filter_complex", filter_graph + ";" + ";".join(audio_parts),
            "-map", "[v]", "-map", audio_map, "-c:a", "aac", "-b:a", "192k",
        ])
    else:
        if has_audio and normalized_segments:
            audio_filter = f"{audio_source}loudnorm=I={loudness_lufs}:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.12"
            if duration and duration > 0.4:
                fade_start = max(0.12, duration - 0.18)
                audio_filter += f",afade=t=out:st={fade_start:.3f}:d=0.18"
            audio_filter += "[aout]"
            command.extend([
                "-filter_complex", filter_graph + ";" + audio_filter,
                "-map", "[v]", "-map", "[aout]", "-c:a", "aac", "-b:a", "192k",
            ])
        else:
            command.extend(["-filter_complex", filter_graph, "-map", "[v]"])
            if has_audio:
                audio_filter = f"loudnorm=I={loudness_lufs}:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.12"
                if duration and duration > 0.4:
                    fade_start = max(0.12, duration - 0.18)
                    audio_filter += f",afade=t=out:st={fade_start:.3f}:d=0.18"
                command.extend(["-map", "0:a:0?", "-af", audio_filter, "-c:a", "aac", "-b:a", "192k"])
            else:
                command.append("-an")
    command.extend(["-r", str(fps), "-c:v", encoder])
    if encoder == "h264_amf":
        command.extend(["-quality", "quality", "-rc", "vbr_peak", "-b:v", bitrate])
    else:
        command.extend(["-preset", "medium", "-crf", "19"])
    command.extend([
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output_path.resolve())
    ])
    return command


def render_vertical_short(
    input_path: Path,
    output_path: Path,
    thumbnail_path: Path,
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    preferred_encoder: str = "h264_amf",
    fallback_encoder: str = "libx264",
    max_duration: float = 60.0,
    bitrate: str = "12M",
    loudness_lufs: int = -14,
    width: int = 1080,
    height: int = 1920,
    layout: str = "blur",
    webcam_zone: str = "none",
    crop_x: int = 50,
    crop_y: int = 50,
    ass_file: Path | None = None,
    fonts_dir: Path | None = None,
    project_root: Path | None = None,
    dynamic_zoom: bool = False,
    peak_timestamp: float = 0.0,
    thumbnail_timestamp: float | None = None,
    zoom_percent: int = 0,
    trim_start: float = 0.0,
    trim_duration: float | None = None,
    sound_effect_path: Path | None = None,
    sound_effect_offset: float = 0.0,
    sound_effect_volume: float = 0.14,
    edit_segments: Sequence[tuple[float, float]] | None = None,
) -> dict[str, Any]:
    input_path = input_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    info = probe_media(input_path, ffprobe)
    trim_start = max(0.0, float(trim_start))
    source_window_duration = float(trim_duration) if trim_duration is not None else max(0.0, info["duration"] - trim_start)
    normalized_segments: list[tuple[float, float]] = []
    if edit_segments:
        previous_end = 0.0
        for raw_start, raw_end in edit_segments:
            start, end = float(raw_start), float(raw_end)
            if (
                not math.isfinite(start) or not math.isfinite(end)
                or start < 0 or end <= start
                or start < previous_end - 0.001
                or end > source_window_duration + 0.05
            ):
                raise MediaError("Le plan de montage contient des segments invalides ou hors de l'extrait.")
            normalized_segments.append((start, end))
            previous_end = end
        if len(normalized_segments) < 2:
            normalized_segments = []
    output_duration = (
        sum(end - start for start, end in normalized_segments)
        if normalized_segments else source_window_duration
    )
    if output_duration > max_duration:
        raise MediaError(
            f"L'extrait monté dure {output_duration:.1f} s. La limite actuelle est de {max_duration:.0f} s."
        )
    if (
        source_window_duration <= 0
        or output_duration <= 0
        or trim_start >= info["duration"]
        or trim_start + source_window_duration > info["duration"] + 0.25
    ):
        raise MediaError("Les bornes de coupe dépassent la durée de la vidéo source.")
    fps = 60 if info["fps"] >= 50 else 30
    ffmpeg_bin = resolve_executable(ffmpeg)
    encoders_result = run_command([ffmpeg_bin, "-hide_banner", "-encoders"], timeout=30)
    encoder_text = encoders_result.stdout + encoders_result.stderr
    encoders = [preferred_encoder, fallback_encoder]
    if preferred_encoder not in encoder_text:
        encoders = [fallback_encoder]
    last_error: Exception | None = None
    for encoder in encoders:
        if output_path.exists():
            output_path.unlink()
        command = build_render_command(
            ffmpeg_bin, input_path, output_path, width=width, height=height,
            bitrate=bitrate, loudness_lufs=loudness_lufs,
            has_audio=info["has_audio"], encoder=encoder, fps=fps,
            layout=layout, crop_x=crop_x, crop_y=crop_y, ass_file=ass_file,
            fonts_dir=fonts_dir, project_root=project_root,
            dynamic_zoom=dynamic_zoom, peak_timestamp=peak_timestamp,
            zoom_percent=zoom_percent, duration=output_duration,
            trim_start=trim_start,
            trim_duration=source_window_duration if trim_start > 0 or source_window_duration < info["duration"] or normalized_segments else None,
            sound_effect_path=sound_effect_path, sound_effect_offset=sound_effect_offset,
            sound_effect_volume=sound_effect_volume, edit_segments=normalized_segments,
        )
        try:
            run_command(command, timeout=max(300, int(info["duration"] * 30)), cwd=project_root)
            info["encoder_used"] = encoder
            break
        except MediaError as exc:
            last_error = exc
            logger.warning("L'encodeur %s a échoué : %s", encoder, exc)
    else:
        raise MediaError(f"Échec de l'encodage avec les encodeurs disponibles : {last_error}")

    rendered_info = probe_media(output_path, ffprobe)
    if rendered_info["width"] != width or rendered_info["height"] != height:
        raise MediaError(
            f"Le rendu n'est pas au format Short attendu : {rendered_info['width']}x{rendered_info['height']} au lieu de {width}x{height}."
        )
    # Sample the selected excerpt and avoid blank sky/transition frames for the cover.
    preferred_thumbnail_time = peak_timestamp if thumbnail_timestamp is None else thumbnail_timestamp
    selected_thumbnail_time: float | None = None
    try:
        selected_thumbnail_time = _extract_best_thumbnail(
            ffmpeg_bin, input_path, thumbnail_path, trim_start=trim_start,
            output_duration=output_duration, preferred_timestamp=preferred_thumbnail_time,
            edit_segments=normalized_segments,
        )
    except (MediaError, OSError):
        logger.exception("La sélection intelligente de miniature a échoué. Tentative sur le timestamp audio.")
        source_offset = _map_output_time_to_source(float(preferred_thumbnail_time), normalized_segments) if normalized_segments else float(preferred_thumbnail_time)
        seek = min(max(0.1, trim_start + source_offset), max(0.1, info["duration"] - 0.1))
        try:
            run_command([
                ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{seek:.3f}",
                "-i", str(input_path.resolve()), "-frames:v", "1", "-q:v", "2", str(thumbnail_path.resolve()),
            ], timeout=30)
            selected_thumbnail_time = max(0.0, float(preferred_thumbnail_time))
        except MediaError:
            logger.exception("La miniature n'a pas pu être générée. Le rendu vidéo reste disponible.")
    info.update({
        "source_duration": info["duration"],
        "duration": output_duration,
        "trim_start": trim_start,
        "trim_end": trim_start + source_window_duration,
        "source_window_duration": source_window_duration,
        "edit_segments": normalized_segments,
        "removed_duration": round(max(0.0, source_window_duration - output_duration), 3),
        "output_path": str(output_path.resolve()),
        "thumbnail_path": str(thumbnail_path.resolve()) if thumbnail_path.is_file() else None,
        "output_width": rendered_info["width"],
        "output_height": rendered_info["height"],
        "layout": layout,
        "fps_output": rendered_info["fps"],
        "peak_timestamp": float(peak_timestamp),
        "thumbnail_timestamp": (
            trim_start + (_map_output_time_to_source(selected_thumbnail_time, normalized_segments) if normalized_segments else selected_thumbnail_time)
        ) if selected_thumbnail_time is not None else None,
        "sound_effect_used": bool(sound_effect_path and Path(sound_effect_path).is_file() and info["has_audio"]),
    })
    return info


def _thumbnail_visual_score(image_path: Path) -> float:
    """Score image detail/contrast so a blank sky or transition cannot become the cover."""
    from PIL import Image, ImageFilter, ImageStat

    with Image.open(image_path) as opened:
        image = opened.convert("RGB")
    width, height = image.size
    if width < 16 or height < 16:
        return 0.0
    # Ignore Twitch borders and HUD edges; score the central gameplay area.
    crop = image.crop((int(width * 0.15), int(height * 0.10), int(width * 0.85), int(height * 0.90)))
    resampling = getattr(Image, "Resampling", Image).BILINEAR
    crop = crop.resize((192, 108), resampling)
    gray = crop.convert("L")
    stats = ImageStat.Stat(gray)
    entropy = gray.entropy() / 8.0
    contrast = min(1.0, stats.stddev[0] / 72.0)
    edge_mean = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0] / 255.0
    edge_score = min(1.0, edge_mean / 0.18)
    saturation = ImageStat.Stat(crop.convert("HSV").getchannel("S")).mean[0] / 255.0
    brightness = stats.mean[0] / 255.0
    exposure_penalty = max(0.0, 0.18 - brightness) * 0.9 + max(0.0, brightness - 0.91) * 0.7
    return 0.42 * entropy + 0.25 * contrast + 0.23 * edge_score + 0.10 * saturation - exposure_penalty


def _map_output_time_to_source(
    output_time: float, segments: Sequence[tuple[float, float]],
) -> float:
    remaining = max(0.0, float(output_time))
    for start, end in segments:
        length = end - start
        if remaining <= length:
            return round(start + remaining, 3)
        remaining -= length
    return round(segments[-1][1], 3) if segments else max(0.0, float(output_time))


def _extract_best_thumbnail(
    ffmpeg_bin: str, input_path: Path, thumbnail_path: Path, *,
    trim_start: float, output_duration: float, preferred_timestamp: float,
    edit_segments: Sequence[tuple[float, float]] | None = None,
) -> float:
    """Sample frames from the kept source segments and return output-local time."""
    duration = max(0.25, float(output_duration))
    preferred = max(0.0, min(float(preferred_timestamp or 0.0), duration - 0.1))
    interval = min(3.0, max(1.5, duration / 12.0))
    segments = list(edit_segments or [(0.0, duration)])
    with tempfile.TemporaryDirectory(prefix="gta-ranked-thumb-", dir=str(thumbnail_path.parent)) as temporary:
        temporary_dir = Path(temporary)
        scored: list[tuple[float, float, float]] = []
        output_offset = 0.0
        for segment_index, (segment_start, segment_end) in enumerate(segments):
            segment_duration = max(0.0, float(segment_end) - float(segment_start))
            if segment_duration < 0.3:
                output_offset += segment_duration
                continue
            base_offset = min(0.35, segment_duration * 0.05)
            remaining = max(0.2, segment_duration - base_offset)
            pattern = temporary_dir / f"segment-{segment_index}-candidate-%03d.jpg"
            sample_command = [
                ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{trim_start + segment_start + base_offset:.3f}", "-i", str(input_path.resolve()),
                "-t", f"{remaining:.3f}", "-vf", f"fps=1/{interval:.3f},scale=480:-2",
                "-q:v", "5", str(pattern),
            ]
            run_command(sample_command, timeout=60)
            candidates = sorted(temporary_dir.glob(f"segment-{segment_index}-candidate-*.jpg"))
            for index, candidate in enumerate(candidates):
                within_segment = min(segment_duration - 0.1, base_offset + index * interval)
                output_time = output_offset + within_segment
                source_time = trim_start + segment_start + within_segment
                visual = _thumbnail_visual_score(candidate)
                proximity = 0.12 * math.exp(-abs(output_time - preferred) / 8.0)
                scored.append((visual + proximity, output_time, source_time))
            output_offset += segment_duration

        if not scored:
            raise MediaError("FFmpeg n'a extrait aucune image candidate pour la miniature.")
        _, chosen_output_time, absolute_time = max(scored, key=lambda item: item[0])
        absolute_time = max(0.1, min(absolute_time, trim_start + max(0.1, segments[-1][1]) - 0.1))
        run_command([
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{absolute_time:.3f}",
            "-i", str(input_path.resolve()), "-frames:v", "1", "-q:v", "2", str(thumbnail_path.resolve()),
        ], timeout=30)
    return chosen_output_time
