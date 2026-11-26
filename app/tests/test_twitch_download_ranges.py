from __future__ import annotations

from studio.web.highlights import build_twitch_download_ranges


def test_twitch_download_range_callback_returns_only_the_requested_window() -> None:
    callback = build_twitch_download_ranges(3600, 4000)

    sections = list(callback({"duration": 19 * 60 * 60}, None))

    assert len(sections) == 1
    assert sections[0]["start_time"] == 3600
    assert sections[0]["end_time"] == 4000


def test_twitch_download_range_callback_preserves_fractional_seconds() -> None:
    callback = build_twitch_download_ranges(3600.25, 4000.75)

    sections = list(callback({"duration": 19 * 60 * 60}, None))

    assert sections[0]["start_time"] == 3600.25
    assert sections[0]["end_time"] == 4000.75
