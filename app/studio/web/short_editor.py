"""Génération de sous-titres ASS et d'overlays éditoriaux pour les Shorts."""

from __future__ import annotations

import math
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


@dataclass(frozen=True)
class PauseTrimPlan:
    """Conservative jump-cut plan expressed in excerpt-relative timestamps."""

    segments: tuple[tuple[float, float], ...]
    removed_pauses: tuple[tuple[float, float], ...]

    @property
    def output_duration(self) -> float:
        return round(sum(end - start for start, end in self.segments), 3)

    @property
    def removed_duration(self) -> float:
        return round(sum(end - start for start, end in self.removed_pauses), 3)


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
            f"Dialogue: 2,0:00:00.00,0:00:02.60,Hook,,0,0,0,,{{\\an8\\pos({width // 2},{int(height * 0.20)})\\fad(160,220)}}{_wrap_words(clean_hook, 5)}"
        )
    clean_context = _clean_ass_text(context_text)
    if clean_context:
        events.append(
            f"Dialogue: 2,0:00:00.35,0:00:03.50,Context,,0,0,0,,{{\\an8\\pos({width // 2},{int(height * 0.29)})\\fad(140,180)}}{_wrap_words(clean_context, 7)}"
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
    return image_path

def _has_sentence_punctuation(text: str) -> bool:
    clean = _clean_ass_text(text or "").strip()
    return bool(re.search(r"[.!?][\"')\]]*$", clean))


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
    max_context_lead_seconds: float = 6.0,
    sentence_pause_seconds: float = 0.65,
    boundary_padding_seconds: float = 0.12,
) -> tuple[float, float]:
    """Select an excerpt around the payoff without cutting into a spoken phrase.

    The opening starts at a nearby phrase boundary (punctuation or a natural
    speech gap) where possible. The ending keeps the first complete payoff
    phrase plus a short reaction tail. Short clips remain untouched.
    """
    duration = max(0.0, float(duration))
    if not math.isfinite(duration) or duration <= 0:
        return 0.0, 0.0
    if duration <= threshold_seconds:
        return 0.0, duration

    peak = max(0.0, min(float(peak_timestamp or 0.0), duration))
    ordered = sorted(
        (word for word in (words or []) if math.isfinite(word.start) and math.isfinite(word.end)
         and word.end > word.start and word.end > 0 and word.start < duration),
        key=lambda item: (item.start, item.end),
    )
    target_start = max(0.0, peak - max(0.0, lead_seconds))
    start = target_start
    if ordered:
        phrase_starts: list[float] = []
        for index, word in enumerate(ordered):
            if word.start > target_start:
                break
            is_boundary = index == 0
            if index > 0:
                previous = ordered[index - 1]
                pause = word.start - previous.end
                is_boundary = _has_sentence_punctuation(previous.text) or pause >= max(0.0, sentence_pause_seconds)
            distance = target_start - word.start
            if is_boundary and distance <= max(0.0, max_context_lead_seconds):
                phrase_starts.append(word.start)

        if phrase_starts:
            start = max(0.0, phrase_starts[-1] - max(0.0, boundary_padding_seconds))
        else:
            preceding_words = [word for word in ordered if word.start <= target_start]
            if preceding_words:
                start = max(0.0, preceding_words[-1].start - max(0.0, boundary_padding_seconds))

    minimum_post_peak = 2.0
    end_after_payoff: float | None = None
    for index, word in enumerate(ordered):
        if word.end < peak or word.end < peak + minimum_post_peak:
            continue
        next_word = next((candidate for candidate in ordered[index + 1:] if candidate.start >= word.end), None)
        pause_after = (next_word.start - word.end) if next_word else 0.0
        if _has_sentence_punctuation(word.text) or pause_after >= 0.9:
            end_after_payoff = word.end
            break

    if end_after_payoff is None:
        nearby = [word for word in ordered if peak <= word.start <= peak + 10.0]
        end_after_payoff = nearby[-1].end if nearby else peak + 12.0
    end = min(duration, max(peak + minimum_post_peak, end_after_payoff + max(0.0, tail_seconds)))

    # Garantit assez de contexte pour que le moment reste compréhensible.
    minimum_seconds = max(0.0, float(minimum_seconds))
    maximum_seconds = max(minimum_seconds, float(maximum_seconds))
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


def plan_speech_pause_edits(
    words: list[WordTiming],
    duration: float,
    peak_timestamp: float,
    *,
    timestamp_mode: str,
    min_pause_seconds: float = 3.0,
    keep_context_seconds: float = 0.55,
    peak_guard_seconds: float = 2.5,
    max_removed_seconds: float = 6.0,
    max_cuts: int = 2,
    min_segment_seconds: float = 1.25,
) -> PauseTrimPlan:
    """Remove only a few long, low-risk speech gaps from a word-DTW excerpt.

    Segment-level SRT timestamps are too coarse for jump cuts, so they never
    trigger pause removal. A protected zone around the detected audio peak
    preserves the main reaction/gameplay payoff.
    """
    duration = float(duration)
    if not math.isfinite(duration) or duration <= 0:
        return PauseTrimPlan((), ())
    full_plan = PauseTrimPlan(((0.0, round(duration, 3)),), ())
    if timestamp_mode != "word_dtw" or max_cuts <= 0 or max_removed_seconds <= 0:
        return full_plan

    ordered = sorted(
        (word for word in (words or []) if math.isfinite(word.start) and math.isfinite(word.end)
         and word.end > word.start and word.end > 0 and word.start < duration),
        key=lambda item: (item.start, item.end),
    )
    if len(ordered) < 4:
        return full_plan

    peak = max(0.0, min(float(peak_timestamp or 0.0), duration))
    minimum_pause = max(0.0, float(min_pause_seconds))
    keep = max(0.0, float(keep_context_seconds))
    guard = max(0.0, float(peak_guard_seconds))
    minimum_segment = max(0.25, float(min_segment_seconds))
    candidates: list[tuple[float, float, float]] = []

    for previous, following in zip(ordered, ordered[1:]):
        gap_start = max(0.0, previous.end)
        gap_end = min(duration, following.start)
        gap_duration = gap_end - gap_start
        if gap_duration < minimum_pause:
            continue
        if gap_start - guard <= peak <= gap_end + guard:
            continue

        cut_start = gap_start + keep
        cut_end = gap_end - keep
        removed = cut_end - cut_start
        if removed < 1.25:
            continue
        candidates.append((cut_start, cut_end, removed))

    # Prefer the longest gaps, but never leave a tiny fragment at either end
    # or between two edits. Both the number and total removed time are capped.
    selected: list[tuple[float, float]] = []
    removed_total = 0.0

    def complement(cuts: list[tuple[float, float]]) -> list[tuple[float, float]]:
        result: list[tuple[float, float]] = []
        cursor = 0.0
        for cut_start, cut_end in sorted(cuts):
            if cut_start > cursor:
                result.append((cursor, cut_start))
            cursor = max(cursor, cut_end)
        if cursor < duration:
            result.append((cursor, duration))
        return result

    for cut_start, cut_end, removed in sorted(candidates, key=lambda item: item[2], reverse=True):
        if len(selected) >= max_cuts or removed_total + removed > max_removed_seconds:
            continue
        if any(cut_start < existing_end and cut_end > existing_start for existing_start, existing_end in selected):
            continue
        tentative = sorted(selected + [(cut_start, cut_end)])
        kept_segments = complement(tentative)
        if len(kept_segments) < 2 or any(end - start < minimum_segment for start, end in kept_segments):
            continue
        selected = tentative
        removed_total += removed

    if not selected:
        return full_plan

    segments = tuple(
        (round(start, 3), round(end, 3))
        for start, end in complement(selected)
    )
    removed_pauses = tuple(
        (round(start, 3), round(end, 3)) for start, end in selected
    )
    return PauseTrimPlan(segments, removed_pauses)


def rebase_word_timings_by_segments(
    words: list[WordTiming], segments: tuple[tuple[float, float], ...] | list[tuple[float, float]],
) -> list[WordTiming]:
    """Rebase word timestamps after several excerpt-relative segments are joined."""
    result: list[WordTiming] = []
    output_offset = 0.0
    for segment_start, segment_end in segments:
        segment_start = max(0.0, float(segment_start))
        segment_end = max(segment_start, float(segment_end))
        for word in words:
            if word.end <= segment_start or word.start >= segment_end:
                continue
            start = output_offset + max(0.0, word.start - segment_start)
            end = output_offset + min(segment_end, word.end) - segment_start
            if end > start:
                result.append(WordTiming(round(start, 3), round(end, 3), word.text))
        output_offset += segment_end - segment_start
    return sorted(result, key=lambda item: (item.start, item.end))


def map_timestamp_through_segments(
    timestamp: float,
    segments: tuple[tuple[float, float], ...] | list[tuple[float, float]],
) -> float:
    """Map a source-relative timestamp into the concatenated output timeline."""
    source_time = max(0.0, float(timestamp))
    output_offset = 0.0
    for start, end in segments:
        start = max(0.0, float(start))
        end = max(start, float(end))
        if source_time <= start:
            return round(output_offset, 3)
        if source_time <= end:
            return round(output_offset + source_time - start, 3)
        output_offset += end - start
    return round(output_offset, 3)


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
