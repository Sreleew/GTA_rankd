from __future__ import annotations

import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Patch v0.7.6 impossible : {count} occurrence(s) de {label} dans {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_before(path: Path, marker: str, addition: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if addition.strip() in text:
        return
    if text.count(marker) != 1:
        raise SystemExit(f"Patch v0.7.6 impossible : ancre {label} absente ou ambigue dans {path}")
    path.write_text(text.replace(marker, addition.rstrip() + "\n\n" + marker, 1), encoding="utf-8")


def patch_app(root: Path) -> None:
    path = root / "studio/web/app.py"
    replace_once(
        path,
        '    whisper_gpu_probe_lock = threading.Lock()\n',
        '    whisper_gpu_probe_lock = threading.Lock()\n    ollama_verify_lock = threading.Lock()\n',
        "verrou de vérification Ollama",
    )

    route = r'''    @app.post("/api/models/ollama/verify")
    def verify_ollama_model() -> dict:
        """Teste le serveur Ollama puis exécute une inférence Qwen courte en local."""
        if not ollama_verify_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Une vérification Ollama est déjà en cours.")
        started_at = time.monotonic()
        base_url = str(config.get("ollama", "base_url", default="http://127.0.0.1:11434")).rstrip("/")
        model_name = str(config.get("ollama", "model", default="qwen2.5:7b-instruct"))
        try:
            try:
                with urllib.request.urlopen(base_url + "/api/tags", timeout=5) as response:
                    tags_payload = json.loads(response.read().decode("utf-8", errors="replace"))
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Ollama ne répond pas sur {base_url}. Vérifie que l'application Ollama est démarrée. Détail : {exc}",
                ) from exc

            models = tags_payload.get("models", []) if isinstance(tags_payload, dict) else []
            installed_names = [str(item.get("name") or item.get("model") or "") for item in models if isinstance(item, dict)]
            model_installed = any(name == model_name or name.startswith(model_name + ":") for name in installed_names)
            if not model_installed:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ollama fonctionne, mais le modèle {model_name} n'est pas installé. Dans PowerShell, exécute : ollama pull {model_name}",
                )

            request_payload = {
                "model": model_name,
                "prompt": "Reply with exactly the single word OK. Do not add punctuation or anything else.",
                "stream": False,
                "keep_alive": "5m",
                "options": {"temperature": 0, "num_predict": 8, "num_ctx": 512},
            }
            request = urllib.request.Request(
                base_url + "/api/generate",
                data=json.dumps(request_payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            timeout_seconds = int(config.get("ollama", "verify_timeout_seconds", default=75))
            timeout_seconds = max(20, min(timeout_seconds, 120))
            try:
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    generation_payload = json.loads(response.read().decode("utf-8", errors="replace"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[-700:]
                raise HTTPException(status_code=502, detail=f"Ollama a refusé le test d'inférence ({exc.code}) : {detail or exc.reason}") from exc
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                raise HTTPException(
                    status_code=504,
                    detail=f"Ollama est joignable et Qwen est installé, mais le test d'inférence a échoué ou dépassé le délai de {timeout_seconds} s : {exc}",
                ) from exc

            if isinstance(generation_payload, dict) and generation_payload.get("error"):
                raise HTTPException(status_code=502, detail=f"Ollama n'a pas pu exécuter {model_name} : {generation_payload['error']}")
            generated_text = str(generation_payload.get("response", "") if isinstance(generation_payload, dict) else "").strip()
            if not generated_text:
                raise HTTPException(status_code=502, detail=f"Ollama a répondu, mais {model_name} n'a renvoyé aucun texte lors du test.")

            elapsed = round(time.monotonic() - started_at, 2)
            return {
                "verified": True,
                "ollama_running": True,
                "model_installed": True,
                "model": model_name,
                "elapsed_seconds": elapsed,
                "message": f"Ollama répond et {model_name} a réussi une inférence locale en {elapsed:.1f} s.",
            }
        finally:
            ollama_verify_lock.release()

'''
    insert_before(path, '    @app.post("/api/models/whisper/verify")\n', route, "route de test Ollama")


def patch_ui(root: Path) -> None:
    html = root / "studio/web/static/index.html"
    replace_once(
        html,
        '<div class="model-row"><div><strong>Ollama · Qwen 2.5 7B</strong><p id="ollama-model-status">Vérification d\'Ollama...</p><small>Génération locale des hooks, titres, descriptions et hashtags.</small></div><div class="model-actions"><a class="mini-button" href="https://ollama.com/download/windows" target="_blank" rel="noopener">Installer Ollama ↗</a><button class="mini-button" id="refresh-models-secondary">Vérifier</button></div></div>',
        '<div class="model-row"><div><strong>Ollama · Qwen 2.5 7B</strong><p id="ollama-model-status">Vérification d\'Ollama...</p><small id="ollama-model-details">Génération locale des hooks, titres, descriptions et hashtags.</small></div><div class="model-actions"><a class="mini-button" href="https://ollama.com/download/windows" target="_blank" rel="noopener">Installer Ollama ↗</a><button type="button" class="mini-button" id="verify-ollama" aria-describedby="ollama-model-details">Vérifier</button></div></div>',
        "bouton Ollama et détail de diagnostic",
    )
    replace_once(
        html,
        '<script src="/static/app.js?v=0.7.5"></script>',
        '<script src="/static/app.js?v=0.7.6"></script>',
        "cache-busting app.js",
    )

    js = root / "studio/web/static/app.js"
    replace_once(
        js,
        "const state = { page: 'dashboard', file: null, toastTimer: null, modelPoll: null, whisperGpuProbeRunning: false, updatePoll: null };",
        "const state = { page: 'dashboard', file: null, toastTimer: null, modelPoll: null, whisperGpuProbeRunning: false, ollamaVerifyRunning: false, ollamaVerificationResult: null, updatePoll: null };",
        "état de vérification Ollama",
    )
    replace_once(
        js,
        "    const ollamaLine = $('#ollama-model-status');\n    if (!data.ollama_running) ollamaLine.textContent = 'Ollama non détecté ou arrêté. Installe-le puis démarre-le pour activer la génération IA.';\n    else if (!data.ollama_model_installed) ollamaLine.textContent = `Ollama fonctionne, mais le modèle ${data.ollama_model} n'est pas installé.`;\n    else ollamaLine.textContent = `Opérationnel · ${data.ollama_model} disponible localement.`;\n",
        "    const ollamaLine = $('#ollama-model-status');\n    const ollamaDetails = $('#ollama-model-details');\n    const ollamaButton = $('#verify-ollama');\n    if (state.ollamaVerifyRunning) {\n      ollamaLine.textContent = 'Vérification Ollama et test Qwen en cours...';\n      ollamaDetails.textContent = 'Connexion au serveur local puis courte génération avec le modèle. Le premier test peut prendre jusqu’à 75 secondes.';\n      ollamaButton.disabled = true;\n      ollamaButton.textContent = 'Test Qwen en cours...';\n    } else if (state.ollamaVerificationResult) {\n      const result = state.ollamaVerificationResult;\n      ollamaLine.textContent = result.verified ? `Opérationnel · ${result.model} répond localement.` : 'Vérification Ollama échouée';\n      ollamaDetails.textContent = result.message;\n      ollamaButton.disabled = false;\n      ollamaButton.textContent = 'Re-vérifier';\n    } else {\n      if (!data.ollama_running) ollamaLine.textContent = 'Ollama non détecté ou arrêté. Installe-le puis démarre-le pour activer la génération IA.';\n      else if (!data.ollama_model_installed) ollamaLine.textContent = `Ollama fonctionne, mais le modèle ${data.ollama_model} n'est pas installé.`;\n      else ollamaLine.textContent = `Opérationnel · ${data.ollama_model} disponible localement.`;\n      ollamaDetails.textContent = 'Le bouton Vérifier lance un vrai test local du modèle Qwen.';\n      ollamaButton.disabled = false;\n      ollamaButton.textContent = 'Vérifier';\n    }\n",
        "rendu état Ollama visible",
    )
    handler = r'''async function verifyOllamaModel() {
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

'''
    insert_before(js, "async function loadUpdates() {\n", handler, "handler de vérification Ollama")
    replace_once(
        js,
        "  $('#refresh-models-secondary').addEventListener('click', () => loadModels(true));\n",
        "  const verifyOllamaButton = $('#verify-ollama');\n  if (verifyOllamaButton) verifyOllamaButton.addEventListener('click', verifyOllamaModel);\n",
        "liaison bouton Ollama",
    )


def patch_tests(root: Path) -> None:
    tests = root / "tests/test_web.py"
    replace_once(
        tests,
        "assert '<script src=\"/static/app.js?v=0.7.5\"></script>' in html",
        "assert '<script src=\"/static/app.js?v=0.7.6\"></script>' in html",
        "version cache test interface GPU",
    )
    api_test = r'''def test_ollama_verify_endpoint_checks_model_and_runs_local_inference(tmp_path: Path, monkeypatch):
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
    assert '<script src="/static/app.js?v=0.7.6"></script>' in html
    assert '<button type="button" class="mini-button" id="verify-ollama"' in html
    assert "/api/models/ollama/verify" in js
    assert "verifyOllamaButton.addEventListener('click', verifyOllamaModel)" in js
    assert "Test Qwen en cours..." in js
    assert "state.ollamaVerificationResult" in js


'''
    insert_before(tests, "def test_clip_enters_library_only_after_atomic_validation(", api_test, "tests endpoint et bouton Ollama")


def patch_release(root: Path) -> None:
    for relative, old, new in (
        ("VERSION.txt", "Version: 0.7.5", "Version: 0.7.6"),
        ("pyproject.toml", 'version = "0.7.5"', 'version = "0.7.6"'),
        ("config.yaml.default", "version: 0.7.5", "version: 0.7.6"),
    ):
        replace_once(root / relative, old, new, f"version {relative}")
    (root / "NOTES-v0.7.6.txt").write_text(
        """GTA Ranked Studio v0.7.6

Vérification Ollama et Qwen :
- Remplace le rafraîchissement silencieux du bouton « Vérifier » par un contrôle dédié.
- Vérifie que le serveur Ollama local répond sur /api/tags et que le modèle Qwen configuré est installé.
- Exécute une courte inférence locale non streamée via /api/generate (8 tokens maximum) avec keep_alive de 5 minutes.
- Affiche l'état de progression, le résultat et les erreurs dans la ligne Ollama, sans les envoyer dans la ligne Whisper.
- Le test est explicite et ne s'exécute pas lors des rafraîchissements périodiques.
""",
        encoding="utf-8",
    )


def apply(root: Path) -> None:
    patch_app(root)
    patch_ui(root)
    patch_tests(root)
    patch_release(root)
    for relative in ("studio/web/app.py", "tests/test_web.py"):
        source = (root / relative).read_text(encoding="utf-8")
        compile(source, str(root / relative), "exec")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-hotfix-v0.7.6.py <gta-ranked-studio-source-root>")
    apply(Path(sys.argv[1]))
    apply(Path(sys.argv[1]))