# Vérification v0.7.1

- Métadonnées générées en un seul titre et une seule légende, partagés sur les trois réseaux.
- Fallback local contenant le nom du streamer, le mot-clé GTA et les hashtags pertinents lorsque les sources le permettent.
- Un seul bouton de copie dans la carte Short.
- Miniature extraite de la source originale au temps du pic, puis composée en 1080x1920.
- Pas de seconde passe d'encodage vidéo ; une seule extraction d'image et composition Pillow.
- Un appel Ollama au maximum, timeout borné à huit secondes.
- Tests ciblés couvrant le partage du texte et la composition verticale depuis une source paysage.
