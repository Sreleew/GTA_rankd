# GTA Ranked Studio

Application Windows locale pour analyser des clips et VOD GTA, repérer les moments intéressants et produire des Shorts verticaux prêts à publier.

**Dernière version stable : v0.8.0.** La mise à jour est proposée dans l'application depuis **Paramètres > Mises à jour**. La mise à jour est proposée dans l'application depuis **Paramètres > Mises à jour**.

[Consulter la Release v0.8.0](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.0)

## Fonctionnalités

- Import de vidéos locales et de clips/VOD Twitch accessibles via yt-dlp.
- Détection audio et transcription Whisper locale pour classer les moments forts.
- Score d'accroche distinct sur les cinq premières secondes.
- Création de Shorts 1080 × 1920 avec cadrage intelligent : gameplay agrandi, hook en haut, sous-titres en bas et focus horizontal réglable. Les modes plein écran et fond flouté restent disponibles.
- Sous-titres, hooks, titres et descriptions éditorialement vérifiés contre les phrases ASR incomplètes.
- Miniatures verticales plus épurées, composées à partir d'images réelles du clip, avec titre court et lisible.
- Métadonnées générées avec Ollama/Qwen local si installé, avec solution de repli sans IA.
- Contrôle qualité après export : MP4, durée, résolution, codec, audio, écrans noirs, images figées, silences et horodatages des sous-titres.
- Prévisualisation, téléchargement, miniature et copie des métadonnées toujours disponibles après validation.

Les traitements vidéo et IA restent locaux. Les médias, modèles, bases, réglages et exports ne sont pas envoyés vers un service cloud par le pipeline.

## Organisation du dépôt

- `app/` : **source de code active et unique** de l'application, tests, installateur, interface et scripts.
- `docs/` : mémoire projet, méthode de travail, feuille de route et processus de publication.
- `archive/releases/v0.7.8/` : archive source figée conservée comme provenance de la Release v0.7.8. Elle n'est pas utilisée pour développer.
- `.github/workflows/` : tests Linux/Windows et publication contrôlée des Releases.

Le code se modifie directement dans `app/`. Il n'y a plus de chaîne de reconstruction par correctifs historiques pour développer une fonctionnalité.

## Développement local

Dans PowerShell :

```powershell
Set-Location app
py -3.11 -m pip install -r requirements.txt
python tools/check_project_memory.py
python -m pytest -q
node --check studio/web/static/app.js
python installer/build_release_package.py --version 0.8.0 --output-dir dist
```

Pour une nouvelle installation, utiliser `app/INSTALL.bat`. Ne jamais remplacer un `config.yaml` existant par le fichier modèle pendant une mise à jour.

## Validation et publication

Chaque PR vers `main` déclenche l'audit Linux et la validation Windows sur le code de `app/`. Le workflow de publication reconstruit le ZIP à partir de cette même source et vérifie son intégrité ainsi que l'exclusion des données locales.

Une Release stable n'est publiée qu'après un changement explicite de `.release-approval` sur `main`, avec une version identique à `VERSION.txt`. Le lancement manuel depuis GitHub Actions reste limité à une Release brouillon.

- [Mémo de continuité](docs/CONTINUATION.md)
- [Méthode de travail](docs/WORKING-AGREEMENT.md)
- [Processus de publication](docs/RELEASE_PROCESS.md)
- [Validation matérielle Windows/AMD](docs/WINDOWS-HARDWARE-VALIDATION.md)
