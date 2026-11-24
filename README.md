Dépôt de distribution de GTA Ranked Studio.

Version source préparée : 0.4.0.

La source complète v0.4.0 est fournie dans `source/GTA-Ranked-Studio-source-v0.4.0.tar.xz`. GitHub Actions vérifie son SHA-256, exécute la suite de tests, construit le paquet de mise à jour Windows et publie une Release stable.

v0.4.0 ajoute la fonctionnalité **Moments forts** : analyse de vidéos locales et de VOD/clips Twitch, découpage facultatif par plage horaire, classement heuristique de passages à partir de l'énergie audio et de la transcription Whisper, puis création d'un Short à partir du passage sélectionné via le pipeline habituel.

La détection est audio + texte dans cette version. Elle ne réalise pas encore d'analyse visuelle du gameplay. Les médias, modèles IA, `config.yaml`, bases de données, rendus et environnements locaux ne sont pas inclus dans le paquet de mise à jour.

Le client Windows lit les Releases publiques de `Sreleew/GTA_rankd` sans token GitHub.
