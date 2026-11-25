"""Vérifie que le mémo de continuité correspond à la version du projet."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

REQUIRED_SECTIONS = (
    "## 1. Objectif du produit",
    "## 2. État actuel et fonctionnalités présentes",
    "## 3. Architecture technique et environnement",
    "## 4. Limites connues",
    "## 5. Source de référence et état des branches",
    "## 6. Fichiers importants",
    "## 7. Commandes de contrôle",
    "## 8. Règles de travail pour toute nouvelle conversation",
    "## 9. Prochaines étapes priorisées",
    "## 10. Message de reprise prêt à copier",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Contrôle le mémo projet avant publication.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.expanduser().resolve()

    version_file = root / "VERSION.txt"
    memory_file = root / "docs" / "CONTINUATION.md"
    if not version_file.is_file() or not memory_file.is_file():
        print("ERREUR: VERSION.txt ou docs/CONTINUATION.md est absent.")
        return 1

    version = None
    for line in version_file.read_text(encoding="utf-8-sig").splitlines():
        if line.strip().lower().startswith("version:"):
            version = line.split(":", 1)[1].strip()
            break
    if not version or not re.fullmatch(r"[0-9]+([.][0-9]+){2,3}", version):
        print("ERREUR: VERSION.txt ne contient pas de version valide.")
        return 1

    memory = memory_file.read_text(encoding="utf-8")
    expected_version = f"- **Version source de référence :** {version}"
    if expected_version not in memory.splitlines():
        print(f"ERREUR: le mémo ne référence pas la version {version}.")
        return 1

    date_prefix = "- **Dernière mise à jour :** "
    date_lines = [line for line in memory.splitlines() if line.startswith(date_prefix)]
    if len(date_lines) != 1:
        print("ERREUR: la date de mise à jour du mémo est absente ou ambiguë.")
        return 1
    date_parts = date_lines[0][len(date_prefix):].split()
    if len(date_parts) != 4 or not date_parts[0].isdigit() or not date_parts[3].isdigit():
        print("ERREUR: date de mise à jour invalide dans docs/CONTINUATION.md.")
        return 1

    missing = [section for section in REQUIRED_SECTIONS if section not in memory]
    if missing:
        print("ERREUR: sections manquantes dans docs/CONTINUATION.md:")
        for section in missing:
            print(f"- {section}")
        return 1

    notes = root / f"NOTES-v{version}.txt"
    if not notes.is_file():
        print(f"ERREUR: fichier de notes absent: {notes.name}")
        return 1

    print(f"Memo de continuite OK pour la version {version}.")
    print(f"{len(REQUIRED_SECTIONS)} sections obligatoires trouvees.")
    print(f"Notes de version trouvees: {notes.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
