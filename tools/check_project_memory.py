"""Vérifie les invariants de structure, version, dépendances et mémoire du dépôt."""
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

import yaml

REQUIRED_SECTIONS = (
    "## 1. Objectif du produit",
    "## 2. État actuel et fonctionnalités présentes",
    "## 3. Architecture technique et environnement",
    "## 4. Limites connues",
    "## 5. Source de référence et état des branches",
    "## 6. Fichiers importants",
    "## 7. Commandes de contrôle",
    "## 8. Règles de travail pour toute nouvelle conversation",
    "## 9. Préférences utilisateur et méthode de collaboration",
    "## 10. Journal de travail récent",
    "## 11. Prochaines étapes priorisées",
    "## 12. Message de reprise prêt à copier",
)
VERSION_PATTERN = re.compile(
    r"(?im)^\s*Version\s*:\s*(\d+(?:\.\d+){2,3})\s*$"
)
DATE_PATTERN = re.compile(r"\d{1,2} [a-zéûôîà]+ \d{4}", re.IGNORECASE)
DATE_PREFIX = "- **Dernière mise à jour :** "


def read_version(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"Fichier de version absent : {path}")
    versions = VERSION_PATTERN.findall(path.read_text(encoding="utf-8-sig"))
    if len(versions) != 1:
        raise ValueError(
            f"Une seule ligne Version: x.y.z est attendue dans {path}."
        )
    return versions[0]


def check_repository(root: Path) -> list[str]:
    root = root.expanduser().resolve()
    app_root = root / "app"
    docs_root = root / "docs"
    errors: list[str] = []

    if not app_root.is_dir() or not docs_root.is_dir():
        return [f"Racine de dépôt invalide : {root} (app/ et docs/ requis)."]

    try:
        version = read_version(root / "VERSION.txt")
        app_version = read_version(app_root / "VERSION.txt")
        if version != app_version:
            errors.append(
                f"VERSION.txt racine ({version}) et app/ ({app_version}) différents."
            )
    except ValueError as exc:
        return [str(exc)]

    try:
        metadata = tomllib.loads(
            (app_root / "pyproject.toml").read_text(encoding="utf-8")
        )
        project = metadata["project"]
        project_version = str(project["version"])
        if project_version != version:
            errors.append(
                f"pyproject.toml annonce {project_version}, attendu {version}."
            )

        runtime_dependencies = {
            str(item).strip().lower() for item in project["dependencies"]
        }
        dev_dependencies = {
            str(item).strip().lower()
            for item in project.get("optional-dependencies", {}).get("dev", [])
        }
        requirements = {
            line.strip().lower()
            for line in (app_root / "requirements.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        if requirements != runtime_dependencies:
            errors.append(
                "requirements.txt doit contenir exactement les dépendances runtime de pyproject.toml."
            )
        overlap = requirements & dev_dependencies
        if overlap:
            errors.append(
                "Dépendances de développement présentes dans requirements.txt : "
                + ", ".join(sorted(overlap))
            )
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"pyproject.toml ou requirements.txt invalide : {exc}")

    try:
        config = yaml.safe_load(
            (app_root / "config.yaml.default").read_text(encoding="utf-8-sig")
        )
        if not isinstance(config, dict) or not isinstance(config.get("app"), dict):
            raise ValueError("La section app doit être un objet YAML.")
        config_version = str(config["app"].get("version", ""))
        if config_version != version:
            errors.append(
                f"config.yaml.default annonce {config_version}, attendu {version}."
            )
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"config.yaml.default invalide : {exc}")

    required_paths = (
        "studio/web/app.py",
        "studio/web/worker.py",
        "installer/install.ps1",
        "installer/apply_update.ps1",
        "installer/check_runtime.py",
        "installer/build_release_package.py",
        "tests",
    )
    for relative in required_paths:
        if not (app_root / relative).exists():
            errors.append(f"Élément applicatif requis absent : app/{relative}.")

    memo_path = docs_root / "CONTINUATION.md"
    try:
        memo = memo_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"Mémo de continuité absent ou illisible : {exc}")
        memo = ""

    missing_sections = [heading for heading in REQUIRED_SECTIONS if heading not in memo]
    if missing_sections:
        errors.append(
            "Sections absentes du mémo : " + ", ".join(missing_sections)
        )

    date_lines = [
        line for line in memo.splitlines() if line.startswith(DATE_PREFIX)
    ]
    if len(date_lines) != 1:
        errors.append("Le mémo doit contenir exactement une date de dernière mise à jour.")
    elif not DATE_PATTERN.fullmatch(date_lines[0][len(DATE_PREFIX):].strip()):
        errors.append("Format de date invalide dans le mémo.")

    root_notes = root / f"NOTES-v{version}.txt"
    app_notes = app_root / f"NOTES-v{version}.txt"
    if not root_notes.is_file():
        errors.append(f"Notes de version absentes : {root_notes.name}.")
    if not app_notes.is_file():
        errors.append(f"Notes de version applicatives absentes : {app_notes.name}.")
    elif root_notes.is_file() and root_notes.read_bytes() != app_notes.read_bytes():
        errors.append("Les notes racine et app/ doivent être identiques.")

    approval = root / ".release-approval"
    if approval.is_file():
        approved_version = approval.read_text(encoding="utf-8-sig").strip().removeprefix("v")
        if approved_version != version:
            errors.append(
                f".release-approval annonce {approved_version}, attendu {version}."
            )

    obsolete_copies = (
        "docs/CONTINUATION.md",
        "docs/UPDATES.md",
        "docs/implementation-plan-v0.7.8.md",
        "tools/check_project_memory.py",
        "README_M0.txt",
        "prompts/bestof_metadata.default.txt",
    )
    for relative in obsolete_copies:
        if (app_root / relative).exists():
            errors.append(f"Copie obsolète à supprimer : app/{relative}.")


    for note in app_root.glob("NOTES-v*.txt"):
        if note.name != f"NOTES-v{version}.txt":
            errors.append(f"Ancienne copie de notes à retirer de app/ : {note.name}.")
    for verification in app_root.glob("VERIFICATION-v*.md"):
        errors.append(f"Ancien rapport de vérification à retirer de app/ : {verification.name}.")
    if (docs_root / "implementation-plan-v0.7.8.md").exists():
        errors.append("Ancien plan v0.7.8 à retirer : docs/implementation-plan-v0.7.8.md.")

    for required_doc in (
        "CONTINUATION.md",
        "WORKING-AGREEMENT.md",
        "RELEASE_PROCESS.md",
        "UPDATES.md",
        "WINDOWS-HARDWARE-VALIDATION.md",
        "PROJECT-MAP.md",
    ):
        if not (docs_root / required_doc).is_file():
            errors.append(f"Document canonique absent : docs/{required_doc}.")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Contrôle les versions, dépendances, documents et fichiers structurants."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Racine du dépôt GTA Ranked Studio.",
    )
    args = parser.parse_args()
    errors = check_repository(args.root)
    if errors:
        for error in errors:
            print(f"ERREUR: {error}", file=sys.stderr)
        return 1
    print("Cohérence du dépôt GTA Ranked Studio : OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
