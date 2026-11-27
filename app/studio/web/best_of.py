"""Sélection et validation du plan de montage Daily Best Of."""

from __future__ import annotations

from pathlib import Path
from typing import Any

MIN_EPISODE_SECONDS = 9 * 60
MAX_EPISODE_SECONDS = 11 * 60
MAX_SELECTED_CLIPS = 50


def build_best_of_plan(
    clips: list[dict[str, Any]],
    clip_ids: list[str],
    *,
    date_key: str | None = None,
) -> dict[str, Any]:
    """Build an ordered, local-only episode plan from explicitly validated Shorts."""
    if not isinstance(clip_ids, list) or not clip_ids:
        raise ValueError("Sélectionne au moins un Short.")
    if len(clip_ids) > MAX_SELECTED_CLIPS:
        raise ValueError(f"Un épisode ne peut pas contenir plus de {MAX_SELECTED_CLIPS} Shorts.")
    normalized_ids = [str(value).strip() for value in clip_ids]
    if any(not value for value in normalized_ids):
        raise ValueError("La sélection contient un identifiant vide.")
    if len(set(normalized_ids)) != len(normalized_ids):
        raise ValueError("Un même Short ne peut apparaître qu'une seule fois dans l'épisode.")

    by_id = {str(clip.get("id") or clip.get("job_id") or ""): clip for clip in clips}
    missing = [clip_id for clip_id in normalized_ids if clip_id not in by_id]
    if missing:
        raise ValueError("Certains Shorts sélectionnés ne sont plus dans la bibliothèque. Actualise la page.")

    ordered: list[dict[str, Any]] = []
    total_duration = 0.0
    for clip_id in normalized_ids:
        clip = by_id[clip_id]
        if clip.get("status") != "validated":
            raise ValueError("Seuls les Shorts validés peuvent entrer dans un Daily Best Of.")
        if date_key and str(clip.get("date_key") or "") != date_key:
            raise ValueError("Tous les Shorts d'un Daily Best Of doivent appartenir à la date sélectionnée.")
        output_path = Path(str(clip.get("output_path") or ""))
        if not output_path.is_file():
            raise ValueError(f"Le rendu du Short {clip_id[:8]} est introuvable sur ce PC.")
        try:
            duration = float(clip.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration <= 0:
            raise ValueError(f"La durée du Short {clip_id[:8]} est invalide.")
        total_duration += duration
        ordered.append({
            "id": clip_id,
            "job_id": str(clip.get("job_id") or clip_id),
            "title": str(clip.get("source_title") or clip.get("streamer") or "GTA moment"),
            "streamer": str(clip.get("streamer") or ""),
            "duration": duration,
            "output_path": str(output_path.resolve()),
            "thumbnail_path": str(clip.get("thumbnail_path") or ""),
            "date_key": str(clip.get("date_key") or ""),
        })

    total_duration = round(total_duration, 2)
    return {
        "clips": ordered,
        "clip_count": len(ordered),
        "total_duration": total_duration,
        "formatted_duration": f"{int(total_duration // 60):02d}:{int(total_duration % 60):02d}",
        "target_min_seconds": MIN_EPISODE_SECONDS,
        "target_max_seconds": MAX_EPISODE_SECONDS,
        "ready_for_render": MIN_EPISODE_SECONDS <= total_duration <= MAX_EPISODE_SECONDS,
        "remaining_to_minimum": round(max(0.0, MIN_EPISODE_SECONDS - total_duration), 2),
        "over_maximum": round(max(0.0, total_duration - MAX_EPISODE_SECONDS), 2),
        "date_key": date_key or (ordered[0]["date_key"] if ordered else ""),
    }
