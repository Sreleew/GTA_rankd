from pathlib import Path
import shutil
import subprocess

import pytest

from fastapi.testclient import TestClient

from studio.config import load_config
from studio.web.app import create_app, safe_upload_name
from studio.web.short_renderer import build_filter_complex, build_render_command
import studio.web.short_renderer as short_renderer
from studio.web.app import _validate_edit_options
from studio.web.store import Store


def test_safe_upload_name_rejects_unsupported_extensions():
    assert safe_upload_name(r"C:\\fake path\\GTA moment.MP4") == "GTA_moment.mp4"
    try:
        safe_upload_name("document.pdf")
    except Exception as exc:
        assert "Format non pris en charge" in str(exc)
    else:
        raise AssertionError("A PDF should be rejected")


def test_default_vertical_filter_preserves_the_complete_landscape_source():
    graph = build_filter_complex(1080, 1920)
    assert "split=2[bgsrc][fgsrc]" in graph
    assert "force_original_aspect_ratio=decrease" in graph
    assert "boxblur" in graph
    assert "overlay=(W-w)/2:(H-h)/2" in graph
    assert "zoompan" not in graph


def test_blur_layout_keeps_the_full_landscape_source_visible():
    graph = build_filter_complex(1080, 1920, layout="blur", dynamic_zoom=False)
    assert "boxblur" in graph
    assert "overlay=(W-w)/2:(H-h)/2" in graph


def test_edit_options_are_validated_and_clamped_by_api():
    options = _validate_edit_options(
        "fill", 50, 40, True, 8, True, "Wait for it", "A chase", True,
        captions_enabled=True, caption_language="fr",
    )
    assert options["layout"] == "fill"
    assert options["crop_x"] == 50
    assert options["dynamic_zoom"] is True
    assert options["auto_trim_enabled"] is True
    assert options["captions_enabled"] is True
    assert options["caption_language"] == "fr"
    smart = _validate_edit_options("smart", 80, 50, False, 0, True, "", "")
    assert smart["layout"] == "blur"
    assert smart["crop_x"] == 80
    assert smart["caption_language"] == "config"
    try:
        _validate_edit_options("smart", 80, 50, False, 0, True, "", "", caption_language="xx")
    except Exception as exc:
        assert "langue" in str(exc).lower()
    else:
        raise AssertionError("Unsupported caption language should be rejected")
    try:
        _validate_edit_options("invalid", 50, 50, True, 8, True, "", "")
    except Exception as exc:
        assert "cadrage" in str(exc).lower()
    else:
        raise AssertionError("Invalid layout should be rejected")


def test_render_command_uses_argument_list_and_amf(tmp_path: Path):
    # On teste la construction sans lancer FFmpeg sur cette machine de test.
    command = build_render_command(
        "ffmpeg", tmp_path / "input.mp4", tmp_path / "output.mp4", encoder="h264_amf", has_audio=True,
        trim_start=4.5, trim_duration=24.0,
    )
    assert isinstance(command, list)
    assert "h264_amf" in command
    assert any(part.startswith("loudnorm=I=-14:TP=-1.5:LRA=11") for part in command)
    assert "-filter_complex" in command
    assert command[command.index("-ss") + 1] == "4.500"
    assert command[command.index("-t") + 1] == "24.000"


def test_store_creates_and_updates_job(tmp_path: Path):
    store = Store(tmp_path / "test.sqlite")
    store.create_job({"id": "job1", "source_kind": "upload", "source_path": "clip.mp4"})
    job = store.get_job("job1")
    assert job is not None
    assert job["status"] == "queued"
    store.update_job("job1", status="ready", progress=100, message="Prêt")
    updated = store.get_job("job1")
    assert updated["status"] == "ready"
    assert store.get_dashboard()["to_review"] == 1


def test_api_health_and_upload_acknowledgement(tmp_path: Path):
    source_root = Path(__file__).resolve().parents[1]
    config_text = (source_root / "config.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_text.replace("database: data/clip_bank.sqlite", f"database: {tmp_path.as_posix()}/clip_bank.sqlite")
                                  .replace("inbox_shorts: inbox/shorts", f"inbox_shorts: {tmp_path.as_posix()}/inbox")
                                  .replace("output_shorts: out/shorts", f"output_shorts: {tmp_path.as_posix()}/out/shorts")
                                  .replace("output_bestof: out/bestof", f"output_bestof: {tmp_path.as_posix()}/out/bestof")
                                  .replace("logs: logs", f"logs: {tmp_path.as_posix()}/logs")
                                  .replace("temp: work/tmp", f"temp: {tmp_path.as_posix()}/tmp")
                                  .replace("fonts: assets/fonts", f"fonts: {tmp_path.as_posix()}/fonts")
                                  .replace("prompts: prompts", f"prompts: {tmp_path.as_posix()}/prompts")
                                  .replace("models: models/whisper", f"models: {tmp_path.as_posix()}/models")
                                  .replace("tools: tools", f"tools: {tmp_path.as_posix()}/tools"), encoding="utf-8")
    config = load_config(config_path)
    app = create_app(config)
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["local_only"] is True
    model_status = client.get("/api/models/status?refresh=true")
    assert model_status.status_code == 200
    assert "whisper_diagnostic" in model_status.json()
    assert model_status.json()["whisper_diagnostic"]["available"] is False
    rejected = client.post("/api/shorts/upload", files={"file": ("clip.mp4", b"not real video", "video/mp4")}, data={"rights_confirmed": "false"})
    assert rejected.status_code == 400


def test_whisper_vulkan_verify_endpoint_persists_a_binary_bound_marker(tmp_path: Path, monkeypatch):
    import studio.web.app as app_module
    config_path = _make_isolated_app_config(tmp_path)
    tools_dir = tmp_path / "tools" / "whisper.cpp"
    tools_dir.mkdir(parents=True, exist_ok=True)
    binary = tools_dir / "whisper-cli.exe"
    binary.write_bytes(b"fake-vulkan-cli")
    model = tmp_path / "models" / "whisper" / "ggml-large-v3-turbo.bin"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b"m" * (1024 * 1024))
    monkeypatch.setattr(app_module, "probe_whisper_vulkan", lambda *args, **kwargs: {
        "verified": True, "backend": "Vulkan0", "gpu_model": "AMD Radeon RX 9060 XT",
        "model_buffer_mb": 1536.0, "reason": "Vulkan0 confirmed.",
    })
    app = create_app(load_config(config_path))
    client = TestClient(app)
    response = client.post("/api/models/whisper/verify")
    assert response.status_code == 200, response.text
    assert response.json()["verified"] is True
    status = client.get("/api/models/status?refresh=true")
    diagnostic = status.json()["whisper_diagnostic"]
    assert diagnostic["vulkan_verified"] is True
    assert diagnostic["vulkan_detected"] is True
    assert diagnostic["gpu_model"] == "AMD Radeon RX 9060 XT"
    binary.write_bytes(b"updated-cli-with-different-binary")
    stale = client.get("/api/models/status?refresh=true").json()["whisper_diagnostic"]
    assert stale["vulkan_verified"] is False

def test_whisper_gpu_button_uses_fresh_script_and_visible_feedback():
    from pathlib import Path

    static = Path(__file__).resolve().parents[1] / "studio" / "web" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.js").read_text(encoding="utf-8")
    assert html.count("peut couper les bords, y compris une webcam en bord d’écran") == 2
    assert '<script src="/static/app.js?v=0.9.4-main-voice-captions"></script>' in html
    assert '<button type="button" class="mini-button" id="verify-whisper-gpu"' in html
    assert "/api/models/whisper/verify" in js
    assert "if (verifyGpuButton) verifyGpuButton.addEventListener('click', verifyWhisperGpu);" in js
    assert "Test Vulkan en cours" in js
    assert "state.whisperGpuProbeRunning" in js

def test_ollama_verify_endpoint_checks_model_and_runs_local_inference(tmp_path: Path, monkeypatch):
    import json
    import studio.web.app as app_module

    config_path = _make_isolated_app_config(tmp_path)
    app = create_app(load_config(config_path))
    client = TestClient(app)
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = json.dumps(payload).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return self.payload

    def fake_urlopen(request, timeout=0):
        url = request if isinstance(request, str) else request.full_url
        calls.append((url, timeout))
        if url.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": "qwen2.5:7b-instruct"}]})
        if url.endswith("/api/generate"):
            body = json.loads(request.data.decode("utf-8"))
            assert body["model"] == "qwen2.5:7b-instruct"
            assert body["stream"] is False
            assert body["options"]["num_predict"] <= 8
            return FakeResponse({"response": "OK", "done": True})
        raise AssertionError(f"Unexpected Ollama URL: {url}")

    monkeypatch.setattr(app_module.urllib.request, "urlopen", fake_urlopen)
    response = client.post("/api/models/ollama/verify")
    assert response.status_code == 200, response.text
    assert response.json()["verified"] is True
    assert response.json()["model"] == "qwen2.5:7b-instruct"
    assert any(url.endswith("/api/tags") for url, _ in calls)
    assert any(url.endswith("/api/generate") for url, _ in calls)


def test_ollama_verify_endpoint_explains_when_model_is_missing(tmp_path: Path, monkeypatch):
    import json
    import studio.web.app as app_module

    config_path = _make_isolated_app_config(tmp_path)
    app = create_app(load_config(config_path))

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({"models": []}).encode("utf-8")

    monkeypatch.setattr(app_module.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    response = TestClient(app).post("/api/models/ollama/verify")
    assert response.status_code == 409
    assert "ollama pull qwen2.5:7b-instruct" in response.json()["detail"]


def test_ollama_verify_button_has_a_dedicated_visible_handler():
    static = Path(__file__).resolve().parents[1] / "studio" / "web" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.js").read_text(encoding="utf-8")
    assert '<script src="/static/app.js?v=0.9.4-main-voice-captions"></script>' in html
    assert '<button type="button" class="mini-button" id="verify-ollama"' in html
    assert "#refresh-models-secondary" in js
    assert "/api/models/ollama/verify" in js
    assert "event.target.closest('#verify-ollama, #refresh-models-secondary')" in js
    assert "verifyOllamaModel(ollamaButton)" in js
    assert "document.addEventListener('click'" in js
    assert "Test Qwen en cours..." in js
    assert "state.ollamaVerificationResult" in js

def test_validated_short_keeps_media_and_metadata_actions():
    static = Path(__file__).resolve().parents[1] / "studio" / "web" / "static"
    js = (static / "app.js").read_text(encoding="utf-8")
    assert "const mediaActions = [" in js
    assert "const metadataActions =" in js
    assert "if (job.status === 'validated')" in js
    assert '${mediaActions}${metadataActions}' in js
    assert 'data-action="copy-title"' in js
    assert 'data-action="copy-description"' in js
    assert 'data-action="copy-hashtags"' in js
    assert 'data-action="copy-social"' in js
    assert "['copy-title', 'copy-description', 'copy-hashtags', 'copy-social'].includes(action)" in js
    assert "metadata.quality_report" in js
    assert "Contrôle qualité" in js


def test_root_page_disables_stale_html_cache():
    from studio.web.app import create_app
    from studio.config import load_config
    from fastapi.testclient import TestClient

    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    client = TestClient(create_app(load_config(config_path)))
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"

def test_clip_enters_library_only_after_atomic_validation(tmp_path: Path):
    store = Store(tmp_path / "validation.sqlite")
    store.create_job({
        "id": "approved-job",
        "source_kind": "upload",
        "source_path": str(tmp_path / "source.mp4"),
        "source_hash": "abc123",
        "streamer": "ExampleStreamer",
        "metadata": {"title": "Titre test", "description": "Description test", "hashtags": ["#GTA", "#Gaming"]},
    })
    store.update_job(
        "approved-job",
        status="ready",
        progress=100,
        duration=12.5,
        output_path=str(tmp_path / "render.mp4"),
        thumbnail_path=str(tmp_path / "thumbnail.jpg"),
    )

    assert store.list_clips() == []
    validated = store.validate_job_and_add_to_clip_bank("approved-job")
    assert validated is not None
    assert validated["status"] == "validated"
    assert validated["metadata"] == {"title": "Titre test", "description": "Description test", "hashtags": ["#GTA", "#Gaming"]}
    clips = store.list_clips()
    assert len(clips) == 1
    assert clips[0]["job_id"] == "approved-job"
    assert clips[0]["status"] == "validated"
    assert store.validate_job_and_add_to_clip_bank("approved-job") is None


def test_dynamic_zoom_is_a_smooth_punch_in_not_a_hard_step():
    graph = build_filter_complex(1080, 1920, dynamic_zoom=True, peak_timestamp=4.0, zoom_percent=10)
    assert "sin(PI*(in_time-3.550)/1.300)" in graph
    assert "(0.100)" in graph


def test_render_command_mixes_optional_original_whoosh(tmp_path: Path):
    sfx = tmp_path / "whoosh.wav"
    sfx.write_bytes(b"fake-wav-for-command-builder")
    command = build_render_command(
        "ffmpeg", tmp_path / "input.mp4", tmp_path / "output.mp4",
        encoder="libx264", has_audio=True, sound_effect_path=sfx, sound_effect_offset=2.35,
    )
    graph = command[command.index("-filter_complex") + 1]
    assert str(sfx.resolve()) in command
    assert "adelay=2350:all=1" in graph
    assert "asplit=2[main_for_ducking][main_for_mix]" in graph
    assert "[main_for_ducking]" in graph and "[main_for_mix]" in graph
    assert "amix=inputs=2" in graph
    assert command[command.index("-map", command.index("-filter_complex")) + 1] == "[v]"


def test_highlight_url_api_only_accepts_twitch_vods_or_clips(tmp_path: Path):
    source_root = Path(__file__).resolve().parents[1]
    config_text = (source_root / "config.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        config_text.replace("database: data/clip_bank.sqlite", f"database: {tmp_path.as_posix()}/clip_bank.sqlite")
        .replace("inbox_shorts: inbox/shorts", f"inbox_shorts: {tmp_path.as_posix()}/inbox")
        .replace("output_shorts: out/shorts", f"output_shorts: {tmp_path.as_posix()}/out/shorts")
        .replace("output_bestof: out/bestof", f"output_bestof: {tmp_path.as_posix()}/out/bestof")
        .replace("logs: logs", f"logs: {tmp_path.as_posix()}/logs")
        .replace("temp: work/tmp", f"temp: {tmp_path.as_posix()}/tmp")
        .replace("fonts: assets/fonts", f"fonts: {tmp_path.as_posix()}/fonts")
        .replace("prompts: prompts", f"prompts: {tmp_path.as_posix()}/prompts")
        .replace("models: models/whisper", f"models: {tmp_path.as_posix()}/models")
        .replace("tools: tools", f"tools: {tmp_path.as_posix()}/tools"),
        encoding="utf-8",
    )
    app = create_app(load_config(config_path))
    client = TestClient(app)
    denied = client.post(
        "/api/highlights/scan/url",
        data={"url": "https://www.youtube.com/watch?v=example", "rights_confirmed": "true"},
    )
    assert denied.status_code == 400
    no_rights = client.post(
        "/api/highlights/scan/url",
        data={"url": "https://www.twitch.tv/videos/12345", "rights_confirmed": "false"},
    )
    assert no_rights.status_code == 400
    one_sided_range = client.post(
        "/api/highlights/scan/url",
        data={"url": "https://www.twitch.tv/videos/12345", "rights_confirmed": "true", "window_start": "30"},
    )
    assert one_sided_range.status_code == 400
    scans = client.get("/api/highlights")
    assert scans.status_code == 200
    assert scans.json() == []


def _make_isolated_app_config(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[1]
    config_text = (source_root / "config.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    replacements = {
        "database: data/clip_bank.sqlite": f"database: {tmp_path.as_posix()}/clip_bank.sqlite",
        "inbox_shorts: inbox/shorts": f"inbox_shorts: {tmp_path.as_posix()}/inbox",
        "output_shorts: out/shorts": f"output_shorts: {tmp_path.as_posix()}/out/shorts",
        "output_bestof: out/bestof": f"output_bestof: {tmp_path.as_posix()}/out/bestof",
        "logs: logs": f"logs: {tmp_path.as_posix()}/logs",
        "temp: work/tmp": f"temp: {tmp_path.as_posix()}/tmp",
        "fonts: assets/fonts": f"fonts: {tmp_path.as_posix()}/fonts",
        "prompts: prompts": f"prompts: {tmp_path.as_posix()}/prompts",
        "models: models/whisper": f"models: {tmp_path.as_posix()}/models",
        "tools: tools": f"tools: {tmp_path.as_posix()}/tools",
    }
    for old, new in replacements.items():
        config_text = config_text.replace(old, new)
    config_path.write_text(config_text, encoding="utf-8")
    return config_path


def test_highlight_url_accepts_hhmmss_ranges_for_long_vods(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    submitted: list[str] = []
    app.state.highlight_scanner.submit = lambda scan_id: submitted.append(scan_id)
    client = TestClient(app)

    response = client.post(
        "/api/highlights/scan/url",
        data={
            "url": "https://www.twitch.tv/videos/123456",
            "rights_confirmed": "true",
            "window_start": "12:30:00",
            "window_end": "15:00:00",
        },
    )

    assert response.status_code == 202, response.text
    scan = app.state.store.get_highlight_scan(response.json()["id"])
    assert scan is not None
    assert scan["window_start"] == 12 * 3600 + 30 * 60
    assert scan["window_end"] == 15 * 3600
    assert submitted == [response.json()["id"]]


def test_highlight_url_rejects_invalid_hhmmss_components(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    client = TestClient(app)

    response = client.post(
        "/api/highlights/scan/url",
        data={
            "url": "https://www.twitch.tv/videos/123456",
            "rights_confirmed": "true",
            "window_start": "12:75:00",
            "window_end": "14:00:00",
        },
    )

    assert response.status_code == 400
    assert "HH:MM:SS" in response.json()["detail"]


def test_highlight_url_batch_splits_nineteen_hour_vod_into_atomic_hourly_scans(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    submitted: list[str] = []
    app.state.highlight_scanner.start = lambda: None
    app.state.highlight_scanner.submit = lambda scan_id: submitted.append(scan_id)
    client = TestClient(app)

    response = client.post(
        "/api/highlights/scan/url/batch",
        data={
            "url": "https://www.twitch.tv/videos/123456",
            "rights_confirmed": "true",
            "window_start": "00:00:00",
            "window_end": "19:00:00",
            "chunk_minutes": "60",
            "streamer": "TestStreamer",
        },
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["count"] == 19
    assert len(payload["scans"]) == 19
    scans = [
        scan for scan in app.state.store.list_highlight_scans(100)
        if scan["metadata"].get("batch_id") == payload["batch_id"]
    ]
    scans.sort(key=lambda scan: scan["metadata"]["batch_index"])
    assert len(scans) == 19
    assert scans[0]["window_start"] == 0
    assert scans[0]["window_end"] == 3600
    assert scans[-1]["window_start"] == 18 * 3600
    assert scans[-1]["window_end"] == 19 * 3600
    assert all(scan["window_end"] - scan["window_start"] <= 3 * 3600 for scan in scans)
    assert [scan["metadata"]["batch_index"] for scan in scans] == list(range(1, 20))
    assert all(scan["metadata"]["batch_count"] == 19 for scan in scans)
    assert set(submitted) == {scan["id"] for scan in scans}


def test_highlight_url_batch_rejects_short_twitch_clips(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    app.state.highlight_scanner.start = lambda: None
    app.state.highlight_scanner.submit = lambda _scan_id: None
    client = TestClient(app)

    response = client.post(
        "/api/highlights/scan/url/batch",
        data={
            "url": "https://clips.twitch.tv/ExampleClip",
            "rights_confirmed": "true",
            "window_start": "00:00:00",
            "window_end": "01:00:00",
            "chunk_minutes": "30",
        },
    )

    assert response.status_code == 400
    assert "réservé aux VOD Twitch" in response.json()["detail"]
    assert app.state.store.list_highlight_scans(100) == []


def test_highlight_url_batch_rejects_too_many_segments_and_invalid_chunk_size(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    submitted: list[str] = []
    app.state.highlight_scanner.submit = lambda scan_id: submitted.append(scan_id)
    client = TestClient(app)
    base = {
        "url": "https://www.twitch.tv/videos/123456",
        "rights_confirmed": "true",
        "window_start": "00:00:00",
        "window_end": "30:00:00",
    }

    too_many = client.post(
        "/api/highlights/scan/url/batch",
        data={**base, "chunk_minutes": "30"},
    )
    bad_chunk = client.post(
        "/api/highlights/scan/url/batch",
        data={**base, "window_end": "02:00:00", "chunk_minutes": "17"},
    )

    assert too_many.status_code == 400
    assert "48 tranches" in too_many.json()["detail"]
    assert bad_chunk.status_code == 400
    assert "durée de tranche" in bad_chunk.json()["detail"]
    assert app.state.store.list_highlight_scans(100) == []
    assert submitted == []


def test_highlight_batch_response_provides_one_global_deduplicated_shortlist(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    store = app.state.store
    batch_id = "long-vod-batch"
    for index, scan_id in enumerate(("segment-1", "segment-2"), start=1):
        store.create_highlight_scan({
            "id": scan_id,
            "source_kind": "url",
            "source_url": "https://www.twitch.tv/videos/123456",
            "streamer": "TestStreamer",
            "rights_confirmed": True,
            "window_start": (index - 1) * 3600,
            "window_end": index * 3600,
            "metadata": {
                "batch_id": batch_id,
                "batch_index": index,
                "batch_count": 2,
            },
        })
        store.update_highlight_scan(scan_id, status="completed", progress=100, source_title="Long VOD")
    repeated = (
        "I cannot believe this police car just flew over the entire bridge "
        "and landed right next to the casino entrance"
    )
    store.save_highlight_candidates("segment-1", [{
        "id": "candidate-1",
        "rank": 1,
        "start_time": 120.0,
        "end_time": 190.0,
        "media_start": 120.0,
        "media_end": 190.0,
        "score": 95.0,
        "transcript": repeated,
    }])
    store.save_highlight_candidates("segment-2", [
        {
            "id": "candidate-2",
            "rank": 1,
            "start_time": 3720.0,
            "end_time": 3790.0,
            "media_start": 120.0,
            "media_end": 190.0,
            "score": 93.0,
            "transcript": repeated,
        },
        {
            "id": "candidate-3",
            "rank": 2,
            "start_time": 4500.0,
            "end_time": 4570.0,
            "media_start": 900.0,
            "media_end": 970.0,
            "score": 90.0,
            "transcript": "The mission marker vanished after we crossed the highway and entered the tunnel",
        },
    ])
    client = TestClient(app)

    response = client.get("/api/highlights?limit=100")

    assert response.status_code == 200
    scans = response.json()
    anchor = next(scan for scan in scans if scan["id"] == "segment-1")
    summary = anchor["batch_summary"]
    assert summary["total"] == 2
    assert summary["completed"] == 2
    assert len(summary["candidates"]) == 2
    assert [candidate["id"] for candidate in summary["candidates"]] == ["candidate-1", "candidate-3"]
    assert [candidate["scan_id"] for candidate in summary["candidates"]] == ["segment-1", "segment-2"]
    assert summary["candidates"][0]["rank"] == 1
    assert summary["candidates"][1]["rank"] == 2


def test_highlight_url_accepts_blank_optional_range_and_queues_scan(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    submitted: list[str] = []
    app.state.highlight_scanner.submit = lambda scan_id: submitted.append(scan_id)
    client = TestClient(app)
    response = client.post(
        "/api/highlights/scan/url",
        data={
            "url": "https://www.twitch.tv/videos/123456",
            "streamer": "TestStreamer",
            "rights_confirmed": "true",
            "window_start": "",
            "window_end": "",
        },
    )
    assert response.status_code == 202, response.text
    scan_id = response.json()["id"]
    scan = app.state.store.get_highlight_scan(scan_id)
    assert scan is not None
    assert scan["source_kind"] == "url"
    assert scan["window_start"] is None
    assert scan["window_end"] is None
    assert submitted == [scan_id]


def test_highlight_candidate_creates_short_with_source_range(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    source = tmp_path / "long-vod.mp4"
    source.write_bytes(b"test-media-placeholder")
    scan_id = "completed-scan"
    candidate_id = "candidate-1"
    app.state.store.create_highlight_scan({
        "id": scan_id,
        "source_kind": "upload",
        "source_path": str(source),
        "source_title": "Long VOD",
        "streamer": "TestStreamer",
        "rights_confirmed": True,
    })
    app.state.store.update_highlight_scan(scan_id, status="completed", progress=100)
    app.state.store.save_highlight_candidates(scan_id, [{
        "id": candidate_id,
        "rank": 1,
        "start_time": 125.0,
        "end_time": 160.0,
        "media_start": 125.0,
        "media_end": 160.0,
        "score": 88.0,
        "audio_score": 0.9,
        "speech_score": 0.8,
        "reaction_score": 0.7,
        "reasons": ["Pic d'énergie audio"],
        "transcript": "BRO WHAT",
    }])
    submitted: list[str] = []
    app.state.runner.submit = lambda job_id: submitted.append(job_id)
    client = TestClient(app)
    response = client.post(f"/api/highlights/{scan_id}/candidates/{candidate_id}/create-short")
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    job = app.state.store.get_job(job_id)
    assert job is not None
    assert job["source_path"] == str(source.resolve())
    assert job["source_url"] is None
    assert job["metadata"]["options"]["source_range"] == {"start": 125.0, "end": 160.0}
    assert job["metadata"]["highlight_score"] == 88.0
    candidate = app.state.store.get_highlight_candidate(scan_id, candidate_id)
    assert candidate is not None and candidate["created_job_id"] == job_id
    assert submitted == [job_id]


def test_queued_short_and_highlight_scan_can_be_cancelled_via_api(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    store = app.state.store
    store.create_job({"id": "cancel-short", "source_kind": "upload", "source_path": "missing.mp4"})
    store.create_highlight_scan({"id": "cancel-scan", "source_kind": "upload", "source_path": "missing.mp4"})
    client = TestClient(app)

    short_response = client.post("/api/jobs/cancel-short/cancel")
    scan_response = client.post("/api/highlights/cancel-scan/cancel")

    assert short_response.status_code == 200
    assert scan_response.status_code == 200
    assert store.get_job("cancel-short")["status"] == "cancelled"
    assert store.get_highlight_scan("cancel-scan")["status"] == "cancelled"



def test_extract_twitch_source_metadata_prefers_broadcaster_over_clip_creator():
    from studio.web.worker import extract_twitch_source_metadata

    title, streamer = extract_twitch_source_metadata({
        "title": "Wild police chase",
        "channel": "ActualStreamer",
        "uploader": "PersonWhoCreatedClip",
        "creator": "AnotherClipCreator",
    })

    assert title == "Wild police chase"
    assert streamer == "ActualStreamer"


def test_extract_twitch_source_metadata_uses_safe_fallbacks():
    from studio.web.worker import extract_twitch_source_metadata

    title, streamer = extract_twitch_source_metadata({
        "id": "abc123",
        "channel": "  ",
        "uploader": "FallbackStreamer",
    })

    assert title == "Twitch source abc123"
    assert streamer == "FallbackStreamer"

    title, streamer = extract_twitch_source_metadata({})
    assert title == "Source Twitch"
    assert streamer == ""



def test_twitch_download_reports_throttled_yt_dlp_progress(tmp_path: Path, monkeypatch):
    import sys
    import types

    from studio.web import worker as worker_module
    from studio.web.worker import JobRunner

    class FakeConfig:
        def path_for(self, section, key):
            assert (section, key) == ("paths", "temp")
            return tmp_path / "temp"

    class RecordingStore:
        def __init__(self):
            self.updates = []

        def update_job(self, job_id, **fields):
            self.updates.append((job_id, fields))

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options
            self.downloaded_path = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def extract_info(self, url, download=True):
            assert url == "https://clips.twitch.tv/ExampleClip"
            assert download is True
            progress_hook = self.options["progress_hooks"][0]
            progress_hook({
                "status": "downloading", "downloaded_bytes": 25 * 1024 * 1024, "total_bytes": 100 * 1024 * 1024,
                "speed": 1.5 * 1024 * 1024, "eta": 12.4,
            })
            progress_hook({
                "status": "downloading", "downloaded_bytes": 75 * 1024 * 1024, "total_bytes_estimate": 100 * 1024 * 1024,
                "speed": 512 * 1024, "eta": 5.2,
            })
            self.downloaded_path = Path(self.options["outtmpl"].replace("%(ext)s", "mp4"))
            self.downloaded_path.parent.mkdir(parents=True, exist_ok=True)
            self.downloaded_path.write_bytes(b"test video")
            progress_hook({"status": "finished"})
            return {"title": "Example Twitch clip"}

        def prepare_filename(self, info):
            assert info["title"] == "Example Twitch clip"
            return str(self.downloaded_path)

    fake_ytdlp = types.ModuleType("yt_dlp")
    fake_ytdlp.YoutubeDL = FakeYoutubeDL
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_ytdlp)
    ticks = iter((10.0, 10.5))
    monkeypatch.setattr(worker_module.time, "monotonic", lambda: next(ticks))

    store = RecordingStore()
    runner = JobRunner.__new__(JobRunner)
    runner.config = FakeConfig()
    runner.store = store

    downloaded_path, info = runner._download("test-job", "https://clips.twitch.tv/ExampleClip")

    assert downloaded_path.is_file()
    assert info["title"] == "Example Twitch clip"
    assert [fields["progress"] for _, fields in store.updates] == [12, 17, 19]
    messages = [fields["message"] for _, fields in store.updates]
    assert "25 %" in messages[0]
    assert "25.0/100.0 MiB" in messages[0]
    assert "1.5 MiB/s" in messages[0]
    assert "reste 00:12" in messages[0]
    assert "75 %" in messages[1]
    assert "75.0/100.0 MiB" in messages[1]
    assert "512 KiB/s" in messages[1]
    assert "reste 00:05" in messages[1]
    assert messages[-1] == "Téléchargement terminé · préparation du Short"
    assert all(job_id == "test-job" for job_id, _ in store.updates)


def test_download_progress_metrics_ignore_missing_or_invalid_values():
    from studio.web.worker import _download_metrics_suffix

    assert _download_metrics_suffix({"speed": None, "eta": None}) == ""
    assert _download_metrics_suffix({"speed": float("nan"), "eta": -1}) == ""
    assert _download_metrics_suffix({"speed": 512, "eta": 3661}) == " · 512 B/s · reste 1:01:01"


def test_short_url_api_accepts_only_public_twitch_clip_or_vod_urls(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    submitted: list[str] = []
    app.state.runner.submit = lambda job_id: submitted.append(job_id)
    client = TestClient(app)

    invalid_urls = [
        "https://www.youtube.com/watch?v=example",
        "https://example.com/clip/ExampleClip",
        "https://twitch.tv.example.com/clip/ExampleClip",
        "http://clips.twitch.tv/ExampleClip",
        "https://www.twitch.tv/some-streamer",
        "not-a-url",
        "https://clips.twitch.tv/" + ("a" * 2100),
    ]
    for url in invalid_urls:
        response = client.post(
            "/api/shorts/url",
            data={"url": url, "rights_confirmed": "true"},
        )
        assert response.status_code == 400, (url, response.text)

    assert app.state.store.list_jobs(100) == []
    assert submitted == []

    valid_urls = [
        "https://clips.twitch.tv/ExampleClip",
        "https://www.twitch.tv/some-streamer/clip/ExampleClip",
        "https://www.twitch.tv/videos/123456?t=1h2m3s",
    ]
    created_ids = []
    for url in valid_urls:
        response = client.post(
            "/api/shorts/url",
            data={"url": url, "rights_confirmed": "true"},
        )
        assert response.status_code == 202, response.text
        job_id = response.json()["id"]
        created_ids.append(job_id)
        job = app.state.store.get_job(job_id)
        assert job is not None
        assert job["source_url"] == url
        assert job["status"] == "queued"
        assert job["metadata"]["options"]["dynamic_zoom"] is False

    assert submitted == created_ids


def test_probe_media_scales_ffprobe_timeout_to_input_size(monkeypatch, tmp_path):
    source = tmp_path / "twitch-clip.mp4"
    source.write_bytes(b"media")
    calls = {}

    monkeypatch.setattr(short_renderer, "resolve_executable", lambda _name: "ffprobe")

    def fake_run_command(args, *, timeout=None, cwd=None):
        calls["timeout"] = timeout
        return short_renderer.subprocess.CompletedProcess(
            args, 0,
            stdout='{"streams":[{"codec_type":"video","width":1920,"height":1080,"avg_frame_rate":"30/1"}],"format":{"duration":"90"}}',
            stderr="",
        )

    monkeypatch.setattr(short_renderer, "run_command", fake_run_command)
    result = short_renderer.probe_media(source)

    assert result["duration"] == 90
    assert calls["timeout"] == short_renderer.probe_timeout_for_file(source)
    assert calls["timeout"] >= 300


def test_probe_media_respects_explicit_timeout(monkeypatch, tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"media")
    calls = {}
    monkeypatch.setattr(short_renderer, "resolve_executable", lambda _name: "ffprobe")

    def fake_run_command(args, *, timeout=None, cwd=None):
        calls["timeout"] = timeout
        return short_renderer.subprocess.CompletedProcess(
            args, 0,
            stdout='{"streams":[{"codec_type":"video","width":1920,"height":1080}],"format":{"duration":"30"}}',
            stderr="",
        )

    monkeypatch.setattr(short_renderer, "run_command", fake_run_command)
    short_renderer.probe_media(source, timeout=42)
    assert calls["timeout"] == 42


def test_best_of_plan_api_requires_validated_local_clips_and_preserves_order(tmp_path: Path):
    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    client = TestClient(app)
    clip_ids = ["clip-a", "clip-b", "clip-c", "clip-d"]
    for clip_id in clip_ids:
        output = tmp_path / f"{clip_id}.mp4"
        output.write_bytes(b"rendered")
        with app.state.store._connect() as connection:
            connection.execute(
                """INSERT INTO jobs (id, status, source_kind, created_at, updated_at)
                   VALUES (?, 'validated', 'upload', ?, ?)""",
                (clip_id, "2026-11-27T12:00:00", "2026-11-27T12:00:00"),
            )
            connection.execute(
                """INSERT INTO clips (id, job_id, date_key, duration, output_path, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'validated', ?)""",
                (clip_id, clip_id, "2026-11-27", 140, str(output), "2026-11-27T12:00:00"),
            )

    response = client.post(
        "/api/bestof/plan",
        json={"clip_ids": ["clip-c", "clip-a", "clip-d", "clip-b"], "date_key": "2026-11-27"},
    )
    assert response.status_code == 200, response.text
    plan = response.json()
    assert [clip["id"] for clip in plan["clips"]] == ["clip-c", "clip-a", "clip-d", "clip-b"]
    assert plan["formatted_duration"] == "09:20"
    assert plan["ready_for_render"] is True

    wrong_day = client.post(
        "/api/bestof/plan",
        json={"clip_ids": ["clip-a"], "date_key": "2026-11-26"},
    )
    assert wrong_day.status_code == 400
    assert "date sélectionnée" in wrong_day.json()["detail"]


def test_daily_best_of_ui_exposes_selection_order_and_duration_validation():
    static = Path(__file__).resolve().parents[1] / "studio" / "web" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.js").read_text(encoding="utf-8")
    assert 'id="bestof-available"' in html
    assert 'id="bestof-selected"' in html
    assert 'id="bestof-validate"' in html
    assert 'id="bestof-render"' in html
    assert "/api/bestof/render" in js
    assert "/api/bestof/jobs/" in js
    assert "/api/bestof/plan" in js
    assert "data-bestof-up" in js
    assert "data-bestof-down" in js
    assert "total >= 540 && total <= 660" in js
    assert 'id="bestof-history"' in html
    assert "/api/bestof/jobs?limit=10" in js
    assert "bestOfHistoryPoll" in js
    assert "progress-label" in js
    assert "data-retry-bestof" in js
    assert "/api/bestof/jobs/${encodeURIComponent(jobId)}/retry" in js
    assert "retryBestOfJob" in js


def test_best_of_store_recovers_interrupted_jobs_and_keeps_completed_history(tmp_path: Path):
    store = Store(tmp_path / "bestof.sqlite")
    store.create_best_of_job({
        "id": "bestof-running",
        "status": "running",
        "progress": 35,
        "message": "Assemblage en cours",
        "date_key": "2026-11-27",
        "clip_count": 4,
        "total_duration": 560,
        "plan": {"clips": [{"id": "clip-a"}]},
        "output_path": str(tmp_path / "running.mp4"),
    })
    store.create_best_of_job({
        "id": "bestof-completed",
        "status": "completed",
        "progress": 100,
        "message": "Daily Best Of prêt",
        "date_key": "2026-11-26",
        "clip_count": 4,
        "total_duration": 560,
        "plan": {"clips": [{"id": "clip-b"}]},
        "output_path": str(tmp_path / "completed.mp4"),
        "output_url": "/outputs/bestof/completed.mp4",
        "result": {"width": 1920, "height": 1080},
    })

    interrupted = store.get_best_of_job("bestof-running")
    assert interrupted is not None
    assert interrupted["plan"]["clips"][0]["id"] == "clip-a"
    assert interrupted["progress"] == 35
    assert store.get_best_of_job("bestof-completed")["result"]["width"] == 1920

    assert store.recover_interrupted_best_of_jobs() == 1
    recovered = store.get_best_of_job("bestof-running")
    assert recovered["status"] == "error"
    assert "interrompu" in recovered["message"]
    assert recovered["plan"]["clips"][0]["id"] == "clip-a"
    assert store.get_best_of_job("bestof-completed")["status"] == "completed"
    assert {job["id"] for job in store.list_best_of_jobs(10)} == {"bestof-completed", "bestof-running"}


def test_daily_best_of_render_history_survives_app_restart(tmp_path: Path, monkeypatch):
    from types import SimpleNamespace

    import studio.web.app as app_module

    config = load_config(_make_isolated_app_config(tmp_path))
    app = create_app(config)
    client = TestClient(app)
    clip_ids = ["episode-a", "episode-b", "episode-c", "episode-d"]
    for clip_id in clip_ids:
        output = tmp_path / f"{clip_id}.mp4"
        output.write_bytes(b"rendered short")
        with app.state.store._connect() as connection:
            connection.execute(
                """INSERT INTO jobs (id, status, source_kind, created_at, updated_at)
                   VALUES (?, 'validated', 'upload', ?, ?)""",
                (clip_id, "2026-11-27T12:00:00", "2026-11-27T12:00:00"),
            )
            connection.execute(
                """INSERT INTO clips (id, job_id, date_key, duration, output_path, status, created_at)
                   VALUES (?, ?, '2026-11-27', 140, ?, 'validated', ?)""",
                (clip_id, clip_id, str(output), "2026-11-27T12:00:00"),
            )

    def fake_render(plan, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"complete Daily Best Of")
        return {"width": 1920, "height": 1080, "duration": 560, "clip_count": len(plan["clips"])}

    class ImmediateThread:
        def __init__(self, *, target, name, daemon):
            self.target = target

        def start(self):
            self.target()

    with monkeypatch.context() as patcher:
        patcher.setattr(app_module, "render_best_of_episode", fake_render)
        patcher.setattr(app_module, "run_quiet", lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="",
        ))
        patcher.setattr(app_module, "threading", SimpleNamespace(Thread=ImmediateThread))
        response = client.post(
            "/api/bestof/render",
            json={"clip_ids": clip_ids, "date_key": "2026-11-27"},
        )

    assert response.status_code == 202, response.text
    render_id = response.json()["id"]
    completed = client.get(f"/api/bestof/jobs/{render_id}")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["file_available"] is True
    assert completed.json()["output_url"].endswith(".mp4")
    history = client.get("/api/bestof/jobs?limit=10")
    assert history.status_code == 200
    assert any(job["id"] == render_id and job["status"] == "completed" for job in history.json())

    app.state.store.create_best_of_job({
        "id": "bestof-interrupted-on-exit",
        "status": "running",
        "progress": 42,
        "message": "Assemblage et encodage 16:9",
        "date_key": "2026-11-27",
        "clip_count": 4,
        "total_duration": 560,
        "plan": {"clips": [{"id": clip_ids[0]}]},
        "output_path": str(tmp_path / "partial.mp4"),
    })
    restarted_app = create_app(config)
    restarted_client = TestClient(restarted_app)
    interrupted = restarted_client.get("/api/bestof/jobs/bestof-interrupted-on-exit")
    assert interrupted.status_code == 200
    assert interrupted.json()["status"] == "error"
    assert "interrompu" in interrupted.json()["message"]
    restored_completed = restarted_client.get(f"/api/bestof/jobs/{render_id}")
    assert restored_completed.status_code == 200
    assert restored_completed.json()["status"] == "completed"
    blocked_completed = restarted_client.post(f"/api/bestof/jobs/{render_id}/retry")
    assert blocked_completed.status_code == 409

    retryable_id = "a" * 32
    retry_plan = restarted_app.state.store.get_best_of_job(render_id)["plan"]
    restarted_app.state.store.create_best_of_job({
        "id": retryable_id,
        "status": "error",
        "progress": 100,
        "message": "Rendu interrompu",
        "date_key": "2026-11-27",
        "clip_count": 4,
        "total_duration": 560,
        "plan": retry_plan,
        "output_path": str(tmp_path / "failed.mp4"),
        "error": "Simulated render interruption",
    })
    with monkeypatch.context() as patcher:
        patcher.setattr(app_module, "render_best_of_episode", fake_render)
        patcher.setattr(app_module, "run_quiet", lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="",
        ))
        patcher.setattr(app_module, "threading", SimpleNamespace(Thread=ImmediateThread))
        retried = restarted_client.post(f"/api/bestof/jobs/{retryable_id}/retry")
        assert retried.status_code == 202, retried.text
        retry_id = retried.json()["id"]
        assert retry_id != retryable_id
        retried_job = restarted_client.get(f"/api/bestof/jobs/{retry_id}")
        assert retried_job.status_code == 200
        assert retried_job.json()["status"] == "completed"
        assert retried_job.json()["file_available"] is True
        duplicate_retry = restarted_client.post(f"/api/bestof/jobs/{retryable_id}/retry")
        assert duplicate_retry.status_code == 409


def test_retry_failed_twitch_url_creates_a_fresh_download_job(tmp_path: Path):
    config = load_config(_make_isolated_app_config(tmp_path))
    app = create_app(config)
    submitted: list[str] = []
    app.state.runner.submit = lambda job_id: submitted.append(job_id)
    client = TestClient(app)

    created = client.post(
        "/api/shorts/url",
        data={
            "url": "https://clips.twitch.tv/ExampleClipSlug",
            "rights_confirmed": "true",
            "streamer": "ExampleStreamer",
            "note": "Retry this clip",
            "layout": "smart",
        },
    )
    assert created.status_code == 202, created.text
    original_id = created.json()["id"]
    app.state.store.update_job(original_id, status="error", message="Download failed", error="Temporary Twitch error")
    submitted.clear()

    retried = client.post(f"/api/jobs/{original_id}/reprocess")
    assert retried.status_code == 202, retried.text
    new_id = retried.json()["id"]
    assert new_id != original_id
    assert submitted == [new_id]

    new_job = app.state.store.get_job(new_id)
    assert new_job is not None
    assert new_job["status"] == "queued"
    assert new_job["source_kind"] == "url"
    assert new_job["source_url"] == "https://clips.twitch.tv/ExampleClipSlug"
    assert new_job["streamer"] == "ExampleStreamer"
    assert new_job["note"] == "Retry this clip"


def test_download_size_suffix_handles_unknown_or_invalid_totals():
    from studio.web.worker import _download_size_suffix

    mib = 1024 * 1024
    assert _download_size_suffix({"downloaded_bytes": 2 * mib, "total_bytes": None}) == " · 2.0 MiB"
    assert _download_size_suffix({"downloaded_bytes": 0, "total_bytes": 10 * mib}) == ""
    assert _download_size_suffix({"downloaded_bytes": "invalid", "total_bytes": 10}) == ""


def test_best_of_filter_graph_builds_landscape_blur_canvas_and_concat():
    from studio.web.best_of import build_best_of_filter_graph

    graph = build_best_of_filter_graph(2, [0, 1])
    assert "[0:v:0]split=2" in graph
    assert "scale=1920:1080" in graph
    assert "boxblur=24:8" in graph
    assert "concat=n=2:v=1:a=1[outv][outa]" in graph
    assert "[1:a:0]aresample=48000" in graph


def test_best_of_filter_graph_rejects_mismatched_audio_inputs():
    import pytest
    from studio.web.best_of import build_best_of_filter_graph

    with pytest.raises(ValueError, match="plan vidéo"):
        build_best_of_filter_graph(2, [0])


def test_best_of_render_endpoint_runs_in_background_and_returns_output_url(tmp_path: Path, monkeypatch):
    import time
    from types import SimpleNamespace
    import studio.web.app as app_module

    app = create_app(load_config(_make_isolated_app_config(tmp_path)))
    client = TestClient(app)
    clip_ids = ["episode-a", "episode-b", "episode-c", "episode-d"]
    for clip_id in clip_ids:
        output = tmp_path / f"{clip_id}.mp4"
        output.write_bytes(b"rendered")
        with app.state.store._connect() as connection:
            connection.execute(
                """INSERT INTO jobs (id, status, source_kind, created_at, updated_at)
                   VALUES (?, 'validated', 'upload', ?, ?)""",
                (clip_id, "2026-11-27T12:00:00", "2026-11-27T12:00:00"),
            )
            connection.execute(
                """INSERT INTO clips (id, job_id, date_key, duration, output_path, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'validated', ?)""",
                (clip_id, clip_id, "2026-11-27", 140, str(output), "2026-11-27T12:00:00"),
            )

    progress_updates = []

    def fake_render(plan, output_path, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        if callable(progress_callback):
            progress_callback(52, "Encodage 16:9 · 52%")
            progress_updates.append((52, "Encodage 16:9 · 52%"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"episode")
        return {"output_path": str(output_path), "duration": 560, "width": 1920, "height": 1080}

    monkeypatch.setattr(app_module, "render_best_of_episode", fake_render)
    monkeypatch.setattr(
        app_module, "run_quiet",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    started = client.post(
        "/api/bestof/render",
        json={"clip_ids": clip_ids, "date_key": "2026-11-27"},
    )
    assert started.status_code == 202, started.text
    job_id = started.json()["id"]

    deadline = time.time() + 3
    job = client.get(f"/api/bestof/jobs/{job_id}")
    while job.json()["status"] not in {"completed", "error"} and time.time() < deadline:
        time.sleep(0.02)
        job = client.get(f"/api/bestof/jobs/{job_id}")

    assert job.status_code == 200
    assert job.json()["status"] == "completed", job.json()
    assert job.json()["output_url"].startswith("/outputs/bestof/2026-11-27/")
    assert progress_updates == [(52, "Encodage 16:9 · 52%")]

def test_batch_twitch_short_import_queues_valid_urls_and_reports_invalid_ones(tmp_path: Path):
    config = load_config(_make_isolated_app_config(tmp_path))
    app = create_app(config)
    queued = []
    app.state.runner.submit = lambda job_id: queued.append(job_id)
    client = TestClient(app)

    response = client.post(
        "/api/shorts/url/batch",
        data={
            "urls": "\n".join([
                "https://clips.twitch.tv/FirstClip",
                "https://www.twitch.tv/videos/123456789",
                "https://clips.twitch.tv/ThirdClip",
                "https://clips.twitch.tv/FirstClip",
                "https://example.com/not-twitch",
            ]),
            "rights_confirmed": "true",
            "streamer": "Test streamer",
            "layout": "blur",
        },
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["created_count"] == 3
    assert payload["rejected_count"] == 1
    assert len(queued) == 3
    assert len(payload["jobs"]) == 3
    assert len(payload["batch_id"]) == 32
    assert payload["rejected"][0]["url"] == "https://example.com/not-twitch"
    jobs = app.state.store.list_jobs(limit=10)
    assert len(jobs) == 3
    assert all(job["batch_id"] == payload["batch_id"] for job in jobs)
    assert all(job["metadata"]["batch_import"] is True for job in jobs)
    assert all(job["metadata"]["batch_count"] == 3 for job in jobs)
    assert sorted(job["metadata"]["batch_index"] for job in jobs) == [1, 2, 3]
    assert all(job["metadata"]["options"]["layout"] == "blur" for job in jobs)
    assert all(job["metadata"]["options"]["dynamic_zoom"] is False for job in jobs)
    assert all(job["metadata"]["options"]["captions_enabled"] is False for job in jobs)

    queued_batch = client.get(f"/api/shorts/batches/{payload['batch_id']}")
    assert queued_batch.status_code == 200
    assert queued_batch.json()["status"] == "running"
    assert queued_batch.json()["progress"] == 0
    assert queued_batch.json()["active_count"] == 3

    app.state.store.update_job(
        payload["jobs"][0]["id"], status="ready", progress=100, message="Short prêt"
    )
    app.state.store.update_job(
        payload["jobs"][1]["id"], status="error", progress=0,
        message="Échec du téléchargement", error="Twitch indisponible",
    )
    app.state.store.update_job(
        payload["jobs"][2]["id"], status="cancelled", progress=20,
        message="Traitement annulé",
    )
    completed_batch = client.get(f"/api/shorts/batches/{payload['batch_id']}")
    assert completed_batch.status_code == 200
    summary = completed_batch.json()
    assert summary["status"] == "completed_with_errors"
    assert summary["progress"] == 100
    assert summary["completed_count"] == 3
    assert summary["ready_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["cancelled_count"] == 1
    assert {job["status"] for job in summary["jobs"]} == {"ready", "error", "cancelled"}
    failed_item = next(job for job in summary["jobs"] if job["status"] == "error")
    assert failed_item["retryable"] is True
    assert failed_item["attempts"] == 1

    # A retry is a new durable job, but it keeps the logical slot in the
    # original batch. Progress therefore remains based on three clips.
    retried = client.post(f"/api/jobs/{failed_item['id']}/reprocess")
    assert retried.status_code == 202, retried.text
    retry_id = retried.json()["id"]
    retry_job = app.state.store.get_job(retry_id)
    assert retry_job["batch_id"] == payload["batch_id"]
    assert retry_job["metadata"]["batch_index"] == 2
    assert retry_job["metadata"]["batch_count"] == 3
    assert retry_job["metadata"]["options"]["layout"] == "blur"

    stale_retry = client.post(f"/api/jobs/{failed_item['id']}/reprocess")
    assert stale_retry.status_code == 409
    assert "tentative plus récente" in stale_retry.json()["detail"]

    retrying_batch = client.get(f"/api/shorts/batches/{payload['batch_id']}").json()
    assert retrying_batch["total"] == 3
    assert retrying_batch["active_count"] == 1
    assert retrying_batch["completed_count"] == 2
    assert retrying_batch["failed_count"] == 0
    assert retrying_batch["progress"] == 67
    retry_item = next(job for job in retrying_batch["jobs"] if job["batch_index"] == 2)
    assert retry_item["id"] == retry_id
    assert retry_item["attempts"] == 2
    assert retry_item["status"] == "queued"
    assert retry_item["retryable"] is False

    app.state.store.update_job(retry_id, status="ready", progress=100, message="Short prêt après relance")
    finished_batch = client.get(f"/api/shorts/batches/{payload['batch_id']}").json()
    assert finished_batch["total"] == 3
    assert finished_batch["completed_count"] == 3
    assert finished_batch["ready_count"] == 2
    assert finished_batch["failed_count"] == 0
    assert finished_batch["progress"] == 100

    assert client.get("/api/shorts/batches/not-a-batch").status_code == 400
    assert client.get(f"/api/shorts/batches/{'0' * 32}").status_code == 404


def test_batch_twitch_short_import_requires_rights_and_limits_urls(tmp_path: Path):
    config = load_config(_make_isolated_app_config(tmp_path))
    app = create_app(config)
    app.state.runner.submit = lambda job_id: None
    client = TestClient(app)

    missing_rights = client.post(
        "/api/shorts/url/batch",
        data={"urls": "https://clips.twitch.tv/ClipOne", "rights_confirmed": "false"},
    )
    assert missing_rights.status_code == 400

    too_many = client.post(
        "/api/shorts/url/batch",
        data={
            "urls": "\n".join(f"https://clips.twitch.tv/Clip{i}" for i in range(11)),
            "rights_confirmed": "true",
        },
    )
    assert too_many.status_code == 400
    assert "Maximum 10" in too_many.json()["detail"]


def test_short_caption_option_requires_local_whisper_and_is_persisted(tmp_path: Path):
    config = load_config(_make_isolated_app_config(tmp_path))
    app = create_app(config)
    app.state.runner.submit = lambda job_id: None
    client = TestClient(app)

    payload = {
        "url": "https://clips.twitch.tv/CaptionTestClip",
        "rights_confirmed": "true",
        "captions_enabled": "true",
        "caption_language": "fr",
    }
    unavailable = client.post("/api/shorts/url", data=payload)
    assert unavailable.status_code == 409
    assert "whisper.cpp" in unavailable.json()["detail"]
    assert app.state.store.list_jobs(limit=10) == []

    whisper_cli = config.path_for("executables", "whisper_cli")
    whisper_cli.parent.mkdir(parents=True, exist_ok=True)
    whisper_cli.write_bytes(b"fake whisper binary")
    missing_model = client.post("/api/shorts/url", data=payload)
    assert missing_model.status_code == 409
    assert "large-v3-turbo" in missing_model.json()["detail"]
    app.state.model_manager._model_is_valid = lambda: True

    accepted = client.post("/api/shorts/url", data=payload)
    assert accepted.status_code == 202, accepted.text
    job = app.state.store.get_job(accepted.json()["id"])
    assert job["metadata"]["options"]["captions_enabled"] is True
    assert job["metadata"]["options"]["caption_language"] == "fr"

    invalid_language = client.post(
        "/api/shorts/url",
        data={**payload, "captions_enabled": "false", "caption_language": "xx"},
    )
    assert invalid_language.status_code == 400
    assert "langue" in invalid_language.json()["detail"].lower()

    configured_default = client.post(
        "/api/shorts/url",
        data={key: value for key, value in payload.items() if key != "caption_language"},
    )
    assert configured_default.status_code == 202, configured_default.text
    default_job = app.state.store.get_job(configured_default.json()["id"])
    assert default_job["metadata"]["options"]["caption_language"] == "config"

    upload = client.post(
        "/api/shorts/upload",
        files={"file": ("caption-upload.mp4", b"video", "video/mp4")},
        data={"rights_confirmed": "true", "captions_enabled": "true", "caption_language": "es"},
    )
    assert upload.status_code == 202, upload.text
    uploaded_job = app.state.store.get_job(upload.json()["id"])
    assert uploaded_job["metadata"]["options"]["captions_enabled"] is True
    assert uploaded_job["metadata"]["options"]["caption_language"] == "es"
    assert uploaded_job["metadata"]["options"]["dynamic_zoom"] is False

    batch_payload = {
        "urls": "https://clips.twitch.tv/CaptionBatchOne\nhttps://clips.twitch.tv/CaptionBatchTwo",
        "rights_confirmed": "true",
        "captions_enabled": "true",
        "caption_language": "auto",
    }
    batch = client.post("/api/shorts/url/batch", data=batch_payload)
    assert batch.status_code == 202, batch.text
    batch_jobs = [app.state.store.get_job(item["id"]) for item in batch.json()["jobs"]]
    assert len(batch_jobs) == 2
    assert all(item["metadata"]["options"]["captions_enabled"] is True for item in batch_jobs)
    assert all(item["metadata"]["options"]["caption_language"] == "auto" for item in batch_jobs)


def test_batch_twitch_import_is_available_in_shorts_ui():
    static = Path(__file__).resolve().parents[1] / "studio" / "web" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.js").read_text(encoding="utf-8")

    assert 'id="short-batch-urls"' in html
    assert 'id="short-batch-submit"' in html
    assert 'id="short-batch-tracker"' in html
    assert "v=0.9.4-main-voice-captions" in html
    assert "JUSQU'À 10 URLS" in html
    assert "/api/shorts/url/batch" in js
    assert "/api/shorts/batches/" in js
    assert "data-retry-short-batch" in js
    assert "/api/jobs/${encodeURIComponent(jobId)}/reprocess" in js
    assert "gta-ranked-short-batches" in js
    assert html.count('name="captions_enabled"') == 2
    assert html.count('name="caption_language"') == 2
    assert "Réglage du Studio" in html
    assert "Détection automatique" in html
    assert "Modèle multilingue local" in html
    assert "large-v3-turbo" in html
    assert "metadata.transcription_warning" in js
    assert "Transcription Whisper" in js
    assert "$('[data-option-checkbox]', form).forEach" in js
    assert "submitShortBatch($('#url-form'))" in js


def test_store_adds_batch_id_to_existing_database_without_losing_jobs(tmp_path: Path):
    import sqlite3

    database = tmp_path / "legacy.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, created_at TEXT NOT NULL, source_hash TEXT, metadata_json TEXT NOT NULL DEFAULT '{}')"
        )
        connection.execute(
            "INSERT INTO jobs (id, status, created_at) VALUES ('existing-job', 'ready', '2026-11-27T12:00:00')"
        )

    migrated = Store(database)
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
    assert "batch_id" in columns
    assert migrated.get_job("existing-job")["status"] == "ready"


def test_cancelled_twitch_short_can_be_reprocessed(tmp_path: Path):
    config = load_config(_make_isolated_app_config(tmp_path))
    app = create_app(config)
    submitted: list[str] = []
    app.state.runner.submit = lambda job_id: submitted.append(job_id)
    client = TestClient(app)

    created = client.post(
        "/api/shorts/url",
        data={"url": "https://clips.twitch.tv/CancelledClip", "rights_confirmed": "true"},
    )
    assert created.status_code == 202
    original_id = created.json()["id"]
    app.state.store.update_job(original_id, status="cancelled", message="Traitement annulé")
    submitted.clear()

    retried = client.post(f"/api/jobs/{original_id}/reprocess")
    assert retried.status_code == 202, retried.text
    new_job = app.state.store.get_job(retried.json()["id"])
    assert new_job["status"] == "queued"
    assert new_job["source_url"] == "https://clips.twitch.tv/CancelledClip"
    assert submitted == [new_job["id"]]


def test_reprocess_preserves_twitch_url_when_reusing_local_download(tmp_path: Path):
    config = load_config(_make_isolated_app_config(tmp_path))
    app = create_app(config)
    submitted: list[str] = []
    app.state.runner.submit = lambda job_id: submitted.append(job_id)
    client = TestClient(app)

    source = tmp_path / "downloaded-twitch.mp4"
    source.write_bytes(b"local Twitch media")
    app.state.store.create_job({
        "id": "local-twitch-source",
        "source_kind": "url",
        "source_url": "https://clips.twitch.tv/OriginalClip",
        "source_path": str(source),
        "streamer": "ExampleStreamer",
        "rights_confirmed": True,
    })
    app.state.store.update_job("local-twitch-source", status="error", error="Render failed")
    submitted.clear()

    first_retry = client.post("/api/jobs/local-twitch-source/reprocess")
    assert first_retry.status_code == 202, first_retry.text
    first_job = app.state.store.get_job(first_retry.json()["id"])
    assert first_job["source_kind"] == "upload"
    assert first_job["source_path"] == str(source.resolve())
    assert first_job["source_url"] == "https://clips.twitch.tv/OriginalClip"

    source.unlink()
    app.state.store.update_job(first_job["id"], status="error", error="Local media missing")
    second_retry = client.post(f"/api/jobs/{first_job['id']}/reprocess")
    assert second_retry.status_code == 202, second_retry.text
    second_job = app.state.store.get_job(second_retry.json()["id"])
    assert second_job["source_kind"] == "url"
    assert second_job["source_url"] == "https://clips.twitch.tv/OriginalClip"
    assert submitted == [first_job["id"], second_job["id"]]


def test_short_audio_analysis_is_skipped_when_no_feature_needs_it():
    from studio.web.worker import _needs_audio_analysis

    assert _needs_audio_analysis(True, 30, dynamic_zoom=False, auto_trim=True) is False
    assert _needs_audio_analysis(True, 90, dynamic_zoom=False, auto_trim=True) is True
    assert _needs_audio_analysis(True, 30, dynamic_zoom=True, auto_trim=False) is True
    assert _needs_audio_analysis(False, 90, dynamic_zoom=True, auto_trim=True) is False


def test_short_ui_explains_full_frame_twitch_composition() -> None:
    html = Path("studio/web/static/index.html").read_text(encoding="utf-8-sig")
    assert "Utilisé uniquement en mode plein écran recadré." in html
    assert "La capture complète reste visible, sans cadre ni bande qui coupe l’image." in html
    assert 'option value="blur" selected' in html
    assert 'option value="smart"' not in html


def test_daily_best_of_rejects_parallel_active_render_but_allows_a_new_one_after_failure(
    tmp_path: Path, monkeypatch,
):
    from types import SimpleNamespace

    import studio.web.app as app_module

    config = load_config(_make_isolated_app_config(tmp_path))
    app = create_app(config)
    client = TestClient(app)
    clip_ids = ["parallel-a", "parallel-b", "parallel-c", "parallel-d"]
    for clip_id in clip_ids:
        output = tmp_path / f"{clip_id}.mp4"
        output.write_bytes(b"rendered short")
        with app.state.store._connect() as connection:
            connection.execute(
                """INSERT INTO jobs (id, status, source_kind, created_at, updated_at)
                   VALUES (?, 'validated', 'upload', ?, ?)""",
                (clip_id, "2026-11-28T12:00:00", "2026-11-28T12:00:00"),
            )
            connection.execute(
                """INSERT INTO clips (id, job_id, date_key, duration, output_path, status, created_at)
                   VALUES (?, ?, '2026-11-28', 140, ?, 'validated', ?)""",
                (clip_id, clip_id, str(output), "2026-11-28T12:00:00"),
            )

    class DeferredThread:
        def __init__(self, *, target, name, daemon):
            self.target = target

        def start(self):
            return None

    monkeypatch.setattr(app_module, "threading", SimpleNamespace(Thread=DeferredThread))
    payload = {"clip_ids": clip_ids, "date_key": "2026-11-28"}

    first = client.post("/api/bestof/render", json=payload)
    assert first.status_code == 202, first.text
    first_id = first.json()["id"]
    assert app.state.store.get_active_best_of_job()["id"] == first_id

    duplicate = client.post("/api/bestof/render", json=payload)
    assert duplicate.status_code == 409
    assert "déjà en cours" in duplicate.json()["detail"]
    assert len(app.state.store.list_best_of_jobs(10)) == 1

    app.state.store.update_best_of_job(
        first_id, status="error", progress=100, message="Rendu interrompu",
    )
    next_render = client.post("/api/bestof/render", json=payload)
    assert next_render.status_code == 202, next_render.text
    assert next_render.json()["id"] != first_id
    assert app.state.store.get_active_best_of_job()["id"] == next_render.json()["id"]

def test_hook_sound_effect_filter_graph_executes_with_real_ffmpeg(tmp_path: Path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg is required for the audio filtergraph integration test")

    source = tmp_path / "source.mp4"
    sound_effect = tmp_path / "whoosh.wav"
    output = tmp_path / "short.mp4"

    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=1",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=1",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(source),
        ],
        check=True,
        capture_output=True,
        timeout=90,
    )
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100:duration=0.25",
            "-c:a", "pcm_s16le", str(sound_effect),
        ],
        check=True,
        capture_output=True,
        timeout=90,
    )

    command = build_render_command(
        ffmpeg,
        source,
        output,
        width=180,
        height=320,
        source_width=320,
        source_height=240,
        encoder="libx264",
        has_audio=True,
        layout="blur",
        duration=1.0,
        sound_effect_path=sound_effect,
        sound_effect_offset=0.12,
    )
    subprocess.run(command, check=True, capture_output=True, timeout=120)

    assert output.is_file()
    assert output.stat().st_size > 0
