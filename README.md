Dépôt de distribution de GTA Ranked Studio.

Dernière version stable : **0.4.1**.

La version 0.4.0 a introduit la fonctionnalité **Moments forts** : analyse de vidéos locales et de VOD/clips Twitch, découpage facultatif par plage horaire, classement heuristique de passages à partir de l'énergie audio et de la transcription Whisper, puis création d'un Short à partir du passage sélectionné via le pipeline habituel.

La version **0.4.1** corrige l'analyse des VOD longues : après téléchargement, l'inspection du fichier par FFprobe utilise désormais un délai calculé selon la taille du média, avec un minimum de 5 minutes et un plafond de 30 minutes. L'interface indique l'étape d'inspection avant l'analyse audio. La transcription Whisper reste découpée en blocs de 5 minutes.

La détection des moments forts reste audio + texte. Elle ne réalise pas encore d'analyse visuelle du gameplay. Les médias, modèles IA, `config.yaml`, bases de données, rendus et environnements locaux ne sont pas inclus dans les paquets de mise à jour.

Le paquet Windows v0.4.1 est publié dans les [Releases GitHub](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.4.1). Le client Windows lit les Releases publiques de `Sreleew/GTA_rankd` sans token GitHub.
