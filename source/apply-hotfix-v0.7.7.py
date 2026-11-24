from __future__ import annotations

import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Patch v0.7.7 impossible : {count} occurrence(s) de {label} dans {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_before(path: Path, marker: str, addition: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if addition.strip() in text:
        return
    if text.count(marker) != 1:
        raise SystemExit(f"Patch v0.7.7 impossible : ancre {label} absente ou ambigue dans {path}")
    path.write_text(text.replace(marker, addition.rstrip() + "\n\n" + marker, 1), encoding="utf-8")


def patch_ui(root: Path) -> None:
    html = root / "studio/web/static/index.html"
    replace_once(
        html,
        '<script src="/static/app.js?v=0.7.6"></script>',
        '<script src="/static/app.js?v=0.7.7"></script>',
        "cache-busting app.js",
    )

    js = root / "studio/web/static/app.js"
    old_render = """    const ollamaLine = $('#ollama-model-status');
    const ollamaDetails = $('#ollama-model-details');
    const ollamaButton = $('#verify-ollama');
    if (state.ollamaVerifyRunning) {
      ollamaLine.textContent = 'Vérification Ollama et test Qwen en cours...';
      ollamaDetails.textContent = 'Connexion au serveur local puis courte génération avec le modèle. Le premier test peut prendre jusqu’à 75 secondes.';
      ollamaButton.disabled = true;
      ollamaButton.textContent = 'Test Qwen en cours...';
    } else if (state.ollamaVerificationResult) {
      const result = state.ollamaVerificationResult;
      ollamaLine.textContent = result.verified ? `Opérationnel · ${result.model} répond localement.` : 'Vérification Ollama échouée';
      ollamaDetails.textContent = result.message;
      ollamaButton.disabled = false;
      ollamaButton.textContent = 'Re-vérifier';
    } else {
      if (!data.ollama_running) ollamaLine.textContent = 'Ollama non détecté ou arrêté. Installe-le puis démarre-le pour activer la génération IA.';
      else if (!data.ollama_model_installed) ollamaLine.textContent = `Ollama fonctionne, mais le modèle ${data.ollama_model} n'est pas installé.`;
      else ollamaLine.textContent = `Opérationnel · ${data.ollama_model} disponible localement.`;
      ollamaDetails.textContent = 'Le bouton Vérifier lance un vrai test local du modèle Qwen.';
      ollamaButton.disabled = false;
      ollamaButton.textContent = 'Vérifier';
    }
"""
    new_render = """    const ollamaLine = $('#ollama-model-status');
    // Accepte aussi l'ancien HTML encore susceptible d'être servi par une page en cache.
    const ollamaDetails = $('#ollama-model-details') || ollamaLine?.parentElement?.querySelector('small');
    const ollamaButton = $('#verify-ollama') || $('#refresh-models-secondary');
    if (ollamaLine) {
      if (state.ollamaVerifyRunning) {
        ollamaLine.textContent = 'Vérification Ollama et test Qwen en cours...';
        if (ollamaDetails) ollamaDetails.textContent = 'Connexion au serveur local puis courte génération avec le modèle. Le premier test peut prendre jusqu’à 75 secondes.';
        if (ollamaButton) {
          ollamaButton.disabled = true;
          ollamaButton.textContent = 'Test Qwen en cours...';
        }
      } else if (state.ollamaVerificationResult) {
        const result = state.ollamaVerificationResult;
        ollamaLine.textContent = result.verified ? `Opérationnel · ${result.model} répond localement.` : 'Vérification Ollama échouée';
        if (ollamaDetails) ollamaDetails.textContent = result.message;
        if (ollamaButton) {
          ollamaButton.disabled = false;
          ollamaButton.textContent = result.verified ? 'Re-vérifier' : 'Vérifier';
        }
      } else {
        if (!data.ollama_running) ollamaLine.textContent = 'Ollama non détecté ou arrêté. Installe-le puis démarre-le pour activer la génération IA.';
        else if (!data.ollama_model_installed) ollamaLine.textContent = `Ollama fonctionne, mais le modèle ${data.ollama_model} n'est pas installé.`;
        else ollamaLine.textContent = `Opérationnel · ${data.ollama_model} disponible localement.`;
        if (ollamaDetails) ollamaDetails.textContent = 'Le bouton Vérifier lance un vrai test local du modèle Qwen.';
        if (ollamaButton) {
          ollamaButton.disabled = false;
          ollamaButton.textContent = 'Vérifier';
        }
      }
    }
"""
    replace_once(js, old_render, new_render, "rendu Ollama compatible ancien/nouveau HTML")

    old_handler = """async function verifyOllamaModel() {
  const button = $('#verify-ollama');
  if (state.ollamaVerifyRunning) return;
  state.ollamaVerifyRunning = true;
  state.ollamaVerificationResult = null;
  button.disabled = true;
  button.textContent = 'Test Qwen en cours...';
  $('#ollama-model-status').textContent = 'Vérification Ollama et test Qwen en cours...';
  $('#ollama-model-details').textContent = 'Connexion au serveur local puis courte génération avec le modèle. Le premier test peut prendre jusqu’à 75 secondes.';
  try {
    const result = await api('/api/models/ollama/verify', { method: 'POST' });
    state.ollamaVerificationResult = { ...result, verified: true };
    toast(`Ollama et ${result.model} sont opérationnels (${result.elapsed_seconds} s).`);
  } catch (error) {
    state.ollamaVerificationResult = { verified: false, message: error.message };
    toast(error.message, true);
  } finally {
    state.ollamaVerifyRunning = false;
    button.disabled = false;
    button.textContent = state.ollamaVerificationResult?.verified ? 'Re-vérifier' : 'Vérifier';
    await loadModels(true);
  }
}
"""
    new_handler = """async function verifyOllamaModel(triggerButton = null) {
  const button = triggerButton || $('#verify-ollama') || $('#refresh-models-secondary');
  const ollamaLine = $('#ollama-model-status');
  const ollamaDetails = $('#ollama-model-details') || ollamaLine?.parentElement?.querySelector('small');
  if (state.ollamaVerifyRunning) return;
  if (!button || !ollamaLine) {
    toast('Le bouton de vérification Ollama est introuvable dans cette page. Recharge GTA Ranked Studio avec Ctrl+F5.', true);
    return;
  }
  state.ollamaVerifyRunning = true;
  state.ollamaVerificationResult = null;
  button.disabled = true;
  button.textContent = 'Test Qwen en cours...';
  ollamaLine.textContent = 'Vérification Ollama et test Qwen en cours...';
  if (ollamaDetails) ollamaDetails.textContent = 'Connexion au serveur local puis courte génération avec le modèle. Le premier test peut prendre jusqu’à 75 secondes.';
  try {
    const result = await api('/api/models/ollama/verify', { method: 'POST' });
    state.ollamaVerificationResult = { ...result, verified: true };
    toast(`Ollama et ${result.model} sont opérationnels (${result.elapsed_seconds} s).`);
  } catch (error) {
    state.ollamaVerificationResult = { verified: false, message: error.message };
    ollamaLine.textContent = 'Vérification Ollama échouée';
    if (ollamaDetails) ollamaDetails.textContent = error.message;
    toast(error.message, true);
  } finally {
    state.ollamaVerifyRunning = false;
    button.disabled = false;
    button.textContent = state.ollamaVerificationResult?.verified ? 'Re-vérifier' : 'Vérifier';
    await loadModels(true);
  }
}
"""
    replace_once(js, old_handler, new_handler, "handler Ollama avec bouton explicite")

    # Remove the direct event binding and use capture-phase delegation instead.
    replace_once(
        js,
        "  const verifyOllamaButton = $('#verify-ollama');\n  if (verifyOllamaButton) verifyOllamaButton.addEventListener('click', verifyOllamaModel);\n",
        "",
        "ancienne liaison directe du bouton Ollama",
    )
    delegated = """document.addEventListener('click', event => {
  const ollamaButton = event.target.closest('#verify-ollama, #refresh-models-secondary');
  if (!ollamaButton) return;
  event.preventDefault();
  verifyOllamaModel(ollamaButton);
}, true);

"""
    insert_before(js, "setupEvents();\n", delegated, "délégation globale clic Ollama")


def patch_app(root: Path) -> None:
    path = root / "studio/web/app.py"
    old = """    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")
"""
    new = """    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        # Force le navigateur à revalider le HTML afin qu'un ancien identifiant
        # de bouton ou une ancienne URL app.js ne reste pas bloqué dans le cache.
        return FileResponse(
            static_dir / "index.html",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
"""
    replace_once(path, old, new, "no-cache HTML page")


def patch_tests(root: Path) -> None:
    tests = root / "tests/test_web.py"
    old_version_assert = "assert '<script src=\"/static/app.js?v=0.7.6\"></script>' in html"
    new_version_assert = "assert '<script src=\"/static/app.js?v=0.7.7\"></script>' in html"
    test_text = tests.read_text(encoding="utf-8-sig")
    if old_version_assert not in test_text and new_version_assert not in test_text:
        raise SystemExit("Patch v0.7.7 impossible : assertion de version JavaScript absente")
    test_text = test_text.replace(old_version_assert, new_version_assert)
    tests.write_text(test_text, encoding="utf-8")
    replace_once(
        tests,
        "    assert \"verifyOllamaButton.addEventListener('click', verifyOllamaModel)\" in js\n",
        "    assert \"event.target.closest('#verify-ollama, #refresh-models-secondary')\" in js\n    assert \"verifyOllamaModel(ollamaButton)\" in js\n    assert \"document.addEventListener('click'\" in js\n",
        "assertion wiring delegated UI",
    )
    replace_once(
        tests,
        "    assert '<button type=\"button\" class=\"mini-button\" id=\"verify-ollama\"' in html\n",
        "    assert '<button type=\"button\" class=\"mini-button\" id=\"verify-ollama\"' in html\n    assert \"#refresh-models-secondary\" in js\n",
        "legacy selector is handled",
    )
    test = r'''def test_root_page_disables_stale_html_cache():
    from studio.web.app import create_app
    from studio.config import load_config
    from fastapi.testclient import TestClient

    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    client = TestClient(create_app(load_config(config_path)))
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"


'''
    insert_before(tests, "def test_clip_enters_library_only_after_atomic_validation(", test, "test cache control index")


def patch_release(root: Path) -> None:
    for relative, old, new in (
        ("VERSION.txt", "Version: 0.7.6", "Version: 0.7.7"),
        ("pyproject.toml", 'version = "0.7.6"', 'version = "0.7.7"'),
        ("config.yaml.default", "version: 0.7.6", "version: 0.7.7"),
    ):
        replace_once(root / relative, old, new, f"version {relative}")
    (root / "NOTES-v0.7.7.txt").write_text(
        """GTA Ranked Studio v0.7.7

Correction du bouton de vérification Ollama :
- Remplace la liaison directe du bouton par une délégation de clic au niveau du document, en phase capture.
- Accepte les deux identifiants de bouton (`verify-ollama` et l'ancien `refresh-models-secondary`) pour résister à une page HTML ancienne.
- Le handler reçoit le bouton effectivement cliqué, affiche immédiatement la progression et restitue les erreurs dans la ligne Ollama.
- Le rendu de la ligne Ollama tolère l'absence de l'ancien identifiant de détails et ne bloque plus le reste de la page.
- La page d'accueil envoie désormais des en-têtes no-cache/no-store afin de forcer le navigateur à revalider le HTML.
- Le fichier JavaScript est chargé avec un identifiant d'asset v0.7.7.
- Le test garde le même appel local à Ollama et Qwen, sans modification du modèle ni des moteurs.
""",
        encoding="utf-8",
    )


def apply(root: Path) -> None:
    root = root.resolve()
    patch_ui(root)
    patch_app(root)
    patch_tests(root)
    patch_release(root)
    for relative in ("studio/web/app.py", "studio/web/static/app.js", "tests/test_web.py"):
        source = (root / relative).read_text(encoding="utf-8")
        if relative.endswith(".py"):
            compile(source, str(root / relative), "exec")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.7.7.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))