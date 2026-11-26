# Mises à jour GTA Ranked Studio

## v0.8.1 : audit de maintenance en préparation

Cette version candidate regroupe la séparation stricte des dépendances runtime et dev, l'allègement de l'installation, le retrait du scaffold Best Of non relié au moteur Shorts, la documentation canonique unique, le linter Ruff, l'audit pip-audit des dépendances runtime et la validation centralisée des packages. Elle n'est pas publiée tant que les contrôles Linux, Windows, sécurité et package ne sont pas terminés.

## v0.8.0 : cadrage vertical intelligent (disponible en mise à jour stable)

Le nouveau mode par défaut compose les Shorts en 9:16 avec un panneau gameplay agrandi, un hook au-dessus et les sous-titres dans une zone basse dédiée. Le focus horizontal est réglable et positionné par défaut à 80 % pour mieux préserver une facecam incrustée à droite. Les sources portrait restent proportionnelles ; les modes plein écran recadré et vidéo entière avec fond flouté restent disponibles. CI Linux : 147 tests réussis, 1 ignoré. CI Windows : 148 tests réussis, aucun ignoré. La validation sur plusieurs clips Twitch réels et sur le PC AMD reste à faire. La version stable est publiée : https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.0. Dans l'application, ouvrir **Paramètres > Mises à jour**, puis rechercher et installer la mise à jour.

## v0.7.9 : disponible en mise à jour stable

La version stable v0.7.9 est publiée : https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.9. Elle améliore la génération des Shorts : miniatures verticales plus épurées et centrées sur une vraie capture du clip, titres et hooks protégés contre les phrases ASR tronquées, et accroches plus courtes. Le montage intelligent conserve les clips Twitch déjà sélectionnés et ne retire que des pauses longues lorsque les timestamps mot à mot sont fiables.

La mise à jour préserve les réglages et données locales. La validation matérielle AMF/Vulkan sur le PC cible reste à effectuer après installation.


## v0.7.8 : disponible en mise à jour stable

La version stable **v0.7.8** est publiée depuis le 25 novembre 2026. Dans l'application, ouvrir **Paramètres > Mises à jour**, cliquer sur **Rechercher une mise à jour**, puis choisir **Télécharger et installer**. L'application se ferme et redémarre après installation.

La Release contient `GTA-Ranked-Studio-v0.7.8.zip` et son contrôle d'intégrité `SHA256SUMS.txt`. Le package exclut la configuration personnelle, les bases de données, les médias et les exports locaux.

Lien de la Release : https://github.com/Sreleew/GTA_rankd/releases/tag/v0.7.8.

## Côté utilisateur

Dans GTA Ranked Studio, ouvrir **Paramètres > Mises à jour**, cliquer sur **Rechercher une mise à jour**, puis sur **Télécharger et installer** si une version est proposée. L'application se ferme et se relance après installation.

La première installation d'une version qui contient le système d'update (v0.3.4) est une mise à jour de transition depuis v0.3.3.3 : l'ancien fichier UPDATE-FROM-ARCHIVE.bat reste nécessaire une seule dernière fois. Après cette transition, plus besoin d'extraire des ZIP manuellement.

## Côté publication

Le dépôt public Sreleew/GTA_rankd est la source des Releases stables. Le client de mise à jour consulte ces Releases, pas les branches ni les artifacts GitHub Actions.

1. Synchroniser VERSION.txt, NOTES-vX.Y.Z.txt, README et la documentation.
2. Ouvrir une PR vers main et vérifier les validations Linux et Windows.
3. Après fusion, créer ou mettre à jour `.release-approval` sur main avec le même numéro que VERSION.txt. Ce commit constitue l'autorisation explicite de publication et déclenche le workflow.
4. Le workflow vérifie la source canonique et le paquet, puis publie la Release stable contenant GTA-Ranked-Studio-vX.Y.Z.zip et SHA256SUMS.txt.
5. En mode manuel depuis Actions, le workflow exige une confirmation et crée uniquement une Release brouillon.

Le paquet est généré par installer/build_release_package.py. Le script exclut les environnements virtuels, les vidéos, les rendus, les bases de données, les journaux et les modèles/outils locaux.

## Sécurité et intégrité

- Le client ne contacte que l'API GitHub de ce dépôt et des URL d'assets de Releases GitHub en HTTPS.
- Le client vérifie la somme SHA-256 avant installation.
- Le ZIP est testé avant extraction.
- L'installateur n'écrase pas config.yaml ni les données personnelles.
- Les dossiers studio, installer et docs sont sauvegardés sous work/updates/rollback-*. Les tests ne sont pas distribués dans le ZIP utilisateur.
- L'installation est restaurée si une erreur survient pendant le remplacement.
- La mise à jour est lancée hors du processus de l'application, puis l'application redémarre.

## Limites connues de v0.3.4

Le téléchargement, le hash et la structure du ZIP sont vérifiés. Le script d'installation PowerShell doit encore être validé sur Windows réel, car le pipeline de test exécuté dans un environnement non-Windows ne peut pas simuler le verrouillage de processus et le redémarrage Windows.

## v0.3.5 : Whisper DTW

Le diagnostic exige les options -dtw, -ojf et -nfa. Le traitement ajoute -nfa pour désactiver Flash Attention et laisser whisper.cpp calculer les timestamps DTW. La validation finale consiste à confirmer des valeurs t_dtw non négatives sur les tokens parlés.

## v0.3.6 : journalisation de l’updater

Le journal last-update.log est initialisé avant le lancement PowerShell et powershell-output.log capture sa sortie console. Si PowerShell échoue immédiatement, le serveur GTA Ranked Studio reste actif et l’erreur est affichée dans l’interface. L’installateur utilise des tableaux simples compatibles Windows PowerShell 5.1 et écrit sa progression dans le journal.

## v0.4.0 : Moments forts

La page Moments forts ajoute l'analyse locale de fichiers vidéo et de VOD/clips Twitch. Les VOD peuvent être limitées à une plage de 3 heures maximum. L'analyse combine énergie audio, densité de transcription Whisper et mots de réaction pour proposer jusqu'à huit passages de 35 secondes. Le candidat sélectionné est envoyé au pipeline Shorts existant via un découpage source_range.

La première version n'analyse pas encore l'image et ne prétend pas comprendre la scène du jeu. Les scores classent des signaux audio/texte et doivent être validés par l'utilisateur.

## v0.4.1 : analyse des VOD longues

L'inspection FFprobe après téléchargement Twitch utilise maintenant un délai calculé selon la taille du fichier (minimum 5 minutes, maximum 30 minutes). La progression distingue l'inspection vidéo de l'analyse audio. Les autres traitements Shorts conservent leur délai FFprobe par défaut.

## v0.4.2 : découpage réel des VOD Twitch

Le téléchargement de plages horaires Twitch utilise l'option Python download_ranges de yt-dlp. Les horaires de début et de fin sont donc appliqués au fichier téléchargé, plutôt que seulement conservés dans les métadonnées du scan. La limite de 3 heures par analyse et le correctif FFprobe v0.4.1 sont conservés.

## v0.5.0 : moments forts adaptatifs et webcam

Le scan compare plusieurs durées de passages, de 25 à 60 secondes, puis sélectionne les candidats les mieux classés sans chevauchement. Lors de l'analyse, tu peux indiquer dans quel coin de la VOD se trouve la webcam. Cette zone est ensuite extraite et superposée au gameplay dans le rendu vertical. Les processus externes utilisés sous Windows ne créent plus de fenêtres console parasites ; leurs sorties restent consignées dans les logs.

## v0.5.1 : rendu vertical sans recadrage

Le rendu par défaut conserve l'image source entière, centrée dans le format 9:16, avec une copie agrandie et floutée en arrière-plan. Le zoom dynamique est désactivé par défaut. La webcam incrustée dans la VOD reste visible dans l'image complète ; le logiciel ne l'extrait plus séparément.

## v0.6.0 : diarisation, hooks et téléchargements

Le mode « Voix dominante uniquement (bêta) » identifie les intervenants sur l'audio du Short final et ne conserve les mots de la voix dominante que si l'écart entre locuteurs est suffisamment clair. Le moteur CPU local est installé à la demande ; en cas d'incertitude, toutes les voix restent sous-titrées. Les hooks sont raccourcis et fondés sur la transcription, la carte de contexte est désactivée par défaut, et la génération de métadonnées est limitée à 20 secondes. Les téléchargements Twitch sont limités à 1080p avec davantage de fragments concurrents et de tentatives. Les téléchargements du modèle Whisper reprennent les fichiers partiels lorsque le serveur accepte HTTP Range.

## v0.6.1 : finition du formulaire de voix

Correction mineure de l'espacement du sélecteur « Voix à sous-titrer ». Aucun changement fonctionnel sur la diarisation ou le rendu.

## v0.6.2 : sélection stricte des moments forts

La détection ne s'arrête plus à huit candidats. GTA Ranked Studio conserve tous les passages distincts dont le score est strictement supérieur à 80/100 et masque les autres. Le classement par score et l'espacement entre passages restent actifs. Le score demeure une heuristique locale basée sur l'énergie audio, la densité de parole et les mots de réaction ; il ne comprend pas encore les événements visuels du gameplay.

## v0.7.0 : social publishing kit et annulation des traitements

GTA Ranked Studio génère désormais des titres, descriptions et hashtags spécifiques à YouTube Shorts, TikTok et Instagram Reels. Un seul appel Ollama local est limité à 8 secondes et un fallback déterministe garantit la disponibilité des exports. Chaque Short est accompagné de trois fichiers texte prêts à copier/coller. La miniature utilise une image réelle du clip et une direction artistique originale GTA Ranked, sans génération d'image distante. Les traitements Shorts et Moments forts peuvent être annulés depuis leur carte ; FFmpeg et Whisper sont interrompus proprement.

## v0.7.1 : miniatures GTA et texte social plus naturel

Les miniatures sont désormais créées à partir d'une vraie image de la vidéo source au moment fort, puis composées en poster vertical 1080x1920 avec une identité GTA Ranked plus forte et sans les grands espaces vides du Short vertical. Le titre et la légende sont unifiés pour YouTube Shorts, TikTok et Instagram Reels ; un seul bouton copie l'ensemble du post. La génération locale reste limitée à un appel Ollama et huit secondes maximum, avec fallback instantané.

## v0.7.2 : sélection d'images de couverture

La couverture analyse plusieurs images du passage et privilégie une capture détaillée proche du moment saillant de la transcription. Les titres et miniatures évitent les phrases tronquées.

## v0.7.3 : textes sociaux plus naturels

Les titres sont plus courts et orientés action. Les descriptions ajoutent du contexte au lieu de répéter le titre et les formulations promotionnelles génériques sont écartées.

## v0.7.4 : diagnostic Whisper Vulkan

Le diagnostic GPU vérifie le backend Vulkan réellement sélectionné et l'allocation du modèle sur ce backend. Le résultat est lié au binaire et au modèle utilisés.

## v0.7.5 : fiabilisation de l'interface GPU

Le bouton de test Vulkan bénéficie d'un chargement JavaScript versionné et son état de progression est préservé pendant les actualisations périodiques.

## v0.7.6 : test réel Ollama/Qwen

Ajout d'une route dédiée qui vérifie le serveur Ollama local, la présence du modèle configuré et une courte inférence locale.

## v0.7.7 : robustesse du contrôle Ollama

La délégation d'événement accepte les anciens et nouveaux identifiants de bouton, et la page d'accueil force la revalidation du HTML pour éviter les états bloqués par le cache.

## v0.7.8 : actions conservées après validation

Les actions de prévisualisation, téléchargement, miniature et copie des éléments de publication restent disponibles après validation d'un Short. La validation ne doit modifier que le statut éditorial et l'entrée de bibliothèque.

## Mémoire de continuité obligatoire

À chaque nouvelle version, mettre à jour docs/CONTINUATION.md, README.md, docs/UPDATES.md et NOTES-vX.Y.Z.txt. Le contrôle python tools/check_project_memory.py doit réussir avant la construction d'une release. Le mémo est la première source à lire pour reprendre le projet dans une nouvelle conversation.


## Classement des moments forts : score d'accroche

Le classement ajoute un indicateur heuristique d'accroche sur les cinq premières secondes, visible séparément sur chaque candidat et pondéré à 10 % du score global. Lorsque Whisper est absent, l'analyse peut toujours faire remonter un passage à partir de l'énergie audio seule. La valeur est enregistrée avec une migration SQLite compatible avec les bases existantes.


## v0.7.8 : contrôle qualité automatique post-export

Après chaque rendu, GTA Ranked Studio vérifie la structure du MP4, sa durée, ses dimensions, son codec et la présence de la piste audio attendue. Une passe d'analyse vidéo/audio signale les écrans noirs, images potentiellement figées et silences prolongés. Les événements ASS et les horodatages de transcription sont comparés à la durée finale. Le rapport est visible sur la carte du Short. Les alertes restent non bloquantes : elles facilitent la revue sans rejeter les choix créatifs intentionnels.
