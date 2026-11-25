# Processus de validation et de publication

## Principe

Un candidat de CI n'est pas une Release. Le bouton de mise à jour de GTA Ranked Studio recherche les GitHub Releases publiques de ce dépôt : une branche, un commit ou un artifact Actions ne suffit donc pas à rendre une version disponible dans l'application.

## Flux obligatoire

1. Développer sur une branche de travail et actualiser le mémo, les notes, le README et le changelog.
2. Ouvrir une PR vers `main`. Les workflows Linux et Windows s'exécutent sur la révision de la PR.
3. Vérifier l'audit Linux : source canonique, manifeste, fichiers, tests Python, JavaScript et paquet Windows.
4. Vérifier le workflow Windows : extraction sécurisée, tests Python, PowerShell, JavaScript et ZIP de mise à jour.
5. Valider manuellement sur le PC cible les changements qui touchent directement l'installation, l'encodage AMF, Whisper Vulkan ou Ollama/Qwen. Pour les autres changements, consigner explicitement ce qui reste à vérifier sur le matériel réel.
6. Fusionner volontairement la PR après examen des deux validations et des données locales préservées.
7. Pour publier une version stable, créer ou mettre à jour `.release-approval` sur `main` avec exactement le numéro de version approuvé, par exemple `0.7.8`. **Ce commit est l'autorisation explicite de publication publique.**
8. Le workflow `Build and prepare GTA Ranked Studio release` vérifie que le marqueur correspond à `VERSION.txt`, que le tag n'existe pas, que l'archive canonique et chaque fichier correspondent au manifeste, exécute les tests Linux et construit puis vérifie le ZIP Windows.
9. Pour un commit `.release-approval`, GitHub crée et publie la Release stable directement, avec le ZIP et `SHA256SUMS.txt`. L'application peut alors détecter cette version via son bouton de mise à jour.

La voie `workflow_dispatch` reste disponible pour préparer une Release brouillon : elle exige la version et une confirmation cochée, puis nécessite une publication manuelle depuis GitHub.

## Garde-fous

- Aucun push ordinaire ne déclenche de publication : seul un changement de `.release-approval` sur `main` le fait.
- La version du marqueur doit correspondre exactement à `VERSION.txt`.
- Le tag déjà existant bloque le workflow, afin de ne jamais écraser une version publiée.
- La voie manuelle ne publie jamais directement : elle crée une brouillon.
- Le manifeste, le checksum et chaque fichier de l'archive canonique sont vérifiés avant extraction.
- Le ZIP est vérifié et exclut `config.yaml`, les secrets, bases, médias, exports, journaux et modèles locaux.
- L'installateur doit préserver les réglages, projets, bases, exports et modèles existants.
- Ne jamais utiliser les fragments v0.8.0 actuels : `part003` et `part004` sont dupliqués et l'archive reconstruite est invalide.

## État v0.7.8 au 25 novembre 2026

- Le candidat v0.7.8 et sa source canonique ont été intégrés dans `main` via la PR #2.
- Dernière Release stable publique au début de la préparation : v0.7.7.
- Audit Linux : 138 tests réussis, 1 test PowerShell ignoré sous Linux.
- Validation Windows CI : 139 tests réussis, aucun ignoré ; tests PowerShell et ZIP Windows validés.
- La RX 9060 XT physique n'a pas encore été utilisée pour valider AMF/Vulkan. Le code v0.7.8 n'a pas été modifié sur ces moteurs ; consigner cette limite et contrôler le premier cycle réel après mise à jour.
- Le workflow de publication contient désormais deux voies : marqueur explicite pour publier une stable, lancement manuel pour produire une brouillon.

## Protection de `main`

La protection de branche reste un réglage GitHub indépendant. Vérifier dans les paramètres du dépôt que les PR et les contrôles obligatoires sont configurés ; ne pas supposer que `main` est protégée si l'interface GitHub ne le confirme pas.
