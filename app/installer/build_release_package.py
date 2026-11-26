"""Build a safe Windows update package for GitHub Releases."""
from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_TOP_LEVEL = {"data", "inbox", "out", "logs", "work", ".venv", "source-bundle"}
EXCLUDED_DIRS = {".git", ".github", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "build", "dist", ".install-state"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", ".log", ".pem", ".key"}
EXCLUDED_ASSET_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}


def get_version() -> str:
    text = (ROOT / "VERSION.txt").read_text(encoding="utf-8-sig")
    match = re.search(r"(?im)^\s*Version\s*:\s*(\d+(?:\.\d+){2,3})\s*$", text)
    if not match:
        raise SystemExit("VERSION.txt ne contient pas de numéro de version valide.")
    return match.group(1)


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if any(part in EXCLUDED_DIRS for part in parts):
        return False
    if parts[0] in EXCLUDED_TOP_LEVEL:
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES or path.name.lower() in {".env", "secrets.json", "credentials.json"}:
        return False
    if rel.as_posix() == "config.yaml":
        return False
    if parts[:2] == ("models", "whisper") or parts[:2] == ("tools", "whisper.cpp"):
        return path.name == ".gitkeep"
    if len(parts) >= 2 and parts[0] == "assets" and parts[1] == "fonts":
        return path.suffix.lower() not in EXCLUDED_ASSET_SUFFIXES
    if len(parts) >= 2 and parts[0] == "assets" and parts[1] == "sfx":
        return path.suffix.lower() in {".wav", ".txt"}
    return path.is_file()


def build(version: str, output_dir: Path) -> tuple[Path, Path]:
    actual = get_version()
    if version.removeprefix("v") != actual:
        raise SystemExit(f"Version demandée {version} différente de VERSION.txt ({actual}).")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"GTA-Ranked-Studio-v{actual}.zip"
    archive_path = output_dir / archive_name
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or not should_include(path):
                continue
            rel = path.relative_to(ROOT).as_posix()
            archive.write(path, f"gta-ranked-studio/{rel}")
    with zipfile.ZipFile(archive_path) as archive:
        bad = archive.testzip()
        if bad:
            raise SystemExit(f"Archive créée mais invalide : {bad}")
        required = {
            "gta-ranked-studio/VERSION.txt",
            "gta-ranked-studio/installer/apply_update.ps1",
            "gta-ranked-studio/studio/web/updater.py",
            "gta-ranked-studio/studio/web/static/index.html",
        }
        missing = required - set(archive.namelist())
        if missing:
            raise SystemExit("Fichiers requis absents : " + ", ".join(sorted(missing)))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = output_dir / "SHA256SUMS.txt"
    checksum_path.write_text(f"{digest}  {archive_name}\n", encoding="utf-8")
    return archive_path, checksum_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    archive, checksums = build(args.version, args.output_dir)
    print(f"Package: {archive}")
    print(f"SHA-256: {checksums}")
