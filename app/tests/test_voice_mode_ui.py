from pathlib import Path


def test_short_creation_ui_keeps_subtitles_paused() -> None:
    html = Path("studio/web/static/index.html").read_text(encoding="utf-8-sig")
    script = Path("studio/web/static/app.js").read_text(encoding="utf-8")
    assert 'name="captions_enabled"' not in html
    assert 'name="caption_voice_mode"' not in html
    assert "Sous-titres anglais" not in html
    assert "speakerFilterStatus" not in script
    assert "subtitleState" not in script
    api = Path("studio/web/app.py").read_text(encoding="utf-8")
    renderer = Path("studio/web/short_renderer.py").read_text(encoding="utf-8")
    assert "webcam_zone" not in api
    assert "webcam_zone" not in renderer
