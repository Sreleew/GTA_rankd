# GTA Ranked Studio

Application Windows locale pour transformer des clips et VOD GTA en Shorts verticaux prêts à relire et publier.

**Dernière version stable : v0.8.7.** [Consulter la Release stable v0.8.7](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.7).

## Fonctionnalités

- Import de vidéos locales et de clips/VOD Twitch accessibles via yt-dlp.
- Analyse audio et transcription Whisper locale pour classer les moments forts.
- Diversité des sélections : évite de proposer plusieurs passages éloignés qui racontent presque la même chose.
- Indexation temporelle des fenêtres audio et des mots Whisper pour accélérer le classement des longues VOD.
- Saisie des plages d'analyse en secondes ou au format lisible `HH:MM:SS`.
- Analyse d'une longue VOD Twitch par lots de tranches indépendantes de 30, 45, 60, 90, 120 ou 180 minutes, jusqu'à 48 tranches par lot.
- Carte de lot avec progression agrégée et shortlist consolidée, triée et dédoublonnée à l'échelle de la VOD. Chaque candidat reste relié à sa tranche source pour créer le Short.
- Les scores audio étant normalisés par tranche, le classement consolidé reste indicatif et doit être relu avant export.
- Score d'accroche distinct sur les cinq premières secondes et score de payoff basé sur le pic audio et les réactions proches.
- Shorts 1080 × 1920 de 60 à 165 secondes, avec coupes naturelles qui préservent les réactions retardées, cadrage intelligent, hook, sous-titres et réglage du focus.
- Habillage éditorial Vice City Dispatch, avec repères visuels et signature GTA Ranked.
- Miniature basée sur une capture réelle du clip.
- Métadonnées locales avec Ollama/Qwen facultatif et fallback sans IA.
- Contrôle qualité post-export et revue humaine.

Le pipeline reste local-first. Les médias, modèles, bases de données, réglages et exports ne sont pas envoyés vers un service cloud.

## Structure

- `app/` : source applicative, tests, installateur et package.
- `docs/` : documentation canonique du projet. Le package de release l'embarque depuis ce dossier.
- `tools/` : vérificateurs de cohérence et d'intégrité de release.
- `archive/releases/v0.7.8/` : archive historique de provenance, conservée en lecture seule.

Les dossiers `Best Of` et l'ancien flux d'URL par fichier texte ont été retirés : ils n'étaient reliés à aucun moteur de production.

## Installation et mise à jour

Pour une première installation, extraire l'archive puis lancer `app/INSTALL.bat`. Pour une installation existante en v0.8.6, utiliser **Paramètres > Mises à jour** pour passer à la v0.8.7.

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

py -3.11 app/installer/build_release_package.py --version 0.8.7 --output-dir app/dist
py -3.11 tools/verify_release_package.py --package app/dist/GTA-Ranked-Studio-v0.8.7.zip --checksum app/dist/SHA256SUMS.txt --version 0.8.7
```

Les dépendances utilisateur sont limitées au runtime. Pytest, HTTPX2, Ruff et pip-audit restent dans les environnements de développement et CI.

## Validation et publication

Chaque PR passe les suites Linux et Windows. Le workflow de release reconstruit le ZIP depuis `app/`, y injecte la documentation canonique, vérifie les exclusions de données locales et valide le SHA-256. La publication stable nécessite la version exacte dans `.release-approval`.
