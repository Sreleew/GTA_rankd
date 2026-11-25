# Processus de validation et de publication

## Principe

Une version n'est publiable que lorsque sa source canonique, les tests Linux, les tests Windows et le contrôle matériel prévu ont été validés. Un artifact GitHub Actions n'est pas une Release. Un candidat CI n'est pas une version stable.

## Flux obligatoire

1. Développer sur une branche de travail, jamais directement sur `main`.
2. Mettre à jour le mémo, les notes, le README et le changelog lorsque le comportement produit change.
3. Lancer le workflow `Audit GTA Ranked Studio source`. Il reconstruit et teste la source, puis met à jour l'archive canonique et ses fichiers de contrôle.
4. Laisser le workflow `Windows runtime validation` tester l'archive canonique sur `windows-latest`, notamment le parseur Windows PowerShell 5.1, les tests Python, le JavaScript et le paquet de mise à jour.
5. Valider manuellement le logiciel sur le PC cible : cycle complet d'un Short, FFmpeg AMF, Whisper Vulkan, Ollama/Qwen, persistance et mise à jour sans perte de données. Utiliser `docs/WINDOWS-HARDWARE-VALIDATION.md`.
6. Examiner la comparaison Git entre la branche de travail et `main`. Résoudre explicitement les changements de workflows avant d'ouvrir ou de fusionner une PR.
7. Fusionner volontairement dans `main` seulement après validation et décision explicite.
8. Depuis `main`, lancer manuellement `Build and prepare GTA Ranked Studio release`, saisir la version canonique et cocher la confirmation. Le workflow refuse toute exécution depuis une autre branche, vérifie l'intégrité de chaque fichier source, rejoue les tests et vérifie le ZIP.
9. Le workflow crée une **Release brouillon**, pas une publication publique. Vérifier les notes, le ZIP et `SHA256SUMS.txt`, puis publier la brouillon manuellement depuis GitHub.

## Garde-fous

- Aucun déclencheur `push` ne publie de Release.
- Une confirmation manuelle est obligatoire.
- Le workflow de publication ne fonctionne que depuis `main`.
- Un tag déjà existant bloque la préparation afin d'éviter l'écrasement d'une version.
- Le manifeste, le checksum et chaque fichier de l'archive canonique sont vérifiés avant extraction.
- Le paquet doit inclure le mémo, le vérificateur et l'historique des mises à jour.
- Les configurations, secrets, bases, médias, exports, journaux, modèles locaux et environnements virtuels ne doivent jamais entrer dans le paquet.
- Ne jamais utiliser les fragments v0.8.0 actuels : `part003` et `part004` sont dupliqués et l'archive reconstruite est invalide.

## Protection de `main`

Le workflow de publication est maintenant verrouillé, mais les règles de protection de branche sont un réglage GitHub indépendant. Elles n'ont pas été modifiées pendant ce sprint. Avant la fusion de la PR, configurer dans les paramètres du dépôt :

- exiger une Pull Request avant toute fusion sur `main` ;
- exiger les contrôles Linux et Windows comme checks obligatoires ;
- interdire les force-push et la suppression de `main` ;
- exiger une conversation de revue résolue.

Ne pas considérer la branche comme protégée tant que ces règles ne sont pas visibles et activées dans GitHub.

## État actuel au 25 novembre 2026

- Base de travail : v0.7.8 canonique sur `feature/v0.7.8-shorts-retention`.
- La dernière Release publique stable est v0.7.7. Le `VERSION.txt` du dépôt `main` indique encore v0.5.1, car l'ancien workflow reconstruisait la v0.7.7 depuis les correctifs historiques. Il s'agit d'une métadonnée obsolète à corriger lors de l'intégration.
- Les deux commits exclusifs de `main` relevés lors du compare Git concernent uniquement l'ancienne évolution du workflow d'audit. Le workflow de la branche de travail est plus complet, mais le diff doit être vérifié dans une PR. Ne pas fusionner aveuglément.
- La validation Linux v0.7.8 a réussi avec 128 tests réussis et 1 ignoré.
- Le workflow Windows vient d'être ajouté. Son premier résultat doit être examiné avant de considérer la validation Windows CI comme acquise.
- Aucune Release stable n'a été publiée.
