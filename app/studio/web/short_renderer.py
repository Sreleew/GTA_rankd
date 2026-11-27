"""Rendu de Shorts verticaux avec FFmpeg, cadrage plein écran et finitions."""

from __future__ import annotations

import json
from functools import lru_cache
import logging
import math
import shutil
import struct
import wave
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

from studio.process import run_quiet

logger = logging.getLogger(__name__)


class MediaError(RuntimeError):
    """Erreur lisible pendant l'analyse ou le rendu vidéo."""



def create_hook_sound_effect(
    output_path: Path,
    style: str = "impact",
    *,
    sample_rate: int = 44100,
) -> Path:
    """Create a short, original hook cue without external audio assets or dependencies.

    The four cues are deliberately restrained and distinct: bass impact,
    two-note question ping, rising suspense sweep, and a sharp reaction snap.
    """
    if sample_rate < 8000:
        raise ValueError("La fréquence audio doit être d'au moins 8 kHz.")
    if style not in {"impact", "question", "suspense", "reaction"}:
        style = "impact"

    duration = 0.62 if style == "suspense" else 0.42
    total = int(sample_rate * duration)
    samples: list[int] = []
    for index in range(total):
        t = index / sample_rate
        if style == "impact":
            envelope = math.exp(-t * 12.0)
            value = (
                0.72 * math.sin(2 * math.pi * (54 - 18 * t) * t) * envelope
                + 0.18 * math.sin(2 * math.pi * 112 * t) * math.exp(-t * 22.0)
            )
        elif style == "question":
            first = math.exp(-max(0.0, t - 0.015) * 9.0) if t >= 0.015 else 0.0
            second = math.exp(-max(0.0, t - 0.17) * 11.0) if t >= 0.17 else 0.0
            value = 0.34 * first * math.sin(2 * math.pi * 660 * t)
            value += 0.25 * second * math.sin(2 * math.pi * 990 * t)
        elif style == "suspense":
            progress = min(1.0, t / duration)
            frequency = 105.0 + 520.0 * progress * progress
            phase = 2 * math.pi * (105.0 * t + (520.0 * t**3) / (3 * duration**2))
            envelope = 0.08 + 0.32 * progress
            value = envelope * math.sin(phase)
            value += 0.08 * math.sin(2 * math.pi * frequency * 1.51 * t)
        else:
            progress = min(1.0, t / 0.12)
            frequency = 210.0 - 125.0 * progress
            envelope = math.exp(-t * 17.0)
            value = 0.52 * math.sin(2 * math.pi * frequency * t) * envelope
            value += 0.16 * math.sin(2 * math.pi * 1450 * t) * math.exp(-t * 55.0)

        # A short fade prevents clicks at the beginning and end of each cue.
        attack = min(1.0, t / 0.008)
        release = min(1.0, max(0.0, (duration - t) / 0.025))
        samples.append(max(-32767, min(32767, int(value * attack * release * 24500))))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return output_path

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
    timeout: int | None = None,
) -> dict[str, Any]:
    # Scale the probe timeout to the actual media size. A fixed 60-second
    # timeout can reject valid Twitch downloads before the Short pipeline starts.
    if timeout is None:
        timeout = probe_timeout_for_file(input_path)
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


@lru_cache(maxsize=8)
def _available_encoder_listing(ffmpeg_bin: str) -> str:
    """Cache FFmpeg encoder capabilities for repeated Short renders in one session."""
    result = run_command([ffmpeg_bin, "-hide_banner", "-encoders"], timeout=30)
    return result.stdout + result.stderr


def build_filter_complex(
    width: int = 1080,
    height: int = 1920,
    blur: int = 28,
    *,
    layout: str = "blur",
    crop_x: int = 50,
    crop_y: int = 50,
    source_width: int = 1920,
    source_height: int = 1080,
    ass_file: Path | None = None,
    fonts_dir: Path | None = None,
    project_root: Path | None = None,
    dynamic_zoom: bool = False,
    peak_timestamp: float = 0.0,
    zoom_timestamps: Sequence[float] | None = None,
    fps: int = 30,
    zoom_percent: int = 0,
) -> str:
    """Build a vertical canvas while preserving the complete source frame."""
    if width <= 0 or height <= 0:
        raise ValueError("Les dimensions de sortie doivent être positives.")
    if layout not in {"fill", "blur", "smart"}:
        raise ValueError("Le layout doit être 'fill', 'blur' ou 'smart'.")

    crop_x = max(0, min(100, int(crop_x))) / 100
    crop_y = max(0, min(100, int(crop_y))) / 100
    if layout == "smart":
        # Editorial 9:16 composition: a large gameplay panel sits between
        # the hook and captions. Landscape sources are cropped to the panel
        # ratio; portrait sources stay intact and are centered over the blur.
        panel_height = max(1, int(height * 0.48))
        panel_y = int(height * 0.30)
        panel_ratio = width / panel_height
        source_ratio = max(0.01, float(source_width) / max(1, int(source_height)))
        base = (
            f"[0:v]split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur={blur}:10,setsar=1[bg];"
        )
        if source_ratio >= panel_ratio:
            base += (
                f"[fgsrc]scale=-2:{panel_height},"
                f"crop={width}:{panel_height}:(in_w-out_w)*{crop_x:.3f}:"
                f"(in_h-out_h)*{crop_y:.3f},setsar=1[panel];"
            )
        else:
            base += (
                f"[fgsrc]scale=-2:{panel_height},setsar=1[panel];"
            )
        # Editorial frame: a restrained hairline and amber edge marker make
        # the gameplay panel feel intentionally art-directed, not generic.
        frame_x = max(8, int(width * 0.035))
        frame_y = max(0, panel_y - max(2, int(height * 0.003)))
        frame_width = max(1, width - frame_x * 2)
        frame_height = panel_height + max(4, int(height * 0.006))
        accent_width = max(3, int(width * 0.006))
        accent_y = panel_y + max(4, int(panel_height * 0.025))
        accent_height = max(1, panel_height - max(8, int(panel_height * 0.05)))
        base += (
            f"[bg][panel]overlay=(W-w)/2:{panel_y},"
            f"drawbox=x={frame_x}:y={frame_y}:w={frame_width}:h={frame_height}:"
            "color=white@0.30:t=2,"
            f"drawbox=x={frame_x}:y={accent_y}:w={accent_width}:h={accent_height}:"
            "color=0xF6C445@0.96:t=fill,setsar=1[base]"
        )
    elif layout == "fill":
        base = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:(in_w-out_w)*{crop_x:.3f}:(in_h-out_h)*{crop_y:.3f},setsar=1[base]"
        )
    else:
        base = (
            f"[0:v]split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur={blur}:10,setsar=1[bg];"
            f"[fgsrc]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"setsar=1[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]"
        )

    graph = base + ";"
    if dynamic_zoom and zoom_percent > 0:
        moments = list(zoom_timestamps or [peak_timestamp])[:5]
        zoom = 1.0 + max(0, min(20, int(zoom_percent))) / 100
        expression = "1.0"
        for moment in reversed(moments):
            center = max(0.0, float(moment))
            start = max(0.0, center - 0.45)
            end = max(start + 0.25, center + 0.85)
            pulse = (
                f"1+({zoom - 1.0:.3f})*sin(PI*(in_time-{start:.3f})/"
                f"{max(0.25, end - start):.3f})"
            )
            expression = f"if(between(in_time,{start:.3f},{end:.3f}),{pulse},{expression})"
        graph += (
            f"[base]zoompan=z='{expression}':"
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
    source_width: int = 1920,
    source_height: int = 1080,
    ass_file: Path | None = None,
    fonts_dir: Path | None = None,
    project_root: Path | None = None,
    dynamic_zoom: bool = False,
    peak_timestamp: float = 0.0,
    zoom_timestamps: Sequence[float] | None = None,
    zoom_percent: int = 0,
    duration: float | None = None,
    trim_start: float = 0.0,
    trim_duration: float | None = None,
    sound_effect_path: Path | None = None,
    sound_effect_offset: float = 0.0,
    sound_effect_volume: float = 0.14,
) -> list[str]:
    filter_graph = build_filter_complex(
        width, height, layout=layout, crop_x=crop_x, crop_y=crop_y,
        source_width=source_width, source_height=source_height,
        ass_file=ass_file, fonts_dir=fonts_dir, project_root=project_root,
        dynamic_zoom=dynamic_zoom, peak_timestamp=peak_timestamp,
        zoom_timestamps=zoom_timestamps, fps=fps, zoom_percent=zoom_percent,
    )
    command = [resolve_executable(ffmpeg), "-hide_banner", "-y"]
    if trim_start > 0:
        command.extend(["-ss", f"{trim_start:.3f}"])
    command.extend(["-i", str(input_path.resolve())])
    sfx_file = Path(sound_effect_path).resolve() if sound_effect_path and Path(sound_effect_path).is_file() else None
    use_sfx = bool(has_audio and sfx_file)
    if use_sfx:
        command.extend(["-i", str(sfx_file)])
    if trim_duration is not None and trim_duration > 0:
        command.extend(["-t", f"{trim_duration:.3f}"])

    if use_sfx:
        offset_ms = max(0, int(max(0.0, float(sound_effect_offset)) * 1000))
        volume = max(0.01, min(0.35, float(sound_effect_volume)))
        audio_parts = [
            f"[0:a:0]loudnorm=I={loudness_lufs}:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.12[main_audio]",
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
    crop_x: int = 50,
    crop_y: int = 50,
    ass_file: Path | None = None,
    fonts_dir: Path | None = None,
    project_root: Path | None = None,
    dynamic_zoom: bool = False,
    peak_timestamp: float = 0.0,
    zoom_timestamps: Sequence[float] | None = None,
    thumbnail_timestamp: float | None = None,
    zoom_percent: int = 0,
    trim_start: float = 0.0,
    trim_duration: float | None = None,
    sound_effect_path: Path | None = None,
    sound_effect_offset: float = 0.0,
    sound_effect_volume: float = 0.14,
) -> dict[str, Any]:
    input_path = input_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    info = probe_media(input_path, ffprobe)
    trim_start = max(0.0, float(trim_start))
    output_duration = float(trim_duration) if trim_duration is not None else info["duration"]
    if output_duration > max_duration:
        raise MediaError(
            f"L'extrait dure {output_duration:.1f} s. La limite actuelle est de {max_duration:.0f} s."
        )
    if output_duration <= 0 or trim_start >= info["duration"] or trim_start + output_duration > info["duration"] + 0.25:
        raise MediaError("Les bornes de coupe dépassent la durée de la vidéo source.")
    fps = 60 if info["fps"] >= 50 else 30
    ffmpeg_bin = resolve_executable(ffmpeg)
    encoder_text = _available_encoder_listing(ffmpeg_bin)
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
            layout=layout, crop_x=crop_x, crop_y=crop_y,
            source_width=info["width"], source_height=info["height"], ass_file=ass_file,
            fonts_dir=fonts_dir, project_root=project_root,
            dynamic_zoom=dynamic_zoom, peak_timestamp=peak_timestamp,
            zoom_timestamps=zoom_timestamps, zoom_percent=zoom_percent, duration=output_duration,
            trim_start=trim_start, trim_duration=output_duration if trim_start > 0 or output_duration < info["duration"] else None,
            sound_effect_path=sound_effect_path, sound_effect_offset=sound_effect_offset,
            sound_effect_volume=sound_effect_volume,
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
        )
    except (MediaError, OSError):
        logger.exception("La sélection intelligente de miniature a échoué. Tentative sur le timestamp audio.")
        seek = min(max(0.1, trim_start + float(preferred_thumbnail_time)), max(0.1, info["duration"] - 0.1))
        try:
            run_command([
                ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{seek:.3f}",
                "-i", str(input_path.resolve()), "-frames:v", "1", "-q:v", "2", str(thumbnail_path.resolve()),
            ], timeout=30)
            selected_thumbnail_time = max(0.0, seek - trim_start)
        except MediaError:
            logger.exception("La miniature n'a pas pu être générée. Le rendu vidéo reste disponible.")
    info.update({
        "source_duration": info["duration"],
        "duration": output_duration,
        "trim_start": trim_start,
        "trim_end": trim_start + output_duration,
        "output_path": str(output_path.resolve()),
        "thumbnail_path": str(thumbnail_path.resolve()) if thumbnail_path.is_file() else None,
        "output_width": rendered_info["width"],
        "output_height": rendered_info["height"],
        "layout": layout,
        "fps_output": rendered_info["fps"],
        "peak_timestamp": float(peak_timestamp),
        "thumbnail_timestamp": (trim_start + selected_thumbnail_time) if selected_thumbnail_time is not None else None,
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


def _extract_best_thumbnail(
    ffmpeg_bin: str, input_path: Path, thumbnail_path: Path, *,
    trim_start: float, output_duration: float, preferred_timestamp: float,
) -> float:
    """Sample a few low-resolution frames, then extract only the best one at full resolution."""
    duration = max(0.25, float(output_duration))
    base_offset = min(0.35, duration * 0.05)
    remaining = max(0.2, duration - base_offset)
    interval = min(3.0, max(1.5, duration / 12.0))
    preferred = max(0.0, min(float(preferred_timestamp or 0.0), duration - 0.25))
    with tempfile.TemporaryDirectory(prefix="gta-ranked-thumb-", dir=str(thumbnail_path.parent)) as temporary:
        temporary_dir = Path(temporary)
        pattern = temporary_dir / "candidate-%03d.jpg"
        sample_command = [
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{trim_start + base_offset:.3f}", "-i", str(input_path.resolve()),
            "-t", f"{remaining:.3f}", "-vf", f"fps=1/{interval:.3f},scale=480:-2",
            "-q:v", "5", str(pattern),
        ]
        run_command(sample_command, timeout=60)
        candidates = sorted(temporary_dir.glob("candidate-*.jpg"))
        scored: list[tuple[float, float]] = []
        for index, candidate in enumerate(candidates):
            local_time = min(duration - 0.1, base_offset + index * interval)
            visual = _thumbnail_visual_score(candidate)
            proximity = 0.12 * math.exp(-abs(local_time - preferred) / 8.0)
            scored.append((visual + proximity, local_time))
        if not scored:
            raise MediaError("FFmpeg n'a extrait aucune image candidate pour la miniature.")
        _, chosen_local_time = max(scored, key=lambda item: item[0])
        absolute_time = max(0.1, min(trim_start + chosen_local_time, trim_start + duration - 0.1))
        run_command([
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{absolute_time:.3f}",
            "-i", str(input_path.resolve()), "-frames:v", "1", "-q:v", "2", str(thumbnail_path.resolve()),
        ], timeout=30)
    return chosen_local_time
