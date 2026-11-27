"""Test d'intégration réel du rendu, si FFmpeg/libx264 est disponible."""

from pathlib import Path
import shutil
import subprocess

import pytest

from studio.web.short_editor import WordTiming, create_ass_file
from studio.web.short_renderer import MediaError, build_filter_complex, create_hook_sound_effect, probe_media, render_vertical_short


def test_smart_layout_fits_the_complete_source_inside_the_editorial_panel() -> None:
    graph = build_filter_complex(
        width=1080, height=1920, layout="smart", crop_x=80,
        source_width=1920, source_height=1080,
    )
    assert "[0:v]split=3[bgsrc][panelbgsrc][fgsrc]" in graph
    assert "scale=1080:921:force_original_aspect_ratio=decrease" in graph
    assert "[panelbg][panelfg]overlay=(W-w)/2:(H-h)/2" in graph
    assert "crop=1080:921:(in_w-out_w)*0.800" not in graph
    assert "overlay=(W-w)/2:576" in graph
    assert graph.count("boxblur=28:10") == 2
    assert "drawbox=x=37:y=571:w=1006:h=932:color=white@0.30:t=2" in graph
    assert "drawbox=x=37:y=599:w=6:h=875:color=0xF6C445@0.96:t=fill" in graph


def test_smart_layout_fits_portrait_sources_inside_the_same_editorial_panel() -> None:
    graph = build_filter_complex(
        width=1080, height=1920, layout="smart",
        source_width=1080, source_height=1920,
    )
    assert "scale=1080:921:force_original_aspect_ratio=decrease" in graph
    assert "[panelbg][panelfg]overlay=(W-w)/2:(H-h)/2" in graph
    assert "crop=1080:921:(in_w-out_w)*" not in graph


def test_dynamic_zoom_uses_multiple_audio_moments_when_available() -> None:
    graph = build_filter_complex(
        width=1080, height=1920, layout="smart",
        dynamic_zoom=True, peak_timestamp=2.0,
        zoom_timestamps=[2.0, 8.0], zoom_percent=8,
    )
    assert "between(in_time,1.550,2.850)" in graph
    assert "between(in_time,7.550,8.850)" in graph
    assert graph.count("sin(PI*(in_time-") == 2


def test_dynamic_zoom_falls_back_to_the_primary_peak() -> None:
    graph = build_filter_complex(
        width=1080, height=1920, layout="smart",
        dynamic_zoom=True, peak_timestamp=3.0, zoom_percent=8,
    )
    assert "between(in_time,2.550,3.850)" in graph



@pytest.mark.parametrize("style", ["impact", "question", "suspense", "reaction"])
def test_hook_sound_effects_are_valid_and_distinct(tmp_path: Path, style: str) -> None:
    import wave

    output = create_hook_sound_effect(tmp_path / f"{style}.wav", style)
    with wave.open(str(output), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 44100
        assert audio.getnframes() >= 15000
        frames = audio.readframes(audio.getnframes())
        assert any(frames)


def test_unknown_hook_sound_style_falls_back_to_impact(tmp_path: Path) -> None:
    expected = create_hook_sound_effect(tmp_path / "impact.wav", "impact")
    fallback = create_hook_sound_effect(tmp_path / "fallback.wav", "unexpected")
    assert expected.read_bytes() == fallback.read_bytes()


def test_each_hook_style_has_a_distinct_sound_signature(tmp_path: Path) -> None:
    styles = ("impact", "question", "suspense", "reaction")
    signatures = {
        create_hook_sound_effect(tmp_path / f"{style}.wav", style).read_bytes()
        for style in styles
    }
    assert len(signatures) == len(styles)


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

    hook_sound = create_hook_sound_effect(tmp_path / "hook-sound.wav", "suspense")
    progress_updates: list[float] = []
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
        dynamic_zoom=True,
        peak_timestamp=0.9,
        zoom_timestamps=[0.35, 1.1],
        zoom_percent=8,
        trim_start=0.25,
        trim_duration=1.5,
        sound_effect_path=hook_sound,
        sound_effect_offset=0.12,
        progress_callback=progress_updates.append,
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
    assert progress_updates
    assert all(0.0 <= value <= 100.0 for value in progress_updates)
    assert progress_updates == sorted(progress_updates)
    assert max(progress_updates) >= 95.0
    assert output.is_file() and output.stat().st_size > 10_000
    assert thumbnail.is_file() and thumbnail.stat().st_size > 1_000


def test_short_render_fallback_restarts_progress_for_cpu_encoder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from studio.web import short_renderer

    source = tmp_path / "source.mp4"
    output = tmp_path / "short.mp4"
    thumbnail = tmp_path / "thumbnail.jpg"
    source.write_bytes(b"source")
    source_info = {
        "duration": 12.0, "width": 1920, "height": 1080, "has_audio": True,
        "fps": 30.0, "video_codec": "h264", "audio_codec": "aac",
    }
    output_info = {
        "duration": 8.0, "width": 360, "height": 640, "has_audio": True,
        "fps": 30.0, "video_codec": "h264", "audio_codec": "aac",
    }
    progress: list[float] = []
    attempts = []

    monkeypatch.setattr(short_renderer, "probe_media", lambda *args, **kwargs: output_info)
    monkeypatch.setattr(short_renderer, "_available_encoder_listing", lambda _: "h264_amf libx264")
    monkeypatch.setattr(short_renderer, "build_render_command", lambda *args, **kwargs: ["ffmpeg", str(output)])

    def fake_run(command, timeout=None, cwd=None, progress_callback=None):
        attempts.append(command)
        if progress_callback is not None:
            progress_callback(4.0 if len(attempts) == 1 else 2.0)
        if len(attempts) == 1:
            raise MediaError("Simulated AMF failure")
        output.write_bytes(b"rendered mp4")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(short_renderer, "run_command", fake_run)

    def fake_thumbnail(*args, **kwargs):
        thumbnail.write_bytes(b"jpeg")
        return 2.0

    monkeypatch.setattr(short_renderer, "_extract_best_thumbnail", fake_thumbnail)
    result = render_vertical_short(
        source, output, thumbnail,
        source_media_info=source_info,
        preferred_encoder="h264_amf",
        fallback_encoder="libx264",
        width=360, height=640,
        trim_start=1.0, trim_duration=8.0,
        progress_callback=progress.append,
    )

    assert result["encoder_used"] == "libx264"
    assert len(attempts) == 2
    assert progress == [0.0, 50.0, 0.0, 25.0]


def test_render_reuses_source_probe_and_returns_output_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from studio.web import short_renderer

    source = tmp_path / "source.mp4"
    output = tmp_path / "short.mp4"
    thumbnail = tmp_path / "thumbnail.jpg"
    source.write_bytes(b"source")
    source_info = {
        "duration": 12.0, "width": 1920, "height": 1080, "has_audio": True,
        "fps": 30.0, "video_codec": "h264", "audio_codec": "aac",
    }
    output_info = {
        "duration": 8.0, "width": 360, "height": 640, "has_audio": True,
        "fps": 30.0, "video_codec": "h264", "audio_codec": "aac",
    }
    probed: list[Path] = []

    def fake_probe(path, ffprobe="ffprobe", **kwargs):
        probed.append(Path(path))
        return output_info

    reported_progress = []

    def report_progress(value: float) -> None:
        if value == 0.0:
            raise RuntimeError("UI callback unavailable")
        reported_progress.append(value)

    def fake_run(command, timeout=None, cwd=None, progress_callback=None):
        output.write_bytes(b"rendered mp4")
        if progress_callback is not None:
            assert command[command.index("-progress") + 1] == "pipe:1"
            progress_callback(4.0)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(short_renderer, "probe_media", fake_probe)
    monkeypatch.setattr(short_renderer, "_available_encoder_listing", lambda _: "libx264")
    monkeypatch.setattr(short_renderer, "build_render_command", lambda *args, **kwargs: ["ffmpeg", str(output)])
    monkeypatch.setattr(short_renderer, "run_command", fake_run)

    def fake_thumbnail(*args, **kwargs):
        thumbnail.write_bytes(b"jpeg")
        return 2.0

    monkeypatch.setattr(short_renderer, "_extract_best_thumbnail", fake_thumbnail)
    result = short_renderer.render_vertical_short(
        source, output, thumbnail,
        source_media_info=source_info,
        preferred_encoder="libx264",
        fallback_encoder="libx264",
        width=360,
        height=640,
        trim_start=1.0,
        trim_duration=8.0,
        progress_callback=report_progress,
    )

    assert reported_progress == [50.0]
    assert probed == [output]
    assert result["source_duration"] == 12.0
    assert result["output_media_info"] == output_info
    assert set(result["performance_timings_ms"]) == {"encode_ms", "output_probe_ms", "thumbnail_ms", "total_ms"}
    assert all(value >= 0 for value in result["performance_timings_ms"].values())


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="FFmpeg/FFprobe absent")
def test_smart_layout_keeps_both_edges_of_a_twitch_frame_visible(tmp_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    assert ffmpeg and ffprobe
    source = tmp_path / "source-with-webcam-at-edge.mp4"
    output = tmp_path / "full-frame-short.mp4"
    thumbnail = tmp_path / "full-frame-thumbnail.jpg"

    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=red:s=640x360:r=30:d=1",
            "-vf",
            "drawbox=x=0:y=0:w=80:h=360:color=green:t=fill,"
            "drawbox=x=560:y=0:w=80:h=360:color=blue:t=fill",
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=True, timeout=60,
    )

    render_vertical_short(
        source, output, thumbnail,
        ffmpeg=ffmpeg, ffprobe=ffprobe,
        preferred_encoder="libx264", fallback_encoder="libx264",
        width=360, height=640, layout="smart", dynamic_zoom=False,
    )

    frame = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", "0.5",
            "-i", str(output), "-frames:v", "1", "-f", "rawvideo",
            "-pix_fmt", "rgb24", "-",
        ],
        capture_output=True, check=True, timeout=60,
    ).stdout
    assert len(frame) == 360 * 640 * 3

    def pixel(x: int, y: int) -> tuple[int, int, int]:
        offset = (y * 360 + x) * 3
        return tuple(frame[offset:offset + 3])

    # The full 16:9 source is fitted into the center panel, so edge content
    # (where Twitch webcams are often placed) must survive the vertical render.
    left_edge = pixel(20, 345)
    right_edge = pixel(340, 345)
    assert left_edge[1] > left_edge[0] * 1.4 and left_edge[1] > left_edge[2] * 1.4
    assert right_edge[2] > right_edge[0] * 1.4 and right_edge[2] > right_edge[1] * 1.4
