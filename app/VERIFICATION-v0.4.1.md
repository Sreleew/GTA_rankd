# Vérification v0.4.1

- Le scanner calcule le délai FFprobe selon la taille du fichier local.
- Le délai minimum est de 300 secondes, avec 60 secondes supplémentaires par tranche de 256 MiB, plafonné à 1 800 secondes.
- Les appels FFprobe des autres flux conservent leur délai par défaut de 60 secondes.
- Des tests couvrent le calcul du délai, le plafond de 30 minutes et la transmission du délai à FFprobe.
- La limite d'analyse reste de 3 heures et la transcription demeure découpée par blocs de 5 minutes.
