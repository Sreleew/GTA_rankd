from pathlib import Path

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
    options = _validate_edit_options("fill", 50, 40, True, 8, True, True, "Wait for it", "A chase", True)
    assert options["layout"] == "fill"
    assert options["crop_x"] == 50
    assert options["dynamic_zoom"] is True
    assert options["auto_trim_enabled"] is True
    smart = _validate_edit_options("smart", 80, 50, False, 0, True, True, "", "")
    assert smart["layout"] == "smart"
    assert smart["crop_x"] == 80
    try:
        _validate_edit_options("invalid", 50, 50, True, 8, True, True, "", "")
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
    assert '<script src="/static/app.js?v=0.8.4"></script>' in html
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
    assert '<script src="/static/app.js?v=0.8.4"></script>' in html
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
            progress_hook({"status": "downloading", "downloaded_bytes": 25, "total_bytes": 100})
            progress_hook({"status": "downloading", "downloaded_bytes": 75, "total_bytes_estimate": 100})
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
    assert "75 %" in messages[1]
    assert messages[-1] == "Téléchargement terminé · préparation du Short"
    assert all(job_id == "test-job" for job_id, _ in store.updates)


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
