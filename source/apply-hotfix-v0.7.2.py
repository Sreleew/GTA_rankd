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
        raise SystemExit(f"Patch v0.7.2 impossible : {count} occurrence(s) du bloc « {label} » dans {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_function(path: Path, name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    start = text.find(f"def {name}(")
    if start < 0:
        if replacement.strip() in text:
            return
        raise SystemExit(f"Fonction introuvable : {name} dans {path}")
    next_start = text.find("\ndef ", start + 1)
    updated = text[:start] + replacement.rstrip() + "\n" + (text[next_start:] if next_start >= 0 else "")
    path.write_text(updated, encoding="utf-8")


def ensure_function(path: Path, name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if f"def {name}(" in text:
        return
    marker = "\ndef _ass_time(" if name == "select_thumbnail_timestamp" else None
    if marker and marker in text:
        text = text.replace(marker, "\n\n" + replacement.rstrip() + marker, 1)
    else:
        text += "\n\n" + replacement.rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


def insert_once(path: Path, marker: str, addition: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if addition.strip() in text:
        return
    if text.count(marker) != 1:
        raise SystemExit(f"Patch v0.7.2 impossible : ancre « {label} » absente ou ambiguë dans {path}")
    path.write_text(text.replace(marker, addition + marker, 1), encoding="utf-8")


def replace_in_function(path: Path, name: str, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    start = text.find(f"def {name}(")
    if start < 0:
        raise SystemExit(f"Fonction introuvable : {name} dans {path}")
    next_start = text.find("\ndef ", start + 1)
    end = next_start if next_start >= 0 else len(text)
    section = text[start:end]
    if section.count(old) == 0 and new in section:
        return
    if section.count(old) != 1:
        raise SystemExit(f"Patch v0.7.2 impossible : {section.count(old)} occurrence(s) du bloc « {label} » dans {name}")
    text = text[:start] + section.replace(old, new, 1) + text[end:]
    path.write_text(text, encoding="utf-8")


def patch_metadata(root: Path) -> None:
    path = root / "studio/web/metadata.py"
    ensure_function(path, "_has_incomplete_quote", r'''def _has_incomplete_quote(value: str) -> bool:
    dangling = {
        "a", "an", "the", "to", "of", "and", "but", "so", "with", "for", "in", "on", "at",
        "because", "if", "when", "that", "this", "is", "are", "was", "were", "my", "your", "his", "her",
    }
    for match in re.finditer(r"[\"“]([^\"”]{2,80})[\"”]", str(value or "")):
        words = re.findall(r"[A-Za-z0-9’']+", match.group(1).lower())
        if len(words) < 3 or (words and words[-1] in dangling):
            return True
    return False''')
    replace_function(path, "_fallback_metadata", r'''def _fallback_metadata(
    *, streamer: str, note: str, source_url: str, transcript: str,
    custom_hook: str, custom_context: str, source_title: str = "",
) -> dict[str, Any]:
    context = _limit_words(custom_context, 10)
    raw_text = re.sub(r"\s+", " ", str(transcript or "")).strip()
    compact = re.sub(r"[^a-z0-9]+", " ", raw_text.lower())
    game = _game_keyword(note, source_title, transcript)
    creator = _creator_name(streamer, source_title)
    promo_words = ("youtube", "subscribe", "sub button", "like button", "hit that like", "sub button")
    is_creator_promo = any(term in compact for term in promo_words)

    if is_creator_promo:
        title_core = f"{creator} turns a {game} encounter into a YouTube promo" if creator else f"A {game} encounter turns into a YouTube promo"
        title = _fit_caption(title_core + " 😭", 90)
        caption = "Bro really turned a random GTA interaction into a whole YouTube promo 😭"
        hook = "HIT THAT LIKE"
        thumbnail_text = "HIT THAT LIKE"
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

    # Make the local model summarise the complete clip and explicitly reject partial ASR quotes.
    old_prompt = '"You are the human editor of a fast-growing GTA/Twitch clips page. Write like a real viewer, "'
    new_prompt = '"You are the human editor of a fast-growing GTA/Twitch clips page. Read the FULL transcript and identify the main moment, not just the opening words. "\n        "The opening may be cut off or ASR may end mid-sentence; never turn an incomplete phrase into a quote or title. "\n        "If the opening is incomplete, use a later complete moment or summarise the action. "\n        "Write like a real viewer, "'
    replace_once(path, old_prompt, new_prompt, "consigne de résumé du transcript complet")

    replace_once(
        path,
        '        if (any(phrase in title.lower() for phrase in generic_phrases)\n                or "gta" not in title.lower()\n                or (known_creator and known_creator.lower() not in title.lower())):\n            title = fallback["title"]\n',
        '        invalid_title = (\n            any(phrase in title.lower() for phrase in generic_phrases)\n            or "gta" not in title.lower()\n            or (known_creator and known_creator.lower() not in title.lower())\n            or _has_incomplete_quote(title)\n        )\n        if invalid_title:\n            title = fallback["title"]\n',
        "rejet des citations tronquées dans les titres")

    replace_once(
        path,
        '        if any(phrase in description.lower() for phrase in generic_phrases):\n            description = fallback["description"].split("\\n\\n")[0]\n        description = _fit_caption(description, 260)\n',
        '        if invalid_title or any(phrase in description.lower() for phrase in generic_phrases):\n            description = fallback["description"].split("\\n\\n")[0]\n        description = _fit_caption(description, 260)\n',
        "alignement de la légende sur le fallback si le titre est tronqué")

    replace_once(
        path,
        '        hook = _limit_words(custom_hook or str(data.get("hook_text", fallback["hook_text"])), 6)\n',
        '        hook = _limit_words(custom_hook or str(data.get("hook_text", fallback["hook_text"])), 6)\n        if _has_incomplete_quote(f"“{hook}”"):\n            hook = fallback["hook_text"]\n',
        "rejet des accroches de voix tronquées",
    )

    replace_once(
        path,
        '        thumbnail_text = _limit_words(str(data.get("thumbnail_text", fallback["thumbnail_text"])), 4)\n        if not thumbnail_text:\n            thumbnail_text = fallback["thumbnail_text"]\n',
        '        thumbnail_text = _limit_words(str(data.get("thumbnail_text", fallback["thumbnail_text"])), 4)\n        if not thumbnail_text or invalid_title or _has_incomplete_quote(f"“{thumbnail_text}”"):\n            thumbnail_text = fallback["thumbnail_text"]\n        if invalid_title:\n            hook = fallback["hook_text"]\n',
        "suppression des accroches de miniature tronquées")


def patch_word_timing(root: Path) -> None:
    path = root / "studio/web/short_editor.py"
    ensure_function(path, "select_thumbnail_timestamp", r'''def select_thumbnail_timestamp(
    words: list[WordTiming], duration: float, *, preferred: float = 0.0,
) -> float:
    """Find a visually useful timestamp near the clip's most descriptive spoken moment."""
    limit = max(0.25, float(duration))
    preferred = max(0.0, min(float(preferred or 0.0), limit - 0.25))
    weights = {
        "youtube": 5.0, "subscribe": 6.0, "sub": 4.0, "button": 3.0, "like": 5.0,
        "police": 5.0, "cop": 4.0, "crash": 6.0, "explosion": 6.0, "explode": 6.0,
        "killed": 5.0, "kill": 4.0, "arrest": 5.0, "rob": 4.0, "bank": 4.0,
        "money": 3.0, "girl": 3.0, "ladies": 3.0, "npc": 3.0, "race": 4.0,
        "win": 3.0, "lost": 3.0, "wtf": 3.0, "omg": 3.0, "help": 2.0,
        "stop": 2.0, "wait": 1.0, "crazy": 2.0, "insane": 2.0,
    }
    anchors: list[tuple[float, float]] = []
    for word in words or []:
        tokens = re.findall(r"[A-Za-z0-9']+", str(word.text or "").lower())
        weight = sum(weights.get(token, 0.0) for token in tokens)
        if weight > 0:
            midpoint = (float(word.start) + float(word.end)) / 2
            anchors.append((max(0.0, min(midpoint, limit)), weight))
    if not anchors:
        return preferred

    best_score = -1.0
    best_time = preferred
    window_seconds = 7.5
    for start, _ in anchors:
        nearby = [(time, weight) for time, weight in anchors if start <= time <= start + window_seconds]
        score = sum(weight for _, weight in nearby)
        if not nearby:
            continue
        if score > best_score:
            best_score = score
            total = sum(weight for _, weight in nearby)
            best_time = sum(time * weight for time, weight in nearby) / max(total, 0.001)
    return max(0.25, min(best_time, limit - 0.25))''')


def patch_renderer(root: Path) -> None:
    path = root / "studio/web/short_renderer.py"
    replace_once(
        path,
        "import json\nimport logging\nimport shutil\nimport subprocess\n",
        "import json\nimport logging\nimport math\nimport shutil\nimport subprocess\nimport tempfile\n",
        "imports pour le sélecteur visuel de miniature",
    )
    ensure_function(path, "_thumbnail_visual_score", r'''def _thumbnail_visual_score(image_path: Path) -> float:
    """Score image detail/contrast so a blank sky or transition cannot become the cover."""
    from PIL import Image, ImageFilter, ImageStat

    with Image.open(image_path) as opened:
        image = opened.convert("RGB")
    width, height = image.size
    if width < 16 or height < 16:
        return 0.0
    # Ignore Twitch borders and HUD edges; score the central gameplay area.
    crop = image.crop((int(width * 0.15), int(height * 0.10), int(width * 0.85), int(height * 0.90)))
    resampling = getattr(Image, "Resampling", Image).BILINEAR
    crop = crop.resize((192, 108), resampling)
    gray = crop.convert("L")
    stats = ImageStat.Stat(gray)
    entropy = gray.entropy() / 8.0
    contrast = min(1.0, stats.stddev[0] / 72.0)
    edge_mean = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0] / 255.0
    edge_score = min(1.0, edge_mean / 0.18)
    saturation = ImageStat.Stat(crop.convert("HSV").getchannel("S")).mean[0] / 255.0
    brightness = stats.mean[0] / 255.0
    exposure_penalty = max(0.0, 0.18 - brightness) * 0.9 + max(0.0, brightness - 0.91) * 0.7
    return 0.42 * entropy + 0.25 * contrast + 0.23 * edge_score + 0.10 * saturation - exposure_penalty


def _extract_best_thumbnail(
    ffmpeg_bin: str, input_path: Path, thumbnail_path: Path, *,
    trim_start: float, output_duration: float, preferred_timestamp: float,
) -> float:
    """Sample a few low-resolution frames, then extract only the best one at full resolution."""
    duration = max(0.25, float(output_duration))
    base_offset = min(0.35, duration * 0.05)
    remaining = max(0.2, duration - base_offset)
    interval = min(3.0, max(1.5, duration / 12.0))
    preferred = max(0.0, min(float(preferred_timestamp or 0.0), duration - 0.25))
    with tempfile.TemporaryDirectory(prefix="gta-ranked-thumb-", dir=str(thumbnail_path.parent)) as temporary:
        temporary_dir = Path(temporary)
        pattern = temporary_dir / "candidate-%03d.jpg"
        sample_command = [
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{trim_start + base_offset:.3f}", "-i", str(input_path.resolve()),
            "-t", f"{remaining:.3f}", "-vf", f"fps=1/{interval:.3f},scale=480:-2",
            "-q:v", "5", str(pattern),
        ]
        run_command(sample_command, timeout=60)
        candidates = sorted(temporary_dir.glob("candidate-*.jpg"))
        scored: list[tuple[float, float]] = []
        for index, candidate in enumerate(candidates):
            local_time = min(duration - 0.1, base_offset + index * interval)
            visual = _thumbnail_visual_score(candidate)
            proximity = 0.12 * math.exp(-abs(local_time - preferred) / 8.0)
            scored.append((visual + proximity, local_time))
        if not scored:
            raise MediaError("FFmpeg n'a extrait aucune image candidate pour la miniature.")
        _, chosen_local_time = max(scored, key=lambda item: item[0])
        absolute_time = max(0.1, min(trim_start + chosen_local_time, trim_start + duration - 0.1))
        run_command([
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{absolute_time:.3f}",
            "-i", str(input_path.resolve()), "-frames:v", "1", "-q:v", "2", str(thumbnail_path.resolve()),
        ], timeout=30)
    return chosen_local_time''')
    replace_in_function(
        path, "render_vertical_short",
        '    peak_timestamp: float = 0.0,\n    zoom_percent: int = 0,\n',
        '    peak_timestamp: float = 0.0,\n    thumbnail_timestamp: float | None = None,\n    zoom_percent: int = 0,\n',
        "paramètre indépendant du timestamp de miniature",
    )
    replace_once(
        path,
        '    # Extract the cover from the original source frame, not the blurred 9:16 render.\n    seek = min(max(0.1, trim_start + float(peak_timestamp)), max(0.1, info["duration"] - 0.1))\n    try:\n        run_command([\n            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{seek:.3f}",\n            "-i", str(input_path.resolve()), "-frames:v", "1", "-q:v", "2", str(thumbnail_path.resolve()),\n        ], timeout=60)\n    except MediaError:\n        logger.exception("La miniature n\'a pas pu être générée. Le rendu vidéo reste disponible.")\n',
        '    # Sample the selected excerpt and avoid blank sky/transition frames for the cover.\n    preferred_thumbnail_time = peak_timestamp if thumbnail_timestamp is None else thumbnail_timestamp\n    selected_thumbnail_time: float | None = None\n    try:\n        selected_thumbnail_time = _extract_best_thumbnail(\n            ffmpeg_bin, input_path, thumbnail_path, trim_start=trim_start,\n            output_duration=output_duration, preferred_timestamp=preferred_thumbnail_time,\n        )\n    except (MediaError, OSError):\n        logger.exception("La sélection intelligente de miniature a échoué. Tentative sur le timestamp audio.")\n        seek = min(max(0.1, trim_start + float(preferred_thumbnail_time)), max(0.1, info["duration"] - 0.1))\n        try:\n            run_command([\n                ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{seek:.3f}",\n                "-i", str(input_path.resolve()), "-frames:v", "1", "-q:v", "2", str(thumbnail_path.resolve()),\n            ], timeout=30)\n            selected_thumbnail_time = max(0.0, seek - trim_start)\n        except MediaError:\n            logger.exception("La miniature n\'a pas pu être générée. Le rendu vidéo reste disponible.")\n',
        "extraction intelligente de miniature non vide")
    replace_once(
        path,
        '        "peak_timestamp": float(peak_timestamp),\n',
        '        "peak_timestamp": float(peak_timestamp),\n        "thumbnail_timestamp": (trim_start + selected_thumbnail_time) if selected_thumbnail_time is not None else None,\n',
        "timestamp réel de la miniature dans les métadonnées du rendu")


def patch_worker(root: Path) -> None:
    path = root / "studio/web/worker.py"
    replace_once(
        path,
        '    apply_thumbnail_overlay, create_ass_file, parse_srt, rebase_word_timings,\n',
        '    apply_thumbnail_overlay, create_ass_file, parse_srt, rebase_word_timings, select_thumbnail_timestamp,\n',
        "import du sélecteur de timestamp de miniature",
    )
    replace_once(
        path,
        '            render_peak_timestamp = max(0.0, peak_timestamp - trim_start)\n',
        '            render_peak_timestamp = max(0.0, peak_timestamp - trim_start)\n            render_thumbnail_timestamp = select_thumbnail_timestamp(\n                render_words, trim_end - trim_start, preferred=render_peak_timestamp\n            )\n',
        "sélection du moment le plus descriptif dans la transcription",
    )
    replace_once(
        path,
        '                peak_timestamp=render_peak_timestamp,\n                zoom_percent=int(options.get("zoom_percent", 8)),\n',
        '                peak_timestamp=render_peak_timestamp,\n                thumbnail_timestamp=render_thumbnail_timestamp,\n                zoom_percent=int(options.get("zoom_percent", 8)),\n',
        "passage du moment transcript-driven au renderer",
    )
    replace_once(
        path,
        '                "render_peak_timestamp": render_peak_timestamp,\n',
        '                "render_peak_timestamp": render_peak_timestamp,\n                "thumbnail_timestamp": result.get("thumbnail_timestamp"),\n',
        "sauvegarde du timestamp de miniature sélectionné",
    )


def patch_tests(root: Path) -> None:
    short_tests = root / "tests/test_short_editor.py"
    insert_once(
        short_tests,
        '\ndef test_long_clip_excerpt_keeps_payoff_and_context() -> None:\n',
        '''\ndef test_thumbnail_timestamp_prefers_descriptive_transcript_moment() -> None:\n    from studio.web.short_editor import select_thumbnail_timestamp\n\n    words = [\n        WordTiming(1.0, 1.2, "Oh"), WordTiming(1.2, 1.4, "I"),\n        WordTiming(1.4, 1.8, "know"), WordTiming(2.0, 2.4, "the"),\n        WordTiming(18.0, 18.4, "YouTube"), WordTiming(19.0, 19.3, "please"),\n        WordTiming(20.0, 20.4, "ladies"), WordTiming(22.0, 22.2, "guys"),\n        WordTiming(22.3, 22.5, "hit"), WordTiming(22.6, 22.8, "that"),\n        WordTiming(22.9, 23.3, "like"), WordTiming(23.4, 23.8, "button"),\n    ]\n    selected = select_thumbnail_timestamp(words, 40.0, preferred=4.0)\n    assert 18.0 <= selected <= 25.0\n\n\ndef test_thumbnail_timestamp_falls_back_to_audio_peak_without_salient_words() -> None:\n    from studio.web.short_editor import select_thumbnail_timestamp\n\n    selected = select_thumbnail_timestamp([WordTiming(1.0, 1.2, "Hello")], 20.0, preferred=8.5)\n    assert selected == 8.5\n\n''',
        "tests de sélection du moment de miniature à partir du transcript")
    meta_tests = root / "tests/test_metadata.py"
    insert_once(
        meta_tests,
        '\ndef test_custom_hook_and_context_override_fallback() -> None:\n',
        '''\ndef test_metadata_generation_rejects_the_truncated_opening_from_ishowspeed_clip() -> None:\n    result = generate_short_metadata(\n        streamer="IShowSpeed", source_title="GTA 5",\n        transcript="Oh I know the place so everybody the and sub button I YouTube so please ladies guys hit that like",\n        source_url="https://www.twitch.tv/videos/2934870795",\n        ollama_base_url="http://127.0.0.1:1", retries=0,\n    )\n    assert result["title"] == "IShowSpeed turns a GTA 5 encounter into a YouTube promo 😭"\n    assert result["thumbnail_text"] == "HIT THAT LIKE"\n    assert result["hook_text"] == "HIT THAT LIKE"\n    assert "oh i know the" not in result["title"].lower()\n\n''',
        "test de génération complète du titre IShowSpeed à partir du transcript réel",
    )
    insert_once(
        meta_tests,
        '\ndef test_custom_hook_and_context_override_fallback() -> None:\n',
        '''\ndef test_metadata_fallback_avoids_incomplete_opening_quote_and_finds_clip_angle() -> None:\n    from studio.web.metadata import _fallback_metadata, _has_incomplete_quote\n\n    result = _fallback_metadata(\n        streamer="IShowSpeed", note="", source_url="https://www.twitch.tv/videos/2934870795",\n        transcript="Oh I know the place so everybody the and sub button I YouTube so please ladies guys hit that like",\n        custom_hook="", custom_context="", source_title="GTA 5",\n    )\n    assert result["title"] == "IShowSpeed turns a GTA 5 encounter into a YouTube promo 😭"\n    assert result["thumbnail_text"] == "HIT THAT LIKE"\n    assert result["hook_text"] == "HIT THAT LIKE"\n    assert not _has_incomplete_quote(result["title"])\n    assert _has_incomplete_quote('IShowSpeed really said “oh i know the” in GTA 5 😭')\n    assert "random GTA interaction" in result["description"]\n\n''',
        "test du rejet de phrase ASR incomplète et du fallback de contexte")
    renderer_tests = root / "tests/test_render_integration.py"
    insert_once(
        renderer_tests,
        '\n@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="FFmpeg/FFprobe absent")\n',
        '''\ndef test_thumbnail_visual_score_rejects_blank_sky_frame(tmp_path: Path) -> None:\n    from PIL import Image, ImageDraw\n    from studio.web.short_renderer import _thumbnail_visual_score\n\n    blank = tmp_path / "blank.jpg"\n    detailed = tmp_path / "detailed.jpg"\n    Image.new("RGB", (640, 360), (180, 190, 195)).save(blank)\n    scene = Image.new("RGB", (640, 360), (65, 110, 75))\n    draw = ImageDraw.Draw(scene)\n    draw.rectangle((40, 150, 500, 320), fill=(220, 110, 35))\n    draw.ellipse((250, 50, 370, 280), fill=(240, 215, 170))\n    for x in range(0, 640, 30):\n        draw.line((x, 0, x + 80, 360), fill=(30, 55, 35), width=3)\n    scene.save(detailed)\n    assert _thumbnail_visual_score(detailed) > _thumbnail_visual_score(blank) + 0.15\n\n''',
        "test visuel de rejet des images quasi vides")


def patch_release(root: Path) -> None:
    for relative in ("VERSION.txt", "pyproject.toml", "config.yaml.default"):
        path = root / relative
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8-sig")
        content = content.replace("Version: 0.7.1", "Version: 0.7.2", 1)
        content = content.replace('version = "0.7.1"', 'version = "0.7.2"', 1)
        content = content.replace("version: 0.7.1", "version: 0.7.2", 1)
        path.write_text(content, encoding="utf-8")

    notes = root / "NOTES-v0.7.2.txt"
    notes.write_text("""GTA Ranked Studio v0.7.2

Miniatures :
- La sélection de la capture ne dépend plus uniquement du pic audio ; plusieurs images du segment sont évaluées rapidement en basse résolution.
- Le score privilégie une scène de gameplay nette et détaillée, pénalise les écrans vides, les ciels uniformes et les transitions, puis extrait une seule image en pleine résolution.
- Le timestamp préféré est choisi à partir des mots-clés du transcript (like, subscribe, YouTube, police, crash, etc.) et reste distinct du pic audio utilisé pour le montage.

Titres et accroches :
- L'éditeur résume maintenant le clip entier plutôt que de citer automatiquement les premiers mots.
- Les citations tronquées par Whisper ou coupées en plein milieu d'une phrase sont rejetées.
- Le fallback détecte les séquences de promotion YouTube/abonnement et produit un titre, une légende et une accroche cohérents avec le passage.

Performance :
- Un seul passage FFmpeg léger échantillonne les images en 480 px ; une seule extraction pleine résolution est conservée.
- Aucun nouvel appel Ollama ; le timeout local reste limité à huit secondes.
- Le rendu vidéo, le choix du pic audio et les options de montage restent inchangés.
""", encoding="utf-8")
    (root / "VERIFICATION-v0.7.2.md").write_text("""# Vérification v0.7.2

- Le timestamp de miniature est sélectionné à partir des mots saillants du transcript.
- Plusieurs images basse résolution sont scorées par entropie, contraste, contours et saturation pour éviter les écrans presque vides.
- Une seule image finale est extraite à pleine résolution depuis la vidéo source.
- Un titre contenant une citation incomplète est rejeté ; le fallback utilise l'angle le plus explicite détecté dans le transcript.
- Le timestamp de miniature reste distinct du pic audio utilisé pour le montage.
- Tests ciblés sur la sélection temporelle, le rejet des citations tronquées et la qualité visuelle.
""", encoding="utf-8")

    for relative in ("installer/apply_update.ps1", "installer/update_from_archive.ps1", "installer/install.ps1"):
        path = root / relative
        if path.is_file():
            content = path.read_text(encoding="utf-8-sig")
            if "'NOTES-v0.7.2.txt', 'VERIFICATION-v0.7.2.md'" not in content:
                anchor = "'NOTES-v0.7.1.txt', 'VERIFICATION-v0.7.1.md'"
                if anchor not in content:
                    raise SystemExit(f"Liste des documents v0.7.1 absente dans {relative}")
                content = content.replace(anchor, anchor + ", 'NOTES-v0.7.2.txt', 'VERIFICATION-v0.7.2.md'", 1)
                path.write_text(content, encoding="utf-8-sig", newline="\r\n")

    readme = root / "README.md"
    content = readme.read_text(encoding="utf-8-sig")
    content = content.replace("Dernière version stable : **0.7.1**.", "Dernière version stable : **0.7.2**.")
    content += "\n\n## v0.7.2 : meilleures images et titres complets\n\nLa couverture sélectionne plusieurs images du clip et retient une capture détaillée proche du moment saillant de la transcription, plutôt que le seul pic audio. Les titres et miniatures ne réutilisent plus les débuts de phrases tronqués ; le résumé s'appuie sur l'ensemble du clip.\n"
    readme.write_text(content, encoding="utf-8")


def apply(root: Path) -> None:
    root = root.resolve()
    patch_metadata(root)
    patch_word_timing(root)
    patch_renderer(root)
    patch_worker(root)
    patch_tests(root)
    patch_release(root)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.7.2.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
