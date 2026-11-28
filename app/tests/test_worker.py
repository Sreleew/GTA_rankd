from pathlib import Path

from studio.web import worker


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
    assert result["audio_path"] == str(existing_audio)
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


def test_short_transcription_slices_existing_analysis_wav_for_selected_excerpt(tmp_path: Path, monkeypatch):
    from studio.config import AppConfig

    config = AppConfig(
        data={
            "executables": {"ffmpeg": "ffmpeg", "whisper_cli": "tools/whisper-cli"},
            "transcription": {"model_path": "models/whisper.bin", "language": "en"},
        },
        path=tmp_path / "config.yaml",
    )
    analysis_audio = tmp_path / "audio-16k.wav"
    analysis_audio.write_bytes(b"wav")
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

    result = worker._transcribe_short_excerpt(
        tmp_path / "source.mp4", tmp_path / "temp", config,
        trim_start=35.0, trim_end=95.0,
        existing_audio_path=analysis_audio,
        existing_audio_start=0.0,
        existing_audio_duration=180.0,
    )

    assert calls[0][0] == analysis_audio
    assert calls[0][2]["start_seconds"] == 35.0
    assert calls[0][2]["duration_seconds"] == 60.0
    assert result["audio_path"] == str(tmp_path / "temp" / "short-captions-16k.wav")


def test_short_excerpt_duration_is_rejected_before_expensive_transcription():
    import pytest

    with pytest.raises(worker.MediaError, match="Active le recadrage automatique"):
        worker._validate_short_excerpt_duration(900.0, 165.0)

    assert worker._validate_short_excerpt_duration(165.0, 165.0) == 165.0

    with pytest.raises(worker.MediaError, match="supérieure à zéro"):
        worker._validate_short_excerpt_duration(0.0, 165.0)


def test_requested_short_captions_stay_enabled_for_the_final_overlay():
    words = [object(), object()]

    assert worker._captions_should_render(True, words) is True
    assert worker._captions_should_render(False, words) is False
    assert worker._captions_should_render(True, []) is False


def test_short_transcription_can_run_for_hook_without_burning_captions():
    words = [object(), object()]

    assert worker._short_transcription_requested(False, True) is True
    assert worker._short_transcription_requested(True, False) is True
    assert worker._short_transcription_requested(False, False) is False
    assert worker._captions_should_render(False, words) is False


def test_caption_voice_filter_keeps_only_words_returned_by_the_diarizer(tmp_path: Path, monkeypatch):
    from studio.web.short_editor import WordTiming

    audio = tmp_path / "short.wav"
    audio.write_bytes(b"wav")
    words = [WordTiming(0.1, 0.4, "STREAMER"), WordTiming(1.0, 1.3, "GAME")]
    calls = []

    def fake_filter(path, received_words):
        calls.append((path, received_words))
        return [received_words[0]], {
            "status": "dominant_filtered",
            "selected_speaker": "SPEAKER_00",
            "dominant_share": 0.78,
        }

    monkeypatch.setattr(worker, "diarize_and_filter", fake_filter)
    filtered, report = worker._filter_caption_words(audio, words)

    assert [word.text for word in filtered] == ["STREAMER"]
    assert calls == [(audio, words)]
    assert report["mode"] == "dominant"
    assert report["words_before"] == 2
    assert report["words_after"] == 1


def test_caption_voice_filter_fails_closed_when_diarization_is_unavailable(tmp_path: Path, monkeypatch):
    from studio.web.speakers import SpeakerFilterError
    from studio.web.short_editor import WordTiming

    audio = tmp_path / "short.wav"
    audio.write_bytes(b"wav")
    words = [WordTiming(0.1, 0.4, "STREAMER")]

    def unavailable(*args, **kwargs):
        raise SpeakerFilterError("Moteur de voix indisponible")

    monkeypatch.setattr(worker, "diarize_and_filter", unavailable)
    filtered, report = worker._filter_caption_words(audio, words)

    assert filtered == []
    assert report["status"] == "diarization_unavailable"
    assert report["words_after"] == 0
    assert "indisponible" in report["reason"]


def test_caption_voice_filter_skips_diarization_when_transcript_is_empty(monkeypatch):
    called = []
    monkeypatch.setattr(worker, "diarize_and_filter", lambda *args, **kwargs: called.append(True))
    filtered, report = worker._filter_caption_words(None, [])

    assert filtered == []
    assert report["status"] == "no_words"
    assert called == []



def test_hook_sound_requires_a_visible_hook_and_user_opt_in():
    assert worker._hook_sound_should_render(True, "WAIT, WHAT JUST HAPPENED?")
    assert worker._hook_sound_should_render(True, "  NO WAY!  ")
    assert not worker._hook_sound_should_render(True, "")
    assert not worker._hook_sound_should_render(True, "   ")
    assert not worker._hook_sound_should_render(False, "WAIT, WHAT JUST HAPPENED?")
