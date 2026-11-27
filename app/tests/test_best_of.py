from pathlib import Path

import pytest

from studio.web.best_of import build_best_of_plan


def _clip(tmp_path: Path, clip_id: str, duration: float = 140.0, *, date_key: str = "2026-11-27", status: str = "validated"):
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


def test_best_of_plan_preserves_user_order_and_targets_nine_to_eleven_minutes(tmp_path: Path):
    clips = [_clip(tmp_path, f"clip-{index}") for index in range(5)]
    plan = build_best_of_plan(clips, ["clip-3", "clip-1", "clip-4", "clip-0"], date_key="2026-11-27")

    assert [clip["id"] for clip in plan["clips"]] == ["clip-3", "clip-1", "clip-4", "clip-0"]
    assert plan["clip_count"] == 4
    assert plan["total_duration"] == 560.0
    assert plan["formatted_duration"] == "09:20"
    assert plan["ready_for_render"] is True
    assert plan["remaining_to_minimum"] == 0


def test_best_of_plan_reports_selection_that_is_too_short_or_too_long(tmp_path: Path):
    clips = [_clip(tmp_path, "short", 120), _clip(tmp_path, "long", 700)]
    too_short = build_best_of_plan(clips, ["short"])
    too_long = build_best_of_plan(clips, ["long"])

    assert too_short["ready_for_render"] is False
    assert too_short["remaining_to_minimum"] == 420
    assert too_long["ready_for_render"] is False
    assert too_long["over_maximum"] == 40


@pytest.mark.parametrize(
    ("clips", "ids", "date_key", "message"),
    [
        ([], [], None, "au moins un Short"),
        ([], ["missing"], None, "plus dans la bibliothèque"),
        ([{"id": "a", "status": "validated"}], ["a", "a"], None, "une seule fois"),
        ([{"id": "a", "status": "ready"}], ["a"], None, "validés"),
        ([{"id": "a", "status": "validated", "date_key": "2026-11-26"}], ["a"], "2026-11-27", "date sélectionnée"),
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
            return {"width": 1920, "height": 1080, "duration": 560.0, "has_audio": True}
        return {
            "width": 1080, "height": 1920, "duration": 280.0,
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
                {"id": "first", "output_path": str(first), "duration": 280},
                {"id": "second", "output_path": str(second), "duration": 280},
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
    assert "concat=n=2:v=1:a=1[outv][outa]" in graph
    assert command[-1] == str(output.resolve())
