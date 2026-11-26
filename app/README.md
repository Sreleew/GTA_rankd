# GTA Ranked Studio

Application Windows locale pour transformer des clips GTA en Shorts verticaux, avec traitement local et validation manuelle.

**Version préparée : 0.8.1.**

## Fonctionnalités

- Import local ou URL Twitch via yt-dlp.
- Analyse audio et transcription Whisper locale pour classer les moments forts.
- Montage vertical 1080 × 1920 avec cadrage intelligent, hooks et sous-titres.
- Miniature basée sur une image réelle du clip.
- Métadonnées avec Ollama/Qwen local facultatif et fallback déterministe.
- Contrôle qualité après export, prévisualisation et validation.
- Actions de prévisualisation, téléchargement, miniature et copie conservées après validation.

Le traitement vidéo, la transcription et la génération locale restent sur ce PC. Les médias, modèles, réglages, bases de données et exports ne sont pas téléversés par l'application.

## Installation et mise à jour

- Première installation : lancer `INSTALL.bat`.
- Mise à jour : **Paramètres > Mises à jour > Rechercher une mise à jour**.
- Ne jamais remplacer manuellement `config.yaml` pendant une mise à jour.
- Les données locales et réglages sont préservés.

## Environnement

- Windows 10/11 et Python 3.11 64 bits.
- FFmpeg/FFprobe.
- AMD AMF si disponible, avec repli libx264.
- whisper.cpp avec Vulkan si disponible, avec repli CPU.
- Ollama/Qwen facultatif.

Les performances AMF et Vulkan doivent être contrôlées sur le PC cible. Une validation CI Windows ne prouve pas que le GPU AMD physique est utilisé.
