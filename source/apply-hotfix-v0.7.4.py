from __future__ import annotations
import sys
from pathlib import Path

def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8-sig')
    if new in text:
        return
    if text.count(old) != 1:
        raise SystemExit(f'Patch v0.7.4 impossible : {text.count(old)} occurrence(s) de {label} dans {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

def insert_before(path: Path, marker: str, addition: str, label: str) -> None:
    text = path.read_text(encoding='utf-8-sig')
    if addition.strip() in text:
        return
    if text.count(marker) != 1:
        raise SystemExit(f'Patch v0.7.4 impossible : ancre {label} absente ou ambigue dans {path}')
    path.write_text(text.replace(marker, addition.rstrip() + '\n\n' + marker, 1), encoding='utf-8')

def patch_transcribe(root: Path) -> None:
    path = root / 'studio/web/transcribe.py'
    replace_once(path, 'import subprocess\nimport sys\nimport wave\n', 'import subprocess\nimport sys\nimport tempfile\nimport wave\n', 'import tempfile')
    probe = r'''def probe_whisper_vulkan(
    binary_value: str | Path,
    *,
    model_path: str | Path,
    expected_gpu: str = "GPU configuré",
    timeout: int = 150,
) -> dict[str, Any]:
    """Valide Vulkan par un vrai chargement du modèle, pas via --list-devices."""
    binary = _resolve_binary(binary_value)
    model = Path(model_path).expanduser().resolve()
    if binary is None:
        return {"verified": False, "reason": "whisper-cli.exe introuvable.", "backend": None, "gpu_model": expected_gpu}
    if not model.is_file() or model.stat().st_size < 1024 * 1024:
        return {"verified": False, "reason": f"Modèle Whisper absent ou invalide : {model}", "backend": None, "gpu_model": expected_gpu}
    try:
        with tempfile.TemporaryDirectory(prefix="gta-ranked-vulkan-probe-") as temp_dir:
            wav_path = Path(temp_dir) / "vulkan-smoke-test.wav"
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"\x00\x00" * 16000)
            result = run_quiet(
                [*_binary_invocation(binary), "-m", str(model), "-f", str(wav_path), "-l", "en", "-nt", "-t", "2"],
                cwd=str(binary.parent), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout, check=False,
            )
    except subprocess.TimeoutExpired:
        return {"verified": False, "reason": f"Le test Vulkan a dépassé {timeout} secondes pendant le chargement du modèle.", "backend": None, "gpu_model": expected_gpu}
    except OSError as exc:
        return {"verified": False, "reason": f"Impossible de lancer le test Whisper : {exc}", "backend": None, "gpu_model": expected_gpu}
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    backend_match = re.search(r"(?im)whisper_backend_init_gpu:\s+using\s+(Vulkan\d+)\s+backend", output)
    if not backend_match:
        detail = output.strip()[-1400:] or f"Code de sortie {result.returncode}"
        return {"verified": False, "reason": "Whisper n'a pas confirmé l'initialisation du backend GPU Vulkan. " + detail, "backend": None, "gpu_model": expected_gpu}
    backend = backend_match.group(1)
    allocation_pattern = rf"(?im)whisper_model_load:\s+{re.escape(backend)}\s+total size\s*=\s*([0-9.]+)\s*MB"
    allocation_match = re.search(allocation_pattern, output)
    if not allocation_match:
        detail = output.strip()[-1400:] or f"Code de sortie {result.returncode}"
        return {"verified": False, "reason": f"Whisper a initialisé {backend}, mais le modèle n'a pas confirmé son allocation sur ce backend. " + detail, "backend": backend, "gpu_model": expected_gpu}
    if result.returncode != 0:
        detail = output.strip()[-1400:] or f"Code de sortie {result.returncode}"
        return {"verified": False, "reason": f"Le backend {backend} a été initialisé, mais le test Whisper s'est terminé en erreur. " + detail, "backend": backend, "gpu_model": expected_gpu, "model_buffer_mb": float(allocation_match.group(1))}
    return {"verified": True, "reason": f"{backend} initialisé ; modèle alloué sur le GPU ({float(allocation_match.group(1)):.1f} MB).", "backend": backend, "gpu_model": expected_gpu, "model_buffer_mb": float(allocation_match.group(1))}
'''
    insert_before(path, 'def _parse_whisper_timestamp(', probe, 'probe runtime Vulkan')

def patch_app(root: Path) -> None:
    path = root / 'studio/web/app.py'
    replace_once(path, 'import hashlib\nimport logging\n', 'import hashlib\nimport json\nimport logging\n', 'import json')
    replace_once(path, 'from studio.web.transcribe import inspect_whisper_cli\n', 'from studio.web.transcribe import inspect_whisper_cli, probe_whisper_vulkan\n', 'import probe Vulkan')
    replace_once(path, '    whisper_diagnostic_lock = threading.Lock()\n', '    whisper_diagnostic_lock = threading.Lock()\n    whisper_gpu_probe_lock = threading.Lock()\n    whisper_gpu_marker = config.path_for("paths", "database").parent / "whisper-vulkan-verification.json"\n', 'verrou diagnostic')
    helpers = r'''    def _whisper_gpu_fingerprint() -> dict | None:
        binary = config.path_for("executables", "whisper_cli")
        model = config.path_for("transcription", "model_path")
        try:
            binary_stat, model_stat = binary.stat(), model.stat()
        except OSError:
            return None
        if binary_stat.st_size <= 0 or model_stat.st_size < 1024 * 1024:
            return None
        return {"binary_path": str(binary), "binary_size": binary_stat.st_size, "binary_mtime_ns": binary_stat.st_mtime_ns,
                "model_path": str(model), "model_size": model_stat.st_size, "model_mtime_ns": model_stat.st_mtime_ns}

    def _load_whisper_gpu_marker() -> dict | None:
        try:
            marker = json.loads(whisper_gpu_marker.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(marker, dict) or marker.get("fingerprint") != _whisper_gpu_fingerprint():
            return None
        if marker.get("verified") is not True or not str(marker.get("backend", "")).startswith("Vulkan"):
            return None
        return marker

    def _write_whisper_gpu_marker(probe: dict) -> dict:
        fingerprint = _whisper_gpu_fingerprint()
        if not fingerprint:
            raise HTTPException(status_code=409, detail="Le binaire Whisper ou le modèle local est introuvable.")
        marker = {"verified": True, "fingerprint": fingerprint, "backend": str(probe.get("backend") or ""),
                  "gpu_model": str(probe.get("gpu_model") or config.get("hardware", "gpu_model", default="GPU Vulkan")),
                  "model_buffer_mb": float(probe.get("model_buffer_mb") or 0), "verified_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        whisper_gpu_marker.parent.mkdir(parents=True, exist_ok=True)
        temp_marker = whisper_gpu_marker.with_suffix(".tmp")
        temp_marker.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_marker, whisper_gpu_marker)
        return marker

'''
    replace_once(path, '    @app.get("/api/models/status")\n', helpers + '    @app.get("/api/models/status")\n', 'helpers marqueur GPU')
    replace_once(
        path,
        '            whisper_diagnostic = dict(whisper_diagnostic_cache["result"])\n        model_state.update({\n',
        '            whisper_diagnostic = dict(whisper_diagnostic_cache["result"])\n        verified_marker = _load_whisper_gpu_marker()\n        whisper_diagnostic["vulkan_verified"] = bool(verified_marker)\n        whisper_diagnostic["vulkan_probe_available"] = bool(whisper_diagnostic.get("available") and config.path_for("transcription", "model_path").is_file())\n        if verified_marker:\n            whisper_diagnostic.update({\n                "vulkan_detected": True,\n                "devices": [f"{verified_marker[\'backend\']} · {verified_marker[\'gpu_model\']}"],\n                "vulkan_backend": verified_marker["backend"],\n                "gpu_model": verified_marker["gpu_model"],\n                "model_buffer_mb": verified_marker["model_buffer_mb"],\n                "verified_at": verified_marker["verified_at"],\n                "message": f"{verified_marker[\'backend\']} confirmé ; modèle alloué sur {verified_marker[\'gpu_model\']}."\n            })\n        elif whisper_diagnostic.get("available") and not whisper_diagnostic.get("device_listing_supported"):\n            whisper_diagnostic["message"] = "Build whisper.cpp exécutable et DTW compatible. Cette build Release ne propose pas --list-devices ; lance le test GPU pour vérifier le backend Vulkan."\n        model_state.update({\n',
        'application du marqueur diagnostic',
    )
    route = r'''    @app.post("/api/models/whisper/verify")
    def verify_whisper_gpu() -> dict:
        """Lance un vrai smoke-test Whisper/Vulkan puis mémorise le résultat lié au binaire courant."""
        if not whisper_gpu_probe_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Un test Vulkan est déjà en cours.")
        try:
            binary = config.path_for("executables", "whisper_cli")
            model = config.path_for("transcription", "model_path")
            expected_gpu = str(config.get("hardware", "gpu_model", default="GPU Vulkan"))
            if not binary.is_file():
                raise HTTPException(status_code=409, detail="whisper-cli.exe est introuvable. Installe d'abord le moteur Whisper.")
            if not model.is_file() or model.stat().st_size < 1024 * 1024:
                raise HTTPException(status_code=409, detail="Le modèle Whisper large-v3-turbo est absent ou incomplet.")
            probe = probe_whisper_vulkan(binary, model_path=model, expected_gpu=expected_gpu, timeout=150)
            if not probe.get("verified"):
                try:
                    whisper_gpu_marker.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Impossible de supprimer un ancien marqueur Vulkan invalide.")
                return {"verified": False, "message": probe.get("reason", "Le backend Vulkan n'a pas été confirmé."), "probe": probe}
            marker = _write_whisper_gpu_marker(probe)
            with whisper_diagnostic_lock:
                whisper_diagnostic_cache["result"] = None
                whisper_diagnostic_cache["checked_at"] = 0.0
            return {"verified": True, "message": f"{marker['backend']} confirmé ; {marker['gpu_model']} utilise le backend Vulkan et le modèle y est alloué.",
                    "backend": marker["backend"], "gpu_model": marker["gpu_model"], "model_buffer_mb": marker["model_buffer_mb"], "verified_at": marker["verified_at"]}
        finally:
            whisper_gpu_probe_lock.release()

'''
    replace_once(path, '    @app.post("/api/models/whisper/download", status_code=202)\n', route + '    @app.post("/api/models/whisper/download", status_code=202)\n', 'route verify Vulkan')

def patch_ui(root: Path) -> None:
    html = root / 'studio/web/static/index.html'
    replace_once(
        html,
        '<div class="model-row"><div><strong>Moteur whisper.cpp · Vulkan</strong><p id="whisper-engine-status">Vérification du moteur...</p><small id="whisper-engine-details">Le moteur doit être installé dans tools/whisper.cpp/ avec ses DLL à côté de whisper-cli.exe.</small></div><div class="model-actions"><a class="mini-button" href="https://github.com/jiang1997/whisper.cpp-release/releases" target="_blank" rel="noopener">Build Vulkan communautaire ↗</a></div></div>',
        '<div class="model-row"><div><strong>Moteur whisper.cpp · Vulkan</strong><p id="whisper-engine-status">Vérification du moteur...</p><small id="whisper-engine-details">Le Studio vérifie le backend par un vrai chargement du modèle, pas par --list-devices.</small></div><div class="model-actions"><button class="mini-button" id="verify-whisper-gpu">Tester le GPU</button><a class="mini-button" href="https://github.com/jiang1997/whisper.cpp-release/releases" target="_blank" rel="noopener">Build Vulkan ↗</a></div></div>',
        'bouton UI test GPU',
    )
    js = root / 'studio/web/static/app.js'
    replace_once(
        js,
        "      const backend = diagnostic.vulkan_detected ? 'Vulkan détecté' : (diagnostic.device_listing_supported ? 'Aucun périphérique Vulkan listé' : 'Backend GPU non vérifiable avec cette build');\n      engineLine.textContent = `Moteur opérationnel · ${backend}`;\n      engineDetails.textContent = `${diagnostic.path || ''} · ${diagnostic.dtw_supported ? 'timestamps mot à mot DTW disponibles' : 'DTW indisponible, fallback par segment'}`;\n",
        "      const backend = diagnostic.vulkan_verified ? 'Vulkan confirmé · modèle alloué sur GPU' : (diagnostic.vulkan_detected ? 'Vulkan détecté' : (diagnostic.device_listing_supported ? 'Aucun périphérique Vulkan listé' : 'Build Vulkan compatible · test GPU à effectuer'));\n      engineLine.textContent = `Moteur opérationnel · ${backend}`;\n      const gpuDetail = diagnostic.vulkan_verified ? ` · ${diagnostic.gpu_model || 'GPU'} · ${diagnostic.model_buffer_mb || 0} MB alloués · vérifié ${diagnostic.verified_at || ''}` : '';\n      engineDetails.textContent = `${diagnostic.path || ''} · ${diagnostic.dtw_supported ? 'timestamps mot à mot DTW disponibles' : 'DTW indisponible, fallback par segment'}${gpuDetail}`;\n      $('#verify-whisper-gpu').disabled = !diagnostic.vulkan_probe_available || Boolean(state.whisperGpuProbeRunning);\n      $('#verify-whisper-gpu').textContent = state.whisperGpuProbeRunning ? 'Test en cours...' : (diagnostic.vulkan_verified ? 'Re-tester le GPU' : 'Tester le GPU');\n",
        'affichage nouveau statut GPU',
    )
    replace_once(
        js,
        "    } else {\n      engineLine.textContent = 'Moteur absent ou non exécutable';\n      engineDetails.textContent = diagnostic.message || 'Installe whisper.cpp puis actualise le diagnostic.';\n    }\n\n    const whisperLine",
        "    } else {\n      engineLine.textContent = 'Moteur absent ou non exécutable';\n      engineDetails.textContent = diagnostic.message || 'Installe whisper.cpp puis actualise le diagnostic.';\n      $('#verify-whisper-gpu').disabled = true;\n      $('#verify-whisper-gpu').textContent = 'Moteur indisponible';\n    }\n\n    const whisperLine",
        'désactivation bouton quand moteur absent',
    )
    replace_once(js, "const state = { page: 'dashboard', file: null, toastTimer: null, modelPoll: null, updatePoll: null };", "const state = { page: 'dashboard', file: null, toastTimer: null, modelPoll: null, whisperGpuProbeRunning: false, updatePoll: null };", 'état UI')
    fn = r'''async function verifyWhisperGpu() {
  const button = $('#verify-whisper-gpu');
  if (state.whisperGpuProbeRunning) return;
  state.whisperGpuProbeRunning = true;
  button.disabled = true;
  button.textContent = 'Test en cours...';
  $('#whisper-engine-status').textContent = 'Test Vulkan en cours · chargement du modèle sur le GPU...';
  $('#whisper-engine-details').textContent = 'Le test peut prendre quelques dizaines de secondes lors de la première exécution. Le moteur actuel n’est pas remplacé.';
  try {
    const result = await api('/api/models/whisper/verify', { method: 'POST' });
    if (!result.verified) throw new Error(result.message || 'Le backend Vulkan n’a pas été confirmé.');
    toast(`Vulkan confirmé sur ${result.gpu_model}.`);
    await loadModels(true);
  } catch (error) {
    toast(error.message, true);
    $('#whisper-engine-status').textContent = 'Test GPU non confirmé';
    $('#whisper-engine-details').textContent = error.message;
  } finally {
    state.whisperGpuProbeRunning = false;
    button.disabled = false;
    button.textContent = 'Tester le GPU';
    loadModels(true);
  }
}

'''
    replace_once(js, 'async function startWhisperDownload() {\n', fn + 'async function startWhisperDownload() {\n', 'fonction JS test GPU')
    replace_once(js, "  $('#refresh-models-secondary').addEventListener('click', () => loadModels(true));\n", "  $('#refresh-models-secondary').addEventListener('click', () => loadModels(true));\n  $('#verify-whisper-gpu').addEventListener('click', verifyWhisperGpu);\n", 'event bouton test')

def patch_tests(root: Path) -> None:
    test_transcribe = root / 'tests/test_transcribe.py'
    test_probe = r'''def test_probe_whisper_vulkan_requires_backend_and_model_allocation(tmp_path: Path):
    import sys
    import textwrap
    from studio.web.transcribe import probe_whisper_vulkan

    binary = tmp_path / "fake-whisper-vulkan.py"
    binary.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import sys
        print("whisper_backend_init_gpu: using Vulkan0 backend", file=sys.stderr)
        print("whisper_model_load: Vulkan0 total size = 1536.00 MB", file=sys.stderr)
        raise SystemExit(0)
    """), encoding="utf-8")
    binary.chmod(0o755)
    model = tmp_path / "ggml-large-v3-turbo.bin"
    model.write_bytes(b"m" * (1024 * 1024))
    result = probe_whisper_vulkan(binary, model_path=model, expected_gpu="AMD Radeon RX 9060 XT")
    assert result["verified"] is True
    assert result["backend"] == "Vulkan0"
    assert result["gpu_model"] == "AMD Radeon RX 9060 XT"
    assert result["model_buffer_mb"] == 1536.0


def test_probe_whisper_vulkan_rejects_cpu_or_missing_model_allocation(tmp_path: Path):
    import sys
    import textwrap
    from studio.web.transcribe import probe_whisper_vulkan
    binary = tmp_path / "fake-whisper-cpu.py"
    binary.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import sys
        print("whisper_backend_init_gpu: no GPU found", file=sys.stderr)
        raise SystemExit(0)
    """), encoding="utf-8")
    binary.chmod(0o755)
    model = tmp_path / "ggml-large-v3-turbo.bin"
    model.write_bytes(b"m" * (1024 * 1024))
    result = probe_whisper_vulkan(binary, model_path=model)
    assert result["verified"] is False
    assert "n'a pas confirmé" in result["reason"]


'''
    insert_before(test_transcribe, 'def test_inspect_whisper_cli_reports_dtw_and_vulkan_devices(', test_probe, 'tests runtime Vulkan')
    test_web = root / 'tests/test_web.py'
    api_test = r'''def test_whisper_vulkan_verify_endpoint_persists_a_binary_bound_marker(tmp_path: Path, monkeypatch):
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


'''
    insert_before(test_web, 'def test_clip_enters_library_only_after_atomic_validation(', api_test, 'API marker test')

def patch_release(root: Path) -> None:
    for relative, old, new in (
        ('VERSION.txt', 'Version: 0.7.3', 'Version: 0.7.4'),
        ('pyproject.toml', 'version = "0.7.3"', 'version = "0.7.4"'),
        ('config.yaml.default', 'version: 0.7.3', 'version: 0.7.4'),
    ):
        path = root / relative
        replace_once(path, old, new, f'version {relative}')
    (root / 'NOTES-v0.7.4.txt').write_text("""GTA Ranked Studio v0.7.4

Diagnostic Whisper Vulkan :
- Corrige le faux état « Backend GPU non vérifiable » des builds Release whisper.cpp qui ne proposent pas --list-devices.
- Ajoute un test GPU explicite depuis Paramètres > Modèles IA > Tester le GPU.
- Le test charge le modèle local sur whisper.cpp et exige à la fois la sélection du backend VulkanN et l'allocation du buffer du modèle sur ce même backend.
- Le résultat positif est conservé dans data/whisper-vulkan-verification.json et lié à la taille/date du binaire et du modèle. Un remplacement du binaire ou du modèle invalide automatiquement le diagnostic.
- Aucun changement n'est fait à Ollama, Qwen, au modèle Whisper ou au binaire Vulkan déjà installé.
- L'actualisation de la page reste légère ; le smoke-test n'est exécuté que sur demande explicite.
""", encoding='utf-8')

def apply(root: Path) -> None:
    patch_transcribe(root)
    patch_app(root)
    patch_ui(root)
    patch_tests(root)
    patch_release(root)
    for relative in ('studio/web/transcribe.py', 'studio/web/app.py', 'tests/test_transcribe.py', 'tests/test_web.py'):
        source = (root / relative).read_text(encoding='utf-8')
        compile(source, str(root / relative), 'exec')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: apply-hotfix-v0.7.4.py <gta-ranked-studio-source-root>')
    apply(Path(sys.argv[1]))