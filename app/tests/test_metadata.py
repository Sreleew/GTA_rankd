from studio.web.metadata import generate_short_metadata


def test_metadata_fallback_is_bounded_and_credits_source():
    result = generate_short_metadata(
        streamer="StreamerA", note="The police chase went wrong", source_url="https://example.test/clip",
        custom_hook="THIS IS A VERY LONG HOOK WITH WAY MORE THAN EIGHT WORDS INCLUDED",
        custom_context="One two three four five six seven eight nine ten eleven twelve",
        ollama_base_url="http://127.0.0.1:1", retries=0,
    )
    assert len(result["hook_text"].split()) <= 8
    assert len(result["context_card"].split()) <= 10
    assert "Clip: StreamerA" in result["description"]
    assert "Source: https://example.test/clip" in result["description"]
    assert result["generator"] == "local_fallback"


def test_fallback_hook_uses_transcript_and_does_not_create_score_context() -> None:
    from studio.web.metadata import _fallback_metadata

    metadata = _fallback_metadata(
        streamer="Streamer",
        note="Moment fort détecté automatiquement · 100/100",
        source_url="",
        transcript="oh my days God bless the United States what just happened",
        custom_hook="",
        custom_context="",
    )

    assert metadata["hook_text"]
    assert len(metadata["hook_text"].split()) <= 6
    assert metadata["context_card"] == ""
    assert "100/100" not in metadata["hook_text"]


def test_metadata_generation_rejects_the_truncated_opening_from_ishowspeed_clip() -> None:
    result = generate_short_metadata(
        streamer="IShowSpeed", source_title="GTA 5",
        transcript="Oh I know the place so everybody the and sub button I YouTube so please ladies guys hit that like",
        source_url="https://www.twitch.tv/videos/2934870795",
        ollama_base_url="http://127.0.0.1:1", retries=0,
    )
    assert result["title"] == "IShowSpeed was farming subs in GTA 5 😭"
    assert result["thumbnail_text"] == "HIT THAT LIKE"
    assert result["hook_text"] == "HIT THAT LIKE"
    assert "oh i know the" not in result["title"].lower()


def test_metadata_fallback_avoids_incomplete_opening_quote_and_finds_clip_angle() -> None:
    from studio.web.metadata import _fallback_metadata, _has_incomplete_quote

    result = _fallback_metadata(
        streamer="IShowSpeed", note="", source_url="https://www.twitch.tv/videos/2934870795",
        transcript="Oh I know the place so everybody the and sub button I YouTube so please ladies guys hit that like",
        custom_hook="", custom_context="", source_title="GTA 5",
    )
    assert result["title"] == "IShowSpeed was farming subs in GTA 5 😭"
    assert result["thumbnail_text"] == "HIT THAT LIKE"
    assert result["hook_text"] == "HIT THAT LIKE"
    assert not _has_incomplete_quote(result["title"])
    assert _has_incomplete_quote('IShowSpeed really said “oh i know the” in GTA 5 😭')
    assert "Still found time to ask everyone for a like" in result["description"]
    assert "random GTA interaction" not in result["description"]
    assert "youtube promo" not in result["description"].lower()


def test_custom_hook_and_context_override_fallback() -> None:
    metadata = generate_short_metadata(
        streamer="Streamer", custom_hook="THIS IS THE MOMENT TO WATCH",
        custom_context="Police chase near Vice City",
        ollama_base_url="http://127.0.0.1:1", retries=0, timeout=1,
    )
    assert metadata["hook_text"] == "THIS IS THE MOMENT TO WATCH"
    assert metadata["context_card"] == "Police chase near Vice City"

def test_metadata_fallback_provides_platform_specific_copy_and_thumbnail_text():
    result = generate_short_metadata(
        streamer="StreamerA", transcript="Bro wait what just happened in that police chase?",
        source_url="https://example.test/clip", ollama_base_url="http://127.0.0.1:1", retries=0,
    )
    assert set(result["platforms"]) == {"youtube_shorts", "tiktok", "instagram"}
    assert result["platforms"]["youtube_shorts"]["title"]
    assert result["platforms"]["tiktok"]["description"]
    assert result["platforms"]["instagram"]["hashtags"]
    assert all("Clip: StreamerA" in item["description"] for item in result["platforms"].values())
    assert all("Local source" not in item["description"] for item in result["platforms"].values())
    assert 1 <= len(result["thumbnail_text"].split()) <= 4



def test_metadata_fallback_uses_one_natural_shared_post_with_search_keywords():
    result = generate_short_metadata(
        streamer="IShowSpeed", source_title="GTA RP", transcript="Letting everybody look good. Hey, it's okay, you know.",
        source_url="https://www.twitch.tv/videos/2934870795", ollama_base_url="http://127.0.0.1:1", retries=0,
    )
    assert set(result["platforms"]) == {"youtube_shorts", "tiktok", "instagram"}
    assert result["title"] == result["platforms"]["youtube_shorts"]["title"]
    assert len({item["title"] for item in result["platforms"].values()}) == 1
    assert len({item["description"] for item in result["platforms"].values()}) == 1
    assert "IShowSpeed" in result["title"]
    assert "GTA RP" in result["title"]
    assert result["game_keyword"] == "GTA RP"
    assert "Watch the full moment" not in result["description"]
    assert "#GTARP" in result["description"]
    assert "#GTAClips" in result["description"]
    assert "https://www.twitch.tv/videos/2934870795" in result["description"]
    assert 1 <= len(result["thumbnail_text"].split()) <= 4



def test_creator_promo_metadata_uses_short_human_title_and_non_repetitive_caption():
    from studio.web.metadata import _fallback_metadata

    result = _fallback_metadata(
        streamer="IShowSpeed", note="", source_url="https://www.twitch.tv/videos/2934870795",
        transcript="Oh I know the place so everybody the and sub button I YouTube so please ladies guys hit that like",
        custom_hook="", custom_context="", source_title="GTA 5",
    )
    assert result["title"] == "IShowSpeed was farming subs in GTA 5 😭"
    assert result["description"].splitlines()[0] == "Still found time to ask everyone for a like 💀"
    assert result["title"] not in result["description"]
    assert result["thumbnail_text"] == "HIT THAT LIKE"
    assert result["hook_text"] == "HIT THAT LIKE"


def test_formulaic_promo_title_is_flagged_for_local_model_fallback():
    from studio.web.metadata import _is_formulaic_promo_copy

    assert _is_formulaic_promo_copy("IShowSpeed turns a GTA 5 encounter into a YouTube promo 😭")
    assert not _is_formulaic_promo_copy("IShowSpeed was farming subs in GTA 5 😭")



def test_local_model_formulaic_promo_copy_falls_back_to_human_title(monkeypatch):
    import io
    import json
    from studio.web import metadata as metadata_module

    payload = {
        "response": json.dumps({
            "title": "IShowSpeed turns a GTA 5 encounter into a YouTube promo 😭",
            "description": "Bro really turned a random GTA interaction into a whole YouTube promo 😭",
            "hashtags": ["#GTA5", "#IShowSpeed", "#GTAClips"],
            "hook_text": "HIT THAT LIKE",
            "thumbnail_text": "HIT THAT LIKE",
        })
    }

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(
        metadata_module.urllib.request,
        "urlopen",
        lambda request, timeout: FakeResponse(json.dumps(payload).encode("utf-8")),
    )
    result = metadata_module.generate_short_metadata(
        streamer="IShowSpeed", source_title="GTA 5",
        transcript="Oh I know the place so everybody the and sub button I YouTube so please ladies guys hit that like",
        source_url="https://www.twitch.tv/videos/2934870795",
    )
    assert result["title"] == "IShowSpeed was farming subs in GTA 5 😭"
    assert result["description"].splitlines()[0] == "Still found time to ask everyone for a like 💀"
    assert "YouTube promo" not in result["description"]



def test_asr_fragment_is_not_reused_as_title_hook_or_thumbnail_copy():
    result = generate_short_metadata(
        streamer="Tminnzy",
        source_title="GTA 5",
        transcript="yeah huh shit got",
        source_url="https://www.twitch.tv/tminnzy/clip/example",
        ollama_base_url="http://127.0.0.1:1",
    )

    assert "yeah huh shit got" not in result["title"].lower()
    assert "really said" not in result["title"].lower()
    assert result["hook_text"] == ""
    assert result["thumbnail_text"] == "Tminnzy GTA MOMENT"
    assert "yeah huh shit got" not in result["description"].lower()


def test_complete_sentence_keeps_its_descriptive_ending_in_metadata_fallback():
    from studio.web.metadata import _fallback_metadata

    result = _fallback_metadata(
        streamer="Tminnzy",
        note="",
        source_url="",
        transcript="I finally got my car back!",
        custom_hook="",
        custom_context="",
        source_title="GTA 5",
    )

    assert "got my car back" in result["title"].lower()
    assert result["thumbnail_text"].lower() == "got my car back"



def test_incomplete_title_does_not_discard_a_complete_thumbnail_phrase(monkeypatch):
    import io
    import json
    from studio.web import metadata as metadata_module

    payload = {
        "response": json.dumps({
            "title": "Tminnzy really said “yeah huh shit got” in GTA 5 😭",
            "description": "Tminnzy was talking about his Lambo.",
            "hashtags": ["#GTA5", "#Tminnzy", "#GTAClips"],
            "hook_text": "YEAH HUH SHIT GOT",
            "thumbnail_text": "YEAH HUH SHIT GOT MY LAMBO",
        })
    }

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(
        metadata_module.urllib.request,
        "urlopen",
        lambda request, timeout: FakeResponse(json.dumps(payload).encode("utf-8")),
    )
    result = metadata_module.generate_short_metadata(
        streamer="Tminnzy",
        source_title="GTA 5",
        transcript="yeah huh shit got my lambo",
        source_url="https://www.twitch.tv/tminnzy/clip/example",
    )

    assert "yeah huh shit got" not in result["title"].lower()
    assert "got my lambo" in result["title"].lower()
    assert result["hook_text"] == "GOT MY LAMBO"
    assert result["thumbnail_text"] == "YEAH HUH SHIT GOT MY LAMBO"



def test_title_rejects_an_unstated_lambo_recovery_claim():
    from studio.web.metadata import _has_unsupported_event_claim

    transcript = "yeah huh shit got my lambo"
    assert _has_unsupported_event_claim(
        "Tminnzy got his Lambo back in GTA 5 😭", transcript,
    )
    assert not _has_unsupported_event_claim(
        "Tminnzy got his Lambo back in GTA 5 😭", transcript + " back",
    )
