# GTA Ranked Studio | Mémo maître de reprise

> Lire ce document en premier dans chaque nouvelle conversation sur le projet. Il décrit l'état réellement livré et la structure source actuelle.

- **Dernière mise à jour :** 28 novembre 2026
- **Progression des releases :** à chaque relance de développement, le compte rendu doit indiquer le lot livré, les PR/CI, l'état d'avancement vers la prochaine version et une estimation actualisée du nombre de lots restants avant sa publication. Cette estimation doit être réévaluée à chaque session, sans promettre une date artificielle.
- **Dernière version stable confirmée :** [v0.9.3](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.9.3), publiée le 28 novembre 2026.
- **État :** les PR #92 à #112 sont intégrées dans `main` (HEAD `88962e05738c2bf0a91fb43159aab340dcd0beb3`). La PR #113 est ouverte sur `fix/hook-diarization-runtime-fallback` pour préserver l’analyse du hook si la diarisation optionnelle installée échoue techniquement, sans relâcher le filtrage strict des sous-titres. La v0.9.3 reste la dernière release stable ; la prochaine publication attend la consolidation du parcours Short et la validation matérielle Windows/AMD.
- **Dépôt :** https://github.com/Sreleew/GTA_rankd
- **Archive de provenance :** `archive/releases/v0.7.8/`. C'est une archive historique de la version publiée, pas la source de développement.
- **Source active :** `app/`. Modifier directement les fichiers Python, JavaScript, CSS, HTML, tests et installateur présents dans ce dossier.
- **Mise à jour intégrée :** l'application consulte les Releases GitHub et installe le ZIP Windows publié, avec vérification SHA-256.
- **CI PR #14 :** Linux et Windows terminés avec succès, y compris suites de régression, analyse statique, audit de dépendances et packaging. Les décomptes détaillés ne sont pas consignés ici.
- **Sécurité et packaging :** Ruff et pip-audit réussis sur Linux et Windows, aucune vulnérabilité connue ; ZIP Windows et SHA-256 vérifiés.
- **PR de maintenance :** [#10](https://github.com/Sreleew/GTA_rankd/pull/10), fusionnée dans `main`.
- **PR coupes naturelles :** [#11](https://github.com/Sreleew/GTA_rankd/pull/11), fusionnée dans `main`. Le départ du Short préfère une frontière après ponctuation ou pause de 0,75 s ; fallback temporel conservé si aucune frontière fiable n'existe.
- **PR profil de production :** [#12](https://github.com/Sreleew/GTA_rankd/pull/12), fusionnée dans `main`. VOD : candidats 60, 90, 120, 150 et 165 s ; sources Twitch plus courtes préservées.
- **CI PR #12 :** Linux 155 réussis + 1 ignoré ; Windows 156 réussis. Ruff, pip-audit, ZIP et SHA-256 validés.
- **Historique v0.8.6 :** ZIP Windows de 193 520 octets et `SHA256SUMS.txt` publiés. Cette version a été remplacée par la v0.8.7, dernière Release stable.
- **Release v0.8.2 :** [publication officielle](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.2), workflow [réussi](https://github.com/Sreleew/GTA_rankd/actions/runs/45850248905).
- **PR de livraison v0.7.9 :** [#8](https://github.com/Sreleew/GTA_rankd/pull/8), fusionnée dans `main`.
- **PR cadrage intelligent v0.8.0 :** [#9](https://github.com/Sreleew/GTA_rankd/pull/9), fusionnée dans `main` et publiée.
- **Workflow de publication v0.7.9 :** https://github.com/Sreleew/GTA_rankd/actions/runs/45793843538.
- **Workflow de publication v0.8.0 :** https://github.com/Sreleew/GTA_rankd/actions/runs/45797395932.
- **CI Linux v0.8.0 :** https://github.com/Sreleew/GTA_rankd/actions/runs/45796472429.
- **CI Windows v0.8.0 :** https://github.com/Sreleew/GTA_rankd/actions/runs/45796473363.
- **Validation PC v0.9.0 (27 novembre 2026) :** mise à jour installée ; Whisper/Vulkan confirmé sur AMD Radeon RX 9060 XT (1 623,92 MB alloués) ; inférence Ollama/Qwen réussie en 7,6 s. L’interface détecte H.264 AMF, mais un export réel reste à confirmer.
- **Profil de durée :** les anciennes configs v0.8.1 migrent les anciens défauts en mémoire uniquement, sans réécrire `config.yaml` et sans remplacer les réglages personnalisés. Les clips de moins de 60 s restent inchangés.

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
- Aucune miniature graphique personnalisée n'est générée : l'aperçu interne reste une capture brute et la plateforme choisit l'image de couverture lors de la publication.
- File de traitement, progression FFmpeg, annulation, prévisualisation, validation/rejet et bibliothèque de clips.
- Après validation d'un Short, Prévisualiser, Télécharger et Copier le titre, la description, les hashtags et le post restent accessibles.
- La shortlist de moments forts écarte les transcriptions longues quasi identiques issues de passages éloignés, sans filtrer les réactions courtes ni les scans audio seuls.
- Le calcul des scores utilise des index temporels sur les fenêtres audio et les mots Whisper, avec fallback linéaire pour les entrées non triées.
- Le montage intelligent de Shorts est intégré : les clips Twitch déjà sélectionnés sont préservés, les pauses longues ne sont retirées qu'avec des timestamps mot à mot DTW fiables, et les sous-titres, le pic audio, le zoom et l'audio sont recalés sur la timeline assemblée.
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
- **Documentation canonique :** `docs/` à la racine. Le constructeur de ZIP injecte les documents requis directement depuis cette source, sans copie de travail sous `app/docs/`.
- **Métadonnées :** `VERSION.txt`, `app/VERSION.txt`, `app/pyproject.toml` et `app/config.yaml.default` doivent annoncer la même version. Les notes de version racine et leur copie applicative doivent être identiques.
- **Profil matériel :** Windows 10/11, AMD Radeon RX 9060 XT 16 Go, FFmpeg H.264 AMF avec fallback libx264, whisper.cpp Vulkan avec fallback CPU, Ollama/Qwen facultatif.

## 4. Limites connues

1. La détection des moments forts repose sur l'audio et le texte. Elle ne comprend pas encore les événements visuels du gameplay et ne doit pas prétendre détecter avec certitude un kill, crash ou événement HUD.
2. Le filtre lexical ne sépare pas mathématiquement streamer et personnages lorsque leurs voix sont mélangées.
3. La diarisation est expérimentale : en cas d'ambiguïté, préserver les sous-titres plutôt que supprimer la mauvaise voix.
4. La CI Linux et le runner Windows ne valident pas les performances AMF/Vulkan sur la RX 9060 XT physique.
5. Les hooks, coupes de phrases, CTA et compositions doivent encore être jugés sur de vrais Shorts. Éviter les CTA génériques en ouverture.
6. Les compilations Best Of, chapitres et Hall of Fame figurent dans d'anciennes feuilles de route, mais leur état fonctionnel n'a pas été confirmé en v0.8.0.
7. Les alertes qualité ne sont pas des rejets : certaines scènes sombres, statiques ou silencieuses sont intentionnelles.

## 5. Source de référence et état des branches

- **Base propre intégrée :** PR #6 fusionnée dans `main`.
- **Montage intelligent intégré :** PR #7 fusionnée dans `main`.
- **Refonte créative intégrée :** PR #8 fusionnée dans `main`, version v0.7.9.
- **Cadrage vertical intelligent (PR #9) :** fusionné dans `main` et publié en v0.8.0. Layout 9:16 par défaut, panneau gameplay agrandi à 42 % de la hauteur, focus horizontal par défaut à 80 %, hook en haut et sous-titres en zone basse. Les sources portrait restent proportionnelles et les modes `fill`/`blur` restent disponibles.
- **Contrôle documentaire :** correction de `tools/check_project_memory.py` pour reconnaître les sections 9 à 12 du mémo, évitant les échecs CI dus à l'ancien plan de sections.
- **Validation restante :** les tests synthétiques Linux/Windows passent. Vérifier le cadrage sur plusieurs vrais clips Twitch, notamment les HUD et les facecams dont la position varie, puis confirmer AMF/Vulkan sur le PC AMD.

- **Source de développement :** `app/`. Ne pas décompresser l'archive de release pour développer.
- **Archive de provenance v0.7.8 :** `archive/releases/v0.7.8/`. La conserver intacte.
- **Fichiers de contrôle :** manifeste et SHA-256 de l'archive de provenance.
- **Anciennes chaînes de correctifs :** retirées de la racine active. Les tags et l'historique Git conservent les commits historiques ; ne pas réintroduire l'ancienne chaîne de reconstruction.
- **Ancienne tentative v0.8.0 :** les fragments incomplets ont été retirés de la racine active. Ne pas restaurer ni reconstruire cette tentative par supposition.
- **CI Linux :** `Audit GTA Ranked Studio application`, teste la source `app/`, le mémo racine et le package.
- **CI Windows :** `Windows runtime validation`, teste la source `app/`, tous les scripts PowerShell et le ZIP.
- **Publication :** `Build and publish GTA Ranked Studio`, construit le ZIP à partir de `app/` ; aucune extraction d'archive ni application de hotfix.

## 6. Fichiers importants

- `app/studio/` : code applicatif.
- `app/installer/` : installateur et constructeur de package.
- `app/tests/` : tests de régression.
- `app/config.yaml.default` : configuration initiale, jamais une configuration personnelle.
- `VERSION.txt` : numéro de release racine, à synchroniser avec `app/VERSION.txt`.
- `NOTES-vX.Y.Z.txt` : notes racine et copie `app/NOTES-vX.Y.Z.txt`, synchronisées dans le dépôt pour contrôler la version. Elles ne sont pas embarquées dans le ZIP utilisateur.
- `docs/CONTINUATION.md` : ce mémo maître.
- `docs/WORKING-AGREEMENT.md` : méthode de travail.
- `docs/RELEASE_PROCESS.md` : procédure de test et de publication.
- `docs/UPDATES.md` : guide utilisateur et historique.
- `docs/WINDOWS-HARDWARE-VALIDATION.md` : protocole de validation sur le PC AMD.
- `tools/check_project_memory.py` : vérificateur canonique unique des versions, de la configuration et du mémo.
- `tools/verify_release_package.py` : contrôle commun du contenu, des exclusions, des chemins et du SHA-256 du ZIP.
- `docs/PROJECT-MAP.md` : carte rapide des modules et chemins de validation.
- `archive/releases/v0.7.8/` : archive historique figée, pas une base de développement.
- `.github/workflows/audit-source.yml` : tests Linux et packaging à partir de `app/`.
- `.github/workflows/windows-smoke.yml` : tests Windows et packaging à partir de `app/`.
- `.github/workflows/release.yml` : publication stable à partir de `app/`.
- `.release-approval` : autorisation explicite d'une version stable sur `main`.

Ne jamais publier `config.yaml`, vidéos, rendus personnels, bases SQLite, modèles IA téléchargés, environnements virtuels, logs, tokens ou secrets. Le processus de mise à jour doit préserver les configurations et données utilisateur.

## 7. Commandes de contrôle

Depuis PowerShell, à la racine du dépôt :

```powershell
py -3.11 -m pip install -e "app[dev]"
py -3.11 tools/check_project_memory.py --root .
ruff check app/studio app/installer app/tests tools
pip-audit -r app/requirements.txt
$createdConfig = $false
if (-not (Test-Path app/config.yaml)) {
    Copy-Item app/config.yaml.default app/config.yaml
    $createdConfig = $true
}
try {
    py -3.11 -m pytest -q -c app/pyproject.toml app/tests
}
finally {
    if ($createdConfig) { Remove-Item app/config.yaml -Force }
}
Set-Location app
node --check studio/web/static/app.js
py -3.11 installer/build_release_package.py --version 0.8.8 --output-dir dist
Set-Location ..
py -3.11 tools/verify_release_package.py --package app/dist/GTA-Ranked-Studio-v0.8.8.zip --checksum app/dist/SHA256SUMS.txt --version 0.8.8
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
- Les workflows vérifient les documents racine et le constructeur les injecte directement dans le ZIP. Aucun snapshot documentaire n'est copié sous `app/`.
- Préserver la configuration, les bases, projets, médias, exports et modèles locaux.
- L'utilisateur a demandé que toute modification demandée soit menée jusqu'à l'intégration et la publication stable, sans s'arrêter à une branche ou une PR. En cas d'échec CI ou de blocage technique, corriger ou expliquer le blocage.
- Ne jamais présenter un test prévu comme réussi. Distinguer code modifié, tests CI et validation matérielle réelle.

## 9. Préférences utilisateur et méthode de collaboration

- **Travailler directement dans GitHub.** Le dépôt est la source de vérité : ne pas demander un ZIP ou une copie locale si les fichiers sont accessibles dans le dépôt.
- **Livrer du propre et du fonctionnel.** Privilégier une base saine, un périmètre ciblé, des tests utiles et une vraie vérification des régressions. Ne pas sacrifier la qualité pour aller plus vite.
- **Éviter les lenteurs inutiles.** Ne pas refaire de longs audits ni relire tout l'historique à chaque demande. Lire le mémo, le HEAD, les contrôles utiles et seulement les fichiers concernés.
- **Aller jusqu'au résultat utilisable.** Pour une modification demandée, travailler sur une branche, tester, fusionner dans `main` et publier une Release stable lorsque les validations passent. Si un contrôle bloque, le corriger ou expliquer précisément pourquoi la livraison est arrêtée.
- **Découpage du travail :** pour les gros chantiers, avancer par lots courts, cohérents et contrôlables, avec des points de reprise explicites. Éviter les réponses monolithiques qui risquent d'expirer.
- **Priorités produit actuelles, dans cet ordre :** (1) fiabiliser et optimiser « Créer un Short » directement à partir d'un clip Twitch : URL → téléchargement → montage vertical → review → métadonnées prêtes à publier ; la plateforme choisit sa miniature ; (2) développer « Daily Best Of » à partir des clips validés de la bibliothèque locale, avec sélection et assemblage horizontal 16:9 d'environ 9 à 11 minutes. Accepter un premier niveau de qualité de 85-90 % et privilégier un flux fiable de production/publication. **Mettre « Moments forts » en pause** : ne pas développer ni raffiner cette fonctionnalité pour le moment, sans la supprimer ni casser le code existant.
- **Durée cible :** Shorts de 60 à 165 secondes. Les clips Twitch plus courts sont conservés tels quels, sans rallongement artificiel. Les passages VOD sont proposés en 60, 90, 120, 150 ou 165 secondes.
- **Miniatures :** les miniatures graphiques custom et leur export sont en pause. La plateforme choisit l'image de couverture ; l'aperçu interne reste une capture brute.
- **Évaluer sur des exemples réels.** Quand l'utilisateur envoie un clip ou un Short généré, examiner concrètement le rendu avant de décider des corrections. Distinguer les observations réelles des hypothèses.
- **Garder les contrôles utiles accessibles après validation.** Conserver prévisualisation, téléchargement et copie des métadonnées ; l'export de miniature custom est en pause.
- **Communication :** être direct et concis, donner les résultats concrets et signaler clairement ce qui reste non testé.
- **Pilotage proactif confirmé le 27 novembre 2026 :** l'utilisateur ne souhaite pas devoir arbitrer les choix techniques ou connaître le développement. L'assistant prend l'initiative de piloter le produit et les décisions techniques, explique les conséquences en termes simples et recommande clairement de ne pas construire une fonctionnalité lorsqu'elle est trop complexe, lente, coûteuse à maintenir, peu utile ou peu rentable par rapport à sa valeur. Toujours comparer le bénéfice attendu au temps de développement, au temps de traitement, à la fiabilité, à la maintenance et à l'impact sur l'expérience utilisateur. Proposer des alternatives plus simples, supprimer ou reporter les idées à faible ROI, anticiper les besoins et pousser le concept vers un produit premium sans sur-ingénierie. Ne demander un arbitrage utilisateur que lorsqu'il dépend réellement de ses goûts, de ses objectifs ou d'une contrainte inaccessible au développeur. L'utilisateur fait confiance à l'assistant pour le guider et attend une posture proactive, experte et honnête.
- **Suivi de progression demandé le 27 novembre 2026 :** terminer chaque relance par un indicateur lisible de progression vers la prochaine Release (lots terminés/restants, contenu restant et estimation de la prochaine mise à jour). Ne pas laisser l'utilisateur deviner où en est le chantier. Les réponses doivent rester courtes et les gros travaux être découpés en petits lots pour éviter les expirations de réception de ChatGPT. Une seule prochaine action prioritaire dans le bilan.

## 10. Journal de travail récent

- **Réorientation produit demandée le 27 novembre 2026 :** priorité au Short créé directement depuis un clip Twitch, puis au Daily Best Of ; la fonctionnalité Moments forts est explicitement en pause. Ne pas poursuivre le chantier de VOD longues, sauf bug bloquant pour les priorités.
- **Audit ciblé des parcours :** l'import URL Short existe et utilise yt-dlp ; l'UI gère montage, captions, réglages, hook/contexte, file, preview, téléchargement, capture brute d'aperçu et métadonnées. Le hook de progression yt-dlp a été corrigé par la PR #32 afin d'afficher l'avancement réel pendant le téléchargement. Les clips de moins de 165 secondes sont conservés en entier par `select_excerpt_range`.
- **PR #32 fusionnée : progression du téléchargement Twitch Short.** Le hook yt-dlp lit `downloaded_bytes` et `total_bytes` ou `total_bytes_estimate`, affiche la progression de 10 à 19 % avec throttling des écritures SQLite, puis affiche « Téléchargement terminé · préparation du Short ». Test simulé : 25 %, 75 % avec taille estimée, et transition à la fin. CI PR Linux [45996501467](https://github.com/Sreleew/GTA_rankd/actions/runs/45996501467) et Windows [45996501488](https://github.com/Sreleew/GTA_rankd/actions/runs/45996501488) réussies. PR fusionnée dans `main` via commit `03c5010cae2dfd27d673060ef751a6b80dd4a8d4`. CI post-fusion Linux [45996808865](https://github.com/Sreleew/GTA_rankd/actions/runs/45996808865) et Windows [45996808775](https://github.com/Sreleew/GTA_rankd/actions/runs/45996808775) réussies.
- **PR #33 fusionnée :** correction documentaire après le correctif de progression Twitch, avec les résultats CI Linux/Windows de la PR #32 et l'état des contrôles post-fusion.
- **PR #34 fusionnée : validation des URL Twitch pour Créer un Short.** La route `/api/shorts/url` réutilise la validation stricte des sources Twitch : HTTPS obligatoire, hôtes Twitch autorisés, URL de clip ou de VOD uniquement, longueur limitée à 2 000 caractères. Le formulaire indique explicitement les formats attendus. Tests API ajoutés pour les domaines tiers, faux domaines Twitch, pages de chaîne, HTTP, URL trop longues et liens Twitch valides. PR fusionnée dans `main` via commit `bf2cd289ab9edcbb06a26b3dac58f288518ec6e7`. CI Linux [45999490719](https://github.com/Sreleew/GTA_rankd/actions/runs/45999490719) et Windows [45999489735](https://github.com/Sreleew/GTA_rankd/actions/runs/45999489735) réussies.
- **Lot en cours : timeout FFprobe proportionnel à la taille du média.** `probe_timeout_for_file()` existait déjà mais n'était pas utilisé par défaut par `probe_media()`, qui conservait un timeout fixe de 60 secondes. Le correctif rend le timeout adaptatif (minimum 5 minutes, progression selon la taille, plafond 30 minutes), tout en permettant un timeout explicite pour les appels qui en ont besoin. Tests ajoutés pour le timeout adaptatif et le respect du timeout explicite. PR et CI à renseigner après validation.
- **PR #37 fusionnée : sous-titres conservateurs en mode « voix principale ».** Lorsque la diarisation est ambiguë, indisponible, sans segments exploitables ou avec trop peu de mots attribuables, le worker omet les sous-titres au lieu de réafficher toutes les voix. Le mode « toutes les voix » reste disponible explicitement. L'interface indique que ce mode bêta ne garantit pas l'identité du streamer. PR fusionnée via commit `e531be2a11343b9b4b29f2264d4e843ce4a91437`. CI Linux [46003699185](https://github.com/Sreleew/GTA_rankd/actions/runs/46003699185) et Windows [46003699225](https://github.com/Sreleew/GTA_rankd/actions/runs/46003699225) réussies après relance du job Windows, initialement bloqué par un timeout externe Chocolatey 504. Aucun test réel de clip Twitch ni de reconnaissance fiable du streamer n'a encore été effectué.
- **PR #35 fusionnée : métadonnées Twitch du Short.** Le worker privilégie désormais le nom du broadcaster (`channel`, puis `channel_name`/`broadcaster_name`) au créateur du clip (`uploader`), et utilise des replis sûrs pour le titre et le streamer. Les métadonnées fournies par l'utilisateur restent prioritaires. Tests unitaires ajoutés pour la priorité broadcaster et les replis. PR fusionnée via commit `17ae226e607c5768822830bbc547aa7d30050f0f`. CI Linux [46002438327](https://github.com/Sreleew/GTA_rankd/actions/runs/46002438327) et Windows [46002438263](https://github.com/Sreleew/GTA_rankd/actions/runs/46002438263) réussies. Tests synthétiques uniquement, pas de téléchargement Twitch réel.
- **PR #36 fusionnée :** mise à jour documentaire consignant la correction des métadonnées Twitch de la PR #35.
- **Daily Best Of :** la page est encore un écran « En développement ». La bibliothèque et la table `clips` existent déjà pour les Shorts validés, mais aucun moteur de sélection, scoring quotidien ou assemblage horizontal n'est présent.

- **v0.8.5 publiée :** PR #19 à #22 fusionnées. Refonte éditoriale Vice City Dispatch, score payoff fondé sur les pics audio et réactions proches, coupes préservant les réactions verbales retardées, puis synchronisation et publication de la version.
- **v0.8.6 publiée :** PR #23 à #25 fusionnées. Diversité des candidats par dédoublonnage des transcriptions longues similaires, indexation temporelle des fenêtres audio/Whisper et préparation de la Release stable. Le benchmark synthétique a mesuré un facteur 68,2 sur la recherche d'intervalles uniquement, pas sur le temps total d'analyse.
- **PR #26 fusionnée :** saisie des plages en secondes ou `HH:MM:SS` pour les analyses locales et Twitch, avec validation des minutes et secondes. CI Linux/Windows réussie.
- **PR #27 fusionnée :** analyse de plages VOD Twitch en lots de tranches de 30, 45, 60, 90, 120 ou 180 minutes, jusqu'à 48 segments. Chaque tranche est un scan indépendant, inséré en base de façon atomique ; les plages sont téléchargées séparément et la VOD entière n'est pas récupérée en un seul fichier.
- **PR #28 fusionnée :** carte de lot avec progression agrégée, erreurs, shortlist globale limitée à 30 candidats, dédoublonnage inter-segments et conservation du `scan_id` d'origine pour créer chaque Short depuis le bon média. L'annulation globale arrête les tranches encore en attente/en cours.
- **Limite du classement global :** les scores audio sont normalisés à l'intérieur de chaque segment. Le classement entre tranches est donc indicatif ; relire les moments avant export.
- **PR #29 fusionnée :** synchronisation des versions, notes de release, documentation et approbation explicite de publication pour la v0.8.7.
- **Release stable v0.8.7 :** publiée le 27 novembre 2026. Workflow officiel [45991509028](https://github.com/Sreleew/GTA_rankd/actions/runs/45991509028) réussi. ZIP Windows de 197 246 octets et `SHA256SUMS.txt` publiés. SHA-256 du ZIP : `8239f0788fa788f793ae19228d589443e76ea32477cd04020e1f0267df1307f3`.
- **CI post-fusion sur main :** Linux [45991878153](https://github.com/Sreleew/GTA_rankd/actions/runs/45991878153) et Windows [45991878149](https://github.com/Sreleew/GTA_rankd/actions/runs/45991878149) réussis sur le commit `0dab6b152acd353ab3e84594f9cb3a1401290f55`.
- **Validation matérielle restante :** aucune validation réelle sur la RX 9060 XT pour l'encodage AMD AMF et Whisper Vulkan n'a encore été effectuée. Les runners CI ne remplacent pas ce test sur le PC utilisateur.

## 10 bis. État après PR #37

- Le mode de sous-titrage « voix principale » est désormais conservateur : il préfère ne rien afficher lorsque la diarisation ne fournit pas une attribution suffisamment fiable, plutôt que d'inclure les dialogues du jeu. Cela réduit les faux sous-titres, mais ne prouve pas que la voix restante est celle du streamer.
- Le parcours de création de Short depuis une URL Twitch dispose maintenant de validations d'URL, d'une progression de téléchargement, d'une extraction du broadcaster et d'un filtrage conservateur des voix. PR #40 ajoute une entrée directe sur URL Twitch et polit le hook/la miniature. Ces validations ne remplacent pas un essai réel avec un clip Twitch.
- PR #37 : https://github.com/Sreleew/GTA_rankd/pull/37. Commit de merge : `e531be2a11343b9b4b29f2264d4e843ce4a91437`.

## 10 ter. État au 27 novembre 2026

- **PR #39 fusionnée** : FFprobe utilise désormais un timeout adaptatif selon la taille du fichier, avec un plancher de 5 minutes et un plafond de 30 minutes. Les timeouts explicitement fournis restent prioritaires. CI Linux et Windows réussie. Commit de merge : `d673c385e48f1957bb32bc064e6e65ff35a5cabe`.
- **PR #40 fusionnée** : la création de Short s'ouvre par défaut sur la saisie d'une URL Twitch ; le texte sur le filtrage des voix correspond au comportement réel ; le hook d'ouverture passe à 2,6 secondes ; le kicker de miniature décrit correctement un clip Twitch. Les clés de cache statique sont actualisées. CI Linux et Windows réussie. Commit de merge : `88b5c29e66dc529dc8360f2f7bbc8068f4bc4dfe`.
- **Priorité utilisateur confirmée** : travailler d'abord sur la création de Shorts depuis une URL de clip Twitch, puis sur le Daily Best Of. La fonctionnalité « Moments forts » est explicitement en pause ; ne pas la développer ni l'optimiser sauf blocage direct d'une priorité.

## 10 quater. Daily Best Of : premier module de composition

- Le placeholder a été remplacé par un constructeur d'épisode : filtre par journée, bibliothèque des Shorts validés, ajout/retrait, ordre manuel avec flèches, durée cumulée et jauge cible 9 à 11 minutes.
- Nouvelle API `POST /api/bestof/plan` : valide les IDs, l'appartenance à la journée, le statut validé, l'existence des rendus locaux et l'ordre choisi. Les médias sources ne sont ni déplacés ni modifiés.
- Nouveau module `app/studio/web/best_of.py` avec validation indépendante et bornes 540 à 660 secondes. Le rendu final 16:9 n'est pas encore implémenté ; l'interface l'indique explicitement.
- **PR #41 fusionnée :** constructeur de sélection Daily Best Of. CI Linux [46009727834](https://github.com/Sreleew/GTA_rankd/actions/runs/46009727834) et Windows [46009727859](https://github.com/Sreleew/GTA_rankd/actions/runs/46009727859) réussies. Le rendu final 16:9 reste à développer.

## 11. Prochaines étapes priorisées

1. **Créer un Short depuis un clip Twitch : priorité immédiate.** Le parcours URL, téléchargement, progression, montage vertical, sous-titres, hook, métadonnées et review existe ; l'image de couverture reste choisie par la plateforme. PR #42 permet de relancer un job Twitch échoué depuis son URL d'origine si le média local n'a pas été téléchargé, tout en réutilisant le fichier local lorsqu'il existe. Prochaine étape : valider le parcours complet avec un vrai clip sur le PC Windows et corriger les défauts constatés.
2. **Daily Best Of : deuxième priorité.** PR #41 ajoute le constructeur de sélection par date, l'ajout/retrait, l'ordre manuel, le calcul de durée et la validation serveur des Shorts validés. Prochaine étape : rendre le plan persistant, puis produire un export horizontal 16:9 de 9 à 11 minutes avec mixage et contrôle qualité.
3. Conserver les actions de prévisualisation, téléchargement et copie des métadonnées après validation d'un Short ; l'export de miniature custom reste en pause.
4. **Moments forts : en pause.** Ne pas ajouter de fonctions, optimiser les scores ou étendre les scans VOD, sauf bug bloquant directement un parcours prioritaire.
5. Valider sur la RX 9060 XT l'encodage AMD AMF, Whisper Vulkan et Ollama/Qwen lors de cycles réels. La CI ne remplace pas ce test matériel.
6. Livrer les lots cohérents avec tests ciblés, CI Linux/Windows, fusion et release. Mettre ce mémo à jour à chaque lot.
## 12. Message de reprise prêt à copier

> Nous reprenons GTA Ranked Studio. Lis `docs/CONTINUATION.md` et `docs/WORKING-AGREEMENT.md`. Dernière Release stable : v0.8.7. Priorité 1 : améliorer « Créer un Short » directement depuis un clip Twitch, du collage de l'URL jusqu'au rendu 9:16, aux métadonnées et à la review. Priorité 2 : développer « Daily Best Of » à partir des clips validés de la bibliothèque, en 16:9 sur 9 à 11 minutes. Laisser « Moments forts » en pause, sans supprimer ce qui existe. Travailler directement dans GitHub, par petits lots courts, tests adaptés, fusion/release après validation. Mettre obligatoirement ce mémo à jour à chaque lot avec les décisions de l'utilisateur, les modifications, PR, commits, tests et limites. Réponses courtes, préserver les données locales et distinguer CI, tests simulés et validation réelle sur le PC.


## 10. Reprise du 27 novembre 2026

- **Priorité 1 :** finaliser et fiabiliser le parcours de création d'un Short depuis une URL de clip Twitch, du téléchargement au rendu et à la validation. Priorité 2 : rendre la compilation Daily Best Of réellement exportable en 16:9. La fonctionnalité « Moments forts » est mise en pause et ne doit pas être développée sauf blocage direct.
- **PR #41 :** fusionnée dans `main` (merge commit `101e3a3c6e2114d024aed602e01d5e764bf22e37`). CI Linux run `46009727834` et Windows run `46009727859` réussis. Le constructeur Daily Best Of valide une sélection mais ne produit pas encore la vidéo finale.
- **Méthode confirmée :** travailler directement dans `Sreleew/GTA_rankd`, avancer sans demander de validation à chaque petite étape, privilégier les améliorations réellement utilisables plutôt que les PR de tests ou de documentation isolées. Garder les lots cohérents, tester Linux et Windows avant fusion, et signaler clairement ce qui est livré versus ce qui reste à faire.
- **Lot en cours :** amélioration de la relance des Shorts Twitch. Si un téléchargement depuis l'URL échoue avant la sauvegarde du média local, l'action « Relancer » doit créer un nouveau job depuis l'URL Twitch d'origine en conservant les options, streamer et note. Si le média a déjà été téléchargé, continuer à le réutiliser sans le télécharger une seconde fois.


## 10 quinquies. Préparation de la v0.8.8, 27 novembre 2026

- **PR #41 fusionnée** dans `main` : constructeur de sélection Daily Best Of (date, clips validés, ajout/retrait, ordre manuel, durée cible 9 à 11 min, validation serveur). Le rendu final 16:9 n'est pas encore disponible.
- **PR #42 fusionnée** dans `main` : relance d'un job Twitch échoué depuis l'URL Twitch d'origine lorsque le téléchargement local a échoué. La relance conserve streamer, note et options ; si le fichier local existe déjà, il est réutilisé. Commit de merge : `2ef1124847a6a3acb34b203a193dadb75dcd60d6`.
- **CI PR #42 :** Linux [46012357301](https://github.com/Sreleew/GTA_rankd/actions/runs/46012357301) et Windows [46012357283](https://github.com/Sreleew/GTA_rankd/actions/runs/46012357283) réussies.
- **CI post-fusion sur main :** Linux [46012922370](https://github.com/Sreleew/GTA_rankd/actions/runs/46012922370) et Windows [46012922379](https://github.com/Sreleew/GTA_rankd/actions/runs/46012922379) réussies.
- **CI de préparation v0.8.8 (PR #43) :** Linux [46013472471](https://github.com/Sreleew/GTA_rankd/actions/runs/46013472471) et Windows [46013472448](https://github.com/Sreleew/GTA_rankd/actions/runs/46013472448) réussies après retrait de l'ancienne copie `app/NOTES-v0.8.7.txt`.
- **Release stable v0.8.8 publiée :** workflow officiel [46014440309](https://github.com/Sreleew/GTA_rankd/actions/runs/46014440309) réussi. ZIP Windows : 207 327 octets ; SHA-256 `c6155b1ce323edf6fb6088ceb386ae38223aaa4c0c875b95f245a7bbb76e8d1b`.
- **Priorité utilisateur inchangée :** finaliser et tester la création de Shorts depuis une URL Twitch, puis terminer le rendu Daily Best Of. « Moments forts » reste en pause.



## 13. Correctif du parcours de mise à jour, 27 novembre 2026

- **Retour utilisateur :** lors de l'installation de la v0.8.8, l'interface a affiché « Failed to fetch » alors que la mise à jour semblait se terminer correctement.
- **Diagnostic probable confirmé par le code :** le script de mise à jour arrête volontairement le serveur local avant de le redémarrer. Pendant cette courte coupure, le rafraîchissement automatique du tableau de bord continue toutes les 5 secondes et transformait l'indisponibilité attendue en toast « Failed to fetch ». Le polling de statut de mise à jour, lui, effaçait son intervalle au premier échec réseau et ne confirmait donc pas le retour du serveur.
- **Correctif en cours :** l'interface distingue désormais la coupure réseau attendue d'une vraie erreur, garde le polling pendant le redémarrage, interroge la version après le retour du serveur et recharge la page lorsque la version attendue est bien installée. Les erreurs de rafraîchissement en arrière-plan sont masquées uniquement pendant la mise à jour.
- **Branche :** `fix/silent-update-restart-fetch`. Tests de régression ajoutés dans `app/tests/test_updates.py`. CI, fusion et publication de la version corrective à renseigner après validation.
- **Priorité utilisateur inchangée :** création de Shorts depuis Twitch, puis rendu Daily Best Of. Moments forts reste en pause.


## 14. Correctif v0.8.9, 27 novembre 2026

- **PR #45 fusionnée** dans `main` : https://github.com/Sreleew/GTA_rankd/pull/45. Commit de merge : `055e257fd9449d7d4fbf83e846d47c3704c5f6cf`.
- **CI PR #45 :** Linux run [46015871458](https://github.com/Sreleew/GTA_rankd/actions/runs/46015871458) et Windows run [46015871444](https://github.com/Sreleew/GTA_rankd/actions/runs/46015871444) réussies.
- **Correctif :** pendant la mise à jour, la coupure du serveur local est maintenant traitée comme un redémarrage attendu. Le polling continue, confirme la version cible au retour du serveur, affiche le succès et recharge l'interface. Les erreurs transitoires du tableau de bord ne déclenchent plus de faux toast pendant cette phase.
- **Préparation de release :** branche `release/v0.8.9-update-restart-fix`, version cible 0.8.9. La Release ne sera considérée comme publiée qu'après fusion de la préparation, réussite du workflow officiel et vérification des assets.
- **Validation utilisateur encore nécessaire :** installer la v0.8.9 depuis Paramètres > Mises à jour et confirmer la version affichée après redémarrage. CI ne remplace pas ce test réel.
- **Priorités produit inchangées :** fiabiliser la création de Shorts depuis Twitch, puis terminer le rendu Daily Best Of 16:9. Moments forts reste en pause.

- **CI initiale de la PR #46 :** Linux run [46016845255](https://github.com/Sreleew/GTA_rankd/actions/runs/46016845255) et Windows run [46016845297](https://github.com/Sreleew/GTA_rankd/actions/runs/46016845297) ont échoué au contrôle de structure avant les suites de tests. Le diagnostic des logs est identique sur les deux runners : l'ancienne copie `app/NOTES-v0.8.8.txt` est encore présente alors que la cible est v0.8.9.
- **Correction de préparation :** retirer uniquement `app/NOTES-v0.8.8.txt`, qui est une copie applicative obsolète. Conserver les notes historiques racine et les notes applicatives v0.8.9. Relancer ensuite les contrôles Linux et Windows avant toute fusion.
- **Méthode de suivi demandée :** l'utilisateur souhaite que les contrôles CI et la publication de cette release soient suivis automatiquement, sans devoir envoyer « continue ». Le suivi automatisé est actif jusqu'à confirmation vérifiée de la publication.


## 15. Direction créative Shorts : identité et hook, 27 novembre 2026

- **Décision utilisateur :** le montage doit sortir du format automatique basique. Il faut une direction artistique propre et reconnaissable, une finition premium et une narration pensée spécifiquement pour le format vertical. Le hook est déterminant : les 1 à 2 premières secondes doivent immédiatement créer curiosité, tension, surprise ou promesse. Pas d'intro/logo qui retarde l'action.
- **Principes de DA :** identité éditoriale cohérente inspirée de l'énergie GTA sans copier les éléments officiels ; typographie cinétique, compositions verticales travaillées, webcam intégrée réellement, gameplay lisible, sous-titres sélectifs et synchronisés, sound design précis et transitions justifiées par l'action. Les effets doivent servir la compréhension ou la rétention, pas être décoratifs.
- **Lot commencé sur la branche** `feat/short-hook-motion-identity` : refonte du hook ASS avec un kicker « RANKED DISPATCH // GTA » et une entrée cinétique du titre (overshoot, rotation légère, flou qui se résorbe). L'objectif est d'établir une signature immédiatement visible sans ajouter une intro longue.
- **Fichiers concernés :** `app/studio/web/short_editor.py`, `app/tests/test_short_editor.py`. Validation CI à venir ; aucun rendu réel sur PC n'est revendiqué.
- **Suite produit :** construire un vrai système de compositions vidéo modulaire, puis une webcam intégrée et des variations de hook adaptées au type de moment. Garder la priorité absolue à la rétention dès les premières secondes.


## 16. Hooks cinétiques par intention, 27 novembre 2026

- État du lot : PR #47 (feat/short-hook-motion-identity) en cours. La première version du hook RANKED DISPATCH a révélé un test de régression obsolète : il attendait encore l'ancienne animation statique fad(120,180). Le rendu attendu a changé, le test doit donc vérifier la nouvelle animation et non l'ancien effet.
- Amélioration ajoutée au lot : détection locale et déterministe du type de hook (question, suspense, réaction ou impact), puis choix d'une animation ASS dédiée. Cela donne quatre entrées visuelles au lieu d'un seul effet répété, sans appel réseau ni délai IA supplémentaire.
- Finition des captions : le mot prononcé reçoit une emphase légère par couleur, échelle et contour, puis revient au style normal pour garder une lecture mobile dynamique sans surcharger chaque mot.
- Intégration : sélection automatique dans create_ass_file, sans changer le parcours utilisateur ni les options existantes. Un style explicitement reconnu peut aussi être passé par le code appelant.
- Tests ajoutés/ajustés : détection des quatre intentions, priorité du hook sur le texte de contexte, fallback contextuel si aucun hook n'est fourni, présence des animations associées et emphase du mot actif. Les validations Linux/Windows de la première version doivent être relancées après cette correction ; aucun rendu réel sur le PC n'est revendiqué.


## 17. Composition éditoriale du gameplay vertical, 27 novembre 2026

- **PR #47 fusionnée :** `Give Shorts a cinematic animated hook identity`, commit de merge `20b720a9f0d665c9959b2095dc3062d3d7d0d7db`. Quatre styles de hook (impact, question, suspense, réaction), kicker RANKED DISPATCH et emphase du mot actif dans les sous-titres. CI PR Linux et Windows réussies. CI post-fusion lancée ; résultat à confirmer.
- **Nouveau lot en cours :** renforcer la composition `smart` du Short avec un cadre éditorial fin autour du gameplay et un repère vertical ambre. L'objectif est de donner au panneau de jeu une finition de marque cohérente avec la typographie du hook, sans rogner davantage l'image ni réduire sa lisibilité.
- **Fichiers modifiés :** `app/studio/web/short_renderer.py` et `app/tests/test_render_integration.py`. Le cadre est généré directement par FFmpeg et ne nécessite aucun asset externe.
- **Limite assumée :** cette évolution ne prétend pas isoler une webcam. Les clips Twitch déjà composés sont rendus tels quels ; la séparation réelle d'une webcam n'est possible que si une source webcam distincte est disponible.
- **Suite :** valider le nouveau cadre sur les runners Linux/Windows, puis s'attaquer à une composition verticale plus ambitieuse et à la gestion de la webcam selon les médias réellement disponibles.


## 18. Détection des hooks francophones, 27 novembre 2026

- **Amélioration ajoutée à la PR #48 :** la classification des hooks reconnaît maintenant les formulations françaises (question, suspense, réaction) en plus de l'anglais. Les accents sont normalisés avant l'analyse afin que les caractères accentués soient correctement traités.
- **Exemples couverts :** « POURQUOI IL A FAIT ÇA ? » -> question ; « ATTENDS DE VOIR LA SUITE » -> suspense ; « C'EST INCROYABLE ! » -> réaction.
- **Effet utilisateur :** les hooks français reçoivent eux aussi une animation cohérente avec leur intention, au lieu de tomber systématiquement sur l'animation impact par défaut.
- **Suite :** finaliser le cadre éditorial du layout smart, puis travailler sur les transitions sonores et les vrais médias source webcam disponibles.


## 19. Sound design adapté au hook, 27 novembre 2026

- **PR #49 fusionnée :** https://github.com/Sreleew/GTA_rankd/pull/49, commit `2cbff49217d14a31312c722bbf0327e98a827d5b`. Les quatre cues originaux impact, question, suspense et réaction sont générés localement avec la bibliothèque standard Python, puis mixés au début du Short. Aucun asset externe ni dépendance supplémentaire ; le réglage SFX existant permet de désactiver le son.
- **CI PR #49 :** Linux run [46029128765](https://github.com/Sreleew/GTA_rankd/actions/runs/46029128765) et Windows run [46029128709](https://github.com/Sreleew/GTA_rankd/actions/runs/46029128709) réussies.
- **Limite utilisateur :** le son synthétique n'a pas encore été écouté sur un vrai Short ni validé sur le PC AMD. Ajuster le volume après retour d'écoute réel.


## 20. Rythme de caméra piloté par les accents audio, 27 novembre 2026

- **Décision de méthode utilisateur :** réduire le temps perdu dans les validations répétitives. Faire les contrôles ciblés pendant le développement et réserver la suite complète Linux/Windows aux changements transversaux, au packaging et aux releases. Ne pas sacrifier la stabilité ; expliquer les résultats en termes simples plutôt que lister des étapes CI sans contexte.
- **Lot en cours :** remplacer le zoom unique au pic audio par plusieurs impulsions de zoom discrètes, déclenchées sur quelques accents audio réellement marqués. Le détecteur ignore les niveaux faibles et le bruit de fond uniforme, limite le nombre d'impulsions à cinq et les espace d'au moins 4,5 secondes. Si aucun accent fiable n'est trouvé, le zoom principal existant reste utilisé.
- **Fichiers concernés :** `app/studio/web/transcribe.py` (détection multi-pics RMS), `app/studio/web/worker.py` (recalage des instants après coupe), `app/studio/web/short_renderer.py` (impulsions FFmpeg), tests de transcription et de rendu.
- **Limite éditoriale :** un accent audio n'est pas une preuve d'événement visuel GTA. Le système pilote seulement le rythme du cadrage à partir de variations sonores ; il ne prétend pas détecter kills, crashs ou événements HUD.
- **Validation visuelle encore nécessaire :** l'intensité et le rendu final doivent être jugés sur un vrai clip Twitch sur le PC AMD de l'utilisateur. Une vérification FFmpeg de rendu réel avec deux impulsions est ajoutée dans un lot de test séparé, car les tests précédents validaient surtout la construction du filtre.


## 21. Progression Twitch enrichie, 27 novembre 2026

- **Constat :** la progression de téléchargement yt-dlp existait déjà dans le message du job et sa barre globale. Elle affichait le pourcentage, mais pas le débit réel ni le temps restant, ce qui rendait les attentes difficiles à estimer sur les clips Twitch volumineux.
- **Amélioration :** le message de progression affiche maintenant les statistiques disponibles de yt-dlp, par exemple « 75 % · 1.5 MiB/s · reste 00:05 ». Les unités s'adaptent (B/s, KiB/s, MiB/s) et l'ETA s'affiche en mm:ss ou h:mm:ss. Les champs absents, invalides ou non finis sont ignorés.
- **Fiabilité :** la limitation de fréquence des mises à jour et la progression monotone existantes sont conservées. Aucun changement SQLite, aucune dépendance supplémentaire, aucun réglage utilisateur ni fichier local modifié.
- **Tests ajoutés :** le test de progression simule les débits et ETA ; un test couvre les valeurs manquantes, invalides et les ETA longues.
- **PR :** [#52](https://github.com/Sreleew/GTA_rankd/pull/52), branche `feat/twitch-download-speed-eta`, commit de code/tests `3bce968efbab655da1d117f5a20dd0f3dfb0eaf1`. La CI Linux/Windows doit réussir avant fusion. Le commit documentaire final relancera également les validations.
- **Suite :** après validation, reprendre la vérification du rendu réel Twitch et de l'intégration webcam ; Daily Best Of reste la priorité suivante. « Moments forts » reste en pause.


## 21 bis. Retour visuel sur le filtrage des voix, 27 novembre 2026

- **Amélioration :** les cartes de Short indiquent désormais explicitement le résultat du filtrage des sous-titres : voix principale isolée, une seule voix détectée, toutes les voix sous-titrées ou sous-titres omis lorsque l'attribution est incertaine.
- **Pourquoi :** le mode dominant peut volontairement supprimer les sous-titres si plusieurs voix sont trop proches ou si la diarisation échoue. L'interface affichait jusque-là les cas d'omission, mais ne disait pas quand une voix avait bien été isolée.
- **Précision technique :** la diarisation distingue des locuteurs, mais ne sait pas lequel est le streamer. Le filtrage dominant reste une heuristique prudente, pas une identification garantie du streamer. La documentation de la fonction reflète désormais ce comportement réel.
- **Tests :** vérification du rendu des libellés de statut et conservation des tests de filtrage existants. La validation complète Linux/Windows sera faite sur la PR.
- **Limite :** aucun algorithme ne peut garantir que le locuteur dominant est le streamer sur tous les clips. Une sélection explicite du locuteur nécessitera un vrai parcours d'écoute/choix utilisateur, qui reste à concevoir.


## 22. Taille téléchargée dans la progression Twitch, 27 novembre 2026

- **Amélioration :** le message de téléchargement affiche maintenant la quantité reçue et la taille totale estimée, en MiB, en complément du pourcentage, du débit et du temps restant. Exemple : « 75 % · 75.0/100.0 MiB · 1.5 MiB/s · reste 00:05 ».
- **Robustesse :** si yt-dlp ne fournit pas de taille totale, seule la quantité déjà reçue est affichée ; les valeurs invalides ou nulles sont ignorées.
- **Impact :** aucun changement au comportement de téléchargement, aux reprises, aux fragments ou aux dépendances. La fréquence des mises à jour reste inchangée.
- **Tests :** assertions de progression avec taille totale connue et cas sans total / valeur invalide.
- **PR :** en attente de CI Linux et Windows.


## 23. Sous-titres découpés aux fins de phrase, 27 novembre 2026

- **PR #54 fusionnée :** progression Twitch enrichie avec taille téléchargée/estimée, débit et ETA. Commit de merge : 776db351a2da5273b8b8160ac66c86d55175c237. CI PR et post-fusion Linux/Windows réussies.
- **PR #56 fusionnée :** les groupes de sous-titres mot à mot se terminent désormais après une ponctuation de fin de phrase (. ! ?), en plus des règles existantes de longueur maximale et de pause vocale. Commit : `9f08cc0967d30a7abe16a766741067f0ad58aff7`.
- **Pourquoi :** éviter qu'une phrase et la réaction suivante restent affichées dans le même bloc. Les timings DTW et les timings individuels des mots restent inchangés.
- **Robustesse :** le premier mot d'un groupe est traité sans accès à un élément précédent inexistant.
- **Tests :** régression couvrant deux phrases successives et leur séparation.
- **Validation :** PR #55 fermée car basée sur un HEAD dépassé ; PR #56 reprise sur main à jour. CI Linux run `46039322749` et Windows run `46039322643` réussies avant fusion.


- **Complément éditorial :** la sélection de miniature tient désormais compte de réactions francophones (par exemple « incroyable », « dingue », « putain ») et de la ponctuation expressive. Cela évite de favoriser uniquement les mots-clés anglais de l'ancien dictionnaire.
- **Test ajouté :** vérifie qu'un groupe de réaction francophone emphatique est retenu face à une parole neutre.


## 24. Sous-titres et miniatures francophones, 27 novembre 2026

- **PR #56 fusionnée dans `main`** après réussite de la CI Linux et Windows. Commit squash : `9f08cc0967d30a7abe16a766741067f0ad58aff7`.
- **Sous-titres :** chaque groupe mot à mot s'arrête désormais après . ! ? même si la pause est courte. Les limites existantes de quatre mots et de 0,55 s restent actives ; les timestamps originaux ne changent pas.
- **Miniatures :** le choix du timestamp reconnaît davantage de réactions françaises, normalise les accents et donne un poids supplémentaire à la ponctuation expressive.
- **Tests CI PR :** Linux run [46039322749](https://github.com/Sreleew/GTA_rankd/actions/runs/46039322749) et Windows run [46039322643](https://github.com/Sreleew/GTA_rankd/actions/runs/46039322643) réussis. Aucun rendu réel Twitch ni écoute sur le PC utilisateur n'a été effectué dans ce lot.
- **État produit :** stable publiée v0.8.9 ; le lot #56 est intégré dans main mais pas encore publié dans une nouvelle Release.
- **Prochaine action prioritaire :** reprendre le parcours réel Twitch Short et mesurer les défauts du rendu final, notamment l'identification du streamer, le cadrage webcam/gameplay et le rendu des sous-titres. Ne pas étendre « Moments forts ».


## 25. Attribution temporelle des mots avec une seule voix, 27 novembre 2026

- **Problème corrigé :** le mode diarisation conservait tous les mots Whisper lorsqu'un seul locuteur était détecté, y compris ceux hors des segments de parole identifiés.
- **Comportement :** même avec une seule voix, chaque mot doit désormais chevaucher un segment diarizé avec un recouvrement minimal. Les mots non attribués sont écartés ; si aucun mot ne correspond, le statut devient `no_word_attribution`.
- **Compatibilité :** le statut `single_speaker` est conservé lorsque des mots sont attribués. Les seuils de dominance multi-voix, les timings DTW, la transcription et le rendu ne changent pas.
- **Tests :** cas avec un mot streamer dans le segment et un mot hors segment, plus cas sans aucun mot attribuable.
- **Validation :** PR #57 fusionnée après réussite de la CI Linux (`46044003129`) et Windows (`46044002914`). Cette heuristique ne prouve toujours pas l'identité du streamer et ne sépare pas deux voix superposées dans un même segment.


## 26. Premier moteur de rendu Daily Best Of 16:9, 27 novembre 2026

- **Changement produit :** le Daily Best Of ne s'arrête plus au constructeur de sélection. Une sélection de Shorts validés entre 9 et 11 minutes peut maintenant lancer un rendu asynchrone depuis l'interface.
- **Composition :** chaque Short vertical est placé au centre d'une toile 1920 × 1080, avec un arrière-plan agrandi et flouté issu de la même vidéo. Les séquences sont concaténées dans l'ordre choisi. L'audio est normalisé en 48 kHz stéréo ; une piste silencieuse est prévue pour un Short sans audio.
- **Sortie :** MP4 H.264, AAC, 30 FPS, pixel format yuv420p et faststart. AMF est privilégié sur AMD ; si le driver ne s'initialise pas, le rendu réessaie une fois en libx264 CPU. Les Shorts sources ne sont jamais modifiés. Les exports sont rangés dans le dossier local output/bestof/<date>.
- **Interface :** bouton de génération après vérification, tâche asynchrone, interrogation du statut et lien de récupération à la fin.
- **Limites connues à valider :** le statut est conservé en mémoire du serveur et disparaît si l'application redémarre pendant le rendu ; la progression est actuellement par phase, pas un pourcentage FFmpeg détaillé. La qualité visuelle, la synchronisation audio et le temps de rendu doivent être vérifiés sur un épisode réel sous Windows/AMD avant publication stable.
- **Validation automatisée :** tests du graphe FFmpeg et CI Linux/Windows à exécuter sur la PR. Aucune vidéo réelle n'a été rendue dans l'environnement de développement.
- **Méthode :** les prochains lots doivent apporter une avancée fonctionnelle visible et groupée, plutôt qu'une succession de micro-correctifs. Priorités maintenues : création Short Twitch, qualité du Short, Daily Best Of. Ne pas reprendre « Moments forts ».


## 27. Orientation du cadrage Shorts et Daily Best Of, 27 novembre 2026

- **Décision produit confirmée :** ne pas développer d'extraction, de recadrage ou d'overlay webcam séparé. La webcam est déjà présente dans la capture d'écran source et doit rester visible dans le rendu qui conserve l'image entière. Le paramètre historique `webcam_zone` n'est pas une priorité produit.
- **Priorités :** améliorer le parcours de création d'un Short Twitch de bout en bout, puis finaliser le moteur Daily Best Of 16:9. Ne pas détourner du temps vers un composant webcam dédié ni vers « Moments forts ».
- **PR #58 :** le premier échec CI provenait d'un import `pytest` manquant dans un nouveau test de graphe FFmpeg, avant même l'exécution de la suite de tests. Correctif ajouté sur la branche, nouvelle CI requise. Ne pas fusionner avant réussite Linux et Windows.


## 28. Import groupé de clips Twitch pour le workflow Shorts, 27 novembre 2026

- **Fonctionnalité :** le formulaire « Créer un Short » accepte un lot de jusqu'à 10 URLs Twitch, une par ligne. Chaque URL valide crée un job Short indépendant dans la file existante et utilise les mêmes options de montage, sous-titres, hook, branding et audio.
- **Robustesse :** URLs dédupliquées dans le lot ; chaque URL est validée individuellement ; une URL invalide est signalée sans empêcher les autres de partir ; si aucune URL valide ne reste, l'API retourne une erreur claire. La confirmation de droits reste obligatoire et vaut pour toutes les sources du lot.
- **Interface :** panneau repliable sous l'import Twitch simple, retour du nombre de Shorts créés et liste des URLs rejetées.
- **Validation :** tests API ajoutés pour les lots mixtes, la déduplication, les options partagées, l'obligation de confirmation et la limite de 10. Test statique de l'interface ajouté. CI Linux/Windows requise sur la PR.
- **Objectif :** accélérer la préparation quotidienne de plusieurs Shorts et alimenter plus facilement le Clip Bank pour le Daily Best Of. Ce lot ne touche pas à « Moments forts » ni à la webcam.

## 29. Fondation du workflow développeur et cadence de livraison, 27 novembre 2026

- **Retour utilisateur :** le projet doit avancer par lots réellement utiles, sans perdre du temps à réinstaller l'application ou à rejouer toute la suite de tests après chaque petite modification. La cible est un outil propre, rapide, stable et maintenable sur plusieurs années.
- **PR #58 fusionnée :** le moteur Daily Best Of 16:9 est intégré dans main. CI Linux run 46045887877 et Windows run 46045887918 réussies.
- **PR #59 fermée volontairement :** elle a été remplacée par la PR #60, recréée sur main à jour pour éviter un conflit documentaire.
- **PR #60 fusionnée :** import groupé de jusqu'à 10 URLs Twitch dans « Créer un Short », déduplication, validation individuelle et mise en file des URLs valides. CI Linux run 46046378763 et Windows run 46046378773 réussies. Commit de merge 90504c7c282e9032fb2bc9d90cc03f83f018f4e2.
- **PR #61 fusionnée :** fondation du workflow développeur intégrée dans `main`, commit `a90c85c60a10618b7d465da39bb11ba1439a93de`. Scripts PowerShell pour conserver un environnement Python `.venv` et lancer les tests ciblés Shorts/Twitch/Best Of/Web, plus une suite complète réservée aux changements transversaux. Guide : `docs/DEVELOPMENT.md`.
- **CI PR #61 :** Linux [46046826564](https://github.com/Sreleew/GTA_rankd/actions/runs/46046826564) et Windows [46046826607](https://github.com/Sreleew/GTA_rankd/actions/runs/46046826607) réussies.
- **CI post-fusion PR #61 :** Linux [46047244429](https://github.com/Sreleew/GTA_rankd/actions/runs/46047244429) et Windows [46047244465](https://github.com/Sreleew/GTA_rankd/actions/runs/46047244465) réussies.
- **Règle de validation :** ne pas refaire l'installation ni les tests inchangés. Tests ciblés pendant le lot ; CI Linux/Windows avant fusion d'un lot cohérent ; validation manuelle sur le PC AMD uniquement pour les changements qui touchent réellement le rendu ou le matériel. La CI ne prouve jamais la qualité visuelle d'un vrai Short.
- **Décision produit à respecter :** pas de chantier webcam dédié. La capture source contient déjà l'écran complet et la webcam ; conserver ce cadrage. webcam_zone n'est pas une priorité. « Moments forts » reste en pause.
- **Suite :** suivre les lots d'import Twitch jusqu'à leur rendu et leur validation, puis fiabiliser les tâches Daily Best Of persistantes.


## 30. Suivi persistant des lots d'import Twitch, 27 novembre 2026

- **Amélioration produit :** chaque import groupé de clips Twitch reçoit désormais un identifiant de lot durable. Les jobs enregistrent cet identifiant dans SQLite, avec leur position et le nombre total de clips valides.
- **Nouveau suivi API :** `GET /api/shorts/batches/{batch_id}` renvoie l'état agrégé du lot, la progression, les Shorts prêts à valider, les validations et les échecs, ainsi que le statut individuel de chaque URL.
- **Interface :** un panneau de suivi affiche la progression du lot et l'état de chaque clip. Les quatre derniers lots suivis sont conservés dans le stockage local du navigateur pour retrouver leur progression après navigation ou redémarrage de l'application. Le suivi peut être masqué sans supprimer les jobs.
- **Robustesse :** les URLs sont toutes validées avant la création des jobs ; les jobs du lot sont persistés avant leur soumission à la file. Les anciennes bases SQLite sont migrées sans supprimer ni réécrire les jobs existants.
- **Tests :** couverture du lot en attente, du mélange Short prêt/échec, des compteurs, des identifiants invalides/inconnus, de l'interface et de la migration SQLite.
- **PR #62 fusionnée dans `main` :** commit squash `6514b37077cacefd4e9274a0dfa5364ada61871c`.
- **CI PR #62 :** Linux [46048103440](https://github.com/Sreleew/GTA_rankd/actions/runs/46048103440) et Windows [46048103427](https://github.com/Sreleew/GTA_rankd/actions/runs/46048103427) réussies. Le premier passage Linux avait signalé deux tests qui attendaient l'ancienne URL de cache `app.js?v=0.8.9` ; les assertions ont été alignées sur la nouvelle clé `0.8.9-batch-progress`, puis la suite complète a réussi.
- **CI post-fusion #62 :** Linux [46048367366](https://github.com/Sreleew/GTA_rankd/actions/runs/46048367366) et Windows [46048367349](https://github.com/Sreleew/GTA_rankd/actions/runs/46048367349) réussies.
- **Limites :** aucun vrai téléchargement Twitch ni rendu matériel AMD n'a été exécuté. La progression agrégée est validée par tests API et la migration SQLite est couverte, mais le comportement visuel reste à vérifier dans la prochaine version installée.
- **Suite :** valider le parcours complet avec un vrai clip Twitch sur le PC Windows/AMD, puis poursuivre les améliorations de fiabilité du rendu Short avant de traiter la persistance des tâches Daily Best Of.


## 31. Simplification du moteur Short et pause des sous-titres, 27 novembre 2026

- **Décision utilisateur :** mettre tout le chantier sous-titres en pause. Aucun besoin de transcription Whisper, d'identification de voix, de diarisation, de génération SRT ou de contrôle qualité des sous-titres dans le parcours Short actuel.
- **Décision utilisateur :** supprimer le composant et les paramètres dédiés à la webcam. Le cadrage traite la vidéo source comme une image complète ; aucune extraction, zone ou superposition webcam.
- **Étape 1 terminée :** parcours Short cartographié de l'import Twitch au rendu et au contrôle qualité. L'import groupé et son suivi persistant sont déjà intégrés dans main.
- **Étape 2 en cours :** réduire le travail inutile dans le chemin de rendu. L'analyse audio reste conditionnelle : pas d'extraction WAV si le clip est sous le seuil de recadrage automatique et que le zoom dynamique est désactivé. Si elle est nécessaire, les pics et accents sont calculés en une seule lecture ; Whisper et la diarisation sont retirés du workflow. Le recadrage automatique autour du pic reste actif pour les sources qui dépassent le seuil. Le hook, le branding, le whoosh, la miniature, le cadrage et l'encodage restent actifs.
- **Interface :** retrait des options de sous-titres et de sélection de voix, qui ne doivent plus suggérer une fonctionnalité active.
- **Optimisations additionnelles :** les pics audio et les accents pour le zoom sont maintenant calculés en une seule lecture du WAV au lieu de deux. La liste des encodeurs FFmpeg est mise en cache pour éviter de relancer `ffmpeg -encoders` à chaque Short d'un lot.
- **API et compatibilité :** les champs webcam ont été retirés des endpoints de scan et d'import. Les champs de sous-titres ont été retirés des endpoints Short ; les anciennes métadonnées de jobs restent lisibles mais ne déclenchent plus de transcription.
- **Validation :** vérifier les tests ciblés worker, renderer et interface, puis CI Linux/Windows. Ne pas annoncer de gain chiffré sans mesure sur une source réelle.
- **À ne pas reprendre dans les prochains lots :** sous-titres, diarisation, webcam, « Moments forts ». Priorité : temps de traitement, robustesse du téléchargement et du rendu Short.


## 32. Fiabilisation de l'installation FFmpeg dans la CI Windows, 27 novembre 2026

- **Constat :** la CI Windows échouait sur l'installation Chocolatey de FFmpeg avec une réponse HTTP 504 du dépôt communautaire, avant les tests de l'application.
- **Correctif :** remplacer cette dépendance à Chocolatey par le téléchargement direct de l'archive Windows statique FFmpeg depuis les releases BtbN, puis ajouter son dossier `bin` au PATH du runner.
- **Portée :** uniquement l'environnement de validation GitHub Actions ; aucun changement dans l'installation locale utilisateur.
- **Validation :** la CI Windows doit confirmer l'URL de release, l'extraction et la présence de ffmpeg/ffprobe avant fusion.


## 33. Réutilisation des métadonnées FFprobe dans le workflow Short, 27 novembre 2026

- **Constat :** le worker analysait déjà le fichier source pour déterminer sa durée, ses pistes et les paramètres de coupe, puis le renderer relançait FFprobe sur le même fichier. Après le rendu, le renderer analysait le MP4 exporté, puis le contrôle qualité relançait encore FFprobe sur ce même export.
- **Changement :** le worker transmet maintenant les métadonnées source déjà obtenues au renderer. Le renderer renvoie également les métadonnées du MP4 qu'il vient de vérifier, et le contrôle qualité les réutilise.
- **Résultat attendu :** deux appels FFprobe redondants supprimés par Short, tout en conservant l'analyse source, la vérification des dimensions exportées et les contrôles qualité image/son.
- **Compatibilité :** les paramètres restent facultatifs. Les appels directs au renderer et au contrôle qualité qui ne fournissent pas de métadonnées continuent d'effectuer leur propre probe.
- **Tests ajoutés :** vérifier que le renderer ne reprobe pas la source lorsqu'elle est déjà connue et que le contrôle qualité ne reprobe pas l'export lorsqu'il reçoit les métadonnées validées.
- **Validation :** CI Linux et Windows requise avant fusion. Aucun benchmark chronométré sur une vidéo Twitch réelle ni sur le GPU AMD local n'a encore été effectué.
- **Suite étape 2 :** examiner le coût du contrôle qualité FFmpeg et du choix de miniature sans dégrader la fiabilité ni le résultat visuel. Ne pas désactiver les contrôles ni réduire la qualité par défaut sans mesure.


## 34. Mesure des temps de traitement Short, 27 novembre 2026

- **Objectif :** rendre les prochaines optimisations guidées par les vrais coûts sur le PC Windows/AMD, plutôt que de deviner où le temps est passé.
- **Métadonnées du Short :** ajout de `processing_timings_ms` dans `meta.json`, avec téléchargement, calcul du hash, probe source, analyse audio, génération des métadonnées, sound effect, contrôle qualité, finition miniature et durée totale.
- **Détail FFmpeg :** le renderer ajoute le temps d'encodage, le probe du fichier exporté, la génération de miniature et son temps total.
- **Diagnostic :** ajout de `audio_analysis_skipped` pour distinguer les clips qui évitent réellement l'extraction audio de ceux qui en ont besoin.
- **Impact :** mesures uniquement, aucun changement au rendu ou à la qualité. Le coût est limité à quelques appels à `perf_counter`.
- **Livraison :** PR #66 fusionnée après succès CI Linux et Windows, y compris la suite de régression Windows et la génération du package de mise à jour.
- **Suite :** après un vrai rendu sur la machine utilisateur, exploiter ces durées pour prioriser le goulot dominant. Ne pas publier de chiffres de performance avant cette mesure réelle.


## Journal de développement récent

- **27 novembre 2026, lot de visibilité des performances Short :** PR #67 fusionnée dans `main` après réussite des CI Linux et Windows. Le panneau repliable « Temps de traitement » est visible sur les cartes de Shorts prêts/validés ; il détaille la préparation, l'encodage, le contrôle qualité, le temps total et les cas où l'analyse audio a été sautée. Les clés de cache CSS/JS ont été incrémentées pour forcer le chargement de l'interface actualisée. Commit squash `e691081b66a69628870b81383b558ae92786dac8`. CI PR Linux [46055670321](https://github.com/Sreleew/GTA_rankd/actions/runs/46055670321) et Windows [46055670259](https://github.com/Sreleew/GTA_rankd/actions/runs/46055670259) réussies. Les validations post-fusion Linux [46056087073](https://github.com/Sreleew/GTA_rankd/actions/runs/46056087073) et Windows [46056087077](https://github.com/Sreleew/GTA_rankd/actions/runs/46056087077) étaient en cours au moment de cette mise à jour documentaire.
- **Méthode de compte rendu :** à chaque relance, annoncer le nombre de lots estimés avant la prochaine Release v0.9.0 et réviser cette estimation selon les résultats réels. La prochaine release doit regrouper plusieurs améliorations cohérentes, pas un patch isolé.


## 35. Pilotage proactif et décisions produit, 27 novembre 2026

- **Consigne utilisateur :** l'utilisateur ne connaît pas le développement et délègue le pilotage technique et produit. Il attend que l'assistant le guide activement, anticipe les besoins et pousse le concept GTA Ranked Studio aussi loin que pertinent.
- **Responsabilité de l'assistant :** choisir les solutions techniques adaptées, fixer l'ordre des priorités, identifier les risques avant qu'ils deviennent des problèmes et expliquer les décisions dans un langage simple. Ne pas transférer à l'utilisateur les arbitrages techniques qu'il n'est pas équipé pour faire.
- **Discipline ROI :** évaluer chaque idée selon sa valeur réelle pour le workflow, le coût de développement, la vitesse de traitement, l'expérience utilisateur, la fiabilité et la maintenance. Déconseiller franchement une idée trop complexe, lente, fragile, inutile ou peu rentable. Préférer une solution plus simple quand elle atteint le même résultat. Ne pas ajouter une fonctionnalité uniquement parce qu'elle est techniquement possible.
- **Ambition :** être proactif sur les améliorations de produit, de design, de performance et d'automatisation, tout en évitant la sur-ingénierie. Garder les deux priorités en tête : Créer un Short depuis Twitch, puis Daily Best Of. Moments forts, sous-titres et composants webcam restent hors périmètre tant que l'utilisateur ne les réactive pas.
- **Suivi après chaque relance :** indiquer le lot terminé/en cours, l'état PR/CI, une estimation de progression vers la prochaine release et le nombre approximatif de lots restants. Réviser cette estimation selon le travail réellement restant, sans annoncer de date artificielle.
- **État du lot du jour :** PR #67 fusionnée. La v0.9.0 reste une cible de regroupement, pas une promesse de date. Estimation actuelle : environ 25 % du regroupement réalisé, avec 2 à 3 lots substantiels à terminer avant de décider si le contenu est assez cohérent pour publier. Le prochain jalon doit apporter une amélioration fonctionnelle visible au parcours Short Twitch, et non une suite de micro-optimisations isolées.


## 36. Relance fiable des clips dans un lot Twitch, 27 novembre 2026

- **Objectif produit :** permettre de réparer un lot de Shorts sans retrouver chaque clip dans la file générale. Les clips en erreur, annulés ou rejetés doivent pouvoir être relancés directement depuis leur lot.
- **Portage sur main :** l'ancienne PR #63 était basée sur une version antérieure de main et ne pouvait pas être fusionnée à cause de conflits. Ses changements ont été réappliqués sur une branche issue de main à jour, sans réintroduire les anciens champs et contrôles de sous-titres qui ont depuis été retirés du workflow Short.
- **API de relance :** autoriser également la reprise d'un job annulé ; conserver l'URL Twitch d'origine même lorsque le fichier local est réutilisé ; si ce fichier disparaît plus tard, utiliser l'URL Twitch conservée comme solution de secours ; transmettre l'identifiant du lot au nouveau job. Pour éviter les doubles mises en file après un clic répété ou une réponse réseau lente, l'API refuse aussi de relancer une ancienne tentative lorsqu'une tentative plus récente existe déjà pour le même emplacement du lot.
- **Progression cohérente :** une relance reste le même clip logique. L'API groupe les tentatives par position dans le lot et n'agrège que la tentative la plus récente. Le total, les compteurs et le pourcentage ne gonflent donc pas à chaque relance. Le nombre de tentatives et l'état de relance sont renvoyés à l'interface.
- **Interface :** ajout d'actions « Relancer » ou « Recréer » directement sur les lignes du suivi de lot, avec état de chargement, message de confirmation et rafraîchissement du suivi. La clé de cache des assets statiques est mise à jour.
- **Tests :** couverture de la relance d'un échec dans un lot, de la stabilité du total/progrès, de la reprise d'un job annulé, de la conservation de l'URL Twitch lors de la réutilisation du média local et du fallback URL si ce média disparaît.
- **Livraison :** PR #68 (`Retry failed Twitch clips from their batch tracker`) fusionnée dans `main`, commit squash `c7fce9dc3bf109db5002be739575465f22753caa`. L'ancienne PR #63, basée sur un main obsolète et en conflit, a été fermée sans fusion après portage des changements.
- **Validation PR #68 :** Linux [46058227244](https://github.com/Sreleew/GTA_rankd/actions/runs/46058227244) réussi avec 223 tests passés et 1 ignoré ; Windows [46058227385](https://github.com/Sreleew/GTA_rankd/actions/runs/46058227385) réussi, avec validation PowerShell et package Windows. Le premier passage avait échoué sur deux assertions de cache statique obsolètes ; elles ont été corrigées avant la réussite finale. Le contrôle post-fusion Linux [46058529239](https://github.com/Sreleew/GTA_rankd/actions/runs/46058529239) a échoué sur le test atomique de miniature introduit trop tôt dans `main`, avant son implémentation. Le correctif complet est préparé dans la PR #69. Le contrôle post-fusion Windows [46058529270](https://github.com/Sreleew/GTA_rankd/actions/runs/46058529270) a échoué sur le même test atomique de miniature, pour la même raison. Aucun téléchargement Twitch réel ni rendu matériel AMD n'est revendiqué.
- **Suite :** vérifier le parcours sur l'installation locale à la prochaine release regroupée. La prochaine optimisation est le traitement non fatal de l'habillage de miniature, afin qu'une erreur de couverture ne fasse pas perdre un MP4 déjà rendu. La v0.9.0 reste une cible de regroupement ; estimation après PR #68 : environ 40 %, avec environ 2 lots substantiels à terminer avant de juger le contenu suffisant.


## 37. Préserver un Short si l'habillage de miniature échoue, 27 novembre 2026

- **Problème identifié :** l'habillage graphique de la miniature était exécuté après le rendu vidéo et le contrôle qualité, mais une erreur Pillow, une police indisponible ou un problème disque faisait remonter l'exception jusqu'au worker. Le job entier passait alors en erreur alors que le MP4 était déjà rendu et contrôlé. L'utilisateur devait relancer inutilement tout le traitement.
- **Fiabilité du fichier :** l'habillage écrit désormais le JPEG final dans un fichier temporaire du même dossier, puis remplace la miniature source uniquement après un encodage réussi. En cas d'échec, le frame extrait par FFmpeg reste intact.
- **Worker :** une erreur d'habillage devient un avertissement non bloquant. Le Short reste prêt pour validation avec sa miniature source non décorée ; les métadonnées enregistrent `thumbnail_overlay_status` et un message de diagnostic court. Les erreurs du rendu vidéo et du contrôle qualité restent inchangées.
- **Interface :** les cartes de Shorts indiquent clairement lorsque l'image source a été conservée sans habillage, afin de ne pas faire croire que la couverture premium a été appliquée.
- **Tests :** écriture atomique et conservation des octets originaux si la sauvegarde échoue ; statut fallback et succès du helper worker ; présence du message de diagnostic dans l'interface. La première CI Linux a révélé deux assertions de cache oubliées dans les tests de vérification Whisper/Ollama ; elles ont été alignées sur la nouvelle clé `0.8.9-thumbnail-fallback`.
- **Branche :** `fix/thumbnail-overlay-fallback-mainline`. CI Linux/Windows à vérifier sur la PR. Aucun rendu matériel AMD ni panne réelle sur une installation utilisateur n'est simulé.
- **Arbitrage ROI :** ne pas relancer un encodage vidéo coûteux pour un simple échec de couverture. Le MP4 reste la livraison principale ; la miniature brute reste utilisable et l'interface signale la finition manquante.
- **Prévention de régression de méthode :** après le déclenchement accidentel du test de régression sur `main` avant l'implémentation correspondante, `docs/WORKING-AGREEMENT.md` ajoute une règle explicite : aucune écriture directe sur `main`, branche de travail toujours fournie explicitement à chaque mise à jour.


## 38. Persistance des rendus Daily Best Of, 27 novembre 2026

- **Problème ciblé :** les rendus Best Of étaient conservés uniquement dans un dictionnaire mémoire du serveur. Un rechargement de page perdait le suivi côté navigateur et un redémarrage du Studio supprimait complètement l'état et le lien de téléchargement.
- **Persistance SQLite :** nouvelle table `best_of_jobs` pour stocker l'identifiant, le statut, la progression, le message, la date compilée, le nombre et la durée des Shorts, le plan complet, le chemin et l'URL d'export, le résultat de rendu, l'erreur et les horodatages.
- **Récupération au démarrage :** les rendus restés `queued` ou `running` lors d'un arrêt sont signalés comme interrompus au redémarrage. Aucun rendu automatique n'est relancé afin d'éviter de consommer le GPU ou de créer un doublon sans action explicite. Le plan de sélection reste stocké.
- **API :** ajout de la liste des 10 derniers rendus et remplacement de la lecture mémoire par une lecture SQLite pour le détail d'un rendu. L'API ne renvoie un lien de téléchargement que si le fichier exporté existe encore sur le PC.
- **Interface :** ajout de l'historique des épisodes dans la page Daily Best Of, avec date, nombre de clips, durée, état, progression et lien de téléchargement. Les rendus actifs sont actualisés automatiquement lorsque la page Best Of est ouverte. L'historique reste consultable après navigation ou rechargement.
- **Tests :** sérialisation du plan et du résultat, conservation des rendus terminés, récupération des tâches interrompues, rendu asynchrone simulé, API liste/détail et persistance après recréation de l'application.
- **Livraison :** PR #72 fusionnée dans `main`, commit squash `3b54a397720b62e3cb3026dbc66fcdc6bf1ca646`. La branche a été réalignée sur le main mis à jour après la PR #69, afin de conserver la correction de secours miniature.
- **CI PR #72 :** Linux [46059970125](https://github.com/Sreleew/GTA_rankd/actions/runs/46059970125) et Windows [46059970150](https://github.com/Sreleew/GTA_rankd/actions/runs/46059970150) réussies. Windows a exécuté les tests complets, vérifié les scripts PowerShell et généré/vérifié le package Windows.
- **CI post-fusion :** Linux [46060274973](https://github.com/Sreleew/GTA_rankd/actions/runs/46060274973) et Windows [46060274965](https://github.com/Sreleew/GTA_rankd/actions/runs/46060274965) réussies.
- **Arbitrage ROI :** pas de reprise automatique d'un encodage interrompu. Le plan reste mémorisé, mais l'utilisateur décide explicitement de relancer pour éviter une consommation GPU inattendue ou un doublon.
- **Limite :** aucun encodage réel sur la RX 9060 XT n'a été exécuté. La qualité visuelle et le temps d'encodage doivent encore être vérifiés sur le PC utilisateur.
- **Progression v0.9.0 :** environ 65 % du regroupement estimé. Prévoir 1 à 2 lots substantiels, dont une vérification réelle du flux et une dernière amélioration à forte valeur, avant de préparer la release. La v0.9.0 reste une cible, sans date artificielle.


## 39. Relance manuelle d'un Daily Best Of depuis l'historique, 27 novembre 2026

- **Besoin produit :** la persistance de l'historique permettait d'identifier un épisode interrompu, mais il fallait encore reconstruire manuellement la sélection avant de pouvoir le relancer.
- **Action utilisateur :** les épisodes en erreur ou interrompus affichent une action « Relancer le rendu » dans l'historique. La sélection originale et la date sont réutilisées ; l'utilisateur n'a pas à rechoisir les Shorts.
- **Sécurité et cohérence :** avant toute relance, l'API vérifie que les Shorts sont toujours dans la bibliothèque, validés, présents sur le disque et cohérents avec la journée. Les rendus réussis ou encore actifs ne peuvent pas être relancés via l'action de récupération.
- **Anti-doublon :** chaque nouvel épisode conserve l'identifiant de la tentative d'origine dans son plan. Une deuxième relance de la même tentative est refusée si la relance précédente est en attente, en cours ou terminée. Une tentative qui échoue peut elle-même être relancée depuis sa propre ligne d'historique.
- **Interface :** bouton de relance désactivé pendant l'envoi, message de confirmation/erreur et rafraîchissement de l'historique. Aucun encodage n'est automatiquement démarré au redémarrage.
- **Tests ajoutés :** endpoint de relance, conservation de la sélection, rendu simulé de la nouvelle tentative, refus des relances depuis un épisode terminé et blocage du double clic/duplicata.
- **Branche :** `feat/retry-daily-bestof-from-history`. CI Linux et Windows à exécuter sur la PR.
- **Arbitrage ROI :** réutiliser le plan déjà persisté est plus simple et plus sûr que créer un deuxième système de sauvegarde/reconstruction d'épisode.
- **Suite :** après validation, la prochaine priorité est de préparer une validation utilisateur guidée de la création Short et du Daily Best Of sur l'installation Windows/AMD, puis de décider si la v0.9.0 est prête.


## 39. Préserver la composition Twitch complète dans le cadrage intelligent, 27 novembre 2026

- **Objectif :** éviter que le cadrage vertical « smart » coupe une webcam déjà intégrée au clip Twitch lorsqu'elle se trouve sur un bord de l'image.
- **Rendu :** le panneau central utilise désormais une version complète de la source ajustée à sa zone. Une copie floutée remplit l'espace restant dans le panneau, tandis que le fond vertical conserve le traitement existant. Les bandes latérales de la vidéo 16:9 ne sont plus coupées.
- **Périmètre webcam :** aucune détection, extraction ou superposition séparée n'est ajoutée. Le studio conserve la composition Twitch telle qu'elle est fournie par le clip, conformément à la décision de ne pas construire de composant webcam dédié.
- **Interface :** le format est renommé « Composition éditoriale 9:16 » et précise que l'image Twitch entière, webcam comprise, est préservée. La clé de cache statique est mise à jour.
- **Tests :** tests de graphe pour sources paysage et portrait, plus un test FFmpeg réel avec des bandes colorées sur les deux bords afin de vérifier que le contenu périphérique survit au rendu vertical.
- **Sous-titres :** le brief actuel les mentionne à nouveau, mais le pipeline actif ne les génère toujours pas depuis la simplification précédente. Leur éventuelle réactivation doit être traitée dans un lot dédié, avec un mode facultatif et un budget de temps explicite, plutôt que de réintroduire Whisper silencieusement dans chaque rendu.
- **Livraison :** PR #74 fusionnée dans `main`, commit squash `9603a753f8d9d05f0bf23dddd5a065991cab4e74`. CI PR Linux [46062092402](https://github.com/Sreleew/GTA_rankd/actions/runs/46062092402) et Windows [46062092452](https://github.com/Sreleew/GTA_rankd/actions/runs/46062092452) réussies, incluant le test FFmpeg de préservation des bords gauche et droit. Aucun rendu sur le PC AMD de l'utilisateur n'est revendiqué.


## 40. Relance des rendus Best Of et validation post-fusion, 27 novembre 2026

- **PR #73 fusionnée** dans `main`, commit squash `1d76b571f1110e09109b0cc980f66530a9db104b`. La relance manuelle d'un rendu Daily Best Of en erreur recrée un job à partir du plan et de la sélection stockés, sans relancer automatiquement les tâches interrompues au démarrage. L'interface propose « Relancer le rendu » dans l'historique ; les doublons de relance sont refusés.
- **Validation PR #73 :** Linux [46060698981](https://github.com/Sreleew/GTA_rankd/actions/runs/46060698981) et Windows [46060698891](https://github.com/Sreleew/GTA_rankd/actions/runs/46060698891) réussies. **Contrôles post-fusion :** Linux [46061031450](https://github.com/Sreleew/GTA_rankd/actions/runs/46061031450) et Windows [46061031449](https://github.com/Sreleew/GTA_rankd/actions/runs/46061031449) réussis.
- **PR #74 fusionnée :** `feat/preserve-full-source-in-smart-layout`, commit squash `9603a753f8d9d05f0bf23dddd5a065991cab4e74`. Le layout smart ajuste l'image complète au panneau central et utilise une copie floutée pour remplir l'espace restant ; les bords et une webcam déjà intégrée à la vidéo restent visibles sans extraction séparée.
- **Tests du lot #74 :** assertions de graphe pour sources paysage/portrait et test FFmpeg réel avec marqueurs de couleur sur les deux bords. CI Linux/Windows réussies après mise à jour de trois assertions de cache qui attendaient l'ancienne clé `0.8.9-bestof-history`. La suite finale compte 230 tests réussis et 1 ignoré sous Linux ; 231 réussis sous Windows.
- **Sous-titres :** le brief de développement actuel les mentionne de nouveau, alors que la simplification précédente les avait mises en pause. Ne pas réintroduire Whisper sans contrôle : préparer un lot dédié avec activation explicite, comportement de secours si le modèle est absent et mesure du coût, afin de ne pas ralentir silencieusement chaque Short.
- **Progression v0.9.0 :** cible de regroupement toujours non publiée. Estimation révisée à environ 65 % ; prévoir 1 à 2 lots substantiels après validation du cadrage complet et examen du parcours Short sur la machine Windows/AMD. Pas de date de publication promise.


## 41. Progression réelle du rendu Daily Best Of, 27 novembre 2026

- **Problème ciblé :** pendant l'encodage 16:9, la tâche affichait essentiellement un message générique et une progression fixe. Sur un épisode de 9 à 11 minutes, l'utilisateur ne pouvait pas savoir si le rendu avançait ou était bloqué.
- **Mesure réelle :** FFmpeg est lancé avec son protocole `-progress pipe:1`. Le processus envoie les timestamps réellement encodés ; ils sont comparés à la durée totale prévue pour calculer la progression de l'épisode. Aucun pourcentage fictif fondé uniquement sur le temps écoulé n'est affiché.
- **Robustesse du processus :** nouveau helper cross-platform qui lit en continu les sorties FFmpeg dans un thread dédié, vérifie le timeout et l'annulation, évite le blocage des pipes, masque la console Windows et ne laisse pas une exception du callback interrompre la vidéo.
- **Phases visibles :** vérification des sources, encodage avec pourcentage réel, contrôle de l'export final. Si AMF échoue et que le renderer repart en libx264 CPU, le statut annonce le fallback et la progression revient au début du nouvel encodage au lieu de conserver un faux pourcentage.
- **Interface :** l'historique Best Of affiche également le pourcentage numérique à côté de la barre de progression. Le rafraîchissement existant de 2,5 secondes suffit ; aucune interrogation réseau supplémentaire n'est ajoutée.
- **Tests ajoutés :** lecture des timestamps FFmpeg, sortie d'échec, annulation du processus, tolérance aux erreurs du callback, callback de progression dans le renderer et propagation du callback par l'API. Les tests utilisent un processus Python et un renderer simulé ; aucun véritable temps d'encodage AMD n'est revendiqué.
- **Livraison :** PR #75 fusionnée dans `main`, commit squash `f016dbe94abeff0bdbac26d282d70bd0236ba77e`. Clé de cache des assets `0.8.9-bestof-live-progress`.
- **CI PR #75 :** Linux [46063430324](https://github.com/Sreleew/GTA_rankd/actions/runs/46063430324) et Windows [46063430259](https://github.com/Sreleew/GTA_rankd/actions/runs/46063430259) réussies. Linux et Windows ont exécuté leurs suites complètes ; Windows a aussi construit et vérifié le package de mise à jour. Les contrôles post-fusion Linux [46063753298](https://github.com/Sreleew/GTA_rankd/actions/runs/46063753298) et Windows [46063753309](https://github.com/Sreleew/GTA_rankd/actions/runs/46063753309) sont en cours.
- **Arbitrage ROI :** réutiliser les rapports de progression natifs FFmpeg plutôt qu'ajouter un mécanisme de polling ou d'estimation séparé. Le coût supplémentaire est limité à la lecture des lignes de progression pendant le rendu.
- **Progression v0.9.0 :** environ 85 % du regroupement technique estimé. Il reste principalement une validation guidée sur la machine Windows/AMD du flux Twitch vers Short et d'un rendu Daily Best Of réel, puis les éventuels ajustements réellement nécessaires avant une Release candidate. Ne pas annoncer de performance matérielle sans mesure locale.
- **Suite prioritaire :** validation sur le PC Windows/AMD dès qu'une version regroupée est disponible. Exploiter ensuite les temps mesurés pour ne modifier que le goulot réellement observé.


## 42. Progression réelle du rendu Short Twitch, 27 novembre 2026

- **Problème ciblé :** pendant l'encodage vertical, le job restait sur un pourcentage fixe malgré un rendu parfois long. Le message ne permettait pas de distinguer un encodage lent d'un traitement bloqué.
- **Mesure réelle :** le renderer peut activer le protocole FFmpeg `-progress pipe:1` et convertir les timestamps média encodés en progression basée sur la durée de l'extrait. Le mécanisme reste facultatif pour préserver les appels existants.
- **Interface :** le worker mappe l'encodage de 60 à 85 %, affiche le pourcentage dans le message du job et ajoute une valeur numérique à côté de la barre de progression. Le contrôle qualité commence ensuite à 88 % comme auparavant.
- **Encodeurs :** la même mesure s'applique à AMD AMF et à l'encodeur CPU de secours. Chaque tentative redémarre à zéro pour éviter un pourcentage trompeur après un fallback.
- **Tests :** le test simulé vérifie l'activation du protocole FFmpeg, la conversion des timestamps en pourcentage et la tolérance à une erreur du callback initial. Un test de fallback vérifie que la progression repart de zéro si AMF échoue et que libx264 prend le relais. Le test d'intégration FFmpeg réel vérifie une progression bornée et monotone jusqu'à la fin de l'encodage. Aucun rendu sur la RX 9060 XT n'est revendiqué.
- **Branche :** `feat/short-render-live-progress`. Clé de cache des assets `0.8.9-short-live-progress`.
- **Arbitrage ROI :** réutiliser le helper de progression FFmpeg du Daily Best Of, sans polling additionnel ni minuterie fictive.
- **Suite :** tests ciblés Linux/Windows, puis validation de la PR. La vérification réelle sur Windows/AMD reste à faire sur le PC utilisateur.


## 43. Sous-titres Whisper locaux facultatifs pour les Shorts, 27 novembre 2026

- **Problème ciblé :** le pipeline Short n'utilisait plus la transcription, donc les rendus standards ne contenaient pas de sous-titres et les hooks/titres ne pouvaient pas exploiter les paroles.
- **Choix ROI :** transcription strictement facultative, désactivée par défaut. Aucun modèle n'est téléchargé automatiquement et aucun coût Whisper n'est ajouté au rendu standard. L'activation nécessite le moteur whisper.cpp et le modèle local large-v3-turbo valide (~1,6 Go), vérifiés avant de mettre un upload ou une URL Twitch en file.
- **Périmètre :** l'audio du seul extrait final sélectionné est transcrit. Le WAV déjà extrait pour l'analyse audio est réutilisé s'il correspond exactement à la plage ; sinon, FFmpeg extrait uniquement la plage Short. La transcription reste locale. La durée finale est validée avant Whisper : une source trop longue sans recadrage automatique échoue immédiatement au lieu de lancer une transcription coûteuse vouée à être refusée au rendu.
- **Rendu :** les mots horodatés DTW sont privilégiés ; le SRT par segments reste le fallback du moteur. Les mots alimentent les captions ASS et le transcript fourni à la génération des métadonnées. Le SRT est conservé à côté du MP4 lorsqu'il existe. Le contrôle qualité vérifie les captions lorsqu'elles ont réellement été générées.
- **Tolérance aux pannes :** si la source n'a pas d'audio ou si Whisper échoue après démarrage, le MP4 reste généré sans captions et l'interface affiche explicitement l'avertissement. Si le moteur ou le modèle manque dès la demande, l'API refuse la mise en file avec une explication avant de télécharger la source. L'échec de copie du SRT annexe ne bloque pas le MP4 lorsque les captions sont déjà intégrées.
- **Compatibilité :** aucun changement de dépendance ni d'encodeur. Le chemin AMD AMF et le fallback libx264 sont inchangés. Le choix de captions est conservé dans les options du job et donc dans une relance.
- **Mesure du coût :** la durée Whisper est enregistrée dans les timings du job et affichée dans le rapport « Temps de traitement » pour comparer le coût réel de la transcription avec et sans l'option.
- **Tests ajoutés :** validation API du prérequis Whisper, persistance de l'option sur upload, URL et lot Twitch, réutilisation du WAV correspondant, extraction exacte de la plage lorsque le WAV existant couvre une autre durée, et vérification de l'affichage du résultat et du timing.
- **Cache UI :** `0.8.9-short-live-progress-captions`.
- **Limites :** les tests ne mesurent pas encore la vitesse réelle de Whisper sur la RX 9060 XT. Le modèle large-v3-turbo reste volontairement optionnel ; une transcription longue peut prolonger le traitement lorsque l'option est activée.
- **Suite :** validation CI Linux/Windows de la PR groupée, puis validation manuelle sur un clip Twitch réel avec le modèle présent, en comparant durée de transcription, synchronisation et lisibilité mobile.


## 44. Préparation de la release v0.9.0, 27 novembre 2026

- **Décision :** l'utilisateur a demandé la publication stable v0.9.0 après intégration et validation de la PR #76.
- **Contenu :** la version regroupe l'import et la relance de lots Twitch, le cadrage 9:16 qui préserve l'image complète, la progression réelle du rendu Short et Best Of, les sous-titres Whisper locaux facultatifs, le rendu Daily Best Of persistant et la récupération manuelle des épisodes interrompus.
- **Version :** `VERSION.txt`, `app/VERSION.txt`, `app/pyproject.toml`, `app/config.yaml.default`, les notes de version et `.release-approval` sont synchronisés en `0.9.0` sur la branche `release/v0.9.0`.
- **Validation déjà obtenue :** la PR #76 a passé l'audit Linux et la validation Windows, y compris les régressions, l'audit de dépendances, les scripts PowerShell et le package Windows.
- **Limite :** le workflow ne remplace pas la validation physique AMD : AMF, Vulkan et la vitesse Whisper sur la RX 9060 XT restent à mesurer sur le PC utilisateur après installation.
- **Publication :** PR #77 fusionnée, commit squash `2e5510ca4084d3876a33dc5a26be259d49d642f6`. Le workflow officiel [46069811823](https://github.com/Sreleew/GTA_rankd/actions/runs/46069811823) a réussi et publié la Release v0.9.0, son ZIP Windows et `SHA256SUMS.txt`.
- **Contrôles post-fusion :** Linux [46069811810](https://github.com/Sreleew/GTA_rankd/actions/runs/46069811810) et Windows [46069811807](https://github.com/Sreleew/GTA_rankd/actions/runs/46069811807) réussis.
- **Suite :** installer v0.9.0 sur le PC Windows/AMD de test, puis mesurer AMF, Vulkan et Whisper sur de vrais médias avant le prochain lot.


## 45. Langue des sous-titres Whisper configurable par Short, 27 novembre 2026

- **Problème ciblé :** les nouveaux rendus utilisaient toujours la langue globale configurée (anglais par défaut), ce qui rendait les sous-titres moins fiables pour les clips français ou multilingues malgré le modèle Whisper large-v3-turbo multilingue.
- **Amélioration :** ajout d'un sélecteur de langue dans les deux parcours de création Short (upload et URL/lot Twitch) : réglage du Studio, détection automatique, anglais, français, espagnol, portugais et allemand.
- **Compatibilité des réglages :** le choix par défaut « Réglage du Studio » conserve la valeur transcription.language existante. L'utilisateur peut choisir explicitement auto ou une langue sans modifier sa configuration globale. Les anciens jobs sans caption_language continuent d'utiliser la configuration existante.
- **Pipeline :** la langue choisie est validée côté API, persistée dans les options du job, transmise à whisper.cpp via le paramètre -l, conservée lors d'une relance et enregistrée dans les métadonnées du rendu (langue demandée et langue effectivement passée au moteur).
- **Modèle :** clarification de l'interface : ggml-large-v3-turbo est présenté comme modèle multilingue, pas comme modèle anglais uniquement.
- **Tests :** validation de l'allowlist API, persistance des langues distinctes sur upload, URL et import groupé, rejet d'une langue invalide, et vérification des arguments -l fr et -l auto dans les tests du moteur Whisper DTW/SRT.
- **Premier retour CI :** 238 tests passés et 1 ignoré ; deux tests UI échouaient uniquement parce qu'ils attendaient encore l'ancienne clé de cache 0.8.9. Les deux assertions ont été alignées sur 0.9.0-short-caption-language ; la validation finale doit confirmer la correction.
- **Cache UI :** 0.9.0-short-caption-language.
- **Version :** aucun numéro de version ni fichier d'approbation de release modifié. La Release publique reste v0.9.0 ; cette évolution est destinée à une prochaine release.
- **Validation :** CI Linux/Windows de la PR à vérifier avant fusion. Aucun rendu Whisper réel ni mesure sur la RX 9060 XT n'est revendiqué.
- **Suite :** valider les deux plateformes, puis tester sur un clip français et un clip anglais en mode auto et en langue forcée ; comparer la qualité des mots, la synchronisation et le temps de transcription.


## 46. Direction artistique par défaut des miniatures, 27 novembre 2026

- **Demande utilisateur :** appliquer aux futures miniatures la composition validée sur l'exemple CaseOh, avec une esthétique plus directement GTA, une typographie nette et peu d'éléments de marque.
- **Implémentation :** refonte du compositeur Pillow dans `app/studio/web/short_editor.py`. Le rendu garde une vraie image du clip, un fond assombri, un papier noir aux bords irréguliers, un seul aplat jaune sous le hook, une police condensée système, le nom du streamer et la signature `GTA_Rankd`. Aucun texte ni visuel n'est confié à un générateur d'images.
- **Test ajouté :** contrôle du format vertical 1080 × 1920 et de la présence de la palette jaune/noir sur le bandeau du hook.
- **Branche :** `feat/gta-thumbnail-default-art-direction`.
- **Limites :** le rendu automatique conserve la frame vidéo réelle et n'extrait pas une webcam séparée ; sa position dépend donc de la composition de la source.
- **CI PR #81 :** audit Linux [46076837564](https://github.com/Sreleew/GTA_rankd/actions/runs/46076837564) et validation Windows [46076837526](https://github.com/Sreleew/GTA_rankd/actions/runs/46076837526) réussis après correction du chevauchement du bandeau avec la frame de gameplay.
- **Version :** v0.9.1 publiée le 27 novembre 2026 pour intégrer le template de miniatures dans l'application.
- **Intégration :** PR #81 fusionnée dans `main`, commit squash `398afdb47ef649970d14b5cc1f1764ee1b3c282e`.
- **Release :** PR #83 fusionnée ; workflow officiel [46078578681](https://github.com/Sreleew/GTA_rankd/actions/runs/46078578681) réussi. La [v0.9.1](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.9.1) et son ZIP Windows sont publiés.
- **Suite :** installer v0.9.1 et examiner une miniature issue d'un nouveau Short réel.


## 47. Correction des sous-titres absents du rendu final, 28 novembre 2026

- **Problème trouvé sur main :** le worker calculait correctement la présence de mots Whisper, puis réinitialisait systématiquement `captions_active` à `False` juste avant la création du fichier ASS. Les sous-titres demandés n'étaient donc jamais intégrés au MP4 et le contrôle qualité ne les vérifiait pas.
- **Correction :** `captions_active` est maintenant déterminé une seule fois à partir de deux conditions : l'utilisateur a demandé les sous-titres et Whisper a effectivement fourni des mots horodatés. Cette valeur pilote à la fois le fichier ASS, le rendu FFmpeg et le contrôle qualité. Le fallback sans sous-titres reste actif si aucune parole exploitable n'est disponible.
- **Régression :** ajout d'un test ciblé couvrant les trois cas (demande + mots, option désactivée, transcription vide).
- **Périmètre :** correction du parcours Short uniquement ; aucune modification du modèle, des réglages locaux, de la langue, du moteur AMD/CPU ou de la version de l'application.
- **Branche :** `fix/short-captions-enabled-in-render`. CI Linux/Windows de la PR à vérifier avant fusion. Aucun rendu matériel réel ni benchmark Whisper sur la RX 9060 XT n'est revendiqué.
- **Suite :** après CI, valider sur Windows un clip réel avec sous-titres activés et un autre sans sous-titres ; vérifier le MP4, le SRT annexe, la synchronisation et le rapport de contrôle qualité.
## 48. Cadrage global des futures miniatures GTA, 28 novembre 2026

- **Retour utilisateur sur v0.9.1 :** la sortie automatique recadrait la source verticale, réduisait la webcam à un fragment, gardait trop de fond vide et affichait « streamer + GTA MOMENT ». La demande porte sur le template global des futures miniatures ; le JPEG montré est uniquement un exemple de défaut et n'est pas retouché.
- **Direction appliquée au générateur :** composition verticale resserrée avec l'image du streamer en haut lorsqu'une webcam déjà intégrée à la capture est repérée, une bande papier courte avec accroche au centre et le gameplay en bas. Nom du streamer en haut, signature GTA_Rankd discrète en bas. Le rendu reste déterministe et utilise la vraie image du clip.
- **Cadrage :** pour une source verticale, recherche d'une zone d'image active afin d'écarter les grands espaces inactifs. Détection locale et conservatrice d'une webcam dans les quatre coins ; si aucun coin n'est assez crédible, la scène complète reste utilisée sans inventer de visage. Pour le panneau de gameplay, le coin de webcam repéré est écarté.
- **Texte :** filtrage du nom du streamer, des tokens GTA/GTAV et des mots génériques « moment/clip » dans l'accroche. Un texte vide, fragmentaire ou composé de fillers utilise « WAIT FOR THE REACTION ».
- **Fichiers :** compositeur app/studio/web/short_editor.py ; assertions existantes actualisées dans app/tests/test_short_editor.py ; ce mémo.
- **Branche :** fix/thumbnail-collage-framing. La validation CI Linux/Windows de la PR devra confirmer le rendu et les régressions avant intégration.
- **Limite :** le repérage de webcam est heuristique à partir des couleurs de peau et ne fonctionne que si elle est déjà visible dans la capture. Il ne remplace ni ne télécharge une webcam séparée.
- **Suite :** ouvrir la PR, traiter les résultats CI Linux/Windows et livrer la nouvelle version stable selon le flux de release.
## 49. Préparation de la release v0.9.2 pour les miniatures, 28 novembre 2026

- **Livrable utilisateur :** corriger le template partagé pour que toutes les futures miniatures aient une composition GTA simple et cohérente. L'image partagée par l'utilisateur a servi de diagnostic uniquement ; elle n'a pas été modifiée.
- **PR #87 fusionnée :** commit `905b8d6b0dda04b06802ee8ebe8d2207a552a6af`. Cadrage de la scène active des sources portrait, webcam intégrée mise en avant quand une heuristique locale la repère, accroche sur bande papier courte, gameplay en dessous et signature discrète GTA_Rankd. Les accroches génériques (streamer/GTA/moment) sont nettoyées, avec « WAIT FOR THE REACTION » en fallback.
- **CI de PR #87 :** audit Linux [46082008049](https://github.com/Sreleew/GTA_rankd/actions/runs/46082008049) et validation Windows [46082007964](https://github.com/Sreleew/GTA_rankd/actions/runs/46082007964) réussis, avec tests, audit, scripts PowerShell et package.
- **Limite :** la webcam n'est pas extraite d'une piste distincte. La détection dépend de la webcam déjà incrustée dans la capture ; sans détection suffisamment fiable, le rendu conserve la scène complète.
- **Préparation release :** branche `release/v0.9.2`, versions synchronisées à 0.9.2, notes racine/app synchronisées et approbation de release préparée. La PR dédiée doit passer la CI avant fusion ; le workflow stable produira alors le ZIP Windows et SHA256SUMS.
- **Suite :** vérifier la PR de release, puis confirmer la publication de la v0.9.2.
## 50. Direction simple pour les miniatures et le montage Short, 28 novembre 2026

- **Retour utilisateur :** la miniature v0.9.2 répète un fallback et duplique la scène ; elle ne correspond pas à la référence approuvée. L'utilisateur met en pause les miniatures custom et veut laisser les plateformes sélectionner leur image au moment de publier.
- **Retour sur le Short généré :** l'utilisateur refuse le cadre blanc et l'accent jaune qui encadrent/coupent l'image, ainsi que l'identité incorrecte `GR // GTA` et `@GTARankedStudio`. Le seul nom de chaîne à utiliser est `GTA_rankd`.
- **Choix faisable pour le montage v0.9.3 :** utiliser le mode existant `blur`, qui conserve la capture Twitch complète (caméra incrustée comprise) au centre et remplit le 9:16 avec un fond flouté. Désactiver les signatures par défaut ; si elles sont activées, n'afficher que `GTA_rankd` en bas et en petit. Retirer le mode smart du formulaire et convertir en `blur` les anciens jobs/configurations qui demandaient `smart`.
- **Pourquoi ce choix :** la source actuelle est une seule image de stream où la caméra est déjà incrustée. Le mode `blur` est directement disponible et ne jette pas de contenu ; le mode plein écran vertical coupe des côtés et peut supprimer la webcam ; séparer la webcam nécessiterait une source caméra distincte ou une sélection manuelle, qui n'est pas prévue.
- **Miniatures :** retirer le traitement graphique et le bouton d'export custom. Garder seulement une image brute interne pour prévisualiser le Short ; elle n'est pas attachée au MP4 ni présentée comme la miniature de la plateforme.
- **Préférences durables :** mises à jour dans `docs/WORKING-AGREEMENT.md`. Pas de formes, cadres blanc/jaune, logo GR, tag @GTARankedStudio ou branding ajouté sans demande explicite.
- **Livré par la PR #89 :** retrait de l'overlay de miniature et de son export, mode `blur` par défaut, branding désactivé, conversion des anciens jobs `smart` vers `blur`, interface simplifiée. La PR est fusionnée dans `main` (commit `bb1c1623670237db98eacd51a71e2cd82d536934`).
- **CI PR #89 :** audit Linux [46084844857](https://github.com/Sreleew/GTA_rankd/actions/runs/46084844857) et validation Windows [46084844858](https://github.com/Sreleew/GTA_rankd/actions/runs/46084844858) réussis.
- **Suite :** préparer et valider la release stable v0.9.3, puis vérifier ses assets publiés.



## 51. Publication de la release v0.9.3, 28 novembre 2026

- **PR #90 :** préparation v0.9.3 fusionnée dans `main`, commit `7c809cc9de267524d6ad811a81f84fa88e54a0d5`. Versions racine/app synchronisées, notes identiques, approbation publiée et mémo mis à jour.
- **CI de PR #90 :** audit Linux [46085837169](https://github.com/Sreleew/GTA_rankd/actions/runs/46085837169) et validation Windows [46085837134](https://github.com/Sreleew/GTA_rankd/actions/runs/46085837134) réussis.
- **CI post-fusion :** audit Linux [46086077738](https://github.com/Sreleew/GTA_rankd/actions/runs/46086077738) et validation Windows [46086077825](https://github.com/Sreleew/GTA_rankd/actions/runs/46086077825) réussis, avec tests complets et vérification du package.
- **Publication :** workflow officiel [46086077731](https://github.com/Sreleew/GTA_rankd/actions/runs/46086077731) réussi. La [v0.9.3](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.9.3) est publiée avec le ZIP Windows `GTA-Ranked-Studio-v0.9.3.zip` (250 018 octets) et `SHA256SUMS.txt`.
- **Suite :** installer la v0.9.3 et examiner un Short réel pour vérifier le rendu visuel final sur Windows ; le CI ne remplace pas ce contrôle sur le PC cible.


## 52. Fidélité des sous-titres SRT et sortie rapide du hook, 28 novembre 2026

- **État de départ :** la PR #86 avait des validations Linux et Windows réussies sur son commit, mais sa branche était devenue divergente et non fusionnable après les évolutions #87 et #89. Son lot mélangeait la correction SRT avec une sélection de frame de couverture par transcript qui n'est plus nécessaire dans la direction v0.9.3.
- **Décision de portage :** reprendre uniquement les changements utiles au montage actuel sur une branche issue du `main` v0.9.3. Ne pas réintroduire de miniature graphique ni de sélection de cover custom ; l'aperçu interne reste une image brute et les plateformes choisissent la couverture.
- **Sous-titres DTW :** le mode `word_dtw` conserve les timestamps mot à mot réels et son emphase cinétique existante.
- **Fallback SRT :** le worker transmet maintenant le mode de timestamps réellement retourné par whisper.cpp. En `segment_srt`, chaque phrase reste affichée sur l'intervalle SRT exact ; le moteur ne répartit plus artificiellement le temps entre les mots. Les phrases sont repliées sur plusieurs lignes et les mots exceptionnellement longs reçoivent une réduction horizontale bornée. Le générateur ASS choisit prudemment le mode segment si aucun mode explicite n'est fourni ; le traitement mot à mot est activé uniquement lorsque whisper.cpp confirme `word_dtw`.
- **Hook :** le texte principal disparaît après 2,0 s et le contexte après 2,6 s. Le gameplay reste visible dès la première image ; aucun écran d'introduction n'est ajouté.
- **Tests :** couverture des bornes SRT exactes, de l'absence de faux surlignage mot à mot, du retour à la mise en emphase DTW et du rythme hook/contexte.
- **Premier retour CI :** Linux a exécuté 236 tests avec 1 ignoré et révélé une assertion de test trop stricte : elle ne normalisait pas le marqueur de retour à la ligne ASS `\\N`. L'assertion a été corrigée pour comparer le texte rendu sans ce séparateur ; le code de rendu n'était pas en échec.
- **Défaut sûr :** si un appelant ne connaît pas le mode Whisper, le générateur reste en mode segment par défaut. Un test dédié vérifie qu'il n'invente pas de synchronisation mot à mot sans confirmation DTW.
- **PR #92 :** [Keep SRT captions accurate and shorten Short opening overlays](https://github.com/Sreleew/GTA_rankd/pull/92), branche `fix/srt-caption-timing-and-hook-exit`, intégrée dans `main` au commit `617cec55b678ff52204808fba471ad32fd6bec23`.
- **Release :** v0.9.3 reste la dernière version stable ; aucun numéro de version, fichier d'approbation ou réglage utilisateur n'est modifié.
- **Limite :** aucun nouveau rendu réel ni benchmark Whisper sur la RX 9060 XT n'est revendiqué.
- **Suite :** valider les deux plateformes, puis comparer un rendu DTW et un fallback SRT sur Windows avant de poursuivre les améliorations éditoriales.


## 53. Préserver les intervalles des entrées DTW contenant plusieurs mots, 28 novembre 2026

- **État de départ :** la PR #92 est intégrée dans `main` ; la comparaison confirme que `main` pointe sur `617cec55b678ff52204808fba471ad32fd6bec23`. Aucune autre PR n'était ouverte au début de ce lot.
- **Défaut identifié :** le moteur conservait les intervalles exacts en mode SRT, mais continuait à découper une entrée DTW contenant plusieurs mots en timings artificiels proportionnels à la longueur des mots. Ce cas est inhabituel, mais peut apparaître si le regroupement des tokens Whisper ne fournit pas une entrée par mot.
- **Correction :** une entrée DTW multi-mots est désormais rendue comme une phrase sur son intervalle d'origine, sans emphase mot à mot. Les entrées réellement unitaires gardent l'emphase cinétique. Les listes mixtes conservent leur ordre chronologique.
- **Lisibilité mobile complémentaire :** les mots isolés exceptionnellement longs en mode DTW sont maintenant comprimés horizontalement de façon bornée, comme dans le fallback phrase. Le timing d'origine et l'emphase cinétique restent préservés.
- **Tests :** régression des entrées mixtes (mot, phrase, mot suivant), plus vérification d'un mot DTW très long : intervalle exact, compression horizontale et emphase conservée.
- **PR #93 :** [Preserve exact timing for mixed DTW caption records](https://github.com/Sreleew/GTA_rankd/pull/93), branche `fix/dtw-caption-mixed-segments`, fusionnée dans `main` au commit `c05ea08be0fd097f11621f61652cc9f4d3afe606` après réussite Linux/Windows sur le HEAD final.
- **Périmètre :** aucun changement au modèle Whisper, aux options de transcription, aux paramètres utilisateur, aux données locales, aux encodeurs AMD/CPU, aux miniatures ou à la version publiée. « Moments forts » reste en pause.
- **Release :** v0.9.3 reste la dernière version stable ; aucune nouvelle release ni approbation de publication n'est créée.
- **Limite :** aucun rendu réel Whisper ni benchmark RX 9060 XT n'est revendiqué.
- **CI initiale :** Linux et Windows ont tous deux réussi Ruff et pip-audit, puis échoué au contrôle `git show --check` à cause d'une ligne vide supplémentaire à la fin du test. Les suites de régression et le packaging ont été sautés par le garde-fou. La ligne vide superflue a été supprimée dans le commit `9b7229c` ; les validations doivent repartir sur ce nouveau commit.
- **CI après extension :** deux premières tentatives ont échoué uniquement sur une ligne vide supplémentaire à la fin du test. Après normalisation de la fin de fichier, Linux [46099885272](https://github.com/Sreleew/GTA_rankd/actions/runs/46099885272) a réussi (239 tests passés, 1 ignoré, package Windows construit et vérifié) et Windows [46099885244](https://github.com/Sreleew/GTA_rankd/actions/runs/46099885244) a réussi (audit, PowerShell, tests et package). Les contrôles post-fusion Linux [46100078401](https://github.com/Sreleew/GTA_rankd/actions/runs/46100078401) et Windows [46100078570](https://github.com/Sreleew/GTA_rankd/actions/runs/46100078570) ont également réussi ; Linux confirme 239 tests passés et 1 ignoré.
- **Suite :** poursuivre l'amélioration des hooks courts et du cadrage du texte éditorial, puis vérifier un extrait Whisper DTW et un fallback SRT sur Windows avant d'élargir le chantier au Daily Best Of.


## 54. Adapter les hooks et le contexte aux limites mobiles, 28 novembre 2026

- État de départ : PR #93 fusionnée dans main ; les contrôles post-fusion Linux et Windows ont réussi.
- Défaut identifié : l'ancien retour à la ligne du hook se basait sur le nombre de mots et pouvait laisser une ligne trop longue. Les hooks français ou anglais comportant de longs mots pouvaient déborder ou produire une composition déséquilibrée. Le contexte pouvait également se rapprocher excessivement d'un hook sur deux lignes.
- Correction : les overlays sont maintenant répartis sur une ou deux lignes équilibrées selon la longueur réelle du texte. La taille de police est réduite de façon bornée lorsque nécessaire et tient compte du grossissement maximal de chaque animation de hook. Le contexte descend automatiquement lorsque le hook occupe deux lignes. Les animations, les durées (hook 2,0 s, contexte 2,6 s) et l'absence d'intro sont conservées.
- Tests : ajout de cas français longs (hook et contexte sur deux lignes) et d'un hook court qui conserve la position compacte du contexte.
- Périmètre : aucun logo, miniature, cadre, changement de composition Twitch, modèle Whisper, encodeur, paramètre utilisateur ou donnée locale. « Moments forts » reste en pause.
- PR #94 : [Mobile-safe hook and context layout](https://github.com/Sreleew/GTA_rankd/pull/94), branche feat/mobile-hook-layout, fusionnée dans main au commit 2b124724671a9550296e20c8044d7de89eebb53d après réussite Linux/Windows sur le HEAD final.
- Release : v0.9.3 reste la dernière version stable ; aucune nouvelle release ni approbation de publication n'est créée.
- Limite : aucun rendu réel ni mesure de rétention sur une vidéo publiée n'est revendiqué.
- CI post-fusion : Linux [46100550613](https://github.com/Sreleew/GTA_rankd/actions/runs/46100550613) et Windows [46100550610](https://github.com/Sreleew/GTA_rankd/actions/runs/46100550610) ont réussi ; Linux confirme 241 tests passés et 1 ignoré, et le package Windows a été construit et vérifié.
- Suite : utiliser la transcription pour choisir le meilleur instant de la vignette existante, sans créer de miniature graphique, puis valider les hooks sur plusieurs clips français et anglais.


## 55. Utiliser la transcription pour choisir l'instant de vignette, 28 novembre 2026

- État de départ : PR #94 fusionnée dans main ; ses contrôles post-fusion Linux et Windows ont réussi.
- Défaut identifié : le worker recevait bien les mots Whisper du Short, mais passait une liste vide à select_thumbnail_timestamp. Le sélecteur ignorait donc les paroles et retombait systématiquement sur le pic audio.
- Correction : transmettre les mots transcrits, déjà recalés sur l'extrait final, au sélecteur existant. Les mots-clés d'action et de réaction en français et en anglais peuvent ainsi guider le choix du timestamp ; en l'absence de mots pertinents, le pic audio reste le fallback inchangé.
- Tests : ajout d'un cluster français « incroyable / police / crash / explosion » et d'un cas sans mots descriptifs qui vérifie le fallback au pic audio.
- Périmètre : sélection du timestamp de la vignette/aperçu déjà existant uniquement ; aucune miniature graphique générée, aucune modification de couverture de plateforme, de layout, de Whisper, d'encodeur ou de paramètres. « Moments forts » reste en pause.
- PR #95 : [Use transcript cues for Short thumbnail timestamp](https://github.com/Sreleew/GTA_rankd/pull/95), branche fix/transcript-aware-short-cover, fusionnée dans main au commit c7b9c06f0c8768455b230bae2a90679de534b942 après réussite Linux/Windows sur le HEAD final.
- Release : v0.9.3 reste la dernière version stable ; aucune nouvelle release ni approbation de publication n'est créée.
- Limite : aucun rendu réel Twitch ni mesure d'engagement sur une plateforme n'est revendiqué.
- CI PR #95 : Linux [46100755822](https://github.com/Sreleew/GTA_rankd/actions/runs/46100755822) et Windows [46100755831](https://github.com/Sreleew/GTA_rankd/actions/runs/46100755831) ont réussi sur le HEAD final ; Linux confirme 243 tests passés et 1 ignoré, le package Windows a été construit et vérifié.
- CI post-fusion PR #95 : Linux [46100933598](https://github.com/Sreleew/GTA_rankd/actions/runs/46100933598) et Windows [46100933521](https://github.com/Sreleew/GTA_rankd/actions/runs/46100933521) ont réussi.
- Suite : valider le parcours complet du Short sur des clips réels, puis consolider la génération Daily Best Of.


## 56. Empêcher les rendus Daily Best Of concurrents, 28 novembre 2026

- État de départ : PR #95 fusionnée dans main après réussite Linux/Windows ; ses contrôles post-fusion Linux et Windows ont également réussi.
- Défaut identifié : l'API pouvait accepter plusieurs demandes Daily Best Of pendant qu'un premier rendu était en file ou en cours. Plusieurs encodages de 9 à 11 minutes pouvaient alors se disputer CPU/GPU et les ressources disque.
- Correction : une réservation protégée par verrou local vérifie atomiquement l'existence d'un job queued/running avant d'en créer un autre. Une demande concurrente reçoit HTTP 409 avec l'identifiant court du rendu actif. Les rendus terminés ou en erreur ne bloquent pas un nouvel épisode. Le stockage expose une requête ciblée sur le seul job actif.
- Tests : un test API démarre un premier rendu différé, vérifie que le second est refusé, puis simule l'échec du premier et confirme qu'un nouveau rendu peut démarrer.
- Périmètre : aucun changement aux clips validés, à leur ordre, aux rendus existants, aux paramètres, aux fichiers locaux ou aux encodeurs AMD/CPU. « Moments forts » reste en pause.
- PR #96 : [Prevent parallel Daily Best Of renders](https://github.com/Sreleew/GTA_rankd/pull/96), branche fix/prevent-parallel-best-of-renders, fusionnée dans main au commit f0c54bc9b759aafeb41958611ed66560a343519e après réussite Linux/Windows sur le HEAD final.
- Release : v0.9.3 reste la dernière version stable ; aucune nouvelle release ni approbation de publication n'est créée.
- CI PR #96 : Linux [46101164834](https://github.com/Sreleew/GTA_rankd/actions/runs/46101164834) a réussi (244 tests passés, 1 ignoré, package Windows construit et vérifié) et Windows [46101164807](https://github.com/Sreleew/GTA_rankd/actions/runs/46101164807) a réussi (audit, PowerShell, tests et package).
- CI post-fusion PR #96 : Linux [46101338246](https://github.com/Sreleew/GTA_rankd/actions/runs/46101338246) et Windows [46101338357](https://github.com/Sreleew/GTA_rankd/actions/runs/46101338357) ont réussi.
- Suite : garantir qu'un Daily Best Of reste strictement limité à une seule date, puis vérifier la reprise après interruption et la composition 16:9 sur des Shorts validés.


## 57. Garantir une seule date par Daily Best Of, 28 novembre 2026

- État de départ : PR #96 fusionnée dans main après réussite Linux/Windows ; ses contrôles post-fusion Linux et Windows ont également réussi.
- Défaut identifié : si un appel API omettait date_key, le plan reprenait la date du premier Short mais acceptait encore des clips d'autres jours. Le titre Daily Best Of pouvait donc masquer une compilation multi-jours.
- Correction : inférer la date depuis le premier Short sélectionné lorsque le filtre n'est pas fourni, puis imposer cette date à tous les clips. Refuser également une sélection dont le premier Short ne possède aucune date exploitable. L'ordre choisi par l'utilisateur et la durée cible de 9 à 11 minutes restent inchangés.
- Tests : vérifier l'inférence d'une date commune, le rejet d'une sélection multi-jours sans filtre et le rejet d'un Short sans date.
- Périmètre : validation du plan uniquement ; aucun changement aux rendus déjà produits, aux clips validés, à l'ordre, aux fichiers locaux, aux paramètres ou aux encodeurs. « Moments forts » reste en pause.
- PR #97 : [Enforce one date per Daily Best Of](https://github.com/Sreleew/GTA_rankd/pull/97), branche fix/daily-best-of-single-date, fusionnée dans main au commit 7613e9838db158d3a619ed2550234ca1d1bbe79a après réussite Linux/Windows sur le HEAD final.
- Release : v0.9.3 reste la dernière version stable ; aucune nouvelle release ni approbation de publication n'est créée.
- CI PR #97 : Linux [46101518330](https://github.com/Sreleew/GTA_rankd/actions/runs/46101518330) a réussi (246 tests passés, 1 ignoré, package Windows construit et vérifié) et Windows [46101518418](https://github.com/Sreleew/GTA_rankd/actions/runs/46101518418) a réussi (audit, PowerShell, tests et package).
- CI post-fusion PR #97 : Linux [46101715515](https://github.com/Sreleew/GTA_rankd/actions/runs/46101715515) et Windows [46101715501](https://github.com/Sreleew/GTA_rankd/actions/runs/46101715501) ont réussi.
- Suite : adoucir les bords audio de l'épisode Daily Best Of, puis confirmer la composition 16:9 sur un rendu complet.


## 58. Adoucir l'entrée et la sortie audio du Daily Best Of, 28 novembre 2026

- État de départ : PR #97 fusionnée dans main après réussite Linux/Windows ; les contrôles post-fusion ont réussi.
- Défaut identifié : la concaténation audio des Shorts validés démarrait et s'arrêtait sans fondu, ce qui pouvait donner une coupe sèche au début ou à la fin de l'épisode.
- Correction : appliquer un fondu audio d'entrée de 0,35 s et un fondu de sortie de 0,75 s au mix final lorsque les durées exactes sont disponibles. Les durées sont bornées pour les tests ou les épisodes exceptionnellement courts. Aucun crossfade n'est ajouté entre les clips afin de ne pas brouiller les dialogues ni les effets de gameplay.
- Tests : vérifier les timestamps exacts sur un épisode de 560 s, le comportement historique sans durées connues et le bornage sur un flux de 0,2 s.
- Périmètre : audio uniquement ; aucun changement aux vidéos, à l'ordre des Shorts, à la durée cible, aux données locales, aux paramètres ou aux encodeurs AMD/CPU. « Moments forts » reste en pause.
- PR #98 : [Add clean audio edges to Daily Best Of](https://github.com/Sreleew/GTA_rankd/pull/98), branche feat/daily-best-of-audio-edges, fusionnée dans main au commit d7d96db68a360f376a3adf07beeb33b7894128bc après réussite Linux/Windows sur le HEAD final.
- Release : v0.9.3 reste la dernière version stable ; aucune nouvelle release ni approbation de publication n'est créée.
- CI PR #98 : Linux [46101822791](https://github.com/Sreleew/GTA_rankd/actions/runs/46101822791) et Windows [46101822773](https://github.com/Sreleew/GTA_rankd/actions/runs/46101822773) ont réussi ; Linux confirme 249 tests passés et 1 ignoré, le package Windows a été construit et vérifié.
- CI post-fusion PR #98 : Linux [46101996557](https://github.com/Sreleew/GTA_rankd/actions/runs/46101996557) et Windows [46101996393](https://github.com/Sreleew/GTA_rankd/actions/runs/46101996393) ont réussi.
- Suite : vérifier le son sur un Daily Best Of complet et ne considérer des transitions entre clips que si elles améliorent la compréhension sans masquer la parole.


## 59. Vérifier la durée réelle des Shorts avant le rendu Daily Best Of, 28 novembre 2026

- État de départ : PR #98 fusionnée dans main après réussite Linux/Windows ; ses contrôles post-fusion ont réussi.
- Défaut identifié : le renderer utilisait uniquement la durée enregistrée dans la bibliothèque pour couper chaque Short et calculer la progression. Si un fichier avait été remplacé ou modifié après validation, la concaténation et le fondu final pouvaient être décalés, voire produire un épisode plus court que prévu.
- Correction : comparer la durée ffprobe de chaque fichier à la durée enregistrée, avec une tolérance bornée à 1 seconde ou 1 % pour absorber les écarts de conteneur. Utiliser ensuite les durées réelles pour les pistes silencieuses, le graphe FFmpeg, les fondus audio et la progression. Refuser le rendu si les durées ont changé ou si le total réel sort de la plage 9 à 11 minutes.
- Tests : ajouter un cas où un Short a été raccourci après validation ; les tests de rendu existants continuent de vérifier les durées exactes utilisées par FFmpeg.
- Périmètre : contrôle avant encodage ; aucun fichier local n'est modifié, aucun clip n'est supprimé et aucune donnée de bibliothèque n'est réécrite. Les encodeurs AMD/CPU et le fallback restent inchangés. « Moments forts » reste en pause.
- PR #99 : [Verify source durations before Daily Best Of render](https://github.com/Sreleew/GTA_rankd/pull/99), branche fix/verify-best-of-source-durations, fusionnée dans main au commit 5f511a375405eb9bc3ef9c6a2ab37ef2941f056a après réussite Linux [46102143385](https://github.com/Sreleew/GTA_rankd/actions/runs/46102143385) et Windows [46102143376](https://github.com/Sreleew/GTA_rankd/actions/runs/46102143376) sur le HEAD final.
- Release : v0.9.3 reste la dernière version stable ; aucune nouvelle release ni approbation de publication n'est créée.
- CI post-fusion PR #99 : audit Linux [46102320456](https://github.com/Sreleew/GTA_rankd/actions/runs/46102320456) et validation Windows [46102320463](https://github.com/Sreleew/GTA_rankd/actions/runs/46102320463) réussis.
- Suite : valider le rendu complet 16:9 et le son sur un ensemble de Shorts validés avant d'élargir le montage.


## 60. Filtrer les sous-titres sur la voix principale et réutiliser le WAV d'analyse, 28 novembre 2026

- **État de départ :** PR #99 est fusionnée dans main au commit 5f511a375405eb9bc3ef9c6a2ab37ef2941f056a après réussite des validations PR Linux/Windows. Ses contrôles post-fusion Linux et Windows ont réussi.
- **Défaut identifié :** le module local `speakers.py` et ses tests existaient toujours, mais le pipeline Whisper facultatif ne l'appelait plus. Les mots de toutes les voix pouvaient être intégrés aux sous-titres et au transcript utilisé pour le hook/métadonnées. Le SRT annexe copié depuis Whisper contenait également les dialogues non filtrés.
- **Correction produit :** lorsque les sous-titres sont demandés, le worker passe maintenant les mots horodatés au filtre local de voix dominante. Si la diarisation est indisponible, ambiguë ou n'attribue pas assez de mots, le pipeline omet les sous-titres au lieu de revenir à toutes les voix. Le transcript transmis au générateur de hook et au sélecteur d'aperçu est recalculé depuis les seuls mots conservés.
- **SRT annexe :** le fichier `captions.srt` est reconstruit à partir des mots filtrés et de leurs intervalles d'origine avec le writer SRT déjà présent dans `short_editor.py`. Le SRT brut Whisper n'est plus copié dans le dossier de sortie, afin de ne pas réintroduire les dialogues du jeu.
- **Performance :** lorsque le WAV d'analyse audio existant couvre l'extrait choisi, Whisper et la diarisation utilisent une découpe de ce WAV au lieu de décoder une deuxième fois la vidéo source. Un WAV déjà exactement aligné reste réutilisé directement.
- **Transparence :** la fiche du Short indique si la voix principale a été isolée ou si les sous-titres ont été omis ; le temps supplémentaire de filtrage vocal apparaît dans le rapport de traitement. L'interface précise que la diarisation est bêta et ne garantit pas que la voix dominante soit celle du streamer.
- **Décision produit :** l'option de sous-titres reste désactivée par défaut. Lorsqu'elle est activée, aucun fallback « toutes les voix » n'est appliqué : si le filtre ne peut pas isoler une voix dominante, le Short reste sans sous-titres plutôt que d'afficher les dialogues du jeu.
- **Coût et limite :** aucun filtre n'est exécuté si les sous-titres sont désactivés. Le paquet local `diarize==0.1.2` reste installé à la demande lors du premier usage des sous-titres ; cette étape peut être longue. En cas d'échec, le Short continue sans sous-titres. La méthode ne sépare pas les voix superposées et ne certifie pas l'identité du streamer.
- **Tests :** couverture de la réutilisation/sélection du WAV d'analyse, du comportement fail-closed de la diarisation, de l'absence de transcription et de l'écriture SRT avec timestamps exacts.
- **Périmètre :** aucune modification de l'encodeur AMD/CPU, du cadrage source complet, des données locales, des paramètres de rendu, des jobs existants ou des miniatures personnalisées. « Moments forts » reste en pause.
- **PR #100 :** [Filter Short captions to the dominant voice](https://github.com/Sreleew/GTA_rankd/pull/100), fusionnée dans `main` au commit `f2b0201425371bdb0ed280d9844b5364164fe370`. CI Linux [46103175130](https://github.com/Sreleew/GTA_rankd/actions/runs/46103175130) réussie (254 tests passés, 1 ignoré, Ruff/audit et package Windows vérifiés) ; CI Windows [46103175134](https://github.com/Sreleew/GTA_rankd/actions/runs/46103175134) réussie (255 tests passés, Ruff/audit, PowerShell et package vérifiés). Contrôles post-fusion Linux [46103374382](https://github.com/Sreleew/GTA_rankd/actions/runs/46103374382) et Windows [46103374415](https://github.com/Sreleew/GTA_rankd/actions/runs/46103374415) réussis ; aucun rendu réel sur Windows/AMD n'est revendiqué.
- **Suite :** valider les suites Linux et Windows, puis effectuer un essai sur un clip Twitch réel pour vérifier si la voix dominante retenue est effectivement celle du streamer et mesurer le surcoût du filtre sur le PC Windows/AMD.



## 61. Vérifier la durée finale du Daily Best Of après encodage, 28 novembre 2026

- **État de départ :** PR #100 est fusionnée dans main au commit f2b02014 ; ses validations pré-fusion et post-fusion Linux/Windows ont réussi.
- **Défaut identifié :** le renderer vérifiait la résolution et la présence audio du MP4 final, mais pouvait encore marquer un rendu comme réussi si le conteneur était tronqué ou si l'encodage s'arrêtait avant la durée attendue.
- **Correction :** comparer la durée ffprobe du fichier final à la somme des durées réelles vérifiées des Shorts sources, avec une tolérance bornée à 1 seconde ou 1 %. Refuser les durées nulles, non finies ou trop éloignées et signaler explicitement un export incomplet.
- **Tests :** ajouter un cas où FFmpeg produit un fichier 1920 × 1080 avec audio mais seulement 500 s au lieu des 560 s attendues.
- **Périmètre :** contrôle qualité après encodage ; aucun fichier existant n'est supprimé ou réécrit, aucun changement aux paramètres ou encodeurs AMD/CPU. « Moments forts » reste en pause.
- **PR #101 :** [Verify final Daily Best Of duration](https://github.com/Sreleew/GTA_rankd/pull/101), branche `fix/verify-best-of-output-duration`, rebasée sur le commit `f2b0201425371bdb0ed280d9844b5364164fe370`, HEAD final `6dd0aa319f283d106947a5f3577c17bfdf93825f`. CI Linux [46103506874](https://github.com/Sreleew/GTA_rankd/actions/runs/46103506874) réussie (255 tests passés, 1 ignoré) ; CI Windows [46103506846](https://github.com/Sreleew/GTA_rankd/actions/runs/46103506846) réussie (256 tests passés, Ruff/audit, PowerShell et package vérifiés). PR fusionnée dans `main` au commit `b190c33f`.
- **Release :** v0.9.3 reste la dernière version stable ; aucune nouvelle release ni approbation de publication n'est créée.
- **Suite :** consolider le parcours Short sur des transcriptions Twitch réelles, puis vérifier le rendu 16:9 complet et son audio avant d'ajouter des transitions visuelles entre clips.


## 62. Borner les timestamps DTW Whisper aux segments source, 28 novembre 2026

- **État de départ :** PR #93 est intégrée dans `main` au commit `c05ea08` ; les sous-titres gardent déjà les intervalles phrase réels pour les enregistrements DTW multi-mots. PR #101 est également fusionnée au commit `b190c33f` après validations Linux/Windows.
- **Défaut identifié :** le parseur DTW rejetait les valeurs non numériques et les timestamps négatifs, mais pouvait accepter un token horodaté avant/après les bornes de son segment Whisper. Une borne de segment absente ou inversée pouvait aussi conduire à inventer une fenêtre d'une seconde. Cela risquait de décaler un mot hors de sa phrase ou hors de l'extrait final.
- **Correction :** valider les champs minutes/secondes de l'horloge Whisper ; ignorer les segments dont les bornes sont absentes, invalides, inversées ou trop courtes ; conserver uniquement les tokens dans l'intervalle du segment avec une marge minimale pour leur durée ; trier les tokens par timestamp avant de reconstruire les mots. Si aucun mot DTW fiable ne survit, le pipeline existant revient au SRT segmentaire, sans fabriquer de timing mot à mot.
- **Tests :** couvrir les tokens avant/après leur segment, les bornes manquantes/inversées/malformées, les tokens fournis dans le désordre et le fallback SRT via le faux exécutable Whisper.
- **PR #102 :** [Bound Whisper DTW timestamps to their source segments](https://github.com/Sreleew/GTA_rankd/pull/102), branche `fix/whisper-dtw-segment-bounds`, fusionnée au commit `7052efbfb3135d5eafd4032568867d065da0dfe4`. Sur le commit de code final `576267d5bb78272d00f4373056330657f2adf057`, CI Linux [46106691275](https://github.com/Sreleew/GTA_rankd/actions/runs/46106691275) et Windows [46106691201](https://github.com/Sreleew/GTA_rankd/actions/runs/46106691201) réussies ; tests complets, audit et package Windows validés.
- **Périmètre :** aucun changement de modèle, de paramètres Whisper, de données locales, d'encodeur AMD/CPU ou de release. Les miniatures personnalisées et « Moments forts » restent en pause.
- **Release :** v0.9.3 reste la dernière version stable ; aucune nouvelle release ni approbation de publication n'est créée.
- **Suite :** poursuivre la fiabilisation éditoriale des sous-titres Shorts, puis vérifier leur rendu sur un vrai clip Twitch et le filtrage de voix avant d'élargir le montage.


## 63. Attacher la ponctuation multilingue aux mots des sous-titres, 28 novembre 2026

- **État de départ :** PR #102 est fusionnée au commit `7052efbf` après succès des validations Linux et Windows sur son commit final.
- **Défaut identifié :** le regroupement des tokens rattachait les ponctuations de fermeture anglaises courantes, mais pouvait laisser `¿`, `¡` ou `«` comme événements isolés et séparer `»`, les guillemets typographiques ou les crochets du mot concerné. Sur mobile, ces signes pouvaient apparaître seuls ou avec un timing décalé.
- **Correction :** reconnaître les préfixes ouvrants espagnols/français et les ponctuations fermantes typographiques ; rattacher les préfixes au mot suivant et les fermetures au mot précédent, en conservant l'intervalle temporel combiné. Le comportement existant des apostrophes anglaises est conservé.
- **Tests :** vérifier le regroupement `¿Qué`, `pasó?` et `«incroyable»`, ainsi que la conservation des bornes de début et de fin.
- **PR #103 :** [Keep multilingual punctuation attached to Short captions](https://github.com/Sreleew/GTA_rankd/pull/103), branche `fix/multilingual-caption-punctuation`, fusionnée dans `main` au commit `304f608c95d0d730dc3d91e89de6398aad059125`. CI Linux [46106990785](https://github.com/Sreleew/GTA_rankd/actions/runs/46106990785) et Windows [46106990740](https://github.com/Sreleew/GTA_rankd/actions/runs/46106990740) réussies : audit, tests de régression, contrôle PowerShell et package Windows validés.
- **Périmètre :** aucune modification du moteur Whisper, des paramètres, des données locales, des encodeurs AMD/CPU ou du Daily Best Of. « Moments forts » reste en pause.
- **Release :** v0.9.3 reste la dernière version stable ; aucune nouvelle release sans validation réelle sur le PC Windows.
- **Suite :** protéger l'intelligibilité de la première parole pendant le hook audio, puis valider le mix sur un vrai clip Twitch Windows/AMD avant d'élargir le sound design.


## 64. Protéger la première parole du streamer pendant le sound design du hook, 28 novembre 2026

- **État de départ :** PR #103 est fusionnée dans `main` au commit `304f608c95d0d730dc3d91e89de6398aad059125`. Les validations Linux [46106990785](https://github.com/Sreleew/GTA_rankd/actions/runs/46106990785) et Windows [46106990740](https://github.com/Sreleew/GTA_rankd/actions/runs/46106990740) ont réussi sur le HEAD final de la PR, avec audit, suites de régression, scripts PowerShell et package Windows.
- **Défaut identifié :** le rendu appliquait un fondu d'entrée audio de 120 ms à la voix et au gameplay, avec ou sans sound effect. Sur un Short qui commence directement par une réaction, ce fondu pouvait atténuer la consonne ou la première syllabe. En parallèle, le cue du hook était simplement additionné au mix à volume fixe et pouvait concurrencer la parole.
- **Correction proposée :** réduire le fondu d'entrée du son source à 20 ms, suffisant pour éviter un clic sans créer une longue montée de volume ; utiliser le signal audio source comme sidechain pour compresser uniquement le cue du hook lorsqu'un son du clip est présent. Le cue reste audible dans les silences et se fait discret pendant la parole ou les impacts du gameplay.
- **Réglages :** conserver le volume utilisateur existant et le décalage actuel du cue ; compression sidechain conservatrice avec seuil 0,03, ratio 8:1, attaque 8 ms et relâchement 180 ms. Aucun nouveau paramètre utilisateur ni dépendance.
- **Tests :** les tests initiaux vérifiaient la construction de la chaîne FFmpeg, mais n'exécutaient pas réellement le graphe avec un cue. Cette lacune a laissé passer un défaut de fan-out ; la PR #106 ajoute maintenant une vraie exécution FFmpeg avec un clip synthétique et un effet sonore.
- **Périmètre :** uniquement le mix audio des Shorts. Aucun changement au cadrage, à Whisper, aux sous-titres, aux données locales, aux paramètres personnels, à l'encodeur AMD/CPU ou au Daily Best Of. « Moments forts » reste en pause.
- **PR #104 :** [Protect streamer speech under Short hook sound effects](https://github.com/Sreleew/GTA_rankd/pull/104), branche `fix/short-hook-audio-ducking`, fusionnée dans `main` au commit `0b6a3df058a9691d8e2e7bce15de8a30f0294b35`. CI PR Linux [46109216983](https://github.com/Sreleew/GTA_rankd/actions/runs/46109216983) et Windows [46109216952](https://github.com/Sreleew/GTA_rankd/actions/runs/46109216952) réussies ; CI post-fusion Linux [46112065461](https://github.com/Sreleew/GTA_rankd/actions/runs/46112065461) et Windows [46112065548](https://github.com/Sreleew/GTA_rankd/actions/runs/46112065548) réussies.
- **Limite :** le sidechain se base sur le mix Twitch complet et non sur une piste voix séparée ; il protège donc aussi contre les impacts du jeu, mais ne prétend pas isoler mathématiquement la voix du streamer. Aucun test réel sur le PC RX 9060 XT n'est revendiqué.
- **Release :** v0.9.3 reste la dernière version stable ; aucune approbation ni nouvelle release n'est créée.
- **Suite :** valider Linux/Windows, puis mesurer subjectivement le niveau du cue et l'intelligibilité de la première syllabe sur un clip réel avant d'ajouter d'autres effets audio.

## 65. Préserver les mots accentués dans les hooks de secours multilingues, 28 novembre 2026

- **État de départ :** PR #104 fusionnée dans `main` au commit `0b6a3df058a9691d8e2e7bce15de8a30f0294b35` après réussite des validations Linux [46109216983](https://github.com/Sreleew/GTA_rankd/actions/runs/46109216983) et Windows [46109216952](https://github.com/Sreleew/GTA_rankd/actions/runs/46109216952) sur le HEAD final `f150f171741207dd238da425aff7f80a185d5c75`. Les validations post-fusion ont été déclenchées ; Linux a réussi et Windows était encore en cours au début de ce lot.
- **Défaut identifié :** les fallbacks de hooks et de phrases complètes utilisaient `[A-Za-z0-9]`, qui découpe ou supprime les lettres accentuées françaises, espagnoles et portugaises. Une transcription telle que « Attends, c'est complètement incroyable » pouvait perdre des caractères et produire un hook dégradé.
- **Correction proposée :** centraliser la tokenisation Unicode en conservant les contractions avec apostrophe ; comparer les mots-clés de réaction sans sensibilité aux accents ; reconnaître les réactions et mots de liaison courants en français, espagnol et portugais ; étendre les ancres GTA multilingues pour les transcriptions sans ponctuation. Le texte affiché conserve exactement les accents de la transcription. Séparer les mots de fin de phrase des mots de liaison autorisés au début d'un titre afin de ne pas supprimer des débuts significatifs comme « got my ».
- **Tests :** couvrir les accents et apostrophes françaises, les cues espagnols et portugais, les phrases incomplètes terminant par une conjonction et les ancres françaises sans ponctuation. Le premier passage CI a aussi révélé une régression de sélection du titre (`got my car back` et `got my lambo`) ; le filtrage du début de phrase a été séparé du filtrage des fins incomplètes.
- **PR #105 :** [Preserve Unicode words in multilingual Short hook fallbacks](https://github.com/Sreleew/GTA_rankd/pull/105), branche `fix/unicode-short-hook-fallback`, HEAD final `3b5950c059e4570f538f6f275d0a436d4679ebb3`, fusionnée dans `main` au commit `0a09915f8821498f44928a1e16757a8bc7db9f76`. CI Linux [46112491110](https://github.com/Sreleew/GTA_rankd/actions/runs/46112491110) et Windows [46112491065](https://github.com/Sreleew/GTA_rankd/actions/runs/46112491065) réussies. Les premières exécutions avaient révélé des lignes blanches terminales et un filtrage trop agressif de « got my » ; les deux problèmes ont été corrigés avant validation finale.
- **Périmètre :** génération locale de secours des hooks, sélection des phrases et mots utilisés pour les métadonnées. Aucun changement au prompt Ollama, à Whisper, aux modèles, aux données locales, aux réglages personnels, au rendu AMD/CPU ou au Daily Best Of. « Moments forts » reste en pause.
- **Release :** v0.9.3 reste la dernière version stable ; aucune approbation de publication ni nouvelle Release n'est créée.
- **Limite :** le fallback reste une heuristique lexicale et ne traduit pas la transcription ; il conserve la langue parlée. La qualité d'une génération Ollama en anglais reste distincte de ce chemin de secours.
- **Suite :** valider Linux/Windows puis vérifier le comportement sur de vrais extraits français/anglais avant d'élargir les règles de hook.

## 66. Corriger le fan-out audio du sidechain de hook avec un test FFmpeg réel, 28 novembre 2026

- **État de départ :** PR #104 est intégrée dans `main` au commit `0b6a3df058a9691d8e2e7bce15de8a30f0294b35`. Ses CI Linux [46109216983](https://github.com/Sreleew/GTA_rankd/actions/runs/46109216983) et Windows [46109216952](https://github.com/Sreleew/GTA_rankd/actions/runs/46109216952) ont réussi avant fusion ; les validations post-fusion Linux [46112065461](https://github.com/Sreleew/GTA_rankd/actions/runs/46112065461) et Windows [46112065548](https://github.com/Sreleew/GTA_rankd/actions/runs/46112065548) ont également réussi. PR #105 a ensuite été fusionnée dans `main` au commit `0a09915f8821498f44928a1e16757a8bc7db9f76`, après réussite de ses validations Linux/Windows.
- **Défaut découvert après fusion :** le graphe audio envoyait la même sortie `[main_audio]` à `sidechaincompress` et à `amix` sans dupliquer explicitement le flux. Une reproduction locale avec FFmpeg 7.1.5 échouait avec `Stream specifier 'main_audio' ... matches no streams`, ce qui empêchait le rendu d'un Short utilisant un effet sonore.
- **Correction proposée :** ajouter `asplit=2[main_for_ducking][main_for_mix]` après la normalisation du son source ; réserver une branche au sidechain et l'autre au mix final. Les volumes, le timing, le fondu de 20 ms et les réglages AMD/CPU restent inchangés.
- **Tests :** renforcer le test de construction du graphe et ajouter un test d'intégration qui génère un clip synthétique vidéo/audio et un cue WAV avec FFmpeg, exécute la commande réelle de rendu vertical et vérifie la création du MP4. La commande synthétique corrigée a réussi localement avec FFmpeg 7.1.5 ; ce n'est pas un test matériel AMD.
- **PR #106 :** [Fix Short hook sidechain audio fan-out](https://github.com/Sreleew/GTA_rankd/pull/106), branche `fix/short-hook-audio-sidechain-fanout`, rebasée sur `main` après la fusion de la PR #105 au commit `0a09915f8821498f44928a1e16757a8bc7db9f76`. Les premiers contrôles `git show --check` ont signalé des lignes blanches terminales dans le test et le mémo ; elles ont été supprimées. La suite Linux a ensuite détecté une ancienne assertion qui attendait encore le graphe sans `asplit` dans `test_render_integration.py` ; cette régression de test a été mise à jour pour vérifier les deux branches distinctes. Linux/Windows sont relancés sur le HEAD corrigé.
- **Périmètre :** uniquement le mix audio du rendu Short et sa couverture FFmpeg. Aucun changement à Whisper, aux sous-titres, aux données locales, aux réglages personnels, à la webcam, au Daily Best Of ou à la publication. « Moments forts » reste en pause.
- **Release :** v0.9.3 reste la dernière version stable ; aucune nouvelle release ni approbation de publication n'est créée.
- **Suite :** faire passer Linux/Windows sur le graphe FFmpeg réel, puis fusionner les PR Shorts uniquement après réussite des deux plateformes.

## 67. Ramener les anciens jobs `smart` à la composition Short sans cadre, 28 novembre 2026

- **État de départ :** PR #106 fusionnée dans `main` au commit `4076f7c21d137e1fbf4ea32840984be36251ffba`, après réussite des validations PR Linux [46112948151](https://github.com/Sreleew/GTA_rankd/actions/runs/46112948151) et Windows [46112948185](https://github.com/Sreleew/GTA_rankd/actions/runs/46112948185). Le test FFmpeg ajouté à la PR a exécuté le graphe réel avec une source vidéo/audio et un cue WAV.
- **Défaut identifié :** le worker normalisait `smart` en `blur` pour l'overlay ASS, mais transmettait encore la valeur brute des options à `render_vertical_short`. Les anciens jobs sauvegardés avec `smart` pouvaient donc réactiver l'ancien panneau éditorial avec liseré blanc et accent jaune, contrairement à la direction validée dans `docs/WORKING-AGREEMENT.md`.
- **Correction proposée :** centraliser `normalize_short_layout` dans le moteur de rendu ; conserver `smart` comme alias rétrocompatible de `blur`, supprimer l'ancien panneau encadré et utiliser la même valeur normalisée pour l'ASS, le rendu et les métadonnées. Le mode explicite `fill` reste disponible et conserve son comportement de recadrage.
- **Tests :** comparer exactement les graphes `smart` et `blur`, vérifier l'absence de `drawbox` et de l'accent jaune, couvrir les sources paysage et portrait, tester la normalisation des trois valeurs et vérifier que `render_vertical_short` transmet/retourne `blur` pour un job historique. Le test FFmpeg existant vérifie également que les bords gauche et droit de la capture Twitch restent visibles.
- **PR #107 :** [Map legacy smart Short layout to the approved borderless blur composition](https://github.com/Sreleew/GTA_rankd/pull/107), branche `fix/legacy-smart-layout-borderless`, HEAD final `6c197eea7df31152bc10efd5135d3ea3608f93bf`, fusionnée dans `main` au commit `70928ad0eb63d8e00c65c302fddbe201f0fe30e9`. Le premier passage CI avait détecté une ligne vide terminale dans ce mémo ; le passage suivant avait révélé une assertion d'intégration obsolète qui attendait `smart` au lieu de la valeur normalisée `blur`. Ces deux défauts ont été corrigés avant validation finale. CI Linux [46120444835](https://github.com/Sreleew/GTA_rankd/actions/runs/46120444835) et Windows [46120444871](https://github.com/Sreleew/GTA_rankd/actions/runs/46120444871) réussies sur le HEAD final.
- **Périmètre :** uniquement le rendu vertical Short et la compatibilité des jobs sauvegardés. Aucune modification des paramètres utilisateur, des médias locaux, de Whisper, du sound design, de la webcam intégrée ou du Daily Best Of. Les modes de recadrage explicite `fill` et les données existantes sont préservés. « Moments forts » reste en pause.
- **Release :** v0.9.3 reste la dernière version stable. Après ce lot, prévoir environ 1 à 2 lots Shorts cohérents supplémentaires et une validation réelle sur le PC Windows/AMD avant de réévaluer la prochaine publication ; aucune date n'est promise. Aucune version, approbation `.release-approval` ou tag n'est modifié. Estimation actuelle : environ 2 à 3 lots produit cohérents avant de réévaluer la prochaine release, sous réserve du test réel sur le PC Windows/AMD.
- **Suite :** vérifier visuellement un ancien job `smart` et un nouveau job `blur` sur un clip Twitch réel ; le prochain correctif rend le zoom dynamique optionnel par défaut et explique explicitement son effet de recadrage sur les bords de la webcam.

## 68. Rendre le zoom dynamique explicitement optionnel, 28 novembre 2026

- **État de départ :** PR #107 fusionnée dans `main` au commit `70928ad0eb63d8e00c65c302fddbe201f0fe30e9` après réussite Linux [46120444835](https://github.com/Sreleew/GTA_rankd/actions/runs/46120444835) et Windows [46120444871](https://github.com/Sreleew/GTA_rankd/actions/runs/46120444871).
- **Incohérence identifiée :** l'interface affichait le zoom dynamique décoché et le mémo le décrivait comme désactivé par défaut, mais les trois routes d'import FastAPI, `config.yaml.default` et le fallback du worker le traitaient comme activé. Les nouveaux imports depuis le navigateur transmettaient bien `false`, mais les appels sans champ et les jobs sans réglage explicite pouvaient activer un zoom qui recadre les bords de la capture, y compris une webcam placée au bord de l'image.
- **Correction :** les trois routes d'import acceptent maintenant une valeur de formulaire facultative. Un choix explicitement envoyé par l'interface/API prime ; si le champ est absent, le réglage existant de `config.yaml` est utilisé. Le fichier de configuration neuf et le fallback worker utilisent `false`, donc le zoom est opt-in sur une installation fraîche. Une configuration utilisateur existante avec `true` reste respectée ; aucun fichier de configuration existant ni job sauvegardé n'est réécrit.
- **Interface :** les deux formulaires Shorts expliquent maintenant que le zoom rapproche l'image autour du pic et peut couper les bords, webcam comprise. L'option reste désactivée par défaut.
- **Tests :** vérifier le défaut `false` pour les imports URL, upload et batch sans champ `dynamic_zoom` avec la configuration neuve ; vérifier qu'une configuration utilisateur `true` reste active si le champ est absent et qu'un choix explicite `false` la désactive ; vérifier la configuration fraîche et la présence de l'avertissement dans les deux formulaires. Linux : 270 passés, 1 ignoré ; Windows : 271 passés. Ruff, pip-audit, scripts PowerShell, build et vérification du package Windows v0.9.3 réussis.
- **PR #108 :** [Make Short dynamic zoom opt-in and protect webcam edges](https://github.com/Sreleew/GTA_rankd/pull/108), branche `fix/short-dynamic-zoom-opt-in-default`, HEAD final `d80c544109f54dab23b2f3f340adc991bd52a06f`, fusionnée dans `main` au commit `5162a788a688997688884f7fc879a63d587e0b74`. CI Linux [46121216245](https://github.com/Sreleew/GTA_rankd/actions/runs/46121216245) et Windows [46121216239](https://github.com/Sreleew/GTA_rankd/actions/runs/46121216239) réussies sur le HEAD final ; 270 tests Linux passés, 1 ignoré, 271 tests Windows passés, package Windows v0.9.3 vérifié.
- **Périmètre :** réglages par défaut et explication UI du zoom dynamique uniquement. Les choix explicites de l'utilisateur restent prioritaires ; aucun changement au layout blur/fill, au son, à Whisper, aux encodeurs AMD/CPU, au Daily Best Of ou aux médias locaux. « Moments forts » reste en pause.
- **Release :** v0.9.3 reste la dernière version stable. Aucune version, approbation `.release-approval` ou tag n'est modifié.
- **Suite :** vérifier sur un clip Twitch réel que le mode blur sans zoom garde la webcam et les bords complets ; la PR #109 règle le niveau d'amplitude affiché lorsque le zoom est activé volontairement.


## 69. Donner une amplitude utile au zoom quand il est activé, 28 novembre 2026

- **État de départ :** PR #108 fusionnée dans `main` au commit `5162a788a688997688884f7fc879a63d587e0b74` après réussite des CI finales Linux [46121216245](https://github.com/Sreleew/GTA_rankd/actions/runs/46121216245) et Windows [46121216239](https://github.com/Sreleew/GTA_rankd/actions/runs/46121216239).
- **Défaut UX identifié :** les deux formulaires Shorts affichaient une puissance de zoom de 0 %, alors que la configuration du Studio utilise 8 %. L'utilisateur pouvait cocher le zoom dynamique sans obtenir d'effet visible tant qu'il ne déplaçait pas aussi le curseur.
- **Correction :** afficher 8 % dans le curseur et sa sortie pour les deux parcours d'import. Le checkbox `dynamic_zoom` reste décoché ; le zoom n'est donc pas appliqué tant que l'utilisateur ne l'active pas explicitement. Le texte rappelle que cette amplitude peut recadrer les bords et la webcam.
- **Tests :** vérifier les deux curseurs à 8 %, les deux sorties à 8 %, les deux cases décochées et la présence de l'avertissement dans les deux formulaires. Linux : 270 passés, 1 ignoré ; Windows : 271 passés. Ruff, pip-audit, scripts PowerShell, build et vérification du package Windows v0.9.3 réussis.
- **PR #109 :** [Give opt-in Short zoom a meaningful default strength](https://github.com/Sreleew/GTA_rankd/pull/109), branche `fix/short-zoom-strength-default`, HEAD validé `5dd54a8e5db8ac9fabde29ba7bce8bf0f41f60ea`. CI Linux [46121439806](https://github.com/Sreleew/GTA_rankd/actions/runs/46121439806) et Windows [46121439772](https://github.com/Sreleew/GTA_rankd/actions/runs/46121439772) réussies sur ce HEAD ; le présent commit de documentation devra repasser les deux plateformes avant fusion.
- **Périmètre :** uniquement l'expérience de réglage du zoom dans les deux formulaires Shorts. Aucun changement au moteur FFmpeg, aux configurations existantes, aux données locales, à l'audio, à Whisper, aux encodeurs AMD/CPU, au Daily Best Of ou aux releases. « Moments forts » reste en pause.
- **Release :** v0.9.3 reste la dernière version stable. Prévoir environ 1 à 2 lots Shorts cohérents supplémentaires et la validation réelle sur le PC Windows/AMD avant de réévaluer la prochaine publication ; aucune date n'est promise.
- **Suite :** valider Linux/Windows, puis contrôler sur un clip Twitch réel le rendu sans zoom et le rendu avec zoom explicitement activé, en vérifiant que la webcam reste lisible et que le recadrage est compris par l'utilisateur.

## 70. Fiabiliser les hooks éditoriaux et le sound design d'ouverture, 28 novembre 2026

- **État de départ :** PR #109 fusionnée dans `main` au commit `68ae8c4a56388838f04339c57e9c82c0281a0ee6`, après réussite des workflows Linux [46121620960](https://github.com/Sreleew/GTA_rankd/actions/runs/46121620960) et Windows [46121620962](https://github.com/Sreleew/GTA_rankd/actions/runs/46121620962). Les deux workflows ont terminé les tests, l'analyse statique, l'audit de dépendances et la vérification du package Windows.
- **Défaut identifié :** les hooks générés par Ollama étaient contrôlés pour les phrases incomplètes, mais pas pour les verbes d'événement non étayés, alors que les titres et descriptions utilisent déjà ce garde-fou. Lorsque la transcription et la note étaient vides, le fallback affichait aussi « WAIT FOR THE REACTION », un hook générique sans lien avec le clip. En parallèle, le validateur pouvait rejeter un hook manuel volontairement court comme « NO WAY! » à cause de la règle de longueur des citations.
- **Correction proposée :** appliquer aux seuls hooks générés le contrôle des affirmations d'événement déjà utilisé pour les titres/descriptions ; revenir au hook déterministe fondé sur la transcription si le modèle invente un vol, une récupération ou un autre événement couvert par ces règles. Préserver les hooks manuels tels que saisis, dans la limite existante de six mots. Si aucune transcription exploitable ni note éditoriale n'existe, laisser le hook vide plutôt que d'inventer une accroche générique.
- **Sound design :** ne créer et ne transmettre un effet sonore d'ouverture que si l'option est activée et qu'un hook visible existe. Si le hook est vide, ne pas jouer un impact générique sans intention éditoriale et enregistrer `hook_sound_style=null`. Le son, son volume et son décalage restent inchangés lorsqu'un hook existe.
- **Interface :** remplacer « Whoosh discret au moment fort » par « Effet sonore du hook » dans les deux formulaires. Le cue est joué au début du Short, pas au pic audio ; le libellé décrit désormais le comportement réel et ne promet pas un whoosh unique alors que plusieurs textures sont générées. Ajouter une explication dans les deux formulaires : Whisper alimente aussi le hook automatique ; sans transcription exploitable ni note de contexte, aucun hook générique n'est inventé et l'utilisateur peut saisir un hook manuel.
- **Tests ajoutés :** réponse locale du modèle avec affirmation « HE STOLE MY LAMBO » non soutenue par « I finally got my Lambo back! » ; préservation du hook manuel de deux mots « NO WAY! », y compris lorsque le titre du modèle est rejeté ; absence de hook générique sans transcription ; activation du cue uniquement si un hook visible et l'option utilisateur sont présents ; vérification du libellé dans les deux formulaires.
- **PR #110 :** [Ground generated Short hooks and avoid empty-hook sound cues](https://github.com/Sreleew/GTA_rankd/pull/110), branche `fix/short-hook-grounding-sound-cues`, fusionnée au commit `ef66fd10857b35bdc089327e19054cfbe9e2b4c9` après réussite Linux [46125369565](https://github.com/Sreleew/GTA_rankd/actions/runs/46125369565) et Windows [46125369566](https://github.com/Sreleew/GTA_rankd/actions/runs/46125369566).
- **Périmètre :** métadonnées éditoriales du Short, génération du cue et libellé UI uniquement. Aucun changement aux vidéos, aux rendus existants, aux configurations personnelles, à Whisper, au mixage FFmpeg, aux encodeurs AMD/CPU ou au Daily Best Of. « Moments forts » reste en pause.
- **Release :** v0.9.3 reste la dernière version stable. Pas de modification de version, tag ou `.release-approval`.
- **Suite :** étendre la sélection des styles de hook aux langues prises en charge, puis vérifier sur des clips Twitch réels que la classification sonore reste cohérente avec la réaction du streamer.

## 71. Adapter les styles de hook aux réactions espagnoles et portugaises, 28 novembre 2026

- **État de départ :** PR #110 intégrée dans `main` au commit `ef66fd10857b35bdc089327e19054cfbe9e2b4c9`, après réussite Linux [46125369565](https://github.com/Sreleew/GTA_rankd/actions/runs/46125369565) et Windows [46125369566](https://github.com/Sreleew/GTA_rankd/actions/runs/46125369566).
- **Défaut identifié :** `infer_hook_style` normalisait déjà les accents, mais ses lexiques de question, suspense et réaction couvraient surtout l'anglais et le français. Des accroches espagnoles ou portugaises claires comme « ¡No puede ser, es increíble! » ou « Não acredito, isso é incrível! » pouvaient donc recevoir le style générique `impact` au lieu de `reaction`.
- **Correction :** ajouter les marqueurs espagnols et portugais aux trois familles existantes : questions (`cómo/como`, `quién/quien`, `dónde/donde`, `quando`, etc.), suspense (`espera`, `mira`, `olha`, `quase`, etc.) et réactions (`increíble/increible`, `incrível/incrivel`, `não/nao`, `dios`, `deus`, etc.). La priorité du texte du hook sur le contexte reste inchangée ; les quatre animations et les sons générés ne sont pas modifiés.
- **Tests ajoutés :** classification des réactions espagnoles et portugaises, des questions espagnoles et des accroches de suspense espagnoles et portugaises ; les tests existants anglais/français et la priorité du hook sur le contexte restent en place.
- **PR #111 :** [Recognize Spanish and Portuguese Short hook styles](https://github.com/Sreleew/GTA_rankd/pull/111), branche `feat/multilingual-hook-style-cues`. Code : `8080db282ce8314f1909aa6a408084ef49c329b2` ; tests : `ffcb09ad4f9eef1ed3eb05f782f6680f3769b8c3`. Les validations Linux/Windows doivent réussir sur le HEAD final avant fusion.
- **Périmètre :** classification éditoriale du hook et tests uniquement. Aucun changement à l'audio, aux durées, au mixage, à Whisper, aux sous-titres, aux données locales, aux encodeurs AMD/CPU, au Daily Best Of ou aux releases. « Moments forts » reste en pause.
- **Release :** v0.9.3 reste la dernière version stable ; aucun numéro de version, tag ou `.release-approval` modifié.
- **Suite :** valider Linux et Windows, puis vérifier sur des clips espagnols/portugais réels que les styles de réaction, question et suspense correspondent à l'intention éditoriale sans rendre les hooks répétitifs.

## 72. Générer le hook Whisper indépendamment des sous-titres, 28 novembre 2026

- **État de départ :** 164a02dfeb48a6ef58a791263e48b6f3c7ee7216 est le HEAD de `main` après fusion de la PR #111. Aucune PR ouverte n'était présente au début du lot.
- **Problème produit :** le hook automatique dépendait entièrement de `captions_enabled`. Si les sous-titres étaient décochés (leur défaut), Whisper ne tournait pas et le hook ne pouvait utiliser que la note ou une saisie manuelle. Cela contredisait l'objectif d'un hook automatique sans obligation d'incruster les sous-titres.
- **Correction :** ajout de l'option distincte `hook_transcription_enabled`, activée par défaut dans les formulaires fichier, URL Twitch et import groupé. Les sous-titres restent désactivés par défaut et n'écrivent un SRT que si l'option correspondante est activée. Une seule transcription locale alimente à la fois le hook, les métadonnées et, si demandé, les sous-titres.
- **Rapidité et compatibilité :** l’analyse vocale est cochée par défaut dans l’interface, mais le champ API est par défaut désactivé pour préserver les clients et jobs historiques ; le formulaire envoie explicitement la valeur cochée/décochée. L’utilisateur peut désactiver l’analyse vocale pour raccourcir le traitement. Si Whisper ou son modèle est absent/incomplet et que seuls les hooks automatiques sont demandés, l'import et le rendu continuent avec un avertissement et le fallback note/hook manuel ; une demande explicite de sous-titres conserve le contrôle strict existant. Les jobs historiques sans la nouvelle clé conservent leur ancien comportement lors d'une relance.
- **Attribution et rapidité :** les sous-titres conservent le filtre vocal strict. Pour un job hook-only, le Studio utilise le filtre de diarisation uniquement s’il est déjà installé ; il ne déclenche pas son installation à la demande, qui peut prendre jusqu’à 30 minutes. Sans ce filtre, la transcription utilisée pour le hook peut inclure des dialogues du jeu ; l’interface l’explique clairement. Une fois le filtre installé par le parcours sous-titres, il est réutilisé.
- **Interface :** ajout d'une case distincte « Analyser la voix pour le hook automatique (Whisper local) », cochée par défaut, dans les deux formulaires. Les libellés de la file distinguent maintenant l'analyse vocale seule des sous-titres effectivement incrustés. Cache JavaScript actualisé.
- **Tests ajoutés/adaptés :** transcription demandée pour hook sans captions ; aucune incrustation SRT lorsque les captions sont désactivées ; API hook-only acceptée sans Whisper installé ; API désactivée par défaut pour les clients qui omettent le champ ; sérialisation UI explicite des cases cochées/décochées ; correction du sélecteur de cases dans l’import Twitch groupé (qui appelait `querySelector` au lieu de `querySelectorAll`) ; assertions des deux formulaires mises à jour pour la nouvelle version de cache JS ; option de désactivation persistée ; valeurs vérifiées pour upload et import Twitch groupé ; vérification que la diarisation optionnelle n’est ni installée ni lancée pour un hook-only ; interface contrôlée dans les deux formulaires.
- **PR #112 :** [Generate automatic Short hooks independently of captions](https://github.com/Sreleew/GTA_rankd/pull/112), branche `feat/short-hook-transcription-without-captions`, HEAD final `e358f44d9e2de5028591249507fa674de13c6e8c`, fusionnée dans `main` au commit `88962e05738c2bf0a91fb43159aab340dcd0beb3`. Les validations Linux [46132246569](https://github.com/Sreleew/GTA_rankd/actions/runs/46132246569) et Windows [46132246562](https://github.com/Sreleew/GTA_rankd/actions/runs/46132246562) ont réussi sur le commit de merge PR `7ff9f93`, qui intègre ce HEAD. Une transcription Whisper distincte alimente maintenant le hook même lorsque les sous-titres sont décochés ; le SRT et l'incrustation restent facultatifs. L'import Twitch groupé sérialise toutes ses cases à cocher. Aucune release ni modification de version.
- **Périmètre :** parcours Shorts uniquement. Pas de modification du Daily Best Of, des miniatures, du cadrage, des données locales, des paramètres existants, des encodeurs AMD/CPU ou de la fonctionnalité « moments forts » (toujours en pause).
- **Release :** v0.9.3 reste la dernière version stable. Aucun changement de version, tag ou `.release-approval`.
- **Suite :** mesurer le coût réel de Whisper hook-only sur de vrais clips et comparer les hooks produits avec/sans filtre vocal déjà installé ; vérifier qu’aucun SRT ni sous-titre incrusté n’est créé lorsque les captions sont désactivées.


## 73. Préserver le hook si la diarisation optionnelle échoue techniquement, 28 novembre 2026

- **État de départ :** PR #112 fusionnée dans `main` au commit `88962e05738c2bf0a91fb43159aab340dcd0beb3`, après réussite Linux [46132246569](https://github.com/Sreleew/GTA_rankd/actions/runs/46132246569) et Windows [46132246562](https://github.com/Sreleew/GTA_rankd/actions/runs/46132246562) sur le merge PR `7ff9f93`.
- **Défaut identifié :** pour le hook seul, l'absence du paquet de diarisation utilisait déjà la transcription Whisper brute avec avertissement. En revanche, si le paquet était présent mais que son chargement, ses dépendances ou l'analyse audio échouaient, le chemin réutilisait le filtre strict des sous-titres et supprimait tous les mots. Le hook perdait alors sa transcription malgré Whisper fonctionnel.
- **Correction :** en mode hook seul uniquement, si la diarisation est techniquement indisponible (`diarization_unavailable`), conserver les mots Whisper non filtrés et enregistrer le statut `diarization_unavailable_fallback`, la raison technique et un avertissement clair indiquant que des dialogues du jeu peuvent être inclus. Les cas où la diarisation fonctionne mais ne peut pas attribuer une voix de manière fiable (`ambiguous_speakers`, `low_word_attribution`, `no_speaker_segments`, `no_word_attribution`) restent volontairement sans fallback. Le filtrage des sous-titres reste strict et continue de supprimer les mots lorsque la diarisation est indisponible.
- **Interface et diagnostic :** l'avertissement du job est maintenant renseigné pour le fallback technique et les attributions ambiguës ; la durée du filtre est conservée dans les métriques lorsqu'une tentative a réellement eu lieu.
- **Tests ajoutés :** paquet de diarisation présent mais `SpeakerFilterError` en hook seul => fallback sur les mots Whisper et avertissement ; diarisation fonctionnelle mais voix ambiguës => aucun fallback ; les tests existants de sous-titres vérifient toujours le comportement strict.
- **PR #113 :** [Keep hook transcription when optional diarization fails](https://github.com/Sreleew/GTA_rankd/pull/113), branche `fix/hook-diarization-runtime-fallback`. Les commits de code et tests sont `eb209b8b881c425dbca913ccfe75b569791a5cd7` et `76852abb27848932263969ad7e803b03a1790b90`. CI Linux/Windows en attente sur le HEAD final de la PR.
- **Périmètre :** robustesse du hook automatique uniquement. Aucun changement au filtrage des sous-titres, à Whisper, au rendu FFmpeg, à la webcam, aux paramètres locaux, aux encodeurs AMD/CPU, au Daily Best Of ou aux releases. « Moments forts » reste en pause.
- **Release :** v0.9.3 reste la dernière version stable ; aucun numéro de version, tag ou `.release-approval` modifié.
- **Suite :** valider Linux/Windows puis comparer sur des clips réels le hook avec diarisation disponible, indisponible et ambiguë, en vérifiant que le fallback ne présente jamais sa transcription brute comme une attribution certaine au streamer.


## 74. Optimiser la préparation audio des Shorts et les imports groupés, 28 novembre 2026

- **État de départ :** main au commit c6db2c2f79bfcbeaaf18dc0b5d58e90f36a24284, après fusion de la PR #113. La PR #114 reste ouverte sur le chantier Daily Best Of ; elle n'a pas été modifiée dans ce lot Shorts.
- **Défauts identifiés :** chaque clip relançait whisper-cli --help pour détecter DTW, -ojf et -nfa ; l'analyse des pics audio chargeait l'intégralité du WAV en mémoire, ce qui pouvait provoquer une forte consommation RAM sur une longue source Twitch.
- **Corrections :** mise en cache de la détection DTW pour les 16 dernières versions de binaires Whisper. La clé combine le chemin résolu, la taille, la date de modification et la date de changement ; les erreurs et timeouts ne sont pas mis en cache. L'analyse des pics audio lit maintenant des blocs de 10 secondes avec chevauchement et conserve toutes les fenêtres partielles valides en fin de fichier. Les seuils, le calcul RMS et l'ordre des pics restent inchangés.
- **Tests ajoutés :** réutilisation du résultat --help entre deux transcriptions ; invalidation après modification du binaire ; lecture WAV bornée ; conservation des pics après une frontière de bloc et dans les fenêtres partielles finales.
- **PR #115 :** [Optimize Short audio analysis for batch imports and long Twitch sources](https://github.com/Sreleew/GTA_rankd/pull/115), branche perf/cache-whisper-cli-capabilities, code et tests validés sur le HEAD 9903e786c60c80e96888e35a30cac1c02960eaf1.
- **Validation Linux :** [workflow 46141984511](https://github.com/Sreleew/GTA_rankd/actions/runs/46141984511) réussi ; 280 tests passés, 1 ignoré ; Ruff, pip-audit et vérification du package Windows réussis.
- **Validation Windows :** [workflow 46141984531](https://github.com/Sreleew/GTA_rankd/actions/runs/46141984531) réussi ; 282 tests passés ; Ruff, pip-audit, scripts PowerShell et package Windows réussis.
- **Limite matérielle :** aucun test réel sur la RX 9060 XT ni sur un VOD de 19 heures. L'analyse ne charge plus tout le WAV en RAM, mais l'extraction audio complète crée toujours un fichier temporaire volumineux et conserve son coût disque/décodage.
- **Release :** v0.9.3 reste la version stable ; aucun numéro, tag ou .release-approval modifié. Les données locales, paramètres et encodeurs AMD/CPU ne sont pas touchés. « Moments forts » reste en pause.
- **Suite :** mesurer le gain sur un import groupé réel et valider la tenue disque/RAM sur une longue source Twitch Windows/AMD avant d'étendre le chantier.
