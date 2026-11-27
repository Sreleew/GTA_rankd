# GTA Ranked Studio | Mémo maître de reprise

> Lire ce document en premier dans chaque nouvelle conversation sur le projet. Il décrit l'état réellement livré et la structure source actuelle.

- **Dernière mise à jour :** 27 novembre 2026
- **Dernière version stable confirmée :** [v0.8.7](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.7), publiée le 27 novembre 2026 avec le ZIP Windows et `SHA256SUMS.txt` (SHA-256 : `8239f0788fa788f793ae19228d589443e76ea32477cd04020e1f0267df1307f3`).
- **État :** PR #19 à #29 fusionnées. PR #26 ajoute la saisie `HH:MM:SS`, PR #27 les lots Twitch multi-tranches, PR #28 le classement global des lots et PR #29 prépare la publication de la v0.8.7, désormais publiée et dernière version stable.
- **Dépôt :** https://github.com/Sreleew/GTA_rankd
- **Archive de provenance :** `archive/releases/v0.7.8/`. C'est une archive historique de la version publiée, pas la source de développement.
- **Source active :** `app/`. Modifier directement les fichiers Python, JavaScript, CSS, HTML, tests et installateur présents dans ce dossier.
- **Mise à jour intégrée :** l'application consulte les Releases GitHub. La Release v0.8.7 contient le ZIP Windows et `SHA256SUMS.txt`; les installations v0.8.6 peuvent passer à v0.8.7 via Paramètres > Mises à jour.
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
py -3.11 installer/build_release_package.py --version 0.8.7 --output-dir dist
Set-Location ..
py -3.11 tools/verify_release_package.py --package app/dist/GTA-Ranked-Studio-v0.8.7.zip --checksum app/dist/SHA256SUMS.txt --version 0.8.7
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
- **Communication :** être direct et concis, donner les résultats concrets et signaler clairement ce qui reste non testé. Les réponses doivent rester courtes et les gros travaux être découpés en petits lots pour éviter les expirations de réception de ChatGPT. Une seule prochaine action prioritaire dans le bilan.

## 10. Journal de travail récent

- **Réorientation produit demandée le 27 novembre 2026 :** priorité au Short créé directement depuis un clip Twitch, puis au Daily Best Of ; la fonctionnalité Moments forts est explicitement en pause. Ne pas poursuivre le chantier de VOD longues, sauf bug bloquant pour les priorités.
- **Audit ciblé des parcours :** l'import URL Short existe et utilise yt-dlp ; l'UI gère montage, captions, réglages, hook/contexte, file, preview, téléchargement, miniature et métadonnées. Le hook de progression yt-dlp a été corrigé par la PR #32 afin d'afficher l'avancement réel pendant le téléchargement. Les clips de moins de 165 secondes sont conservés en entier par `select_excerpt_range`.
- **PR #32 fusionnée : progression du téléchargement Twitch Short.** Le hook yt-dlp lit `downloaded_bytes` et `total_bytes` ou `total_bytes_estimate`, affiche la progression de 10 à 19 % avec throttling des écritures SQLite, puis affiche « Téléchargement terminé · préparation du Short ». Test simulé : 25 %, 75 % avec taille estimée, et transition à la fin. CI PR Linux [45996501467](https://github.com/Sreleew/GTA_rankd/actions/runs/45996501467) et Windows [45996501488](https://github.com/Sreleew/GTA_rankd/actions/runs/45996501488) réussies. PR fusionnée dans `main` via commit `03c5010cae2dfd27d673060ef751a6b80dd4a8d4`. CI post-fusion Linux [45996808865](https://github.com/Sreleew/GTA_rankd/actions/runs/45996808865) réussie ; Windows [45996808775](https://github.com/Sreleew/GTA_rankd/actions/runs/45996808775) encore en cours lors de cette mise à jour.
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

## 11. Prochaines étapes priorisées

1. **Créer un Short depuis un clip Twitch : priorité immédiate.** Le premier lot de progression du téléchargement est fusionné dans `main` via PR #32 ; les CI Linux/Windows de la PR sont vertes. Le contrôle Windows post-fusion restait en cours lors de la dernière vérification. Le parcours existant passe par `/api/shorts/url`, yt-dlp et `JobRunner`, puis ffprobe/audio/Whisper, sélection de l'extrait, diarisation dominante expérimentale, métadonnées locales avec Ollama facultatif, ASS, rendu vertical FFmpeg, contrôle qualité et review. Les sources de moins de 165 secondes sont préservées intégralement par le seuil actuel. Premier défaut concret à traiter : pendant le téléchargement yt-dlp, le job reste à 10 % car le progress hook ne met à jour que l'annulation ; afficher une progression réelle et throttled avant d'améliorer les autres étapes. Auditer ensuite validation/erreurs URL, titre/streamer, voix sous-titrées, hook, miniature et review. Distinguer tests simulés et téléchargements/rendus réels.
2. **Daily Best Of : deuxième priorité.** L'écran actuel est un placeholder ; aucun moteur de scoring, de sélection ou d'assemblage n'est encore implémenté. La table locale `clips` contient déjà les Shorts validés avec leur source, leur rendu, leur miniature, leur streamer, durée et date. Partir de ces clips validés, établir le flux MVP de sélection/ordre/inclusion, classement quotidien et assemblage horizontal 16:9 de 9 à 11 minutes. Préserver leurs fichiers sources, rendus, métadonnées et données locales.
3. Conserver le pipeline de Short comme socle : les actions de prévisualisation, téléchargement, miniature et copie des métadonnées doivent rester accessibles après validation.
4. **Moments forts : en pause.** Ne pas ajouter de fonctions, optimiser les scores ou étendre les scans VOD pour le moment. N'intervenir que si un bug bloque directement les parcours prioritaires ou une dépendance existante.
5. Vérifier sur la RX 9060 XT l'encodage AMD AMF, Whisper Vulkan et Ollama/Qwen pendant des cycles réels de création de Short et de Best Of. Ne pas présenter la CI comme une validation matérielle.
6. Livrer chaque amélioration par petits lots cohérents, avec tests ciblés puis CI Linux/Windows, fusion et release lorsque les changements applicatifs sont prêts. Mettre ce mémo à jour à chaque lot.

## 12. Message de reprise prêt à copier

> Nous reprenons GTA Ranked Studio. Lis `docs/CONTINUATION.md` et `docs/WORKING-AGREEMENT.md`. Dernière Release stable : v0.8.7. Priorité 1 : améliorer « Créer un Short » directement depuis un clip Twitch, du collage de l'URL jusqu'au rendu 9:16, aux métadonnées et à la review. Priorité 2 : développer « Daily Best Of » à partir des clips validés de la bibliothèque, en 16:9 sur 9 à 11 minutes. Laisser « Moments forts » en pause, sans supprimer ce qui existe. Travailler directement dans GitHub, par petits lots courts, tests adaptés, fusion/release après validation. Mettre obligatoirement ce mémo à jour à chaque lot avec les décisions de l'utilisateur, les modifications, PR, commits, tests et limites. Réponses courtes, préserver les données locales et distinguer CI, tests simulés et validation réelle sur le PC.
