# Vérification v0.4.0

## Fonctionnalités
- Source locale ou URL Twitch de VOD/clip.
- Analyse complète jusqu'à 3 heures, ou plage début/fin facultative.
- Préflight de durée avant téléchargement d'une VOD Twitch longue.
- Audio RMS par fenêtres de 2 secondes.
- Transcription Whisper par blocs de 5 minutes si le modèle et le binaire existent.
- Score explicable composé de l'énergie audio, de la densité de parole et de mots de réaction.
- Jusqu'à 8 candidats non chevauchants de 35 secondes.
- Conversion d'un candidat vers un job Short avec `source_range`, sans re-télécharger la source Twitch.

## Tests effectués
- Tests unitaires du calcul d'énergie, scoring, persistance et découpage WAV.
- Tests API : validation des URL Twitch, consentement, plages horaires vides et création d'un Short depuis un candidat.
- Smoke test FFmpeg local : génération d'une source synthétique de 48 secondes, détection d'un passage audio intense, création d'un Short de 35 secondes depuis ce passage.
- Le pipeline Shorts Whisper existant est préservé ; les timestamps DTW restent produits par le correctif v0.3.5.

## Limites connues
- Le classement initial ne réalise pas d'analyse visuelle du gameplay.
- Les scores sont des signaux de tri, pas une garantie que le passage est divertissant.
- Les VOD Twitch privées ou réservées aux abonnés peuvent être inaccessibles par URL sans accès local authentifié ; l'import d'un fichier auquel l'utilisateur a légitimement accès reste possible.
- Une analyse complète d'une VOD de plusieurs heures peut prendre du temps, car Whisper analyse les blocs audio en local.
