from pathlib import Path

from studio.web.short_editor import (
    WordTiming, apply_thumbnail_overlay, create_ass_file, infer_hook_style, parse_srt,
    rebase_word_timings, select_excerpt_range, write_srt_file,
)


def test_parse_srt_word_timestamps(tmp_path: Path):
    srt = tmp_path / "captions.srt"
    srt.write_text(
        "1\n00:00:00,120 --> 00:00:00,420\nBro\n\n"
        "2\n00:00:00,430 --> 00:00:00,700\nwhat\n\n"
        "3\n00:00:00,710 --> 00:00:01,000\nHAPPENED?\n",
        encoding="utf-8",
    )
    words = parse_srt(srt)
    assert [word.text for word in words] == ["Bro", "what", "HAPPENED?"]
    assert words[0].start == 0.12
    assert words[-1].end == 1.0


def test_ass_contains_hook_branding_and_active_word_highlight(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "captions.ass",
        words=[WordTiming(0.1, 0.3, "Bro"), WordTiming(0.3, 0.6, "WHAT"), WordTiming(0.6, 0.9, "HAPPENED?")],
        hook_text="BRO THOUGHT HE WAS SAFE",
        context_text="A GTA VI police chase goes wrong",
        handle="@GTARankedStudio",
        brand_enabled=True,
    )
    content = path.read_text(encoding="utf-8-sig")
    assert "BRO THOUGHT HE WAS SAFE" in content
    assert "@GTARankedStudio" in content
    assert "GTA VI" in content
    assert "GR  //  GTA VI" in content
    assert r"\fad(180,120)" in content
    assert "0:00:02.60,Hook" in content
    assert "Style: Kicker" in content
    assert "HAPPENED?" in content
    assert r"\c&H0000C8F5&" in content


def test_hook_style_inference_selects_distinct_animations_for_short_hooks(tmp_path: Path):
    examples = [
        ("WHAT JUST HAPPENED?", "question", r"\frz-2"),
        ("WAIT FOR IT", "suspense", r"\blur7"),
        ("NO WAY!", "reaction", r"\fscy122"),
        ("THE CLEANEST GETAWAY", "impact", r"\fscx142"),
    ]
    for index, (hook, expected_style, animation_marker) in enumerate(examples):
        assert infer_hook_style(hook) == expected_style
        path = create_ass_file(
            tmp_path / f"hook-{index}.ass",
            hook_text=hook,
            captions_enabled=False,
            brand_enabled=False,
        )
        content = path.read_text(encoding="utf-8-sig")
        assert animation_marker in content

    # A generic summary must not override the actual hook's intended treatment.
    assert infer_hook_style("THE CLEANEST GETAWAY", "What happened during the chase?") == "impact"
    assert infer_hook_style("", "Wait for the police") == "suspense"
    assert infer_hook_style("POURQUOI IL A FAIT ÇA ?") == "question"
    assert infer_hook_style("ATTENDS DE VOIR LA SUITE") == "suspense"
    assert infer_hook_style("C'EST INCROYABLE !") == "reaction"


def test_caption_active_word_gets_a_subtle_kinetic_pop(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "active-word.ass",
        words=[WordTiming(0.1, 0.4, "WAIT"), WordTiming(0.4, 0.8, "WHAT?")],
        hook_text="",
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    assert r"{\c&H0000C8F5&\fscx106\fscy106\bord7}WAIT" in content
    assert r"{\c&H00FFFFFF&\fscx100\fscy100\bord6}" in content


def test_hook_uses_animated_ranked_dispatch_identity(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "cinematic-hook.ass",
        words=[],
        hook_text="HE THOUGHT HE WAS SAFE",
        badge_text="GTA",
        captions_enabled=False,
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    assert "Style: HookKicker" in content
    assert "RANKED DISPATCH  //  GTA" in content
    assert "HE THOUGHT HE WAS SAFE" in content
    assert infer_hook_style("HE THOUGHT HE WAS SAFE") == "suspense"
    assert r"\blur7" in content
    assert r"\t(0,320,\fscx100\fscy100\blur0)" in content
    assert "0:00:02.60,Hook" in content


def test_smart_layout_moves_captions_below_the_gameplay_panel(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "smart-captions.ass",
        words=[WordTiming(0.1, 0.4, "LAMBO")],
        captions_enabled=True,
        brand_enabled=False,
        layout="smart",
        width=1080,
        height=1920,
    )
    content = path.read_text(encoding="utf-8-sig")
    assert r"\pos(540,1670)" in content


def test_ass_can_disable_captions_and_brand(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "minimal.ass", words=[WordTiming(0, 0.3, "HELLO")],
        captions_enabled=False, brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    assert "HELLO" not in content
    assert "@GTARankedStudio" not in content


def test_thumbnail_overlay_adds_editorial_text(tmp_path: Path) -> None:
    from PIL import Image, ImageChops

    thumbnail = tmp_path / "thumbnail.jpg"
    Image.new("RGB", (360, 640), (30, 40, 55)).save(thumbnail, quality=90)
    with Image.open(thumbnail) as original:
        baseline = original.convert("RGB").copy()
    apply_thumbnail_overlay(thumbnail, "GTA VI CRAZY MOMENT")
    with Image.open(thumbnail) as result:
        assert result.size == (1080, 1920)
        assert result.format == "JPEG"
        assert ImageChops.difference(baseline.resize(result.size), result.convert("RGB")).getbbox() is not None
        assert thumbnail.stat().st_size > 10_000


def test_thumbnail_timestamp_prefers_descriptive_transcript_moment() -> None:
    from studio.web.short_editor import select_thumbnail_timestamp

    words = [
        WordTiming(1.0, 1.2, "Oh"), WordTiming(1.2, 1.4, "I"),
        WordTiming(1.4, 1.8, "know"), WordTiming(2.0, 2.4, "the"),
        WordTiming(18.0, 18.4, "YouTube"), WordTiming(19.0, 19.3, "please"),
        WordTiming(20.0, 20.4, "ladies"), WordTiming(22.0, 22.2, "guys"),
        WordTiming(22.3, 22.5, "hit"), WordTiming(22.6, 22.8, "that"),
        WordTiming(22.9, 23.3, "like"), WordTiming(23.4, 23.8, "button"),
    ]
    selected = select_thumbnail_timestamp(words, 40.0, preferred=4.0)
    assert 18.0 <= selected <= 25.0


def test_thumbnail_timestamp_falls_back_to_audio_peak_without_salient_words() -> None:
    from studio.web.short_editor import select_thumbnail_timestamp

    selected = select_thumbnail_timestamp([WordTiming(1.0, 1.2, "Hello")], 20.0, preferred=8.5)
    assert selected == 8.5


def test_long_clip_excerpt_keeps_payoff_and_context() -> None:
    words = [
        WordTiming(25.0, 25.3, "Wait"),
        WordTiming(25.35, 25.7, "for"),
        WordTiming(25.75, 26.1, "it."),
        WordTiming(29.0, 29.4, "What"),
        WordTiming(29.45, 30.0, "happened?"),
    ]
    start, end = select_excerpt_range(60.0, 29.2, words)
    assert 0 <= start < 29.2 < end <= 60
    assert 15 <= end - start <= 45
    assert end >= 32.0  # environ 2 secondes après la fin de la réaction



def test_long_clip_excerpt_starts_on_a_sentence_boundary_before_the_payoff() -> None:
    words = [
        WordTiming(4.0, 4.3, "We"),
        WordTiming(4.3, 4.6, "left"),
        WordTiming(4.6, 5.0, "early."),
        WordTiming(6.0, 6.3, "Then"),
        WordTiming(6.3, 6.6, "the"),
        WordTiming(6.6, 7.0, "police"),
        WordTiming(7.0, 7.4, "arrived."),
        WordTiming(20.0, 20.3, "Wait"),
        WordTiming(20.3, 20.6, "what?"),
        WordTiming(20.8, 21.0, "No."),
    ]

    start, end = select_excerpt_range(60.0, 20.5, words)

    assert start == 6.0
    assert end >= 22.6
    assert 15.0 <= end - start <= 45.0


def test_long_clip_excerpt_can_start_after_a_natural_pause_without_punctuation() -> None:
    words = [
        WordTiming(10.0, 10.4, "We"),
        WordTiming(10.4, 10.8, "waited"),
        WordTiming(15.0, 15.3, "Then"),
        WordTiming(15.3, 15.6, "he"),
        WordTiming(15.6, 16.0, "crashed"),
        WordTiming(20.0, 20.3, "No"),
        WordTiming(20.3, 20.7, "way."),
    ]

    start, end = select_excerpt_range(60.0, 20.5, words, minimum_seconds=5.0)

    assert start == 15.0
    assert end >= 22.7
    assert 5.0 <= end - start <= 45.0




def test_long_clip_excerpt_keeps_delayed_streamer_reaction_after_audio_peak() -> None:
    words = [
        WordTiming(60.0, 60.3, "We"),
        WordTiming(60.3, 60.6, "were"),
        WordTiming(60.6, 61.0, "driving."),
        WordTiming(80.0, 80.3, "Wait"),
        WordTiming(80.3, 80.6, "what"),
        WordTiming(80.6, 80.9, "happened?"),
        WordTiming(84.0, 84.3, "BRO"),
        WordTiming(84.3, 84.7, "NO"),
        WordTiming(84.7, 85.2, "WAY!"),
        WordTiming(87.0, 87.4, "That"),
        WordTiming(87.4, 87.8, "was"),
        WordTiming(87.8, 88.2, "crazy."),
    ]

    start, end = select_excerpt_range(
        180.0, 81.0, words, minimum_seconds=60.0, maximum_seconds=165.0,
    )

    assert start <= 81.0
    assert end >= 87.2  # reaction phrase + configured tail
    assert 60.0 <= end - start <= 165.0


def test_long_clip_excerpt_does_not_stop_at_pause_before_delayed_reaction() -> None:
    words = [
        WordTiming(30.0, 30.3, "Wait"),
        WordTiming(30.3, 30.6, "for"),
        WordTiming(30.6, 31.0, "it."),
        WordTiming(36.0, 36.3, "NO"),
        WordTiming(36.3, 36.8, "WAY!"),
    ]

    _, end = select_excerpt_range(180.0, 31.0, words)

    assert end >= 38.8

def test_production_excerpt_profile_targets_one_to_two_minutes_forty_five() -> None:
    short_source = select_excerpt_range(
        120.0, 55.0, [], threshold_seconds=165.0,
        minimum_seconds=60.0, maximum_seconds=165.0,
    )
    assert short_source == (0.0, 120.0)

    long_source = select_excerpt_range(
        300.0, 150.0, [], threshold_seconds=165.0,
        minimum_seconds=60.0, maximum_seconds=165.0,
    )
    assert 60.0 <= long_source[1] - long_source[0] <= 165.0
    assert long_source[0] <= 104.0
    assert long_source[1] >= 162.0



def test_short_clip_is_never_trimmed_and_word_times_are_rebased(tmp_path: Path) -> None:
    assert select_excerpt_range(21.1, 10.0, []) == (0.0, 21.1)
    original = [WordTiming(10.0, 10.3, "Bro"), WordTiming(10.35, 10.8, "WHAT?")]
    rebased = rebase_word_timings(original, 9.0, 11.0)
    assert rebased == [WordTiming(1.0, 1.3, "Bro"), WordTiming(1.35, 1.8, "WHAT?")]
    path = write_srt_file(tmp_path / "captions.srt", rebased)
    contents = path.read_text(encoding="utf-8")
    assert "00:00:01,000 --> 00:00:01,300" in contents
    assert "WHAT?" in contents


def test_long_caption_segment_is_split_and_wrapped_for_vertical_safe_area(tmp_path: Path):
    words = [WordTiming(0.0, 1.2, "SHOOT IF I'M CLOSE TO CIVILIANS, THEY")]
    path = create_ass_file(tmp_path / "wrapped.ass", words=words, brand_enabled=False)
    content = path.read_text(encoding="utf-8-sig")
    assert r"\N" in content
    assert "CIVILIANS" in content
    # A segment-level fallback is expanded to individual active words.
    assert content.count("Dialogue: 0,") > 1


def test_thumbnail_overlay_builds_vertical_gta_poster_from_full_landscape_gameplay(tmp_path: Path) -> None:
    from PIL import Image, ImageChops

    thumbnail = tmp_path / "thumbnail.jpg"
    # Simulates a 16:9 Twitch gameplay frame rather than a pre-rendered blurred Short.
    Image.new("RGB", (1920, 1080), (30, 120, 55)).save(thumbnail, quality=90)
    with Image.open(thumbnail) as original:
        baseline = original.convert("RGB").copy()
    apply_thumbnail_overlay(thumbnail, "LETTING EVERYBODY LOOK GOOD", streamer="IShowSpeed", game_label="GTA RP")
    with Image.open(thumbnail) as result:
        assert result.size == (1080, 1920)
        assert result.format == "JPEG"
        assert ImageChops.difference(baseline.resize(result.size), result.convert("RGB")).getbbox() is not None
        panel_pixel = result.convert("RGB").getpixel((540, 900))
        assert panel_pixel[1] > panel_pixel[0] * 2, "La capture de gameplay doit rester visible dans le cadre principal."
        assert thumbnail.stat().st_size > 10_000



def test_thumbnail_overlay_uses_a_compact_editorial_cover_and_sanitizes_fragment(tmp_path: Path):
    from PIL import Image

    thumbnail = tmp_path / "editorial-thumbnail.jpg"
    Image.new("RGB", (1920, 1080), (42, 70, 90)).save(thumbnail, quality=90)

    apply_thumbnail_overlay(
        thumbnail,
        "YEAH HUH SHIT GOT",
        streamer="Tminnzy",
        game_label="GTA 5",
    )

    with Image.open(thumbnail) as result:
        assert result.size == (1080, 1920)
        assert result.format == "JPEG"
        assert result.width == 1080 and result.height == 1920
        assert thumbnail.stat().st_size > 15_000



def test_thumbnail_headline_prefers_complete_meaningful_tail_over_filler():
    from studio.web.short_editor import _thumbnail_headline

    assert _thumbnail_headline("YEAH HUH SHIT GOT MY LAMBO", "Tminnzy") == "GOT MY LAMBO"
    assert _thumbnail_headline("YEAH HUH SHIT GOT", "Tminnzy") == "Tminnzy GTA MOMENT"
    assert _thumbnail_headline("YEAH HUH SHIT", "Tminnzy") == "Tminnzy GTA MOMENT"


def test_caption_groups_break_at_sentence_punctuation():
    from studio.web.short_editor import _caption_events

    words = [
        WordTiming(0.00, 0.20, "I"),
        WordTiming(0.21, 0.55, "got"),
        WordTiming(0.56, 0.90, "him."),
        WordTiming(1.00, 1.30, "Wait"),
        WordTiming(1.31, 1.70, "what?"),
    ]
    events = _caption_events(words, 1080, 1920)

    assert len(events) == 5
    assert all("WAIT" not in event for event in events[:3])
    assert all("GOT" not in event for event in events[3:])
