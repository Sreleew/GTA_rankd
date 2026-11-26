# Vérification v0.7.0

- Contrat metadata legacy conservé : title, description, hashtags et title_variants restent disponibles.
- Nouveaux champs platforms.youtube_shorts, platforms.tiktok et platforms.instagram validés.
- Les descriptions de chaque plateforme ajoutent une seule ligne de crédit contrôlée par l'application.
- Fichiers texte de publication produits avec chaque Short.
- Miniature créée localement à partir de l'image extraite par FFmpeg, sans appel à un service distant.
- Annulation des tâches queued et running exposée par API pour les Shorts et les scans Moments forts.
- run_quiet termine le processus enfant quand l'événement d'annulation est déclenché.
- Test de régression de sous-processus annulable ajouté.
