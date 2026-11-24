Dépôt de distribution de GTA Ranked Studio.

Version publiée : 0.3.6.

Le dossier `source/` contient un snapshot source assaini et les correctifs reproductibles v0.3.5 et v0.3.6 appliqués par GitHub Actions avant les tests et la construction des paquets Windows. Aucun environnement virtuel, média personnel, base de données, configuration locale ou modèle IA n'est inclus.

La v0.3.5 corrige les timestamps Whisper DTW en désactivant Flash Attention avec `-nfa`. La v0.3.6 fiabilise le programme de mise à jour Windows : journal créé avant l'exécution PowerShell, capture de stdout/stderr, détection d'un arrêt immédiat et meilleure compatibilité Windows PowerShell 5.1.

Le client Windows lit les Releases publiques de `Sreleew/GTA_rankd` sans token GitHub. Les modifications du snapshot ou des correctifs lancent les tests, construisent le paquet de mise à jour et publient une Release stable.

Ne jamais publier de vidéos personnelles, `config.yaml`, bases de données, modèles ou secrets.
