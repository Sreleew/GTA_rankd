from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from studio.web import export_quality
from studio.web.short_editor import WordTiming
from studio.web.short_renderer import MediaError


def test_parse_ffmpeg_diagnostics_extracts_black_freeze_and_silence() -> None:
    log = """
    [blackdetect] black_start:2.000 black_end:4.000 black_duration:2.000
    [freezedetect] freeze_start: 6.000
    [freezedetect] freeze_duration: 3.500
    [silencedetect] silence_start: 8.000
    [silencedetect] silence_end: 12.500 | silence_duration: 4.500
    """
    result = export_quality.parse_ffmpeg_diagnostics(log, 15.0)
    assert result["black"] == [{"start": 2.0, "end": 4.0, "duration": 2.0}]
    assert result["freeze"][0]["start"] == 6.0
    assert result["freeze"][0]["duration"] == 3.5
    assert result["silence"][0]["start"] == 8.0
    assert result["silence"][0]["duration"] == 4.5


def _mock_clean_media(monkeypatch: pytest.MonkeyPatch, stderr: str = "") -> None:
    info = {
        "duration": 15.0,
        "width": 1080,
        "height": 1920,
        "has_audio": True,
        "fps": 30.0,
        "video_codec": "h264",
        "audio_codec": "aac",
    }
    monkeypatch.setattr(export_quality, "resolve_executable", lambda _: "ffmpeg")
    monkeypatch.setattr(export_quality, "probe_media", lambda *args, **kwargs: info)
    monkeypatch.setattr(
        export_quality,
        "run_command",
        lambda args, timeout=None: subprocess.CompletedProcess(args, 0, "", stderr),
    )


def test_analyze_export_quality_marks_clean_export_as_passed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "short.mp4"
    output.write_bytes(b"x" * 20_000)
    ass = tmp_path / "captions.ass"
    ass.write_text(
        "[Events]\n"
        "Dialogue: 0,0:00:01.00,0:00:01.50,Caption,,0,0,0,,HELLO WORLD\n",
        encoding="utf-8",
    )
    _mock_clean_media(monkeypatch)

    report = export_quality.analyze_export_quality(
        output,
        expected_duration=15.0,
        expected_width=1080,
        expected_height=1920,
        expect_audio=True,
        ass_file=ass,
        caption_words=[WordTiming(1.0, 1.5, "hello")],
        caption_expected=True,
    )

    assert report["status"] == "passed"
    assert report["warnings"] == []
    assert report["metrics"]["caption_events"] == 1
    assert report["metrics"]["caption_word_timings_invalid"] == 0


def test_analyze_export_quality_flags_detected_media_defects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "short.mp4"
    output.write_bytes(b"x" * 20_000)
    _mock_clean_media(
        monkeypatch,
        "black_start:2.000 black_end:4.000 black_duration:2.000\n"
        "freeze_start: 6.000\nfreeze_duration: 3.500\n"
        "silence_start: 8.000\nsilence_end: 12.500 | silence_duration: 4.500\n",
    )

    report = export_quality.analyze_export_quality(output, expected_duration=15.0)
    assert report["status"] == "review"
    assert len(report["warnings"]) == 3
    assert report["metrics"]["black_segments"][0]["duration"] == 2.0


def test_analyze_export_quality_flags_caption_events_past_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "short.mp4"
    output.write_bytes(b"x" * 20_000)
    ass = tmp_path / "captions.ass"
    ass.write_text(
        "[Events]\n"
        "Dialogue: 0,0:00:14.80,0:00:15.50,Caption,,0,0,0,,TOO LATE\n",
        encoding="utf-8",
    )
    _mock_clean_media(monkeypatch)

    report = export_quality.analyze_export_quality(
        output, ass_file=ass, caption_expected=True, caption_words=[WordTiming(14.8, 15.5, "late")]
    )
    assert report["status"] == "review"
    assert report["metrics"]["caption_events_out_of_range"] == 1
    assert report["metrics"]["caption_word_timings_invalid"] == 1


def test_analyze_export_quality_returns_partial_when_signal_scan_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "short.mp4"
    output.write_bytes(b"x" * 20_000)
    info = {
        "duration": 15.0, "width": 1080, "height": 1920, "has_audio": False,
        "fps": 30.0, "video_codec": "h264", "audio_codec": None,
    }
    monkeypatch.setattr(export_quality, "resolve_executable", lambda _: "ffmpeg")
    monkeypatch.setattr(export_quality, "probe_media", lambda *args, **kwargs: info)
    monkeypatch.setattr(export_quality, "run_command", lambda *args, **kwargs: (_ for _ in ()).throw(MediaError("filter unavailable")))

    report = export_quality.analyze_export_quality(output, expect_audio=False)
    assert report["status"] == "partial"
    assert any(item["key"] == "signal_scan" and item["status"] == "partial" for item in report["checks"])


def test_analyze_export_quality_reports_missing_audio_without_crashing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "short.mp4"
    output.write_bytes(b"x" * 20_000)
    info = {
        "duration": 15.0, "width": 1080, "height": 1920, "has_audio": False,
        "fps": 30.0, "video_codec": "h264", "audio_codec": None,
    }
    monkeypatch.setattr(export_quality, "resolve_executable", lambda _: "ffmpeg")
    monkeypatch.setattr(export_quality, "probe_media", lambda *args, **kwargs: info)
    monkeypatch.setattr(export_quality, "run_command", lambda args, timeout=None: subprocess.CompletedProcess(args, 0, "", ""))

    report = export_quality.analyze_export_quality(output, expect_audio=True)
    assert report["status"] == "review"
    assert any("n'en contient pas" in warning for warning in report["warnings"])


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg/FFprobe absent")
def test_real_ffmpeg_analysis_detects_inserted_black_segment(tmp_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    assert ffmpeg and ffprobe
    output = tmp_path / "synthetic-black-segment.mp4"
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=30:duration=3",
        "-f", "lavfi", "-i", "color=c=black:s=320x568:r=30:d=2",
        "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=30:duration=3",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0,format=yuv420p[v]",
        "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "ultrafast", str(output),
    ]
    subprocess.run(command, capture_output=True, check=True, timeout=60)

    report = export_quality.analyze_export_quality(
        output,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        expected_duration=8.0,
        expected_width=320,
        expected_height=568,
        expect_audio=False,
    )

    assert report["status"] == "review"
    assert len(report["metrics"]["black_segments"]) == 1
    assert report["metrics"]["black_segments"][0]["duration"] == pytest.approx(2.0, abs=0.15)


def test_analyze_export_quality_reuses_preprobed_media_info(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "short.mp4"
    output.write_bytes(b"x" * 20_000)
    info = {
        "duration": 15.0, "width": 1080, "height": 1920, "has_audio": True,
        "fps": 30.0, "video_codec": "h264", "audio_codec": "aac",
    }
    _mock_clean_media(monkeypatch)
    monkeypatch.setattr(
        export_quality, "probe_media",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("redundant FFprobe call")),
    )
    report = export_quality.analyze_export_quality(output, preprobed_info=info, expected_duration=15.0)
    assert report["status"] == "passed"
    assert report["metrics"]["width"] == 1080
