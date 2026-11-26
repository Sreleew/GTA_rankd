from __future__ import annotations

from studio.web.short_renderer import build_filter_complex


def test_legacy_webcam_zone_does_not_extract_or_overlay_a_second_video() -> None:
    baseline = build_filter_complex(layout="blur", dynamic_zoom=False)
    legacy_option = build_filter_complex(
        layout="blur", dynamic_zoom=False, webcam_zone="bottom-left"
    )

    assert legacy_option == baseline
    assert "[0:v]split=2[bgsrc][fgsrc]" in legacy_option
    assert "[webcam_src]" not in legacy_option
    assert "overlay=(W-w)/2:(H-h)/2" in legacy_option
    assert "boxblur" in legacy_option
