# GTA Ranked Studio

Application Windows locale pour analyser des clips et VOD GTA, repérer les moments intéressants et produire des Shorts verticaux prêts à publier.

**Version stable : 0.7.8.**

## Fonctionnalités principales

- Import de vidéos locales et de clips/VOD Twitch accessibles via yt-dlp, avec plage horaire facultative.
- Analyse audio et transcription Whisper locale pour classer les moments forts.
- Score d'accroche distinct sur les cinq premières secondes, avec repli audio si Whisper n'est pas disponible.
- Création de Shorts verticaux 1080 × 1920, sous-titres, hooks et textes sociaux.
- Miniatures créées à partir de vraies images du clip.
- Métadonnées générées par Ollama/Qwen local si disponible, avec solution de repli déterministe.
- File de traitement, progression, annulation, prévisualisation, validation et bibliothèque de clips.
- Après validation, les actions Prévisualiser, Télécharger, Miniature et Copier les métadonnées restent disponibles.
- Contrôle qualité post-export non bloquant : validité MP4, durée, résolution, codec, audio, écrans noirs, images figées, silences et cohérence des sous-titres.

L'application prépare les contenus, mais ne publie pas automatiquement vers YouTube, TikTok ou Instagram.

## Installation et mise à jour

Pour une première installation, lancer `INSTALL.bat`.

Pour mettre à jour une installation existante, ouvrir **Paramètres > Mises à jour**, cliquer sur **Rechercher une mise à jour**, puis sur **Télécharger et installer**. L'application se ferme et redémarre après installation.

La mise à jour préserve les réglages, projets, bases, modèles, médias et exports locaux. Ne jamais remplacer manuellement `config.yaml` pendant une mise à jour.

## Configuration locale

- Windows 10/11.
- Python 3.11.
- FFmpeg pour le rendu vidéo.
- AMD H.264 AMF si disponible, avec repli libx264.
- whisper.cpp avec Vulkan si disponible, avec repli CPU.
- Ollama/Qwen local facultatif.

Les performances AMF et Vulkan doivent être vérifiées sur le PC cible. Une validation CI Windows ne prouve pas que le GPU AMD physique est utilisé.
