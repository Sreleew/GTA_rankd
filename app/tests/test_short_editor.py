from pathlib import Path

from studio.web.short_editor import (
    WordTiming, create_ass_file, infer_hook_style, parse_srt,
    rebase_word_timings, sanitize_word_timings, select_excerpt_range, select_reaction_zoom_timestamps,
    select_thumbnail_timestamp, tighten_speech_edges, write_srt_file,
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


def test_tighten_speech_edges_removes_only_long_lead_and_tail_gaps():
    words = [
        WordTiming(3.0, 3.3, "Wait"),
        WordTiming(30.0, 30.3, "what"),
        WordTiming(54.8, 55.0, "happened?"),
    ]

    start, end = tighten_speech_edges(words, 60.0)

    assert start == 2.7
    assert end == 57.0


def test_tighten_speech_edges_preserves_short_natural_pauses_and_unknown_audio():
    words = [WordTiming(0.4, 0.7, "Hey"), WordTiming(19.0, 19.3, "later")]

    assert tighten_speech_edges(words, 20.0) == (0.0, 20.0)
    assert tighten_speech_edges([], 20.0) == (0.0, 20.0)


def test_reaction_zoom_targets_spoken_reactions_and_stays_sparse():
    words = [
        WordTiming(0.5, 0.8, "WHAT?"),
        WordTiming(2.1, 2.3, "What?"),
        WordTiming(8.0, 8.2, "No"),
        WordTiming(8.3, 8.5, "WAY!"),
        WordTiming(15.0, 15.3, "INSANE!"),
        WordTiming(21.0, 21.3, "normal"),
    ]

    assert select_reaction_zoom_timestamps(words, 30.0) == [2.2, 8.4, 15.15]


def test_reaction_zoom_recognizes_french_spanish_and_portuguese_reactions():
    words = [
        WordTiming(3.0, 3.3, "PUTAIN!"),
        WordTiming(9.0, 9.3, "¡INCREÍBLE!"),
        WordTiming(15.0, 15.3, "INCRÍVEL!"),
    ]

    assert len(select_reaction_zoom_timestamps(words, 24.0)) == 3


def test_reaction_zoom_skips_generic_speech_and_very_short_clips():
    words = [WordTiming(3.0, 3.3, "We"), WordTiming(5.0, 5.3, "drove")]

    assert select_reaction_zoom_timestamps(words, 20.0) == []
    assert select_reaction_zoom_timestamps([WordTiming(1.0, 1.3, "OMG!")], 2.0) == []


def test_ass_contains_hook_branding_and_active_word_highlight(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "captions.ass",
        words=[WordTiming(0.1, 0.3, "Bro"), WordTiming(0.3, 0.6, "WHAT"), WordTiming(0.6, 0.9, "HAPPENED?")],
        hook_text="BRO THOUGHT HE WAS SAFE",
        context_text="A GTA VI police chase goes wrong",
        handle="GTA_rankd",
        word_timed_captions=True,
        brand_enabled=True,
    )
    content = path.read_text(encoding="utf-8-sig")
    assert "BRO THOUGHT HE WAS SAFE" in content
    assert "GTA_rankd" in content
    assert "GTA VI" in content
    assert "GR  //" not in content
    assert r"\fad(180,120)" in content
    assert "0:00:02.00,Hook" in content
    assert "Style: HookKicker" not in content
    assert "HAPPENED?" in content
    assert r"\c&H0000C8F5&" in content


def test_ass_branding_is_disabled_by_default(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "default-brand.ass",
        words=[],
        hook_text="WAIT FOR IT",
        captions_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    assert "GTA_rankd" not in content


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
    assert infer_hook_style("¡NO PUEDE SER, ES INCREÍBLE!") == "reaction"
    assert infer_hook_style("NÃO ACREDITO, ISSO É INCRÍVEL!") == "reaction"
    assert infer_hook_style("¿CÓMO PASÓ ESTO?") == "question"
    assert infer_hook_style("ESPERA, MIRA LO QUE PASÓ") == "suspense"
    assert infer_hook_style("ESPERA, OLHA O QUE ACONTECEU") == "suspense"


def test_caption_active_word_gets_a_subtle_kinetic_pop(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "active-word.ass",
        words=[WordTiming(0.1, 0.4, "WAIT"), WordTiming(0.4, 0.8, "WHAT?")],
        hook_text="",
        word_timed_captions=True,
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    assert r"{\c&H0000C8F5&\fscx106\fscy106\bord7}WAIT" in content
    assert r"{\c&H00FFFFFF&\fscx100\fscy100\bord6}" in content


def test_hook_uses_direct_text_without_series_branding(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "cinematic-hook.ass",
        words=[],
        hook_text="HE THOUGHT HE WAS SAFE",
        badge_text="GTA",
        captions_enabled=False,
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    assert "RANKED DISPATCH" not in content
    assert "HE THOUGHT HE WAS SAFE" in content
    assert infer_hook_style("HE THOUGHT HE WAS SAFE") == "suspense"
    assert r"\blur7" in content
    assert r"\t(0,320,\fscx100\fscy100\blur0)" in content
    assert "0:00:02.00,Hook" in content


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


def test_srt_fallback_keeps_phrase_timing_and_wraps_for_vertical_safe_area(tmp_path: Path):
    words = [WordTiming(0.0, 1.2, "SHOOT IF I'M CLOSE TO CIVILIANS, THEY")]
    path = create_ass_file(
        tmp_path / "wrapped-srt.ass",
        words=words,
        captions_enabled=True,
        word_timed_captions=False,
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    caption_lines = [line for line in content.splitlines() if line.startswith("Dialogue: 0,")]
    assert len(caption_lines) == 1
    assert "0:00:00.00,0:00:01.20" in caption_lines[0]
    assert r"\N" in caption_lines[0]
    assert "CIVILIANS" in caption_lines[0]
    assert r"\c&H0000C8F5&" not in caption_lines[0]


def test_ass_uses_safe_segment_timing_when_timestamp_mode_is_not_supplied(tmp_path: Path):
    words = [WordTiming(0.25, 1.65, "We got away from the police!")]
    path = create_ass_file(
        tmp_path / "unknown-timing.ass",
        words=words,
        captions_enabled=True,
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    caption_lines = [line for line in content.splitlines() if line.startswith("Dialogue: 0,")]
    assert len(caption_lines) == 1
    assert "0:00:00.25,0:00:01.65" in caption_lines[0]
    assert "WE GOT AWAY FROM THE POLICE!" in caption_lines[0].replace(r"\N", " ")
    assert r"\c&H0000C8F5&" not in caption_lines[0]


def test_srt_fallback_scales_an_unbreakable_word_without_changing_its_timing(tmp_path: Path):
    words = [WordTiming(0.0, 1.8, "SUPERCALIFRAGILISTICEXPIALIDOCIOUS")]
    path = create_ass_file(
        tmp_path / "long-srt-word.ass",
        words=words,
        captions_enabled=True,
        word_timed_captions=False,
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    caption_line = next(line for line in content.splitlines() if line.startswith("Dialogue: 0,"))
    assert "0:00:00.00,0:00:01.80" in caption_line
    assert r"\fscx" in caption_line
    assert "SUPERCALIFRAGILISTICEXPIALIDOCIOUS" in caption_line


def test_hook_and_context_clear_quickly_without_an_intro_screen(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "fast-hook.ass",
        hook_text="WAIT, WHAT JUST HAPPENED?",
        context_text="The getaway goes wrong",
        captions_enabled=False,
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    assert "0:00:02.00,Hook" in content
    assert "0:00:02.60,Context" in content


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


def test_thumbnail_timestamp_recognizes_french_reactions_and_emphasis():
    from studio.web.short_editor import select_thumbnail_timestamp

    words = [
        WordTiming(1.0, 1.3, "normal"),
        WordTiming(12.0, 12.4, "C'est"),
        WordTiming(12.4, 13.0, "INCROYABLE!"),
        WordTiming(13.1, 13.5, "Putain!"),
        WordTiming(13.6, 14.0, "DINGUE!"),
        WordTiming(14.1, 14.5, "Sérieux!"),
    ]
    selected = select_thumbnail_timestamp(words, 30.0, preferred=2.0)
    assert 12.0 <= selected <= 14.0

def test_word_dtw_keeps_multiword_records_on_their_real_phrase_interval(tmp_path: Path):
    words = [
        WordTiming(0.00, 0.20, "WAIT"),
        WordTiming(0.25, 1.20, "WE GOT AWAY"),
        WordTiming(1.25, 1.60, "FAST!"),
    ]
    path = create_ass_file(
        tmp_path / "mixed-dtw.ass",
        words=words,
        captions_enabled=True,
        word_timed_captions=True,
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    caption_lines = [line for line in content.splitlines() if line.startswith("Dialogue: 0,")]

    assert len(caption_lines) == 3
    assert "0:00:00.00,0:00:00.20" in caption_lines[0]
    assert r"{\c&H0000C8F5&" in caption_lines[0]
    assert "0:00:00.25,0:00:01.20" in caption_lines[1]
    assert "WE GOT AWAY" in caption_lines[1]
    assert r"{\c&H0000C8F5&" not in caption_lines[1]
    assert "0:00:01.25,0:00:01.60" in caption_lines[2]
    assert "FAST!" in caption_lines[2]
    assert r"{\c&H0000C8F5&" in caption_lines[2]

def test_word_timed_caption_scales_long_unbreakable_word_without_changing_timing(tmp_path: Path):
    word = "SUPERCALIFRAGILISTICEXPIALIDOCIOUS"
    path = create_ass_file(
        tmp_path / "long-dtw-word.ass",
        words=[WordTiming(0.0, 1.8, word)],
        captions_enabled=True,
        word_timed_captions=True,
        brand_enabled=False,
    )
    caption_line = next(
        line for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.startswith("Dialogue: 0,")
    )

    assert "0:00:00.00,0:00:01.80" in caption_line
    assert word in caption_line
    assert r"\fscx60" in caption_line
    assert r"\fscx64" in caption_line


def test_long_hook_and_context_are_balanced_and_kept_inside_mobile_safe_area(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "long-editorial-overlays.ass",
        hook_text="IL A VRAIMENT PENSÉ POUVOIR ÉCHAPPER À LA POLICE",
        hook_style="impact",
        context_text="ET LE STREAMER N'AVAIT ABSOLUMENT RIEN VU VENIR",
        captions_enabled=False,
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    hook_line = next(line for line in content.splitlines() if ",Hook,," in line)
    context_line = next(line for line in content.splitlines() if ",Context,," in line)

    assert hook_line.count(r"\N") == 1
    assert context_line.count(r"\N") == 1
    assert r"\fs" in hook_line
    assert r"\fscx142" in hook_line
    assert r"\fs" in context_line
    assert "0:00:00.00,0:00:02.00" in hook_line
    assert "0:00:00.35,0:00:02.60" in context_line
    assert r"\pos(540,345)" in hook_line
    assert r"\pos(540,672)" in context_line


def test_short_hook_keeps_context_in_its_compact_position(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "compact-editorial-overlays.ass",
        hook_text="WAIT FOR IT",
        context_text="THE GETAWAY GOES WRONG",
        captions_enabled=False,
        brand_enabled=False,
    )
    content = path.read_text(encoding="utf-8-sig")
    hook_line = next(line for line in content.splitlines() if ",Hook,," in line)
    context_line = next(line for line in content.splitlines() if ",Context,," in line)

    assert r"\pos(540,345)" in hook_line
    assert r"\pos(540,576)" in context_line
    assert "WAIT FOR IT" in hook_line
    assert "THE GETAWAY GOES WRONG" in context_line


def test_thumbnail_timestamp_prefers_cluster_of_transcribed_action_cues():
    words = [
        WordTiming(4.0, 4.2, "Incroyable!"),
        WordTiming(4.3, 4.5, "Police!"),
        WordTiming(5.0, 5.2, "Crash!"),
        WordTiming(6.0, 6.2, "Explosion!"),
    ]

    selected = select_thumbnail_timestamp(words, 20.0, preferred=12.0)

    assert 4.5 <= selected <= 5.5


def test_thumbnail_timestamp_falls_back_to_audio_peak_without_descriptive_words():
    words = [WordTiming(1.0, 1.2, "hello"), WordTiming(2.0, 2.2, "everyone")]

    assert select_thumbnail_timestamp(words, 20.0, preferred=12.0) == 12.0


def test_filtered_srt_sidecar_preserves_only_supplied_words_and_exact_intervals(tmp_path: Path):
    from studio.web.short_editor import parse_srt, write_srt_file

    words = [
        WordTiming(0.125, 0.450, "STREAMER"),
        WordTiming(1.200, 1.850, "REACTION!"),
    ]
    path = write_srt_file(tmp_path / "captions.srt", words)

    assert parse_srt(path) == words
    content = path.read_text(encoding="utf-8-sig")
    assert "00:00:00,125 --> 00:00:00,450" in content
    assert "00:00:01,200 --> 00:00:01,850" in content
    assert "GAME_DIALOGUE" not in content


def test_caption_punctuation_keeps_spanish_and_french_marks_with_their_words():
    from studio.web.short_editor import _merge_punctuation

    words = [
        WordTiming(0.10, 0.12, "¿"),
        WordTiming(0.12, 0.25, "Qué"),
        WordTiming(0.25, 0.35, "pasó"),
        WordTiming(0.35, 0.40, "?"),
        WordTiming(0.50, 0.52, "«"),
        WordTiming(0.52, 0.80, "incroyable"),
        WordTiming(0.80, 0.84, "»"),
    ]

    merged = _merge_punctuation(words)

    assert [word.text for word in merged] == ["¿Qué", "pasó?", "«incroyable»"]
    assert merged[0].start == 0.10
    assert merged[0].end == 0.25
    assert merged[1].end == 0.40
    assert merged[2].start == 0.50
    assert merged[2].end == 0.84



def test_rebase_word_timings_discards_non_finite_and_reversed_words():
    words = [
        WordTiming(float("nan"), 1.2, "nan start"),
        WordTiming(1.0, float("inf"), "infinite end"),
        WordTiming(float("-inf"), 0.5, "negative infinity"),
        WordTiming(2.0, 1.5, "reversed"),
        WordTiming(3.0, 3.5, "valid"),
    ]

    assert rebase_word_timings(words, 0.0, 5.0) == [
        WordTiming(3.0, 3.5, "valid"),
    ]


def test_rebase_word_timings_clips_valid_words_to_the_selected_range():
    words = [
        WordTiming(2.5, 3.5, "starts before"),
        WordTiming(4.5, 5.5, "ends after"),
    ]

    assert rebase_word_timings(words, 3.0, 5.0) == [
        WordTiming(0.0, 0.5, "starts before"),
        WordTiming(1.5, 2.0, "ends after"),
    ]


def test_rebase_word_timings_rejects_invalid_cut_bounds():
    words = [WordTiming(1.0, 2.0, "valid")]

    assert rebase_word_timings(words, float("nan"), 3.0) == []
    assert rebase_word_timings(words, 3.0, 2.0) == []



def test_sanitize_word_timings_clips_sorts_and_discards_invalid_words():
    words = [
        WordTiming(1.5, 2.0, "later"),
        WordTiming(2.5, 3.0, "first same start"),
        WordTiming(2.5, 2.8, "second same start"),
        WordTiming(float("nan"), 0.5, "nan start"),
        WordTiming(0.2, float("inf"), "infinite end"),
        WordTiming(1.0, 0.5, "reversed"),
        WordTiming(-0.2, 0.3, "  clipped start  "),
        WordTiming(4.8, 5.5, "clipped end"),
        WordTiming(5.1, 5.4, "outside"),
        WordTiming(2.2, 2.4, "   "),
    ]

    assert sanitize_word_timings(words, 5.0) == [
        WordTiming(0.0, 0.3, "clipped start"),
        WordTiming(1.5, 2.0, "later"),
        WordTiming(2.5, 3.0, "first same start"),
        WordTiming(2.5, 2.8, "second same start"),
        WordTiming(4.8, 5.0, "clipped end"),
    ]


def test_ass_caption_generation_ignores_invalid_raw_word_timings(tmp_path: Path):
    path = create_ass_file(
        tmp_path / "sanitized-caption-input.ass",
        words=[
            WordTiming(float("nan"), 0.5, "NAN WORD"),
            WordTiming(0.5, float("inf"), "INFINITE WORD"),
            WordTiming(1.0, 1.4, "VALID WORD"),
        ],
        word_timed_captions=True,
        brand_enabled=False,
    )

    content = path.read_text(encoding="utf-8-sig")
    assert "VALID WORD" in content
    assert "NAN WORD" not in content
    assert "INFINITE WORD" not in content


def test_thumbnail_timestamp_ignores_invalid_raw_word_timings():
    words = [
        WordTiming(float("nan"), 1.0, "CRASH"),
        WordTiming(2.0, float("inf"), "EXPLOSION"),
    ]

    assert select_thumbnail_timestamp(words, 10.0, preferred=3.0) == 3.0
