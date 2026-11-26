"""GitHub Releases updater for GTA Ranked Studio.

Only public release assets are downloaded. Personal data and runtime dependencies
are never part of the update package and are never overwritten.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

REPOSITORY = "Sreleew/GTA_rankd"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
USER_AGENT = "GTA-Ranked-Studio-Updater/1.0"
MAX_PACKAGE_BYTES = 750 * 1024 * 1024


def _version_tuple(value: str) -> tuple[int, ...]:
    cleaned = str(value or "").strip().lstrip("vV")
    if not re.fullmatch(r"\d+(?:\.\d+){2,3}", cleaned):
        raise ValueError(f"Numéro de version invalide : {value}")
    parts = tuple(int(part) for part in cleaned.split("."))
    return parts + (0,) * (4 - len(parts))


def _read_json(url: str, timeout: int = 12) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(2 * 1024 * 1024 + 1)
    if len(payload) > 2 * 1024 * 1024:
        raise RuntimeError("La réponse de GitHub est anormalement volumineuse.")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("Réponse GitHub invalide.")
    return value


def _download(url: str, destination: Path, max_bytes: int = MAX_PACKAGE_BYTES) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"
    }:
        raise RuntimeError("URL de téléchargement GitHub non autorisée.")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    written = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(request, timeout=45) as response, temporary.open("wb") as output:
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise RuntimeError("Le paquet de mise à jour dépasse la taille maximale autorisée.")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise RuntimeError("Le paquet de mise à jour dépasse la taille maximale autorisée.")
                digest.update(chunk)
                output.write(chunk)
        temporary.replace(destination)
        return digest.hexdigest()
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


class UpdateService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()
        self._lock = threading.Lock()
        self._install_started = False
        self._state: dict[str, str] = {
            "status": "idle",
            "message": "Aucune mise à jour en cours.",
        }

    def get_status(self) -> dict[str, str]:
        with self._lock:
            return dict(self._state)

    def current_version(self) -> str:
        version_file = self.project_root / "VERSION.txt"
        text = version_file.read_text(encoding="utf-8-sig")
        match = re.search(r"(?im)^\s*Version\s*:\s*(\d+(?:\.\d+){2,3})\s*$", text)
        if not match:
            raise RuntimeError("Impossible de lire VERSION.txt.")
        return match.group(1)

    def _latest_release(self) -> dict[str, Any]:
        release = _read_json(RELEASES_API)
        if release.get("draft") or release.get("prerelease"):
            raise RuntimeError("La dernière publication GitHub n'est pas une version stable.")
        tag = str(release.get("tag_name") or "")
        version = tag.lstrip("vV")
        _version_tuple(version)
        assets = release.get("assets") or []
        expected_zip = f"GTA-Ranked-Studio-v{version}.zip"
        asset_by_name = {str(asset.get("name") or ""): asset for asset in assets}
        package = asset_by_name.get(expected_zip)
        checksums = asset_by_name.get("SHA256SUMS.txt")
        if not package or not checksums:
            raise RuntimeError(
                f"La publication {tag} est incomplète : paquet ZIP ou SHA256SUMS.txt absent."
            )
        for asset in (package, checksums):
            if int(asset.get("size") or 0) <= 0 or int(asset.get("size") or 0) > MAX_PACKAGE_BYTES:
                raise RuntimeError("Taille de fichier de mise à jour invalide.")
        return {
            "version": version,
            "tag": tag,
            "name": str(release.get("name") or f"GTA Ranked Studio {tag}"),
            "body": str(release.get("body") or ""),
            "published_at": release.get("published_at"),
            "html_url": str(release.get("html_url") or ""),
            "package": package,
            "checksums": checksums,
        }

    def check(self) -> dict[str, Any]:
        current = self.current_version()
        release = self._latest_release()
        latest = release["version"]
        return {
            "current_version": current,
            "latest_version": latest,
            "update_available": _version_tuple(latest) > _version_tuple(current),
            "release_name": release["name"],
            "release_notes": release["body"][:12000],
            "published_at": release["published_at"],
            "release_url": release["html_url"],
        }

    def start_install(self, server: Any, parent_pid: int) -> dict[str, Any]:
        with self._lock:
            if self._install_started:
                raise RuntimeError("Une mise à jour est déjà en cours.")
            self._install_started = True
            self._state = {
                "status": "downloading",
                "message": "Téléchargement du paquet de mise à jour...",
            }

        thread = threading.Thread(
            target=self._download_and_launch,
            args=(server, parent_pid),
            name="gta-ranked-updater",
            daemon=True,
        )
        thread.start()
        return {
            "status": "starting",
            "message": "Préparation de la mise à jour. GTA Ranked Studio va se fermer puis redémarrer automatiquement.",
        }

    def _download_and_launch(self, server: Any, parent_pid: int) -> None:
        try:
            release = self._latest_release()
            if _version_tuple(release["version"]) <= _version_tuple(self.current_version()):
                raise RuntimeError("GTA Ranked Studio est déjà à jour.")
            local_app_data = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData/Local"))
            updater_home = local_app_data / "GTA Ranked Studio" / "updates"
            downloads = updater_home / "downloads"
            package_name = str(release["package"]["name"])
            checksum_name = str(release["checksums"]["name"])
            package_path = downloads / package_name
            checksum_path = downloads / checksum_name

            package_url = str(release["package"].get("browser_download_url") or "")
            checksum_url = str(release["checksums"].get("browser_download_url") or "")
            package_hash = _download(package_url, package_path)
            with self._lock:
                self._state = {
                    "status": "verifying",
                    "message": "Vérification de l'intégrité du paquet...",
                }
            _download(checksum_url, checksum_path, max_bytes=1024 * 1024)

            expected_hash = None
            for line in checksum_path.read_text(encoding="utf-8-sig").splitlines():
                match = re.match(r"^\s*([a-fA-F0-9]{64})\s+\*?(.+?)\s*$", line)
                if match and match.group(2).strip() == package_name:
                    expected_hash = match.group(1).lower()
                    break
            if not expected_hash or package_hash.lower() != expected_hash:
                raise RuntimeError("La vérification SHA-256 du paquet a échoué.")

            with zipfile.ZipFile(package_path, "r") as archive:
                bad_member = archive.testzip()
                if bad_member:
                    raise RuntimeError(f"Archive ZIP endommagée : {bad_member}")
                updater_member = "gta-ranked-studio/installer/apply_update.ps1"
                if updater_member not in archive.namelist():
                    raise RuntimeError("Le paquet ne contient pas l'installateur de mise à jour.")
                updater_script = archive.read(updater_member)

            updater_script_path = updater_home / "apply_update.ps1"
            updater_script_path.parent.mkdir(parents=True, exist_ok=True)
            updater_script_path.write_bytes(updater_script)

            powershell = shutil.which("powershell.exe") or shutil.which("powershell")
            if not powershell:
                raise RuntimeError("Windows PowerShell est introuvable. Aucun fichier de l'application n'a été modifié.")

            log_path = updater_home / "last-update.log"
            args = [
                powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(updater_script_path),
                "-ProjectRoot", str(self.project_root),
                "-ArchivePath", str(package_path),
                "-ExpectedVersion", str(release["version"]),
                "-ParentPid", str(parent_pid),
                "-LogPath", str(log_path),
            ]
            # Create a bootstrap log before starting PowerShell. In v0.3.4/v0.3.5
            # stdout/stderr were discarded, so a PowerShell startup/parse error
            # could silently stop the updater before its own log was created.
            log_path.parent.mkdir(parents=True, exist_ok=True)
            console_log_path = updater_home / "powershell-output.log"
            with log_path.open("a", encoding="utf-8") as bootstrap_log:
                bootstrap_log.write(
                    f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Python updater: launching PowerShell for v{release['version']}\n"
                )
                bootstrap_log.write(f"Project root: {self.project_root}\n")
                bootstrap_log.flush()
                creation_flags = 0
                if os.name == "nt":
                    # CREATE_NO_WINDOW works with redirected stdout/stderr and avoids
                    # the DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP combination.
                    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                with console_log_path.open("a", encoding="utf-8") as powershell_log:
                    powershell_process = subprocess.Popen(
                        args,
                        cwd=str(self.project_root),
                        stdin=subprocess.DEVNULL,
                        stdout=powershell_log,
                        stderr=subprocess.STDOUT,
                        close_fds=True,
                        creationflags=creation_flags,
                    )
                    bootstrap_log.write(f"PowerShell process started: PID {powershell_process.pid}\n")
                    bootstrap_log.flush()
            # Catch immediate PowerShell launch/parse failures before shutting down
            # the web server. If it survives, it will wait for this parent process.
            time.sleep(1.0)
            if powershell_process.poll() is not None:
                raise RuntimeError(
                    f"PowerShell s'est arrêté immédiatement (code {powershell_process.returncode}). "
                    f"Consulte {console_log_path} et {log_path}."
                )
            with self._lock:
                self._state = {
                    "status": "restarting",
                    "message": "Paquet vérifié. Fermeture puis redémarrage de GTA Ranked Studio...",
                }
            logger.info("Mise à jour %s téléchargée et vérifiée ; arrêt de l'application.", release["version"])

            def request_shutdown() -> None:
                time.sleep(1.0)
                try:
                    server.should_exit = True
                except Exception:
                    logger.exception("Impossible de demander l'arrêt de l'application pour la mise à jour.")

            threading.Thread(target=request_shutdown, name="gta-update-shutdown", daemon=True).start()
        except Exception as exc:
            logger.exception("Échec de préparation de la mise à jour")
            with self._lock:
                self._install_started = False
                self._state = {
                    "status": "error",
                    "message": "Échec de la mise à jour : " + str(exc),
                }
