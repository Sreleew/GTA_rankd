from __future__ import annotations

import re
import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"Patch v0.4.1 impossible : bloc introuvable ({label}) dans {path}")
    if text.count(old) != 1:
        raise SystemExit(f"Patch v0.4.1 ambigu : {text.count(old)} occurrences ({label}) dans {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def set_version(path: Path, pattern: str, replacement: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count == 0:
        if "0.4.1" in text:
            return
        raise SystemExit(f"Version {label} introuvable dans {path}")
    path.write_text(updated, encoding="utf-8")


def apply(root: Path) -> None:
    root = root.resolve()
    renderer = root / "studio/web/short_renderer.py"

    helper = '''def probe_timeout_for_file(input_path: Path) -> int:
    """Return a generous FFprobe timeout scaled to the downloaded media size.

    Twitch VOD downloads can be large or have container indexes that take much
    longer to inspect than a short clip. Keep a five-minute floor, add one
    minute per 256 MiB, and cap the wait at thirty minutes.
    """
    try:
        size_bytes = max(0, int(input_path.stat().st_size))
    except OSError:
        size_bytes = 0
    size_steps = size_bytes // (256 * 1024 * 1024)
    return min(30 * 60, max(5 * 60, 3 * 60 + int(size_steps) * 60))


'''
    signature_old = 'def probe_media(input_path: Path, ffprobe: str = "ffprobe") -> dict[str, Any]:\n'
    signature_new = '''def probe_media(
    input_path: Path,
    ffprobe: str = "ffprobe",
    *,
    timeout: int = 60,
) -> dict[str, Any]:
'''
    replace_once(renderer, signature_old, helper + signature_new, "paramètre timeout FFprobe")
    replace_once(
        renderer,
        '    ], timeout=60)\n    try:\n        data = json.loads(result.stdout)\n',
        '    ], timeout=timeout)\n    try:\n        data = json.loads(result.stdout)\n',
        "timeout FFprobe configurable",
    )

    highlights = root / "studio/web/highlights.py"
    replace_once(
        highlights,
        "from studio.web.short_renderer import MediaError, probe_media\n",
        "from studio.web.short_renderer import MediaError, probe_media, probe_timeout_for_file\n",
        "import du délai FFprobe dynamique",
    )
    replace_once(
        highlights,
        '            media = probe_media(source_path, str(self.config.get("executables", "ffprobe", default="ffprobe")))\n',
        '''            probe_timeout = probe_timeout_for_file(source_path)
            self.store.update_highlight_scan(
                scan_id, progress=18,
                message=f"Inspection de la vidéo (délai maximal : {probe_timeout // 60} min)",
            )
            media = probe_media(
                source_path,
                str(self.config.get("executables", "ffprobe", default="ffprobe")),
                timeout=probe_timeout,
            )
''',
        "appel FFprobe dans le scanner",
    )
    replace_once(
        highlights,
        '                progress=15, message=f"Analyse audio sur {analysis_duration / 60:.1f} minutes",\n',
        '                progress=20, message=f"Analyse audio sur {analysis_duration / 60:.1f} minutes",\n',
        "progression après inspection vidéo",
    )

    test_file = root / "tests/test_probe_timeout.py"
    test_file.write_text(
        '''from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from studio.web import short_renderer


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        (0, 300),
        (1, 300),
        (1024 * 1024 * 1024, 420),
        (20 * 1024 * 1024 * 1024, 1800),
    ],
)
def test_probe_timeout_scales_with_file_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size_bytes: int, expected: int
) -> None:
    media = tmp_path / "vod.mp4"
    media.write_bytes(b"test")
    monkeypatch.setattr(Path, "stat", lambda self: SimpleNamespace(st_size=size_bytes))
    assert short_renderer.probe_timeout_for_file(media) == expected


def test_probe_media_uses_the_supplied_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "vod.mp4"
    media.write_bytes(b"test")
    payload = {
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "60/1",
                "codec_name": "h264",
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": "900"},
    }
    calls: list[int | None] = []

    def fake_run_command(args, timeout=None, cwd=None):
        calls.append(timeout)
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr(short_renderer, "resolve_executable", lambda _: "ffprobe")
    monkeypatch.setattr(short_renderer, "run_command", fake_run_command)
    result = short_renderer.probe_media(media, "ffprobe", timeout=420)

    assert calls == [420]
    assert result["duration"] == 900
    assert result["has_audio"] is True
''',
        encoding="utf-8",
    )

    (root / "VERSION.txt").write_text("GTA Ranked Studio\nVersion: 0.4.1\n", encoding="utf-8")
    pyproject = root / "pyproject.toml"
    set_version(
        pyproject,
        r'^(\s*version\s*=\s*)["\'][^"\']+["\'](\s*(?:#.*)?)$',
        r'\g<1>"0.4.1"\g<2>',
        "pyproject.toml",
    )
    config = root / "config.yaml.default"
    set_version(
        config,
        r'^(\s{2}version:\s*)[^\s#]+(\s*(?:#.*)?)$',
        r'\g<1>0.4.1\g<2>',
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
        new = old + ", 'NOTES-v0.4.1.txt', 'VERIFICATION-v0.4.1.md'"
        if new not in text:
            if old not in text:
                raise SystemExit(f"Liste de fichiers root absente dans {relative}")
            text = text.replace(old, new, 1)
        path.write_bytes(b"\xef\xbb\xbf" + text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))

    (root / "NOTES-v0.4.1.txt").write_text(
        """GTA Ranked Studio v0.4.1

Correctif de l'analyse des VOD longues :
- FFprobe dispose désormais d'un délai calculé selon la taille du média téléchargé.
- Le délai dispose d'un minimum de 5 minutes et est plafonné à 30 minutes.
- L'écran indique l'étape d'inspection de la vidéo avant l'analyse audio.
- La limite de 3 heures par analyse et la transcription Whisper par blocs de 5 minutes sont conservées.
- Les vidéos, modèles IA, projets, réglages et données locaux sont préservés.
""",
        encoding="utf-8",
    )
    (root / "VERIFICATION-v0.4.1.md").write_text(
        """# Vérification v0.4.1

- Le scanner calcule le délai FFprobe selon la taille du fichier local.
- Le délai minimum est de 300 secondes, avec 60 secondes supplémentaires par tranche de 256 MiB, plafonné à 1 800 secondes.
- Les appels FFprobe des autres flux conservent leur délai par défaut de 60 secondes.
- Des tests couvrent le calcul du délai, le plafond de 30 minutes et la transmission du délai à FFprobe.
- La limite d'analyse reste de 3 heures et la transcription demeure découpée par blocs de 5 minutes.
""",
        encoding="utf-8",
    )

    for relative in ("README.md", "docs/UPDATES.md"):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        text += """
        
## v0.4.1 : analyse des VOD longues

L'inspection FFprobe après téléchargement Twitch utilise maintenant un délai calculé selon la taille du fichier (minimum 5 minutes, maximum 30 minutes). La progression distingue l'inspection vidéo de l'analyse audio. Les autres traitements Shorts conservent leur délai FFprobe par défaut.
"""
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.4.1.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
