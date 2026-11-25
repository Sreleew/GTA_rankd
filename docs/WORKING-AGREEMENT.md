# Méthode de travail | GTA Ranked Studio

Ce document définit la méthode de collaboration à appliquer dans chaque conversation. Il complète `docs/CONTINUATION.md`, qui reste le mémo maître technique.

## Objectif

Livrer des changements concrets, testés et traçables sans passer un temps disproportionné en inspection, en appels GitHub ou en vérifications répétées. La qualité technique reste obligatoire, mais l'analyse doit être proportionnée au risque et au périmètre du changement.

## Règles par défaut

1. **Commencer par l'état utile, pas par un audit complet.** Lire le mémo maître, vérifier la branche de travail, le dernier commit pertinent et les workflows récents. Ne pas relire tout l'historique Git ou toute l'application sans raison précise.
2. **Inspecter uniquement le périmètre concerné.** Lire les fichiers, fonctions et tests nécessaires à la tâche. Élargir l'inspection seulement lorsqu'un lien technique ou une régression potentielle le justifie.
3. **Passer rapidement à une modification concrète.** Dès que le diagnostic est suffisamment étayé, modifier le code et ajouter ou ajuster les tests dans le même lot. Ne pas multiplier les phases d'analyse qui répètent une information déjà connue.
4. **Regrouper les changements liés dans un commit logique.** Éviter un commit par fichier. Faire les modifications de code, tests et documentation ensemble quand elles appartiennent au même livrable. Ne pas déclencher une CI complète à chaque petit ajustement.
5. **Tester en fonction du risque.** Pendant le travail, lancer les tests ciblés et les contrôles de syntaxe pertinents. À la fin d'un lot fonctionnel, exécuter la suite complète Linux et Windows lorsque le changement touche le comportement, le packaging ou l'installation. Pour une modification documentaire, lancer l'audit complet seulement si le mémo ou les documents intégrés au paquet changent.
6. **Ne pas attendre la CI pour avancer sans raison.** La CI complète valide un lot cohérent. Les vérifications ciblées peuvent être utilisées avant cela. Ne pas relancer la même suite si aucun code, test, configuration ou workflow pertinent n'a changé.
7. **Faire des mises à jour visibles et utiles.** Pendant une tâche longue, envoyer une mise à jour dès qu'un résultat concret est obtenu ou qu'un blocage apparaît. Ne pas envoyer uniquement des messages de progression vagues. Ne pas laisser l'utilisateur sans information pendant une longue série d'opérations.
8. **Terminer par un bilan exploitable.** Indiquer les fichiers changés, le commit et la branche, les tests réellement exécutés avec leurs résultats, les éléments non testés et la prochaine action précise. Ne jamais présenter un contrôle prévu comme un contrôle réussi.
9. **Préserver les données et limiter le risque.** Ne jamais toucher à `main`, fusionner, publier une Release ou supprimer des données sans instruction explicite. Ne jamais inclure les configurations locales, secrets, bases, médias, exports ou modèles dans Git ou dans les paquets de mise à jour.
10. **Ne pas demander à nouveau les fichiers déjà accessibles.** Utiliser le dépôt GitHub lorsque l'accès est disponible. Ne pas demander un ZIP ou une archive si la source de travail est déjà accessible directement.

## Politique de vérification

- **Lecture seule :** vérifier le fichier ciblé et le contexte direct.
- **Changement documentaire isolé :** modifier en lot, vérifier les liens et exécuter le contrôle de mémoire si le mémo change.
- **Changement de code ciblé :** tests du module concerné, vérification syntaxique et revue des régressions associées.
- **Changement transversal ou de pipeline :** suite complète Linux, validation Windows et inspection du paquet.
- **Changement d'installation ou de rendu matériel :** tests automatisés puis validation manuelle sur Windows et le matériel cible. Un runner CI Windows ne prouve pas que la RX 9060 XT utilise réellement AMF ou Vulkan.

## Format de compte rendu

Chaque lot se termine par un court bilan :

- Livré : ce qui a réellement changé.
- GitHub : branche et commit.
- Tests : commandes ou workflows exécutés et résultats constatés.
- Limites : ce qui n'a pas été validé ou nécessite la machine locale.
- Suite : une seule prochaine action prioritaire.

## Règle de reprise

Au début d'une nouvelle conversation, lire d'abord `docs/CONTINUATION.md`, puis ce document. Vérifier rapidement le HEAD actuel et le dernier état CI, puis reprendre à partir de la prochaine action prioritaire. Ne pas refaire les audits déjà documentés si rien n'a changé depuis.
