from pathlib import Path


def test_voice_mode_select_is_separated_by_real_html_whitespace() -> None:
    html = Path("studio/web/static/index.html").read_text(encoding="utf-8-sig")
    assert "\\n                  <label>Voix à sous-titrer" not in html
    assert "\n                  <label>Voix à sous-titrer" in html
    assert html.count('name="caption_voice_mode"') == 2


def test_voice_filter_result_is_explained_in_short_job_cards() -> None:
    script = Path("studio/web/static/app.js").read_text(encoding="utf-8")
    assert "Voix principale isolée" in script
    assert "Une seule voix détectée" in script
    assert "Toutes les voix sous-titrées" in script
    assert "Sous-titres omis : voix non isolée" in script
