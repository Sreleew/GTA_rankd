"""Smoke test court des imports et dépendances de production."""
from __future__ import annotations

import sys
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version

SUCCESS_MARKER = "GTA_RS_RUNTIME_CHECK_OK"
REQUIRED_MODULES = (
    "fastapi",
    "multipart",
    "PIL",
    "typer",
    "uvicorn",
    "yaml",
    "yt_dlp",
    "studio.cli",
    "studio.doctor",
    "studio.web.app",
    "studio.web.worker",
)
RUNTIME_DISTRIBUTIONS = (
    "PyYAML",
    "typer",
    "fastapi",
    "uvicorn",
    "python-multipart",
    "Pillow",
    "yt-dlp",
)


def main() -> int:
    try:
        for module_name in REQUIRED_MODULES:
            import_module(module_name)
        for distribution in RUNTIME_DISTRIBUTIONS:
            try:
                print(f"{distribution}: {version(distribution)}")
            except PackageNotFoundError as exc:
                raise RuntimeError(f"Paquet runtime absent : {distribution}") from exc
        print(f"Python: {sys.version.split()[0]}")
        print("Imports applicatifs: OK")
        print(SUCCESS_MARKER)
        return 0
    except Exception as exc:
        print(f"Smoke test runtime échoué: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
