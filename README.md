Dépôt de distribution de GTA Ranked Studio.

Version publiée : 0.3.5.

Le dossier `source/` contient un snapshot source assaini et le correctif reproductible `apply-hotfix-v0.3.5.py` appliqué par GitHub Actions avant les tests et la construction des paquets Windows. Le snapshot et le correctif n'incluent aucun environnement virtuel, média personnel, base de données, configuration locale ou modèle IA.

La version 0.3.5 corrige la synchronisation Whisper DTW : whisper.cpp désactive les timestamps DTW si Flash Attention reste activé. L'application transmet désormais `-nfa` en même temps que `-dtw` et `-ojf`.

Le client Windows lit les Releases publiques de `Sreleew/GTA_rankd` sans token GitHub. Les modifications du snapshot ou du correctif lancent les tests, construisent le paquet de mise à jour et publient une Release stable.

Ne jamais publier de vidéos personnelles, `config.yaml`, bases de données, modèles ou secrets.
