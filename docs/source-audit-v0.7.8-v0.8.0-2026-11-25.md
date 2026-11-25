# Audit des sources GTA Ranked Studio : v0.7.8 vs v0.8.0

Date de l'audit : 25 novembre 2026  
Dépôt : [Sreleew/GTA_rankd](https://github.com/Sreleew/GTA_rankd)  
Branche de travail : `feature/v0.7.8-shorts-retention`

## Conclusion

La source reconstruite v0.7.8 peut servir de base technique vérifiée pour la suite. Le snapshot source v0.8.0 actuellement présent dans le dépôt est incomplet ou corrompu : deux segments encodés sont strictement identiques. Il n'est donc pas possible d'effectuer une comparaison fiable du code v0.7.8 vers v0.8.0.

Ne pas fusionner ni considérer le snapshot v0.8.0 comme une source canonique tant que le segment manquant n'a pas été restauré ou que l'archive n'a pas été régénérée.

## v0.7.8 : reconstruction et validation

La source est reconstruite par le workflow GitHub Actions à partir de l'archive de base v0.4.0, puis par application des correctifs cumulatifs jusqu'à v0.7.8.

Résultat du workflow d'audit du 25 novembre 2026 :

- Reconstruction de la source v0.7.8 : réussie.
- Tests Python : **128 réussis, 1 ignoré**.
- Vérification syntaxique de `studio/web/static/app.js` : réussie.
- Construction du paquet Windows v0.7.8 : réussie.
- Upload du candidat : réussi.

Checksum SHA-256 du paquet Windows v0.7.8 :

`358329a8aa7911cc56661033562be1a8914b8ee15e231a47e740bd9a7f522710`

Le correctif v0.7.8 conserve après validation du Short les actions Prévisualiser, Télécharger, Miniature, Copier le titre, Copier la description, Copier les hashtags et Copier le post.

Le paquet est un **candidat validé par CI**, pas une Release GitHub publiée.

Workflow : [audit v0.7.8, run 45645972995](https://github.com/Sreleew/GTA_rankd/actions/runs/45645972995)

## Mise à jour du sprint de stabilisation du 25 novembre 2026

Le workflow Linux le plus récent, [run 45673431003](https://github.com/Sreleew/GTA_rankd/actions/runs/45673431003), a terminé avec succès : reconstruction v0.7.8, 128 tests réussis, 1 ignoré, contrôle JavaScript, génération du snapshot canonique et du ZIP Windows candidat.

Le sprint ajoute maintenant :
- un workflow Windows séparé qui contrôle le SHA-256 de l'archive, chaque fichier du manifeste, lance l'ensemble des tests sur `windows-latest`, vérifie réellement les scripts PowerShell et construit le ZIP Windows ;
- un workflow de release exclusivement manuel, réservé à `main`, qui exige une confirmation et crée une Release brouillon au lieu de publier directement ;
- une procédure de publication et une checklist de validation matérielle pour la RX 9060 XT.

Le premier résultat Windows doit encore être inspecté. Un runner Windows hébergé ne valide pas le matériel AMD local : AMF, Whisper Vulkan et Ollama/Qwen doivent être vérifiés séparément sur le PC cible.

## v0.8.0 : intégrité du snapshot

Le snapshot v0.8.0 est réparti en 17 segments Base64 :

`source/v0.8.0-source.part000.b64` à `source/v0.8.0-source.part016.b64`.

Contrôles effectués :

- 17 segments récupérés.
- 16 contenus de segment uniques.
- Les segments `part003` et `part004` ont exactement le même contenu et le même SHA de blob Git.
- Chaque segment dupliqué contient 8 000 caractères.
- L'assemblage des 17 fragments produit 102 000 octets, mais ne reconstitue pas une archive XZ valide.

La recherche de l'historique Git de `part004` ne montre qu'un seul commit d'ajout. Aucune version précédente de ce fichier n'est disponible dans l'historique consulté.

Fichier suspect : [source/v0.8.0-source.part004.b64](https://github.com/Sreleew/GTA_rankd/blob/main/source/v0.8.0-source.part004.b64)

Empreinte SHA-256 de l'assemblage invalide, utile uniquement pour identifier ce résultat d'audit :

`76cf6c87a094d9c08cd57bee22ccdf56544783f48abcfbf44a26e32e47f705ee`

## Décision technique

1. Utiliser la source reconstruite v0.7.8 comme base technique de travail temporaire.
2. Ne pas intégrer le snapshot v0.8.0 actuel.
3. Restaurer le véritable segment 004 depuis la source d'origine, ou régénérer et publier un snapshot v0.8.0 complet avec checksum.
4. Relancer ensuite une comparaison réelle des fichiers v0.7.8 et v0.8.0 avant toute migration.

## Portée des changements effectués pour cet audit

Seul le workflow `.github/workflows/audit-source.yml` a été enrichi sur la branche de travail afin de détecter les segments dupliqués et de publier un rapport d'intégrité même lorsque le snapshot v0.8.0 est bloqué. Aucun fichier de l'application, aucune configuration utilisateur, aucune base locale et aucun média n'a été modifié.
