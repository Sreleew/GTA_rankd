# Vérification v0.5.0

- Scoring adaptatif testé sur 25, 35, 45 et 60 secondes.
- La sélection finale vérifie l'absence de chevauchement et conserve le classement par score.
- Tests du filtre webcam pour les quatre coins, le mode désactivé et une valeur invalide.
- Tests du wrapper de sous-processus sur Windows et les autres plateformes.
- Les tests d'intégration FFmpeg de la suite vérifient le rendu MP4 vertical.
- La caméra est découpée à partir d'une zone de coin choisie dans le formulaire. Il n'y a pas de détection automatique de visage dans cette version.
