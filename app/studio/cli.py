"""Interface en ligne de commande Typer."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from studio.config import ConfigError, load_config
from studio.doctor import run_doctor
from studio.logging_setup import configure_logging

app = typer.Typer(
    name="studio",
    help="Automatisation locale de vidéos GTA VI.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def root(
    ctx: typer.Context,
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Chemin du fichier de configuration YAML."),
) -> None:
    """Commandes de GTA Ranked Studio."""

    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@app.command()
def doctor(
    ctx: typer.Context,
    strict: bool = typer.Option(False, "--strict", help="Retourne un code d'erreur si un composant externe est manquant."),
) -> None:
    """Vérifie Python, FFmpeg/AMF, whisper.cpp, Vulkan, Ollama et les dossiers."""

    try:
        config = load_config(ctx.obj["config_path"])
        configure_logging(config)
        report = run_doctor(config)
    except ConfigError as exc:
        typer.secho(f"Configuration invalide : {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    except OSError as exc:
        logging.getLogger(__name__).exception("Erreur système pendant le diagnostic")
        typer.secho(f"Erreur système : {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    typer.secho("\nGTA RANKED STUDIO | DIAGNOSTIC M0", bold=True)
    for item in report["checks"]:
        status = item["status"]
        color = {
            "OK": typer.colors.GREEN,
            "WARN": typer.colors.YELLOW,
            "FAIL": typer.colors.RED,
        }.get(status, typer.colors.WHITE)
        typer.secho(f"[{status:4}] {item['name']}: {item['details']}", fg=color)

    summary = report["summary"]
    typer.echo(
        f"\nRésultat : {summary['ok']} OK | {summary['warnings']} avertissement(s) | "
        f"{summary['failures']} erreur(s)"
    )
    typer.echo(f"Rapport JSON : {config.path_for('paths', 'logs') / 'doctor-report.json'}")

    required_failure = any(item["status"] == "FAIL" and item["required"] for item in report["checks"])
    any_warning = summary["warnings"] > 0
    if required_failure or (strict and any_warning):
        raise typer.Exit(code=1)



@app.command()
def web(
    ctx: typer.Context,
    host: str | None = typer.Option(None, "--host", help="Adresse d’écoute. Garde 127.0.0.1 pour un usage privé sur ce PC."),
    port: int | None = typer.Option(None, "--port", min=1024, max=65535, help="Port du serveur web local."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Ne pas ouvrir automatiquement le navigateur."),
) -> None:
    """Lance le site GTA Ranked Studio dans le navigateur."""

    try:
        import threading
        import webbrowser
        import uvicorn
        from studio.web.app import create_app

        config = load_config(ctx.obj["config_path"])
        configure_logging(config)
        host = host or str(config.get("web", "host", default="127.0.0.1"))
        port = port or int(config.get("web", "port", default=8765))
        if host not in {"127.0.0.1", "localhost", "::1"}:
            typer.secho("Pour la confidentialité, le serveur doit écouter uniquement sur localhost.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        url = f"http://127.0.0.1:{port}"
        typer.secho(f"GTA Ranked Studio est accessible sur {url}", fg=typer.colors.GREEN, bold=True)
        typer.echo("Garde cette fenêtre ouverte pendant l’utilisation. Ctrl+C arrête le serveur.")
        app_instance = create_app(config)
        server_config = uvicorn.Config(
            app_instance, host="127.0.0.1", port=port, log_level="info", log_config=None
        )
        server = uvicorn.Server(server_config)
        app_instance.state.uvicorn_server = server
        if not no_browser:
            threading.Timer(1.2, lambda: webbrowser.open(url)).start()
        server.run()
    except ImportError as exc:
        typer.secho(f"Dépendance manquante : {exc}. Installe requirements.txt.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        typer.secho(f"Impossible de démarrer le site : {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc


def main() -> None:
    """Point d'entrée du script `studio`."""

    app()
