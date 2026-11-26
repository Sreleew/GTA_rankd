from pathlib import Path

from studio.web.model_manager import ModelManager


def test_model_manager_does_not_mark_tiny_invalid_file_as_installed(tmp_path: Path):
    model = tmp_path / "ggml-large-v3-turbo.bin"
    model.write_bytes(b"not a real whisper model")

    manager = ModelManager(model)
    status = manager.status()

    assert status["exists"] is True
    assert status["valid"] is False
    assert status["status"] == "invalid"


def test_model_manager_marks_full_size_model_as_installed(tmp_path: Path):
    model = tmp_path / "ggml-large-v3-turbo.bin"
    with model.open("wb") as stream:
        stream.truncate(1024 * 1024 * 1024)

    manager = ModelManager(model)
    status = manager.status()

    assert status["exists"] is True
    assert status["valid"] is True
    assert status["status"] == "ready"


def test_model_manager_resumes_partial_download_with_http_range(tmp_path: Path, monkeypatch):
    from studio.web import model_manager

    model = tmp_path / "ggml-large-v3-turbo.bin"
    partial = model.with_suffix(model.suffix + ".part")
    partial.write_bytes(b"a" * 64)
    manager = ModelManager(model)
    monkeypatch.setattr(model_manager, "MIN_WHISPER_MODEL_BYTES", 1)
    captured = {}

    class FakeResponse:
        status = 206
        headers = {"Content-Length": "64", "Content-Range": "bytes 64-127/128"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return self.status

        def read(self, size=-1):
            if captured.get("read"):
                return b""
            captured["read"] = True
            return b"b" * 64

    def fake_urlopen(request, timeout=0):
        captured["range"] = request.headers.get("Range")
        return FakeResponse()

    monkeypatch.setattr(model_manager.urllib.request, "urlopen", fake_urlopen)
    manager._download_whisper()

    assert captured["range"] == "bytes=64-"
    assert model.read_bytes() == b"a" * 64 + b"b" * 64
    assert not partial.exists()
    assert manager.status()["status"] == "ready"
