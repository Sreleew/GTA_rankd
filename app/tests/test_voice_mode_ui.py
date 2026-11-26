from pathlib import Path


def test_voice_mode_select_is_separated_by_real_html_whitespace() -> None:
    html = Path("studio/web/static/index.html").read_text(encoding="utf-8-sig")
    assert "\\n                  <label>Voix à sous-titrer" not in html
    assert "\n                  <label>Voix à sous-titrer" in html
    assert html.count('name="caption_voice_mode"') == 2
