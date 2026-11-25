from __future__ import annotations
import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8-sig')
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Patch v0.7.8 impossible : {count} occurrence(s) de {label} dans {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def patch_ui(root: Path) -> None:
    html = root / 'studio/web/static/index.html'
    replace_once(html, '<script src="/static/app.js?v=0.7.7"></script>',
                 '<script src="/static/app.js?v=0.7.8"></script>', 'cache-busting app.js')

    js = root / 'studio/web/static/app.js'
    old = """  let actions = '';
  if (job.status === 'ready') {
    actions = `<div class="job-actions"><a class="mini-button" href="${outputUrl}" target="_blank" rel="noopener">Prévisualiser ↗</a><a class="mini-button" href="${outputUrl}" download>Télécharger ↓</a>${thumbUrl ? `<a class="mini-button" href="${thumbUrl}" download="${escapeHtml((metadata.title || 'gta-ranked-cover').replace(/[^a-z0-9]+/gi,'-').toLowerCase())}.jpg">Miniature ↓</a>` : ''}<button class="mini-button good" data-action="copy-social" data-id="${job.id}">Copier le post</button><button class="mini-button good" data-action="validate" data-id="${job.id}">Valider ✓</button><button class="mini-button" data-action="reject" data-id="${job.id}">Rejeter</button></div>`;
  } else if (['queued','running'].includes(job.status)) {
    actions = `<div class="job-actions"><button class="mini-button danger" data-action="cancel" data-id="${job.id}">Annuler le traitement</button></div>`;
  } else if (job.status === 'validated') {
    actions = `<div class="job-actions"><a class="mini-button" href="${outputUrl}" target="_blank" rel="noopener">Ouvrir le Short ↗</a><span class="status-pill validated">✓ Validé</span><button class="mini-button" data-action="reprocess" data-id="${job.id}">Recréer ce Short</button></div>`;
"""
    new = """  let actions = '';
  // Les actions liées aux fichiers et aux métadonnées restent disponibles
  // indépendamment du statut éditorial (à valider ou déjà validé).
  const mediaActions = [
    outputUrl ? `<a class="mini-button" href="${outputUrl}" target="_blank" rel="noopener">Prévisualiser ↗</a><a class="mini-button" href="${outputUrl}" download>Télécharger ↓</a>` : '',
    thumbUrl ? `<a class="mini-button" href="${thumbUrl}" download="${escapeHtml((metadata.title || 'gta-ranked-cover').replace(/[^a-z0-9]+/gi,'-').toLowerCase())}.jpg">Miniature ↓</a>` : '',
  ].join('');
  const metadataActions = `<button class="mini-button" data-action="copy-title" data-id="${job.id}">Copier le titre</button><button class="mini-button" data-action="copy-description" data-id="${job.id}">Copier la description</button><button class="mini-button" data-action="copy-hashtags" data-id="${job.id}">Copier les hashtags</button><button class="mini-button good" data-action="copy-social" data-id="${job.id}">Copier le post</button>`;
  if (job.status === 'ready') {
    actions = `<div class="job-actions">${mediaActions}${metadataActions}<button class="mini-button good" data-action="validate" data-id="${job.id}">Valider ✓</button><button class="mini-button" data-action="reject" data-id="${job.id}">Rejeter</button></div>`;
  } else if (['queued','running'].includes(job.status)) {
    actions = `<div class="job-actions"><button class="mini-button danger" data-action="cancel" data-id="${job.id}">Annuler le traitement</button></div>`;
  } else if (job.status === 'validated') {
    actions = `<div class="job-actions">${mediaActions}${metadataActions}<span class="status-pill validated">✓ Validé</span><button class="mini-button" data-action="reprocess" data-id="${job.id}">Recréer ce Short</button></div>`;
"""
    replace_once(js, old, new, 'barre actions ready/validated')

    marker = """  if (action === 'copy-social') {
    const job = await api(`/api/jobs/${id}`);
    const metadata = job.metadata || {};
    const content = `${metadata.title || 'Titre non généré'}\\n\\n${metadata.description || 'Description non générée'}`;
    try { await navigator.clipboard.writeText(content); toast('Texte de publication copié.'); }
    catch { toast(content); }
    return;
  }
"""
    addition = """  if (['copy-title', 'copy-description', 'copy-hashtags', 'copy-social'].includes(action)) {
    const job = await api(`/api/jobs/${id}`);
    const metadata = job.metadata || {};
    const values = {
      'copy-title': { text: metadata.title || 'Titre non généré', label: 'Titre copié.' },
      'copy-description': { text: metadata.description || 'Description non générée', label: 'Description copiée.' },
      'copy-hashtags': { text: Array.isArray(metadata.hashtags) ? metadata.hashtags.join(' ') : '', label: 'Hashtags copiés.' },
      'copy-social': { text: `${metadata.title || 'Titre non généré'}\\n\\n${metadata.description || 'Description non générée'}`, label: 'Texte de publication copié.' },
    };
    const selected = values[action];
    if (!selected.text) { toast('Aucun hashtag disponible pour ce Short.', true); return; }
    try { await navigator.clipboard.writeText(selected.text); toast(selected.label); }
    catch { toast(selected.text); }
    return;
  }
"""
    replace_once(js, marker, addition, 'actions de copie individuelles')


def patch_tests(root: Path) -> None:
    tests = root / 'tests/test_web.py'
    text = tests.read_text(encoding='utf-8-sig')
    text = text.replace("assert '<script src=\\"/static/app.js?v=0.7.7\\"></script>' in html",
                        "assert '<script src=\\"/static/app.js?v=0.7.8\\"></script>' in html")
    text = text.replace('''        "streamer": "ExampleStreamer",
    })
    store.update_job(
''','''        "streamer": "ExampleStreamer",
        "metadata": {"title": "Titre test", "description": "Description test", "hashtags": ["#GTA", "#Gaming"]},
    })
    store.update_job(
''')
    text = text.replace('''    assert validated["status"] == "validated"
    clips = store.list_clips()
''','''    assert validated["status"] == "validated"
    assert validated["metadata"] == {"title": "Titre test", "description": "Description test", "hashtags": ["#GTA", "#Gaming"]}
    clips = store.list_clips()
''')
    tests.write_text(text, encoding='utf-8')
    test = r'''def test_validated_short_keeps_media_and_metadata_actions():
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


'''
    anchor = 'def test_root_page_disables_stale_html_cache():'
    if test.strip() not in text:
        replace_once(tests, anchor, test + anchor, 'test actions conservées après validation')


def patch_release(root: Path) -> None:
    for relative, old, new in (
        ('VERSION.txt', 'Version: 0.7.7', 'Version: 0.7.8'),
        ('pyproject.toml', 'version = "0.7.7"', 'version = "0.7.8"'),
        ('config.yaml.default', 'version: 0.7.7', 'version: 0.7.8'),
    ):
        replace_once(root / relative, old, new, f'version {relative}')
    (root / 'NOTES-v0.7.8.txt').write_text(
        '''GTA Ranked Studio v0.7.8

Conservation des actions après validation d'un Short :
- Les actions Prévisualiser, Télécharger et Miniature restent accessibles lorsque le Short est validé.
- Ajout d'actions indépendantes pour copier le titre, la description et les hashtags.
- Le bouton Copier le post reste disponible avant et après validation.
- La validation continue uniquement de modifier le statut éditorial et l'entrée Clip Library.
- Aucun changement des médias, modèles IA, réglages, projets ou données locales.
''', encoding='utf-8')


def apply(root: Path) -> None:
    root = root.resolve()
    patch_ui(root)
    patch_tests(root)
    patch_release(root)
    compile((root / 'tests/test_web.py').read_text(encoding='utf-8'), str(root / 'tests/test_web.py'), 'exec')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: apply-hotfix-v0.7.8.py <gta-ranked-studio-source-root>')
    apply(Path(sys.argv[1]))
