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

## État au 27 novembre 2026

- Dernière Release stable publiée : [v0.9.1](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.9.1), avec le ZIP Windows et `SHA256SUMS.txt` (publication vérifiée le 27 novembre 2026).
- PR #41 fusionnée : constructeur de sélection Daily Best Of, avec CI Linux et Windows réussies.
- PR #42 fusionnée : relance des jobs Twitch en erreur depuis l'URL d'origine, conservation des options et réutilisation du média local.
- CI PR #42 : Linux [46012357301](https://github.com/Sreleew/GTA_rankd/actions/runs/46012357301) et Windows [46012357283](https://github.com/Sreleew/GTA_rankd/actions/runs/46012357283) réussies.
- CI post-fusion sur main : Linux [46012922370](https://github.com/Sreleew/GTA_rankd/actions/runs/46012922370) et Windows [46012922379](https://github.com/Sreleew/GTA_rankd/actions/runs/46012922379) réussies.
- CI PR #43 de préparation v0.8.8 : Linux [46013472471](https://github.com/Sreleew/GTA_rankd/actions/runs/46013472471) et Windows [46013472448](https://github.com/Sreleew/GTA_rankd/actions/runs/46013472448) réussies.
- PR #43 : préparation et synchronisation de la release v0.8.8, fusionnée dans `main` après CI Linux/Windows réussies.
- Workflow officiel de publication v0.8.8 : [46014440309](https://github.com/Sreleew/GTA_rankd/actions/runs/46014440309), terminé avec succès.
- ZIP v0.8.8 : 207 327 octets ; SHA-256 `c6155b1ce323edf6fb6088ceb386ae38223aaa4c0c875b95f245a7bbb76e8d1b`.
- **Après la publication v0.8.9 :** PR #58 a ajouté le rendu asynchrone Daily Best Of 16:9 dans `main` (merge `f1f0670fa2ce1a33ce679bfc666823ce1702de8c`). Cette évolution n'est pas incluse dans l'archive v0.8.9.
- La validation physique de la RX 9060 XT pour AMF/Vulkan reste à faire.
## Protection de main

Les changements de code doivent passer par une PR et les contrôles Linux/Windows. Ne pas supposer que la protection GitHub de la branche est activée sans la vérifier dans les paramètres du dépôt.


## Publication de la v0.8.9, 27 novembre 2026

- PR #45 fusionnée : correctif du faux « Failed to fetch » pendant le redémarrage du serveur lors d'une mise à jour.
- CI Linux [46015871458](https://github.com/Sreleew/GTA_rankd/actions/runs/46015871458) et Windows [46015871444](https://github.com/Sreleew/GTA_rankd/actions/runs/46015871444) réussies.
- La version cible 0.8.9 ajoute la confirmation automatique de la version après redémarrage et masque les erreurs réseau transitoires attendues pendant l'installation.
- Le test de mise à jour depuis l'application sur un PC Windows réel reste à effectuer après publication.


### Vérification des assets publiés

- Release stable GitHub vérifiée : [GTA Ranked Studio v0.8.9](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.8.9), publiée le 27 novembre 2026.
- ZIP Windows `GTA-Ranked-Studio-v0.8.9.zip` : 209 227 octets ; SHA-256 `949cbbe890c605493cccbb2dd8b30a530f037e33f9c48256ac84ce5a2b0c79c8`.
- Manifeste `SHA256SUMS.txt` : 95 octets ; SHA-256 `b737b1eea388338c966ea35ae29666081fd6435e6ffd218b1c40348ae9713695`.
- Le test réel de mise à jour depuis une installation Windows existante reste à confirmer sur le PC utilisateur.

### Évolutions de main postérieures à v0.8.9

Les PR suivantes sont fusionnées après la création de l'archive v0.8.9. Elles sont présentes dans `main`, mais nécessitent une prochaine Release pour être distribuées dans l'application installable.

- **PR #58** : rendu asynchrone du Daily Best Of en 16:9, merge `f1f0670fa2ce1a33ce679bfc666823ce1702de8c`.
- **PR #60** : import groupé de jusqu'à 10 clips Twitch dans le parcours Short, merge `90504c7c282e9032fb2bc9d90cc03f83f018f4e2`.
- **PR #61** : environnement développeur local persistant et commandes de tests ciblés, merge `a90c85c60a10618b7d465da39bb11ba1439a93de`.
- **PR #62** : suivi persistant des lots Twitch avec progression agrégée, merge `6514b37077cacefd4e9274a0dfa5364ada61871c`.
- La v0.9.1 a été publiée après validation de sa PR dédiée ; elle met à disposition la direction artistique des miniatures demandée par l'utilisateur.


## Publication de la v0.9.1, 27 novembre 2026

- PR #81 : nouvelle direction artistique par défaut pour les miniatures de Short. CI Linux et Windows réussies.
- PR #82 : mise à jour du mémo après fusion de la fonctionnalité. CI Linux et Windows réussies.
- PR #83 : préparation de la v0.9.1, synchronisation des versions et approbation de la release. CI PR Linux [46078299248](https://github.com/Sreleew/GTA_rankd/actions/runs/46078299248) et Windows [46078299263](https://github.com/Sreleew/GTA_rankd/actions/runs/46078299263) réussies.
- Workflow officiel de publication : [46078578681](https://github.com/Sreleew/GTA_rankd/actions/runs/46078578681), terminé avec succès.
- Release stable : [GTA Ranked Studio v0.9.1](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.9.1).
- ZIP Windows `GTA-Ranked-Studio-v0.9.1.zip` : 249 800 octets ; SHA-256 `d798b112838ecccc9877267949035a6a7faaede5c76ab80898aab9b07e311200`.
- Manifeste `SHA256SUMS.txt` : 95 octets ; SHA-256 `a2bc90f701dd022eab65dae71b1005b18b29939b222d5eef6617c78dddbcbfa9`.
- Limite confirmée : la miniature garde la frame source entière. La webcam n'est pas isolée ni déplacée ; sa taille et sa position restent celles de la source.
