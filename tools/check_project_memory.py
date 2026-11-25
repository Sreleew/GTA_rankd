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

    match = re.search(
        r"(?im)^Version:\\s*(\\d+(?:\\.\\d+){2,3})\\s*$",
        version_file.read_text(encoding="utf-8-sig"),
    )
    if not match:
        print("ERREUR: VERSION.txt ne contient pas de version valide.")
        return 1
    version = match.group(1)
    memory = memory_file.read_text(encoding="utf-8")

    expected_version = rf"(?m)^- \\*\\*Version source de référence :\\*\\* {re.escape(version)}$"
    if not re.search(expected_version, memory):
        print(f"ERREUR: le mémo ne référence pas la version {version}.")
        return 1

    if not re.search(
        r"(?m)^- \\*\\*Dernière mise à jour :\\*\\* \\d{1,2} [A-Za-zÀ-ÿ]+ \\d{4}$",
        memory,
    ):
        print("ERREUR: date de mise à jour du mémo absente ou invalide.")
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

    print(f"Mémo de continuité OK pour la version {version}.")
    print(f"{len(REQUIRED_SECTIONS)} sections obligatoires trouvées.")
    print(f"Notes de version trouvées: {notes.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
