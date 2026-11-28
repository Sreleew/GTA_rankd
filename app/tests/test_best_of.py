from pathlib import Path

import pytest

from studio.web.best_of import build_best_of_plan


def _clip(tmp_path: Path, clip_id: str, duration: float = 155.0, *, date_key: str = "2026-11-27", status: str = "validated"):
    output = tmp_path / f"{clip_id}.mp4"
    output.write_bytes(b"rendered short")
    return {
        "id": clip_id,
        "job_id": clip_id,
        "status": status,
        "date_key": date_key,
        "duration": duration,
        "output_path": str(output),
        "thumbnail_path": "",
        "source_title": f"Moment {clip_id}",
        "streamer": "Streamer",
    }


def test_best_of_plan_preserves_user_order_and_targets_ten_to_eleven_minutes(tmp_path: Path):
    clips = [_clip(tmp_path, f"clip-{index}") for index in range(5)]
    plan = build_best_of_plan(clips, ["clip-3", "clip-1", "clip-4", "clip-0"], date_key="2026-11-27")

    assert [clip["id"] for clip in plan["clips"]] == ["clip-3", "clip-1", "clip-4", "clip-0"]
    assert plan["clip_count"] == 4
    assert plan["total_duration"] == 620.0
    assert plan["formatted_duration"] == "10:20"
    assert plan["ready_for_render"] is True
    assert plan["remaining_to_minimum"] == 0


def test_best_of_plan_reports_selection_that_is_too_short_or_too_long(tmp_path: Path):
    clips = [_clip(tmp_path, "short", 120), _clip(tmp_path, "long", 700)]
    too_short = build_best_of_plan(clips, ["short"])
    too_long = build_best_of_plan(clips, ["long"])

    assert too_short["ready_for_render"] is False
    assert too_short["remaining_to_minimum"] == 480
    assert too_long["ready_for_render"] is False
    assert too_long["over_maximum"] == 40


@pytest.mark.parametrize(
    ("clips", "ids", "date_key", "message"),
    [
        ([], [], None, "au moins un Short"),
        ([], ["missing"], None, "plus dans la bibliothèque"),
        ([{"id": "a", "status": "validated"}], ["a", "a"], None, "une seule fois"),
        ([{"id": "a", "status": "ready", "date_key": "2026-11-27"}], ["a"], None, "validés"),
    ],
)
def test_best_of_plan_rejects_invalid_selection(clips, ids, date_key, message):
    with pytest.raises(ValueError, match=message):
        build_best_of_plan(clips, ids, date_key=date_key)


def test_best_of_plan_rejects_missing_local_render(tmp_path: Path):
    clip = _clip(tmp_path, "gone")
    Path(clip["output_path"]).unlink()
    with pytest.raises(ValueError, match="introuvable sur ce PC"):
        build_best_of_plan([clip], ["gone"])


def test_best_of_renderer_reencodes_landscape_and_adds_silence_when_needed(tmp_path: Path, monkeypatch):
    from studio.web import short_renderer
    from studio.web.best_of import render_best_of_episode

    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"first source")
    second.write_bytes(b"second source")
    output = tmp_path / "episode.mp4"
    probes = []

    def fake_probe(path, ffprobe="ffprobe", timeout=None):
        probes.append(Path(path))
        if Path(path) == output:
            return {"width": 1920, "height": 1080, "duration": 620.0, "has_audio": True}
        return {
            "width": 1080, "height": 1920, "duration": 310.0,
            "has_audio": Path(path) == first,
        }

    commands = []

    def fake_run(command, timeout=None, cwd=None):
        commands.append(command)
        output.write_bytes(b"rendered episode")
        return None

    monkeypatch.setattr(short_renderer, "probe_media", fake_probe)
    monkeypatch.setattr(short_renderer, "resolve_executable", lambda value: str(value))
    monkeypatch.setattr(short_renderer, "run_command", fake_run)

    result = render_best_of_episode(
        {
            "ready_for_render": True,
            "clips": [
                {"id": "first", "output_path": str(first), "duration": 310},
                {"id": "second", "output_path": str(second), "duration": 310},
            ],
        },
        output,
        encoder="libx264",
    )

    command = commands[0]
    graph = command[command.index("-filter_complex") + 1]
    assert result["width"] == 1920 and result["height"] == 1080
    assert result["clip_count"] == 2
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in command
    assert "concat=n=2:v=1:a=1[outv][outa_raw]" in graph
    assert "[outa_raw]afade=t=in:st=0:d=0.350,afade=t=out:st=619.250:d=0.750[outa]" in graph
    assert command[-1] == str(output.resolve())


def test_best_of_plan_rejects_non_finite_clip_durations(tmp_path: Path):
    clip = _clip(tmp_path, "invalid-duration", float("nan"))
    with pytest.raises(ValueError, match="durée du Short"):
        build_best_of_plan([clip], ["invalid-duration"])


def test_best_of_filter_graph_rejects_non_finite_durations():
    from studio.web.best_of import build_best_of_filter_graph

    with pytest.raises(ValueError, match="durées"):
        build_best_of_filter_graph(1, [0], clip_durations=[float("inf")])


def test_best_of_renderer_falls_back_to_cpu_when_amf_cannot_initialize(tmp_path: Path, monkeypatch):
    from studio.web import short_renderer
    from studio.web.best_of import render_best_of_episode

    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "episode.mp4"
    calls = []

    def fake_probe(path, ffprobe="ffprobe", timeout=None):
        if Path(path) == output:
            return {"width": 1920, "height": 1080, "duration": 620, "has_audio": True}
        return {"width": 1080, "height": 1920, "duration": 620, "has_audio": True}

    def fake_run(command, timeout=None, cwd=None):
        calls.append(list(command))
        if len(calls) == 1:
            raise short_renderer.MediaError("AMF encoder device initialization failed")
        output.write_bytes(b"cpu rendered episode")

    monkeypatch.setattr(short_renderer, "probe_media", fake_probe)
    monkeypatch.setattr(short_renderer, "resolve_executable", lambda value: str(value))
    monkeypatch.setattr(short_renderer, "run_command", fake_run)

    result = render_best_of_episode(
        {
            "ready_for_render": True,
            "clips": [{"id": "source", "output_path": str(source), "duration": 620}],
        },
        output,
        encoder="h264_amf",
    )

    assert len(calls) == 2
    assert calls[1][calls[1].index("-c:v") + 1] == "libx264"
    assert "-crf" in calls[1]
    assert result["width"] == 1920



def test_best_of_renderer_reports_real_encoding_progress(tmp_path: Path, monkeypatch):
    from studio.web import short_renderer
    from studio.web.best_of import render_best_of_episode

    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "episode.mp4"
    callbacks = []
    commands = []

    def fake_probe(path, ffprobe="ffprobe", timeout=None):
        if Path(path) == output:
            return {"width": 1920, "height": 1080, "duration": 620, "has_audio": True}
        return {"width": 1080, "height": 1920, "duration": 620, "has_audio": True}

    def fake_run(command, timeout=None, cwd=None, progress_callback=None):
        commands.append(list(command))
        assert "-progress" in command
        assert command[command.index("-progress") + 1] == "pipe:1"
        assert callable(progress_callback)
        progress_callback(310.0)
        output.write_bytes(b"rendered episode")

    monkeypatch.setattr(short_renderer, "probe_media", fake_probe)
    monkeypatch.setattr(short_renderer, "resolve_executable", lambda value: str(value))
    monkeypatch.setattr(short_renderer, "run_command", fake_run)

    render_best_of_episode(
        {
            "ready_for_render": True,
            "clips": [{"id": "source", "output_path": str(source), "duration": 620}],
        },
        output,
        encoder="libx264",
        progress_callback=lambda progress, message: callbacks.append((progress, message)),
    )

    assert any(message == "Vérification des sources · 1/1" for _, message in callbacks)
    assert (52, "Encodage 16:9 · 52%") in callbacks
    assert callbacks[-1] == (95, "Vérification du fichier exporté")


def test_best_of_plan_allows_mixing_shorts_from_different_days(tmp_path: Path):
    clips = [
        _clip(tmp_path, "day-one-a", date_key="2026-11-27"),
        _clip(tmp_path, "day-two-b", date_key="2026-11-28"),
        _clip(tmp_path, "day-three-c", date_key="2026-11-29"),
        _clip(tmp_path, "day-one-d", date_key="2026-11-27"),
    ]

    plan = build_best_of_plan(
        clips,
        ["day-two-b", "day-one-a", "day-three-c", "day-one-d"],
    )

    assert [clip["id"] for clip in plan["clips"]] == [
        "day-two-b", "day-one-a", "day-three-c", "day-one-d",
    ]
    assert [clip["date_key"] for clip in plan["clips"]] == [
        "2026-11-28", "2026-11-27", "2026-11-29", "2026-11-27",
    ]
    assert plan["ready_for_render"] is True
    assert plan["date_key"] == "multi"

    same_day = build_best_of_plan(clips, ["day-one-a", "day-one-d"])
    assert same_day["date_key"] == "2026-11-27"


def test_best_of_plan_allows_shorts_without_a_date(tmp_path: Path):
    clip = _clip(tmp_path, "undated", date_key="")

    plan = build_best_of_plan([clip], ["undated"])

    assert plan["clips"][0]["id"] == "undated"
    assert plan["date_key"] == ""




def test_best_of_plan_accepts_exactly_ten_minutes_and_rejects_just_under(tmp_path: Path):
    clips = [
        _clip(tmp_path, f"ten-minute-{index}", duration=120.0)
        for index in range(5)
    ]
    exact = build_best_of_plan(clips, [clip["id"] for clip in clips])
    assert exact["total_duration"] == 600.0
    assert exact["ready_for_render"] is True

    clips[-1]["duration"] = 119.99
    under = build_best_of_plan(clips, [clip["id"] for clip in clips])
    assert under["ready_for_render"] is False
    assert under["remaining_to_minimum"] == 0.01
