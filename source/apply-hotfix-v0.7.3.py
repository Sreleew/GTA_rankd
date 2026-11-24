from __future__ import annotations

import re
import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    count = text.count(old)
    if count == 0 and new in text:
        return
    if count != 1:
        raise SystemExit(f"Patch v0.7.3 impossible : {count} occurrence(s) du bloc « {label} » dans {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_function(path: Path, name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    start = text.find(f"def {name}(")
    if start < 0:
        raise SystemExit(f"Fonction introuvable : {name} dans {path}")
    next_start = text.find("\ndef ", start + 1)
    end = next_start if next_start >= 0 else len(text)
    updated = text[:start] + replacement.rstrip() + "\n" + text[end:]
    path.write_text(updated, encoding="utf-8")


def ensure_function(path: Path, name: str, replacement: str, before: str = "_fallback_metadata") -> None:
    text = path.read_text(encoding="utf-8-sig")
    if f"def {name}(" in text:
        replace_function(path, name, replacement)
        return
    anchor = f"\ndef {before}("
    if anchor not in text:
        raise SystemExit(f"Point d'insertion absent pour {name} dans {path}")
    path.write_text(text.replace(anchor, "\n" + replacement.rstrip() + "\n" + anchor, 1), encoding="utf-8")


def patch_metadata(root: Path) -> None:
    path = root / "studio/web/metadata.py"

    ensure_function(path, "_is_formulaic_promo_copy", r'''def _is_formulaic_promo_copy(value: str) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    patterns = (
        "youtube promo", "random gta interaction", "random gta encounter",
        "gta encounter into", "encounter into a", "whole youtube promo",
        "turns a gta", "turned a random", "turns a random",
    )
    return any(pattern in text for pattern in patterns)''')

    replace_function(path, "_fallback_metadata", r'''def _fallback_metadata(
    *, streamer: str, note: str, source_url: str, transcript: str,
    custom_hook: str, custom_context: str, source_title: str = "",
) -> dict[str, Any]:
    context = _limit_words(custom_context, 10)
    raw_text = re.sub(r"\s+", " ", str(transcript or "")).strip()
    compact = re.sub(r"[^a-z0-9]+", " ", raw_text.lower())
    game = _game_keyword(note, source_title, transcript)
    creator = _creator_name(streamer, source_title)

    promo_terms = ("youtube", "subscribe", "sub button", "like button", "hit that like", "hit like")
    is_creator_promo = any(term in compact for term in promo_terms)
    mentions_subscribe = any(term in compact for term in ("subscribe", "sub button", "sub to", "subscribers"))
    mentions_like = "like" in compact or "like button" in compact

    if is_creator_promo:
        if mentions_subscribe:
            title = f"{creator} was farming subs in {game} 😭" if creator else f"Someone was farming subs in {game} 😭"
            hook = "HIT THAT LIKE" if mentions_like else "SUBSCRIBE"
            caption = "Still found time to ask everyone for a like 💀" if mentions_like else "The sub button wasn't safe either 💀"
        else:
            title = f"{creator} was farming likes in {game} 😭" if creator else f"Someone was farming likes in {game} 😭"
            hook = "HIT THAT LIKE"
            caption = "The like button was NOT getting left alone 💀"
        thumbnail_text = "HIT THAT LIKE" if mentions_like else "SUBSCRIBE"
    else:
        hook = _limit_words(custom_hook or _fallback_hook(raw_text, note), 6)
        dangling = {"the", "a", "an", "to", "of", "and", "but", "so", "with", "for", "in", "on", "at", "because", "if", "when", "that"}
        quote_words = hook.split()
        while quote_words and quote_words[-1].lower().strip(".,!?;:") in dangling:
            quote_words.pop()
        phrase = _limit_words(" ".join(quote_words), 4) or "GTA MOMENT"
        if creator:
            title = _fit_caption(f"{creator} really said “{phrase.lower()}” in {game} 😭", 90)
        else:
            title = _fit_caption(f"“{phrase.lower()}” in {game} 😭", 90)
        caption = f"“{phrase.lower()}” 😭"
        thumbnail_text = _limit_words(phrase, 4) or "GTA MOMENT"

    credit = f"Clip: {creator}" if creator else "Original clip"
    source_line = f"Source: {source_url.strip()}" if source_url.strip() else ""
    tags = _default_tags(game, streamer, source_title)
    description = "\n".join(part for part in (caption, "", credit, source_line, " ".join(tags)) if part is not None)
    shared = {"title": title, "description": description, "hashtags": tags}
    platforms = {key: dict(shared) for key in PLATFORMS}
    return {
        "hook_text": hook,
        "context_card": context,
        "title": title,
        "title_variants": {key: title for key in PLATFORMS},
        "description": description,
        "hashtags": tags,
        "platforms": platforms,
        "game_keyword": game,
        "thumbnail_text": thumbnail_text,
        "transcript_excerpt": raw_text[:1200],
        "generator": "local_fallback",
    }''')

    # Make the local model write more like a human clip editor and ban the previous formula.
    old_prompt = '"You are the human editor of a fast-growing GTA/Twitch clips page. Read the FULL transcript and identify the main moment, not just the opening words. "'
    new_prompt = '"You are the human editor of a fast-growing GTA/Twitch clips page. Read the FULL transcript and identify the funniest or most memorable specific beat. "\n        "Write like someone who actually watches Twitch clips, not a marketing agency or an AI summary. "\n        "Prefer a short, action-led title with natural gaming language; aim for 5-10 words and under 75 characters. "\n        "Use slang only when it fits naturally. Never describe a specific clip as an \'encounter\', \'interaction\' or \'YouTube promo\'. "\n        "Avoid constructions like \'turns a X encounter into Y\', \'random GTA interaction\' and \'whole YouTube promo\'. "\n        "Example of the desired tone (do not copy its facts): \'IShowSpeed was farming subs in GTA 5 😭\'. "\n        "The description must add a second detail or punchline; it must not paraphrase or repeat the title. "'
    replace_once(path, old_prompt, new_prompt, "consignes de style éditorial humain")

    replace_once(
        path,
        '        invalid_title = (\n            any(phrase in title.lower() for phrase in generic_phrases)\n            or "gta" not in title.lower()\n            or (known_creator and known_creator.lower() not in title.lower())\n            or _has_incomplete_quote(title)\n        )\n',
        '        promo_detected = any(term in re.sub(r"[^a-z0-9]+", " ", transcript.lower()) for term in ("youtube", "subscribe", "sub button", "like button", "hit that like"))\n        invalid_title = (\n            any(phrase in title.lower() for phrase in generic_phrases)\n            or "gta" not in title.lower()\n            or (known_creator and known_creator.lower() not in title.lower())\n            or _has_incomplete_quote(title)\n            or (promo_detected and _is_formulaic_promo_copy(title))\n        )\n',
        "rejet des titres promotionnels trop génériques")

    replace_once(
        path,
        '        if invalid_title or any(phrase in description.lower() for phrase in generic_phrases):\n            description = fallback["description"].split("\\n\\n")[0]\n',
        '        if (invalid_title or any(phrase in description.lower() for phrase in generic_phrases)\n                or (promo_detected and _is_formulaic_promo_copy(description))):\n            description = fallback["description"].split("\\n\\n")[0]\n',
        "rejet des descriptions promotionnelles artificielles")


    prompt_path = root / "prompts/short_metadata.default.txt"
    prompt_path.write_text("""Write one natural, shared title and caption for a GTA/Twitch clips page.
Sound like a real Twitch viewer, not a marketing agency or an AI summary. Use casual English and light Gen Z energy, but never force slang.
Lead with the actual action or funniest detail. Prefer short action-led titles (5-10 words) that include the streamer and GTA keyword when known.
For a creator asking for likes/subs, use a direct viewer-style angle such as “IShowSpeed was farming subs in GTA 5 😭”. Do not use “encounter”, “interaction”, “YouTube promo”, “turns X into Y” or “random GTA interaction”.
The caption must add a second detail or punchline, not repeat the title. Keep it to one natural sentence, then add the streamer/source credit and 3-4 relevant hashtags.
Never invent a reaction, event, location, game mode or payoff. Avoid generic filler and forced phrases like “Bro really turned...” or “this moment was wild”.
Thumbnail text: 2-4 punchy words from the clip, readable on a phone. Return only the JSON schema requested by the app.
""", encoding="utf-8")


def patch_tests(root: Path) -> None:
    path = root / "tests/test_metadata.py"
    text = path.read_text(encoding="utf-8-sig")
    text = text.replace(
        '"IShowSpeed turns a GTA 5 encounter into a YouTube promo 😭"',
        '"IShowSpeed was farming subs in GTA 5 😭"',
    )
    text = text.replace(
        'assert "random GTA interaction" in result["description"]',
        'assert "Still found time to ask everyone for a like" in result["description"]\n    assert "random GTA interaction" not in result["description"]\n    assert "youtube promo" not in result["description"].lower()',
    )
    if 'def test_creator_promo_metadata_uses_short_human_title_and_non_repetitive_caption(' not in text:
        text += r'''


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
'''
    path.write_text(text, encoding="utf-8")


def patch_release(root: Path) -> None:
    for relative in ("VERSION.txt", "pyproject.toml", "config.yaml.default"):
        path = root / relative
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8-sig")
        content = content.replace("Version: 0.7.2", "Version: 0.7.3", 1)
        content = content.replace('version = "0.7.2"', 'version = "0.7.3"', 1)
        content = content.replace("version: 0.7.2", "version: 0.7.3", 1)
        path.write_text(content, encoding="utf-8")

    (root / "NOTES-v0.7.3.txt").write_text("""GTA Ranked Studio v0.7.3

Titres et descriptions :
- Les titres fallback sont désormais plus courts, orientés action et écrits dans un langage de clips gaming naturel.
- Pour les séquences de promotion, l'application privilégie une formulation directe comme « IShowSpeed was farming subs in GTA 5 😭 » au lieu d'un résumé artificiel du type « turns an encounter into a YouTube promo ».
- La description complète le titre avec un second détail ou une punchline, sans le répéter.
- Le modèle local reçoit des exemples de style et les titres/descriptions trop génériques sont rejetés au profit du fallback local.
- Les crédits, la source et les hashtags restent conservés ; le même texte est partagé entre Shorts, TikTok et Reels.

Performance :
- Aucun nouveau modèle, aucun nouvel appel réseau et aucun changement sur le pipeline vidéo.
- Même plafond Ollama de huit secondes ; le fallback est immédiat si le modèle renvoie un texte trop générique.
- Les miniatures, la sélection des images et l'annulation des tâches restent inchangées.
""", encoding="utf-8")
    (root / "VERIFICATION-v0.7.3.md").write_text("""# Vérification v0.7.3

- Test du fallback éditorial IShowSpeed : titre court et spécifique, description complémentaire, accroche et miniature cohérentes.
- Test du détecteur de formulations promotionnelles génériques.
- Les citations ASR tronquées restent protégées par les garde-fous v0.7.2.
- Aucun changement de dépendance, de modèle, de pipeline vidéo ou de durée d'encodage.
""", encoding="utf-8")

    for relative in ("installer/apply_update.ps1", "installer/update_from_archive.ps1", "installer/install.ps1"):
        path = root / relative
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8-sig")
        new_docs = "'NOTES-v0.7.3.txt', 'VERIFICATION-v0.7.3.md'"
        if new_docs not in content:
            anchor = "'NOTES-v0.7.2.txt', 'VERIFICATION-v0.7.2.md'"
            if anchor not in content:
                raise SystemExit(f"Liste des documents v0.7.2 absente dans {relative}")
            content = content.replace(anchor, anchor + ", " + new_docs, 1)
            path.write_text(content, encoding="utf-8-sig", newline="\r\n")

    readme = root / "README.md"
    content = readme.read_text(encoding="utf-8-sig")
    content = content.replace("Dernière version stable : **0.7.2**.", "Dernière version stable : **0.7.3**.")
    content += "\n\n## v0.7.3 : textes de publication plus naturels\n\nLes titres sont plus courts et orientés action ; les descriptions apportent un détail supplémentaire au lieu de répéter le titre. Les formulations promotionnelles génériques sont rejetées au profit d'un fallback humain et vérifié sur le transcript.\n"
    readme.write_text(content, encoding="utf-8")


def apply(root: Path) -> None:
    root = root.resolve()
    patch_metadata(root)
    patch_tests(root)
    patch_release(root)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.7.3.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
    apply(Path(sys.argv[1]))