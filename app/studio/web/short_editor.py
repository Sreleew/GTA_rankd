"""Génération de sous-titres ASS et d'overlays éditoriaux pour les Shorts."""

from __future__ import annotations

import re
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
        if current and (len(current) >= 4 or pause > 0.55):
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
                    r"{\c&H0000C8F5&}" + text + r"{\c&H00FFFFFF&}"
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
                f"Dialogue: 0,{start_stamp},{end_stamp},Caption,,0,0,0,,{{\\an2\\pos({x},{y})}}{line}"
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
) -> Path:
    """Crée une piste ASS avec hook, contexte, branding et captions mot à mot."""
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
Style: Caption,{font},66,&H00FFFFFF,&H0000C8F5,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,70,70,300,1
Style: Hook,{font},78,&H0000C8F5,&H00FFFFFF,&H00101010,&H90000000,-1,0,0,0,100,100,1,0,1,5,2,8,75,75,340,1
Style: Context,{font},34,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,-1,0,0,0,100,100,0,0,1,3,1,8,80,80,490,1
Style: Brand,{font},27,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,7,55,55,90,1
Style: Handle,{font},25,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,9,55,55,90,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events: list[str] = []
    if brand_enabled:
        events.append(
            f"Dialogue: 3,0:00:00.00,9:59:59.99,Brand,,0,0,0,,{{\\an7\\pos(65,90)}}{_clean_ass_text(badge_text)}"
        )
        events.append(
            f"Dialogue: 3,0:00:00.00,9:59:59.99,Handle,,0,0,0,,{{\\an9\\pos({width - 65},90)}}{_clean_ass_text(handle)}"
        )
    clean_hook = _clean_ass_text(hook_text)
    if clean_hook:
        events.append(
            f"Dialogue: 2,0:00:00.00,0:00:02.60,Hook,,0,0,0,,{{\\an8\\pos({width // 2},{int(height * 0.20)})}}{_wrap_words(clean_hook, 5)}"
        )
    clean_context = _clean_ass_text(context_text)
    if clean_context:
        events.append(
            f"Dialogue: 2,0:00:00.35,0:00:03.50,Context,,0,0,0,,{{\\an8\\pos({width // 2},{int(height * 0.29)})}}{_wrap_words(clean_context, 7)}"
        )
    if captions_enabled and words:
        events.extend(_caption_events(words, width, height))

    output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    return output_path


def apply_thumbnail_overlay(
    image_path: Path,
    text: str,
    *,
    font_path: Path | None = None,
    max_words: int = 4,
    streamer: str = "",
    game_label: str = "GTA",
) -> Path:
    """Create a clean, high-contrast 9:16 cover built around the actual clip frame."""
    if not image_path.is_file():
        raise FileNotFoundError(f"Miniature introuvable : {image_path}")

    creator = re.sub(r"\s+", " ", str(streamer or "")).strip()[:30]
    game = re.sub(r"[^A-Za-z0-9 ]", "", str(game_label or "GTA")).upper()[:18] or "GTA"
    words = _clean_ass_text(text).split()[:max_words]
    incomplete_endings = {
        "a", "an", "and", "are", "as", "at", "because", "but", "by", "for",
        "from", "got", "had", "has", "have", "he", "her", "him", "his",
        "i", "if", "in", "is", "it", "me", "my", "of", "on", "or", "our",
        "she", "so", "that", "the", "their", "them", "then", "there", "they",
        "this", "to", "was", "we", "were", "with", "you", "your",
    }
    if not words or words[-1].strip(".,!?;:").lower() in incomplete_endings:
        label = f"{creator.split()[0]} GTA MOMENT" if creator else "GTA MOMENT"
    else:
        label = " ".join(words).upper()

    with Image.open(image_path) as source:
        source_image = source.convert("RGB")

    width, height = 1080, 1920
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    background = ImageOps.fit(source_image, (width, height), method=resampling, centering=(0.5, 0.48))
    background = background.filter(ImageFilter.GaussianBlur(radius=42))
    background = ImageEnhance.Color(background).enhance(1.12)
    background = ImageEnhance.Brightness(background).enhance(0.24)
    canvas = background.convert("RGBA")

    # A subtle vertical veil keeps the blurred image atmospheric without competing
    # with the actual gameplay frame or the headline.
    shade = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade, "RGBA")
    for y in range(height):
        progress = y / max(1, height - 1)
        alpha = int(72 + 92 * abs(progress - 0.48))
        shade_draw.line((0, y, width, y), fill=(3, 5, 8, alpha))
    canvas = Image.alpha_composite(canvas, shade)

    font_candidates: list[Path] = []
    if font_path:
        font_candidates.append(Path(font_path))
    font_candidates.extend([
        Path("C:/Windows/Fonts/Anton-Regular.ttf"),
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
    muted = (205, 210, 216, 230)
    margin = 52
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    # Minimal brand header.
    draw.rounded_rectangle((margin, 86, margin + 64, 150), radius=16, fill=accent)
    mark_font = load_font(34)
    mark = "GR"
    mark_box = draw.textbbox((0, 0), mark, font=mark_font)
    draw.text((margin + (64 - (mark_box[2] - mark_box[0])) / 2, 96 - mark_box[1]),
              mark, font=mark_font, fill=(8, 10, 13, 255))
    brand_font = load_font(32)
    draw.text((margin + 82, 99), "GTA RANKED", font=brand_font, fill=white)
    game_font = load_font(23)
    game_text = game.upper()
    game_box = draw.textbbox((0, 0), game_text, font=game_font)
    game_width = game_box[2] - game_box[0] + 34
    draw.rounded_rectangle((width - margin - game_width, 96, width - margin, 146),
                           radius=14, fill=(9, 12, 16, 190), outline=(255, 255, 255, 70), width=2)
    draw.text((width - margin - game_width + 17, 108 - game_box[1]), game_text,
              font=game_font, fill=muted)

    # The gameplay is the hero. Keep the full 16:9 frame visible so the streamer
    # webcam and the surrounding game context are not cropped away.
    panel_x, panel_y, panel_w, panel_h = 38, 390, 1004, 650
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow, "RGBA")
    shadow_draw.rounded_rectangle((panel_x - 10, panel_y + 14, panel_x + panel_w + 10, panel_y + panel_h + 14),
                                  radius=32, fill=(0, 0, 0, 190))
    canvas = Image.alpha_composite(canvas, shadow)

    gameplay = ImageOps.contain(source_image, (panel_w - 20, panel_h - 20), method=resampling)
    panel = Image.new("RGB", (panel_w, panel_h), (8, 10, 13))
    panel.paste(gameplay, ((panel_w - gameplay.width) // 2, (panel_h - gameplay.height) // 2))
    mask = Image.new("L", (panel_w, panel_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, panel_w - 1, panel_h - 1), radius=27, fill=255)
    canvas.paste(panel, (panel_x, panel_y), mask)
    draw = ImageDraw.Draw(overlay, "RGBA")
    draw.rounded_rectangle((panel_x, panel_y, panel_x + panel_w, panel_y + panel_h),
                           radius=27, outline=accent, width=4)
    draw.rounded_rectangle((panel_x + 22, panel_y + 20, panel_x + 190, panel_y + 66),
                           radius=13, fill=(8, 10, 13, 205))
    tag_font = load_font(20)
    draw.text((panel_x + 38, panel_y + 30), "THE CLIP", font=tag_font, fill=white)

    # Editorial headline: short, complete and readable at phone size.
    title_top = 1130
    kicker_font = load_font(24)
    draw.rounded_rectangle((margin, title_top - 36, margin + 8, title_top - 5), radius=4, fill=accent)
    draw.text((margin + 24, title_top - 38), "THE MOMENT", font=kicker_font, fill=accent)

    def wrap_headline(candidate_font) -> list[str]:
        lines: list[str] = []
        current = ""
        for token in label.split():
            trial = f"{current} {token}".strip()
            box = draw.textbbox((0, 0), trial, font=candidate_font, stroke_width=1)
            if current and box[2] - box[0] > width - 2 * margin:
                lines.append(current)
                current = token
            else:
                current = trial
        if current:
            lines.append(current)
        return lines

    font_size = 112
    headline_font = load_font(font_size)
    lines = wrap_headline(headline_font)
    while len(lines) > 2 and font_size > 68:
        font_size -= 4
        headline_font = load_font(font_size)
        lines = wrap_headline(headline_font)
    if len(lines) > 2:
        label = "GTA MOMENT"
        headline_font = load_font(112)
        lines = [label]

    y = title_top + 20
    for index, line in enumerate(lines):
        box = draw.textbbox((0, 0), line, font=headline_font, stroke_width=1)
        line_height = box[3] - box[1]
        x = (width - (box[2] - box[0])) // 2 - box[0]
        fill = accent if index == 0 else white
        draw.text((x + 3, y + 7 - box[1]), line, font=headline_font,
                  fill=(0, 0, 0, 220), stroke_width=5, stroke_fill=(0, 0, 0, 220))
        draw.text((x, y - box[1]), line, font=headline_font,
                  fill=fill, stroke_width=1, stroke_fill=(8, 10, 13, 255))
        y += line_height + 8

    # Small creator credit, never a second headline.
    credit_y = max(y + 26, 1510)
    if creator:
        credit_font = load_font(27)
        creator_text = creator.upper()
        creator_box = draw.textbbox((0, 0), creator_text, font=credit_font)
        creator_width = creator_box[2] - creator_box[0] + 46
        draw.rounded_rectangle((margin, credit_y, margin + creator_width, credit_y + 58),
                               radius=16, fill=(8, 10, 13, 210), outline=(255, 255, 255, 70), width=2)
        draw.text((margin + 23, credit_y + 13 - creator_box[1]), creator_text,
                  font=credit_font, fill=white)

    footer_y = 1770
    draw.line((margin, footer_y, width - margin, footer_y), fill=(255, 255, 255, 72), width=2)
    footer_font = load_font(21)
    draw.text((margin, footer_y + 25), "@GTARANKEDSTUDIO", font=footer_font, fill=muted)
    footer_right = "GTA CLIPS"
    right_box = draw.textbbox((0, 0), footer_right, font=footer_font)
    draw.text((width - margin - (right_box[2] - right_box[0]), footer_y + 25),
              footer_right, font=footer_font, fill=accent)

    final_image = Image.alpha_composite(canvas, overlay).convert("RGB")
    final_image.save(image_path, format="JPEG", quality=94, optimize=True, progressive=True, subsampling=0)
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
    """Sélectionne un passage resserré autour du pic, si la source est longue.

    Les mots transcrits servent à repérer une fin de phrase ou une pause après
    le pic. Sans transcription, une fenêtre de secours centrée sur le pic est
    choisie. Les clips courts sont conservés intégralement.
    """
    duration = max(0.0, float(duration))
    if duration <= 0:
        return 0.0, 0.0
    if duration <= threshold_seconds:
        return 0.0, duration

    peak = max(0.0, min(float(peak_timestamp), duration))
    start = max(0.0, peak - max(0.0, lead_seconds))
    end_after_payoff: float | None = None
    ordered = sorted(words or [], key=lambda item: (item.start, item.end))
    punctuation = re.compile(r"[.!?][\"')\]]*$")
    after_peak = [item for item in ordered if item.end >= peak]
    if after_peak:
        for item in after_peak:
            clean = _clean_ass_text(item.text)
            next_item = next((candidate for candidate in ordered if candidate.start >= item.end and candidate is not item), None)
            pause_after = (next_item.start - item.end) if next_item else 0.0
            if punctuation.search(clean) or pause_after >= 0.75:
                end_after_payoff = item.end
                break
        if end_after_payoff is None:
            nearby = [item for item in after_peak if item.start <= peak + 10.0]
            if nearby:
                end_after_payoff = nearby[-1].end

    if end_after_payoff is None:
        end_after_payoff = peak + 12.0
    end = min(duration, max(peak + 2.0, end_after_payoff + max(0.0, tail_seconds)))

    # Garantit assez de contexte pour que le moment reste compréhensible.
    if end - start < minimum_seconds:
        desired_start = max(0.0, peak - max(1.5, minimum_seconds * 0.565))
        start = min(start, desired_start)
        end = min(duration, max(end, start + minimum_seconds))
        if end - start < minimum_seconds:
            start = max(0.0, end - minimum_seconds)

    if end - start > maximum_seconds:
        start = max(0.0, min(start, peak - min(12.0, maximum_seconds * 0.35)))
        end = min(duration, start + maximum_seconds)
        if end - start > maximum_seconds:
            start = end - maximum_seconds

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
