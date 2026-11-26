"""Construit un ZIP Windows sûr depuis app/ et la documentation canonique du dépôt."""
from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CANONICAL_DOCS = (
    "CONTINUATION.md",
    "WORKING-AGREEMENT.md",
    "PROJECT-MAP.md",
    "UPDATES.md",
    "RELEASE_PROCESS.md",
    "WINDOWS-HARDWARE-VALIDATION.md",
)
EXCLUDED_TOP_LEVEL = {
    "data", "inbox", "out", "logs", "work", "models", "tools",
    "tests", "docs", ".venv", "venv", "env", "source-bundle",
    "coverage", "htmlcov",
}
EXCLUDED_DIRS = {
    ".git", ".github", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", "node_modules", "build", "dist",
    ".install-state", ".cache", "__MACOSX", "data", "inbox", "out",
    "logs", "work", "models", "tools", "tests", "docs", "venv", "env",
    ".ssh", ".aws", ".gnupg", ".azure", "secrets", "credentials", "tokens",
}
EXCLUDED_SUFFIXES = {
    ".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", ".log",
    ".pem", ".key", ".p12", ".pfx", ".bak", ".tmp", ".crt",
    ".jks", ".keystore", ".secret", ".token", ".credentials", ".wal", ".shm",
}
EXCLUDED_NAMES = {
    "secrets.json", "credentials.json", "token.json", ".netrc",
    "id_rsa", "id_ed25519", "id_ecdsa", ".pypirc", ".npmrc",
    ".dockerconfigjson", "auth.json", "access_token", "refresh_token",
    ".ds_store", "thumbs.db", "desktop.ini",
}
EXCLUDED_FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}


def get_version() -> str:
    text = (ROOT / "VERSION.txt").read_text(encoding="utf-8-sig")
    matches = re.findall(r"(?im)^\s*Version\s*:\s*(\d+(?:\.\d+){2,3})\s*$", text)
    if len(matches) != 1:
        raise SystemExit("VERSION.txt doit contenir exactement une version x.y.z.")
    return matches[0]


def should_include(path: Path) -> bool:
    """Reject symlinks, private state, developer tools and generated files."""
    if path.is_symlink() or not path.is_file():
        return False
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    parts = tuple(part.lower() for part in relative.parts)
    name = path.name.lower()
    if not parts or parts[0] in EXCLUDED_TOP_LEVEL:
        return False
    if relative.as_posix() == "installer/build_release_package.py":
        return False
    if any(part in EXCLUDED_DIRS for part in parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES or name in EXCLUDED_NAMES:
        return False
    if name.startswith(".env") and name != ".env.example":
        return False
    if name.startswith("._") or name.startswith("notes-v") or name.startswith("verification-v"):
        return False
    if name.startswith(".") and name not in {".gitignore", ".env.example"}:
        return False
    # Le module applicatif studio/config.py est du code runtime, pas une configuration utilisateur.
    if (name.startswith("config.")
            and relative.as_posix() != "studio/config.py"
            and name not in {"config.yaml.default", "config.example.yaml"}):
        return False
    if len(parts) >= 2 and parts[:2] == ("assets", "fonts"):
        return path.suffix.lower() not in EXCLUDED_FONT_SUFFIXES
    if len(parts) >= 2 and parts[:2] == ("assets", "sfx"):
        return path.suffix.lower() in {".wav", ".txt"}
    return True


def _sources() -> list[tuple[Path, str]]:
    sources: list[tuple[Path, str]] = []
    for path in sorted(ROOT.rglob("*")):
        if should_include(path):
            relative = path.relative_to(ROOT).as_posix()
            sources.append((path, f"gta-ranked-studio/{relative}"))
    for name in CANONICAL_DOCS:
        path = REPO_ROOT / "docs" / name
        if not path.is_file():
            raise SystemExit(f"Documentation canonique absente : docs/{name}.")
        sources.append((path, f"gta-ranked-studio/docs/{name}"))
    destinations = [destination for _, destination in sources]
    if len(destinations) != len(set(destinations)):
        raise SystemExit("Le package contiendrait des chemins dupliqués.")
    return sources


def build(version: str, output_dir: Path) -> tuple[Path, Path]:
    actual = get_version()
    if version.removeprefix("v") != actual:
        raise SystemExit(f"Version demandée {version} différente de VERSION.txt ({actual}).")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"GTA-Ranked-Studio-v{actual}.zip"
    archive_path = output_dir / archive_name
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for source, destination in _sources():
            archive.write(source, destination)
    with zipfile.ZipFile(archive_path) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise SystemExit(f"Archive créée mais invalide : {corrupt}")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = output_dir / "SHA256SUMS.txt"
    checksum_path.write_text(f"{digest}  {archive_name}\n", encoding="utf-8")
    return archive_path, checksum_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Construit le package Windows GTA Ranked Studio.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    package, checksum = build(args.version, args.output_dir)
    print(f"Package: {package}")
    print(f"SHA-256: {checksum}")
