from pathlib import Path

from studio.web import worker


def test_thumbnail_overlay_failure_keeps_the_short_usable(tmp_path: Path, monkeypatch):
    thumbnail = tmp_path / "thumbnail.jpg"
    thumbnail.write_bytes(b"original frame")

    def fail_overlay(*args, **kwargs):
        raise OSError("font unavailable")

    monkeypatch.setattr(worker, "apply_thumbnail_overlay", fail_overlay)

    status, warning = worker._apply_thumbnail_overlay_safely(
        thumbnail,
        "GTA MOMENT",
        streamer="ExampleStreamer",
    )

    assert status == "fallback"
    assert warning == "font unavailable"
    assert thumbnail.read_bytes() == b"original frame"


def test_thumbnail_overlay_success_is_reported(tmp_path: Path, monkeypatch):
    thumbnail = tmp_path / "thumbnail.jpg"
    thumbnail.write_bytes(b"original frame")
    calls = []

    def apply_overlay(path, text, **kwargs):
        calls.append((path, text, kwargs))

    monkeypatch.setattr(worker, "apply_thumbnail_overlay", apply_overlay)

    status, warning = worker._apply_thumbnail_overlay_safely(
        thumbnail,
        "GTA MOMENT",
        streamer="ExampleStreamer",
    )

    assert status == "applied"
    assert warning is None
    assert calls == [(thumbnail, "GTA MOMENT", {"font_path": None, "streamer": "ExampleStreamer", "game_label": "GTA"})]


def test_short_transcription_reuses_audio_analysis_wav_for_exact_excerpt(tmp_path: Path, monkeypatch):
    from studio.config import AppConfig

    config = AppConfig(
        data={
            "executables": {"ffmpeg": "ffmpeg", "whisper_cli": "tools/whisper-cli"},
            "transcription": {
                "model_path": "models/whisper.bin", "language": "en", "threads": 4,
                "vad_model_path": "models/vad.bin", "short_timeout_seconds": 900,
            },
        },
        path=tmp_path / "config.yaml",
    )
    existing_audio = tmp_path / "audio-16k.wav"
    existing_audio.write_bytes(b"wav")
    calls = []
    monkeypatch.setattr(worker, "extract_audio_wav", lambda *args, **kwargs: calls.append(("extract", args, kwargs)))
    monkeypatch.setattr(
        worker,
        "transcribe_with_whisper_cpp",
        lambda audio, **kwargs: calls.append(("transcribe", audio, kwargs)) or {"status": "completed", "words": []},
    )

    result = worker._transcribe_short_excerpt(
        tmp_path / "source.mp4", tmp_path / "temp", config,
        trim_start=12.0, trim_end=72.0,
        existing_audio_path=existing_audio, existing_audio_start=12.0, existing_audio_duration=60.0,
    )

    assert result["status"] == "completed"
    assert len(calls) == 1
    assert calls[0][0] == "transcribe"
    assert calls[0][1] == existing_audio
    assert calls[0][2]["language"] == "en"
    assert calls[0][2]["threads"] == 4
    assert calls[0][2]["timeout"] == 900


def test_short_transcription_extracts_only_selected_excerpt_when_audio_differs(tmp_path: Path, monkeypatch):
    from studio.config import AppConfig

    config = AppConfig(
        data={
            "executables": {"ffmpeg": "ffmpeg", "whisper_cli": "tools/whisper-cli"},
            "transcription": {"model_path": "models/whisper.bin", "language": "en"},
        },
        path=tmp_path / "config.yaml",
    )
    calls = []
    monkeypatch.setattr(
        worker,
        "extract_audio_wav",
        lambda source, output, **kwargs: calls.append((source, output, kwargs)) or output,
    )
    monkeypatch.setattr(
        worker,
        "transcribe_with_whisper_cpp",
        lambda audio, **kwargs: {"status": "completed", "words": []},
    )

    worker._transcribe_short_excerpt(
        tmp_path / "source.mp4", tmp_path / "temp", config,
        trim_start=35.0, trim_end=95.0,
        existing_audio_path=tmp_path / "full-source.wav",
        existing_audio_start=0.0, existing_audio_duration=180.0,
    )

    assert len(calls) == 1
    assert calls[0][0] == tmp_path / "source.mp4"
    assert calls[0][1] == tmp_path / "temp" / "short-captions-16k.wav"
    assert calls[0][2]["start_seconds"] == 35.0
    assert calls[0][2]["duration_seconds"] == 60.0
