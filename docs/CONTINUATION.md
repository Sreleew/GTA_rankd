# GTA Ranked Studio | Mémo maître de reprise

> Lire ce document en premier dans chaque nouvelle conversation sur le projet. Il décrit l'état réellement livré et la structure source actuelle.

- **Dernière mise à jour :** 26 novembre 2026
- **Version source de référence :** 0.7.8
- **État :** v0.7.8 reste la dernière Release stable. La source applicative est directement dans `app/`. Le nettoyage est proposé dans la PR #6 et le montage intelligent des Shorts est développé sur `feature/smart-short-editing`. Aucune de ces PR n'est fusionnée dans `main`.
- **Dépôt :** https://github.com/Sreleew/GTA_rankd
- **Dernière Release stable :** [v0.7.8](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.8)
- **Archive de provenance :** `archive/releases/v0.7.8/`. C'est une archive historique de la version publiée, pas la source de développement.
- **Source active :** `app/`. Modifier directement les fichiers Python, JavaScript, CSS, HTML, tests et installateur présents dans ce dossier.
- **Mise à jour intégrée :** l'application consulte les Releases GitHub. Le ZIP v0.7.8 et `SHA256SUMS.txt` sont publiés.
- **Tests de la base nettoyée :** Linux 138 réussis, 1 ignoré ; Windows 139 réussis. **Tests du montage intelligent :** Linux 146 réussis, 1 ignoré ; Windows 147 réussis, aucun ignoré. Le rendu FFmpeg réel avec coupe audio/vidéo concaténée est couvert.
- **Workflow de publication v0.7.8 :** https://github.com/Sreleew/GTA_rankd/actions/runs/45714213999.
- **Validation matérielle :** le PC AMD Radeon RX 9060 XT n'a pas encore été validé physiquement pour AMF/Vulkan après mise à jour.

## 1. Objectif du produit

Application Windows locale qui analyse des clips et VOD GTA, repère les passages intéressants, produit des Shorts verticaux soignés et prépare les éléments de publication.

Le projet doit rester local-first, sans abonnement ni API IA payante obligatoire. Les vidéos, médias, transcriptions, rendus et modèles locaux ne doivent pas être envoyés vers un service cloud par le pipeline.

## 2. État actuel et fonctionnalités présentes en v0.7.8

- Import de vidéos locales et d'URLs de clips/VOD Twitch accessibles via yt-dlp.
- Téléchargement de plages horaires avec progression et gestion des erreurs/reprises.
- Analyse audio et transcription Whisper : énergie, densité de parole, expressions de réaction, classement heuristique et sélection manuelle.
- Score distinct d'accroche sur les cinq premières secondes, pondéré à 10 % du score global. Sans Whisper, le score utilise l'énergie audio disponible.
- Contrôle qualité post-export : vérification MP4/FFprobe, dimensions, durée, codec, audio attendu, plages noires, images figées, silences, sous-titres ASS et horodatages de transcription. Les alertes restent non bloquantes.
- Génération de Shorts 1080 × 1920. Le rendu conserve l'image source complète avec fond flouté par défaut. Le zoom dynamique est désactivé par défaut.
- Transcription locale, sous-titres, filtre lexical de réactions et mode expérimental de voix dominante.
- Hooks, titres, descriptions et hashtags générés localement avec Ollama/Qwen facultatif et fallback déterministe. Les hooks génériques d'engagement ne sont pas inventés : sans élément probant dans la transcription, le hook reste vide.
- Miniatures issues d'images réelles du clip, habillage GTA Ranked, signature de chaîne et effets sonores.
- File de traitement, progression FFmpeg, annulation, prévisualisation, validation/rejet et bibliothèque de clips.
- Après validation d'un Short, Prévisualiser, Télécharger, Miniature et Copier le titre, la description, les hashtags et le post restent accessibles.
- Montage intelligent candidat sur `feature/smart-short-editing` : début d'extrait calé sur une frontière de phrase ou une pause naturelle ; suppression de pauses longues uniquement avec timestamps Whisper mot à mot DTW ; sous-titres, pic, zoom, audio et miniature recalés sur la timeline assemblée. La détection des pauses utilise la transcription de toutes les voix, indépendamment du filtre de sous-titres dominant, afin de ne pas couper les dialogues masqués. Les raccords audio des jump cuts reçoivent des micro-fondus de 40 ms aux jonctions ; hook et carte de contexte apparaissent/disparaissent avec un fondu ASS discret. Les URLs de clips Twitch sont traitées comme des passages déjà sélectionnés : l'auto-recadrage est désactivé par défaut, mais le nettoyage conservateur des pauses reste actif. Une option explicite peut réactiver l'auto-recadrage.
- La publication vers YouTube, TikTok et Instagram reste manuelle.

## 3. Architecture technique et environnement

- **Source active :** `app/`, seule racine à modifier pour le code de l'application.
- **Backend :** `app/studio/`, Python 3.11, FastAPI.
- **Interface :** `app/studio/web/static/`, HTML/CSS/JavaScript.
- **Orchestration :** `app/studio/web/worker.py`.
- **Classement des moments forts :** `app/studio/web/highlights.py`.
- **Édition et rendu :** `app/studio/web/short_editor.py`, `short_renderer.py`.
- **Contrôle qualité :** `app/studio/web/export_quality.py`.
- **Transcription et voix :** `transcribe.py`, `speakers.py`.
- **Persistance :** `app/studio/web/store.py`.
- **Mise à jour :** `app/studio/web/updater.py` et `app/installer/`.
- **Tests :** `app/tests/`.
- **Documentation du dépôt :** `docs/`. Les documents nécessaires à l'application sont synchronisés dans `app/docs/` lors de la validation et du packaging.
- **Configuration :** `VERSION.txt` et `app/VERSION.txt` doivent rester synchronisés. Les notes de version racine sont copiées dans `app/` avant la construction du package.
- **Profil matériel :** Windows 10/11, AMD Radeon RX 9060 XT 16 Go, FFmpeg H.264 AMF avec fallback libx264, whisper.cpp Vulkan avec fallback CPU, Ollama/Qwen facultatif.

## 4. Limites connues

1. La détection des moments forts repose sur l'audio et le texte. Elle ne comprend pas encore les événements visuels du gameplay et ne doit pas prétendre détecter avec certitude un kill, crash ou événement HUD.
2. Le filtre lexical ne sépare pas mathématiquement streamer et personnages lorsque leurs voix sont mélangées.
3. La diarisation est expérimentale : en cas d'ambiguïté, préserver les sous-titres plutôt que supprimer la mauvaise voix.
4. La CI Linux et le runner Windows ne valident pas les performances AMF/Vulkan sur la RX 9060 XT physique.
5. Les hooks, coupes de phrases, CTA et compositions doivent encore être jugés sur de vrais Shorts. Éviter les CTA génériques en ouverture.
6. Les compilations Best Of, chapitres et Hall of Fame figurent dans d'anciennes feuilles de route, mais leur état fonctionnel n'a pas été confirmé en v0.7.8.
7. Les alertes qualité ne sont pas des rejets : certaines scènes sombres, statiques ou silencieuses sont intentionnelles.

## 5. Source de référence et état des branches

- **Source de développement :** `app/`. Ne pas décompresser l'archive de release pour développer.
- **PR de nettoyage :** #6, base `main`, branche `chore/clean-source-layout`, ouverte et validée Linux/Windows : https://github.com/Sreleew/GTA_rankd/pull/6.
- **Branche fonctionnalité :** `feature/smart-short-editing`, basée sur `chore/clean-source-layout`. Elle contient le montage intelligent de Shorts et ses tests. Ne pas la rebaser directement sur `main` tant que la PR #6 n'est pas intégrée.
- **PR montage intelligent :** #7, base `chore/clean-source-layout`, branche `feature/smart-short-editing`, un seul commit fonctionnel, ouverte et validée Linux/Windows : https://github.com/Sreleew/GTA_rankd/pull/7.
- **Note de réconciliation Git :** un oubli de paramètre `branch` lors d'un ajout de test a créé par erreur le commit `8380de9989973f1ae86f4a30bea63ef3d44833b6` sur `main`. Il ajoute uniquement `app/tests/test_short_editor.py` isolé, sans code applicatif ni changement de Release. La branche de nettoyage a intégré cet historique comme deuxième parent tout en conservant le fichier canonique de l'application. La PR #6 remplace donc le fichier isolé par la version correcte au sein de `app/`. Tant que la PR #6 n'est pas fusionnée, le fichier isolé reste présent sur `main`. Ne pas ajouter d'autres commits directs sur `main`.
- **Archive de provenance v0.7.8 :** `archive/releases/v0.7.8/`. La conserver intacte.
- **Fichiers de contrôle :** manifeste et SHA-256 de l'archive de provenance.
- **Anciennes chaînes de correctifs :** retirées de la racine active. Les tags et l'historique Git conservent les commits historiques ; ne pas réintroduire l'ancienne chaîne de reconstruction.
- **Ancienne tentative v0.8.0 :** les fragments incomplets ont été retirés de la racine active. Ne pas restaurer ni reconstruire cette tentative par supposition.
- **CI Linux :** `Audit GTA Ranked Studio application`, teste directement `app/`.
- **CI Windows :** `Windows runtime validation`, teste directement `app/`, PowerShell et le ZIP.
- **Publication :** `Build and publish GTA Ranked Studio`, construit le ZIP à partir de `app/` ; aucune extraction d'archive ni application de hotfix.

## 6. Fichiers importants

- `app/studio/` : code applicatif.
- `app/installer/` : installateur et constructeur de package.
- `app/tests/` : tests de régression.
- `app/config.yaml.default` : configuration initiale, jamais une configuration personnelle.
- `VERSION.txt` : numéro de release racine, à synchroniser avec `app/VERSION.txt`.
- `NOTES-vX.Y.Z.txt` : notes racine, copiées dans `app/` au moment de la validation et du packaging.
- `docs/CONTINUATION.md` : ce mémo maître.
- `docs/WORKING-AGREEMENT.md` : méthode de travail.
- `docs/RELEASE_PROCESS.md` : procédure de test et de publication.
- `docs/UPDATES.md` : guide utilisateur et historique.
- `docs/WINDOWS-HARDWARE-VALIDATION.md` : protocole de validation sur le PC AMD.
- `tools/check_project_memory.py` : copie de référence du vérificateur de mémoire, synchronisée dans `app/tools/` avant packaging.
- `archive/releases/v0.7.8/` : archive historique figée, pas une base de développement.
- `.github/workflows/audit-source.yml` : tests Linux et packaging à partir de `app/`.
- `.github/workflows/windows-smoke.yml` : tests Windows et packaging à partir de `app/`.
- `.github/workflows/release.yml` : publication stable à partir de `app/`.
- `.release-approval` : autorisation explicite d'une version stable sur `main`.

Ne jamais publier `config.yaml`, vidéos, rendus personnels, bases SQLite, modèles IA téléchargés, environnements virtuels, logs, tokens ou secrets. Le processus de mise à jour doit préserver les configurations et données utilisateur.

## 7. Commandes de contrôle

Depuis PowerShell, à la racine du dépôt :

```powershell
Set-Location app
py -3.11 -m pip install -r requirements.txt
python tools/check_project_memory.py
python -m pytest -q
node --check studio/web/static/app.js
python installer/build_release_package.py --version 0.7.8 --output-dir dist
```

Pour un test isolé, créer `config.yaml` depuis `config.yaml.default` uniquement si aucun fichier de configuration personnel n'existe. Ne jamais écraser un `config.yaml` existant.

## 8. Règles de travail pour toute nouvelle conversation

- Lire ce mémo puis `docs/WORKING-AGREEMENT.md`.
- Modifier le code directement sous `app/`. Ne pas modifier une archive compressée, une ancienne branche ou un correctif historique.
- Lire uniquement les fichiers et tests nécessaires à la tâche.
- Regrouper les modifications liées dans un commit logique.
- Lancer les tests ciblés pendant le développement ; exécuter Linux et Windows avant une modification transversale, un packaging ou une installation.
- Maintenir synchronisés `VERSION.txt` et `app/VERSION.txt`, ainsi que les notes de release racine et `app/`.
- Les workflows synchronisent les documents racine dans le package applicatif avant de tester et publier.
- Préserver la configuration, les bases, projets, médias, exports et modèles locaux.
- Ne jamais toucher à `main`, fusionner, publier une Release ou supprimer des données sans instruction explicite.
- Ne jamais présenter un test prévu comme réussi. Distinguer code modifié, tests CI et validation matérielle réelle.

## 9. Prochaines étapes priorisées

1. Finaliser la PR #6 qui établit `app/` comme source directe, sans la fusionner sans instruction explicite.
2. Examiner plusieurs Shorts GTA réels pour vérifier qu'aucune réaction n'est amputée et ajuster les seuils à partir des résultats vidéo.
3. Améliorer le hook d'ouverture et la hiérarchie hook/contexte/sous-titres, sans CTA générique avant que l'action démarre.
4. Tester le cycle Short complet sur la RX 9060 XT : AMF, Whisper Vulkan, Ollama/Qwen, prévisualisation, validation et persistance.
5. Développer ensuite la détection visuelle GTA (HUD, kill feed, changements de scène) et fusionner ses signaux au classement audio/texte.
6. Continuer à modifier directement `app/`, avec tests ciblés puis Linux/Windows sur les changements transversaux.

## 10. Message de reprise prêt à copier

> Nous reprenons GTA Ranked Studio. Lis `docs/CONTINUATION.md` puis `docs/WORKING-AGREEMENT.md`. La source active est directement dans `app/`. La v0.7.8 reste la dernière Release stable : https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.8. La PR #6 (`chore/clean-source-layout`) est la base propre à intégrer en premier. La branche `feature/smart-short-editing` ajoute des coupes conservatrices des pauses longues avec timestamps Whisper `word_dtw`, synchronisées avec audio, vidéo, sous-titres et miniature. CI : Linux 139 pass / 1 skipped ; Windows 140 pass. Vérifier plusieurs vrais Shorts avant d'assouplir les seuils. La RX 9060 XT n'a pas encore été validée physiquement pour AMF/Vulkan. Préserve les données locales, modifie uniquement `app/` et ne fusionne/publie pas sans instruction explicite.
