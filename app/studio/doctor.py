"""Diagnostic de l'environnement Windows et des dépendances locales."""

from __future__ import annotations

import importlib.util
import json
import logging
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from studio.config import AppConfig
from studio.process import run_quiet

logger = logging.getLogger(__name__)


@dataclass
class Check:
    name: str
    status: str
    details: str
    required: bool = False


def _run(args: Sequence[str], timeout: int = 15) -> subprocess.CompletedProcess[str] | None:
    """Exécute une commande sous forme de liste, sans shell."""

    try:
        return run_quiet(
            list(args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("Échec de la commande %s : %s", args[0] if args else "?", exc)
        return None


def _command_output(command: str, *args: str, timeout: int = 15) -> str | None:
    executable = shutil.which(command)
    if not executable:
        return None
    result = _run([executable, *args], timeout=timeout)
    if result is None or result.returncode != 0:
        return None
    return (result.stdout or result.stderr).strip()


def _powershell(command: str, timeout: int = 15) -> str | None:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        return None
    result = _run([powershell, "-NoProfile", "-NonInteractive", "-Command", command], timeout=timeout)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def _check_python() -> Check:
    version = platform.python_version()
    ok = sys.version_info >= (3, 11)
    return Check(
        "Python",
        "OK" if ok else "FAIL",
        f"Python {version}" + (" (compatible)" if ok else " (Python 3.11 minimum requis)"),
        required=True,
    )


def _check_packages() -> Check:
    package_map = {
        "PyYAML": "yaml",
        "Typer": "typer",
        "FastAPI": "fastapi",
        "Uvicorn": "uvicorn",
        "python-multipart": "multipart",
        "Pillow": "PIL",
        "Watchdog": "watchdog",
        "yt-dlp": "yt_dlp",
        "pytest": "pytest",
    }
    missing = [display for display, module in package_map.items() if importlib.util.find_spec(module) is None]
    if missing:
        return Check("Dépendances Python", "FAIL", "Modules manquants : " + ", ".join(missing), required=True)
    return Check("Dépendances Python", "OK", "Toutes les dépendances Python de l’application sont importables.", required=True)


def _check_binary(name: str, executable: str, args: tuple[str, ...] = ("-version",)) -> tuple[Check, str | None]:
    path = shutil.which(executable)
    if not path:
        return Check(name, "WARN", f"'{executable}' introuvable dans PATH."), None
    output = _command_output(executable, *args)
    if output is None:
        return Check(name, "WARN", f"Binaire trouvé ({path}), mais la commande de version a échoué."), path
    first_line = output.splitlines()[0] if output else "Version non communiquée"
    return Check(name, "OK", f"{path} | {first_line}"), path


def _ensure_project_directories(config: AppConfig) -> list[Check]:
    directory_keys = (
        "inbox_shorts",
        "inbox_bestof",
        "output_shorts",
        "output_bestof",
        "logs",
        "temp",
        "fonts",
        "prompts",
        "models",
        "tools",
    )
    checks: list[Check] = []
    for key in directory_keys:
        try:
            path = config.path_for("paths", key)
            path.mkdir(parents=True, exist_ok=True)
            checks.append(Check(f"Dossier {key}", "OK", str(path)))
        except (OSError, ValueError) as exc:
            checks.append(Check(f"Dossier {key}", "FAIL", str(exc), required=True))

    try:
        urls_file = config.path_for("paths", "inbox_urls")
        urls_file.parent.mkdir(parents=True, exist_ok=True)
        if not urls_file.exists():
            urls_file.write_text(
                "# Une URL Twitch ou YouTube par ligne. Les lignes commençant par # sont ignorées.\n",
                encoding="utf-8",
            )
        checks.append(Check("Fichier inbox/urls.txt", "OK", str(urls_file)))
    except OSError as exc:
        checks.append(Check("Fichier inbox/urls.txt", "FAIL", str(exc), required=True))
    return checks


def _check_ffmpeg(config: AppConfig) -> list[Check]:
    ffmpeg_name = str(config.get("executables", "ffmpeg", default="ffmpeg"))
    ffprobe_name = str(config.get("executables", "ffprobe", default="ffprobe"))
    ffmpeg_check, ffmpeg_path = _check_binary("FFmpeg", ffmpeg_name)
    ffprobe_check, _ = _check_binary("FFprobe", ffprobe_name)
    checks = [ffmpeg_check, ffprobe_check]

    if not ffmpeg_path:
        checks.append(Check("Encodage vidéo AMD", "WARN", "Non vérifiable tant que FFmpeg n'est pas installé."))
        checks.append(Check("Filtres FFmpeg", "WARN", "Non vérifiables tant que FFmpeg n'est pas installé."))
        return checks

    encoders_result = _run([ffmpeg_path, "-hide_banner", "-encoders"], timeout=20)
    encoders_text = "" if encoders_result is None else (encoders_result.stdout + encoders_result.stderr)
    preferred = str(config.get("encoding", "video_codec", default="h264_amf"))
    fallback = str(config.get("encoding", "fallback_video_codec", default="libx264"))
    has_preferred = preferred in encoders_text
    has_fallback = fallback in encoders_text

    if has_preferred:
        checks.append(Check("Encodage vidéo AMD", "OK", f"Encodeur matériel {preferred} détecté."))
    elif has_fallback:
        checks.append(Check(
            "Encodage vidéo AMD",
            "WARN",
            f"{preferred} absent. L'encodeur logiciel {fallback} est disponible en secours.",
        ))
    else:
        checks.append(Check("Encodage vidéo AMD", "FAIL", f"Ni {preferred} ni {fallback} ne sont disponibles.", required=True))

    filters_result = _run([ffmpeg_path, "-hide_banner", "-filters"], timeout=20)
    filters_text = "" if filters_result is None else (filters_result.stdout + filters_result.stderr)
    required_filters = ("loudnorm", "ass", "boxblur")
    missing_filters = [name for name in required_filters if name not in filters_text]
    if missing_filters:
        checks.append(Check("Filtres FFmpeg", "WARN", "Filtres non détectés : " + ", ".join(missing_filters)))
    else:
        checks.append(Check("Filtres FFmpeg", "OK", "loudnorm, ass et boxblur sont disponibles."))
    return checks


def _check_whisper(config: AppConfig) -> list[Check]:
    configured = config.path_for("executables", "whisper_cli")
    found = configured if configured.is_file() else None
    if found is None:
        for candidate in ("whisper-cli.exe", "whisper-cli"):
            path = shutil.which(candidate)
            if path:
                found = Path(path)
                break

    model = config.path_for("transcription", "model_path")
    backend = str(config.get("transcription", "backend", default="vulkan"))
    if found is None:
        binary_check = Check(
            "whisper.cpp",
            "WARN",
            f"Binaire absent. Chemin attendu : {configured}. Backend configuré : {backend}.",
        )
    else:
        binary_check = Check("whisper.cpp", "OK", f"{found} | backend configuré : {backend}")

    if model.is_file():
        model_check = Check("Modèle de transcription", "OK", str(model))
    else:
        model_check = Check("Modèle de transcription", "WARN", f"Modèle absent : {model}")
    return [binary_check, model_check]


def _check_ollama(config: AppConfig) -> list[Check]:
    base_url = str(config.get("ollama", "base_url", default="http://127.0.0.1:11434")).rstrip("/")
    model_name = str(config.get("ollama", "model", default=""))
    timeout = int(config.get("ollama", "request_timeout_seconds", default=180))
    checks: list[Check] = []

    ollama_binary = shutil.which("ollama")
    if ollama_binary:
        version_result = _run([ollama_binary, "--version"], timeout=15)
        version_text = "" if version_result is None else (version_result.stdout or version_result.stderr).strip()
        checks.append(Check("Ollama CLI", "OK", version_text or ollama_binary))
    else:
        checks.append(Check("Ollama CLI", "WARN", "Commande 'ollama' absente de PATH."))

    request = urllib.request.Request(f"{base_url}/api/tags", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=min(timeout, 8)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        checks.append(Check("Ollama local", "WARN", f"API non joignable sur {base_url} : {exc}"))
        checks.append(Check("Modèle Ollama", "WARN", f"Impossible de vérifier le modèle {model_name}."))
        return checks

    checks.append(Check("Ollama local", "OK", f"API locale disponible sur {base_url}."))
    installed = [str(item.get("name", "")) for item in payload.get("models", []) if isinstance(item, dict)]
    present = model_name in installed
    if present:
        checks.append(Check("Modèle Ollama", "OK", f"{model_name} installé. Modèles trouvés : {', '.join(installed)}"))
    else:
        checks.append(Check("Modèle Ollama", "WARN", f"{model_name} absent. Commande : ollama pull {model_name}"))
    checks.append(Check("Backend Ollama", "WARN", "Le diagnostic confirme l'API et le modèle, mais ne mesure pas encore l'offload GPU Vulkan. Celui-ci sera testé avec une génération réelle."))
    return checks


def _check_windows_hardware(config: AppConfig) -> list[Check]:
    if platform.system() != "Windows":
        return [Check("Matériel Windows", "WARN", f"Diagnostic matériel Windows ignoré sur {platform.system()}.")]

    gpu_output = _powershell("Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name")
    cpu_output = _powershell("Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name")
    ram_output = _powershell("[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)")

    checks: list[Check] = []
    if gpu_output:
        gpu_names = [line.strip() for line in gpu_output.splitlines() if line.strip()]
        expected_gpu = str(config.get("hardware", "gpu_model", default="")).casefold()
        matching = any(expected_gpu in name.casefold() for name in gpu_names) if expected_gpu else True
        status = "OK" if matching else "WARN"
        checks.append(Check("Carte graphique détectée", status, "; ".join(gpu_names)))
    else:
        checks.append(Check("Carte graphique détectée", "WARN", "PowerShell n'a pas retourné de nom de GPU."))

    if cpu_output:
        checks.append(Check("Processeur", "OK", cpu_output.strip()))
    else:
        checks.append(Check("Processeur", "WARN", f"{platform.processor() or 'Non détecté'} | {os_cpu_count()} threads logiques"))

    if ram_output:
        checks.append(Check("Mémoire système", "OK", f"{ram_output.strip()} Go de RAM détectés."))
    else:
        checks.append(Check("Mémoire système", "WARN", "Impossible de lire la mémoire système."))

    checks.append(Check(
        "Profil AMD",
        "OK",
        f"Configuration : {config.get('hardware', 'gpu_model')} / {config.get('hardware', 'gpu_vram_gb')} Go / architecture {config.get('hardware', 'gpu_architecture')}.",
    ))
    return checks


def os_cpu_count() -> int:
    """Retourne le nombre de processeurs logiques."""

    import os

    return os.cpu_count() or 1


def _check_vulkan() -> Check:
    vulkaninfo = shutil.which("vulkaninfo")
    if not vulkaninfo:
        return Check("Vulkan", "WARN", "vulkaninfo absent de PATH. Le pilote AMD peut néanmoins fournir Vulkan; installe le Vulkan SDK pour le diagnostic détaillé.")
    result = _run([vulkaninfo, "--summary"], timeout=20)
    if result is None or result.returncode != 0:
        return Check("Vulkan", "WARN", "vulkaninfo est présent mais n'a pas pu interroger le pilote.")
    summary = (result.stdout or result.stderr).strip().splitlines()
    detail = " | ".join(line.strip() for line in summary[:4] if line.strip())
    return Check("Vulkan", "OK", detail or "Pilote Vulkan interrogé avec succès.")


def _check_fonts(config: AppConfig) -> Check:
    fonts_dir = config.path_for("paths", "fonts")
    fonts = list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf")) + list(fonts_dir.glob("*.ttc"))
    if fonts:
        return Check("Polices locales", "OK", f"{len(fonts)} fichier(s) de police dans {fonts_dir}.")
    return Check("Polices locales", "WARN", f"Aucune police ajoutée dans {fonts_dir}. La police système '{config.get('branding', 'font_name', default='Arial')}' sera utilisée en attendant.")


def run_doctor(config: AppConfig) -> dict[str, Any]:
    """Lance les vérifications et écrit un rapport JSON local."""

    checks: list[Check] = []
    checks.extend(_ensure_project_directories(config))
    checks.extend([
        _check_python(),
        _check_packages(),
    ])
    checks.extend(_check_ffmpeg(config))
    checks.extend(_check_whisper(config))
    checks.extend(_check_ollama(config))
    checks.extend(_check_windows_hardware(config))
    checks.append(_check_vulkan())
    checks.append(_check_fonts(config))

    report = {
        "app": config.get("app", "name", default="gta-ranked-studio"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(config.root),
        "checks": [asdict(check) for check in checks],
        "summary": {
            "ok": sum(check.status == "OK" for check in checks),
            "warnings": sum(check.status == "WARN" for check in checks),
            "failures": sum(check.status == "FAIL" for check in checks),
        },
    }

    report_path = config.path_for("paths", "logs") / "doctor-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Rapport de diagnostic écrit dans %s", report_path)
    return report
