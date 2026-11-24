from __future__ import annotations
import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8-sig')
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Patch v0.7.5 impossible : {count} occurrence(s) de {label} dans {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def insert_after(path: Path, marker: str, addition: str, label: str) -> None:
    text = path.read_text(encoding='utf-8-sig')
    if addition.strip() in text:
        return
    if text.count(marker) != 1:
        raise SystemExit(f'Patch v0.7.5 impossible : ancre {label} absente ou ambigue dans {path}')
    path.write_text(text.replace(marker, marker + addition.rstrip() + '\n', 1), encoding='utf-8')


def insert_before(path: Path, marker: str, addition: str, label: str) -> None:
    text = path.read_text(encoding='utf-8-sig')
    if addition.strip() in text:
        return
    if text.count(marker) != 1:
        raise SystemExit(f'Patch v0.7.5 impossible : ancre {label} absente ou ambigue dans {path}')
    path.write_text(text.replace(marker, addition.rstrip() + '\n\n' + marker, 1), encoding='utf-8')


def patch_ui(root: Path) -> None:
    html = root / 'studio/web/static/index.html'
    replace_once(
        html,
        '<button class="mini-button" id="verify-whisper-gpu">Tester le GPU</button>',
        '<button type="button" class="mini-button" id="verify-whisper-gpu" aria-describedby="whisper-engine-details">Tester le GPU</button>',
        'bouton GPU non-submit',
    )
    replace_once(
        html,
        '<script src="/static/app.js?v=0.4.0"></script>',
        '<script src="/static/app.js?v=0.7.5"></script>',
        'cache-busting app.js',
    )

    js = root / 'studio/web/static/app.js'
    # The settings page polls models every 5 seconds. Keep the explicit smoke-test
    # progress visible instead of letting the normal status refresh overwrite it.
    insert_after(
        js,
        "    const data = await api(`/api/models/status${forceRefresh ? '?refresh=true' : ''}`);\n",
        "    if (state.whisperGpuProbeRunning) {\n"
        "      const probeButton = $('#verify-whisper-gpu');\n"
        "      if (probeButton) { probeButton.disabled = true; probeButton.textContent = 'Test en cours...'; }\n"
        "      $('#whisper-engine-status').textContent = 'Test Vulkan en cours · chargement du modèle sur le GPU...';\n"
        "      $('#whisper-engine-details').textContent = 'Le test peut prendre quelques dizaines de secondes. Le moteur actuel reste intact.';\n"
        "      return;\n"
        "    }\n",
        'préserver progression du test GPU',
    )
    replace_once(
        js,
        "  $('#verify-whisper-gpu').addEventListener('click', verifyWhisperGpu);\n",
        "  const verifyGpuButton = $('#verify-whisper-gpu');\n"
        "  if (verifyGpuButton) verifyGpuButton.addEventListener('click', verifyWhisperGpu);\n",
        'liaison tolérante du clic GPU',
    )
    # Ensure the test routine reports its state before the request starts and has
    # a stable, visible result even if the API returns an error.
    replace_once(
        js,
        "  $('#whisper-engine-status').textContent = 'Test Vulkan en cours · chargement du modèle sur le GPU...';\n",
        "  $('#whisper-engine-status').textContent = 'Test Vulkan en cours · chargement du modèle sur le GPU...';\n"
        "  $('#whisper-engine-status').setAttribute('aria-live', 'polite');\n",
        'retour accessible état GPU',
    )


def patch_tests(root: Path) -> None:
    test_web = root / 'tests/test_web.py'
    test = r'''def test_whisper_gpu_button_uses_fresh_script_and_visible_feedback():
    from pathlib import Path

    static = Path(__file__).resolve().parents[1] / "studio" / "web" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.js").read_text(encoding="utf-8")
    assert '<script src="/static/app.js?v=0.7.5"></script>' in html
    assert '<button type="button" class="mini-button" id="verify-whisper-gpu"' in html
    assert "/api/models/whisper/verify" in js
    assert "if (verifyGpuButton) verifyGpuButton.addEventListener('click', verifyWhisperGpu);" in js
    assert "Test Vulkan en cours" in js
    assert "state.whisperGpuProbeRunning" in js


'''
    insert_before(test_web, 'def test_clip_enters_library_only_after_atomic_validation(', test, 'test cache UI GPU')


def patch_release(root: Path) -> None:
    for relative, old, new in (
        ('VERSION.txt', 'Version: 0.7.4', 'Version: 0.7.5'),
        ('pyproject.toml', 'version = "0.7.4"', 'version = "0.7.5"'),
        ('config.yaml.default', 'version: 0.7.4', 'version: 0.7.5'),
    ):
        replace_once(root / relative, old, new, f'version {relative}')
    (root / 'NOTES-v0.7.5.txt').write_text(
        """GTA Ranked Studio v0.7.5\n\nDiagnostic GPU Vulkan :\n- Corrige le cache statique du JavaScript : le bouton « Tester le GPU » utilise désormais un identifiant d'asset propre à la version.\n- Déclare explicitement le bouton comme type=button pour empêcher toute soumission de formulaire involontaire.\n- Rend la liaison du clic tolérante et garde le statut « Test en cours » visible pendant les actualisations automatiques.\n- Aucun changement du moteur Whisper, du modèle, d'Ollama ou de Qwen.\n""",
        encoding='utf-8',
    )


def apply(root: Path) -> None:
    patch_ui(root)
    patch_tests(root)
    patch_release(root)
    for relative in ('studio/web/static/app.js', 'tests/test_web.py'):
        source = (root / relative).read_text(encoding='utf-8')
        compile(source, str(root / relative), 'exec') if relative.endswith('.py') else None


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: apply-hotfix-v0.7.5.py <gta-ranked-studio-source-root>')
    apply(Path(sys.argv[1]))