"""Fast local social metadata generation with deterministic fallbacks."""
from __future__ import annotations

import json
import logging
import re
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
PLATFORMS = ("youtube_shorts", "tiktok", "instagram")
DEFAULT_TAGS = {
    "youtube_shorts": ["#GTA", "#GTAOnline", "#Shorts"],
    "tiktok": ["#GTA", "#Gaming", "#GTAV", "#GamingClips"],
    "instagram": ["#GTA", "#GTAV", "#GamingReels", "#GTAClips"],
}


def _limit_words(value: str, maximum: int) -> str:
    return " ".join(str(value or "").split()[:maximum]).strip()


def _word_tokens(value: str) -> list[str]:
    """Split words without dropping accents or splitting apostrophe contractions."""
    return re.findall(r"[^\W_]+(?:[’'][^\W_]+)*", str(value or ""), flags=re.UNICODE)


def _token_key(value: str) -> str:
    """Return an accent-insensitive key for matching multilingual cue words."""
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


_HOOK_CUES = {
    # English
    "what", "wait", "bro", "no", "oh", "why", "look", "listen", "insane",
    "crazy", "actually", "help", "stop", "how", "wtf", "omg", "nah", "clutch",
    # French
    "quoi", "attends", "regarde", "ecoute", "incroyable", "dingue", "impossible",
    "serieux", "fou", "folle", "merde", "putain", "non", "pourquoi", "comment", "aide",
    # Spanish and Portuguese
    "mira", "espera", "increible", "locura", "dios", "ayuda", "como",
    "nao", "incrivel", "caramba", "olha", "ajuda", "meu", "deus",
}
_FILLER_OPENERS = {
    "yeah", "yea", "huh", "uh", "um", "bro", "man", "shit", "like",
    "ouais", "bah", "ben", "genre", "frere", "mano", "tio", "bueno", "vale",
}
_DANGLING_WORDS = {
    # English
    "a", "an", "and", "are", "at", "because", "but", "for", "from", "got",
    "had", "has", "have", "he", "her", "his", "if", "in", "is", "it", "my",
    "of", "on", "or", "she", "so", "that", "the", "their", "them", "then",
    "there", "they", "this", "to", "was", "we", "were", "with", "you", "your",
    "yeah", "yea", "huh", "shit", "uh", "um",
    # French, Spanish and Portuguese articles, prepositions and conjunctions
    "de", "du", "des", "le", "la", "les", "un", "une", "et", "mais", "pour",
    "avec", "dans", "sur", "au", "aux", "que", "qui", "est", "sont", "ont",
    "ce", "cette", "mon", "ma", "mes", "son", "sa", "ses", "leur", "leurs",
    "pas", "ne", "se", "ou", "donc", "car", "el", "los", "las", "una", "y",
    "pero", "por", "para", "con", "del", "al", "es", "mi", "tu", "su", "sus",
    "o", "os", "as", "um", "uma", "e", "do", "da", "em", "com", "quem",
    "meu", "minha", "seu", "sua",
}
_LEADING_DANGLING_WORDS = {
    # Function words only: do not remove meaningful verbs or pronouns such as "got" or "my".
    "a", "an", "and", "but", "for", "from", "in", "of", "on", "or", "so", "the", "to", "with",
    # French, Spanish and Portuguese articles, prepositions and conjunctions
    "de", "du", "des", "le", "la", "les", "un", "une", "et", "mais", "pour", "avec",
    "dans", "sur", "au", "aux", "en", "que", "qui", "el", "los", "las", "una", "y",
    "pero", "por", "para", "con", "del", "al", "o", "os", "as", "uma", "e", "do",
    "da", "em", "com",
}
_GTA_ANCHORS = {
    # English
    "lambo", "lamborghini", "car", "cars", "whip", "ride", "vehicle", "police",
    "cop", "cops", "crash", "crashed", "explosion", "bank", "money", "bike",
    "motorcycle", "plane", "helicopter", "train", "house", "store", "shop",
    "robbery", "robbed", "chase", "chased",
    # French, Spanish and Portuguese
    "voiture", "voitures", "vehicule", "police", "flic", "flics", "accident",
    "explosion", "banque", "argent", "moto", "avion", "helicoptere", "train",
    "maison", "magasin", "boutique", "braquage", "braque", "poursuite",
    "coche", "carro", "policia", "choque", "banco", "dinero", "helicoptero",
    "tren", "casa", "tienda", "robo", "persecucion", "acidente", "dinheiro",
    "aviao", "trem", "loja", "roubo", "perseguicao",
}


def _clean_line(value: Any, maximum: int, fallback: str = "") -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().strip('"\'')
    return text[:maximum].rstrip() or fallback


def _fit_caption(value: str, maximum: int) -> str:
    text = str(value or "").strip()
    if len(text) <= maximum:
        return text
    clipped = text[: max(1, maximum - 1)]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped.rstrip(" .,!?:;\n") + "…"


def _normalise_tags(value: Any, fallback: list[str], maximum: int) -> list[str]:
    items = value if isinstance(value, list) else fallback
    output: list[str] = []
    for item in items:
        tag = re.sub(r"[^A-Za-z0-9_]", "", str(item).lstrip("#"))
        if tag:
            tag = "#" + tag
            if tag.lower() not in {existing.lower() for existing in output}:
                output.append(tag)
        if len(output) >= maximum:
            break
    return output or fallback[:maximum]


def _fallback_hook(transcript: str, note: str = "") -> str:
    source = str(transcript or "").strip()
    if not source:
        note_clean = re.sub(r"\s+", " ", str(note or "")).strip()
        if note_clean and not re.search(r"(?:moment fort détecté|score|100/100|automatiquement)", note_clean, re.I):
            return _limit_words(note_clean, 5).upper()
        return "WAIT FOR THE REACTION"
    words = _word_tokens(source)
    if not words:
        return "WAIT FOR THE REACTION"
    keys = [_token_key(word) for word in words]
    cue_index = next((i for i, key in enumerate(keys) if key in _HOOK_CUES), 0)
    start = max(0, cue_index - 2)
    chosen = words[start:start + 6]
    if len(chosen) < 3:
        chosen = words[:6]
    while len(chosen) > 1 and _token_key(chosen[0]) in _FILLER_OPENERS:
        chosen.pop(0)
    while chosen and _token_key(chosen[-1]) in _DANGLING_WORDS:
        chosen.pop()
    return " ".join(chosen).upper()


def _credit_line(streamer: str, source_title: str, source_url: str) -> str:
    person = streamer.strip() or source_title.strip() or "GTA creator"
    source = source_url.strip()
    return f"Clip: {person} ({source})" if source else f"Clip: {person}"


def _creator_name(streamer: str, source_title: str) -> str:
    return re.sub(r"\s+", " ", str(streamer or "")).strip()[:42]

def _creator_tag(streamer: str, source_title: str) -> str | None:
    value = re.sub(r"[^A-Za-z0-9_]", "", str(streamer or ""))
    if len(value) < 3 or value.lower() in {"streamer", "creator", "unknown"}:
        return None
    return "#" + value[:28]

def _default_tags(game: str, streamer: str, source_title: str) -> list[str]:
    tags = ["#GTA"]
    if game == "GTA RP":
        tags.append("#GTARP")
    elif game == "GTA Online":
        tags.append("#GTAOnline")
    else:
        tags.append("#GTA5")
    creator = _creator_tag(streamer, source_title)
    if creator and creator.lower() not in {tag.lower() for tag in tags}:
        tags.append(creator)
    tags.append("#GTAClips")
    return tags[:4]

def _game_keyword(note: str, source_title: str, transcript: str) -> str:
    text = " ".join((str(note or ""), str(source_title or ""), str(transcript or ""))).lower()
    compact = re.sub(r"[^a-z0-9]+", " ", text)
    if any(term in compact for term in ("gta rp", "gta roleplay", "roleplay", "role play")):
        return "GTA RP"
    if any(term in compact for term in ("gta online", "gtao")):
        return "GTA Online"
    if any(term in compact for term in ("gta 5", "gta v", "grand theft auto v")):
        return "GTA 5"
    return "GTA 5"

def _is_formulaic_promo_copy(value: str) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    patterns = (
        "youtube promo", "random gta interaction", "random gta encounter",
        "gta encounter into", "encounter into a", "whole youtube promo",
        "turns a gta", "turned a random", "turns a random",
    )
    return any(pattern in text for pattern in patterns)

def _is_incomplete_phrase(value: str) -> bool:
    words = _word_tokens(str(value or "").lower())
    if not words:
        return True
    return _token_key(words[-1]) in _DANGLING_WORDS


def _last_complete_phrase(transcript: str) -> str:
    """Return a complete ASR sentence or a short phrase anchored by a clear GTA noun."""
    clean = re.sub(r"\s+", " ", str(transcript or "")).strip()
    phrases = re.split(r"(?<=[.!?])\s+", clean)
    for phrase in reversed(phrases):
        words = _word_tokens(phrase)
        if 3 <= len(words) <= 14 and not _is_incomplete_phrase(phrase):
            return phrase.strip()

    # ASR often omits punctuation. Retain a short phrase only when it contains
    # a concrete object/action word, including common French, Spanish and Portuguese terms.
    tokens = _word_tokens(clean)
    keys = [_token_key(token) for token in tokens]
    for index in range(len(tokens) - 1, -1, -1):
        if keys[index] not in _GTA_ANCHORS:
            continue
        start = max(0, index - 3)
        end = min(len(tokens), index + 2)
        selected = tokens[start:end]
        while len(selected) > 1 and _token_key(selected[0]) in _FILLER_OPENERS:
            selected.pop(0)
        while selected and _token_key(selected[-1]) in _DANGLING_WORDS:
            selected.pop()
        if 2 <= len(selected) <= 5:
            return " ".join(selected)
    return ""


def _has_unsupported_event_claim(title: str, transcript: str, note: str = "") -> bool:
    """Reject strong event claims that the source text does not actually support."""
    source_tokens = set(re.findall(r"[A-Za-z0-9']+", f"{transcript} {note}".lower()))
    title_tokens = set(re.findall(r"[A-Za-z0-9']+", str(title or "").lower()))
    claims = {
        "back": {"back"},
        "stole": {"steal", "stole", "stolen", "stealing"},
        "stolen": {"steal", "stole", "stolen", "stealing"},
        "stealing": {"steal", "stole", "stolen", "stealing"},
        "returned": {"return", "returned", "returning", "back"},
        "recovered": {"recover", "recovered", "recovering"},
        "won": {"win", "won", "winning"},
        "lost": {"lose", "lost", "losing"},
        "crashed": {"crash", "crashed", "crashing"},
        "exploded": {"explode", "exploded", "explosion"},
        "arrested": {"arrest", "arrested", "arresting"},
    }
    return any(token in title_tokens and not (allowed & source_tokens) for token, allowed in claims.items())


def _fallback_metadata(
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
        complete_phrase = _last_complete_phrase(raw_text)
        hook = _limit_words(custom_hook or _fallback_hook(complete_phrase or raw_text, note), 6)
        if not custom_hook and _is_incomplete_phrase(hook):
            hook = ""
        if complete_phrase:
            phrase_words = _word_tokens(complete_phrase)[-4:]
            while phrase_words and _token_key(phrase_words[0]) in _LEADING_DANGLING_WORDS:
                phrase_words.pop(0)
            phrase = _limit_words(" ".join(phrase_words), 4) or "GTA MOMENT"
            if creator:
                title = _fit_caption(f"{creator} really said “{phrase.lower()}” in {game} 😭", 90)
            else:
                title = _fit_caption(f"“{phrase.lower()}” in {game} 😭", 90)
            caption = f"“{phrase.lower()}” 😭"
            thumbnail_text = phrase
        else:
            # An ASR fragment is not a quote. Stay factual until a complete
            # spoken thought or a reliable editorial summary is available.
            title = _fit_caption(f"{creator}'s {game} moment 😭" if creator else f"A {game} moment 😭", 90)
            caption = f"A {game} moment with {creator} 😭" if creator else f"A {game} moment 😭"
            thumbnail_text = f"{creator.split()[0]} GTA MOMENT" if creator else "GTA MOMENT"

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
    }

def generate_short_metadata(
    *, streamer: str = "", note: str = "", source_url: str = "", source_title: str = "",
    transcript: str = "", custom_hook: str = "", custom_context: str = "",
    ollama_base_url: str = "http://127.0.0.1:11434", ollama_model: str = "qwen2.5:7b-instruct",
    prompt_path: Path | None = None, timeout: int = 8, retries: int = 0,
) -> dict[str, Any]:
    fallback = _fallback_metadata(
        streamer=streamer, note=note, source_url=source_url, transcript=transcript,
        custom_hook=custom_hook, custom_context=custom_context, source_title=source_title,
    )
    if not transcript.strip() and not note.strip() and not custom_hook.strip() and not custom_context.strip():
        return fallback

    prompt_rules = (
        "You are the human editor of a fast-growing GTA/Twitch clips page. Read the FULL transcript and identify the funniest or most memorable specific beat. "
        "Write like someone who actually watches Twitch clips, not a marketing agency or an AI summary. "
        "Prefer a short, action-led title with natural gaming language; aim for 5-10 words and under 75 characters. "
        "Use slang only when it fits naturally. Never describe a specific clip as an 'encounter', 'interaction' or 'YouTube promo'. "
        "Avoid constructions like 'turns a X encounter into Y', 'random GTA interaction' and 'whole YouTube promo'. "
        "Example of the desired tone (do not copy its facts): 'IShowSpeed was farming subs in GTA 5 😭'. "
        "The description must add a second detail or punchline; it must not paraphrase or repeat the title. "
        "The opening may be cut off or ASR may end mid-sentence; never turn an incomplete phrase into a quote or title. "
        "If the opening is incomplete, use a later complete moment or summarise the action. "
        "Write like a real viewer, "
        "not a marketing agency or an AI assistant. Use casual natural English with light Gen Z energy; "
        "use 😭 or 💀 only when they genuinely fit. Never force slang. Use ONLY facts and moments supported "
        "by the transcript, title or note. Find the most specific funny, awkward, chaotic or surprising detail. "
        "Include a searchable GTA keyword (GTA RP, GTA Online or GTA 5) and the streamer name when known, "
        "but never invent the game mode. Make the title sound like a human wrote it: concise, clear and clickable. "
        "Do not start every title with 'GTA:'. Avoid formulaic phrases like 'Watch the full moment', "
        "'This moment was wild', 'you won't believe', 'GTA never disappoints', 'POV', 'unexpected moment', "
        "'the craziest moment ever' or 'worth watching'. Do not repeat the title word-for-word in the caption. "
        "Write ONE shared title and ONE shared caption/description for all platforms, not separate versions. "
        "Caption: one or two short natural lines, no generic CTA, followed by a simple streamer credit, source URL "
        "when supplied, and 3-4 useful search hashtags. Prefer #GTA, #GTA5 or #GTARP as appropriate, plus the "
        "creator tag when known. Thumbnail text: 2-4 punchy words, readable on a phone, not a sentence. Never use a transcript fragment as the thumbnail headline. "
        "If a spoken phrase is incomplete or has no clear ending, do not quote it in the title, description, hook or thumbnail. "
        "Do not claim that a car was stolen, returned, recovered, won, lost, crashed or exploded unless the transcript or note explicitly supports that event. "
        "Prefer an action-led summary only when the action is explicitly supported by the transcript or supplied context; otherwise use a short neutral GTA moment title and an empty hook. "
        "Hook text: 3-6 words for the opening 2.6 seconds, grounded in a complete thought from the transcript. context_card must be empty "
        "unless a custom context was supplied. Return valid JSON only with title, description, hashtags, "
        "hook_text, context_card and thumbnail_text."
    )
    if prompt_path and prompt_path.is_file():
        extra = prompt_path.read_text(encoding="utf-8", errors="replace").strip()
        if extra:
            prompt_rules += "\n\nAdditional style guidance (do not override the required JSON schema):\n" + extra
    payload = {
        "streamer": streamer, "source_title": source_title, "note": note,
        "source_url": source_url, "transcript": transcript[:4200],
        "required_json": {
            "title": "one shared searchable title",
            "description": "one shared natural caption plus source credit and hashtags",
            "hashtags": ["3-4 relevant search tags"],
            "hook_text": "string", "context_card": "string", "thumbnail_text": "2-4 words",
        },
    }
    request_body = json.dumps({
        "model": ollama_model, "system": prompt_rules,
        "prompt": json.dumps(payload, ensure_ascii=False), "stream": False,
        "format": "json", "options": {"temperature": 0.62, "num_predict": 240},
    }).encode("utf-8")
    request = urllib.request.Request(
        ollama_base_url.rstrip("/") + "/api/generate", data=request_body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(3, min(8, int(timeout)))) as response:
            outer = json.loads(response.read().decode("utf-8", errors="replace"))
        raw = outer.get("response", "")
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict):
            raise ValueError("Réponse Ollama non structurée.")

        legacy_platforms = data.get("platforms") if isinstance(data.get("platforms"), dict) else {}
        youtube = legacy_platforms.get("youtube_shorts") if isinstance(legacy_platforms.get("youtube_shorts"), dict) else {}
        candidate_title = data.get("title") or youtube.get("title") or fallback["title"]
        title = _clean_line(candidate_title, 90, fallback["title"])
        generic_phrases = (
            "watch the full moment", "worth watching", "unexpected moment",
            "this moment was wild", "gta never disappoints", "you won't believe",
        )
        known_creator = _creator_name(streamer, source_title)
        promo_detected = any(term in re.sub(r"[^a-z0-9]+", " ", transcript.lower()) for term in ("youtube", "subscribe", "sub button", "like button", "hit that like"))
        invalid_title = (
            any(phrase in title.lower() for phrase in generic_phrases)
            or "gta" not in title.lower()
            or (known_creator and known_creator.lower() not in title.lower())
            or _has_incomplete_quote(title)
            or ("said" in title.lower() and not _last_complete_phrase(transcript))
            or _has_unsupported_event_claim(title, transcript, note)
            or (promo_detected and _is_formulaic_promo_copy(title))
        )
        if invalid_title:
            title = fallback["title"]

        candidate_description = data.get("description") or youtube.get("description") or fallback["description"]
        description = str(candidate_description or "").strip()
        description = "\n".join(
            line for line in description.splitlines()
            if not line.strip().lower().startswith(("clip:", "source:"))
            and not re.match(r"^#[A-Za-z0-9_]+(?:\s+#[A-Za-z0-9_]+)*$", line.strip())
        ).strip()
        if (_has_incomplete_quote(description) or _is_incomplete_phrase(description)
                or _has_unsupported_event_claim(description, transcript, note)
                or any(phrase in description.lower() for phrase in generic_phrases)
                or (promo_detected and _is_formulaic_promo_copy(description))):
            description = fallback["description"].split("\n\n")[0]
        description = _fit_caption(description, 260)

        game = _game_keyword(note, source_title, transcript)
        tags_input = data.get("hashtags") if isinstance(data.get("hashtags"), list) else youtube.get("hashtags")
        model_tags = _normalise_tags(tags_input, [], 4) if tags_input else []
        tags = []
        for tag in _default_tags(game, streamer, source_title)[:2] + model_tags + _default_tags(game, streamer, source_title)[2:]:
            if tag.lower() not in {item.lower() for item in tags}:
                tags.append(tag)
            if len(tags) >= 4:
                break
        creator = _creator_name(streamer, source_title)
        credit = f"Clip: {creator}" if creator else "Original clip"
        source_line = f"Source: {source_url.strip()}" if source_url.strip() else ""
        description = "\n".join(part for part in (description, "", credit, source_line, " ".join(tags)) if part is not None)

        hook = _limit_words(custom_hook or str(data.get("hook_text", fallback["hook_text"])), 6)
        # A manual hook is an explicit editorial choice. Validate only model-generated
        # hooks, and reject event claims that the transcript/note cannot support.
        if not custom_hook and (
            _has_incomplete_quote(f"“{hook}”")
            or _is_incomplete_phrase(hook)
            or _has_unsupported_event_claim(hook, transcript, note)
        ):
            hook = fallback["hook_text"]
        context = _limit_words(custom_context, 10)
        thumbnail_text = _limit_words(str(data.get("thumbnail_text", fallback["thumbnail_text"])), 8)
        if not thumbnail_text or _has_incomplete_quote(f"“{thumbnail_text}”") or _is_incomplete_phrase(thumbnail_text):
            thumbnail_text = fallback["thumbnail_text"]
        if invalid_title:
            hook = fallback["hook_text"]
        shared = {"title": title, "description": description, "hashtags": tags}
        platforms = {key: dict(shared) for key in PLATFORMS}
        return {
            "hook_text": hook, "context_card": context,
            "title": title, "title_variants": {key: title for key in PLATFORMS},
            "description": description, "hashtags": tags,
            "platforms": platforms, "thumbnail_text": thumbnail_text,
            "game_keyword": game,
            "transcript_excerpt": transcript[:1200], "generator": "ollama_local",
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        logger.info("Ollama indisponible ou réponse invalide : %s", exc)
    return fallback


def _has_incomplete_quote(value: str) -> bool:
    dangling = {
        "a", "an", "the", "to", "of", "and", "but", "so", "with", "for", "in", "on", "at",
        "because", "if", "when", "that", "this", "is", "are", "was", "were", "my", "your", "his", "her", "got", "has", "have", "yeah", "yea", "huh", "shit", "uh", "um",
    }
    for match in re.finditer(r"[\"“]([^\"”]{2,80})[\"”]", str(value or "")):
        words = re.findall(r"[A-Za-z0-9’']+", match.group(1).lower())
        if len(words) < 3 or (words and words[-1] in dangling):
            return True
    return False
