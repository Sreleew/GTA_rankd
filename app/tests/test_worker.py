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
