from __future__ import annotations
import sys
from pathlib import Path

def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    count = text.count(old)
    if count == 0 and new in text:
        return
    if count != 1:
        raise SystemExit(f"Patch v0.6.2 impossible : {count} occurrence(s) du bloc « {label} » dans {path}")
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

def patch_highlights(root: Path) -> None:
    path = root / "studio/web/highlights.py"
    replace_once(path, "MAX_CANDIDATES = 8", "MIN_CANDIDATE_SCORE = 80.0", "seuil qualité")
    replace_once(path, "    max_candidates: int = MAX_CANDIDATES,", "    max_candidates: int | None = None,", "suppression du plafond par défaut")
    replace_once(path, "    if duration <= 0 or max_candidates <= 0:", "    if duration <= 0 or (max_candidates is not None and max_candidates <= 0):", "validation du plafond optionnel")
    replace_once(path, "            if score < 8.0:\n                continue", "            if score <= MIN_CANDIDATE_SCORE:\n                continue", "seuil strict supérieur à 80")
    replace_once(path, "        selected.append(candidate)\n        if len(selected) >= max_candidates:\n            break", "        selected.append(candidate)\n        if max_candidates is not None and len(selected) >= max_candidates:\n            break", "conservation de tous les candidats qualifiés")

def patch_tests(root: Path) -> None:
    path = root / "tests/test_highlights.py"
    replace_function(path, "test_score_candidates_returns_bounded_ranked_non_overlapping_results", '''def test_score_candidates_returns_only_high_quality_ranked_results() -> None:
    audio = [
        {"start": float(second), "end": float(second + 2), "rms": 0.03 if 40 <= second < 65 else 0.005}
        for second in range(0, 120, 2)
    ]
    cues = ["BRO", "WHAT", "NO", "WAIT", "OMG", "INSANE", "CRAZY", "HOLY", "SHIT", "FUCK", "DAMN", "BRUH", "WTF", "HELP", "YO", "NAH", "SICK", "CLUTCH"]
    words = [WordTiming(40.0 + index * 1.2, 40.4 + index * 1.2, cue) for index, cue in enumerate(cues)]
    candidates = score_highlight_candidates(120, audio, words, candidate_seconds=30, max_candidates=5)
    assert candidates
    assert len(candidates) <= 5
    assert all(item["score"] > 80 for item in candidates)
    assert [item["rank"] for item in candidates] == list(range(1, len(candidates) + 1))
    assert all(0 <= item["start_time"] < item["end_time"] <= 120 for item in candidates)
    assert all(item["end_time"] - item["start_time"] <= 30 for item in candidates)
    assert [item["score"] for item in candidates] == sorted((item["score"] for item in candidates), reverse=True)
''')
    replace_function(path, "test_default_highlight_candidates_are_non_overlapping_and_use_supported_lengths", '''def test_default_highlight_candidates_are_non_overlapping_and_use_supported_lengths() -> None:
    audio = [
        {"start": float(second), "end": float(second + 2),
         "rms": 0.06 if (40 <= second < 70 or 110 <= second < 140) else 0.005}
        for second in range(0, 180, 2)
    ]
    cues = ["BRO", "WHAT", "NO", "WAIT", "OMG", "INSANE", "CRAZY", "HOLY", "SHIT", "FUCK", "DAMN", "BRUH", "WTF", "HELP", "YO", "NAH", "SICK", "CLUTCH"]
    words = [
        WordTiming(start + 1.0 + index * 1.2, start + 1.3 + index * 1.2, cues[index])
        for start in (40.0, 110.0) for index in range(len(cues))
    ]
    candidates = score_highlight_candidates(180, audio, words)
    assert candidates
    assert all(item["score"] > 80 for item in candidates)
    assert all(round(item["end_time"] - item["start_time"]) in {25, 35, 45, 60} for item in candidates)
    for index, first in enumerate(candidates):
        for second in candidates[index + 1:]:
            assert first["end_time"] + 6 <= second["start_time"] or second["end_time"] + 6 <= first["start_time"]
''')
    replace_function(path, "test_score_short_twitch_clip_returns_single_candidate", '''def test_score_short_twitch_clip_below_threshold_is_not_proposed() -> None:
    candidates = score_highlight_candidates(
        24,
        [{"start": 0, "end": 2, "rms": 0.02}, {"start": 2, "end": 4, "rms": 0.04}],
        [WordTiming(2, 3, "NO"), WordTiming(3, 4, "BRO")],
        candidate_seconds=35,
    )
    assert candidates == []
''')
    if "def test_highlight_candidates_are_unlimited_above_score_threshold" not in path.read_text(encoding="utf-8-sig"):
        with path.open("a", encoding="utf-8") as handle:
            handle.write('''

def test_highlight_candidates_are_unlimited_above_score_threshold() -> None:
    duration = 650
    event_starts = [10 + index * 70 for index in range(9)]
    audio = [
        {"start": float(second), "end": float(second + 2),
         "rms": 0.06 if any(start <= second < start + 30 for start in event_starts) else 0.005}
        for second in range(0, duration, 2)
    ]
    cues = ["BRO", "WHAT", "NO", "WAIT", "OMG", "INSANE", "CRAZY", "HOLY", "SHIT", "FUCK", "DAMN", "BRUH", "WTF", "HELP", "YO", "NAH", "SICK", "CLUTCH"]
    words = [
        WordTiming(start + 1.0 + index * 1.2, start + 1.3 + index * 1.2, cues[index])
        for start in event_starts for index in range(len(cues))
    ]
    candidates = score_highlight_candidates(duration, audio, words, candidate_seconds=30, max_candidates=None)
    assert len(candidates) >= 9
    assert all(item["score"] > 80 for item in candidates)
    assert [item["rank"] for item in candidates] == list(range(1, len(candidates) + 1))
''')

def patch_ui(root: Path) -> None:
    replace_once(root / "studio/web/static/index.html",
        "Durées adaptatives de 25 à 60 secondes, sans chevauchement",
        "Seuls les passages au score supérieur à 80/100 sont proposés, sans limite de quantité",
        "information de sélection dans l'interface")
    app = root / "studio/web/static/app.js"
    replace_once(app, "Math.round(candidate.score)", "Number(candidate.score).toFixed(1)", "affichage précis du score")
    replace_once(app, "Aucun passage assez marqué détecté. Essaie une autre plage horaire.",
        "Aucun passage n'a dépassé le seuil strict de 80/100. Essaie une autre plage horaire.",
        "message sans candidat qualifié")

def patch_release(root: Path) -> None:
    for relative in ("installer/apply_update.ps1", "installer/update_from_archive.ps1", "installer/install.ps1"):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        entry = "'NOTES-v0.6.2.txt', 'VERIFICATION-v0.6.2.md'"
        if entry not in text:
            anchor = "'NOTES-v0.6.1.txt', 'VERIFICATION-v0.6.1.md'"
            if anchor not in text:
                raise SystemExit(f"Liste des documents de release absente dans {relative}")
            text = text.replace(anchor, anchor + ", " + entry, 1)
        path.write_text(text, encoding="utf-8-sig", newline="\r\n")

    (root / "VERSION.txt").write_text("GTA Ranked Studio\nVersion: 0.6.2\n", encoding="utf-8")
    replace_once(root / "pyproject.toml", 'version = "0.6.1"', 'version = "0.6.2"', "version pyproject")
    replace_once(root / "config.yaml.default", "  version: 0.6.1", "  version: 0.6.2", "version config")
    (root / "NOTES-v0.6.2.txt").write_text("""GTA Ranked Studio v0.6.2

Sélection des moments forts :
- Suppression de la limite fixe de 8 candidats.
- Conservation de tous les passages distincts qualifiés, sans plafond par défaut.
- Seuls les scores strictement supérieurs à 80/100 sont proposés.
- Les candidats restent triés du meilleur au moins bon et ne se chevauchent pas.
- Les scores sont affichés avec une décimale.
- Si aucun passage ne dépasse le seuil, aucun candidat n'est proposé.

Le score reste une heuristique locale fondée sur l'énergie audio (55 %), la densité de parole (25 %) et les mots de réaction (20 %). Il ne constitue pas une compréhension visuelle du gameplay ni une garantie de viralité. Les vidéos, modèles, projets, réglages et données locales sont préservés.
""", encoding="utf-8")
    (root / "VERIFICATION-v0.6.2.md").write_text("""# Vérification v0.6.2

- Plus de limite par défaut de 8 candidats.
- Seuil strict : un score de 80.0 ou inférieur est rejeté.
- Tous les candidats retenus dépassent 80/100.
- Tri par score et espacement anti-chevauchement préservés.
- Le paramètre max_candidates reste disponible pour les appels explicites qui souhaitent un plafond.
- Tests couvrant le rejet des scores faibles et un scan retournant au moins 9 passages.
- Interface affichant les scores avec une décimale et expliquant le seuil.
""", encoding="utf-8")
    for relative in ("README.md", "docs/UPDATES.md"):
        path = root / relative
        content = path.read_text(encoding="utf-8-sig")
        marker = "## v0.6.2 : sélection stricte des moments forts"
        if marker not in content:
            content += """

## v0.6.2 : sélection stricte des moments forts

La détection ne s'arrête plus à huit candidats. GTA Ranked Studio conserve tous les passages distincts dont le score est strictement supérieur à 80/100 et masque les autres. Le classement par score et l'espacement entre passages restent actifs. Le score demeure une heuristique locale basée sur l'énergie audio, la densité de parole et les mots de réaction ; il ne comprend pas encore les événements visuels du gameplay.
"""
        path.write_text(content, encoding="utf-8")
    readme = root / "README.md"
    content = readme.read_text(encoding="utf-8-sig").replace("Dernière version stable : **0.6.1**.", "Dernière version stable : **0.6.2**.")
    readme.write_text(content, encoding="utf-8")

def apply(root: Path) -> None:
    root = root.resolve()
    patch_highlights(root)
    patch_tests(root)
    patch_ui(root)
    patch_release(root)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.6.2.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
