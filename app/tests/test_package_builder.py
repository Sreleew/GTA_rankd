"""Vérifie que le ZIP n'embarque pas les données personnelles ou les outils de développement."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import zipfile

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "installer" / "build_release_package.py"
SPEC = importlib.util.spec_from_file_location("release_package_builder", MODULE_PATH)
builder = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(builder)


def test_package_contains_runtime_and_canonical_docs_but_no_local_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = tmp_path / "app"
    docs = tmp_path / "docs"
    for path in (
        "studio/web/static", "installer", "assets/sfx", "tests",
        "tools/whisper.cpp", "data", "inbox/shorts", "out/shorts",
    ):
        (app / path).mkdir(parents=True, exist_ok=True)
    (app / "VERSION.txt").write_text("GTA Ranked Studio\nVersion: 0.8.1\n", encoding="utf-8")
    (app / "installer/build_release_package.py").write_text("developer tool", encoding="utf-8")
    (app / "NOTES-v0.8.1.txt").write_text("release notes", encoding="utf-8")
    (app / "VERIFICATION-v0.7.3.md").write_text("old checks", encoding="utf-8")
    (app / "config.yaml.default").write_text("app:\n  version: 0.8.1\n", encoding="utf-8")
    (app / "studio/config.py").write_text("# runtime config module\n", encoding="utf-8")
    for path in (
        "installer/install.ps1", "installer/apply_update.ps1",
        "studio/web/updater.py", "studio/web/static/index.html",
    ):
        (app / path).write_text("safe runtime file", encoding="utf-8")
    (app / "assets/sfx/soft_whoosh.wav").write_bytes(b"wav")
    (app / "tests/test_fake.py").write_text("dev test", encoding="utf-8")
    (app / "tools/whisper.cpp/whisper-cli.exe").write_bytes(b"local model tool")
    (app / "config.yaml").write_text("private config", encoding="utf-8")
    (app / "config.private.toml").write_text("private config", encoding="utf-8")
    (app / ".env.local").write_text("secret", encoding="utf-8")
    (app / ".python-version").write_text("3.11", encoding="utf-8")
    (app / "credentials").mkdir()
    (app / "credentials/token.json").write_text("secret", encoding="utf-8")
    (app / "data/db.sqlite").write_bytes(b"database")
    (app / "out/shorts/private.mp4").write_bytes(b"video")
    for name in builder.CANONICAL_DOCS:
        (docs / name).parent.mkdir(parents=True, exist_ok=True)
        (docs / name).write_text(f"canonical {name}", encoding="utf-8")
    monkeypatch.setattr(builder, "ROOT", app)
    monkeypatch.setattr(builder, "REPO_ROOT", tmp_path)
    package, checksum = builder.build("0.8.1", tmp_path / "dist")
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        assert "gta-ranked-studio/assets/sfx/soft_whoosh.wav" in names
        assert "gta-ranked-studio/studio/config.py" in names
        assert "gta-ranked-studio/installer/build_release_package.py" not in names
        assert not any("/NOTES-v" in name or "/VERIFICATION-v" in name for name in names)
        for name in builder.CANONICAL_DOCS:
            assert f"gta-ranked-studio/docs/{name}" in names
        assert not any("/tests/" in name or "/tools/" in name for name in names)
        assert not any(name.endswith((".sqlite", ".mp4")) for name in names)
        assert not any(
            name.endswith((".env.local", "/config.yaml", "/config.private.toml",
                           "/.python-version", "/credentials/token.json"))
            for name in names
        )
    verifier = Path(__file__).resolve().parents[2] / "tools" / "verify_release_package.py"
    result = subprocess.run(
        [sys.executable, str(verifier), "--package", str(package),
         "--checksum", str(checksum), "--version", "0.8.1"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_package_builder_never_follows_symbolic_links(tmp_path: Path) -> None:
    target = tmp_path / "private.txt"
    target.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Les liens symboliques ne sont pas disponibles sur ce runner.")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(builder, "ROOT", tmp_path)
        assert builder.should_include(link) is False
    finally:
        monkeypatch.undo()
