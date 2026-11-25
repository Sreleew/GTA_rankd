"""Vérifie les dépendances Python critiques et le client de test FastAPI.

La sortie standard est explicitement configurée en UTF-8 : Windows peut sinon
utiliser une page de code différente lorsque le processus est capturé par pytest.
"""

from __future__ import annotations

import sys
import warnings
from importlib.metadata import PackageNotFoundError, version


SUCCESS_MARKER = "GTA_RS_RUNTIME_CHECK_OK"


def configure_utf8_output() -> None:
    """Force UTF-8 même si Windows lance le processus avec une page de code OEM."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    configure_utf8_output()
    try:
        import fastapi
        import httpx
        import httpx2
        import multipart
        import PIL
        import pytest
        import typer
        import uvicorn
        import watchdog
        import yaml
        import yt_dlp
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/health")
        def health() -> dict[str, bool]:
            return {"ok": True}

        # Starlette recent deprecates the legacy httpx adapter in favor of httpx2.
        # Capture only this known warning and make it a clear installation error.
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            from fastapi.testclient import TestClient

            with TestClient(app) as client:
                response = client.get("/health")
                if response.status_code != 200 or response.json() != {"ok": True}:
                    raise RuntimeError("FastAPI TestClient n'a pas renvoyé la réponse attendue.")

        legacy_httpx_warning = any(
            "Using `httpx` with `starlette.testclient` is deprecated" in str(item.message)
            for item in caught_warnings
        )
        if legacy_httpx_warning:
            raise RuntimeError("Starlette utilise encore l'adaptateur HTTPX historique. Installe ou mets a jour httpx2.")

        packages = (
            "PyYAML",
            "typer",
            "fastapi",
            "uvicorn",
            "python-multipart",
            "Pillow",
            "watchdog",
            "yt-dlp",
            "pytest",
            "httpx",
            "httpx2",
        )
        for package in packages:
            try:
                print(f"{package} : {version(package)}")
            except PackageNotFoundError as exc:
                raise RuntimeError(f"Le paquet {package} est introuvable dans cet environnement.") from exc

        print(f"Python : {sys.version.split()[0]}")
        print("FastAPI TestClient : OK")
        print("Toutes les dépendances déclarées sont importables.")
        # Le test d'installation compare ce marqueur ASCII, indépendant des accents.
        print(SUCCESS_MARKER)
        return 0
    except Exception as exc:
        print(f"Vérification Python impossible : {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
