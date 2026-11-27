from __future__ import annotations

import array
import wave
from pathlib import Path

from studio.web.highlights import read_audio_energy, score_highlight_candidates, write_wav_chunk
from studio.web.short_editor import WordTiming
from studio.web.store import Store


def _write_test_wav(path: Path) -> None:
    rate = 16000
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        for second in range(20):
            amplitude = 26000 if 8 <= second < 12 else 2500
            frames = array.array("h", [amplitude] * rate)
            audio.writeframes(frames.tobytes())


def test_read_audio_energy_detects_loud_windows(tmp_path: Path) -> None:
    audio_path = tmp_path / "energy.wav"
    _write_test_wav(audio_path)
    windows = read_audio_energy(audio_path, window_seconds=1)
    assert len(windows) == 20
    assert max(item["rms"] for item in windows[8:12]) > 5 * max(item["rms"] for item in windows[:8])


def test_score_candidates_returns_only_high_quality_ranked_results() -> None:
    audio = [
        {"start": float(second), "end": float(second + 2), "rms": 0.03 if 40 <= second < 65 else 0.005}
        for second in range(0, 120, 2)
    ]
    cues = ["BRO", "WHAT", "NO", "WAIT", "OMG", "INSANE", "CRAZY", "HOLY", "SHIT", "FUCK", "DAMN", "BRUH", "WTF", "HELP", "YO", "NAH", "SICK", "CLUTCH"]
    words = [WordTiming(40.0 + index * 1.2, 40.4 + index * 1.2, cue) for index, cue in enumerate(cues)]
    candidates = score_highlight_candidates(120, audio, words, candidate_seconds=30, max_candidates=5)
    assert candidates
    assert len(candidates) <= 5
    assert all(item["score"] > 80 for item in candidates)
    assert [item["rank"] for item in candidates] == list(range(1, len(candidates) + 1))
    assert all(0 <= item["start_time"] < item["end_time"] <= 120 for item in candidates)
    assert all(item["end_time"] - item["start_time"] <= 30 for item in candidates)
    assert [item["score"] for item in candidates] == sorted((item["score"] for item in candidates), reverse=True)

def test_default_highlight_candidates_are_non_overlapping_and_use_supported_lengths() -> None:
    audio = [
        {"start": float(second), "end": float(second + 2),
         "rms": 0.06 if (40 <= second < 70 or 110 <= second < 140) else 0.005}
        for second in range(0, 180, 2)
    ]
    cues = ["BRO", "WHAT", "NO", "WAIT", "OMG", "INSANE", "CRAZY", "HOLY", "SHIT", "FUCK", "DAMN", "BRUH", "WTF", "HELP", "YO", "NAH", "SICK", "CLUTCH"]
    words = [
        WordTiming(start + 1.0 + index * 1.2, start + 1.3 + index * 1.2, cues[index])
        for start in (40.0, 110.0) for index in range(len(cues))
    ]
    candidates = score_highlight_candidates(180, audio, words)
    assert candidates
    assert all(item["score"] > 80 for item in candidates)
    assert all(round(item["end_time"] - item["start_time"]) in {60, 90, 120, 150, 165} for item in candidates)
    for index, first in enumerate(candidates):
        for second in candidates[index + 1:]:
            assert first["end_time"] + 6 <= second["start_time"] or second["end_time"] + 6 <= first["start_time"]

def test_audio_only_scans_can_return_high_energy_candidates_without_whisper() -> None:
    audio = [
        {"start": float(second), "end": float(second + 2),
         "rms": 0.04 if 40 <= second < 60 else 0.005}
        for second in range(0, 120, 2)
    ]

    candidates = score_highlight_candidates(120, audio, [], candidate_seconds=25, max_candidates=3)

    assert candidates
    assert all(candidate["score"] > 80 for candidate in candidates)
    assert all(candidate["transcript"] == "" for candidate in candidates)
    assert all(0.0 <= candidate["opening_score"] <= 1.0 for candidate in candidates)


def test_opening_activity_breaks_ties_in_favor_of_faster_hooks() -> None:
    early_audio = [
        {"start": float(second), "end": float(second + 2), "rms": 0.04 if second < 10 else 0.005}
        for second in range(0, 50, 2)
    ]
    late_audio = [
        {"start": float(second), "end": float(second + 2), "rms": 0.04 if 20 <= second < 30 else 0.005}
        for second in range(0, 50, 2)
    ]
    early_words = [WordTiming(0.05 + index * 0.09, 0.10 + index * 0.09, "NO") for index in range(50)]
    late_words = [WordTiming(20.05 + index * 0.09, 20.10 + index * 0.09, "NO") for index in range(50)]

    early = score_highlight_candidates(50, early_audio, early_words, candidate_seconds=50)[0]
    late = score_highlight_candidates(50, late_audio, late_words, candidate_seconds=50)[0]

    assert early["audio_score"] == late["audio_score"]
    assert early["speech_score"] == late["speech_score"]
    assert early["reaction_score"] == late["reaction_score"]
    assert early["opening_score"] > late["opening_score"] + 0.5
    assert early["score"] > late["score"]


def test_score_short_twitch_clip_below_threshold_is_not_proposed() -> None:
    candidates = score_highlight_candidates(
        24,
        [{"start": 0, "end": 2, "rms": 0.02}, {"start": 2, "end": 4, "rms": 0.04}],
        [WordTiming(2, 3, "NO"), WordTiming(3, 4, "BRO")],
        candidate_seconds=35,
    )
    assert candidates == []

def test_highlight_scans_and_candidates_are_persisted(tmp_path: Path) -> None:
    store = Store(tmp_path / "clips.sqlite")
    store.create_highlight_scan({
        "id": "scan-123", "source_kind": "upload", "source_path": "local-vod.mp4",
        "rights_confirmed": True, "window_start": 10.0, "window_end": 80.0,
    })
    store.update_highlight_scan("scan-123", status="completed", progress=100, message="Analyse terminée")
    store.save_highlight_candidates("scan-123", [{
        "rank": 1, "start_time": 25.0, "end_time": 60.0,
        "media_start": 25.0, "media_end": 60.0, "score": 82.5,
        "audio_score": 0.9, "speech_score": 0.7, "reaction_score": 1.0,
        "opening_score": 0.85, "payoff_score": 0.9,
        "reasons": ["Pic d'énergie audio", "Mots de réaction détectés", "Accroche immédiate"],
        "transcript": "BRO WHAT NO",
    }])
    scan = store.get_highlight_scan("scan-123")
    candidates = store.list_highlight_candidates("scan-123")
    assert scan and scan["status"] == "completed"
    assert scan["rights_confirmed"] is True
    assert len(candidates) == 1
    assert candidates[0]["score"] == 82.5
    assert candidates[0]["opening_score"] == 0.85
    assert candidates[0]["payoff_score"] == 0.9
    assert candidates[0]["reasons"] == ["Pic d'énergie audio", "Mots de réaction détectés", "Accroche immédiate"]


def test_payoff_scoring_rewards_a_rising_audio_peak_with_a_nearby_reaction() -> None:
    audio = [
        {"start": float(second), "end": float(second + 2),
         "rms": 0.045 if second == 20 else (0.006 if second < 20 else 0.008)}
        for second in range(0, 50, 2)
    ]
    words = [WordTiming(20.2, 20.6, "WHAT"), WordTiming(21.0, 21.4, "BRO")]

    candidates = score_highlight_candidates(50, audio, words, candidate_seconds=50)

    assert candidates
    assert candidates[0]["payoff_score"] >= 0.85
    assert "Montée en tension / payoff détecté" in candidates[0]["reasons"]


def test_write_wav_chunk_sets_the_actual_frame_count(tmp_path: Path) -> None:
    source_path = tmp_path / "source.wav"
    _write_test_wav(source_path)
    with wave.open(str(source_path), "rb") as source:
        params = source.getparams()
        chunk_path = tmp_path / "chunk.wav"
        write_wav_chunk(source, chunk_path, start_frame=5 * params.framerate, frame_count=3 * params.framerate, params=params)
    with wave.open(str(chunk_path), "rb") as chunk:
        assert chunk.getnframes() == 3 * params.framerate
        assert chunk.getnframes() / chunk.getframerate() == 3


def test_silent_audio_does_not_create_random_highlight_candidates() -> None:
    windows = [{"start": float(index * 2), "end": float(index * 2 + 2), "rms": 0.0} for index in range(30)]
    assert score_highlight_candidates(60, windows, []) == []


def test_highlight_candidates_are_unlimited_above_score_threshold() -> None:
    duration = 650
    event_starts = [10 + index * 70 for index in range(9)]
    audio = [
        {"start": float(second), "end": float(second + 2),
         "rms": 0.06 if any(start <= second < start + 30 for start in event_starts) else 0.005}
        for second in range(0, duration, 2)
    ]
    cues = ["BRO", "WHAT", "NO", "WAIT", "OMG", "INSANE", "CRAZY", "HOLY", "SHIT", "FUCK", "DAMN", "BRUH", "WTF", "HELP", "YO", "NAH", "SICK", "CLUTCH"]
    words = [
        WordTiming(start + 1.0 + index * 1.2, start + 1.3 + index * 1.2, cues[index])
        for start in event_starts for index in range(len(cues))
    ]
    candidates = score_highlight_candidates(duration, audio, words, candidate_seconds=30, max_candidates=None)
    assert len(candidates) >= 9
    assert all(item["score"] > 80 for item in candidates)
    assert [item["rank"] for item in candidates] == list(range(1, len(candidates) + 1))


def test_store_migrates_existing_highlight_candidates_table(tmp_path: Path) -> None:
    import sqlite3

    database_path = tmp_path / "legacy-clips.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """CREATE TABLE highlight_candidates (
                id TEXT PRIMARY KEY,
                scan_id TEXT NOT NULL,
                rank INTEGER NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                media_start REAL NOT NULL,
                media_end REAL NOT NULL,
                score REAL NOT NULL,
                audio_score REAL NOT NULL DEFAULT 0,
                speech_score REAL NOT NULL DEFAULT 0,
                reaction_score REAL NOT NULL DEFAULT 0,
                reasons_json TEXT NOT NULL DEFAULT '[]',
                transcript TEXT NOT NULL DEFAULT '',
                created_job_id TEXT,
                created_at TEXT NOT NULL
            )"""
        )

    store = Store(database_path)
    store.create_highlight_scan({
        "id": "legacy-scan", "source_kind": "upload", "source_path": "vod.mp4",
        "rights_confirmed": True,
    })
    store.save_highlight_candidates("legacy-scan", [{
        "rank": 1, "start_time": 0, "end_time": 25, "media_start": 0, "media_end": 25,
        "score": 91, "opening_score": 0.7, "payoff_score": 0.8,
    }])

    candidates = store.list_highlight_candidates("legacy-scan")
    assert candidates[0]["opening_score"] == 0.7
    assert candidates[0]["payoff_score"] == 0.8
