Dépôt de distribution de GTA Ranked Studio.

Dernière version stable : **0.5.1**.

La version 0.4.0 a introduit la fonctionnalité **Moments forts** : analyse de vidéos locales et de VOD/clips Twitch, découpage facultatif par plage horaire, classement heuristique de passages à partir de l'énergie audio et de la transcription Whisper, puis création d'un Short à partir du passage sélectionné via le pipeline habituel.

La version **0.4.1** a corrigé le délai d'inspection FFprobe pour les VOD longues.

La version **0.4.2** corrige le découpage des VOD Twitch : le début et la fin renseignés sont maintenant transmis à l'API Python yt-dlp avec `download_ranges`. Le téléchargement porte donc sur la plage sélectionnée au lieu de récupérer la VOD entière. Les horodatages des moments détectés restent référencés à la VOD d'origine.

La détection des moments forts reste audio + texte. Elle ne réalise pas encore d'analyse visuelle du gameplay. Les médias, modèles IA, `config.yaml`, bases de données, rendus et environnements locaux ne sont pas inclus dans les paquets de mise à jour.

Le paquet Windows v0.4.2 est publié dans les [Releases GitHub](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.4.2). Le client Windows lit les Releases publiques de `Sreleew/GTA_rankd` sans token GitHub.


La version **0.5.1** conserve l'image complète de la VOD dans le Short vertical : le gameplay reste centré sans recadrage, une copie floutée remplit l'arrière-plan et le zoom dynamique est désactivé par défaut. La webcam déjà intégrée au stream reste visible dans l'image source, sans extraction séparée.

Le paquet Windows v0.5.1 est publié dans les [Releases GitHub](https://github.com/Sreleew/GTA_rankd/releases/tag/v0.5.1).
