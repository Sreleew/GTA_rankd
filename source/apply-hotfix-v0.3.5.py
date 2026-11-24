from __future__ import annotations

import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, *, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"Patch v0.3.5 impossible : bloc introuvable ({label}) dans {path}")
    if text.count(old) != 1:
        raise SystemExit(f"Patch v0.3.5 ambigu : {text.count(old)} occurrences ({label}) dans {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def apply(project_root: Path) -> None:
    project_root = project_root.resolve()
    transcribe = project_root / "studio/web/transcribe.py"
    if not transcribe.is_file():
        raise SystemExit("Dossier source GTA Ranked Studio invalide.")

    replace_once(
        transcribe,
        '    dtw_supported = "-dtw" in help_text and "-ojf" in help_text\n',
        '    # whisper.cpp désactive DTW si Flash Attention reste actif : -nfa est requis.\n'
        '    dtw_supported = all(flag in help_text for flag in ("-dtw", "-ojf", "-nfa"))\n',
        label="détection DTW + no-flash-attn",
    )
    replace_once(
        transcribe,
        """        "message": "Moteur Whisper exécutable." + (
            " DTW disponible." if dtw_supported else " DTW absent, les captions resteront par segment."
        ),
""",
        """        "message": "Moteur Whisper exécutable." + (
            " DTW disponible (Flash Attention désactivé pendant la transcription)."
            if dtw_supported
            else " DTW indisponible : le binaire doit exposer -dtw, -ojf et -nfa."
        ),
""",
        label="diagnostic explicite DTW",
    )
    replace_once(
        transcribe,
        '        supports_dtw = "-dtw" in help_text and "-ojf" in help_text\n',
        '        supports_dtw = all(flag in help_text for flag in ("-dtw", "-ojf", "-nfa"))\n',
        label="détection DTW dans le traitement",
    )
    replace_once(
        transcribe,
        '        command.extend(["-dtw", dtw_model_preset, "-ojf"])\n',
        '        # whisper.cpp désactive lui-même DTW lorsque Flash Attention reste actif.\n'
        '        command.extend(["-dtw", dtw_model_preset, "-ojf", "-nfa"])\n',
        label="désactivation de Flash Attention",
    )

    tests = project_root / "tests/test_transcribe.py"
    replace_once(
        tests,
        "            print('-ojf --output-json-full')\n",
        "            print('-ojf --output-json-full')\n"
        "            print('-nfa --no-flash-attn')\n",
        label="fixture CLI DTW",
    )
    replace_once(
        tests,
        "        if '-dtw' not in args or '-ojf' not in args:\n",
        "        if '-dtw' not in args or '-ojf' not in args or '-nfa' not in args:\n",
        label="assertion de commande DTW",
    )
    replace_once(
        tests,
        "            print('-dtw --dtw-model -ojf --output-json-full --list-devices')\n",
        "            print('-dtw --dtw-model -ojf --output-json-full -nfa --no-flash-attn --list-devices')\n",
        label="fixture diagnostic DTW",
    )
    extra_test = (
        "\n\ndef test_inspect_whisper_cli_requires_no_flash_attention_for_dtw(tmp_path: Path):\n"
        "    import sys\n"
        "    from studio.web.transcribe import inspect_whisper_cli\n"
        "    binary = tmp_path / 'fake-whisper-dtw-no-nfa.py'\n"
        "    binary.write_text(\n"
        "        '#!' + sys.executable + '\\n'\n"
        "        'import sys\\n'\n"
        "        \"if '--help' in sys.argv: print('-dtw MODEL --dtw MODEL -ojf --output-json-full')\\n\"\n"
        "        'raise SystemExit(0)\\n', encoding='utf-8')\n"
        "    binary.chmod(0o755)\n"
        "    result = inspect_whisper_cli(binary)\n"
        "    assert result['available'] is True\n"
        "    assert result['dtw_supported'] is False\n"
        "    assert '-nfa' in result['message']\n"
    )
    test_text = tests.read_text(encoding="utf-8-sig")
    if "test_inspect_whisper_cli_requires_no_flash_attention_for_dtw" not in test_text:
        tests.write_text(test_text + extra_test, encoding="utf-8")

    (project_root / "VERSION.txt").write_text("GTA Ranked Studio\nVersion: 0.3.5\n", encoding="utf-8")

    pyproject = project_root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    if 'version = "0.3.4"' in text:
        text = text.replace('version = "0.3.4"', 'version = "0.3.5"', 1)
    elif 'version = "0.3.5"' not in text:
        raise SystemExit("Version pyproject.toml inattendue.")
    pyproject.write_text(text, encoding="utf-8")

    config = project_root / "config.yaml.default"
    ctext = config.read_text(encoding="utf-8")
    if "  version: 0.3.4\n" in ctext:
        ctext = ctext.replace("  version: 0.3.4\n", "  version: 0.3.5\n", 1)
    elif "  version: 0.3.5\n" not in ctext:
        raise SystemExit("Version config.yaml.default inattendue.")
    config.write_text(ctext, encoding="utf-8")

    for relative in ("installer/apply_update.ps1", "installer/update_from_archive.ps1", "installer/install.ps1"):
        path = project_root / relative
        content = path.read_text(encoding="utf-8-sig")
        if "NOTES-v0.3.5.txt" not in content:
            lines = content.splitlines()
            for index, line in enumerate(lines):
                if "'VERSION.txt'" in line and "NOTES-v0.3." in line:
                    line = line.rstrip()
                    if line.endswith("'"):
                        line = line[:-1] + "', 'NOTES-v0.3.5.txt', 'VERIFICATION-v0.3.5.md'"
                    lines[index] = line
                    break
            else:
                raise SystemExit(f"Liste de fichiers de mise à jour introuvable dans {relative}")
            updated = "\r\n".join(lines) + "\r\n"
            path.write_bytes(b"\xef\xbb\xbf" + updated.encode("utf-8"))

    (project_root / "NOTES-v0.3.5.txt").write_text(
        "GTA Ranked Studio v0.3.5\n\n"
        "Correctif Whisper DTW :\n"
        "- Désactive explicitement Flash Attention avec -nfa lorsque DTW est demandé.\n"
        "- Le diagnostic exige les options -dtw, -ojf et -nfa.\n"
        "- Aucun changement du modèle large-v3-turbo, des données ou des médias.\n",
        encoding="utf-8",
    )
    (project_root / "VERIFICATION-v0.3.5.md").write_text(
        "# Vérification v0.3.5\n\n"
        "## Cause corrigée\n"
        "whisper.cpp désactive dtw_token_timestamps quand Flash Attention est activé. "
        "Le CLI était lancé avec -dtw mais sans -nfa.\n\n"
        "## Correctif\n"
        "Le client vérifie -dtw, -ojf et -nfa dans --help, puis transmet -dtw large.v3.turbo -ojf -nfa.\n\n"
        "## Validation\n"
        "Tests unitaires de construction de commande et de diagnostic. "
        "Un nouveau transcript.json sur Windows doit confirmer t_dtw non négatif pour les tokens parlés.\n",
        encoding="utf-8",
    )

    readme = project_root / "README.md"
    rtext = readme.read_text(encoding="utf-8-sig")
    rtext = rtext.replace("> Version du paquet : **0.3.4**.", "> Version du paquet : **0.3.5**.", 1)
    rtext += (
        "\n\n## v0.3.5 : correction DTW Whisper\n\n"
        "Le moteur whisper.cpp est désormais lancé avec -nfa lorsqu'il calcule les timestamps DTW, "
        "car Flash Attention et DTW ne peuvent pas être actifs simultanément. "
        "Le diagnostic vérifie aussi que le binaire expose cette option.\n"
    )
    readme.write_text(rtext, encoding="utf-8")

    docs = project_root / "docs/UPDATES.md"
    dtext = docs.read_text(encoding="utf-8-sig")
    dtext += (
        "\n\n## v0.3.5 : Whisper DTW\n\n"
        "Le diagnostic exige les options -dtw, -ojf et -nfa. Le traitement ajoute -nfa "
        "pour désactiver Flash Attention et laisser whisper.cpp calculer les timestamps DTW. "
        "La validation finale consiste à confirmer des valeurs t_dtw non négatives sur les tokens parlés.\n"
    )
    docs.write_text(dtext, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.3.5.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
