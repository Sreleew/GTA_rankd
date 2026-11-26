# Vérification v0.7.2

- Le timestamp de miniature est sélectionné à partir des mots saillants du transcript.
- Plusieurs images basse résolution sont scorées par entropie, contraste, contours et saturation pour éviter les écrans presque vides.
- Une seule image finale est extraite à pleine résolution depuis la vidéo source.
- Un titre contenant une citation incomplète est rejeté ; le fallback utilise l'angle le plus explicite détecté dans le transcript.
- Le timestamp de miniature reste distinct du pic audio utilisé pour le montage.
- Tests ciblés sur la sélection temporelle, le rejet des citations tronquées et la qualité visuelle.
