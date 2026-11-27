"""Test d'intégration réel du rendu, si FFmpeg/libx264 est disponible."""

from pathlib import Path
import shutil
import subprocess

import pytest

from studio.web.short_editor import WordTiming, create_ass_file
from studio.web.short_renderer import build_filter_complex, probe_media, render_vertical_short


def test_smart_layout_builds_large_gameplay_panel_and_respects_horizontal_focus() -> None:
    graph = build_filter_complex(
        width=1080, height=1920, layout="smart", crop_x=80,
        source_width=1920, source_height=1080,
    )
    assert "scale=-2:921" in graph
    assert "crop=1080:921:(in_w-out_w)*0.800" in graph
    assert "overlay=(W-w)/2:576" in graph
    assert "boxblur=28:10" in graph
    assert "drawbox=x=37:y=571:w=1006:h=932:color=white@0.30:t=2" in graph
    assert "drawbox=x=37:y=599:w=6:h=875:color=0xF6C445@0.96:t=fill" in graph


def test_smart_layout_preserves_portrait_sources_without_aggressive_crop() -> None:
    graph = build_filter_complex(
        width=1080, height=1920, layout="smart",
        source_width=1080, source_height=1920,
    )
    assert "scale=-2:921,setsar=1[panel]" in graph
    assert "crop=1080:921" not in graph


def test_thumbnail_visual_score_rejects_blank_sky_frame(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw
    from studio.web.short_renderer import _thumbnail_visual_score

    blank = tmp_path / "blank.jpg"
    detailed = tmp_path / "detailed.jpg"
    Image.new("RGB", (640, 360), (180, 190, 195)).save(blank)
    scene = Image.new("RGB", (640, 360), (65, 110, 75))
    draw = ImageDraw.Draw(scene)
    draw.rectangle((40, 150, 500, 320), fill=(220, 110, 35))
    draw.ellipse((250, 50, 370, 280), fill=(240, 215, 170))
    for x in range(0, 640, 30):
        draw.line((x, 0, x + 80, 360), fill=(30, 55, 35), width=3)
    scene.save(detailed)
    assert _thumbnail_visual_score(detailed) > _thumbnail_visual_score(blank) + 0.15


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="FFmpeg/FFprobe absent")
def test_real_vertical_short_render(tmp_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    assert ffmpeg and ffprobe

    encoder_result = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if encoder_result.returncode != 0 or "libx264" not in (encoder_result.stdout + encoder_result.stderr):
        pytest.skip("La build FFmpeg ne contient pas libx264")

    source = tmp_path / "synthetic-input.mp4"
    output = tmp_path / "rendered-short.mp4"
    thumbnail = tmp_path / "thumbnail.jpg"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=duration=2:size=320x180:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=60,
    )

    captions = tmp_path / "captions.ass"
    create_ass_file(
        captions,
        words=[WordTiming(0.15, 0.45, "BRO"), WordTiming(0.46, 0.85, "WHAT"), WordTiming(0.86, 1.20, "HAPPENED?")],
        hook_text="WAIT FOR IT",
        context_text="GTA VI MOMENT",
        handle="@GTARankedStudio",
        badge_text="GTA VI",
        width=360,
        height=640,
        captions_enabled=True,
        brand_enabled=True,
    )

    result = render_vertical_short(
        source,
        output,
        thumbnail,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        preferred_encoder="libx264",
        fallback_encoder="libx264",
        max_duration=60,
        width=360,
        height=640,
        ass_file=captions,
        project_root=tmp_path,
        layout="smart",
        crop_x=80,
        dynamic_zoom=False,
        peak_timestamp=0.9,
        zoom_percent=8,
        trim_start=0.25,
        trim_duration=1.5,
        sound_effect_path=Path(__file__).resolve().parents[1] / "assets" / "sfx" / "soft_whoosh.wav",
        sound_effect_offset=0.55,
    )

    rendered = probe_media(output, ffprobe)
    assert result["encoder_used"] == "libx264"
    assert result["sound_effect_used"] is True
    assert result["layout"] == "smart"
    assert result["source_duration"] == pytest.approx(2.0, abs=0.15)
    assert result["duration"] == pytest.approx(1.5, abs=0.01)
    assert result["trim_start"] == pytest.approx(0.25)
    assert rendered["width"] == 360
    assert rendered["height"] == 640
    assert rendered["has_audio"] is True
    assert output.is_file() and output.stat().st_size > 10_000
    assert thumbnail.is_file() and thumbnail.stat().st_size > 1_000
