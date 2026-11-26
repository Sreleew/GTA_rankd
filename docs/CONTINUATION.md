# GTA Ranked Studio | Mémo maître de reprise

> Lire ce document en premier dans chaque nouvelle conversation sur le projet. Il décrit l'état réellement livré et la structure source actuelle.

- **Dernière mise à jour :** 26 novembre 2026
- **Version source de référence :** 0.7.9
- **État :** v0.7.9 est la Release stable publiée depuis `main`. La source applicative est maintenue directement dans `app/`.
- **Dépôt :** https://github.com/Sreleew/GTA_rankd
- **Dernière Release stable :** [v0.7.9](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.9)
- **Archive de provenance :** `archive/releases/v0.7.8/`. C'est une archive historique de la version publiée, pas la source de développement.
- **Source active :** `app/`. Modifier directement les fichiers Python, JavaScript, CSS, HTML, tests et installateur présents dans ce dossier.
- **Mise à jour intégrée :** l'application consulte les Releases GitHub. Le ZIP v0.7.9 et `SHA256SUMS.txt` sont publiés par le workflow de release.
- **Tests v0.7.9 :** Linux 144 réussis, 1 ignoré (PowerShell non disponible sous Linux) ; Windows 145 réussis.
- **PR de livraison :** [#8](https://github.com/Sreleew/GTA_rankd/pull/8), fusionnée dans `main`.
- **Workflow de publication v0.7.9 :** https://github.com/Sreleew/GTA_rankd/actions/runs/45793843538.
- **Validation matérielle :** le PC AMD Radeon RX 9060 XT n'a pas encore été validé physiquement pour AMF/Vulkan après mise à jour.

## 1. Objectif du produit

Application Windows locale qui analyse des clips et VOD GTA, repère les passages intéressants, produit des Shorts verticaux soignés et prépare les éléments de publication.

Le projet doit rester local-first, sans abonnement ni API IA payante obligatoire. Les vidéos, médias, transcriptions, rendus et modèles locaux ne doivent pas être envoyés vers un service cloud par le pipeline.

## 2. État actuel et fonctionnalités présentes

- Import de vidéos locales et d'URLs de clips/VOD Twitch accessibles via yt-dlp.
- Téléchargement de plages horaires avec progression et gestion des erreurs/reprises.
- Analyse audio et transcription Whisper : énergie, densité de parole, expressions de réaction, classement heuristique et sélection manuelle.
- Score distinct d'accroche sur les cinq premières secondes, pondéré à 10 % du score global. Sans Whisper, le score utilise l'énergie audio disponible.
- Contrôle qualité post-export : vérification MP4/FFprobe, dimensions, durée, codec, audio attendu, plages noires, images figées, silences, sous-titres ASS et horodatages de transcription. Les alertes restent non bloquantes.
- Génération de Shorts 1080 × 1920. Le rendu conserve l'image source complète avec fond flouté par défaut. Le zoom dynamique est désactivé par défaut.
- Transcription locale, sous-titres, filtre lexical de réactions et mode expérimental de voix dominante.
- Hooks, titres, descriptions et hashtags générés localement avec Ollama/Qwen facultatif et fallback déterministe. Les fragments ASR incomplets ne sont pas utilisés comme citations ; en l'absence de phrase ou de contexte fiable, le fallback reste neutre.
- Miniatures issues d'images réelles du clip, avec une composition verticale 1080 × 1920 plus épurée, gameplay mis au premier plan, fond assombri, titre court et branding discret.
- File de traitement, progression FFmpeg, annulation, prévisualisation, validation/rejet et bibliothèque de clips.
- Après validation d'un Short, Prévisualiser, Télécharger, Miniature et Copier le titre, la description, les hashtags et le post restent accessibles.
- Le montage intelligent de Shorts est intégré : les clips Twitch déjà sélectionnés sont préservés, les pauses longues ne sont retirées qu'avec des timestamps mot à mot DTW fiables, et les sous-titres, le pic audio, le zoom, l'audio et la miniature sont recalés sur la timeline assemblée.
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
6. Les compilations Best Of, chapitres et Hall of Fame figurent dans d'anciennes feuilles de route, mais leur état fonctionnel n'a pas été confirmé en v0.7.9.
7. Les alertes qualité ne sont pas des rejets : certaines scènes sombres, statiques ou silencieuses sont intentionnelles.

## 5. Source de référence et état des branches

- **Base propre intégrée :** PR #6 fusionnée dans `main`.
- **Montage intelligent intégré :** PR #7 fusionnée dans `main`.
- **Refonte créative intégrée :** PR #8 fusionnée dans `main`, version v0.7.9.

- **Source de développement :** `app/`. Ne pas décompresser l'archive de release pour développer.
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
python installer/build_release_package.py --version 0.7.9 --output-dir dist
```

Pour un test isolé, créer `config.yaml` depuis `config.yaml.default` uniquement si aucun fichier de configuration personnel n'existe. Ne jamais écraser un `config.yaml` existant.

## 8. Règles de travail pour toute nouvelle conversation

- Lire ce mémo puis `docs/WORKING-AGREEMENT.md`.
- Modifier le code directement sous `app/`. Ne pas modifier une archive compressée, une ancienne branche ou un correctif historique.
- Lire uniquement les fichiers et tests nécessaires à la tâche.
- Regrouper les modifications liées dans un commit logique.
- Lancer les tests ciblés pendant le développement ; exécuter Linux et Windows avant une modification transversale, un packaging ou une installation.
- Maintenir synchronisés `VERSION.txt` et `app/VERSION.txt`, ainsi que les notes de release racine et `app/`.
- **Obligation prioritaire :** mettre à jour `docs/CONTINUATION.md` à chaque lot de modifications, avant le compte rendu final. Y consigner brièvement les remarques/décisions de l'utilisateur, la méthode de travail, les fichiers ou fonctionnalités modifiés, les commits/PR/releases, les tests et les limites. Garder le document concis, factuel et à jour.
- Les workflows synchronisent les documents racine dans le package applicatif avant de tester et publier.
- Préserver la configuration, les bases, projets, médias, exports et modèles locaux.
- L'utilisateur a demandé que toute modification demandée soit menée jusqu'à l'intégration et la publication stable, sans s'arrêter à une branche ou une PR. En cas d'échec CI ou de blocage technique, corriger ou expliquer le blocage.
- Ne jamais présenter un test prévu comme réussi. Distinguer code modifié, tests CI et validation matérielle réelle.

## 9. Préférences utilisateur et méthode de collaboration

- **Travailler directement dans GitHub.** Le dépôt est la source de vérité : ne pas demander un ZIP ou une copie locale si les fichiers sont accessibles dans le dépôt.
- **Livrer du propre et du fonctionnel.** Privilégier une base saine, un périmètre ciblé, des tests utiles et une vraie vérification des régressions. Ne pas sacrifier la qualité pour aller plus vite.
- **Éviter les lenteurs inutiles.** Ne pas refaire de longs audits ni relire tout l'historique à chaque demande. Lire le mémo, le HEAD, les contrôles utiles et seulement les fichiers concernés.
- **Aller jusqu'au résultat utilisable.** Pour une modification demandée, travailler sur une branche, tester, fusionner dans `main` et publier une Release stable lorsque les validations passent. Si un contrôle bloque, le corriger ou expliquer précisément pourquoi la livraison est arrêtée.
- **Priorité produit actuelle :** le parcours Twitch clip → Short prêt à publier. L'utilisateur fournit principalement une URL de clip Twitch ; améliorer la sélection/montage, le rythme, les sous-titres, le hook, la miniature, le titre et la description. Ne pas disperser le travail sur des fonctions secondaires sans demande.
- **Direction des miniatures :** rendu propre, esthétique, lisible et immédiatement compréhensible, construit autour d'une vraie image du clip. Le visuel doit donner envie de cliquer sans surcharge, faux événement ou texte tronqué.
- **Évaluer sur des exemples réels.** Quand l'utilisateur envoie un clip ou un Short généré, examiner concrètement le rendu avant de décider des corrections. Distinguer les observations réelles des hypothèses.
- **Garder les contrôles accessibles après validation.** Ne pas retirer les actions de prévisualisation, téléchargement, miniature et copie du titre/description/hashtags après validation d'un Short.
- **Communication :** être direct et concis, donner les résultats concrets et signaler clairement ce qui reste non testé. Une seule prochaine action prioritaire dans le bilan.

## 10. Journal de travail récent

- **v0.7.9 publiée :** refonte des miniatures verticales, sélection de phrases plus complètes pour les hooks/titres, garde-fous contre les événements inventés dans les métadonnées, raccords audio plus doux et conservation des clips Twitch sélectionnés.
- **Intégration :** PR #8 fusionnée dans `main`, Release stable [v0.7.9](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.9).
- **Validation :** Linux 144 réussis + 1 ignoré ; Windows 145 réussis. ZIP et SHA-256 publiés.
- **À vérifier sur le PC utilisateur :** cycle réel de mise à jour depuis v0.7.8, préservation des données, rendu d'un Short et fonctionnement matériel AMD AMF/Vulkan sur RX 9060 XT.

## 11. Prochaines étapes priorisées

1. Après publication, installer v0.7.9 depuis **Paramètres > Mises à jour**, puis vérifier que les réglages, projets, bases et exports sont conservés.
2. Exécuter `docs/WINDOWS-HARDWARE-VALIDATION.md` sur la RX 9060 XT : AMF, Whisper Vulkan, Ollama/Qwen et cycle Short complet.
3. Calibrer le contrôle qualité sur plusieurs vrais Shorts GTA, en mesurant les faux positifs sur les scènes sombres, pauses voulues et séquences sans musique.
4. Améliorer les coupes naturelles et la construction des hooks à partir des limites de phrases, sans CTA générique à l'ouverture.
5. Développer le classement visuel des événements GTA (HUD, kill feed et changements de scène) avec un score explicable et une validation humaine.
6. Garder les futures améliorations dans `app/` et produire les packages depuis cette source directe.

## 12. Message de reprise prêt à copier

> Nous reprenons GTA Ranked Studio. Lis `docs/CONTINUATION.md` puis `docs/WORKING-AGREEMENT.md`. La source de développement est directement dans `app/`, et non dans une archive. La v0.7.9 est la Release stable actuelle : https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.9. Les workflows Linux, Windows et Release doivent tous tester/construire directement depuis `app/`, sans hotfix ni extraction d'archive. Préserve les données locales. Modifie uniquement les fichiers nécessaires, ajoute les tests pertinents, valide sous Linux et Windows pour les changements transversaux. La RX 9060 XT n'a pas encore été validée physiquement pour AMF/Vulkan. L'utilisateur souhaite que toute modification demandée soit intégrée et publiée directement dès que les contrôles sont réussis. Travailler directement dans GitHub, éviter les audits redondants, préserver une qualité élevée et maintenir ce mémo à jour à chaque lot.
