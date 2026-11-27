# GTA Ranked Studio | Mémo maître de reprise

> Lire ce document en premier dans chaque nouvelle conversation sur le projet. Il décrit l'état réellement livré et la structure source actuelle.

- **Dernière mise à jour :** 27 novembre 2026
- **Dernière version stable confirmée :** [0.8.7](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.7), publiée le 27 novembre 2026 avec le ZIP Windows et `SHA256SUMS.txt`.
- **État :** PR #19 à #29 fusionnées. PR #26 ajoute la saisie `HH:MM:SS`, PR #27 les lots Twitch multi-tranches, PR #28 le classement global des lots et PR #29 prépare la Release v0.8.7. La v0.8.7 est publiée et constitue la dernière version stable.
- **Dépôt :** https://github.com/Sreleew/GTA_rankd
- **Dernière Release stable confirmée :** [v0.8.7](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.7). Assets publiés : `GTA-Ranked-Studio-v0.8.7.zip` et `SHA256SUMS.txt`.
- **Archive de provenance :** `archive/releases/v0.7.8/`. C'est une archive historique de la version publiée, pas la source de développement.
- **Source active :** `app/`. Modifier directement les fichiers Python, JavaScript, CSS, HTML, tests et installateur présents dans ce dossier.
- **Mise à jour intégrée :** l'application consulte les Releases GitHub. La Release v0.8.7 contient le ZIP Windows et `SHA256SUMS.txt`; les installations v0.8.6 peuvent passer à v0.8.7 via Paramètres > Mises à jour.
- **CI PR #14 :** Linux et Windows terminés avec succès, y compris suites de régression, analyse statique, audit de dépendances et packaging. Les décomptes détaillés ne sont pas consignés ici.
- **Sécurité et packaging :** Ruff et pip-audit réussis sur Linux et Windows, aucune vulnérabilité connue ; ZIP Windows et SHA-256 vérifiés.
- **PR de maintenance :** [#10](https://github.com/Sreleew/GTA_rankd/pull/10), fusionnée dans `main`.
- **PR coupes naturelles :** [#11](https://github.com/Sreleew/GTA_rankd/pull/11), fusionnée dans `main`. Le départ du Short préfère une frontière après ponctuation ou pause de 0,75 s ; fallback temporel conservé si aucune frontière fiable n'existe.
- **PR profil de production :** [#12](https://github.com/Sreleew/GTA_rankd/pull/12), fusionnée dans `main`. VOD : candidats 60, 90, 120, 150 et 165 s ; sources Twitch plus courtes préservées.
- **CI PR #12 :** Linux 155 réussis + 1 ignoré ; Windows 156 réussis. Ruff, pip-audit, ZIP et SHA-256 validés.
- **Statut de livraison :** v0.8.6 publiée. Le ZIP Windows (193 520 octets) est attaché à la Release et GitHub expose son digest SHA-256 `bcbe46f063fc3918b3a6a9b33a25f56ed87e453fb9e2f769b763878c870cee0e`. Le fichier `SHA256SUMS.txt` est également publié.
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
py -3.11 installer/build_release_package.py --version 0.8.1 --output-dir dist
Set-Location ..
py -3.11 tools/verify_release_package.py --package app/dist/GTA-Ranked-Studio-v0.8.1.zip --checksum app/dist/SHA256SUMS.txt --version 0.8.1
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
- **Priorité produit actuelle :** lancer rapidement la chaîne GTA VI. Accepter un niveau de qualité initial de 85-90 % et privilégier un flux fiable de production/publication plutôt que des raffinements interminables. Parcours prioritaire : URL Twitch/VOD → moment fort → Short 9:16 → review → titre/description/hashtags/miniature prêts à publier.
- **Durée cible :** Shorts de 60 à 165 secondes. Les clips Twitch plus courts sont conservés tels quels, sans rallongement artificiel. Les passages VOD sont proposés en 60, 90, 120, 150 ou 165 secondes.
- **Direction des miniatures :** rendu propre, esthétique, lisible et immédiatement compréhensible, construit autour d'une vraie image du clip. Le visuel doit donner envie de cliquer sans surcharge, faux événement ou texte tronqué.
- **Évaluer sur des exemples réels.** Quand l'utilisateur envoie un clip ou un Short généré, examiner concrètement le rendu avant de décider des corrections. Distinguer les observations réelles des hypothèses.
- **Garder les contrôles accessibles après validation.** Ne pas retirer les actions de prévisualisation, téléchargement, miniature et copie du titre/description/hashtags après validation d'un Short.
- **Communication :** être direct et concis, donner les résultats concrets et signaler clairement ce qui reste non testé. Une seule prochaine action prioritaire dans le bilan.

## 10. Journal de travail récent

- **Correctif installateur v0.8.4 :** PR #14 fusionnée. `installer/check_runtime.py` ajoute `app/` à `sys.path` avant les imports. Test de régression depuis un cwd externe sans `PYTHONPATH`. CI Linux et Windows réussies (tests, Ruff, pip-audit et package). Le tag `v0.8.4` est présent ; vérifier les assets de Release avant installation.

- **Correctif v0.8.3 en préparation :** le serveur local attend 8 secondes après le lancement de PowerShell avant de s'arrêter, pour laisser le navigateur recevoir la réponse HTTP et lire le statut. Ajout d'un test de régression. Branche `fix/updater-shutdown-handshake` ; publication après validation Linux/Windows.

- **v0.8.1 publiée :** séparation runtime/dev, retrait du scaffold Best Of non relié, suppression des duplications documentaires et rapports historiques, exclusion des outils développeur et données locales du ZIP, contrôle Ruff/pip-audit, analyse PowerShell, tests Linux/Windows et vérification ZIP/SHA-256. PR #10 fusionnée et Release stable publiée.
- **v0.8.2 publiée :** PR #11 ajoute les coupes naturelles après ponctuation ou pause de 0,75 s ; PR #12 ajoute le profil 60-165 s, le scan VOD multi-durée et la migration non destructive des anciennes configurations. Les clips Twitch courts sont conservés.

- **v0.7.9 publiée :** refonte des miniatures verticales, sélection de phrases plus complètes pour les hooks/titres, garde-fous contre les événements inventés dans les métadonnées, raccords audio plus doux et conservation des clips Twitch sélectionnés.
- **Intégration :** PR #8 fusionnée dans `main`, Release stable [v0.7.9](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.9).
- **v0.8.0 publiée :** PR #9 fusionnée, cadrage intelligent activé par défaut, ZIP Windows et SHA-256 publiés. README, guide des mises à jour et processus de release synchronisés après publication.
- **Validation :** Linux 147 réussis + 1 ignoré ; Windows 148 réussis. ZIP et SHA-256 publiés.
- **À vérifier sur le PC utilisateur :** mise à jour depuis v0.8.0, préservation des données, rendu d'un Short avec cadrage intelligent et fonctionnement matériel AMD AMF/Vulkan sur RX 9060 XT.

## 11. Prochaines étapes priorisées

1. Mettre à jour le Studio depuis la v0.8.6 via **Paramètres > Mises à jour**.
2. Tester le nouveau flux sur une vraie VOD longue, idéalement celle de 19 heures : saisir la plage en `HH:MM:SS`, choisir des tranches horaires, lancer le lot et vérifier progression, erreurs et shortlist consolidée.
3. Relire les meilleurs moments avant export. Les scores audio sont normalisés à l'intérieur de chaque segment ; le classement global est indicatif.
4. Vérifier sur la RX 9060 XT l'encodage AMF, Whisper Vulkan et Ollama/Qwen pendant un cycle complet de téléchargement, analyse et rendu. Cette validation matérielle n'a pas encore été faite.
5. Corriger uniquement les défauts récurrents constatés sur les vrais rendus : coupe incompréhensible, cadrage raté, sous-titres illisibles, audio défectueux ou métadonnées trompeuses.
6. Démarrer la publication régulière et mesurer les résultats avant d'investir du temps dans les fonctions secondaires.

## 12. Message de reprise prêt à copier

 > Nous reprenons GTA Ranked Studio. Lis `docs/CONTINUATION.md` puis `docs/WORKING-AGREEMENT.md`. La dernière Release stable est v0.8.6, publiée avec ZIP Windows et SHA256SUMS. Les PR #19 à #26 sont fusionnées. La source de développement est `app/`. Préserve les données locales, valide les changements transversaux sous Linux et Windows, et publie une Release stable après validation. La RX 9060 XT n'a pas encore été validée physiquement pour AMF/Vulkan. L'utilisateur demande de travailler de façon autonome, sans demander de confirmations répétitives, jusqu'à un résultat propre et publié.
