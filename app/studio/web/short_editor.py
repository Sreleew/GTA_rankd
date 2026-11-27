"""Génération de sous-titres ASS et d'overlays éditoriaux pour les Shorts."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


@dataclass(frozen=True)
class WordTiming:
    start: float
    end: float
    text: str


def parse_srt(path: Path) -> list[WordTiming]:
    """Lit un SRT Whisper et récupère ses segments horodatés."""
    if not path.is_file():
        return []
    content = path.read_text(encoding="utf-8-sig", errors="replace")
    blocks = re.split(r"\r?\n\s*\r?\n", content.strip())
    result: list[WordTiming] = []
    time_pattern = re.compile(
        r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
    )
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        match = next((time_pattern.search(line) for line in lines if time_pattern.search(line)), None)
        if not match:
            continue
        text_index = next((i for i, line in enumerate(lines) if time_pattern.search(line)), -1)
        text = " ".join(lines[text_index + 1:]).strip()
        text = re.sub(r"<[^>]+>", "", text)
        if not text:
            continue
        start = _srt_time(match.group("start"))
        end = _srt_time(match.group("end"))
        if end > start:
            result.append(WordTiming(start=start, end=end, text=text))
    return result


def _srt_time(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)



def select_thumbnail_timestamp(
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
        # French reactions are common in GTA RP clips and should influence the cover too.
        "putain": 5.0, "merde": 4.0, "incroyable": 5.0, "dingue": 4.0,
        "fou": 3.0, "folle": 3.0, "impossible": 4.0, "serieux": 3.0,
        "non": 2.0, "quoi": 2.0, "attends": 2.0, "abuse": 3.0,
        "seriously": 2.0, "unreal": 4.0, "holy": 3.0, "no": 2.0,
        "way": 2.0, "bro": 1.0,
    }
    anchors: list[tuple[float, float]] = []
    for word in words or []:
        raw_text = str(word.text or "").lower()
        normalized_text = "".join(
            char for char in unicodedata.normalize("NFKD", raw_text)
            if not unicodedata.combining(char)
        )
        tokens = re.findall(r"[A-Za-z0-9']+", normalized_text)
        weight = sum(weights.get(token, 0.0) for token in tokens)
        if weight and "!" in raw_text:
            weight += 1.5
        elif weight and "?" in raw_text:
            weight += 0.75
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
    return max(0.25, min(best_time, limit - 0.25))
def _ass_time(seconds: float) -> str:
    total_cs = max(0, round(float(seconds) * 100))
    hours, remainder = divmod(total_cs, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def _clean_ass_text(value: str) -> str:
    cleaned = str(value or "").replace("\r", " ").replace("\n", " ")
    cleaned = cleaned.replace("\\", "／").replace("{", "｛").replace("}", "｝")
    return re.sub(r"\s+", " ", cleaned).strip()


def _wrap_words(value: str, max_words: int = 5) -> str:
    words = _clean_ass_text(value).split()
    if len(words) <= max_words:
        return " ".join(words)
    midpoint = min(max_words, (len(words) + 1) // 2)
    return " ".join(words[:midpoint]) + r"\N" + " ".join(words[midpoint:])


def infer_hook_style(hook_text: str, context_text: str = "") -> str:
    """Choisit une animation de hook selon la promesse éditoriale du texte."""
    hook = _clean_ass_text(hook_text).casefold()
    # The actual hook drives the treatment. Context is only a fallback when no
    # headline was produced, so a summary cannot override the editorial promise.
    source_text = hook or _clean_ass_text(context_text).casefold()
    normalized_text = "".join(
        char for char in unicodedata.normalize("NFKD", source_text)
        if not unicodedata.combining(char)
    )
    tokens = set(re.findall(r"[a-z0-9']+", normalized_text))

    question_words = {
        "why", "how", "what", "who", "where", "when", "which",
        "did", "does", "could", "would", "can", "will",
        "pourquoi", "comment", "quoi", "que", "qui", "ou", "quand",
        "est", "ce", "vraiment",
    }
    suspense_words = {
        "wait", "watch", "until", "before", "thought", "safe",
        "almost", "then", "just", "secret", "never",
        "attends", "regarde", "jusque", "avant", "croyait", "pensait",
        "presque", "ensuite", "jamais", "tranquille", "jusqu",
    }
    reaction_words = {
        "no", "way", "wtf", "omg", "holy", "damn", "crazy",
        "insane", "unreal", "nah", "bro", "wow", "sheesh",
        "incroyable", "dingue", "fou", "folle", "serieux", "impossible",
        "putain", "merde", "abuse", "non",
    }

    scores = {
        "question": (3 if "?" in hook else 0) + len(tokens & question_words),
        "suspense": len(tokens & suspense_words) * 2,
        "reaction": len(tokens & reaction_words) * 2 + (2 if "!" in hook else 0),
    }
    if re.search(r"\bno way\b|\bwhat the\b|\bholy\b", hook):
        scores["reaction"] += 2

    selected = max(scores, key=scores.get)
    return selected if scores[selected] > 0 else "impact"


_HOOK_ANIMATIONS = {
    # Fast scale-in with a controlled overshoot for a direct, high-energy payoff.
    "impact": r"\fad(25,150)\fscx142\fscy142\frz-4\blur4\t(0,140,\fscx106\fscy106\frz0\blur0)\t(140,230,\fscx100\fscy100)",
    # A smaller, calmer arrival leaves visual room for the question.
    "question": r"\fad(65,140)\fscx88\fscy88\frz-2\blur1\t(0,220,\fscx100\fscy100\frz0\blur0)",
    # Longer reveal builds anticipation without adding a separate intro.
    "suspense": r"\fad(180,120)\fscx96\fscy96\blur7\t(0,320,\fscx100\fscy100\blur0)",
    # A brief squash-and-stretch sells a genuine reaction.
    "reaction": r"\fad(20,130)\fscx78\fscy122\frz4\blur3\t(0,110,\fscx108\fscy96\frz-1\blur0)\t(110,210,\fscx100\fscy100\frz0)",
}


def _merge_punctuation(words: Iterable[WordTiming]) -> list[WordTiming]:
    output: list[WordTiming] = []
    punctuation = re.compile(r"^[,.;:!?)]")
    for word in words:
        text = _clean_ass_text(word.text)
        if not text:
            continue
        if output and (punctuation.match(text) or text.startswith("'")):
            previous = output[-1]
            output[-1] = WordTiming(previous.start, max(previous.end, word.end), previous.text + text)
        else:
            output.append(WordTiming(word.start, max(word.end, word.start + 0.04), text))
    return output


def _caption_events(words: list[WordTiming], width: int, height: int) -> list[str]:
    events: list[str] = []
    words = _merge_punctuation(words)

    # SRT fallback returns one timing per sentence/segment rather than per word.
    # Split those phrases into approximate word timings so captions stay readable
    # and the active-word treatment does not highlight an entire sentence.
    expanded: list[WordTiming] = []
    for item in words:
        parts = item.text.split()
        if len(parts) <= 1:
            expanded.append(item)
            continue
        weights = [max(1, len(part.strip(".,!?;:"))) for part in parts]
        total_weight = sum(weights)
        duration = max(0.04, item.end - item.start)
        cursor = item.start
        for part_index, (part, weight) in enumerate(zip(parts, weights)):
            next_cursor = (
                item.end if part_index == len(parts) - 1
                else cursor + duration * weight / total_weight
            )
            expanded.append(WordTiming(cursor, max(cursor + 0.04, next_cursor), part))
            cursor = next_cursor
    words = expanded

    groups: list[list[WordTiming]] = []
    current: list[WordTiming] = []
    for word in words:
        pause = word.start - current[-1].end if current else 0.0
        previous_text = current[-1].text.rstrip('"”’)]}') if current else ""
        sentence_finished = bool(previous_text) and previous_text[-1] in ".!?"
        if current and (len(current) >= 4 or pause > 0.55 or sentence_finished):
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)

    y = int(height * 0.79)
    x = width // 2
    for group in groups:
        for index, active in enumerate(group):
            next_word = group[index + 1] if index + 1 < len(group) else None
            end = next_word.start if next_word and next_word.start > active.start else active.end
            end = max(active.start + 0.06, min(end, active.end + 0.8 if next_word is None else end))
            caption_lines: list[list[str]] = [[]]
            line_length = 0
            max_line_chars = 16
            for word_index, word in enumerate(group):
                text = _clean_ass_text(word.text).upper()
                highlighted = (
                    r"{\c&H0000C8F5&\fscx106\fscy106\bord7}" + text
                    + r"{\c&H00FFFFFF&\fscx100\fscy100\bord6}"
                    if word_index == index else text
                )
                plain_length = len(text)
                required = plain_length + (1 if caption_lines[-1] else 0)
                if caption_lines[-1] and line_length + required > max_line_chars:
                    caption_lines.append([])
                    line_length = 0
                caption_lines[-1].append(highlighted)
                line_length += plain_length + (1 if len(caption_lines[-1]) > 1 else 0)
            line = r"\N".join(" ".join(parts) for parts in caption_lines)
            start_stamp = _ass_time(active.start)
            end_stamp = _ass_time(end)
            events.append(
                f"Dialogue: 0,{start_stamp},{end_stamp},Caption,,0,0,0,,{{\\an2\\pos({x},{y})\\fad(45,65)}}{line}"
            )
    return events


def create_ass_file(
    output_path: Path,
    *,
    words: list[WordTiming] | None = None,
    hook_text: str = "",
    context_text: str = "",
    handle: str = "@GTARankedStudio",
    badge_text: str = "GTA VI",
    width: int = 1080,
    height: int = 1920,
    font_name: str = "Arial",
    captions_enabled: bool = True,
    brand_enabled: bool = True,
    layout: str = "blur",
    hook_style: str = "auto",
) -> Path:
    """Crée une piste ASS avec hook animé, contexte, branding et captions mot à mot."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font = _clean_ass_text(font_name) or "Arial"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Caption,{font},68,&H00FFFFFF,&H0000C8F5,&H00050910,&HCC050910,-1,0,0,0,100,100,0,0,1,6,3,2,64,64,285,1
Style: Hook,{font},86,&H0000C8F5,&H00FFFFFF,&H00050910,&HCC050910,-1,0,0,0,100,100,1,0,1,7,3,8,70,70,330,1
Style: HookKicker,{font},24,&H00E0DFFF,&H00E0DFFF,&H00050910,&HCC050910,-1,0,0,0,100,100,2,0,1,4,2,8,70,70,455,1
Style: Context,{font},31,&H00FFFFFF,&H00FFFFFF,&H00050910,&HCC050910,-1,0,0,0,100,100,0,0,1,4,2,8,80,80,475,1
Style: Brand,{font},25,&H00FFFFFF,&H00FFFFFF,&H00050910,&HCC050910,-1,0,0,0,100,100,1,0,1,4,2,7,55,55,82,1
Style: Handle,{font},23,&H00FFFFFF,&H00FFFFFF,&H00050910,&HCC050910,-1,0,0,0,100,100,0,0,1,3,2,9,55,55,82,1
Style: Kicker,{font},24,&H00E8F4F4,&H00E8F4F4,&H00050910,&HCC050910,-1,0,0,0,100,100,2,0,1,4,2,8,70,70,455,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events: list[str] = []
    if brand_enabled:
        events.append(
            f"Dialogue: 3,0:00:00.00,9:59:59.99,Brand,,0,0,0,,{{\\an7\\pos(65,90)}}GR  //  {_clean_ass_text(badge_text)}"
        )
        events.append(
            f"Dialogue: 3,0:00:00.00,9:59:59.99,Handle,,0,0,0,,{{\\an9\\pos({width - 65},90)}}{_clean_ass_text(handle)}"
        )
    clean_hook = _clean_ass_text(hook_text)
    if clean_hook:
        # A compact editorial kicker establishes the series identity without
        # delaying the clip. The headline then lands with a short overshoot,
        # like a broadcast title card rather than a static subtitle.
        kicker = f"RANKED DISPATCH  //  {_clean_ass_text(badge_text).upper()}"
        events.append(
            f"Dialogue: 2,0:00:00.00,0:00:02.60,HookKicker,,0,0,0,,"
            f"{{\\an8\\pos({width // 2},{int(height * 0.155)})\\fad(65,120)\\fscx78\\fscy78\\t(0,180,\\fscx100\\fscy100)}}{kicker}"
        )
        selected_hook_style = str(hook_style or "auto").strip().lower()
        if selected_hook_style == "auto" or selected_hook_style not in _HOOK_ANIMATIONS:
            selected_hook_style = infer_hook_style(clean_hook, context_text)
        motion = _HOOK_ANIMATIONS[selected_hook_style]
        events.append(
            f"Dialogue: 2,0:00:00.00,0:00:02.60,Hook,,0,0,0,,"
            f"{{\\an8\\pos({width // 2},{int(height * 0.20)}){motion}}}{_wrap_words(clean_hook, 5)}"
        )
    clean_context = _clean_ass_text(context_text)
    if clean_context:
        events.append(
            f"Dialogue: 2,0:00:00.35,0:00:03.50,Context,,0,0,0,,{{\\an8\\pos({width // 2},{int(height * 0.29)})}}{_wrap_words(clean_context, 7)}"
        )
    if captions_enabled and words:
        caption_events = _caption_events(words, width, height)
        if layout == "smart":
            # Keep subtitles in the dedicated lower safe area, below gameplay.
            caption_events = [
                event.replace(f"\\pos({width // 2},{int(height * 0.79)})",
                              f"\\pos({width // 2},{int(height * 0.87)})")
                for event in caption_events
            ]
        events.extend(caption_events)

    output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    return output_path


def _thumbnail_headline(text: str, streamer: str = "", *, max_words: int = 4) -> str:
    """Keep only a short, meaningful hook; never use creator/game boilerplate."""
    raw_words = _clean_ass_text(text).split()
    limit = max(1, int(max_words))
    words = raw_words[:limit]
    incomplete_endings = {
        "a", "an", "and", "are", "as", "at", "because", "but", "by", "for",
        "from", "got", "had", "has", "have", "he", "her", "him", "his",
        "i", "if", "in", "is", "it", "me", "my", "of", "on", "or", "our",
        "she", "so", "that", "the", "their", "them", "then", "there", "they",
        "this", "to", "was", "we", "were", "with", "you", "your",
        "yeah", "yea", "huh", "shit", "uh", "um", "like",
    }
    if words and words[-1].strip(".,!?;:").lower() in incomplete_endings and len(raw_words) > len(words):
        words = raw_words[-limit:]

    def normalise_token(value: str) -> str:
        token = re.sub(r"[^a-z0-9]+", "", value.casefold())
        return token[:-1] if value.casefold().endswith("'s") else token

    creator_tokens = {
        normalise_token(token)
        for token in re.split(r"[\s_]+", str(streamer or "").strip())
        if normalise_token(token)
    }
    boilerplate = {"gta", "gtav", "gtavi", "5", "v", "vi", "moment", "moments", "clip", "clips"}
    filler_openers = {"yeah", "yea", "huh", "uh", "um", "bro", "man", "shit", "like"}
    while len(words) > 1 and normalise_token(words[0]) in filler_openers:
        words = words[1:]
    meaningful = [
        word for word in words
        if normalise_token(word) not in creator_tokens | boilerplate
    ]
    while meaningful and normalise_token(meaningful[0]) in filler_openers:
        meaningful.pop(0)
    if (not meaningful or normalise_token(meaningful[-1]) in incomplete_endings
            or all(normalise_token(word) in filler_openers for word in meaningful)):
        return "WAIT FOR THE REACTION"
    return " ".join(meaningful).upper()


def _thumbnail_scene_frame(source: Image.Image) -> Image.Image:
    """Remove inactive letterbox areas from an already-vertical Short frame."""
    if source.width / max(1, source.height) >= 0.82:
        return source.copy()

    gray = source.convert("L")
    pixels = gray.load()
    step_x = max(1, source.width // 100)
    scores: list[float] = []
    for y in range(source.height):
        row = [pixels[x, y] for x in range(0, source.width, step_x)]
        if not row:
            scores.append(0.0)
            continue
        mean = sum(row) / len(row)
        variance = sum((value - mean) ** 2 for value in row) / len(row)
        scores.append(variance ** 0.5 if mean > 12 else 0.0)

    active = [score > 17 for score in scores]
    runs: list[tuple[int, int]] = []
    run_start = None
    for index, is_active in enumerate(active + [False]):
        if is_active and run_start is None:
            run_start = index
        elif not is_active and run_start is not None:
            runs.append((run_start, index))
            run_start = None
    if not runs:
        return source.copy()
    top, bottom = max(runs, key=lambda run: run[1] - run[0])
    if bottom - top < source.height * 0.28:
        return source.copy()
    padding = int((bottom - top) * 0.018)
    top = max(0, top - padding)
    bottom = min(source.height, bottom + padding)
    return source.crop((0, top, source.width, bottom))


def _thumbnail_webcam_crop(frame: Image.Image) -> tuple[Image.Image | None, str | None]:
    """Find a likely facecam in a screen corner using a conservative skin-tone cue."""
    width, height = frame.size
    crop_width = max(1, round(width * 0.38))
    crop_height = max(1, round(height * 0.48))
    candidates = {
        "top-left": (0, 0, crop_width, crop_height),
        "top-right": (width - crop_width, 0, width, crop_height),
        "bottom-left": (0, height - crop_height, crop_width, height),
        "bottom-right": (width - crop_width, height - crop_height, width, height),
    }
    best: tuple[float, Image.Image, str] | None = None
    for corner, box in candidates.items():
        region = frame.crop(box)
        hsv = region.convert("HSV").resize((72, 72))
        data = list(hsv.getdata())
        xs: list[int] = []
        ys: list[int] = []
        count = 0
        for index, (hue, saturation, value) in enumerate(data):
            skin_hue = hue <= 28 or hue >= 246
            if skin_hue and 20 <= saturation <= 175 and 65 <= value <= 245:
                count += 1
                xs.append(index % region.width)
                ys.append(index // region.width)
        if count < max(65, int(72 * 72 * 0.022)):
            continue
        box_width = max(xs) - min(xs) + 1
        box_height = max(ys) - min(ys) + 1
        # A face-like patch should occupy a coherent part of the corner region.
        if box_width < 72 * 0.14 or box_height < 72 * 0.14:
            continue
        score = count / max(1, region.width * region.height)
        if best is None or score > best[0]:
            best = (score, region, corner)
    if best is None:
        return None, None
    return best[1], best[2]


def apply_thumbnail_overlay(
    image_path: Path,
    text: str,
    *,
    font_path: Path | None = None,
    max_words: int = 4,
    streamer: str = "",
    game_label: str = "GTA",
) -> Path:
    """Build a compact GTA paper-collage cover from the real clip frame."""
    if not image_path.is_file():
        raise FileNotFoundError(f"Miniature introuvable : {image_path}")

    creator = re.sub(r"\s+", " ", str(streamer or "")).strip()[:30]
    label = _thumbnail_headline(text, creator, max_words=max_words)

    with Image.open(image_path) as source:
        source_image = source.convert("RGB")
    scene = _thumbnail_scene_frame(source_image)

    width, height = 1080, 1920
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    background = ImageOps.fit(
        source_image, (width, height), method=resampling, centering=(0.5, 0.45),
    ).filter(ImageFilter.GaussianBlur(radius=48))
    background = ImageEnhance.Color(background).enhance(0.72)
    background = ImageEnhance.Brightness(background).enhance(0.43)
    canvas = background.convert("RGBA")

    font_candidates: list[Path] = []
    if font_path:
        font_candidates.append(Path(font_path))
    font_candidates.extend([
        Path("C:/Windows/Fonts/Anton-Regular.ttf"),
        Path("C:/Windows/Fonts/impact.ttf"),
        Path("C:/Windows/Fonts/arialbi.ttf"),
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

    accent = (245, 196, 0, 255)
    paper = (11, 12, 14, 248)
    white = (249, 246, 235, 255)

    # Keep the authentic Twitch frame. If a likely facecam is already embedded
    # in a corner, give it the visual emphasis from the approved cover direction.
    facecam, corner = _thumbnail_webcam_crop(scene)
    top_image = facecam if facecam is not None else scene
    top_image = ImageOps.fit(top_image, (width, 760), method=resampling, centering=(0.5, 0.42))
    top_image = ImageEnhance.Contrast(top_image).enhance(1.06)
    canvas.alpha_composite(top_image.convert("RGBA"), (0, 72))

    gameplay = scene
    if corner in {"top-left", "bottom-left"} and scene.width > 4:
        gameplay = scene.crop((round(scene.width * 0.38), 0, scene.width, scene.height))
    elif corner in {"top-right", "bottom-right"} and scene.width > 4:
        gameplay = scene.crop((0, 0, round(scene.width * 0.62), scene.height))
    gameplay = ImageOps.fit(gameplay, (width, 610), method=resampling, centering=(0.5, 0.54))
    gameplay = ImageEnhance.Contrast(gameplay).enhance(1.05)
    canvas.alpha_composite(gameplay.convert("RGBA"), (0, 1220))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    if creator:
        draw.text((48, 26), creator.upper(), font=load_font(34), fill=white,
                  stroke_width=3, stroke_fill=(0, 0, 0, 200))

    # Short torn-paper strip that joins the face and gameplay images.
    paper_top, paper_bottom = 765, 1248
    top_edge = [(-20, 18), (160, 6), (340, 15), (540, 3), (760, 17), (940, 5), (1100, 15)]
    bottom_edge = [(-20, 10), (175, 2), (360, 13), (565, 4), (760, 14), (950, 3), (1100, 11)]
    draw.polygon(
        [(x, paper_top + y) for x, y in top_edge]
        + [(x, paper_bottom + y) for x, y in reversed(bottom_edge)],
        fill=paper,
    )
    torn = (249, 246, 235, 225)
    draw.line([(x, paper_top + y) for x, y in top_edge], fill=torn, width=4)
    draw.line([(x, paper_bottom + y) for x, y in bottom_edge], fill=torn, width=4)

    words = label.split()
    if len(words) > 1:
        split_at = (len(words) + 1) // 2
        lines = [" ".join(words[:split_at]), " ".join(words[split_at:])]
    else:
        lines = [label]

    font_size = 132
    headline_font = load_font(font_size)
    while font_size > 68:
        headline_font = load_font(font_size)
        widths = [draw.textbbox((0, 0), line, font=headline_font)[2] for line in lines]
        if max(widths, default=0) <= width - 116:
            break
        font_size -= 4
    line_height = font_size + 8
    first_y = 832
    second_y = first_y + line_height + 28
    if len(lines) == 2:
        marker_y = second_y - 8
        draw.polygon(
            [(45, marker_y + 8), (220, marker_y), (410, marker_y + 7),
             (615, marker_y - 2), (830, marker_y + 8), (1035, marker_y),
             (1028, marker_y + line_height + 18), (820, marker_y + line_height + 10),
             (610, marker_y + line_height + 20), (405, marker_y + line_height + 10),
             (215, marker_y + line_height + 16), (52, marker_y + line_height + 8)],
            fill=accent,
        )
    else:
        marker_y = first_y - 2
        draw.polygon(
            [(50, marker_y + 5), (260, marker_y - 4), (480, marker_y + 4),
             (710, marker_y - 2), (1030, marker_y + 5),
             (1026, marker_y + line_height + 14), (800, marker_y + line_height + 7),
             (580, marker_y + line_height + 16), (350, marker_y + line_height + 8),
             (55, marker_y + line_height + 14)], fill=accent,
        )

    for index, line in enumerate(lines):
        bounds = draw.textbbox((0, 0), line, font=headline_font)
        line_width = bounds[2] - bounds[0]
        x = (width - line_width) // 2 - bounds[0]
        y = first_y if index == 0 else second_y
        fill = white if len(lines) == 2 and index == 0 else (9, 10, 12, 255)
        draw.text((x + 2, y + 5 - bounds[1]), line, font=headline_font,
                  fill=(0, 0, 0, 180), stroke_width=4, stroke_fill=(0, 0, 0, 190))
        draw.text((x, y - bounds[1]), line, font=headline_font, fill=fill)

    channel_text = "GTA_Rankd"
    channel_font = load_font(29)
    channel_box = draw.textbbox((0, 0), channel_text, font=channel_font)
    channel_width = channel_box[2] - channel_box[0]
    draw.text((width - 48 - channel_width, 1842 - channel_box[1]), channel_text,
              font=channel_font, fill=white, stroke_width=2, stroke_fill=(0, 0, 0, 180))

    final_image = Image.alpha_composite(canvas, overlay).convert("RGB")
    temporary_path = image_path.with_name(f"{image_path.stem}.overlay.tmp.jpg")
    try:
        final_image.save(temporary_path, format="JPEG", quality=96, optimize=True, progressive=True, subsampling=0)
        temporary_path.replace(image_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return image_path

def select_excerpt_range(
    duration: float,
    peak_timestamp: float,
    words: list[WordTiming] | None = None,
    *,
    threshold_seconds: float = 45.0,
    lead_seconds: float = 1.5,
    tail_seconds: float = 2.0,
    minimum_seconds: float = 15.0,
    maximum_seconds: float = 45.0,
) -> tuple[float, float]:
    """Select a payoff-centred excerpt while respecting spoken phrase boundaries.

    Long clips are trimmed around the audio peak. When word timings are available,
    the beginning prefers a sentence or natural-pause boundary before the peak and
    the end prefers the first completed phrase after it. Clips shorter than the
    threshold are preserved in full.
    """
    duration = max(0.0, float(duration))
    if duration <= 0:
        return 0.0, 0.0
    threshold_seconds = max(0.0, float(threshold_seconds))
    if duration <= threshold_seconds:
        return 0.0, duration

    peak = max(0.0, min(float(peak_timestamp), duration))
    lead_seconds = max(0.0, float(lead_seconds))
    tail_seconds = max(0.0, float(tail_seconds))
    minimum_seconds = max(0.0, float(minimum_seconds))
    maximum_seconds = max(minimum_seconds, float(maximum_seconds))
    latest_start = max(0.0, peak - lead_seconds)
    start = latest_start

    ordered = sorted(words or [], key=lambda item: (item.start, item.end))
    punctuation = re.compile(r"""[.!?]["')\]]*$""")
    sentence_starts: list[float] = []
    lookback_seconds = min(maximum_seconds, 24.0)
    earliest_start = max(0.0, peak - max(lead_seconds, lookback_seconds))

    for index, item in enumerate(ordered):
        item_start = max(0.0, float(item.start))
        if item_start < earliest_start or item_start > latest_start:
            continue
        if index == 0:
            sentence_starts.append(item_start)
            continue
        previous = ordered[index - 1]
        previous_text = _clean_ass_text(previous.text)
        pause_before = item_start - float(previous.end)
        if punctuation.search(previous_text) or pause_before >= 0.75:
            sentence_starts.append(item_start)

    # Prefer the latest complete sentence/pause boundary that still leaves
    # enough lead-in to understand the reaction.
    if sentence_starts:
        start = max(sentence_starts)

    # A loud sound is not always the payoff: the streamer's verbal reaction
    # can happen a few seconds later. When transcript cues exist, keep the
    # complete reaction and then stop at its next phrase boundary.
    reaction_cues = {
        "bro", "bruh", "no", "what", "wow", "whoa", "holy", "shit", "fuck",
        "damn", "crazy", "insane", "run", "dead", "killed", "kill", "shoot",
        "police", "help", "oh", "god", "wait", "yo", "nah", "clutch", "nice",
        "wtf", "omg", "sick", "actually", "seriously", "impossible",
    }
    reaction_words = [
        item for item in ordered
        if peak - 2.0 <= float(item.start) <= peak + 14.0
        and any(token in reaction_cues for token in re.findall(r"[a-z']+", item.text.lower()))
    ]
    reaction_end = max((float(item.end) for item in reaction_words), default=None)

    end_after_payoff: float | None = None
    after_peak = [item for item in ordered if float(item.end) >= peak]
    if after_peak:
        # If a reaction is detected, ignore pauses before its final cue. This
        # prevents cutting on the impact sound before the streamer reacts.
        boundary_floor = reaction_end if reaction_end is not None else peak
        for index, item in enumerate(after_peak):
            if float(item.end) < boundary_floor:
                continue
            clean = _clean_ass_text(item.text)
            next_item = after_peak[index + 1] if index + 1 < len(after_peak) else None
            pause_after = float(next_item.start) - float(item.end) if next_item else 0.0
            if punctuation.search(clean) or pause_after >= 0.75:
                end_after_payoff = float(item.end)
                break
        if end_after_payoff is None:
            nearby = [item for item in after_peak if float(item.start) <= max(peak + 10.0, (reaction_end or peak) + 4.0)]
            if nearby:
                end_after_payoff = float(nearby[-1].end)

    if end_after_payoff is None:
        end_after_payoff = max(peak + 12.0, (reaction_end or peak) + 1.0)
    end = min(duration, max(peak + 2.0, end_after_payoff + tail_seconds))

    # If the selected payoff is short, expand backwards to a prior sentence
    # boundary when one can satisfy the minimum duration. Otherwise use a
    # deterministic time fallback rather than producing an unusably short clip.
    if end - start < minimum_seconds:
        desired_start = max(0.0, end - minimum_seconds)
        eligible = [boundary for boundary in sentence_starts if boundary <= desired_start]
        start = max(eligible) if eligible else min(start, desired_start)
        if end - start < minimum_seconds:
            start = max(0.0, end - minimum_seconds)

    # Enforce the maximum duration, preferring a later natural boundary when
    # available so the clip does not begin in the middle of a spoken sentence.
    if end - start > maximum_seconds:
        earliest_allowed = max(0.0, end - maximum_seconds)
        eligible = [
            boundary for boundary in sentence_starts
            if earliest_allowed <= boundary <= latest_start
        ]
        start = max(eligible) if eligible else max(start, earliest_allowed)
        if end - start > maximum_seconds:
            start = max(0.0, end - maximum_seconds)

    start = max(0.0, min(start, duration))
    end = max(start, min(end, duration))
    return round(start, 3), round(end, 3)

def rebase_word_timings(words: list[WordTiming], trim_start: float, trim_end: float) -> list[WordTiming]:
    """Garde les mots dans la coupe et ramène leurs horodatages à zéro."""
    result: list[WordTiming] = []
    for word in words:
        if word.end <= trim_start or word.start >= trim_end:
            continue
        start = round(max(0.0, word.start - trim_start), 3)
        end = round(max(start + 0.04, min(trim_end, word.end) - trim_start), 3)
        result.append(WordTiming(start, end, word.text))
    return result


def _format_srt_time(seconds: float) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def write_srt_file(output_path: Path, words: list[WordTiming]) -> Path:
    """Écrit un SRT en conservant les timestamps mot à mot."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for index, word in enumerate(words, start=1):
        start = max(0.0, word.start)
        end = max(start + 0.04, word.end)
        blocks.append(
            f"{index}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{_clean_ass_text(word.text)}"
        )
    output_path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    return output_path
