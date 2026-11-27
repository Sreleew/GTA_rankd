# Développement local

Ce guide décrit le workflow de développement Windows pour GTA Ranked Studio. Le dépôt GitHub reste la source de vérité ; l'environnement local est un accélérateur, pas une source de code indépendante.

## Installation unique

Depuis la racine du dépôt, avec Python 3.11 installé :

    .\scripts\dev-setup.ps1

Le script crée .venv une seule fois, installe le projet en mode éditable (app[dev]) et vérifie les dépendances. Le dossier .venv est persistant et ne doit pas être supprimé ou recréé entre les sessions normales.

Après une modification de dépendances (app/pyproject.toml ou app/requirements.txt), relancer .\scripts\dev-setup.ps1. Pour une modification de code Python ou de l'interface, l'installation n'a pas besoin d'être répétée.

## Tests rapides par domaine

Lancer uniquement le périmètre concerné pendant le développement :

    .\scripts\test-quick.ps1 -Target shorts
    .\scripts\test-quick.ps1 -Target twitch
    .\scripts\test-quick.ps1 -Target bestof
    .\scripts\test-quick.ps1 -Target web

- shorts : éditeur, rendu, transcription et attribution des voix.
- twitch : endpoints Twitch et téléchargement par plages.
- bestof : moteur de rendu et API Daily Best Of.
- web : suite API/interface complète.

Le script crée temporairement app/config.yaml depuis le modèle uniquement si aucun fichier personnel n'existe, puis supprime uniquement le fichier qu'il a créé. Une configuration existante n'est jamais écrasée.

## Suite complète

Réserver la suite complète aux changements transversaux, aux changements de packaging/installation et aux préparations de release :

    .\scripts\test-full.ps1
    .\scripts\test-full.ps1 -SecurityAudit

Elle exécute compilation Python, suite pytest, contrôle JavaScript si Node.js est installé, Ruff et, avec -SecurityAudit, pip-audit.

## Règles pour ne pas perdre de temps

1. Ne pas recréer .venv à chaque session.
2. Ne pas réinstaller les dépendances si les fichiers de dépendances n'ont pas changé.
3. Pendant un lot, lancer les tests du domaine touché, puis élargir seulement si une dépendance directe ou une régression le justifie.
4. Ne pas relancer un test identique après une modification documentaire uniquement.
5. Garder la CI Linux et Windows comme filet de sécurité avant fusion. Les validations matérielles FFmpeg/AMF/Vulkan restent distinctes et ne sont nécessaires que lorsqu'un changement touche réellement le rendu ou le matériel.
6. Ne jamais committer .venv, app/config.yaml, vidéos, exports, modèles, bases de données ou secrets.

## Limites

Ces scripts sont des raccourcis de développement, pas un remplacement de la CI. Ils ne simulent pas le GPU AMD et ne prouvent pas qu'un rendu réel Twitch est visuellement correct. Avant une release de rendu, faire une validation manuelle sur un vrai clip Windows/AMD.
