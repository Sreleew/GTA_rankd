# Vérification v0.6.0

- Tests unitaires de sélection d'une voix dominante, de fallback prudent et du cas mono-voix.
- Le moteur diarize est chargé et installé uniquement à la demande.
- Le pipeline extrait l'audio du Short final et non l'intégralité de la VOD pour la diarisation.
- Les erreurs d'installation ou d'analyse des voix ne bloquent pas le rendu : les sous-titres de toutes les voix sont restaurés.
- Le hook utilise un maximum de six mots et la carte de contexte ne s'affiche que si elle est personnalisée.
- Les délais Ollama sont plafonnés à 20 secondes avec un seul essai.
- Le gestionnaire du modèle Whisper conserve les téléchargements partiels et reprend via HTTP Range quand le serveur l'autorise.
- Téléchargement Twitch plafonné à 1080p avec tentatives et fragments concurrents supplémentaires.
