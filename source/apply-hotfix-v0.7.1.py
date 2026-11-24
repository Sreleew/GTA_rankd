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
        raise SystemExit(f"Patch v0.7.1 impossible : {count} occurrence(s) du bloc « {label} » dans {path}")
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


def replace_or_append_function(path: Path, name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if f"def {name}(" in text:
        replace_function(path, name, replacement)
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n\n" + replacement.rstrip() + "\n")


def ensure_function(path: Path, name: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if f"def {name}(" in text:
        replace_function(path, name, replacement)
        return
    anchor = "\ndef _fallback_metadata("
    if anchor not in text:
        raise SystemExit(f"Point d'insertion absent pour {name} dans {path}")
    text = text.replace(anchor, "\n" + replacement.rstrip() + "\n" + anchor, 1)
    path.write_text(text, encoding="utf-8")


def patch_metadata(root: Path) -> None:
    path = root / "studio/web/metadata.py"
    ensure_function(path, "_creator_name", r'''def _creator_name(streamer: str, source_title: str) -> str:
    return re.sub(r"\s+", " ", str(streamer or "")).strip()[:42]''')
    ensure_function(path, "_creator_tag", r'''def _creator_tag(streamer: str, source_title: str) -> str | None:
    value = re.sub(r"[^A-Za-z0-9_]", "", str(streamer or ""))
    if len(value) < 3 or value.lower() in {"streamer", "creator", "unknown"}:
        return None
    return "#" + value[:28]''')
    ensure_function(path, "_default_tags", r'''def _default_tags(game: str, streamer: str, source_title: str) -> list[str]:
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
    return tags[:4]''')
    ensure_function(path, "_game_keyword", r'''def _game_keyword(note: str, source_title: str, transcript: str) -> str:
    text = " ".join((str(note or ""), str(source_title or ""), str(transcript or ""))).lower()
    compact = re.sub(r"[^a-z0-9]+", " ", text)
    if any(term in compact for term in ("gta rp", "gta roleplay", "roleplay", "role play")):
        return "GTA RP"
    if any(term in compact for term in ("gta online", "gtao")):
        return "GTA Online"
    if any(term in compact for term in ("gta 5", "gta v", "grand theft auto v")):
        return "GTA 5"
    return "GTA 5"''')
    replace_function(path, "_fallback_metadata", r'''def _fallback_metadata(
    *, streamer: str, note: str, source_url: str, transcript: str,
    custom_hook: str, custom_context: str, source_title: str = "",
) -> dict[str, Any]:
    context = _limit_words(custom_context, 10)
    hook = _limit_words(custom_hook or _fallback_hook(transcript, note), 6)
    phrase = _limit_words(hook, 4) or "THE UNEXPECTED"
    game = _game_keyword(note, source_title, transcript)
    creator = _creator_name(streamer, source_title)
    title = _fit_caption((f"{creator} really said “{phrase.lower()}” in {game} 😭" if creator else f"“{phrase.lower()}” in {game} 😭"), 90)
    credit = f"Clip: {creator}" if creator else "Original clip"
    source_line = f"Source: {source_url.strip()}" if source_url.strip() else ""
    tags = _default_tags(game, streamer, source_title)
    caption = f"“{phrase.lower()}” 😭"
    description = "\n".join(part for part in (caption, "", credit, source_line, " ".join(tags)) if part is not None)
    shared = {"title": title, "description": description, "hashtags": tags}
    platforms = {key: dict(shared) for key in PLATFORMS}
    thumbnail_text = _limit_words(phrase, 4) or ("GTA RP SIDE QUEST" if game == "GTA RP" else "GTA SIDE QUEST")
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
        "transcript_excerpt": transcript[:1200],
        "generator": "local_fallback",
    }''')

    replace_function(path, "generate_short_metadata", r'''def generate_short_metadata(
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
        "You are the human editor of a fast-growing GTA/Twitch clips page. Write like a real viewer, "
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
        "creator tag when known. Thumbnail text: 2-4 punchy words, readable on a phone, not a sentence. "
        "Hook text: 3-6 words for the opening 2.6 seconds, grounded in the transcript. context_card must be empty "
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
        if (any(phrase in title.lower() for phrase in generic_phrases)
                or "gta" not in title.lower()
                or (known_creator and known_creator.lower() not in title.lower())):
            title = fallback["title"]

        candidate_description = data.get("description") or youtube.get("description") or fallback["description"]
        description = str(candidate_description or "").strip()
        description = "\n".join(
            line for line in description.splitlines()
            if not line.strip().lower().startswith(("clip:", "source:"))
            and not re.match(r"^#[A-Za-z0-9_]+(?:\s+#[A-Za-z0-9_]+)*$", line.strip())
        ).strip()
        if any(phrase in description.lower() for phrase in generic_phrases):
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
        context = _limit_words(custom_context, 10)
        thumbnail_text = _limit_words(str(data.get("thumbnail_text", fallback["thumbnail_text"])), 4)
        if not thumbnail_text:
            thumbnail_text = fallback["thumbnail_text"]
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
    return fallback''')


def patch_thumbnail(root: Path) -> None:
    path = root / "studio/web/short_editor.py"
    replace_once(
        path,
        "from PIL import Image, ImageDraw, ImageEnhance, ImageFont",
        "from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps",
        "imports Pillow pour cover éditoriale",
    )
    replace_function(path, "apply_thumbnail_overlay", r'''def apply_thumbnail_overlay(
    image_path: Path,
    text: str,
    *,
    font_path: Path | None = None,
    max_words: int = 4,
    streamer: str = "",
    game_label: str = "GTA",
) -> Path:
    if not image_path.is_file():
        raise FileNotFoundError(f"Miniature introuvable : {image_path}")

    words = _clean_ass_text(text).split()[:max_words]
    label = " ".join(words).upper() or "GTA MOMENT"
    creator = re.sub(r"\s+", " ", str(streamer or "")).strip()[:30]
    game = re.sub(r"[^A-Za-z0-9 ]", "", str(game_label or "GTA")).upper()[:18] or "GTA"
    with Image.open(image_path) as source:
        source_image = source.convert("RGB")

    width, height = 1080, 1920
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    background = ImageOps.fit(source_image, (width, height), method=resampling, centering=(0.5, 0.48))
    background = background.filter(ImageFilter.GaussianBlur(radius=28))
    background = ImageEnhance.Color(background).enhance(1.22)
    background = ImageEnhance.Brightness(background).enhance(0.36)
    background = ImageEnhance.Contrast(background).enhance(1.12).convert("RGBA")
    canvas = background
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    font_candidates: list[Path] = []
    if font_path:
        font_candidates.append(Path(font_path))
    font_candidates.extend([
        Path("C:/Windows/Fonts/impact.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ])

    def load_font(size: int):
        for candidate in font_candidates:
            if candidate.is_file():
                try:
                    return ImageFont.truetype(str(candidate), size)
                except OSError:
                    continue
        return ImageFont.load_default()

    accent = (255, 197, 42, 255)
    white = (250, 249, 244, 255)
    muted = (221, 222, 224, 230)
    margin = 58

    draw.rounded_rectangle((margin, 64, margin + 300, 132), radius=15,
                           fill=(5, 7, 10, 220), outline=(255, 197, 42, 245), width=3)
    draw.text((margin + 22, 80), "GTA RANKED", font=load_font(30), fill=white)
    series = "CLIP / GTA UNIVERSE"
    series_font = load_font(20)
    series_width = draw.textbbox((0, 0), series, font=series_font)[2]
    draw.text((width - margin - series_width, 91), series, font=series_font, fill=muted)

    kicker = f"{game}  /  STREAM MOMENT"
    draw.text((margin, 190), kicker, font=load_font(26), fill=accent)

    max_text_width = width - 2 * margin
    font_size = 106
    headline_font = load_font(font_size)

    def wrap_for_font(candidate_font) -> list[str]:
        lines: list[str] = []
        current = ""
        for token in label.split():
            trial = f"{current} {token}".strip()
            if current and draw.textbbox((0, 0), trial, font=candidate_font, stroke_width=2)[2] > max_text_width:
                lines.append(current)
                current = token
            else:
                current = trial
        if current:
            lines.append(current)
        return lines

    lines = wrap_for_font(headline_font)
    while len(lines) > 2 and font_size > 72:
        font_size -= 4
        headline_font = load_font(font_size)
        lines = wrap_for_font(headline_font)
    if len(lines) > 2:
        lines = [" ".join(lines[:-1]), lines[-1]]

    text_top = 248
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=headline_font, stroke_width=3)
        line_heights.append(bbox[3] - bbox[1])
    line_gap = 3
    total_text_height = sum(line_heights) + line_gap * max(0, len(lines) - 1)
    draw.rounded_rectangle((margin, text_top - 12, margin + 12, text_top + total_text_height + 8), radius=6, fill=accent)
    y = text_top
    for index, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=headline_font, stroke_width=3)
        line_width = bbox[2] - bbox[0]
        x = (width - line_width) // 2 - bbox[0]
        fill = accent if index == 0 else white
        draw.text((x + 4, y - bbox[1] + 8), line, font=headline_font, fill=(0, 0, 0, 235),
                  stroke_width=10, stroke_fill=(0, 0, 0, 240))
        draw.text((x, y - bbox[1]), line, font=headline_font, fill=fill,
                  stroke_width=3, stroke_fill=(5, 7, 10, 255))
        y += line_heights[index] + line_gap

    # Keep the entire source frame so the facecam and gameplay context remain visible.
    panel_x, panel_y, panel_w, panel_h = 42, 640, 996, 560
    canvas_draw = ImageDraw.Draw(canvas, "RGBA")
    canvas_draw.rounded_rectangle((panel_x - 8, panel_y - 8, panel_x + panel_w + 8, panel_y + panel_h + 8),
                                  radius=24, fill=(0, 0, 0, 220))
    gameplay = ImageOps.contain(source_image, (panel_w, panel_h), method=resampling)
    panel = Image.new("RGB", (panel_w, panel_h), (8, 10, 13))
    panel.paste(gameplay, ((panel_w - gameplay.width) // 2, (panel_h - gameplay.height) // 2))
    mask = Image.new("L", (panel_w, panel_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, panel_w - 1, panel_h - 1), radius=16, fill=255)
    canvas.paste(panel, (panel_x, panel_y), mask)
    draw = ImageDraw.Draw(overlay, "RGBA")
    draw.rounded_rectangle((panel_x - 4, panel_y - 4, panel_x + panel_w + 4, panel_y + panel_h + 4),
                           radius=21, outline=accent, width=4)
    context_y = 1250
    chip_font = load_font(29)
    game_bbox = draw.textbbox((0, 0), game, font=chip_font)
    game_w = game_bbox[2] + 50
    draw.rounded_rectangle((margin, context_y, margin + game_w, context_y + 62), radius=13,
                           fill=(255, 197, 42, 245))
    draw.text((margin + 25, context_y + 13), game, font=chip_font, fill=(8, 10, 13, 255))
    if creator:
        creator_font = load_font(28)
        creator_text = creator.upper()
        creator_w = draw.textbbox((0, 0), creator_text, font=creator_font)[2] + 48
        x = width - margin - creator_w
        draw.rounded_rectangle((x, context_y, x + creator_w, context_y + 62), radius=13,
                               fill=(5, 7, 10, 220), outline=(255, 255, 255, 90), width=2)
        draw.text((x + 24, context_y + 14), creator_text, font=creator_font, fill=white)

    footer_y = 1765
    draw.line((margin, footer_y, width - margin, footer_y), fill=(255, 255, 255, 120), width=2)
    footer_font = load_font(24)
    draw.text((margin, footer_y + 24), "@GTARANKEDSTUDIO", font=footer_font, fill=muted)
    footer_right = "GTA CLIPS"
    right_width = draw.textbbox((0, 0), footer_right, font=footer_font)[2]
    draw.text((width - margin - right_width, footer_y + 24), footer_right, font=footer_font, fill=accent)

    final_image = Image.alpha_composite(canvas, overlay).convert("RGB")
    final_image.save(image_path, format="JPEG", quality=92, optimize=True, progressive=True, subsampling=0)
    return image_path''')


def patch_renderer(root: Path) -> None:
    path = root / "studio/web/short_renderer.py"
    replace_once(
        path,
        '    seek = min(max(0.1, float(peak_timestamp)), max(0.1, output_duration - 0.1))\n',
        '    # Extract the cover from the original source frame, not the blurred 9:16 render.\n    seek = min(max(0.1, trim_start + float(peak_timestamp)), max(0.1, info["duration"] - 0.1))\n',
        "horodatage de la vraie image source",
    )
    replace_once(
        path,
        '            "-i", str(output_path.resolve()), "-frames:v", "1", "-q:v", "2", str(thumbnail_path.resolve()),\n',
        '            "-i", str(input_path.resolve()), "-frames:v", "1", "-q:v", "2", str(thumbnail_path.resolve()),\n',
        "extraction de la miniature depuis la source",
    )


def patch_worker(root: Path) -> None:
    path = root / "studio/web/worker.py"
    replace_once(
        path,
        '            platform_metadata = metadata.get("platforms", {}) if isinstance(metadata.get("platforms"), dict) else {}\n            for platform_key in ("youtube_shorts", "tiktok", "instagram"):\n                platform = platform_metadata.get(platform_key, {}) if isinstance(platform_metadata.get(platform_key), dict) else {}\n                platform_title = str(platform.get("title") or metadata.get("title", "GTA Short"))\n                platform_description = str(platform.get("description") or metadata.get("description", ""))\n                (output_dir / f"{platform_key}.txt").write_text(\n                    platform_title + "\\n\\n" + platform_description + "\\n", encoding="utf-8"\n                )\n',
        '            publication_text = str(metadata.get("title", "GTA Short")) + "\\n\\n" + str(metadata.get("description", "")) + "\\n"\n            (output_dir / "publication.txt").write_text(publication_text, encoding="utf-8")\n',
        "un seul fichier texte commun aux réseaux",
    )
    replace_once(
        path,
        '                    font_path=custom_font if custom_font.is_file() else None,\n                )',
        '                    font_path=custom_font if custom_font.is_file() else None,\n                    streamer=str(job.get("streamer", "")),\n                    game_label=str(metadata.get("game_keyword") or "GTA"),\n                )',
        "identité de la miniature liée au streamer et au jeu détecté",
    )


def patch_ui(root: Path) -> None:
    app = root / "studio/web/static/app.js"
    replace_once(
        app,
        '  const platforms = metadata.platforms || {};\n',
        '',
        "suppression des variantes plateforme côté UI",
    )
    replace_once(
        app,
        "  const title = metadata.title || job.source_title || job.streamer || (job.source_kind === 'url' ? job.source_url : 'Clip importé') || 'Clip';\n  let actions = '';",
        "  const title = metadata.title || job.source_title || job.streamer || (job.source_kind === 'url' ? job.source_url : 'Clip importé') || 'Clip';\n  const socialCaption = String(metadata.description || '').split('\\n')[0].trim();\n  let actions = '';",
        "aperçu du texte social sur la carte",
    )
    replace_once(
        app,
        '<div class="job-main"><strong title="${escapeHtml(title)}">${escapeHtml(title)}</strong><div class="job-meta">',
        """<div class="job-main"><strong title="${escapeHtml(title)}">${escapeHtml(title)}</strong>${socialCaption ? `<div class="job-caption">${escapeHtml(socialCaption)}</div>` : ''}<div class="job-meta">""",
        "affichage du premier extrait de la légende",
    )
    replace_once(
        app,
        '<button class="mini-button" data-action="copy-platform" data-platform="youtube_shorts" data-id="${job.id}">Copier YT</button><button class="mini-button" data-action="copy-platform" data-platform="tiktok" data-id="${job.id}">Copier TikTok</button><button class="mini-button" data-action="copy-platform" data-platform="instagram" data-id="${job.id}">Copier Insta</button>',
        '<button class="mini-button good" data-action="copy-social" data-id="${job.id}">Copier le post</button>',
        "un seul bouton de copie sociale",
    )
    replace_once(
        app,
        "  if (action === 'copy-platform') {\n    const job = await api(`/api/jobs/${id}`);\n    const metadata = job.metadata || {};\n    const platform = metadata.platforms?.[button.dataset.platform] || {};\n    const title = platform.title || metadata.title_variants?.[button.dataset.platform] || metadata.title || 'Titre non généré';\n    const description = platform.description || metadata.description || 'Description non générée';\n    const content = `${title}\\n\\n${description}`;\n    try { await navigator.clipboard.writeText(content); toast(`Texte ${button.dataset.platform.replace('_', ' ')} copié.`); }\n    catch { toast(content); }\n    return;\n  }",
        "  if (action === 'copy-social') {\n    const job = await api(`/api/jobs/${id}`);\n    const metadata = job.metadata || {};\n    const content = `${metadata.title || 'Titre non généré'}\\n\\n${metadata.description || 'Description non générée'}`;\n    try { await navigator.clipboard.writeText(content); toast('Texte de publication copié.'); }\n    catch { toast(content); }\n    return;\n  }",
        "action de copie sociale unifiée",
    )


def patch_tests(root: Path) -> None:
    path = root / "tests/test_metadata.py"
    replace_once(path,
        '    assert "Clip: StreamerA (https://example.test/clip)" in result["description"]',
        '    assert "Clip: StreamerA" in result["description"]\n    assert "Source: https://example.test/clip" in result["description"]',
        "crédit source séparé et lisible")
    replace_or_append_function(path, "test_metadata_fallback_uses_one_natural_shared_post_with_search_keywords", '''def test_metadata_fallback_uses_one_natural_shared_post_with_search_keywords():
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
''')
    short_editor = root / "tests/test_short_editor.py"
    replace_once(short_editor,
        "        assert result.size == (360, 640)",
        "        assert result.size == (1080, 1920)",
        "dimensions de la nouvelle miniature verticale")
    replace_once(short_editor,
        '        assert ImageChops.difference(baseline, result.convert("RGB")).getbbox() is not None',
        '        assert ImageChops.difference(baseline.resize(result.size), result.convert("RGB")).getbbox() is not None',
        "comparaison de la miniature redimensionnée")
    replace_once(short_editor,
        "        assert thumbnail.stat().st_size > 1000",
        "        assert thumbnail.stat().st_size > 10_000",
        "qualité minimale du poster JPEG")
    replace_or_append_function(short_editor, "test_thumbnail_overlay_builds_full_bleed_vertical_cover_from_landscape_gameplay", '''def test_thumbnail_overlay_builds_vertical_gta_poster_from_full_landscape_gameplay(tmp_path: Path) -> None:
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
''')
    app_js = root / "studio/web/static/app.js"
    js_text = app_js.read_text(encoding="utf-8-sig")
    if "data-action=\"copy-platform\"" in js_text or "Copier TikTok" in js_text or "Copier Insta" in js_text:
        raise SystemExit("L'interface conserve encore plusieurs boutons de copie")
    if "data-action=\"copy-social\"" not in js_text:
        raise SystemExit("Le bouton de copie unique est absent")
    styles = root / "studio/web/static/styles.css"
    css = styles.read_text(encoding="utf-8-sig")
    if ".job-caption{" not in css:
        css += "\n.job-caption{margin:5px 0 2px;color:#d5d1c2;font-size:10px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;max-width:760px}\n"
        styles.write_text(css, encoding="utf-8")


def patch_prompt(root: Path) -> None:
    prompt = root / "prompts/short_metadata.default.txt"
    prompt.write_text("""Write one natural, shared title and caption for a GTA/Twitch clips page.
Sound like a real viewer, not a marketing agency or an AI assistant. Use casual English and light Gen Z energy, but never force slang.
Lead with the actual funny, awkward, chaotic or surprising detail from the clip. Include GTA / GTA RP / GTA Online / GTA 5 and the streamer name when supported by the source.
Avoid generic filler: never write “Watch the full moment”, “This moment was wild”, “GTA never disappoints”, “POV”, “worth watching” or fake clickbait.
Do not invent a reaction, event, location, game mode or payoff. Keep the title concise and searchable. The caption should add context instead of repeating the title.
Use 3-4 relevant hashtags, including the game keyword and creator tag when known. Thumbnail text: 2-4 punchy words, readable on a phone.
Return only the JSON schema requested by the app.
""", encoding="utf-8")


def patch_release(root: Path) -> None:
    replacements = {
        "Version: 0.7.0": "Version: 0.7.1",
        'version = "0.7.0"': 'version = "0.7.1"',
        "  version: 0.7.0": "  version: 0.7.1",
    }
    for relative in ("VERSION.txt", "pyproject.toml", "config.yaml.default"):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        for old, new in replacements.items():
            if old in text:
                text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")

    for relative in ("installer/apply_update.ps1", "installer/update_from_archive.ps1", "installer/install.ps1"):
        path = root / relative
        content = path.read_text(encoding="utf-8-sig")
        anchor = "'NOTES-v0.7.0.txt', 'VERIFICATION-v0.7.0.md'"
        addition = "'NOTES-v0.7.1.txt', 'VERIFICATION-v0.7.1.md'"
        if addition not in content:
            if anchor not in content:
                raise SystemExit(f"Liste des documents de release v0.7.0 absente dans {relative}")
            content = content.replace(anchor, anchor + ", " + addition, 1)
            path.write_text(content, encoding="utf-8-sig", newline="\r\n")

    (root / "NOTES-v0.7.1.txt").write_text("""GTA Ranked Studio v0.7.1

Miniatures GTA :
- La miniature est désormais extraite d'une vraie image de la vidéo source au moment fort, et non d'une image du rendu vertical.
- Nouveau poster vertical 1080x1920 : la capture 16:9 complète est conservée dans un grand cadre de gameplay, avec un fond cinématique assombri, une headline condensée et des repères de marque.
- Le texte de miniature est limité à quatre mots pour rester lisible sur téléphone.

Texte de publication :
- Un seul titre et une seule légende partagés entre YouTube Shorts, TikTok et Instagram Reels.
- Style plus naturel et spécifique au clip, avec mots-clés GTA et streamer quand connus, argot léger sans formule artificielle.
- Suppression des phrases génériques comme « Watch the full moment ».
- Un seul bouton « Copier le post » et un seul fichier publication.txt à côté du rendu.

Performance :
- Toujours un appel Ollama maximum, timeout de 8 secondes, puis fallback local immédiat.
- La miniature utilise une extraction FFmpeg d'une seule image et un traitement Pillow, sans réencoder la vidéo.
- Les traitements Shorts et Moments forts conservent leur fonctionnement et leur bouton d'annulation.
""", encoding="utf-8")
    (root / "VERIFICATION-v0.7.1.md").write_text("""# Vérification v0.7.1

- Métadonnées générées en un seul titre et une seule légende, partagés sur les trois réseaux.
- Fallback local contenant le nom du streamer, le mot-clé GTA et les hashtags pertinents lorsque les sources le permettent.
- Un seul bouton de copie dans la carte Short.
- Miniature extraite de la source originale au temps du pic, puis composée en 1080x1920.
- Pas de seconde passe d'encodage vidéo ; une seule extraction d'image et composition Pillow.
- Un appel Ollama au maximum, timeout borné à huit secondes.
- Tests ciblés couvrant le partage du texte et la composition verticale depuis une source paysage.
""", encoding="utf-8")

    for relative in ("README.md", "docs/UPDATES.md"):
        path = root / relative
        content = path.read_text(encoding="utf-8-sig")
        content += """

## v0.7.1 : miniatures GTA et texte social plus naturel

Les miniatures sont désormais créées à partir d'une vraie image de la vidéo source au moment fort, puis composées en poster vertical 1080x1920 avec une identité GTA Ranked plus forte et sans les grands espaces vides du Short vertical. Le titre et la légende sont unifiés pour YouTube Shorts, TikTok et Instagram Reels ; un seul bouton copie l'ensemble du post. La génération locale reste limitée à un appel Ollama et huit secondes maximum, avec fallback instantané.
"""
        path.write_text(content, encoding="utf-8")
    readme = root / "README.md"
    content = readme.read_text(encoding="utf-8-sig").replace("Dernière version stable : **0.6.2**.", "Dernière version stable : **0.7.1**.")
    readme.write_text(content, encoding="utf-8")


def apply(root: Path) -> None:
    root = root.resolve()
    patch_metadata(root)
    patch_thumbnail(root)
    patch_renderer(root)
    patch_worker(root)
    patch_ui(root)
    patch_tests(root)
    patch_prompt(root)
    patch_release(root)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.7.1.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))