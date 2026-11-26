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

def test_twitch_clip_urls_are_preserved_as_preselected_moments() -> None:
    from studio.web.worker import _is_twitch_clip_url, _resolve_auto_trim_enabled

    clip_urls = [
        "https://clips.twitch.tv/InterestingClipSlug",
        "https://www.twitch.tv/somecreator/clip/InterestingClipSlug",
        "https://m.twitch.tv/somecreator/clip/InterestingClipSlug",
    ]
    for url in clip_urls:
        assert _is_twitch_clip_url(url)
        assert _resolve_auto_trim_enabled({}, url, configured_default=True) is False

    assert not _is_twitch_clip_url("https://www.twitch.tv/videos/123456789")
    assert _resolve_auto_trim_enabled({}, "https://www.twitch.tv/videos/123456789", True) is True
    # Twitch clip URLs stay intact even when the general UI checkbox is on.
    assert _resolve_auto_trim_enabled(
        {"auto_trim_enabled": True}, clip_urls[0], configured_default=True,
    ) is False
    assert _resolve_auto_trim_enabled(
        {"auto_trim_enabled": False}, "https://www.twitch.tv/videos/123456789", configured_default=True,
    ) is False

