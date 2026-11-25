# GTA Ranked Studio

Application Windows locale pour analyser des clips et VOD GTA, repérer les passages intéressants et produire des Shorts verticaux avec leurs éléments de publication.

**Dernière version stable : 0.7.8**, publiée le 25 novembre 2026. Pour l'installer depuis une version antérieure, ouvrir **Paramètres > Mises à jour**, puis cliquer sur **Rechercher une mise à jour**.

## Fonctionnalités principales

- Import de vidéos locales et de clips/VOD Twitch accessibles via yt-dlp, avec plage horaire facultative.
- Détection audio + transcription Whisper, classement des moments forts et estimation de l'accroche sur les cinq premières secondes.
- Le classement reste fonctionnel sans Whisper : l'énergie audio seule peut suffire à faire ressortir un passage.
- Shorts verticaux 1080 × 1920, conservation de l'image source complète et fond flouté par défaut.
- Transcription locale, sous-titres, filtre de réactions et mode expérimental de voix dominante.
- Hooks, titres, descriptions et hashtags générés par Ollama/Qwen local si installé, avec fallback déterministe.
- Miniatures issues d'images réelles du clip, habillage GTA Ranked et sound design.
- File de traitement, progression, annulation, prévisualisation, validation et bibliothèque de clips.
- Après validation, les actions Prévisualiser, Télécharger, Miniature et copie des métadonnées restent disponibles.
- Contrôle qualité automatique post-export : validité MP4, durée, résolution, piste audio, écrans noirs, images figées, silences prolongés et horodatages des sous-titres. Les alertes guident une revue humaine et ne bloquent pas automatiquement le fichier.
- Mises à jour via les GitHub Releases publiques de ce dépôt.

## Limites connues

La détection des moments forts repose sur l'audio et le texte : elle ne comprend pas encore les événements visuels du gameplay. Le filtre lexical des réactions ne sépare pas les voix lorsque le streamer et les personnages sont mélangés. La diarisation reste expérimentale. La publication sur les plateformes est manuelle.

## Architecture

- Interface locale : FastAPI + HTML/CSS/JavaScript.
- Encodage : FFmpeg H.264 AMD AMF si disponible, fallback libx264.
- Transcription : whisper.cpp local, Vulkan si disponible, fallback CPU.
- Métadonnées : Ollama/Qwen en local, facultatif.
- Téléchargements : yt-dlp pour les URLs accessibles.
- Profil matériel de référence : Windows et AMD Radeon RX 9060 XT 16 Go. Les performances GPU doivent être validées sur la machine Windows cible.

Les médias, transcriptions, rendus, modèles, paramètres et bases restent locaux. Ne jamais publier `config.yaml`, vidéos, bases SQLite, modèles téléchargés, .venv, logs ou secrets.

## Développement

```powershell
Copy-Item config.yaml.default config.yaml
python -m pip install -r requirements.txt
python tools/check_project_memory.py
python -m pytest -q
node --check studio/web/static/app.js
```

Construire un ZIP avec `python installer/build_release_package.py --version 0.7.8 --output-dir dist`.

## Validation et publication

Le workflow `Windows runtime validation` vérifie la source canonique sur Windows, exécute les tests PowerShell et construit le paquet de mise à jour. Il ne remplace pas les tests matériels sur la RX 9060 XT.

Une publication stable est déclenchée uniquement par un commit explicite qui crée ou met à jour `.release-approval` sur `main`, avec un numéro identique à `VERSION.txt`. Le workflow vérifie la source canonique, les tests et le ZIP avant de publier. Le lancement manuel reste disponible pour produire une Release brouillon.

- [Mémo de continuité](docs/CONTINUATION.md)
- [Processus de validation et de publication](docs/RELEASE_PROCESS.md)
- [Checklist de validation Windows et AMD](docs/WINDOWS-HARDWARE-VALIDATION.md)

## Reprise du projet

**Lire en premier [docs/CONTINUATION.md](docs/CONTINUATION.md).** Ce mémo maître doit être mis à jour à chaque version avec les fonctionnalités, commits, résultats de tests, limites et prochaines tâches. Le contrôle `tools/check_project_memory.py` vérifie que le mémo et les notes correspondent à `VERSION.txt`.
