# GTA Ranked Studio | Mémo maître de reprise

> À lire en premier dans toute nouvelle conversation sur le projet. Ce document est la mémoire durable de GTA Ranked Studio et doit être actualisé à chaque mise à jour.

- **Dernière mise à jour :** 25 novembre 2026
- **Version source de référence :** 0.7.8
- **État :** v0.7.8 publiée en Release stable publique le 25 novembre 2026. Le bouton intégré de mise à jour peut désormais la détecter depuis GitHub Releases.
- **Dépôt :** https://github.com/Sreleew/GTA_rankd
- **Branche fonctionnelle intégrée :** `feature/v0.7.8-shorts-retention` (PR #2 fusionnée). Les PR #3, #4 et #5 ont intégré le flux de publication, le pin Python 3.11 et la normalisation des dates ZIP.
- **Dernière Release stable publique :** [v0.7.8](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.8). Asset de mise à jour : `GTA-Ranked-Studio-v0.7.8.zip` + `SHA256SUMS.txt`.
- **État du dépôt `main` :** `VERSION.txt` indique `0.7.8`. Le workflow stable publie uniquement après changement explicite de `.release-approval`.
- **Dernier audit Linux v0.7.8 :** 138 tests réussis, 1 ignoré (PowerShell non disponible sous Linux) : https://github.com/Sreleew/GTA_rankd/actions/runs/45713882573.
- **Validation Windows CI v0.7.8 :** 139 tests réussis, aucun ignoré, PowerShell et ZIP Windows validés : https://github.com/Sreleew/GTA_rankd/actions/runs/45713882963. Cela ne valide pas le GPU AMD physique.
- **Source canonique :** `source/canonical-v0.7.8/`. `MANIFEST.json` et `SHA256SUMS.txt` font foi pour les fichiers et empreintes courants ; ne pas recopier un SHA d'archive ou un HEAD dans ce mémo, car ils changent à chaque reconstruction.
- **Comparaison des sources :** `docs/source-audit-v0.7.8-v0.8.0-2026-11-25.md`

## 1. Objectif du produit

Application Windows locale qui analyse des clips et VOD GTA, repère les passages intéressants, produit des Shorts verticaux soignés et prépare les éléments de publication. La cible à terme est un flux largement automatisé : importer une VOD, classer les moments forts, proposer une sélection éditoriale, produire les Shorts, puis conserver vidéos, miniatures et métadonnées dans une bibliothèque exploitable.

Le projet doit rester local-first, sans abonnement ni API IA payante obligatoire. Les vidéos et médias ne doivent pas être envoyés vers un service cloud par le pipeline de traitement.

## 2. État actuel et fonctionnalités présentes en v0.7.8

- Import de vidéos locales et d'URLs de clips/VOD Twitch accessibles via yt-dlp.
- Téléchargement de plages horaires avec progression et gestion des erreurs/reprises.
- Analyse audio + transcription Whisper : énergie, densité de parole, expressions de réaction, classement heuristique et sélection manuelle des passages.
- Score distinct d'accroche sur les cinq premières secondes, pondéré à 10 % du score global et affiché dans chaque carte de candidat. Sans Whisper, le score se replie sur l'énergie audio disponible.
- Contrôle qualité post-export : vérification MP4/FFprobe, dimensions, durée, codec, audio attendu, détection de plages noires, images figées et silences prolongés, plus cohérence des sous-titres ASS et horodatages de transcription. Le rapport est visible sur la carte Short et ses alertes sont non bloquantes.
- Génération de Shorts 1080 × 1920. Le rendu par défaut conserve l'image source complète, centrée, avec fond flouté. Le zoom dynamique est désactivé par défaut.
- Transcription locale, sous-titres, filtre lexical de réactions et mode expérimental de voix dominante.
- Hooks, titres, descriptions et hashtags générés localement avec Ollama/Qwen facultatif et fallback déterministe.
- Miniatures composées depuis de vraies images du clip, habillage GTA Ranked, signature de chaîne et effets sonores.
- File de traitement, progression FFmpeg, annulation, prévisualisation, validation/rejet et bibliothèque de clips.
- **Correctif v0.7.8 :** après validation d'un Short, Prévisualiser, Télécharger, Miniature, Copier le titre, Copier la description, Copier les hashtags et Copier le post restent accessibles. La validation ne doit pas supprimer les métadonnées ni les fichiers associés.
- L'application prépare les contenus de publication mais ne publie pas automatiquement vers YouTube, TikTok ou Instagram.

## 3. Architecture technique et environnement

- Backend : Python 3.11, FastAPI, application web servie localement.
- Frontend : HTML/CSS/JavaScript dans `studio/web/static/`.
- Orchestration : `studio/web/worker.py`.
- Analyse des moments forts : `studio/web/highlights.py`.
- Rendu : `studio/web/short_renderer.py`, édition : `studio/web/short_editor.py`.
- Contrôle qualité post-export : `studio/web/export_quality.py`.
- Transcription : `studio/web/transcribe.py`, voix : `studio/web/speakers.py`.
- Métadonnées : `studio/web/metadata.py` et `prompts/`.
- Persistance : `studio/web/store.py`.
- Mise à jour : `studio/web/updater.py` et `installer/`.
- Profil matériel cible : Windows 10/11, AMD Radeon RX 9060 XT 16 Go, FFmpeg H.264 AMF avec fallback libx264, whisper.cpp Vulkan avec fallback CPU, Ollama/Qwen local facultatif.

**Débit à ne pas confondre :** la source v0.7.8 actuellement reconstruite définit `encoding.amf_bitrate: 12M`. Un ancien mémo mentionnait 9 Mbit/s, mais cette valeur n'est pas celle de la configuration reconstruite. Ne change pas le débit sans mesure sur le PC Windows réel.

## 4. Limites connues

1. La détection des moments forts est audio/texte. Elle ne comprend pas encore les événements visuels du gameplay et ne doit pas prétendre détecter avec certitude un kill, crash ou événement HUD.
2. Le filtre lexical ne sépare pas mathématiquement streamer et personnages lorsque leurs voix sont mélangées.
3. La diarisation est expérimentale : en cas d'ambiguïté, mieux vaut préserver les sous-titres que supprimer la mauvaise voix.
4. La CI Linux ne valide pas les performances réelles AMF/Vulkan de la RX 9060 XT sous Windows.
5. Les hooks, coupes de phrases, CTA et compositions doivent encore être jugés sur des Shorts réels. Éviter les CTA génériques en ouverture.
6. Les compilations Best Of, chapitres et Hall of Fame figurent dans l'ancienne roadmap mais leur état fonctionnel n'a pas été confirmé dans la source v0.7.8.
7. La publication sur les plateformes reste manuelle.
8. Les alertes du contrôle qualité ne sont pas des rejets : certaines scènes sombres, statiques ou silencieuses peuvent être intentionnelles. Le rapport doit guider une revue, pas supprimer ou bloquer automatiquement un export.

## 5. Source de référence et état des branches

### Candidat v0.7.8

La source canonique initiale v0.7.8 a été produite à partir du snapshot v0.4.0 et des correctifs cumulatifs jusqu'à v0.7.8. Les audits suivants valident et extraient désormais directement cette source canonique, sans rejouer la chaîne historique. Dernière validation GitHub Actions Linux connue :
- reconstruction réussie ;
- **128 tests réussis, 1 ignoré** ;
- contrôle syntaxique JavaScript réussi ;
- paquet Windows candidat construit et uploadé.
- Le SHA-256 du paquet est consigné dans le fichier `SHA256SUMS.txt` de chaque artifact ; utiliser le checksum associé au run concerné plutôt qu'un hash recopié dans ce mémo.

C'est un candidat validé par CI, pas une Release stable et pas une validation GPU sur Windows réel.

### Snapshot canonique v0.7.8

- Source canonique reconstruite, déterministe et commitée dans `source/canonical-v0.7.8/`.
- Archive : `GTA-Ranked-Studio-source-v0.7.8.tar.xz`.
- Fichiers de contrôle : `MANIFEST.json` et `SHA256SUMS.txt`.
- Le manifeste inventorie les fichiers et leurs SHA-256 individuels. Le dernier snapshot contrôlé contient 106 fichiers.
- Le mémo, son vérificateur et le changelog complet sont inclus dans l'archive et dans le ZIP Windows.
- Aucun `config.yaml`, média, base SQLite, modèle local, log ou bytecode Python n'est inclus.
- Ne jamais recopier le SHA-256 de l'archive dans ce mémo. `MANIFEST.json` et `SHA256SUMS.txt` dans le dossier canonique sont les seules sources de vérité, car le snapshot change après une mise à jour des documents.
- Dernier workflow Linux validé : https://github.com/Sreleew/GTA_rankd/actions/runs/45689877019.
- Dernier workflow Windows validé : https://github.com/Sreleew/GTA_rankd/actions/runs/45688998298.

Le workflow de release lit l'archive canonique, vérifie le checksum et l'intégrité de chaque fichier du manifeste, puis lance les tests et le packaging. Il ne rejoue plus la chaîne de patchs depuis v0.4.0. La voie stable se déclenche uniquement quand `.release-approval` est créé ou modifié sur `main` : le numéro doit correspondre à `VERSION.txt`, le tag ne doit pas exister, et les tests/contrôles du ZIP sont rejoués avant publication publique. La voie `workflow_dispatch` exige une confirmation et reste limitée à une Release brouillon.


### Intégration des branches et publication v0.7.8

- PR #2 : intégration des fonctionnalités applicatives v0.7.8 : https://github.com/Sreleew/GTA_rankd/pull/2.
- PR #3 : déclenchement de publication explicite et validations PR Linux/Windows : https://github.com/Sreleew/GTA_rankd/pull/3.
- PR #4 : pin du workflow de publication sur Python 3.11 : https://github.com/Sreleew/GTA_rankd/pull/4.
- PR #5 : normalisation à 1980-01-01 UTC des dates de la copie extraite avant packaging ZIP, tout en gardant les timestamps du tar canonique à 1970 pour sa reproductibilité : https://github.com/Sreleew/GTA_rankd/pull/5.
- Release stable publiée et vérifiée : https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.8.
- Workflow de publication réussi : https://github.com/Sreleew/GTA_rankd/actions/runs/45714213999.
- Audit Linux : 138 passed, 1 skipped. CI Windows : 139 passed. Le package contient le ZIP et le checksum, sans les données locales.

### Snapshot v0.8.0 bloqué

Le dépôt contient 17 fragments `source/v0.8.0-source.part000.b64` à `part016.b64`. Les segments `part003` et `part004` sont strictement identiques : seulement 16 contenus uniques. L'archive reconstruite est invalide. L'historique Git consulté ne fournit pas d'ancienne version de `part004`.

**Ne pas utiliser, fusionner ou réparer par supposition le snapshot v0.8.0 actuel.** Restaurer le véritable segment depuis la source d'origine ou régénérer l'archive depuis un arbre source complet et vérifié.

Le snapshot v0.7.8 canonique est maintenant créé, vérifié et enregistré dans Git. Les futures versions doivent partir de cette base plutôt que rejouer les anciens correctifs depuis v0.4.0.

## 6. Fichiers importants

- `VERSION.txt` : numéro de version.
- `NOTES-vX.Y.Z.txt` : notes de chaque mise à jour.
- `README.md` : documentation produit.
- `docs/UPDATES.md` : guide utilisateur et historique des mises à jour.
- `docs/CONTINUATION.md` : ce mémo maître à lire en premier.
- `docs/WORKING-AGREEMENT.md` : méthode de travail efficace, règles de tests et format de compte rendu à appliquer dans chaque conversation.
- `docs/UPDATES.md` : guide de mise à jour et historique complet des versions.
- `source/canonical-v0.7.8/` : archive source de référence, manifeste et SHA-256.
- `source/apply-hotfix-v0.7.8-retention.py` et `source/apply-hotfix-v0.7.8-export-qc.py` : correctifs reproductibles appliqués après extraction de la source canonique.
- Le patch QC est idempotent : il compare les SHA-256 des six fichiers. Si les six correspondent déjà à la version attendue, il ne les réécrit pas ; un état partiel est refusé.
- `source/export-quality-patch-v0.7.8.diff.xz.b64` : patch compressé et contrôlé par SHA-256 qui ajoute le contrôle qualité post-export.
- `tools/check_project_memory.py` : vérifie l'alignement du mémo avec la version et les notes.
- `.github/workflows/audit-source.yml` : vérifie et extrait la source canonique, injecte les documents courants, teste, puis régénère le snapshot sans se relancer sur le commit de l'archive.
- `.github/workflows/windows-smoke.yml` : teste la source canonique sur un runner Windows, exécute les tests PowerShell et vérifie le paquet de mise à jour.
- `.github/workflows/release.yml` : prépare une Release brouillon depuis `main` après déclenchement manuel et confirmation.
- `docs/RELEASE_PROCESS.md` : procédure contrôlée d'intégration et de publication.
- `docs/WINDOWS-HARDWARE-VALIDATION.md` : protocole de test sur le PC AMD cible.
- `installer/build_release_package.py` : crée le ZIP de mise à jour.
- `studio/web/` : application et interface.
- `tests/` : tests de régression.

Ne jamais publier `config.yaml`, vidéos, rendus personnels, bases SQLite, modèles IA téléchargés, environnements virtuels, logs, tokens ou secrets. Les mises à jour doivent préserver les configurations et données utilisateur.

## 7. Commandes de contrôle

Depuis la racine source, dans PowerShell :

```powershell
Copy-Item config.yaml.default config.yaml
python -m pip install -r requirements.txt
python tools/check_project_memory.py
python -m pytest -q
node --check studio/web/static/app.js
python installer/build_release_package.py --version 0.7.8 --output-dir dist
```

La copie du fichier de configuration n'est valable que pour une installation neuve ou un environnement de test isolé. Ne jamais écraser le `config.yaml` existant de l'utilisateur.

## 8. Règles de travail pour toute nouvelle conversation

- Travailler directement depuis le dépôt GitHub `Sreleew/GTA_rankd` quand son accès est disponible. Ne pas redemander le ZIP à l'utilisateur.
- Lire et appliquer `docs/WORKING-AGREEMENT.md` : limiter l'inspection au périmètre utile, passer rapidement à l'action, regrouper les changements liés dans un commit logique, tester en fonction du risque et donner des comptes rendus concrets.
- Lire ce mémo, puis vérifier le HEAD des branches, les commits, les Releases et les workflows avant toute modification.
- Ne pas confondre branche, candidat CI, artifact et Release stable.
- Modifier une branche de travail, tester, conserver des commits explicites, ne pas publier une version non validée.
- Préserver config, bases, projets, exports, médias et modèles locaux.
- À chaque version, mettre à jour ensemble `VERSION.txt`, `NOTES-vX.Y.Z.txt`, `README.md`, `docs/UPDATES.md` et ce mémo.
- Le contrôle CI doit échouer si la version du mémo ne correspond pas à `VERSION.txt`, si la date ou des sections essentielles manquent, ou si les notes de version sont absentes.
- Le workflow de release doit partir de `source/canonical-vX.Y.Z/`, vérifier son `SHA256SUMS.txt` et confirmer que le paquet Windows contient le mémo, le vérificateur et le changelog.
- Le workflow de publication a deux voies : `.release-approval` sur `main` pour une publication stable explicitement autorisée, et `workflow_dispatch` avec confirmation pour une Release brouillon.
- Le workflow d'audit ne surveille pas son propre dossier de snapshot canonique, ce qui évite une boucle de reconstruction sur le commit du bot.
- Les runners Windows valident le parseur PowerShell et le package, mais ne remplacent pas les essais GPU sur la RX 9060 XT réelle.
- À chaque mise à jour, ajouter au mémo les fonctionnalités livrées, les tests et résultats, la branche/commit, le statut CI/Release, les limites et les prochaines tâches.
- Toujours distinguer « implémenté », « testé en CI », « testé sous Windows réel » et « publié ».

- Score distinct d'accroche sur les cinq premières secondes, pondéré à 10 % du score global et affiché dans chaque carte de candidat.
- Sans transcription Whisper, le scan peut classer les candidats sur l'énergie audio seule au lieu de plafonner artificiellement le score disponible.

Limite du score d'accroche : il s'agit d'un indicateur heuristique audio/texte sur les cinq premières secondes, pas d'une mesure réelle de rétention YouTube/TikTok ni d'une compréhension visuelle du gameplay.

## 9. Prochaines étapes priorisées

1. Calibrer les seuils du contrôle qualité sur plusieurs vrais Shorts GTA, en mesurant les faux positifs sur des scènes sombres, pauses voulues et séquences sans musique.
2. Exécuter `docs/WINDOWS-HARDWARE-VALIDATION.md` sur le PC cible : AMF, Whisper Vulkan, Qwen, cycle Short complet, rapport QC et persistance après mise à jour.
3. Améliorer les coupes naturelles et la construction des hooks à partir des limites de phrases, sans CTA générique à l'ouverture.
4. Développer le classement visuel des événements GTA (HUD, kill feed et changements de scène) avec un score explicable et une validation humaine.
5. Sur le PC cible, ouvrir **Paramètres > Mises à jour**, rechercher v0.7.8, installer et vérifier le redémarrage de l'application ainsi que la conservation des réglages, projets, bases et exports.
6. Exécuter `docs/WINDOWS-HARDWARE-VALIDATION.md` sur la RX 9060 XT : AMF, Whisper Vulkan, Ollama/Qwen et cycle Short complet. La CI Windows ne remplace pas cette validation GPU physique.
7. Continuer les améliorations de montage Shorts et de détection visuelle GTA sans modifier le tag v0.7.8 déjà publié.
8. Restaurer le vrai fragment `part004` ou reconstruire la source v0.8.0 depuis un arbre complet ; ne pas utiliser les fragments actuels.
9. À chaque lot, actualiser le mémo, les notes, le README et le changelog, puis laisser la CI reconstruire et contrôler le snapshot canonique.

## 10. Message de reprise prêt à copier

> Nous reprenons GTA Ranked Studio depuis `main`. Lis `docs/CONTINUATION.md` puis `docs/WORKING-AGREEMENT.md`. La v0.7.8 est une Release stable publiée : https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.8. L'utilisateur peut l'installer depuis Paramètres > Mises à jour. Le ZIP de Release est `GTA-Ranked-Studio-v0.7.8.zip` et le checksum `SHA256SUMS.txt`. L'audit Linux a réussi avec 138 tests, 1 ignoré ; Windows avec 139 tests, aucun ignoré. Le workflow de publication a réussi : run 45714213999. Le contrôle qualité post-export est intégré et ses alertes sont non bloquantes. La RX 9060 XT n'a pas encore été validée physiquement pour AMF/Vulkan. La source canonique est dans `source/canonical-v0.7.8/`. Le snapshot v0.8.0 actuel est corrompu car `part003` et `part004` sont identiques : ne l'utilise pas. Continue directement depuis GitHub, préserve les données locales, lis le mémo et l'accord de travail avant de modifier, fais des commits groupés et valide les PR sous Linux et Windows avant fusion. Ne réutilise pas le tag v0.7.8 pour de nouveaux changements.
