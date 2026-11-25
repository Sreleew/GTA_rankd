from pathlib import Path

from studio.web.short_editor import (
    WordTiming, apply_thumbnail_overlay, create_ass_file, map_timestamp_through_segments,
    parse_srt, plan_speech_pause_edits, rebase_word_timings,
    rebase_word_timings_by_segments, select_excerpt_range, write_srt_file,
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
    assert "HAPPENED?" in content
    assert r"\c&H0000C8F5&" in content


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



def test_excerpt_starts_at_a_natural_phrase_boundary_and_keeps_the_payoff() -> None:
    words = [
        WordTiming(18.0, 18.5, "Yesterday."),
        WordTiming(22.0, 22.3, "Then"),
        WordTiming(22.4, 22.6, "he"),
        WordTiming(22.65, 23.0, "crashed"),
        WordTiming(23.1, 23.3, "into"),
        WordTiming(23.4, 23.5, "the"),
        WordTiming(23.6, 24.2, "store!"),
        WordTiming(25.0, 25.2, "Oh"),
        WordTiming(25.3, 25.5, "my"),
        WordTiming(25.6, 26.0, "god!"),
    ]

    start, end = select_excerpt_range(
        100.0, 23.8, words,
        minimum_seconds=1.0, maximum_seconds=30.0,
        tail_seconds=2.0,
    )

    assert start == 21.88
    assert end >= 28.0


def test_pause_trim_requires_word_dtw_and_protects_the_peak() -> None:
    words = [
        WordTiming(1.0, 1.2, "So"),
        WordTiming(1.3, 1.5, "we"),
        WordTiming(1.6, 1.8, "waited."),
        WordTiming(5.8, 6.0, "Then"),
        WordTiming(6.1, 6.3, "he"),
        WordTiming(6.4, 6.7, "crashed!"),
        WordTiming(19.0, 19.2, "No"),
        WordTiming(19.3, 19.6, "way!"),
    ]

    plan = plan_speech_pause_edits(
        words, 30.0, 20.0, timestamp_mode="word_dtw",
    )
    assert plan.segments == ((0.0, 2.35), (5.25, 30.0))
    assert plan.removed_pauses == ((2.35, 5.25),)
    assert plan.removed_duration == 2.9

    imprecise = plan_speech_pause_edits(
        words, 30.0, 20.0, timestamp_mode="segment_srt",
    )
    assert imprecise.removed_pauses == ()
    assert imprecise.segments == ((0.0, 30.0),)

    protected = plan_speech_pause_edits(
        words, 30.0, 4.5, timestamp_mode="word_dtw",
    )
    assert protected.removed_pauses == ()


def test_pause_plan_rebases_captions_and_peak_to_the_joined_timeline() -> None:
    segments = ((0.0, 2.35), (5.25, 30.0))
    words = [
        WordTiming(1.6, 1.8, "waited."),
        WordTiming(5.8, 6.0, "Then"),
        WordTiming(6.1, 6.3, "he"),
        WordTiming(6.4, 6.7, "crashed!"),
        WordTiming(19.0, 19.2, "No"),
    ]

    rebased = rebase_word_timings_by_segments(words, segments)
    assert [word.text for word in rebased] == ["waited.", "Then", "he", "crashed!", "No"]
    assert rebased[1] == WordTiming(2.9, 3.1, "Then")
    assert map_timestamp_through_segments(20.0, segments) == 17.1

def test_pause_detection_uses_all_speakers_not_only_caption_voice() -> None:
    # The dominant speaker pauses while another character keeps talking.
    # Filtering captions to the dominant speaker must not turn that dialogue
    # into a false silence that the editor then removes from the video.
    all_speakers = [
        WordTiming(0.2, 0.5, "I"),
        WordTiming(0.7, 1.0, "wait"),
        WordTiming(2.0, 2.3, "hello"),
        WordTiming(3.0, 3.3, "what"),
        WordTiming(4.0, 4.3, "happened"),
        WordTiming(5.0, 5.3, "Then"),
        WordTiming(5.5, 5.8, "go!"),
        WordTiming(15.0, 15.2, "wow"),
        WordTiming(15.4, 15.8, "crazy!"),
    ]
    dominant_voice_only = [
        all_speakers[0], all_speakers[1],
        all_speakers[5], all_speakers[6],
        all_speakers[7], all_speakers[8],
    ]

    safe_plan = plan_speech_pause_edits(
        all_speakers, 20.0, 15.5, timestamp_mode="word_dtw",
    )
    filtered_plan = plan_speech_pause_edits(
        dominant_voice_only, 20.0, 15.5, timestamp_mode="word_dtw",
    )

    assert safe_plan.removed_pauses == ()
    assert filtered_plan.removed_pauses == ((1.55, 4.45),)

