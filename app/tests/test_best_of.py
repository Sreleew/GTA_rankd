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
