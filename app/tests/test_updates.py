from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from studio.web import updater


def test_version_tuple_compares_numeric_versions() -> None:
    assert updater._version_tuple("v0.3.10") > updater._version_tuple("0.3.9")
    assert updater._version_tuple("0.3.4.1") > updater._version_tuple("0.3.4")
    assert updater._version_tuple("0.3.4") == updater._version_tuple("0.3.4.0")


@pytest.mark.parametrize("value", ["", "latest", "0.3", "0.3.4-beta", "1.2.3.4.5"])
def test_version_tuple_rejects_invalid_versions(value: str) -> None:
    with pytest.raises(ValueError):
        updater._version_tuple(value)


def _release(version: str = "0.3.5") -> dict:
    return {
        "tag_name": f"v{version}",
        "name": f"GTA Ranked Studio v{version}",
        "body": "Correctifs et nouveautés",
        "published_at": "2026-11-24T00:00:00Z",
        "html_url": "https://github.com/Sreleew/GTA_rankd/releases/tag/v" + version,
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": f"GTA-Ranked-Studio-v{version}.zip",
                "size": 1024,
                "browser_download_url": f"https://github.com/Sreleew/GTA_rankd/releases/download/v{version}/GTA-Ranked-Studio-v{version}.zip",
            },
            {
                "name": "SHA256SUMS.txt",
                "size": 100,
                "browser_download_url": f"https://github.com/Sreleew/GTA_rankd/releases/download/v{version}/SHA256SUMS.txt",
            },
        ],
    }


def test_check_reports_update_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "VERSION.txt").write_text("GTA Ranked Studio\nVersion: 0.3.4\n", encoding="utf-8")
    monkeypatch.setattr(updater, "_read_json", lambda *_args, **_kwargs: _release("0.3.5"))
    result = updater.UpdateService(tmp_path).check()
    assert result["current_version"] == "0.3.4"
    assert result["latest_version"] == "0.3.5"
    assert result["update_available"] is True
    assert result["release_notes"] == "Correctifs et nouveautés"


def test_check_reports_up_to_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "VERSION.txt").write_text("Version: 0.3.5\n", encoding="utf-8")
    monkeypatch.setattr(updater, "_read_json", lambda *_args, **_kwargs: _release("0.3.5"))
    assert updater.UpdateService(tmp_path).check()["update_available"] is False


def test_release_must_have_zip_and_checksum_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _release()
    payload["assets"] = payload["assets"][:1]
    monkeypatch.setattr(updater, "_read_json", lambda *_args, **_kwargs: payload)
    with pytest.raises(RuntimeError, match="incomplète"):
        updater.UpdateService(Path.cwd())._latest_release()


def test_release_must_be_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _release()
    payload["prerelease"] = True
    monkeypatch.setattr(updater, "_read_json", lambda *_args, **_kwargs: payload)
    with pytest.raises(RuntimeError, match="stable"):
        updater.UpdateService(Path.cwd())._latest_release()


def test_download_rejects_non_github_urls(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="non autorisée"):
        updater._download("https://example.com/update.zip", tmp_path / "update.zip")


def test_release_builder_excludes_user_data(tmp_path: Path) -> None:
    import importlib.util

    builder_path = Path(__file__).resolve().parents[1] / "installer" / "build_release_package.py"
    spec = importlib.util.spec_from_file_location("release_builder", builder_path)
    assert spec and spec.loader
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    archive, checksum = builder.build(builder.get_version(), tmp_path)
    assert archive.is_file() and checksum.is_file()
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        assert "gta-ranked-studio/installer/apply_update.ps1" in names
        assert "gta-ranked-studio/studio/web/updater.py" in names
        assert "gta-ranked-studio/config.yaml" not in names
        assert not any(name.startswith("gta-ranked-studio/data/") and not name.endswith(".gitkeep") for name in names)
        assert not any("/.venv/" in name or "/models/whisper/" in name and not name.endswith(".gitkeep") for name in names)
        assert package.testzip() is None
    expected_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert expected_hash in checksum.read_text(encoding="utf-8")


def test_powershell_installer_preserves_personal_data_and_rolls_back() -> None:
    script = (Path(__file__).resolve().parents[1] / "installer" / "apply_update.ps1").read_text(encoding="utf-8-sig")
    assert "'config.yaml'" not in script.split("$rootFiles = @(", 1)[1].split(")", 1)[0]
    assert "'studio', 'installer', 'docs'" in script
    assert "work\\updates\\rollback-" in script
    assert "Tentative de restauration" in script
    assert "$replacedDirectories" in script
    assert "$replacedFiles" in script
    assert "foreach ($directoryName in $replacedDirectories)" in script
    assert "foreach ($fileName in $replacedFiles)" in script
    assert "models" not in script.split("foreach ($directoryName in @('studio', 'installer', 'docs'))", 1)[0]


def test_application_ui_exposes_integrated_update_controls() -> None:
    html = (Path(__file__).resolve().parents[1] / "studio" / "web" / "static" / "index.html").read_text(encoding="utf-8-sig")
    script = (Path(__file__).resolve().parents[1] / "studio" / "web" / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="check-updates"' in html
    assert 'id="install-update"' in html
    assert "/api/updates/check" in script
    assert "/api/updates/install" in script



def test_updater_captures_powershell_output_and_creates_bootstrap_log() -> None:
    source = (Path(__file__).resolve().parents[1] / "studio" / "web" / "updater.py").read_text(encoding="utf-8")
    assert "powershell-output.log" in source
    assert "stdout=powershell_log" in source
    assert "stderr=subprocess.STDOUT" in source
    assert "Python updater: launching PowerShell" in source
    assert "s'est arrêté immédiatement" in source


def test_powershell_update_script_logs_before_waiting_and_avoids_generic_lists() -> None:
    script = (Path(__file__).resolve().parents[1] / "installer" / "apply_update.ps1").read_text(encoding="utf-8-sig")
    assert "=== GTA Ranked Studio updater ===" in script
    assert "En attente de la fermeture" in script
    assert "New-Object 'System.Collections.Generic.List[string]'" not in script
    assert "Tentative de restauration" in script
