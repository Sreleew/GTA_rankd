from __future__ import annotations

import re
import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"Patch v0.5.0 impossible : {count} occurrence(s) du bloc « {label} » dans {path}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"Patch v0.5.0 impossible : bloc « {label} » absent dans {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def set_version(path: Path, pattern: str, replacement: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count == 0:
        if "0.5.0" in text:
            return
        raise SystemExit(f"Version {label} introuvable dans {path}")
    path.write_text(updated, encoding="utf-8")


def patch_highlight_scoring(root: Path) -> None:
    path = root / "studio/web/highlights.py"
    text = path.read_text(encoding="utf-8-sig")
    start = text.index("def score_highlight_candidates(")
    end = text.index("\n\ndef write_wav_chunk", start)
    current = text[start:end]
    if "candidate_seconds: float | None = None" in current:
        return

    replacement = r'''def score_highlight_candidates(
    duration: float,
    audio_windows: list[dict[str, float]],
    words: list[WordTiming],
    *,
    candidate_seconds: float | None = None,
    max_candidates: int = MAX_CANDIDATES,
) -> list[dict[str, Any]]:
    """Rank variable-length excerpts and keep only distinct, non-overlapping moments.

    The default scan evaluates several useful Short lengths. Supplying
    candidate_seconds keeps the deterministic single-length mode used by tests
    and callers that need a fixed duration.
    """
    duration = max(0.0, float(duration))
    if duration <= 0 or max_candidates <= 0:
        return []

    if candidate_seconds is not None:
        clip_lengths = [min(max(1.0, float(candidate_seconds)), duration)]
    else:
        clip_lengths = sorted({min(value, duration) for value in (25.0, 35.0, 45.0, 60.0) if value <= duration})
        if not clip_lengths:
            clip_lengths = [duration]

    rms_values = [float(item["rms"]) for item in audio_windows if item.get("rms", 0) >= 0]
    if rms_values:
        sorted_rms = sorted(rms_values)
        p50 = sorted_rms[int((len(sorted_rms) - 1) * 0.50)]
        p98 = sorted_rms[int((len(sorted_rms) - 1) * 0.98)]
    else:
        p50 = p98 = 0.0
    audio_span = max(0.0001, p98 - p50)

    ranked: list[dict[str, Any]] = []
    for clip_length in clip_lengths:
        if duration <= clip_length + 0.01:
            starts = [0.0]
        else:
            hop = max(4.0, min(10.0, clip_length / 4.0))
            starts = []
            current = 0.0
            while current + clip_length <= duration + 0.01:
                starts.append(current)
                current += hop
            last_start = max(0.0, duration - clip_length)
            if not starts or last_start - starts[-1] > 0.5:
                starts.append(last_start)

        for start in starts:
            end = min(duration, start + clip_length)
            local_audio = [
                float(item["rms"])
                for item in audio_windows
                if item["end"] > start and item["start"] < end
            ]
            local_audio.sort(reverse=True)
            top_count = max(1, min(5, len(local_audio)))
            peak_average = sum(local_audio[:top_count]) / top_count if local_audio else 0.0
            audio_score = max(0.0, min(1.0, (peak_average - p50) / audio_span))

            local_words = _words_for_window(words, start, end)
            speech_density = len(local_words) / max(1.0, end - start)
            speech_score = max(0.0, min(1.0, speech_density / 1.35))
            cue_count = 0
            for word in local_words:
                tokens = re.findall(r"[a-z']+", word.text.lower())
                cue_count += sum(1 for token in tokens if token in REACTION_CUES)
            reaction_score = max(0.0, min(1.0, cue_count / 3.0))

            score = 100.0 * (
                0.55 * audio_score + 0.25 * speech_score + 0.20 * reaction_score
            )
            reasons: list[str] = []
            if audio_score >= 0.55:
                reasons.append("Pic d'énergie audio")
            if speech_score >= 0.55:
                reasons.append("Dialogue soutenu")
            if reaction_score > 0:
                reasons.append("Mots de réaction détectés")
            if not reasons:
                reasons.append("Activité audio repérée")

            if score < 8.0:
                continue
            transcript = " ".join(word.text.strip() for word in local_words).strip()
            ranked.append({
                "start_time": round(start, 3),
                "end_time": round(end, 3),
                "score": round(score, 1),
                "audio_score": round(audio_score, 3),
                "speech_score": round(speech_score, 3),
                "reaction_score": round(reaction_score, 3),
                "reasons": reasons,
                "transcript": transcript[:700],
            })

    ranked.sort(key=lambda item: item["score"], reverse=True)
    selected: list[dict[str, Any]] = []
    minimum_gap = 6.0
    for candidate in ranked:
        start = float(candidate["start_time"])
        end = float(candidate["end_time"])
        overlaps = any(
            start < float(chosen["end_time"]) + minimum_gap
            and end + minimum_gap > float(chosen["start_time"])
            for chosen in selected
        )
        if overlaps:
            continue
        selected.append(candidate)
        if len(selected) >= max_candidates:
            break

    for index, candidate in enumerate(selected, start=1):
        candidate["rank"] = index
    return selected'''
    path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")


def patch_quiet_subprocesses(root: Path) -> None:
    process_file = root / "studio/process.py"
    process_file.write_text(
        '''"""Cross-platform helpers for launching external tools without console flashes."""

from __future__ import annotations

import os
import subprocess
from typing import Any


def run_quiet(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run a child process and suppress its console window on Windows.

    stdout/stderr remain captured by the caller, so diagnostics still reach the
    application log and error messages.
    """
    if os.name == "nt":
        kwargs.setdefault(
            "creationflags",
            getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )
    return subprocess.run(*args, **kwargs)
''',
        encoding="utf-8",
    )

    imports = {
        "studio/doctor.py": (
            "from studio.config import AppConfig\n",
            "from studio.config import AppConfig\nfrom studio.process import run_quiet\n",
        ),
        "studio/web/app.py": (
            "from studio.config import AppConfig, load_config\n",
            "from studio.config import AppConfig, load_config\nfrom studio.process import run_quiet\n",
        ),
        "studio/web/short_renderer.py": (
            "from typing import Any, Sequence\n",
            "from typing import Any, Sequence\n\nfrom studio.process import run_quiet\n",
        ),
        "studio/web/transcribe.py": (
            "from typing import Any\n",
            "from typing import Any\n\nfrom studio.process import run_quiet\n",
        ),
    }
    for relative, (old_import, new_import) in imports.items():
        path = root / relative
        replace_once(path, old_import, new_import, f"import run_quiet dans {relative}")
        replace_all(path, "subprocess.run(", "run_quiet(", f"appels subprocess dans {relative}")


WEBCAM_FILTER = r'''def build_filter_complex(
    width: int = 1080,
    height: int = 1920,
    blur: int = 28,
    *,
    layout: str = "fill",
    crop_x: int = 50,
    crop_y: int = 50,
    ass_file: Path | None = None,
    fonts_dir: Path | None = None,
    project_root: Path | None = None,
    dynamic_zoom: bool = True,
    peak_timestamp: float = 0.0,
    fps: int = 30,
    zoom_percent: int = 8,
    webcam_zone: str = "none",
) -> str:
    """Build a vertical video graph with an optional webcam crop from the same VOD."""
    if width <= 0 or height <= 0:
        raise ValueError("Les dimensions de sortie doivent être positives.")
    if layout not in {"fill", "blur"}:
        raise ValueError("Le layout doit être 'fill' ou 'blur'.")

    webcam_regions = {
        "top-left": (0.02, 0.02, 0.25, 0.25),
        "top-right": (0.73, 0.02, 0.25, 0.25),
        "bottom-left": (0.02, 0.73, 0.25, 0.25),
        "bottom-right": (0.73, 0.73, 0.25, 0.25),
    }
    if webcam_zone not in {"none", *webcam_regions.keys()}:
        raise ValueError("La zone webcam doit être none ou l'un des quatre coins.")

    crop_x = max(0, min(100, int(crop_x))) / 100
    crop_y = max(0, min(100, int(crop_y))) / 100
    prefix = ""
    source_label = "0:v"
    if webcam_zone != "none":
        prefix = "[0:v]split=2[game_src][webcam_src];"
        source_label = "game_src"

    if layout == "fill":
        base = (
            f"[{source_label}]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:(in_w-out_w)*{crop_x:.3f}:(in_h-out_h)*{crop_y:.3f},setsar=1[base]"
        )
    else:
        base = (
            f"[{source_label}]split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur={blur}:10,setsar=1[bg];"
            f"[fgsrc]scale={width}:{height}:force_original_aspect_ratio=decrease,setsar=1[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]"
        )

    graph = prefix + base + ";"
    if dynamic_zoom and zoom_percent > 0:
        start = max(0.0, float(peak_timestamp) - 0.45)
        end = max(start + 0.25, float(peak_timestamp) + 0.85)
        zoom = 1.0 + max(0, min(20, int(zoom_percent))) / 100
        graph += (
            f"[base]zoompan=z='if(between(in_time,{start:.3f},{end:.3f}),"
            f"1+({zoom - 1.0:.3f})*sin(PI*(in_time-{start:.3f})/{max(0.25, end - start):.3f}),1.0)':"
            f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={fps},setsar=1[zoomed];"
        )
        current = "zoomed"
    else:
        current = "base"

    if webcam_zone != "none":
        crop_x_norm, crop_y_norm, crop_w_norm, crop_h_norm = webcam_regions[webcam_zone]
        webcam_width = max(140, int(width * 0.34))
        graph += (
            f"[webcam_src]crop=w=iw*{crop_w_norm:.3f}:h=ih*{crop_h_norm:.3f}:"
            f"x=iw*{crop_x_norm:.3f}:y=ih*{crop_y_norm:.3f},"
            f"scale={webcam_width}:-2,drawbox=x=0:y=0:w=iw:h=ih:color=white@0.95:t=5[webcam];"
        )
        overlay_x = "36" if webcam_zone.endswith("left") else "W-w-36"
        overlay_y = str(max(120, int(height * 0.20))) if webcam_zone.startswith("top") else f"H-h-{max(140, int(height * 0.18))}"
        graph += f"[{current}][webcam]overlay={overlay_x}:{overlay_y}:shortest=1[with_webcam];"
        current = "with_webcam"

    if ass_file:
        ass_option = f"ass=filename={_filter_path(ass_file, project_root)}"
        if fonts_dir:
            ass_option += f":fontsdir={_filter_path(fonts_dir, project_root)}"
        graph += f"[{current}]{ass_option},format=yuv420p[v]"
    else:
        graph += f"[{current}]format=yuv420p[v]"
    return graph'''


def patch_webcam_rendering(root: Path) -> None:
    renderer = root / "studio/web/short_renderer.py"
    text = renderer.read_text(encoding="utf-8-sig")
    start = text.index("def build_filter_complex(")
    end = text.index("\n\ndef build_render_command", start)
    current = text[start:end]
    if "webcam_zone: str = \"none\"" not in current:
        renderer.write_text(text[:start] + WEBCAM_FILTER + text[end:], encoding="utf-8")

    # Thread the selected corner through both command construction and rendering.
    replace_once(
        renderer,
        '    zoom_percent: int = 8,\n    duration: float | None = None,',
        '    zoom_percent: int = 8,\n    webcam_zone: str = "none",\n    duration: float | None = None,',
        "paramètre webcam build_render_command",
    )
    replace_once(
        renderer,
        '        zoom_percent=zoom_percent,\n    )\n    command = [resolve_executable(ffmpeg), "-hide_banner", "-y"]',
        '        zoom_percent=zoom_percent, webcam_zone=webcam_zone,\n    )\n    command = [resolve_executable(ffmpeg), "-hide_banner", "-y"]',
        "transmission webcam vers build_filter_complex",
    )
    replace_once(
        renderer,
        '    layout: str = "fill",\n    crop_x: int = 50,',
        '    layout: str = "fill",\n    webcam_zone: str = "none",\n    crop_x: int = 50,',
        "paramètre webcam render_vertical_short",
    )
    replace_once(
        renderer,
        '            zoom_percent=zoom_percent, duration=output_duration,',
        '            zoom_percent=zoom_percent, webcam_zone=webcam_zone, duration=output_duration,',
        "transmission webcam vers commande FFmpeg",
    )

    worker = root / "studio/web/worker.py"
    replace_once(
        worker,
        '                layout=str(options.get("layout", self.config.get("shorts", "layout", default="fill"))),\n                crop_x=int(options.get("crop_x", 50)),',
        '                layout=str(options.get("layout", self.config.get("shorts", "layout", default="fill"))),\n                webcam_zone=str(options.get("webcam_zone", "none")),\n                crop_x=int(options.get("crop_x", 50)),',
        "passage webcam depuis la file de rendu",
    )


def patch_webcam_api_and_ui(root: Path) -> None:
    app = root / "studio/web/app.py"
    replace_once(
        app,
        '    def _validate_highlight_window(start: float | None, end: float | None) -> tuple[float | None, float | None]:\n',
        '''    def _validate_webcam_zone(value: str) -> str:
        allowed = {"none", "top-left", "top-right", "bottom-left", "bottom-right"}
        zone = str(value or "none").strip().lower()
        if zone not in allowed:
            raise HTTPException(status_code=400, detail="Zone webcam invalide.")
        return zone

    def _validate_highlight_window(start: float | None, end: float | None) -> tuple[float | None, float | None]:
''',
        "validation des zones webcam",
    )

    for route_marker, form_signature, metadata_marker in (
        (
            '@app.post("/api/highlights/scan/url", status_code=202)',
            '        window_end: Annotated[str | None, Form()] = None,\n    ) -> dict:',
            '            "metadata": {"note": note.strip()[:1000]},',
        ),
        (
            '@app.post("/api/highlights/scan/upload", status_code=202)',
            '        window_end: Annotated[str | None, Form()] = None,\n    ) -> dict:',
            '            "rights_confirmed": True, "metadata": {"note": note.strip()[:1000], "file_size": written},',
        ),
    ):
        del route_marker
        if form_signature not in app.read_text(encoding="utf-8-sig"):
            raise SystemExit("Signature du formulaire Moments forts introuvable.")
        replace_once(
            app,
            form_signature,
            '        window_end: Annotated[str | None, Form()] = None,\n        webcam_zone: Annotated[str, Form()] = "none",\n    ) -> dict:',
            "champ webcam du formulaire",
        )
        # The helper call is inserted separately into each route by matching the
        # source-specific validation sequence.
        if "scan/url" in metadata_marker:
            pass

    # Validate the source-region input before persisting it with the scan.
    replace_once(
        app,
        '        start, end = _validate_highlight_window(start, end)\n        scan_id = uuid.uuid4().hex\n',
        '        start, end = _validate_highlight_window(start, end)\n        webcam_zone = _validate_webcam_zone(webcam_zone)\n        scan_id = uuid.uuid4().hex\n',
        "validation webcam route URL",
    )
    replace_once(
        app,
        '        start, end = _validate_highlight_window(start, end)\n        scan_id = uuid.uuid4().hex\n',
        '        start, end = _validate_highlight_window(start, end)\n        webcam_zone = _validate_webcam_zone(webcam_zone)\n        scan_id = uuid.uuid4().hex\n',
        "validation webcam route upload",
    )
    replace_once(
        app,
        '            "metadata": {"note": note.strip()[:1000]},',
        '            "metadata": {"note": note.strip()[:1000], "webcam_zone": webcam_zone},',
        "stockage webcam URL",
    )
    replace_once(
        app,
        '"rights_confirmed": True, "metadata": {"note": note.strip()[:1000], "file_size": written},',
        '"rights_confirmed": True, "metadata": {"note": note.strip()[:1000], "file_size": written, "webcam_zone": webcam_zone},',
        "stockage webcam upload",
    )

    replace_once(
        app,
        '        job_id = uuid.uuid4().hex\n        options = {\n            "layout": "fill", "crop_x": 50, "crop_y": 50, "dynamic_zoom": True, "zoom_percent": 8,',
        '        job_id = uuid.uuid4().hex\n        scan_metadata = scan.get("metadata") or {}\n        webcam_zone = str(scan_metadata.get("webcam_zone", "none"))\n        if webcam_zone not in {"none", "top-left", "top-right", "bottom-left", "bottom-right"}:\n            webcam_zone = "none"\n        options = {\n            "layout": "fill", "crop_x": 50, "crop_y": 50, "dynamic_zoom": True, "zoom_percent": 8,\n            "webcam_zone": webcam_zone,',
        "transmission webcam au job Short",
    )

    html = root / "studio/web/static/index.html"
    insert = '''<div class="form-grid"><label>Zone webcam dans la VOD <span>OPTIONNEL</span><select name="webcam_zone"><option value="none">Sans webcam</option><option value="top-left">Haut gauche</option><option value="top-right">Haut droite</option><option value="bottom-left">Bas gauche</option><option value="bottom-right">Bas droite</option></select></label></div>
              <small class="form-note">La zone choisie est extraite de la vidéo source puis superposée au gameplay dans le Short. Choisis le coin où la webcam apparaît dans la VOD.</small>
              '''
    replace_once(
        html,
        '              <small class="form-note">Laisse début et fin vides pour analyser toute la vidéo.',
        '              ' + insert + '<small class="form-note">Laisse début et fin vides pour analyser toute la vidéo.',
        "sélecteur webcam du formulaire local",
    )
    replace_once(
        html,
        '              <small class="form-note">Les temps sont en secondes : 3 600 = 01:00:00. Pour une VOD, sélectionne une plage afin d\\'éviter un téléchargement massif.',
        '              ' + insert + '<small class="form-note">Les temps sont en secondes : 3 600 = 01:00:00. Pour une VOD, sélectionne une plage afin d\\'éviter un téléchargement massif.',
        "sélecteur webcam du formulaire Twitch",
    )


def patch_tests(root: Path) -> None:
    (root / "tests/test_process.py").write_text(
        '''from __future__ import annotations

import subprocess

from studio import process


def test_run_quiet_does_not_add_windows_flags_on_non_windows(monkeypatch) -> None:
    monkeypatch.setattr(process.os, "name", "posix")
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(process.subprocess, "run", fake_run)
    process.run_quiet(["tool", "--version"])

    assert "creationflags" not in captured


def test_run_quiet_suppresses_windows_console(monkeypatch) -> None:
    monkeypatch.setattr(process.os, "name", "nt")
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(process.subprocess, "run", fake_run)
    process.run_quiet(["tool", "--version"])

    expected = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    assert captured["creationflags"] == expected
''',
        encoding="utf-8",
    )

    (root / "tests/test_webcam_renderer.py").write_text(
        '''from __future__ import annotations

import pytest

from studio.web.short_renderer import build_filter_complex


@pytest.mark.parametrize("zone", ["top-left", "top-right", "bottom-left", "bottom-right"])
def test_webcam_graph_splits_source_and_overlays_selected_corner(zone: str) -> None:
    graph = build_filter_complex(webcam_zone=zone, dynamic_zoom=False)

    assert "[0:v]split=2[game_src][webcam_src]" in graph
    assert "[webcam_src]crop=" in graph
    assert "overlay=" in graph
    assert "[with_webcam]" in graph
    assert graph.endswith("[v]")


def test_webcam_graph_can_be_disabled() -> None:
    graph = build_filter_complex(webcam_zone="none", dynamic_zoom=False)

    assert "webcam_src" not in graph
    assert "overlay=" not in graph
    assert "[0:v]scale=" in graph


def test_webcam_graph_rejects_unknown_zone() -> None:
    with pytest.raises(ValueError, match="zone webcam"):
        build_filter_complex(webcam_zone="center")
''',
        encoding="utf-8",
    )


def apply(root: Path) -> None:
    root = root.resolve()
    patch_highlight_scoring(root)
    patch_quiet_subprocesses(root)
    patch_webcam_rendering(root)
    patch_webcam_api_and_ui(root)
    patch_tests(root)

    # Update the Windows update manifest so release notes are kept in the
    # rollback and replacement package.
    for relative in (
        "installer/apply_update.ps1",
        "installer/update_from_archive.ps1",
        "installer/install.ps1",
    ):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        if "'NOTES-v0.5.0.txt', 'VERIFICATION-v0.5.0.md'" not in text:
            anchor = "'NOTES-v0.4.2.txt', 'VERIFICATION-v0.4.2.md'"
            if anchor not in text:
                raise SystemExit(f"Liste de fichiers root absente dans {relative}")
            text = text.replace(
                anchor,
                anchor + ", 'NOTES-v0.5.0.txt', 'VERIFICATION-v0.5.0.md'",
                1,
            )
        path.write_bytes(
            b"\\xef\\xbb\\xbf"
            + text.replace("\\r\\n", "\\n").replace("\\n", "\\r\\n").encode("utf-8")
        )

    (root / "VERSION.txt").write_text(
        "GTA Ranked Studio\\nVersion: 0.5.0\\n",
        encoding="utf-8",
    )
    set_version(
        root / "pyproject.toml",
        r'^(\\s*version\\s*=\\s*)["\\'][^"\\']+["\\'](\\s*(?:#.*)?)$',
        r'\\g<1>"0.5.0"\\g<2>',
        "pyproject.toml",
    )
    set_version(
        root / "config.yaml.default",
        r'^(\\s{2}version:\\s*)[^\\s#]+(\\s*(?:#.*)?)$',
        r'\\g<1>0.5.0\\g<2>',
        "config.yaml.default",
    )

    (root / "NOTES-v0.5.0.txt").write_text(
        """GTA Ranked Studio v0.5.0

Améliorations des Moments forts :
- Les passages candidats sont désormais évalués sur plusieurs durées (25, 35, 45 et 60 secondes).
- Les candidats retenus sont classés par score et ne se chevauchent plus, avec un intervalle minimal entre deux passages.
- Le pipeline Shorts existant reste utilisé pour chaque passage sélectionné.

Montage webcam :
- Possibilité d'extraire la webcam intégrée à la VOD depuis l'un des quatre coins de l'image.
- La webcam est superposée au gameplay dans le rendu vertical 9:16.
- Le choix du coin est fait au moment de l'analyse et conservé lors de la création du Short.

Windows :
- FFmpeg, FFprobe, Whisper et les diagnostics sont lancés sans créer de fenêtre console parasite.
- Les sorties et erreurs restent capturées pour les journaux locaux.

Les vidéos, modèles IA, projets, réglages et données locales sont préservés.
La sélection webcam est basée sur une zone prédéfinie dans un coin de l'image, pas sur une détection automatique de visage.
""",
        encoding="utf-8",
    )
    (root / "VERIFICATION-v0.5.0.md").write_text(
        """# Vérification v0.5.0

- Scoring adaptatif testé sur 25, 35, 45 et 60 secondes.
- La sélection finale vérifie l'absence de chevauchement et conserve le classement par score.
- Tests du filtre webcam pour les quatre coins, le mode désactivé et une valeur invalide.
- Tests du wrapper de sous-processus sur Windows et les autres plateformes.
- Les tests d'intégration FFmpeg de la suite vérifient le rendu MP4 vertical.
- La caméra est découpée à partir d'une zone de coin choisie dans le formulaire. Il n'y a pas de détection automatique de visage dans cette version.
""",
        encoding="utf-8",
    )

    for relative in ("README.md", "docs/UPDATES.md"):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        if "## v0.5.0 : moments forts adaptatifs" not in text:
            text += """

## v0.5.0 : moments forts adaptatifs et webcam

Le scan compare plusieurs durées de passages, de 25 à 60 secondes, puis sélectionne les candidats les mieux classés sans chevauchement. Lors de l'analyse, tu peux indiquer dans quel coin de la VOD se trouve la webcam. Cette zone est ensuite extraite et superposée au gameplay dans le rendu vertical. Les processus externes utilisés sous Windows ne créent plus de fenêtres console parasites ; leurs sorties restent consignées dans les logs.
"""
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.5.0.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
