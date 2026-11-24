from __future__ import annotations

import re
import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"Patch v0.4.2 impossible : bloc introuvable ({label}) dans {path}")
    if text.count(old) != 1:
        raise SystemExit(f"Patch v0.4.2 ambigu : {text.count(old)} occurrences ({label}) dans {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def set_version(path: Path, pattern: str, replacement: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count == 0:
        if "0.4.2" in text:
            return
        raise SystemExit(f"Version {label} introuvable dans {path}")
    path.write_text(updated, encoding="utf-8")


def apply(root: Path) -> None:
    root = root.resolve()
    highlights = root / "studio/web/highlights.py"

    helper = '''def build_twitch_download_ranges(start_seconds: float, end_seconds: float):
    """Build yt-dlp's Python API callback for one precise VOD time range."""
    try:
        from yt_dlp.utils import download_range_func
    except ImportError as exc:
        raise MediaError("yt-dlp ne fournit pas l'API de découpage nécessaire.") from exc
    return download_range_func(None, [(float(start_seconds), float(end_seconds))])


'''
    anchor = "def _format_section_time(seconds: float) -> str:\n"
    replace_once(
        highlights,
        anchor,
        helper + anchor,
        "helper yt-dlp download_ranges",
    )
    replace_once(
        highlights,
        '                options["download_sections"] = [f"*{_format_section_time(float(start))}-{_format_section_time(float(end))}"]\n',
        '                options["download_ranges"] = build_twitch_download_ranges(float(start), float(end))\n',
        "option yt-dlp download_ranges",
    )

    test_file = root / "tests/test_twitch_download_ranges.py"
    test_file.write_text(
        '''from __future__ import annotations

from studio.web.highlights import build_twitch_download_ranges


def test_twitch_download_range_callback_returns_only_the_requested_window() -> None:
    callback = build_twitch_download_ranges(3600, 4000)

    sections = list(callback({"duration": 19 * 60 * 60}, None))

    assert len(sections) == 1
    assert sections[0]["start_time"] == 3600
    assert sections[0]["end_time"] == 4000


def test_twitch_download_range_callback_preserves_fractional_seconds() -> None:
    callback = build_twitch_download_ranges(3600.25, 4000.75)

    sections = list(callback({"duration": 19 * 60 * 60}, None))

    assert sections[0]["start_time"] == 3600.25
    assert sections[0]["end_time"] == 4000.75
''',
        encoding="utf-8",
    )

    (root / "VERSION.txt").write_text("GTA Ranked Studio\nVersion: 0.4.2\n", encoding="utf-8")
    pyproject = root / "pyproject.toml"
    set_version(
        pyproject,
        r'^(\s*version\s*=\s*)["\'][^"\']+["\'](\s*(?:#.*)?)$',
        r'\g<1>"0.4.2"\g<2>',
        "pyproject.toml",
    )
    config = root / "config.yaml.default"
    set_version(
        config,
        r'^(\s{2}version:\s*)[^\s#]+(\s*(?:#.*)?)$',
        r'\g<1>0.4.2\g<2>',
        "config.yaml.default",
    )

    for relative in (
        "installer/apply_update.ps1",
        "installer/update_from_archive.ps1",
        "installer/install.ps1",
    ):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        old = "'NOTES-v0.3.6.txt', 'VERIFICATION-v0.3.6.md'"
        required = [
            "'NOTES-v0.4.1.txt', 'VERIFICATION-v0.4.1.md'",
            "'NOTES-v0.4.2.txt', 'VERIFICATION-v0.4.2.md'",
        ]
        if old in text:
            text = text.replace(old, old + ", " + ", ".join(required), 1)
        else:
            missing = [entry for entry in required if entry not in text]
            if missing:
                marker = required[0]
                if marker not in text:
                    raise SystemExit(f"Liste de fichiers root absente dans {relative}")
                text = text.replace(marker, marker + ", " + required[1], 1)
        path.write_bytes(b"\xef\xbb\xbf" + text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))

    (root / "NOTES-v0.4.2.txt").write_text(
        """GTA Ranked Studio v0.4.2

Correctif du découpage temporel des VOD Twitch :
- Utilisation de l'API Python yt-dlp download_ranges pour transmettre le début et la fin demandés.
- Les plages horaires sélectionnées sont maintenant appliquées au téléchargement au lieu de télécharger la VOD complète.
- Les horodatages des moments détectés restent référencés à la VOD d'origine.
- La limite de 3 heures par analyse est conservée.
- Le correctif d'inspection FFprobe de la version 0.4.1 est conservé.
- Les médias, modèles IA, projets, réglages et données locaux sont préservés.
""",
        encoding="utf-8",
    )
    (root / "VERIFICATION-v0.4.2.md").write_text(
        """# Vérification v0.4.2

- Le découpage Twitch utilise yt_dlp.utils.download_range_func via l'option Python download_ranges.
- Les tests vérifient le début/fin exacts, y compris les secondes fractionnaires.
- La suite complète de tests doit passer avant publication.
- La limite de 3 heures par plage et le délai FFprobe dynamique de v0.4.1 sont conservés.
""",
        encoding="utf-8",
    )

    for relative in ("README.md", "docs/UPDATES.md"):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        text += """
        
## v0.4.2 : découpage réel des VOD Twitch

Le téléchargement de plages horaires Twitch utilise l'option Python download_ranges de yt-dlp. Les horaires de début et de fin sont donc appliqués au fichier téléchargé, plutôt que seulement conservés dans les métadonnées du scan. La limite de 3 heures par analyse et le correctif FFprobe v0.4.1 sont conservés.
"""
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.4.2.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
