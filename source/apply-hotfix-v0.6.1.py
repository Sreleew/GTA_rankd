from __future__ import annotations

import sys
from pathlib import Path


def apply(root: Path) -> None:
    root = root.resolve()
    html = root / "studio/web/static/index.html"
    text = html.read_text(encoding="utf-8-sig")
    bad = r"\n                  <label>Voix à sous-titrer"
    good = "\n                  <label>Voix à sous-titrer"
    if bad in text:
        text = text.replace(bad, good)
    elif good not in text:
        raise SystemExit("Le sélecteur de voix à corriger est introuvable.")
    html.write_text(text, encoding="utf-8")

    tests = root / "tests/test_voice_mode_ui.py"
    tests.write_text(
        '''from pathlib import Path


def test_voice_mode_select_is_separated_by_real_html_whitespace() -> None:
    html = Path("studio/web/static/index.html").read_text(encoding="utf-8-sig")
    assert "\\\\n                  <label>Voix à sous-titrer" not in html
    assert "\\n                  <label>Voix à sous-titrer" in html
    assert html.count('name="caption_voice_mode"') == 2
''',
        encoding="utf-8",
    )

    for relative in (
        "installer/apply_update.ps1",
        "installer/update_from_archive.ps1",
        "installer/install.ps1",
    ):
        path = root / relative
        content = path.read_text(encoding="utf-8-sig")
        entry = "'NOTES-v0.6.1.txt', 'VERIFICATION-v0.6.1.md'"
        if entry not in content:
            anchor = "'NOTES-v0.6.0.txt', 'VERIFICATION-v0.6.0.md'"
            if anchor not in content:
                raise SystemExit(f"Liste de fichiers root absente dans {relative}")
            content = content.replace(anchor, anchor + ", " + entry, 1)
        path.write_text(content, encoding="utf-8-sig", newline="\r\n")

    (root / "VERSION.txt").write_text(
        "GTA Ranked Studio\nVersion: 0.6.1\n",
        encoding="utf-8",
    )
    pyproject = root / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8-sig")
    content = content.replace('version = "0.6.0"', 'version = "0.6.1"', 1)
    pyproject.write_text(content, encoding="utf-8")

    config = root / "config.yaml.default"
    content = config.read_text(encoding="utf-8-sig")
    content = content.replace("  version: 0.6.0", "  version: 0.6.1", 1)
    config.write_text(content, encoding="utf-8")

    (root / "NOTES-v0.6.1.txt").write_text(
        """GTA Ranked Studio v0.6.1

Correctif de présentation :
- Correction de l'espacement HTML du sélecteur « Voix à sous-titrer ».
- Aucun changement sur le moteur de diarisation, les réglages ou les modèles locaux.
""",
        encoding="utf-8",
    )
    (root / "VERIFICATION-v0.6.1.md").write_text(
        """# Vérification v0.6.1

- Test de présence des deux sélecteurs de voix.
- Test de l'espacement HTML réel, sans séquence littérale \\\\n visible.
- Le moteur v0.6.0, ses seuils de sécurité et les fonctions de téléchargement sont inchangés.
""",
        encoding="utf-8",
    )
    for relative in ("README.md", "docs/UPDATES.md"):
        path = root / relative
        content = path.read_text(encoding="utf-8-sig")
        marker = "## v0.6.1 : finition du formulaire de voix"
        if marker not in content:
            content += """

## v0.6.1 : finition du formulaire de voix

Correction mineure de l'espacement du sélecteur « Voix à sous-titrer ». Aucun changement fonctionnel sur la diarisation ou le rendu.
"""
        path.write_text(content, encoding="utf-8")
    readme = root / "README.md"
    content = readme.read_text(encoding="utf-8-sig")
    content = content.replace("Dernière version stable : **0.6.0**.", "Dernière version stable : **0.6.1**.")
    readme.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.6.1.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
