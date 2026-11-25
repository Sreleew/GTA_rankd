# Validation Windows réelle | GTA Ranked Studio v0.7.8

Ce protocole complète les tests GitHub Actions. Un runner Windows hébergé ne possède pas la configuration matérielle cible et ne peut pas valider la RX 9060 XT.

## Préparation sûre

- Utiliser une copie de test distincte de l'installation quotidienne.
- Conserver une sauvegarde de la configuration et des données existantes.
- Ne jamais copier de configuration active, base SQLite, vidéo privée, export, token ou modèle local dans le dépôt GitHub.
- Noter la version de Windows, le pilote AMD, la version FFmpeg et le modèle Whisper installé.

## Checklist fonctionnelle

### Démarrage et configuration
- [ ] L'application démarre sans erreur et ouvre l'interface locale.
- [ ] Les paramètres existants sont chargés sans réinitialisation.
- [ ] Les chemins des dossiers locaux sont corrects.
- [ ] Les logs ne contiennent pas d'erreur bloquante au démarrage.

### Cycle de vie d'un Short
- [ ] Importer un petit clip de test autorisé.
- [ ] Générer un Short et attendre la fin complète du rendu.
- [ ] Vérifier que la vidéo, la miniature, le titre, la description et les hashtags sont présents.
- [ ] Prévisualiser et télécharger le Short avant validation.
- [ ] Valider le Short.
- [ ] Vérifier que Prévisualiser, Télécharger, Miniature et toutes les actions de copie sont toujours disponibles.
- [ ] Fermer puis relancer l'application.
- [ ] Vérifier que le Short validé, ses fichiers et ses métadonnées sont toujours accessibles.
- [ ] Vérifier qu'une seconde validation ne crée pas de doublon dans la bibliothèque.

### Encodage AMD
- [ ] Lancer le diagnostic ou un rendu avec l'encodeur AMD AMF.
- [ ] Vérifier dans le résultat ou les logs que `h264_amf` est réellement sélectionné.
- [ ] Vérifier la résolution 1080 × 1920, la fluidité et la lecture du MP4 final.
- [ ] Comparer le résultat avec le fallback `libx264` si nécessaire.
- [ ] Ne pas modifier le bitrate AMF de référence (12M) sans mesure et comparaison réelles.

### Whisper Vulkan
- [ ] Lancer le diagnostic Whisper.
- [ ] Confirmer que le backend Vulkan est réellement utilisé et que le modèle est chargé sur le GPU.
- [ ] Générer des sous-titres sur un clip avec voix du streamer et voix du jeu.
- [ ] Vérifier les timestamps, la synchronisation et le comportement en cas de voix ambiguës.
- [ ] Vérifier que le fallback CPU fonctionne lorsque Vulkan n'est pas disponible.

### Ollama / Qwen
- [ ] Vérifier que le serveur Ollama local répond.
- [ ] Confirmer la présence du modèle Qwen configuré.
- [ ] Lancer le test d'inférence depuis l'application.
- [ ] Vérifier que le fallback déterministe produit encore des métadonnées si Ollama est arrêté.

### Mise à jour et préservation des données
- [ ] Effectuer ce test uniquement dans une installation de test dédiée.
- [ ] Créer des fichiers marqueurs de test dans les répertoires de données concernés.
- [ ] Conserver un `config.yaml` de test avec des valeurs identifiables.
- [ ] Appliquer le ZIP de mise à jour via le mécanisme prévu.
- [ ] Vérifier que `config.yaml`, les bases, projets, médias, exports, modèles et logs n'ont pas été supprimés ou remplacés.
- [ ] Vérifier que l'application redémarre et que le rollback reste disponible en cas d'échec.

## Critères de validation

La validation matérielle est réussie uniquement si :
- aucun test fonctionnel critique n'échoue ;
- la vidéo exportée est lisible et conforme ;
- AMF et Vulkan sont confirmés par les diagnostics/logs, pas seulement sélectionnés dans les paramètres ;
- les données locales survivent à la fermeture, au redémarrage et au test de mise à jour ;
- les résultats sont reproductibles sur plusieurs clips.

## Rapport de test à conserver localement

Noter : date, version GTA Ranked Studio, Windows, pilote AMD, FFmpeg, encodeur réellement utilisé, backend Whisper, modèle, durée du clip, durée du traitement, résultats, incidents et chemin local du rapport/export.

Ne pas verser de médias privés, de bases, de configuration active ou de logs contenant des secrets dans GitHub.
