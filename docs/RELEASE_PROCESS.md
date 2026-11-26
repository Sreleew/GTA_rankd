# Processus de validation et de publication

## Principe

La source de développement et de publication est `app/`. Les workflows ne décompressent plus l'archive v0.7.8 et ne rejouent plus de correctifs historiques. La documentation canonique reste à la racine dans `docs/` et le constructeur l'injecte directement dans le package : aucune copie applicative `app/docs/` n'est requise.

Le bouton de mise à jour de GTA Ranked Studio consulte les Releases publiques du dépôt GitHub. Une branche ou un artifact Actions ne constitue pas une mise à jour disponible.

## Flux obligatoire

1. Développer directement sous `app/` sur une branche de travail.
2. Ajouter ou ajuster les tests sous `app/tests/`.
3. Synchroniser le numéro de version racine `VERSION.txt` avec `app/VERSION.txt`, et les notes racine avec `app/NOTES-vX.Y.Z.txt`.
4. Ouvrir une PR vers `main`. L'audit Linux et la validation Windows exécutent Ruff, pip-audit, compileall, les tests directement depuis `app/` et le contrôle JavaScript.
5. Examiner les résultats, les fichiers du package et les exclusions de données locales.
6. Fusionner après validation Linux/Windows lorsque l'utilisateur a demandé le résultat complet, puis créer la Release stable approuvée.
7. Pour autoriser une nouvelle Release stable, créer ou mettre à jour `.release-approval` sur `main` avec exactement la version présente dans les deux `VERSION.txt`. Ce commit constitue l'approbation explicite de publication.
8. Le workflow de Release vérifie la version, le tag, les manifestes, le mémo, exécute la suite complète, construit le ZIP avec `app/installer/build_release_package.py`, puis le valide avec `tools/verify_release_package.py` (contenu requis, chemins sûrs, exclusions et SHA-256).
9. GitHub publie le ZIP Windows et `SHA256SUMS.txt`. L'application peut détecter cette version via son bouton de mise à jour.

La voie `workflow_dispatch` reste disponible pour préparer une Release brouillon : elle exige une version et une confirmation cochée.

## Garde-fous

- Seul un changement de `.release-approval` sur `main` déclenche une publication stable.
- La version approuvée doit correspondre à `VERSION.txt` et `app/VERSION.txt`.
- Un tag existant bloque le workflow : une Release publiée n'est jamais écrasée.
- Le workflow manuel crée uniquement une brouillon.
- Linux et Windows testent la même source directe `app/`.
- Le ZIP exclut la configuration personnelle, les secrets, bases, médias, exports, logs et modèles locaux.
- L'installateur doit préserver les réglages, projets, bases, exports et modèles existants.
- Les scripts PowerShell doivent conserver le BOM UTF-8 et les CRLF ; cette règle est versionnée dans `.gitattributes` et contrôlée par les tests.
- L'archive `archive/releases/v0.7.8/` est conservée uniquement comme provenance historique de la Release v0.7.8.

## État au 26 novembre 2026

- Release stable actuelle : [v0.8.2](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.2).
- PR #10 maintenance, PR #11 coupes naturelles et PR #12 profil de durée de production sont fusionnées dans `main`.
- CI PR #12 : Linux 155 tests réussis + 1 ignoré ; Windows 156 tests réussis.
- CI `main` après fusion : Linux et Windows validés avant préparation de la Release v0.8.2.
- Profil de production : passages VOD de 60, 90, 120, 150 et 165 secondes ; clips Twitch plus courts préservés sans rallongement artificiel.
- La migration des anciennes valeurs de configuration v0.8.1 s'effectue en mémoire uniquement et préserve les valeurs personnalisées.
- Workflow de publication v0.8.2 réussi : https://github.com/Sreleew/GTA_rankd/actions/runs/45850248905.
- Assets publiés : `GTA-Ranked-Studio-v0.8.2.zip` et `SHA256SUMS.txt`.
- La validation physique de la RX 9060 XT pour AMF/Vulkan reste à faire.

## Protection de main

Les changements de code doivent passer par une PR et les contrôles Linux/Windows. Ne pas supposer que la protection GitHub de la branche est activée sans la vérifier dans les paramètres du dépôt.
