# GTA Ranked Studio

Application Windows locale pour transformer des clips et VOD GTA en Shorts verticaux prêts à relire et publier.

**Dernière version stable : v0.8.3.**

[Consulter la Release stable v0.8.2](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.2)

## Fonctionnalités

- Import de vidéos locales et de clips/VOD Twitch accessibles via yt-dlp.
- Analyse audio et transcription Whisper locale pour classer les moments forts.
- Score d'accroche distinct sur les cinq premières secondes.
- Shorts 1080 × 1920 de 60 à 165 secondes, avec coupes naturelles, cadrage intelligent, hook, sous-titres et réglage du focus.
- Miniature basée sur une capture réelle du clip.
- Métadonnées locales avec Ollama/Qwen facultatif et fallback sans IA.
- Contrôle qualité post-export et revue humaine.
- Prévisualisation, téléchargement, miniature et copie des métadonnées disponibles après validation.

Le pipeline reste local-first. Les médias, modèles, bases de données, réglages et exports ne sont pas envoyés vers un service cloud.

## Structure

- `app/` : source applicative, tests, installateur et package.
- `docs/` : documentation canonique du projet. Le package de release l'embarque depuis ce dossier.
- `tools/` : vérificateurs de cohérence et d'intégrité de release.
- `archive/releases/v0.7.8/` : archive historique de provenance, conservée en lecture seule.

Les dossiers `Best Of` et l'ancien flux d'URL par fichier texte ont été retirés : ils n'étaient reliés à aucun moteur de production.

## Installation et mise à jour

Pour une première installation, extraire l'archive puis lancer `app/INSTALL.bat`. Pour une installation existante, utiliser **Paramètres > Mises à jour**.

La mise à jour préserve les données locales. Ne jamais remplacer manuellement `config.yaml`.

## Développement et vérification

Dans PowerShell :

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
    Set-Location app
    py -3.11 -m pytest -q
    node --check studio/web/static/app.js
}
finally {
    if ($createdConfig) { Remove-Item config.yaml -Force }
    Set-Location ..
}

py -3.11 app/installer/build_release_package.py --version 0.8.1 --output-dir app/dist
py -3.11 tools/verify_release_package.py --package app/dist/GTA-Ranked-Studio-v0.8.1.zip --checksum app/dist/SHA256SUMS.txt --version 0.8.1
```

Les dépendances utilisateur sont limitées au runtime. Pytest, HTTPX2, Ruff et pip-audit restent dans les environnements de développement et CI.

## Validation et publication

Chaque PR passe la suite Linux et Windows. Le workflow de release reconstruit le ZIP depuis `app/`, y injecte la documentation canonique, vérifie les exclusions de données locales et valide le SHA-256. La publication stable nécessite la version exacte dans `.release-approval`.
