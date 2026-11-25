# Vérification v0.6.2

- Plus de limite par défaut de 8 candidats.
- Seuil strict : un score de 80.0 ou inférieur est rejeté.
- Tous les candidats retenus dépassent 80/100.
- Tri par score et espacement anti-chevauchement préservés.
- Le paramètre max_candidates reste disponible pour les appels explicites qui souhaitent un plafond.
- Tests couvrant le rejet des scores faibles et un scan retournant au moins 9 passages.
- Interface affichant les scores avec une décimale et expliquant le seuil.
