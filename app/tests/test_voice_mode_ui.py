from pathlib import Path


def test_short_creation_keeps_local_whisper_captions_opt_in() -> None:
    html = Path("studio/web/static/index.html").read_text(encoding="utf-8-sig")
    script = Path("studio/web/static/app.js").read_text(encoding="utf-8")
    api = Path("studio/web/app.py").read_text(encoding="utf-8")
    worker = Path("studio/web/worker.py").read_text(encoding="utf-8")
    renderer = Path("studio/web/short_renderer.py").read_text(encoding="utf-8")

    assert html.count('name="captions_enabled"') == 2
    assert 'name="captions_enabled" data-option-checkbox' in html
    assert "large-v3-turbo" in html
    assert 'name="caption_voice_mode"' not in html
    assert "Sous-titres anglais" not in html
    assert "speakerFilterStatus" in script
    assert "voiceFilterOmitted" in script
    assert "Filtrage vocal local en bêta" in html
    assert "diarize_and_filter" in worker
    assert "subtitleState" not in script
    assert "captions_enabled: Annotated[bool, Form()] = False" in api
    assert "transcribe_with_whisper_cpp" in worker
    assert "webcam_zone" not in api
    assert "webcam_zone" not in renderer
