# Méthode de travail | GTA Ranked Studio

Ce document définit la méthode de collaboration à appliquer dans chaque conversation. Il complète `docs/CONTINUATION.md`, qui reste le mémo maître technique.

## Objectif

Livrer des changements concrets, propres et testés sans passer un temps disproportionné à explorer les anciennes versions, à relire des historiques ou à répéter les mêmes contrôles.

## Source de vérité

- Le code de l'application vit directement dans `app/`. C'est le seul dossier à modifier pour les fonctionnalités du produit.
- `app/studio/` contient le backend et l'interface.
- `app/installer/` contient les scripts d'installation, de mise à jour et de packaging.
- `app/tests/` contient les tests.
- `docs/` à la racine contient la mémoire du projet et le processus de travail. C'est la source documentaire canonique, injectée directement dans les ZIP par le constructeur.
- `archive/releases/v0.7.8/` est une archive historique immuable. Ne jamais développer à partir de cette archive.
- Les anciennes chaînes de correctifs ne font plus partie du processus de développement.

## Règles par défaut

1. **Commencer par l'état utile.** Lire le mémo, vérifier la branche, le dernier commit pertinent et les derniers contrôles CI. Ne pas refaire un audit complet si rien de pertinent n'a changé.
2. **Inspecter le bon périmètre.** Lire les quelques fichiers, fonctions et tests nécessaires. Élargir uniquement si une dépendance ou une régression le justifie.
3. **Agir rapidement.** Dès que le diagnostic est étayé, modifier le code et ajouter les tests dans le même lot.
4. **Regrouper.** Un commit logique pour un livrable cohérent, pas un commit par fichier.
5. **Tester proportionnellement.** Tests ciblés et syntaxe pendant le développement. Suite complète Linux et Windows pour les changements de comportement, de packaging, d'installation ou de pipeline.
6. **Éviter les vérifications redondantes.** Ne pas relancer la même suite si aucun code, test, configuration ou workflow pertinent n'a changé.
7. **Préserver la qualité.** Un résultat rapide n'est pas un résultat bâclé. Vérifier les erreurs, les régressions, la compatibilité Windows et l'absence d'effets sur les données locales.
8. **Communiquer avec des résultats.** Pendant une tâche longue, donner une mise à jour lorsqu'un résultat concret ou un blocage est identifié.
9. **Terminer par un bilan exploitable.** Indiquer les fichiers modifiés, branche et commit, tests réellement exécutés, limites et prochaine action.
10. **Préserver les données et les versions.** Ne jamais publier `config.yaml`, secrets, bases, vidéos, rendus, modèles ou exports. Ne jamais modifier un tag publié.
11. **Livrer jusqu'à publication.** Quand l'utilisateur demande une modification et souhaite un résultat utilisable, aller jusqu'à l'intégration dans `main`, la création de la Release stable et la mise à disposition du package. Ne pas s'arrêter à un commit, une branche ou une PR. Si une validation échoue ou si un blocage technique empêche la publication, corriger le problème ou expliquer précisément le blocage.
12. **Découper les gros chantiers.** Organiser les tâches longues en lots autonomes avec des validations et points de reprise. Éviter les réponses ou modifications monolithiques susceptibles d'expirer.
13. **Mettre la mémoire à jour à chaque lot.** Après chaque lot de modifications, mettre à jour `docs/CONTINUATION.md` avant de terminer : remarques et décisions utilisateur, méthode de travail, changements réellement livrés, branche/PR/commit/Release, tests et limites. Rester concis, factuel et supprimer ou remplacer les informations devenues obsolètes. C'est une étape obligatoire, pas une tâche documentaire facultative.
14. **Respecter les priorités produit en cours.** Le parcours « Créer un Short » depuis un clip Twitch est prioritaire, suivi du Daily Best Of construit depuis les clips validés. La fonctionnalité « Moments forts » est explicitement en pause : ne pas investir dans son évolution tant que les deux parcours prioritaires ne sont pas suffisamment fiables. Ne pas la supprimer ni casser ses dépendances existantes. La progression Twitch enrichie (pourcentage, taille, débit et ETA) est déjà intégrée : ne pas refaire ce chantier sans défaut concret. La direction artistique doit être premium, reconnaissable et propre au projet : hook immédiat (1 à 2 secondes), typographie cinétique, compositions verticales, sound design et transitions au service de la rétention. La source capture déjà l'écran entier, webcam comprise : conserver ce cadrage et ne pas développer d'extraction, d'overlay ou de sélection webcam_zone dédiée.

15. **Éviter les micro-lots et les tests redondants.** Regrouper les changements qui servent le même parcours en un livrable cohérent. Pendant le développement, exécuter uniquement les tests ciblés du domaine touché ; élargir le périmètre si un impact indirect est identifié. Ne pas relancer les mêmes tests après une modification qui ne touche ni le code ni la configuration testés. Garder une validation CI Linux/Windows avant fusion des lots de comportement, mais ne pas créer une PR séparée uniquement pour faire tourner des tests ou déplacer de la documentation. Utiliser les scripts locaux documentés dans docs/DEVELOPMENT.md et conserver l'environnement .venv entre les sessions.

## Flux de développement

1. Créer ou utiliser une branche de travail à partir de `main`.
2. Modifier directement `app/`.
3. Ajouter ou mettre à jour les tests sous `app/tests/`.
4. Synchroniser le numéro de version racine `VERSION.txt` avec `app/VERSION.txt`, et les notes de release racine avec celles de `app/` lorsqu'une nouvelle version est préparée.
5. Exécuter les tests ciblés.
6. Ouvrir une PR vers `main`.
7. Vérifier l'audit Linux et la validation Windows sur cette PR.
8. Vérifier les contrôles Linux et Windows, puis fusionner et publier la Release stable lorsque l'utilisateur a demandé le résultat complet. Créer `.release-approval` sur `main` avec la version synchronisée afin de déclencher la publication.

## Politique de vérification

- **Lecture seule :** lire le fichier ciblé et son contexte immédiat.
- **Changement de code ciblé :** tests du module, syntaxe Python/JavaScript et tests de régression associés.
- **Changement transversal :** suite complète Linux, validation Windows, Ruff, pip-audit, compilation Python, contrôle JavaScript et vérification du ZIP.
- **Changement d'installation ou de rendu matériel :** tests automatisés puis validation manuelle sur Windows et le matériel cible. Un runner CI Windows ne prouve pas que la RX 9060 XT utilise réellement AMF ou Vulkan.
- **Documentation seule :** vérifier le mémo et les liens, sans audit complet si les documents du package ne sont pas modifiés.

## Format de compte rendu

Chaque lot se termine par un court bilan :

- **Mémo :** `docs/CONTINUATION.md` mis à jour à chaque lot, avec un journal concis des décisions et changements.
- **Livré :** ce qui a réellement changé.
- **GitHub :** branche et commit.
- **Tests :** commandes ou workflows exécutés et résultats constatés.
- **Limites :** ce qui n'a pas été validé.
- **Suite :** une seule prochaine action prioritaire.

## Reprise

Au début d'une nouvelle conversation, lire d'abord `docs/CONTINUATION.md`, puis ce document. Vérifier rapidement le HEAD et l'état CI, puis reprendre à partir de la prochaine action prioritaire. Ne pas demander à nouveau les fichiers déjà accessibles dans GitHub.
