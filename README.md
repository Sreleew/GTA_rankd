Dépôt de distribution de GTA Ranked Studio.

Version source préparée : 0.3.4.

Le dossier `source/` contient un snapshot source assaini utilisé par GitHub Actions pour construire les paquets de mise à jour Windows. Le snapshot n'inclut aucun environnement virtuel, média personnel, base de données, configuration locale ou modèle IA.

Le client Windows lit les Releases publiques de `Sreleew/GTA_rankd` sans token GitHub. Pour publier une version, synchroniser le snapshot et lancer Actions → Build and publish GTA Ranked Studio en indiquant le numéro de `VERSION.txt`.

Ne jamais publier de vidéos personnelles, `config.yaml`, bases de données, modèles ou secrets.
