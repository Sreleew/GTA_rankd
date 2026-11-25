# Vérification v0.4.2

- Le découpage Twitch utilise yt_dlp.utils.download_range_func via l'option Python download_ranges.
- Les tests vérifient le début/fin exacts, y compris les secondes fractionnaires.
- La suite complète de tests doit passer avant publication.
- La limite de 3 heures par plage et le délai FFprobe dynamique de v0.4.1 sont conservés.
