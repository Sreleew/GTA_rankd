const state = { page: 'dashboard', file: null, toastTimer: null, modelPoll: null, whisperGpuProbeRunning: false, ollamaVerifyRunning: false, ollamaVerificationResult: null, updatePoll: null, updateInProgress: false, updateTargetVersion: '', bestOfClips: [], bestOfSelectedIds: [], bestOfDate: '', bestOfPlan: null, bestOfRenderJob: null, shortBatchIds: [] };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function toast(message, error = false) {
  const node = $('#toast');
  node.textContent = message;
  node.style.borderColor = error ? '#824747' : '#536044';
  node.classList.add('show');
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => node.classList.remove('show'), 5200);
}

function setPage(name) {
  state.page = name;
  $$('.page').forEach(page => page.classList.toggle('active', page.id === `page-${name}`));
  $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.page === name));
  const labels = { dashboard: 'Vue d\'ensemble', shorts: 'Créer un Short', highlights: 'Moments forts', library: 'Clip library', bestof: 'Daily Best Of', settings: 'Paramètres' };
  $('#page-title').textContent = labels[name] || 'GTA Ranked Studio';
  if (name === 'shorts') loadJobs();
  if (name === 'highlights') loadHighlights();
  if (name === 'library') loadLibrary();
  if (name === 'bestof') loadBestOf();
  if (name === 'settings') { loadModels(); loadUpdates(); }
}

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

function statusLabel(status) {
  return ({ queued: 'EN ATTENTE', running: 'EN COURS', cancelling: 'ANNULATION…', cancelled: 'ANNULÉ', ready: 'À VALIDER', validated: 'VALIDÉ', rejected: 'REJETÉ', error: 'ERREUR' })[status] || String(status || '').toUpperCase();
}

function outputUrlFromPath(filePath) {
  if (!filePath) return '';
  const parts = String(filePath).split(/[\\/]/).slice(-4);
  return `/outputs/${parts.map(encodeURIComponent).join('/')}`;
}

function jobCard(job) {
  const outputUrl = outputUrlFromPath(job.output_path);
  const thumbUrl = outputUrlFromPath(job.thumbnail_path);
  const metadata = job.metadata || {};
  const title = metadata.title || job.source_title || job.streamer || (job.source_kind === 'url' ? job.source_url : 'Clip importé') || 'Clip';
  const socialCaption = String(metadata.description || '').split('\n')[0].trim();
  let actions = '';
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
  } else if (job.status === 'error' || job.status === 'cancelled') {
    actions = `<div class="job-actions">${job.status === 'error' ? `<button class="mini-button" data-action="details" data-id="${job.id}">Voir l'erreur</button>` : '<span class="muted">Traitement interrompu</span>'}<button class="mini-button" data-action="reprocess" data-id="${job.id}">Relancer</button></div>`;
  } else if (job.status === 'rejected') {
    actions = `<div class="job-actions"><button class="mini-button" data-action="reprocess" data-id="${job.id}">Recréer ce Short</button></div>`;
  }
  const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
  const meta = [job.streamer, job.duration ? `${Number(job.duration).toFixed(1)} s` : '', new Date(job.created_at).toLocaleString('fr-FR')].filter(Boolean).join(' · ');
  const quality = metadata.quality_report || null;
  const qualityLabels = { passed: 'QC OK', review: 'À vérifier', partial: 'Contrôle partiel', failed: 'Problème détecté' };
  const qualityHtml = quality ? `<details class="quality-report ${escapeHtml(quality.status || 'partial')}"><summary><span>Contrôle qualité</span><strong>${escapeHtml(qualityLabels[quality.status] || 'Contrôle')}</strong></summary><p>${escapeHtml(quality.summary || '')}</p>${(quality.warnings || []).length ? `<ul>${quality.warnings.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}</details>` : '';
  const speakerFilterStatus = metadata.speaker_filter?.status || '';
  const voiceState = {
    dominant_filtered: 'Voix principale isolée',
    single_speaker: 'Une seule voix détectée',
    all_voices: 'Toutes les voix sous-titrées',
  }[speakerFilterStatus] || '';
  const subtitleState = ['ambiguous_speakers', 'low_word_attribution', 'diarization_unavailable', 'no_speaker_segments'].includes(speakerFilterStatus)
    ? 'Sous-titres omis : voix non isolée'
    : metadata.transcription_status === 'completed'
      ? 'Sous-titres mot à mot (DTW)'
      : metadata.transcription_status === 'completed_segment_fallback'
        ? 'Sous-titres par segment (DTW indisponible)'
        : metadata.transcription_message || '';
  return `<article class="job-card">
    ${thumbUrl ? `<img class="job-thumb" src="${thumbUrl}" alt="Miniature du Short">` : `<div class="job-thumb job-thumb-placeholder">▶</div>`}
    <div class="job-main"><strong title="${escapeHtml(title)}">${escapeHtml(title)}</strong>${socialCaption ? `<div class="job-caption">${escapeHtml(socialCaption)}</div>` : ''}<div class="job-meta">${escapeHtml(meta || (job.source_kind || 'clip').toUpperCase())}</div><div class="job-message">${escapeHtml(job.message || '')}${subtitleState ? ` · ${escapeHtml(subtitleState)}` : ''}${voiceState ? ` · ${escapeHtml(voiceState)}` : ''}${job.error ? ` · ${escapeHtml(job.error.slice(0, 200))}` : ''}</div>${qualityHtml}${['queued','running'].includes(job.status) ? `<div class="job-progress"><span style="width:${progress}%"></span></div>` : ''}${actions}</div>
    <div class="job-side"><span class="status-pill ${escapeHtml(job.status)}">${statusLabel(job.status)}</span></div>
  </article>`;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || data.message || `Erreur HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

async function loadDashboard() {
  try {
    const data = await api('/api/dashboard');
    $('#stat-total').textContent = data.total_jobs;
    $('#stat-processing').textContent = data.processing;
    $('#stat-review').textContent = data.to_review;
    $('#stat-validated').textContent = data.validated;
    $('#nav-review-count').textContent = data.to_review;
    $('#recent-jobs').innerHTML = data.recent_jobs.length ? data.recent_jobs.map(jobCard).join('') : '<div class="empty-state">Aucun clip pour le moment. Ajoute ton premier fichier pour commencer.</div>';
  } catch (error) { if (!state.updateInProgress) toast(error.message, true); }
}

function persistShortBatchIds() {
  try { localStorage.setItem('gta-ranked-short-batches', JSON.stringify(state.shortBatchIds)); }
  catch { /* Le suivi reste disponible en mémoire si le stockage navigateur est indisponible. */ }
}

function trackShortBatch(batchId) {
  if (!/^[a-f0-9]{32}$/.test(String(batchId || ''))) return;
  state.shortBatchIds = [batchId, ...state.shortBatchIds.filter(id => id !== batchId)].slice(0, 4);
  persistShortBatchIds();
}

function renderShortBatchTracker(batches) {
  const container = $('#short-batch-tracker');
  if (!container) return;
  if (!batches.length) {
    container.classList.add('hidden');
    container.innerHTML = '';
    return;
  }
  container.classList.remove('hidden');
  container.innerHTML = batches.map(batch => {
    const progress = Math.max(0, Math.min(100, Number(batch.progress) || 0));
    const statusText = batch.status === 'running'
      ? 'Traitement en cours'
      : batch.status === 'completed_with_errors'
        ? 'Terminé avec des erreurs'
        : 'Lot terminé';
    const rows = (batch.jobs || []).map(job => {
      const label = job.status === 'error' ? 'Erreur'
        : job.status === 'cancelled' ? 'Annulé'
          : job.status === 'ready' ? 'À valider'
            : job.status === 'validated' ? 'Validé'
              : job.status === 'rejected' ? 'Rejeté'
                : statusLabel(job.status);
      const detail = job.error || job.message || '';
      return `<li><span class="short-batch-job-title" title="${escapeHtml(job.title || '')}">${escapeHtml(job.title || 'Clip Twitch')}<small>${escapeHtml(detail)}</small></span><span class="status-pill ${escapeHtml(job.status)}">${escapeHtml(label)}</span></li>`;
    }).join('');
    return `<article class="short-batch-card">
      <div class="short-batch-heading"><div><strong>Lot Twitch · ${batch.total} clips</strong><small>${escapeHtml(statusText)}</small></div><button type="button" class="text-button" data-dismiss-short-batch="${escapeHtml(batch.batch_id)}">Masquer</button></div>
      <div class="short-batch-progress"><span style="width:${progress}%"></span></div>
      <p>${escapeHtml(batch.message || '')} · ${progress}%</p>
      <ul>${rows}</ul>
    </article>`;
  }).join('');
}

async function refreshShortBatchTracker() {
  if (!state.shortBatchIds.length) return;
  const results = await Promise.all(state.shortBatchIds.map(async batchId => {
    try {
      return { batchId, batch: await api(`/api/shorts/batches/${encodeURIComponent(batchId)}`), missing: false };
    } catch (error) {
      return { batchId, batch: null, missing: error.status === 404 };
    }
  }));
  state.shortBatchIds = results.filter(item => !item.missing).map(item => item.batchId).slice(0, 4);
  persistShortBatchIds();
  renderShortBatchTracker(results.filter(item => item.batch).map(item => item.batch));
}

async function loadJobs() {
  try {
    const jobs = await api('/api/jobs?limit=100');
    $('#all-jobs').innerHTML = jobs.length ? jobs.map(jobCard).join('') : '<div class="empty-state">Tes clips apparaîtront ici après leur import.</div>';
    $('#nav-review-count').textContent = jobs.filter(job => job.status === 'ready').length;
    await refreshShortBatchTracker();
  } catch (error) { if (!state.updateInProgress) toast(error.message, true); }
}

async function loadLibrary() {
  try {
    const clips = await api('/api/clips?limit=100');
    $('#clip-library').innerHTML = clips.length ? clips.map(clip => jobCard({
      id: clip.job_id, status: clip.status, progress: 100, source_kind: clip.source_url ? 'url' : 'upload',
      source_title: clip.source_title || 'Clip', streamer: clip.streamer, duration: clip.duration,
      output_path: clip.output_path, thumbnail_path: clip.thumbnail_path, message: 'Enregistré dans le clip bank', created_at: clip.created_at,
    })).join('') : '<div class="empty-state">Aucun clip enregistré.</div>';
  } catch (error) { toast(error.message, true); }
}

function bestOfClipTitle(clip) {
  return clip.source_title || clip.streamer || 'GTA moment';
}

function bestOfClipCard(clip, selectedIndex = -1) {
  const thumbnail = outputUrlFromPath(clip.thumbnail_path);
  const title = escapeHtml(bestOfClipTitle(clip));
  const streamer = escapeHtml(clip.streamer || 'Streamer non renseigné');
  const duration = formatMediaTime(clip.duration);
  const image = thumbnail
    ? `<img class="bestof-thumb" src="${thumbnail}" alt="">`
    : '<div class="bestof-thumb bestof-thumb-empty">▶</div>';
  if (selectedIndex < 0) {
    return `<article class="bestof-clip">${image}<div class="bestof-clip-info"><strong>${title}</strong><small>${streamer} · ${duration}</small></div><button type="button" class="mini-button good" data-bestof-add="${escapeHtml(clip.id)}">Ajouter +</button></article>`;
  }
  return `<article class="bestof-clip bestof-clip-selected"><span class="bestof-order">${selectedIndex + 1}</span>${image}<div class="bestof-clip-info"><strong>${title}</strong><small>${streamer} · ${duration}</small></div><div class="bestof-clip-controls"><button type="button" class="mini-button" data-bestof-up="${selectedIndex}" ${selectedIndex === 0 ? 'disabled' : ''} aria-label="Monter">↑</button><button type="button" class="mini-button" data-bestof-down="${selectedIndex}" ${selectedIndex === state.bestOfSelectedIds.length - 1 ? 'disabled' : ''} aria-label="Descendre">↓</button><button type="button" class="mini-button danger" data-bestof-remove="${escapeHtml(clip.id)}" aria-label="Retirer">×</button></div></article>`;
}

function renderBestOf() {
  const dateClips = state.bestOfClips.filter(clip => String(clip.date_key || '').slice(0, 10) === state.bestOfDate);
  const selected = state.bestOfSelectedIds.map(id => dateClips.find(clip => clip.id === id)).filter(Boolean);
  const available = dateClips.filter(clip => !state.bestOfSelectedIds.includes(clip.id));
  $('#bestof-available-count').textContent = `${available.length} disponible${available.length > 1 ? 's' : ''}`;
  $('#bestof-selected-count').textContent = `${selected.length} sélection${selected.length > 1 ? 's' : ''}`;
  $('#bestof-available').innerHTML = available.length
    ? available.map(clip => bestOfClipCard(clip)).join('')
    : '<div class="empty-state">Tous les Shorts de cette journée sont dans la sélection.</div>';
  $('#bestof-selected').innerHTML = selected.length
    ? selected.map((clip, index) => bestOfClipCard(clip, index)).join('')
    : '<div class="empty-state">Ajoute des Shorts depuis la bibliothèque.</div>';
  const total = selected.reduce((sum, clip) => sum + Math.max(0, Number(clip.duration) || 0), 0);
  $('#bestof-total-time').textContent = formatMediaTime(total);
  $('#bestof-progress-fill').style.width = `${Math.min(100, total / 660 * 100)}%`;
  const valid = total >= 540 && total <= 660 && selected.length > 0;
  let target = 'Sélectionne des clips';
  let feedback = 'Le rendu vidéo sera activé après validation de ce module de sélection.';
  if (selected.length && total < 540) {
    target = `Encore ${formatMediaTime(540 - total)}`;
    feedback = 'Ajoute des Shorts pour atteindre au moins 9 minutes.';
  } else if (total > 660) {
    target = `Retire ${formatMediaTime(total - 660)}`;
    feedback = 'La sélection dépasse 11 minutes. Retire ou réordonne les séquences.';
  } else if (valid) {
    target = 'Durée cible atteinte';
    feedback = 'La sélection peut être vérifiée. Les fichiers sources restent inchangés.';
  }
  $('#bestof-target-state').textContent = target;
  $('#bestof-feedback').textContent = feedback;
  $('#bestof-validate').disabled = !valid;
  state.bestOfPlan = null;
  state.bestOfRenderJob = null;
  const renderButton = $('#bestof-render');
  if (renderButton) renderButton.classList.add('hidden');
}

async function loadBestOf() {
  try {
    state.bestOfClips = await api('/api/clips?limit=200');
    const dates = [...new Set(state.bestOfClips.map(clip => String(clip.date_key || '').slice(0, 10)).filter(Boolean))].sort().reverse();
    const dateSelect = $('#bestof-date');
    if (!dates.length) {
      state.bestOfDate = '';
      dateSelect.innerHTML = '<option value="">Aucune journée disponible</option>';
      state.bestOfSelectedIds = [];
      renderBestOf();
      $('#bestof-available').innerHTML = '<div class="empty-state">Aucun Short validé dans la bibliothèque. Termine un Short puis clique sur « Valider » pour l’ajouter ici.</div>';
      return;
    }
    if (!dates.includes(state.bestOfDate)) {
      state.bestOfDate = dates[0];
      state.bestOfSelectedIds = [];
    }
    dateSelect.innerHTML = dates.map(date => `<option value="${escapeHtml(date)}" ${date === state.bestOfDate ? 'selected' : ''}>${new Date(`${date}T12:00:00`).toLocaleDateString('fr-FR', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' })}</option>`).join('');
    state.bestOfSelectedIds = state.bestOfSelectedIds.filter(id => state.bestOfClips.some(clip => clip.id === id && clip.date_key === state.bestOfDate));
    renderBestOf();
  } catch (error) {
    toast(error.message, true);
    $('#bestof-available').innerHTML = '<div class="empty-state">Impossible de charger la bibliothèque locale.</div>';
  }
}

async function validateBestOfSelection() {
  const button = $('#bestof-validate');
  button.disabled = true;
  button.textContent = 'Vérification…';
  try {
    const plan = await api('/api/bestof/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clip_ids: state.bestOfSelectedIds, date_key: state.bestOfDate }),
    });
    state.bestOfPlan = plan;
    $('#bestof-feedback').textContent = `Sélection vérifiée : ${plan.clip_count} Shorts, ${plan.formatted_duration}. Prêt pour l'assemblage 16:9.`;
    $('#bestof-render').classList.remove('hidden');
    toast('Sélection Daily Best Of vérifiée.');
  } catch (error) {
    $('#bestof-feedback').textContent = error.message;
    toast(error.message, true);
  } finally {
    const currentClips = state.bestOfSelectedIds
      .map(id => state.bestOfClips.find(clip => clip.id === id))
      .filter(Boolean);
    const currentDuration = currentClips.reduce((sum, clip) => sum + Math.max(0, Number(clip.duration) || 0), 0);
    button.disabled = !(currentClips.length && currentDuration >= 540 && currentDuration <= 660);
    button.textContent = 'Vérifier la sélection';
  }
}


async function renderBestOfEpisode() {
  if (!state.bestOfPlan || !state.bestOfPlan.ready_for_render) {
    toast('Vérifie d’abord la sélection.', true);
    return;
  }
  const button = $('#bestof-render');
  button.disabled = true;
  button.textContent = 'Démarrage…';
  $('#bestof-feedback').textContent = 'Préparation du rendu horizontal 1920 × 1080…';
  try {
    const started = await api('/api/bestof/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clip_ids: state.bestOfSelectedIds, date_key: state.bestOfDate }),
    });
    state.bestOfRenderJob = started.id;
    let finished = false;
    const deadline = Date.now() + 45 * 60 * 1000;
    while (!finished && Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      const job = await api(`/api/bestof/jobs/${encodeURIComponent(started.id)}`);
      $('#bestof-feedback').textContent = job.error
        ? `Échec du rendu : ${job.error}`
        : job.message || 'Assemblage en cours…';
      if (job.status === 'completed') {
        const link = document.createElement('a');
        link.href = job.output_url;
        link.download = '';
        link.className = 'mini-button bestof-download';
        link.textContent = 'Ouvrir / télécharger le Daily Best Of';
        $('#bestof-feedback').append(' ', link);
        toast('Daily Best Of exporté en 16:9.');
        finished = true;
      } else if (job.status === 'error') {
        throw new Error(job.error || 'Le rendu a échoué.');
      }
    }
    if (!finished) throw new Error('Le rendu prend plus de temps que prévu. Vérifie la bibliothèque dans quelques instants.');
  } catch (error) {
    $('#bestof-feedback').textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = 'Générer le Daily Best Of 16:9';
  }
}

function formatMediaTime(value) {
  const total = Math.max(0, Math.floor(Number(value) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  return hours > 0
    ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function highlightCandidateCard(scan, candidate) {
  const alreadyCreated = Boolean(candidate.created_job_id);
  const reasons = (candidate.reasons || []).map(reason => `<span class="highlight-reason">${escapeHtml(reason)}</span>`).join('');
  const transcript = candidate.transcript
    ? `<p class="highlight-transcript">“${escapeHtml(candidate.transcript)}”</p>`
    : '<p class="highlight-transcript muted">Aucune parole détectée sur ce passage.</p>';
  return `<article class="highlight-candidate">
    <div class="highlight-candidate-top"><div><span class="highlight-rank">#${candidate.rank}</span><strong>${formatMediaTime(candidate.start_time)} → ${formatMediaTime(candidate.end_time)}</strong></div><span class="highlight-score">${Number(candidate.score).toFixed(1)}/100</span></div>
    <div class="highlight-reasons">${reasons}</div>
    ${transcript}
    <div class="highlight-candidate-bottom"><small>Énergie ${Math.round(candidate.audio_score * 100)} · Dialogue ${Math.round(candidate.speech_score * 100)} · Réaction ${Math.round(candidate.reaction_score * 100)} · Accroche ${Math.round((candidate.opening_score || 0) * 100)}</small>
      <button class="mini-button ${alreadyCreated ? 'is-created' : ''}" data-highlight-create data-scan-id="${scan.id}" data-candidate-id="${candidate.id}" ${alreadyCreated ? 'disabled' : ''}>${alreadyCreated ? 'Envoyé dans les Shorts ✓' : 'Créer ce Short →'}</button>
    </div>
  </article>`;
}

function highlightScanCard(scan) {
  const sourceName = scan.source_title || scan.source_url || (scan.source_kind === 'upload' ? 'Fichier vidéo local' : 'Source Twitch');
  const statusNames = { queued: 'EN ATTENTE', running: 'ANALYSE EN COURS', cancelling: 'ANNULATION…', cancelled: 'ANNULÉE', completed: 'ANALYSE TERMINÉE', error: 'ERREUR' };
  const candidateList = (scan.candidates || []).length
    ? `<div class="highlight-candidates">${scan.candidates.map(candidate => highlightCandidateCard(scan, candidate)).join('')}</div>`
    : (scan.status === 'completed'
      ? '<div class="empty-state compact-empty">Aucun passage ne dépasse le seuil strict de 80/100. Essaie une autre plage horaire.</div>'
      : '');
  const progress = `<div class="highlight-progress"><div class="highlight-progress-track"><span style="width:${Math.max(0, Math.min(100, Number(scan.progress) || 0))}%"></span></div><small>${Math.max(0, Math.min(100, Number(scan.progress) || 0))}% · ${escapeHtml(scan.message || '')}</small></div>`;
  const cancelAction = ['queued','running'].includes(scan.status) ? `<div class="highlight-actions"><button class="mini-button danger" data-highlight-cancel data-scan-id="${scan.id}">Annuler l'analyse</button></div>` : '';
  const error = scan.error ? `<p class="highlight-error">${escapeHtml(scan.error)}</p>` : '';
  const duration = scan.source_duration ? ` · ${formatMediaTime(scan.source_duration)}` : '';
  const batchLabel = scan.metadata && Number(scan.metadata.batch_count) > 1
    ? ` · LOT ${Number(scan.metadata.batch_index)}/${Number(scan.metadata.batch_count)} · ${formatMediaTime(scan.window_start)} → ${formatMediaTime(scan.window_end)}`
    : (scan.window_start != null && scan.window_end != null
      ? ` · ${formatMediaTime(scan.window_start)} → ${formatMediaTime(scan.window_end)}`
      : '');
  const transcriptionNote = scan.status === 'completed' && scan.metadata
    ? `<small class="highlight-method-note">${scan.metadata.transcription_available
        ? `Whisper local · ${Number(scan.metadata.transcribed_words || 0)} mots analysés`
        : 'Whisper non détecté · classement audio uniquement'}</small>`
    : '';
  return `<article class="highlight-scan-card">
    <div class="highlight-scan-header"><div><div class="eyebrow">${scan.source_kind === 'url' ? 'TWITCH SOURCE' : 'LOCAL VIDEO'}${duration}${batchLabel}</div><h4>${escapeHtml(sourceName)}</h4><small>${escapeHtml(scan.streamer || 'Streamer non renseigné')} · ${new Date(scan.created_at).toLocaleString('fr-FR')}</small></div><span class="status-pill ${scan.status === 'completed' ? 'validated' : scan.status === 'error' ? 'error' : 'running'}">${statusNames[scan.status] || scan.status}</span></div>
    ${['queued','running'].includes(scan.status) ? progress : `<p class="highlight-complete">${escapeHtml(scan.message || (scan.status === 'cancelled' ? 'Analyse annulée' : 'Analyse terminée'))}</p>`}
    ${cancelAction}${error}${transcriptionNote}${candidateList}
  </article>`;
}

function highlightBatchCard(scan, summary) {
  const sourceName = summary.source_title || scan.source_title || summary.source_url || 'VOD Twitch';
  const total = Number(summary.total) || 0;
  const completed = Number(summary.completed) || 0;
  const errors = Number(summary.errors) || 0;
  const cancelled = Number(summary.cancelled) || 0;
  const queued = Number(summary.queued) || 0;
  const running = Number(summary.running) || 0;
  const active = queued + running;
  const progress = Math.max(0, Math.min(100, Number(summary.progress) || 0));
  const status = active
    ? 'LOT EN COURS'
    : errors
      ? 'LOT TERMINÉ AVEC ERREURS'
      : cancelled
        ? (cancelled === total ? 'LOT ANNULÉ' : 'LOT PARTIELLEMENT ANNULÉ')
        : 'LOT TERMINÉ';
  const statusClass = active ? 'running' : errors ? 'error' : 'validated';
  const pendingIds = (summary.scans || [])
    .filter(item => ['queued', 'running'].includes(item.status))
    .map(item => item.id)
    .join(',');
  const cancelAction = pendingIds
    ? `<div class="highlight-actions"><button class="mini-button danger" data-highlight-batch-cancel data-scan-ids="${escapeHtml(pendingIds)}">Annuler le lot</button></div>`
    : '';
  const message = active
    ? `${completed}/${total} tranches terminées · ${queued} en attente · ${running} en cours`
    : `${completed}/${total} tranches terminées · ${errors} erreurs · ${cancelled} annulées`;
  const candidates = (summary.candidates || []).length
    ? `<div class="highlight-candidates">${summary.candidates.map(candidate => highlightCandidateCard({ id: candidate.scan_id }, candidate)).join('')}</div>`
    : (active
      ? ''
      : '<div class="empty-state compact-empty">Aucun passage ne dépasse le seuil strict de 80/100 sur ce lot. Essaie une autre plage horaire.</div>');
  const failed = (summary.scans || []).filter(item => item.status === 'error');
  const errorsList = failed.length
    ? `<div class="highlight-batch-errors">${failed.map(item => `<p>${formatMediaTime(item.window_start)} → ${formatMediaTime(item.window_end)} · ${escapeHtml(item.error || item.message || 'Erreur inconnue')}</p>`).join('')}</div>`
    : '';
  return `<article class="highlight-scan-card highlight-batch-card">
    <div class="highlight-scan-header"><div><div class="eyebrow">TWITCH VOD · LOT DE ${total} TRANCHES · ${progress}%</div><h4>${escapeHtml(sourceName)}</h4><small>${escapeHtml(summary.streamer || scan.streamer || 'Streamer non renseigné')} · ${message}</small></div><span class="status-pill ${statusClass}">${status}</span></div>
    <div class="highlight-progress"><div class="highlight-progress-track"><span style="width:${progress}%"></span></div><small>${progress}% · progression moyenne des tranches</small></div>
    ${cancelAction}${errorsList}
    <small class="highlight-method-note">Classement consolidé indicatif · doublons entre tranches filtrés · vérifie les meilleurs passages avant de créer les Shorts.</small>
    ${candidates}
  </article>`;
}

function renderHighlightScans(scans) {
  const groups = new Map();
  for (const scan of scans) {
    const batchId = scan.metadata && scan.metadata.batch_id;
    if (batchId && Number(scan.metadata.batch_count) > 1) {
      if (!groups.has(batchId)) groups.set(batchId, []);
      groups.get(batchId).push(scan);
    }
  }
  const rendered = new Set();
  return scans.map(scan => {
    const batchId = scan.metadata && scan.metadata.batch_id;
    if (!batchId || Number(scan.metadata.batch_count) <= 1) return highlightScanCard(scan);
    const group = groups.get(batchId) || [];
    const expected = Number(scan.metadata.batch_count);
    if (group.length !== expected) return highlightScanCard(scan);
    if (rendered.has(batchId)) return '';
    rendered.add(batchId);
    const anchor = group.find(item => Number(item.metadata.batch_index) === 1);
    return anchor && anchor.batch_summary ? highlightBatchCard(anchor, anchor.batch_summary) : group.map(highlightScanCard).join('');
  }).join('');
}

async function cancelHighlightBatch(button) {
  const scanIds = (button.dataset.scanIds || '').split(',').filter(Boolean);
  if (!scanIds.length) return;
  button.disabled = true;
  button.textContent = 'Annulation du lot…';
  let cancelled = 0;
  for (const scanId of scanIds) {
    try {
      await api(`/api/highlights/${scanId}/cancel`, { method: 'POST' });
      cancelled += 1;
    } catch {
      // A segment may finish or enter cancellation while the batch is being stopped.
    }
  }
  toast(`${cancelled}/${scanIds.length} analyses annulées.`, cancelled !== scanIds.length);
  await loadHighlights();
}

async function cancelHighlightScan(button) {
  const scanId = button.dataset.scanId;
  button.disabled = true;
  button.textContent = 'Annulation…';
  try {
    const result = await api(`/api/highlights/${scanId}/cancel`, { method: 'POST' });
    toast(result.message || 'Annulation de l’analyse demandée.');
    await loadHighlights();
  } catch (error) {
    toast(error.message, true);
    button.disabled = false;
    button.textContent = 'Annuler l’analyse';
  }
}

async function loadHighlights() {
  try {
    const scans = await api('/api/highlights?limit=100');
    $('#highlight-scans').innerHTML = scans.length
      ? renderHighlightScans(scans)
      : '<div class="empty-state">Aucune analyse pour le moment. Ajoute une VOD ou un clip Twitch pour commencer.</div>';
  } catch (error) { toast(error.message, true); }
}

function showHighlightSourceTab(kind) {
  $$('.highlight-source-tab').forEach(tab => tab.classList.toggle('active', tab.dataset.highlightSourceTab === kind));
  $('#highlight-upload-form').classList.toggle('hidden', kind !== 'file');
  $('#highlight-url-form').classList.toggle('hidden', kind !== 'url');
}

async function submitHighlightForm(form, endpoint) {
  const button = $('button[type="submit"]', form);
  const oldText = button.innerHTML;
  button.disabled = true;
  button.textContent = 'Ajout à la file d’analyse...';
  try {
    const response = await fetch(endpoint, { method: 'POST', body: new FormData(form) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Erreur HTTP ${response.status}`);
    toast(data.message || 'Analyse ajoutée à la file.');
    form.reset();
    await loadHighlights();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.innerHTML = oldText;
  }
}

async function submitHighlightBatch(form) {
  if (!form.reportValidity()) return;
  const batchButton = $('#highlight-batch-submit');
  const submitButton = $('button[type="submit"]', form);
  const oldBatchText = batchButton.textContent;
  const oldSubmitText = submitButton.textContent;
  batchButton.disabled = true;
  submitButton.disabled = true;
  batchButton.textContent = 'Création du lot…';
  try {
    const response = await fetch('/api/highlights/scan/url/batch', {
      method: 'POST',
      body: new FormData(form),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Erreur HTTP ${response.status}`);
    toast(data.message || `${data.count || 0} tranches ajoutées à la file.`);
    form.reset();
    await loadHighlights();
  } catch (error) {
    toast(error.message, true);
  } finally {
    batchButton.disabled = false;
    submitButton.disabled = false;
    batchButton.textContent = oldBatchText;
    submitButton.textContent = oldSubmitText;
  }
}

async function createShortFromHighlight(button) {
  const scanId = button.dataset.scanId;
  const candidateId = button.dataset.candidateId;
  button.disabled = true;
  button.textContent = 'Envoi...';
  try {
    const result = await api(`/api/highlights/${scanId}/candidates/${candidateId}/create-short`, { method: 'POST' });
    toast(result.message || 'Passage envoyé dans les Shorts.');
    await Promise.all([loadHighlights(), loadJobs(), loadDashboard()]);
  } catch (error) {
    toast(error.message, true);
    button.disabled = false;
    button.textContent = 'Réessayer';
  }
}

async function loadHealth() {
  try {
    const data = await api('/api/health');
    $('#gpu-name').textContent = data.gpu;
    $('#settings-gpu').textContent = data.gpu;
    const checks = [
      ['Serveur local', true, '127.0.0.1'],
      ['FFmpeg / FFprobe', data.ffmpeg && data.ffprobe, data.ffmpeg && data.ffprobe ? 'Détectés' : 'À vérifier'],
      ['Encodage AMD AMF', data.amf, data.amf ? 'H.264 matériel détecté' : 'Fallback CPU disponible'],
      ['Whisper CLI', data.whisper_cli, data.whisper_cli ? 'Installé' : 'À installer'],
      ['Modèle Whisper', data.whisper_model, data.whisper_model ? 'Installé' : 'À télécharger'],
    ];
    $('#system-checks').innerHTML = checks.map(([name, ok, detail]) => `<div class="system-check"><span class="check-dot ${ok ? '' : 'off'}"></span><span>${escapeHtml(name)}</span><span style="margin-left:auto;color:#79818a;font:9px var(--mono)">${escapeHtml(detail)}</span></div>`).join('');
  } catch (error) {
    $('#system-checks').innerHTML = '<div class="system-check"><span class="check-dot off"></span><span>Serveur local indisponible</span></div>';
  }
}

async function loadModels(forceRefresh = false) {
  try {
    const data = await api(`/api/models/status${forceRefresh ? '?refresh=true' : ''}`);
    if (state.whisperGpuProbeRunning) {
      const probeButton = $('#verify-whisper-gpu');
      if (probeButton) { probeButton.disabled = true; probeButton.textContent = 'Test en cours...'; }
      $('#whisper-engine-status').textContent = 'Test Vulkan en cours · chargement du modèle sur le GPU...';
      $('#whisper-engine-details').textContent = 'Le test peut prendre quelques dizaines de secondes. Le moteur actuel reste intact.';
      return;
    }
    const diagnostic = data.whisper_diagnostic || {};
    const engineLine = $('#whisper-engine-status');
    const engineDetails = $('#whisper-engine-details');
    if (diagnostic.available) {
      const backend = diagnostic.vulkan_verified ? 'Vulkan confirmé · modèle alloué sur GPU' : (diagnostic.vulkan_detected ? 'Vulkan détecté' : (diagnostic.device_listing_supported ? 'Aucun périphérique Vulkan listé' : 'Build Vulkan compatible · test GPU à effectuer'));
      engineLine.textContent = `Moteur opérationnel · ${backend}`;
      const gpuDetail = diagnostic.vulkan_verified ? ` · ${diagnostic.gpu_model || 'GPU'} · ${diagnostic.model_buffer_mb || 0} MB alloués · vérifié ${diagnostic.verified_at || ''}` : '';
      engineDetails.textContent = `${diagnostic.path || ''} · ${diagnostic.dtw_supported ? 'timestamps mot à mot DTW disponibles' : 'DTW indisponible, fallback par segment'}${gpuDetail}`;
      $('#verify-whisper-gpu').disabled = !diagnostic.vulkan_probe_available || Boolean(state.whisperGpuProbeRunning);
      $('#verify-whisper-gpu').textContent = state.whisperGpuProbeRunning ? 'Test en cours...' : (diagnostic.vulkan_verified ? 'Re-tester le GPU' : 'Tester le GPU');
    } else {
      engineLine.textContent = 'Moteur absent ou non exécutable';
      engineDetails.textContent = diagnostic.message || 'Installe whisper.cpp puis actualise le diagnostic.';
      $('#verify-whisper-gpu').disabled = true;
      $('#verify-whisper-gpu').textContent = 'Moteur indisponible';
    }

    const whisperLine = $('#whisper-model-status');
    if (data.status === 'downloading') {
      whisperLine.textContent = data.message || 'Téléchargement en cours...';
      $('#download-whisper-model').disabled = true;
      $('#download-whisper-model').textContent = 'Téléchargement...';
      $('#cancel-whisper-download').classList.remove('hidden');
      $('#whisper-progress-wrap').classList.remove('hidden');
      $('#whisper-progress-bar').style.width = `${data.progress || 0}%`;
      $('#whisper-progress-label').textContent = `${data.progress || 0} %`;
      state.modelPoll = setTimeout(loadModels, 1500);
    } else if (data.valid) {
      whisperLine.textContent = `Modèle valide · ${(data.size_bytes / (1024 ** 3)).toFixed(2)} Go · ${diagnostic.available ? 'prêt à transcrire' : 'en attente du moteur'}`;
      $('#download-whisper-model').disabled = true;
      $('#download-whisper-model').textContent = 'Modèle installé';
      $('#cancel-whisper-download').classList.add('hidden');
      $('#whisper-progress-wrap').classList.add('hidden');
    } else {
      whisperLine.textContent = data.status === 'invalid' ? 'Fichier existant invalide ou incomplet. Télécharge-le à nouveau.' : 'Modèle non installé.';
      $('#download-whisper-model').disabled = !diagnostic.available;
      $('#download-whisper-model').textContent = diagnostic.available ? 'Télécharger le modèle (~1,6 Go)' : 'Installer le moteur d’abord';
      $('#cancel-whisper-download').classList.add('hidden');
      $('#whisper-progress-wrap').classList.add('hidden');
    }
    const ollamaLine = $('#ollama-model-status');
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
  } catch (error) {
    $('#whisper-model-status').textContent = error.message;
  }
}

async function verifyOllamaModel(triggerButton = null) {
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

async function loadUpdates() {
  const status = $('#update-check-status');
  const version = $('#update-current-version');
  const installButton = $('#install-update');
  installButton.classList.add('hidden');
  version.textContent = 'Vérification...';
  status.textContent = 'Contact de GitHub pour rechercher la dernière version stable...';
  try {
    const data = await api('/api/updates/check');
    version.textContent = `v${data.current_version}`;
    state.updateTargetVersion = data.update_available ? data.latest_version : '';
    if (data.update_available) {
      status.textContent = `Une nouvelle version est disponible : v${data.latest_version} (actuellement v${data.current_version}).`;
      const notes = $('#update-release-notes');
      notes.textContent = data.release_notes || 'Aucune note de version fournie.';
      notes.classList.remove('hidden');
      installButton.textContent = `Installer la v${data.latest_version}`;
      installButton.classList.remove('hidden');
      installButton.disabled = false;
    } else {
      status.textContent = `Tu utilises la dernière version stable (${data.current_version}).`;
      $('#update-release-notes').classList.add('hidden');
    }
  } catch (error) {
    version.textContent = 'Connexion indisponible';
    status.textContent = error.message.includes('404')
      ? 'Aucune version publiée pour le moment. La première publication sera bientôt disponible.'
      : `Impossible de vérifier les mises à jour : ${error.message}`;
  }
}

async function installUpdate() {
  const button = $('#install-update');
  button.disabled = true;
  button.textContent = 'Préparation...';
  state.updateInProgress = true;
  let restartObserved = false;
  let offlinePolls = 0;
  let pollCount = 0;
  try {
    const result = await api('/api/updates/install', { method: 'POST' });
    toast(result.message || 'La mise à jour va démarrer.');
    $('#update-check-status').textContent = 'Téléchargement et vérification du paquet. GTA Ranked Studio va se fermer puis redémarrer automatiquement.';
    clearInterval(state.updatePoll);
    state.updatePoll = setInterval(async () => {
      pollCount += 1;
      if (pollCount > 120) {
        clearInterval(state.updatePoll);
        state.updateInProgress = false;
        button.disabled = false;
        button.textContent = 'Réessayer';
        $('#update-check-status').textContent = 'Le redémarrage prend plus de temps que prévu. Vérifie la version après avoir relancé l’application.';
        return;
      }
      try {
        const progress = await api('/api/updates/status');
        if (offlinePolls > 0) restartObserved = true;
        $('#update-check-status').textContent = progress.message || 'Mise à jour en cours...';
        if (progress.status === 'error') {
          clearInterval(state.updatePoll);
          state.updateInProgress = false;
          button.disabled = false;
          button.textContent = 'Réessayer';
          toast(progress.message, true);
        } else if (restartObserved && progress.status === 'idle') {
          const check = await api('/api/updates/check');
          if (state.updateTargetVersion && check.current_version === state.updateTargetVersion) {
            clearInterval(state.updatePoll);
            state.updateInProgress = false;
            $('#update-check-status').textContent = `Mise à jour installée avec succès : v${check.current_version}.`;
            toast(`GTA Ranked Studio v${check.current_version} est installé.`);
            window.location.reload();
          } else if (state.updateTargetVersion) {
            clearInterval(state.updatePoll);
            state.updateInProgress = false;
            button.disabled = false;
            button.textContent = 'Réessayer';
            $('#update-check-status').textContent = `Le serveur a redémarré, mais la version détectée est v${check.current_version} au lieu de v${state.updateTargetVersion}.`;
            toast('La mise à jour n’a pas pu être confirmée.', true);
          }
        }
      } catch {
        // La coupure réseau est normale pendant l'arrêt puis le redémarrage du serveur.
        offlinePolls += 1;
        $('#update-check-status').textContent = 'Redémarrage de GTA Ranked Studio en cours...';
      }
    }, 1500);
  } catch (error) {
    state.updateInProgress = false;
    toast(error.message, true);
    button.disabled = false;
    button.textContent = 'Réessayer';
  }
}

function showSourceTab(kind) {
  $$('.source-tab').forEach(tab => tab.classList.toggle('active', tab.dataset.sourceTab === kind));
  $('#upload-form').classList.toggle('hidden', kind !== 'file');
  $('#url-form').classList.toggle('hidden', kind !== 'url');
}

async function submitForm(form, endpoint) {
  const button = $('button[type="submit"]', form);
  const oldText = button.innerHTML;
  button.disabled = true;
  button.textContent = 'Traitement de la demande...';
  try {
    const payload = new FormData(form);
    $$('[data-option-checkbox]', form).forEach(input => payload.set(input.name, input.checked ? 'true' : 'false'));
    const response = await fetch(endpoint, { method: 'POST', body: payload });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Erreur HTTP ${response.status}`);
    toast(data.message || 'Clip ajouté à la file de traitement.');
    form.reset();
    state.file = null;
    const selected = $('#selected-file');
    if (selected) selected.textContent = '';
    await loadJobs();
    await loadDashboard();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.innerHTML = oldText;
  }
}

async function submitShortBatch(form) {
  const rights = form.elements.namedItem('rights_confirmed');
  const urls = $('#short-batch-urls').value.trim();
  if (!rights.checked) { toast('Confirme d’abord que tu disposes des droits nécessaires.', true); return; }
  if (!urls) { toast('Colle au moins une URL Twitch, une par ligne.', true); return; }
  const button = $('#short-batch-submit');
  const feedback = $('#short-batch-feedback');
  const oldText = button.textContent;
  button.disabled = true;
  button.textContent = 'Ajout du lot…';
  feedback.textContent = 'Validation des URLs et création des Shorts…';
  try {
    const payload = new FormData(form);
    payload.delete('url');
    payload.set('urls', urls);
    $('[data-option-checkbox]', form).forEach(input => payload.set(input.name, input.checked ? 'true' : 'false'));
    const response = await fetch('/api/shorts/url/batch', { method: 'POST', body: payload });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Erreur HTTP ${response.status}`);
    const errors = (data.rejected || []).map(item => `• ${item.url} : ${item.reason}`);
    if (data.batch_id) trackShortBatch(data.batch_id);
    feedback.textContent = [data.message || `${data.created_count} Short(s) ajouté(s).`, ...errors].join('\n');
    toast(data.message || 'Lot ajouté à la file.');
    $('#short-batch-urls').value = '';
    await Promise.all([loadJobs(), loadDashboard()]);
  } catch (error) {
    feedback.textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = oldText;
  }
}

async function handleJobAction(button) {
  const id = button.dataset.id;
  const action = button.dataset.action;
  if (action === 'details') {
    const job = await api(`/api/jobs/${id}`);
    toast(job.error || 'Aucune information complémentaire.', true);
    return;
  }
  if (['copy-title', 'copy-description', 'copy-hashtags', 'copy-social'].includes(action)) {
    const job = await api(`/api/jobs/${id}`);
    const metadata = job.metadata || {};
    const values = {
      'copy-title': { text: metadata.title || 'Titre non généré', label: 'Titre copié.' },
      'copy-description': { text: metadata.description || 'Description non générée', label: 'Description copiée.' },
      'copy-hashtags': { text: Array.isArray(metadata.hashtags) ? metadata.hashtags.join(' ') : '', label: 'Hashtags copiés.' },
      'copy-social': { text: `${metadata.title || 'Titre non généré'}\n\n${metadata.description || 'Description non générée'}`, label: 'Texte de publication copié.' },
    };
    const selected = values[action];
    if (!selected.text) { toast('Aucun hashtag disponible pour ce Short.', true); return; }
    try { await navigator.clipboard.writeText(selected.text); toast(selected.label); }
    catch { toast(selected.text); }
    return;
  }
  if (action === 'cancel') {
    button.disabled = true;
    button.textContent = 'Annulation…';
    try {
      const result = await api(`/api/jobs/${id}/cancel`, { method: 'POST' });
      toast(result.message || 'Annulation demandée.');
      await Promise.all([loadJobs(), loadDashboard()]);
    } catch (error) { toast(error.message, true); button.disabled = false; button.textContent = 'Annuler le traitement'; }
    return;
  }
  if (action === 'metadata') {
    const job = await api(`/api/jobs/${id}`);
    const metadata = job.metadata || {};
    const text = [metadata.title || 'Titre non généré', '', metadata.description || 'Description non générée'].join('\n');
    try { await navigator.clipboard.writeText(text); toast('Titre et description copiés dans le presse-papiers.'); }
    catch { toast(text); }
    return;
  }
  const endpoint = action === 'reprocess'
    ? `/api/jobs/${id}/reprocess`
    : `/api/jobs/${id}/${action}`;
  try {
    const result = await api(endpoint, { method: 'POST' });
    toast(action === 'reprocess' ? (result.message || 'Nouveau traitement lancé.') : (action === 'validate' ? 'Short validé.' : 'Short rejeté.'));
    await Promise.all([loadJobs(), loadDashboard(), state.page === 'library' ? loadLibrary() : Promise.resolve()]);
  } catch (error) { toast(error.message, true); }
}

function setFile(file) {
  if (!file) return;
  state.file = file;
  const input = $('#clip-file');
  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  input.files = dataTransfer.files;
  $('#selected-file').textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
}

async function verifyWhisperGpu() {
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

async function startWhisperDownload() {
  try {
    await api('/api/models/whisper/download', { method: 'POST' });
    toast('Téléchargement du modèle Whisper lancé. Il fait environ 1,62 Go.');
    loadModels();
  } catch (error) { toast(error.message, true); }
}

async function cancelWhisperDownload() {
  try {
    await api('/api/models/whisper/cancel', { method: 'POST' });
    toast('Annulation du téléchargement demandée.');
    loadModels();
  } catch (error) { toast(error.message, true); }
}

function updateRangeOutput(input) {
  const output = input.parentElement.querySelector('output');
  if (output) output.textContent = `${input.value} %`;
}

function setupEvents() {
  $$('.nav-item').forEach(item => item.addEventListener('click', () => setPage(item.dataset.page)));
  $$('[data-go]').forEach(item => item.addEventListener('click', () => setPage(item.dataset.go)));
  $$('.source-tab').forEach(tab => tab.addEventListener('click', () => showSourceTab(tab.dataset.sourceTab)));
  $('#browse-file').addEventListener('click', () => $('#clip-file').click());
  $('#dropzone').addEventListener('click', event => { if (event.target.id !== 'browse-file') $('#clip-file').click(); });
  $('#clip-file').addEventListener('change', event => setFile(event.target.files[0]));
  const dropzone = $('#dropzone');
  ['dragenter','dragover'].forEach(name => dropzone.addEventListener(name, event => { event.preventDefault(); dropzone.classList.add('dragover'); }));
  ['dragleave','drop'].forEach(name => dropzone.addEventListener(name, event => { event.preventDefault(); dropzone.classList.remove('dragover'); }));
  dropzone.addEventListener('drop', event => setFile(event.dataTransfer.files[0]));
  $('#upload-form').addEventListener('submit', event => { event.preventDefault(); if (!$('#clip-file').files[0]) { toast('Sélectionne d’abord un fichier vidéo.', true); return; } submitForm(event.currentTarget, '/api/shorts/upload'); });
  $('#url-form').addEventListener('submit', event => { event.preventDefault(); submitForm(event.currentTarget, '/api/shorts/url'); });
  $('#short-batch-submit').addEventListener('click', () => submitShortBatch($('#url-form')));
  $('#short-batch-tracker').addEventListener('click', event => {
    const dismiss = event.target.closest('[data-dismiss-short-batch]');
    if (!dismiss) return;
    const batchId = dismiss.dataset.dismissShortBatch;
    state.shortBatchIds = state.shortBatchIds.filter(id => id !== batchId);
    persistShortBatchIds();
    refreshShortBatchTracker();
  });
  $$('.highlight-source-tab').forEach(tab => tab.addEventListener('click', () => showHighlightSourceTab(tab.dataset.highlightSourceTab)));
  $('#highlight-upload-form').addEventListener('submit', event => { event.preventDefault(); if (!$('#highlight-file').files[0]) { toast('Sélectionne un fichier vidéo.', true); return; } submitHighlightForm(event.currentTarget, '/api/highlights/scan/upload'); });
  $('#highlight-url-form').addEventListener('submit', event => { event.preventDefault(); submitHighlightForm(event.currentTarget, '/api/highlights/scan/url'); });
  $('#highlight-batch-submit').addEventListener('click', () => submitHighlightBatch($('#highlight-url-form')));
  $('#refresh-highlights').addEventListener('click', loadHighlights);
  $('#highlight-scans').addEventListener('click', event => {
    const createButton = event.target.closest('[data-highlight-create]');
    if (createButton) createShortFromHighlight(createButton);
    const batchCancelButton = event.target.closest('[data-highlight-batch-cancel]');
    if (batchCancelButton) cancelHighlightBatch(batchCancelButton);
    const cancelButton = event.target.closest('[data-highlight-cancel]');
    if (cancelButton) cancelHighlightScan(cancelButton);
  });
  $('#bestof-date').addEventListener('change', event => {
    state.bestOfDate = event.target.value;
    state.bestOfSelectedIds = [];
    renderBestOf();
  });
  $('#refresh-bestof').addEventListener('click', loadBestOf);
  $('#bestof-validate').addEventListener('click', validateBestOfSelection);
  $('#bestof-render').addEventListener('click', renderBestOfEpisode);
  $('#bestof-available').addEventListener('click', event => {
    const button = event.target.closest('[data-bestof-add]');
    if (!button) return;
    const id = button.dataset.bestofAdd;
    if (!state.bestOfSelectedIds.includes(id)) state.bestOfSelectedIds.push(id);
    renderBestOf();
  });
  $('#bestof-selected').addEventListener('click', event => {
    const remove = event.target.closest('[data-bestof-remove]');
    if (remove) state.bestOfSelectedIds = state.bestOfSelectedIds.filter(id => id !== remove.dataset.bestofRemove);
    const up = event.target.closest('[data-bestof-up]');
    if (up) {
      const index = Number(up.dataset.bestofUp);
      if (index > 0) [state.bestOfSelectedIds[index - 1], state.bestOfSelectedIds[index]] = [state.bestOfSelectedIds[index], state.bestOfSelectedIds[index - 1]];
    }
    const down = event.target.closest('[data-bestof-down]');
    if (down) {
      const index = Number(down.dataset.bestofDown);
      if (index < state.bestOfSelectedIds.length - 1) [state.bestOfSelectedIds[index + 1], state.bestOfSelectedIds[index]] = [state.bestOfSelectedIds[index], state.bestOfSelectedIds[index + 1]];
    }
    renderBestOf();
  });
  $('#refresh-jobs').addEventListener('click', () => loadJobs());
  $('#refresh-models').addEventListener('click', () => loadModels(true));
  const verifyOllamaButton = $('#verify-ollama');
  if (verifyOllamaButton) verifyOllamaButton.addEventListener('click', verifyOllamaModel);
  const verifyGpuButton = $('#verify-whisper-gpu');
  if (verifyGpuButton) verifyGpuButton.addEventListener('click', verifyWhisperGpu);
  $('#check-updates').addEventListener('click', loadUpdates);
  $('#install-update').addEventListener('click', installUpdate);
  $('#download-whisper-model').addEventListener('click', startWhisperDownload);
  $('#cancel-whisper-download').addEventListener('click', cancelWhisperDownload);
  $$('[data-crop-slider], [data-zoom-slider]').forEach(input => {
    updateRangeOutput(input);
    input.addEventListener('input', () => updateRangeOutput(input));
  });
  document.addEventListener('click', event => { const button = event.target.closest('[data-action]'); if (button) handleJobAction(button); });
}

document.addEventListener('click', event => {
  const ollamaButton = event.target.closest('#verify-ollama, #refresh-models-secondary');
  if (!ollamaButton) return;
  event.preventDefault();
  verifyOllamaModel(ollamaButton);
}, true);

setupEvents();
try {
  const storedBatches = JSON.parse(localStorage.getItem('gta-ranked-short-batches') || '[]');
  state.shortBatchIds = Array.isArray(storedBatches)
    ? storedBatches.filter(id => /^[a-f0-9]{32}$/.test(String(id))).slice(0, 4)
    : [];
} catch { state.shortBatchIds = []; }
loadDashboard();
loadHealth();
setInterval(() => {
  loadDashboard();
  if (state.page === 'shorts') loadJobs();
  if (state.page === 'highlights') loadHighlights();
  if (state.page === 'settings') loadModels();
}, 5000);
