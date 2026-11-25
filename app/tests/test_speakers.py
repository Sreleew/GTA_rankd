from __future__ import annotations

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
