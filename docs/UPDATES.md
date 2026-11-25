# GTA Ranked Studio | Mises à jour et publication

## Publication

Le paquet Windows est construit par `installer/build_release_package.py`. Une Release stable doit contenir le ZIP de mise à jour et `SHA256SUMS.txt`. Ne pas confondre un artifact GitHub Actions temporaire avec une Release stable publiée.

Avant chaque version, synchroniser `VERSION.txt`, `NOTES-vX.Y.Z.txt`, `README.md`, `docs/UPDATES.md` et `docs/CONTINUATION.md`. Exécuter `python tools/check_project_memory.py` avant les tests et le packaging. La CI doit bloquer si le mémo n'est pas aligné sur la version.

## Historique

- **0.7.4** : diagnostic réel du backend Whisper Vulkan et de l'allocation du modèle.
- **0.7.5** : corrections du cache JavaScript et du feedback du diagnostic GPU.
- **0.7.6** : vérification explicite du serveur Ollama, de la présence de Qwen et d'une courte inférence locale.
- **0.7.7** : robustesse du bouton Ollama et revalidation du HTML pour éviter les états bloqués par le cache.
- **0.7.8** : les actions Prévisualiser, Télécharger, Miniature, Copier le titre, Copier la description, Copier les hashtags et Copier le post restent accessibles après validation d'un Short.

## Confidentialité et intégrité

- Les médias et données de production restent sur la machine.
- Ne jamais inclure `config.yaml`, médias, bases de données, modèles téléchargés, environnements virtuels, logs, tokens ou secrets dans les snapshots et releases.
- L'updater doit préserver config, projets, base de données et exports utilisateur.
- Distinguer explicitement test CI, test sur Windows réel et publication stable.
