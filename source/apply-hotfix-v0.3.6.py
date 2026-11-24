from __future__ import annotations
import sys
from pathlib import Path

def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"Patch v0.3.6 : bloc introuvable ({label}) dans {path}")
    if text.count(old) != 1:
        raise SystemExit(f"Patch v0.3.6 : {text.count(old)} occurrences ({label}) dans {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

def apply(root: Path) -> None:
    root = root.resolve()
    updater = root / "studio/web/updater.py"
    old = '''            creation_flags = 0
            if os.name == "nt":
                creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
                ) | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            subprocess.Popen(
                args,
                cwd=str(self.project_root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=creation_flags,
            )
'''
    new = '''            # Keep a bootstrap log before PowerShell starts. v0.3.4/v0.3.5
            # discarded all child output, hiding startup and parse errors.
            log_path.parent.mkdir(parents=True, exist_ok=True)
            console_log_path = updater_home / "powershell-output.log"
            with log_path.open("a", encoding="utf-8") as bootstrap_log:
                bootstrap_log.write(
                    f"\\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Python updater: launching PowerShell for v{release['version']}\\n"
                )
                bootstrap_log.write(f"Project root: {self.project_root}\\n")
                bootstrap_log.flush()
                creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
                with console_log_path.open("a", encoding="utf-8") as powershell_log:
                    powershell_process = subprocess.Popen(
                        args,
                        cwd=str(self.project_root),
                        stdin=subprocess.DEVNULL,
                        stdout=powershell_log,
                        stderr=subprocess.STDOUT,
                        close_fds=True,
                        creationflags=creation_flags,
                    )
                    bootstrap_log.write(f"PowerShell process started: PID {powershell_process.pid}\\n")
                    bootstrap_log.flush()
            # If PowerShell exits immediately (for example because of a parse
            # error), keep GTA Ranked Studio alive and show the diagnostic paths.
            time.sleep(1.0)
            if powershell_process.poll() is not None:
                raise RuntimeError(
                    f"PowerShell s'est arrêté immédiatement (code {powershell_process.returncode}). "
                    f"Consulte {console_log_path} et {log_path}."
                )
'''
    replace_once(updater, old, new, "journal bootstrap PowerShell")

    ps = root / "installer/apply_update.ps1"
    text = ps.read_text(encoding="utf-8-sig")
    text = text.replace("New-Object 'System.Collections.Generic.List[string]'", "@()")
    pairs = [
        ("[void]$backedDirectories.Add($directoryName)", "$backedDirectories += $directoryName"),
        ("[void]$backedFiles.Add($fileName)", "$backedFiles += $fileName"),
        ("[void]$replacedDirectories.Add($directoryName)", "$replacedDirectories += $directoryName"),
        ("[void]$replacedFiles.Add($fileName)", "$replacedFiles += $fileName"),
        ("$backedDirectories.Contains($directoryName)", "$directoryName -in $backedDirectories"),
        ("$backedFiles.Contains($fileName)", "$fileName -in $backedFiles"),
    ]
    for before, after in pairs:
        text = text.replace(before, after)
    text = text.replace(
        "'NOTES-v0.3.5.txt', 'VERIFICATION-v0.3.5.md'",
        "'NOTES-v0.3.5.txt', 'VERIFICATION-v0.3.5.md', 'NOTES-v0.3.6.txt', 'VERIFICATION-v0.3.6.md'",
    )
    if "'NOTES-v0.3.6.txt'" not in text:
        raise SystemExit("Liste rootFiles de apply_update.ps1 non mise à jour")
    ps.write_bytes(b"\xef\xbb\xbf" + text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))

    for relative in ("installer/update_from_archive.ps1", "installer/install.ps1"):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        text = text.replace(
            "'NOTES-v0.3.5.txt', 'VERIFICATION-v0.3.5.md'",
            "'NOTES-v0.3.5.txt', 'VERIFICATION-v0.3.5.md', 'NOTES-v0.3.6.txt', 'VERIFICATION-v0.3.6.md'",
        )
        path.write_bytes(b"\xef\xbb\xbf" + text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))

    (root / "VERSION.txt").write_text("GTA Ranked Studio\nVersion: 0.3.6\n", encoding="utf-8")
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8").replace('version = "0.3.5"', 'version = "0.3.6"', 1)
    pyproject.write_text(text, encoding="utf-8")
    config = root / "config.yaml.default"
    text = config.read_text(encoding="utf-8").replace("  version: 0.3.5\n", "  version: 0.3.6\n", 1)
    config.write_text(text, encoding="utf-8")

    (root / "NOTES-v0.3.6.txt").write_text(
        """GTA Ranked Studio v0.3.6

Correctif prioritaire de l'updater Windows :
- Création de last-update.log par Python avant le lancement PowerShell.
- Capture de stdout/stderr PowerShell dans powershell-output.log.
- Détection d'un arrêt immédiat de PowerShell sans fermer GTA Ranked Studio.
- Remplacement des collections génériques PowerShell par des tableaux compatibles Windows PowerShell 5.1.
- Conservation du correctif Whisper DTW v0.3.5.
- Les modèles, vidéos, projets, configuration et environnement Python restent préservés.
""",
        encoding="utf-8",
    )
    (root / "VERIFICATION-v0.3.6.md").write_text(
        """# Vérification v0.3.6

- Le journal bootstrap est créé avant le lancement de PowerShell.
- La sortie console PowerShell est conservée séparément.
- Le processus Python détecte un exit immédiat de PowerShell avant de demander l'arrêt du serveur.
- L'installateur évite la création de Generic.List avant le bloc try et conserve la sauvegarde/restauration.
- Aucun remplacement de config.yaml, .venv, data, inbox, out, logs, models, tools ou médias utilisateur.

L'exécution réelle du script PowerShell et le redémarrage restent à valider sur Windows. En cas d'échec, last-update.log et powershell-output.log doivent maintenant être disponibles.
""",
        encoding="utf-8",
    )

    for relative in ("README.md", "docs/UPDATES.md"):
        path = root / relative
        text = path.read_text(encoding="utf-8-sig")
        text += """
        
## v0.3.6 : journalisation de l'updater Windows

Le client initialise last-update.log avant le lancement PowerShell et capture stdout/stderr dans powershell-output.log. Il détecte un arrêt immédiat du processus sans fermer le serveur local. Le script d'installation utilise des tableaux simples compatibles Windows PowerShell 5.1. Le correctif DTW v0.3.5 reste inclus.
"""
        path.write_text(text, encoding="utf-8")

    tests = root / "tests/test_updates.py"
    text = tests.read_text(encoding="utf-8-sig")
    text += '''

def test_updater_captures_powershell_output_and_creates_bootstrap_log() -> None:
    source = (Path(__file__).resolve().parents[1] / "studio" / "web" / "updater.py").read_text(encoding="utf-8")
    assert "powershell-output.log" in source
    assert "stdout=powershell_log" in source
    assert "stderr=subprocess.STDOUT" in source
    assert "Python updater: launching PowerShell" in source
    assert "s'est arrêté immédiatement" in source


def test_powershell_update_script_uses_windows_powershell_compatible_arrays() -> None:
    script = (Path(__file__).resolve().parents[1] / "installer" / "apply_update.ps1").read_text(encoding="utf-8-sig")
    assert "New-Object 'System.Collections.Generic.List[string]'" not in script
    assert "$backedDirectories += $directoryName" in script
    assert "Tentative de restauration" in script
    assert "NOTES-v0.3.6.txt" in script
'''
    tests.write_text(text, encoding="utf-8")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.3.6.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
