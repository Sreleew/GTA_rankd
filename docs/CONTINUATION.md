# GTA Ranked Studio | Mémo maître de reprise

> Lire ce document en premier dans chaque nouvelle conversation sur le projet. Il décrit l'état réellement livré et la structure source actuelle.

- **Dernière mise à jour :** 27 novembre 2026
- **Progression des releases :** à chaque relance de développement, le compte rendu doit indiquer le lot livré, les PR/CI, l'état d'avancement vers la prochaine version et une estimation actualisée du nombre de lots restants avant sa publication. Cette estimation doit être réévaluée à chaque session, sans promettre une date artificielle.
- **Dernière version stable confirmée :** [v0.8.9](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.9), publiée le 27 novembre 2026. Correctif de redémarrage et de confirmation de version après mise à jour.
- **État :** PR #64 (pause des sous-titres et suppression webcam), #65 (réutilisation des probes FFprobe), #66 (mesure des temps de traitement Short), #67 (affichage des durées dans les cartes de Shorts), #68 (relance des clips Twitch en échec depuis leur lot), #69 (miniature de secours non bloquante) et #72 (historique persistant Daily Best Of) fusionnées dans `main`. Le lot #73 ajoute la relance manuelle des rendus Best Of depuis l'historique et est en cours. La v0.8.9 reste la dernière Release stable publiée ; les améliorations récentes seront regroupées dans une release ultérieure. Les PR #47 à #49 ajoutent les hooks cinétiques, le cadre éditorial du gameplay et le sound design local adapté à l'intention du hook. La PR #50 ajoute plusieurs impulsions de zoom pilotées par les accents audio.
- **Dépôt :** https://github.com/Sreleew/GTA_rankd
- **Archive de provenance :** `archive/releases/v0.7.8/`. C'est une archive historique de la version publiée, pas la source de développement.
- **Source active :** `app/`. Modifier directement les fichiers Python, JavaScript, CSS, HTML, tests et installateur présents dans ce dossier.
- **Mise à jour intégrée :** l'application consulte les Releases GitHub. La Release v0.8.8 contient le ZIP Windows et `SHA256SUMS.txt`; les installations v0.8.7 peuvent passer à v0.8.8 via Paramètres > Mises à jour.
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
- **Validation matérielle :** le PC AMD Radeon RX 9060 XT n'a pas encore été validé physiquement pour AMF/Vulkan après mise à jour.
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
- Miniatures issues d'images réelles du clip, avec une composition verticale 1080 × 1920 plus épurée, gameplay mis au premier plan, fond assombri, titre court et branding discret.
- File de traitement, progression FFmpeg, annulation, prévisualisation, validation/rejet et bibliothèque de clips.
- Après validation d'un Short, Prévisualiser, Télécharger, Miniature et Copier le titre, la description, les hashtags et le post restent accessibles.
- La shortlist de moments forts écarte les transcriptions longues quasi identiques issues de passages éloignés, sans filtrer les réactions courtes ni les scans audio seuls.
- Le calcul des scores utilise des index temporels sur les fenêtres audio et les mots Whisper, avec fallback linéaire pour les entrées non triées.
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
- **Priorités produit actuelles, dans cet ordre :** (1) fiabiliser et optimiser « Créer un Short » directement à partir d'un clip Twitch : URL → téléchargement → montage vertical → review → métadonnées et miniature prêtes à publier ; (2) développer « Daily Best Of » à partir des clips validés de la bibliothèque locale, avec sélection et assemblage horizontal 16:9 d'environ 9 à 11 minutes. Accepter un premier niveau de qualité de 85-90 % et privilégier un flux fiable de production/publication. **Mettre « Moments forts » en pause** : ne pas développer ni raffiner cette fonctionnalité pour le moment, sans la supprimer ni casser le code existant.
- **Durée cible :** Shorts de 60 à 165 secondes. Les clips Twitch plus courts sont conservés tels quels, sans rallongement artificiel. Les passages VOD sont proposés en 60, 90, 120, 150 ou 165 secondes.
- **Direction des miniatures :** rendu propre, esthétique, lisible et immédiatement compréhensible, construit autour d'une vraie image du clip. Le visuel doit donner envie de cliquer sans surcharge, faux événement ou texte tronqué.
- **Évaluer sur des exemples réels.** Quand l'utilisateur envoie un clip ou un Short généré, examiner concrètement le rendu avant de décider des corrections. Distinguer les observations réelles des hypothèses.
- **Garder les contrôles accessibles après validation.** Ne pas retirer les actions de prévisualisation, téléchargement, miniature et copie du titre/description/hashtags après validation d'un Short.
- **Communication :** être direct et concis, donner les résultats concrets et signaler clairement ce qui reste non testé.
- **Pilotage proactif confirmé le 27 novembre 2026 :** l'utilisateur ne souhaite pas devoir arbitrer les choix techniques ou connaître le développement. L'assistant prend l'initiative de piloter le produit et les décisions techniques, explique les conséquences en termes simples et recommande clairement de ne pas construire une fonctionnalité lorsqu'elle est trop complexe, lente, coûteuse à maintenir, peu utile ou peu rentable par rapport à sa valeur. Toujours comparer le bénéfice attendu au temps de développement, au temps de traitement, à la fiabilité, à la maintenance et à l'impact sur l'expérience utilisateur. Proposer des alternatives plus simples, supprimer ou reporter les idées à faible ROI, anticiper les besoins et pousser le concept vers un produit premium sans sur-ingénierie. Ne demander un arbitrage utilisateur que lorsqu'il dépend réellement de ses goûts, de ses objectifs ou d'une contrainte inaccessible au développeur. L'utilisateur fait confiance à l'assistant pour le guider et attend une posture proactive, experte et honnête.
- **Suivi de progression demandé le 27 novembre 2026 :** terminer chaque relance par un indicateur lisible de progression vers la prochaine Release (lots terminés/restants, contenu restant et estimation de la prochaine mise à jour). Ne pas laisser l'utilisateur deviner où en est le chantier. Les réponses doivent rester courtes et les gros travaux être découpés en petits lots pour éviter les expirations de réception de ChatGPT. Une seule prochaine action prioritaire dans le bilan.

## 10. Journal de travail récent

- **Réorientation produit demandée le 27 novembre 2026 :** priorité au Short créé directement depuis un clip Twitch, puis au Daily Best Of ; la fonctionnalité Moments forts est explicitement en pause. Ne pas poursuivre le chantier de VOD longues, sauf bug bloquant pour les priorités.
- **Audit ciblé des parcours :** l'import URL Short existe et utilise yt-dlp ; l'UI gère montage, captions, réglages, hook/contexte, file, preview, téléchargement, miniature et métadonnées. Le hook de progression yt-dlp a été corrigé par la PR #32 afin d'afficher l'avancement réel pendant le téléchargement. Les clips de moins de 165 secondes sont conservés en entier par `select_excerpt_range`.
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

1. **Créer un Short depuis un clip Twitch : priorité immédiate.** Le parcours URL, téléchargement, progression, montage vertical, sous-titres, hook, miniature, métadonnées et review existe. PR #42 permet de relancer un job Twitch échoué depuis son URL d'origine si le média local n'a pas été téléchargé, tout en réutilisant le fichier local lorsqu'il existe. Prochaine étape : valider le parcours complet avec un vrai clip sur le PC Windows et corriger les défauts constatés.
2. **Daily Best Of : deuxième priorité.** PR #41 ajoute le constructeur de sélection par date, l'ajout/retrait, l'ordre manuel, le calcul de durée et la validation serveur des Shorts validés. Prochaine étape : rendre le plan persistant, puis produire un export horizontal 16:9 de 9 à 11 minutes avec mixage et contrôle qualité.
3. Conserver les actions de prévisualisation, téléchargement, miniature et copie des métadonnées après validation d'un Short.
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
- **Validation :** CI Linux et Windows à effectuer sur la PR. Aucun rendu sur le PC AMD de l'utilisateur n'est revendiqué.
