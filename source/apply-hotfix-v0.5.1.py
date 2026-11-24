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
            f"Patch v0.5.1 impossible : {count} occurrence(s) du bloc « {label} » dans {path}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"Patch v0.5.1 impossible : bloc « {label} » absent dans {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def patch_renderer(root: Path) -> None:
    renderer = root / "studio/web/short_renderer.py"
    text = renderer.read_text(encoding="utf-8-sig")
    start = text.index("def build_filter_complex(")
    end = text.index("\n\ndef build_render_command", start)
    replacement = r'''def build_filter_complex(
    width: int = 1080,
    height: int = 1920,
    blur: int = 28,
    *,
    layout: str = "blur",
    crop_x: int = 50,
    crop_y: int = 50,
    ass_file: Path | None = None,
    fonts_dir: Path | None = None,
    project_root: Path | None = None,
    dynamic_zoom: bool = False,
    peak_timestamp: float = 0.0,
    fps: int = 30,
    zoom_percent: int = 0,
    webcam_zone: str = "none",
) -> str:
    """Build a vertical canvas while preserving the complete source frame.

    The legacy webcam_zone argument is accepted for compatibility with jobs
    created by v0.5.0, but no webcam crop or extraction is performed.
    """
    if width <= 0 or height <= 0:
        raise ValueError("Les dimensions de sortie doivent être positives.")
    if layout not in {"fill", "blur"}:
        raise ValueError("Le layout doit être 'fill' ou 'blur'.")

    crop_x = max(0, min(100, int(crop_x))) / 100
    crop_y = max(0, min(100, int(crop_y))) / 100
    if layout == "fill":
        base = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:(in_w-out_w)*{crop_x:.3f}:(in_h-out_h)*{crop_y:.3f},setsar=1[base]"
        )
    else:
        base = (
            f"[0:v]split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur={blur}:10,setsar=1[bg];"
            f"[fgsrc]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"setsar=1[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]"
        )

    graph = base + ";"
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

    if ass_file:
        ass_option = f"ass=filename={_filter_path(ass_file, project_root)}"
        if fonts_dir:
            ass_option += f":fontsdir={_filter_path(fonts_dir, project_root)}"
        graph += f"[{current}]{ass_option},format=yuv420p[v]"
    else:
        graph += f"[{current}]format=yuv420p[v]"
    return graph'''
    if replacement not in text[start:end]:
        renderer.write_text(text[:start] + replacement + text[end:], encoding="utf-8")

    replace_all(renderer, 'layout: str = "fill"', 'layout: str = "blur"', "format vidéo par défaut")
    replace_all(renderer, "dynamic_zoom: bool = True", "dynamic_zoom: bool = False", "zoom désactivé par défaut")
    replace_all(renderer, "zoom_percent: int = 8", "zoom_percent: int = 0", "puissance de zoom par défaut")
    replace_all(
        renderer,
        "zoom_percent=zoom_percent, webcam_zone=webcam_zone,",
        "zoom_percent=zoom_percent,",
        "suppression de la transmission de la zone webcam au filtre",
    )


def patch_highlight_defaults(root: Path) -> None:
    app = root / "studio/web/app.py"
    text = app.read_text(encoding="utf-8-sig")
    old = '''        options = {
            "layout": "fill", "crop_x": 50, "crop_y": 50, "dynamic_zoom": True, "zoom_percent": 8,
            "captions_enabled": True, "brand_enabled": True, "auto_trim_enabled": False, "sfx_enabled": True,
            "hook_text": "", "context_text": "",
            "source_range": {"start": media_start, "end": media_end},
        }'''
    new = '''        options = {
            "layout": "blur", "crop_x": 50, "crop_y": 50, "dynamic_zoom": False, "zoom_percent": 0,
            "captions_enabled": True, "brand_enabled": True, "auto_trim_enabled": False, "sfx_enabled": True,
            "hook_text": "", "context_text": "",
            "source_range": {"start": media_start, "end": media_end},
        }'''
    replace_once(app, old, new, "rendu des passages candidats sans recadrage ni zoom")


def patch_ui(root: Path) -> None:
    html = root / "studio/web/static/index.html"
    text = html.read_text(encoding="utf-8-sig")

    webcam_pattern = (
        r'\s*<div class="form-grid"><label>Zone webcam dans la VOD.*?'
        r'Choisis le coin où la webcam apparaît dans la VOD\.</small>\s*'
    )
    text, count = re.subn(webcam_pattern, "\n              ", text, flags=re.DOTALL)
    if count != 2:
        if "Zone webcam dans la VOD" in text:
            raise SystemExit(f"Suppression du sélecteur webcam incomplète : {count} occurrence(s).")

    old_layout = (
        '<select name="layout"><option value="fill" selected>Plein écran vertical 9:16</option>'
        '<option value="blur">Vidéo entière + fond flouté</option></select>'
        '<small>Le plein écran recadre les côtés d\'une vidéo paysage.</small>'
    )
    new_layout = (
        '<select name="layout"><option value="fill">Plein écran recadré 9:16</option>'
        '<option value="blur" selected>Vidéo entière + fond flouté</option></select>'
        '<small>Toute l’image d’origine est conservée, sans zoom ni recadrage.</small>'
    )
    if old_layout in text:
        text = text.replace(old_layout, new_layout)
    elif new_layout not in text:
        raise SystemExit("Options de format vidéo introuvables dans index.html.")

    text = text.replace(
        '<output data-zoom-output>8 %</output><input type="range" name="zoom_percent" min="0" max="20" value="8" data-zoom-slider>',
        '<output data-zoom-output>0 %</output><input type="range" name="zoom_percent" min="0" max="20" value="0" data-zoom-slider>',
    )
    text = text.replace(
        '<input type="checkbox" name="dynamic_zoom" checked data-option-checkbox>',
        '<input type="checkbox" name="dynamic_zoom" data-option-checkbox>',
    )
    text = text.replace(
        "Le montage remplit l’écran en 9:16, peut resserrer les clips longs autour du moment fort, ajoute les finitions et prépare tes captions si Whisper est installé.",
        "Le montage conserve toute l’image d’origine au centre du format 9:16, avec un fond flouté pour remplir l’écran. Le zoom dynamique est désactivé par défaut.",
    )
    html.write_text(text, encoding="utf-8")


def patch_tests(root: Path) -> None:
    web_test = root / "tests/test_web.py"
    text = web_test.read_text(encoding="utf-8-sig")
    old = '''def test_default_vertical_filter_fills_the_9_16_frame():
    graph = build_filter_complex(1080, 1920)
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in graph
    assert "crop=1080:1920" in graph
    assert "boxblur" not in graph
    assert "zoompan" in graph'''
    new = '''def test_default_vertical_filter_preserves_the_complete_landscape_source():
    graph = build_filter_complex(1080, 1920)
    assert "split=2[bgsrc][fgsrc]" in graph
    assert "force_original_aspect_ratio=decrease" in graph
    assert "boxblur" in graph
    assert "overlay=(W-w)/2:(H-h)/2" in graph
    assert "zoompan" not in graph'''
    replace_once(web_test, old, new, "test du format vertical par défaut")

    webcam_test = root / "tests/test_webcam_renderer.py"
    webcam_test.write_text(
        '''from __future__ import annotations

from studio.web.short_renderer import build_filter_complex


def test_legacy_webcam_zone_does_not_extract_or_overlay_a_second_video() -> None:
    baseline = build_filter_complex(layout="blur", dynamic_zoom=False)
    legacy_option = build_filter_complex(
        layout="blur", dynamic_zoom=False, webcam_zone="bottom-left"
    )

    assert legacy_option == baseline
    assert "[0:v]split=2[bgsrc][fgsrc]" in legacy_option
    assert "[webcam_src]" not in legacy_option
    assert "overlay=(W-w)/2:(H-h)/2" in legacy_option
    assert "boxblur" in legacy_option
''',
        encoding="utf-8",
    )

    render_test = root / "tests/test_render_integration.py"
    render_text = render_test.read_text(encoding="utf-8-sig")
    render_text = render_text.replace('        webcam_zone="top-right",\n', "")
    if 'layout="blur"' not in render_text:
        render_text = render_text.replace(
            "        dynamic_zoom=True,\n",
            '        layout="blur",\n        dynamic_zoom=False,\n',
            1,
        )
    render_test.write_text(render_text, encoding="utf-8")


def patch_release_docs(root: Path) -> None:
    for relative in (
        "installer/apply_update.ps1",
        "installer/update_from_archive.ps1",
        "installer/install.ps1",
    ):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        entry = "'NOTES-v0.5.1.txt', 'VERIFICATION-v0.5.1.md'"
        if entry not in text:
            anchor = "'NOTES-v0.5.0.txt', 'VERIFICATION-v0.5.0.md'"
            if anchor not in text:
                raise SystemExit(f"Liste de fichiers root absente dans {relative}")
            text = text.replace(anchor, anchor + ", " + entry, 1)
        path.write_text(text, encoding="utf-8-sig", newline="\r\n")

    (root / "VERSION.txt").write_text(
        "GTA Ranked Studio\nVersion: 0.5.1\n",
        encoding="utf-8",
    )
    replace_once(
        root / "pyproject.toml",
        'version = "0.5.0"',
        'version = "0.5.1"',
        "version pyproject.toml",
    )
    replace_once(
        root / "config.yaml.default",
        "  version: 0.5.0",
        "  version: 0.5.1",
        "version config.yaml.default",
    )

    (root / "NOTES-v0.5.1.txt").write_text(
        """GTA Ranked Studio v0.5.1

Amélioration du rendu vertical :
- Le rendu par défaut conserve toute l'image source 16:9, sans recadrer les côtés.
- L'image complète est centrée dans la vidéo 9:16.
- Une version agrandie et floutée de la source remplit l'arrière-plan.
- Le zoom dynamique est désactivé par défaut afin de ne pas rogner l'image.
- La webcam déjà incrustée dans la VOD reste visible à son emplacement d'origine. Aucune extraction ni détection webcam n'est effectuée.

Les options de cadrage et de zoom restent disponibles pour les utilisateurs qui souhaitent personnaliser manuellement un autre rendu. Les vidéos, modèles IA, projets, réglages et données locales sont préservés.
""",
        encoding="utf-8",
    )
    (root / "VERIFICATION-v0.5.1.md").write_text(
        """# Vérification v0.5.1

- Le filtre vertical par défaut utilise la source complète comme couche centrale.
- Le fond agrandi et flouté remplit les dimensions 1080 × 1920 sans recadrer la couche principale.
- Le zoom dynamique est désactivé par défaut.
- L'ancienne option webcam est ignorée pour compatibilité avec les analyses créées en v0.5.0 ; aucun second crop ni overlay webcam n'est généré.
- Le test d'intégration vérifie le rendu MP4 vertical avec le mode vidéo entière + fond flouté.
""",
        encoding="utf-8",
    )

    for relative in ("README.md", "docs/UPDATES.md"):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        marker = "## v0.5.1 : rendu vertical sans recadrage"
        if marker not in text:
            text += """

## v0.5.1 : rendu vertical sans recadrage

Le rendu par défaut conserve l'image source entière, centrée dans le format 9:16, avec une copie agrandie et floutée en arrière-plan. Le zoom dynamique est désactivé par défaut. La webcam incrustée dans la VOD reste visible dans l'image complète ; le logiciel ne l'extrait plus séparément.
"""
        path.write_text(text, encoding="utf-8")


def apply(root: Path) -> None:
    root = root.resolve()
    patch_renderer(root)
    patch_highlight_defaults(root)
    patch_ui(root)
    patch_tests(root)
    patch_release_docs(root)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.5.1.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
