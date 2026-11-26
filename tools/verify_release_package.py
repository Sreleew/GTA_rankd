"""Validate a Windows release ZIP against required content and privacy rules."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

VERSION_PATTERN = re.compile(r"(?im)^\s*Version\s*:\s*(\d+(?:\.\d+){2,3})\s*$")
FORBIDDEN_PARTS = {
    ".git", ".github", ".venv", "venv", "env", "tests", "tools",
    "data", "inbox", "out", "logs", "work", "models", "secrets",
    "credentials", "tokens", ".ssh", ".aws", ".gnupg", ".azure",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", "coverage", "htmlcov", ".install-state",
}
FORBIDDEN_SUFFIXES = {
    ".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", ".log",
    ".pem", ".key", ".p12", ".pfx", ".bak", ".tmp", ".crt",
    ".jks", ".keystore", ".secret", ".token", ".credentials", ".wal", ".shm",
}
FORBIDDEN_NAMES = {
    "config.yaml", "secrets.json", "credentials.json", "token.json",
    ".netrc", "id_rsa", "id_ed25519", "id_ecdsa", ".pypirc",
    ".npmrc", ".dockerconfigjson", "auth.json", "access_token",
    "refresh_token", ".ds_store", "thumbs.db", "desktop.ini",
}
REQUIRED_FILES = {
    "gta-ranked-studio/VERSION.txt",
    "gta-ranked-studio/config.yaml.default",
    "gta-ranked-studio/installer/install.ps1",
    "gta-ranked-studio/installer/apply_update.ps1",
    "gta-ranked-studio/studio/web/updater.py",
    "gta-ranked-studio/studio/web/static/index.html",
    "gta-ranked-studio/docs/CONTINUATION.md",
    "gta-ranked-studio/docs/WORKING-AGREEMENT.md",
    "gta-ranked-studio/docs/PROJECT-MAP.md",
    "gta-ranked-studio/docs/UPDATES.md",
    "gta-ranked-studio/docs/RELEASE_PROCESS.md",
    "gta-ranked-studio/docs/WINDOWS-HARDWARE-VALIDATION.md",
}


def _validate_member(name: str, info: zipfile.ZipInfo) -> None:
    if "\\" in name or name.startswith(("/", "\\")):
        raise ValueError(f"Chemin non portable ou absolu dans le ZIP : {name}")
    path = PurePosixPath(name)
    if path.as_posix() != name or not name.startswith("gta-ranked-studio/"):
        raise ValueError(f"Chemin hors de la racine autorisée du package : {name}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Chemin dangereux dans le ZIP : {name}")
    parts = {part.lower() for part in path.parts}
    filename = path.name.lower()
    if parts & FORBIDDEN_PARTS:
        raise ValueError(f"Répertoire local ou de développement interdit : {name}")
    if filename in FORBIDDEN_NAMES or filename.startswith(".env") and filename != ".env.example":
        raise ValueError(f"Fichier privé interdit dans le ZIP : {name}")
    if filename.startswith("._") or filename.startswith("notes-v") or filename.startswith("verification-v"):
        raise ValueError(f"Fichier de métadonnées/historique non nécessaire interdit dans le ZIP : {name}")
    if filename.startswith(".") and filename not in {".gitignore", ".env.example"}:
        raise ValueError(f"Fichier caché interdit dans le ZIP : {name}")
    if filename.startswith("config.") and filename not in {"config.yaml.default", "config.example.yaml"}:
        raise ValueError(f"Configuration locale interdite dans le ZIP : {name}")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        raise ValueError(f"Fichier local/sensible interdit dans le ZIP : {name}")
    mode = (info.external_attr >> 16) & 0o170000
    if mode == 0o120000:
        raise ValueError(f"Lien symbolique interdit dans le ZIP : {name}")


def verify(package: Path, checksum: Path, version: str) -> list[str]:
    errors: list[str] = []
    if not package.is_file():
        return [f"Package absent : {package}"]
    if not checksum.is_file():
        return [f"Fichier SHA-256 absent : {checksum}"]
    try:
        with zipfile.ZipFile(package) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                errors.append("Le ZIP contient des chemins dupliqués.")
            for info in infos:
                try:
                    _validate_member(info.filename, info)
                except ValueError as exc:
                    errors.append(str(exc))
            corrupt = archive.testzip()
            if corrupt:
                errors.append(f"Entrée corrompue dans le ZIP : {corrupt}")
            missing = REQUIRED_FILES - set(names)
            if missing:
                errors.append("Fichiers requis absents : " + ", ".join(sorted(missing)))
            version_file = "gta-ranked-studio/VERSION.txt"
            if version_file in names:
                text = archive.read(version_file).decode("utf-8-sig")
                matches = VERSION_PATTERN.findall(text)
                if matches != [version]:
                    errors.append(f"Version du ZIP incorrecte : {matches!r}, attendu {version}.")
    except (OSError, zipfile.BadZipFile, UnicodeError) as exc:
        return [f"Lecture du package impossible : {exc}"]

    try:
        lines = checksum.read_text(encoding="utf-8-sig").splitlines()
        expected = [
            (match.group(1), match.group(2))
            for line in lines
            if (match := re.fullmatch(r"([0-9a-fA-F]{64})\s+(.+)", line.strip()))
        ]
        actual_name = package.name
        if (len(expected) != 1 or expected[0][1] != actual_name
                or expected[0][0].lower() != hashlib.sha256(package.read_bytes()).hexdigest()):
            errors.append("Le fichier SHA-256 ne correspond pas exactement au package.")
    except OSError as exc:
        errors.append(f"Lecture du checksum impossible : {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Vérifie le contenu, les exclusions et le SHA-256 du ZIP Windows.")
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--checksum", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    errors = verify(args.package, args.checksum, args.version.removeprefix("v"))
    if errors:
        for error in errors:
            print(f"ERREUR: {error}", file=sys.stderr)
        return 1
    print(f"Package Windows v{args.version.removeprefix('v')} vérifié : contenu, exclusions et SHA-256 OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
