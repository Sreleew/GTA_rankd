# GTA Ranked Studio v0.3.2 - guide de mise a jour et d'utilisation

## 1. Mise a jour depuis ta version v0.2.6, v0.3.0 ou v0.3.1

1. Dans ton ancien dossier d'installation, double-clique sur `STOP-STUDIO.bat` pour arreter le serveur local.
2. Telecharge et extrais `gta-ranked-studio-installable-v0.3.2.zip` dans un nouveau dossier temporaire. Ne l'extrais pas par-dessus l'ancien dossier.
3. Ouvre le dossier `gta-ranked-studio` contenu dans le ZIP.
4. Double-clique sur `UPDATE-FROM-ARCHIVE.bat`.
5. L'assistant cherche l'emplacement de l'installation existante via le marqueur Windows. S'il demande le chemin, colle :

```text
C:\Outils\GTA Ranked Studio\gta-ranked-studio-installable-v0.2.6\gta-ranked-studio
```

6. L'assistant sauvegarde le code de la version precedente, met a jour `studio`, `installer` et `tests`, puis verifie les scripts, dependances et tests.
7. Il conserve `.venv`, `config.yaml`, les prompts actifs, `data`, `inbox`, `out`, `models`, `tools`, `assets`, `work` et `logs`. Il ne telecharge pas a nouveau les paquets deja satisfaits.
8. Quand le message `MISE A JOUR TERMINEE` apparait, ferme la fenetre et lance `START-STUDIO.bat` dans ton ancien dossier d'installation.
9. Recharge Chrome avec `Ctrl + F5`. La version affichee en bas a gauche doit etre `v0.3.2`.

Ne relance pas `INSTALL.bat` pour cette mise a jour. Ne supprime pas l'ancien dossier ni la sauvegarde de code avant d'avoir verifie que l'application s'ouvre et qu'un rendu de test fonctionne.

## 2. Tester le format Short vertical

1. Ouvre `Créer un Short`.
2. Importe un fichier video de 15 a 30 secondes pour le premier test.
3. Confirme que tu as le droit d'utiliser ce clip et son audio.
4. Laisse `Plein ecran vertical 9:16` selectionne.
5. Laisse le zoom dynamique et le whoosh discret actives pour le premier essai.
6. Lance le rendu, puis ouvre le MP4.

Le fichier doit faire 1080 x 1920 pixels. Le mode plein ecran recadre les bords d'une source paysage. Si le streamer ou une partie importante est hors champ, utilise les curseurs horizontaux et verticaux. Si tu dois conserver tout le cadre source, choisis `Video entiere + fond floute`.

## 3. Options de montage disponibles

- **Plein ecran vertical 9:16** : remplit le cadre vertical en recadrant la source.
- **Video entiere + fond floute** : conserve l'image originale au centre et ajoute un fond rempli/floute.
- **Position X/Y** : ajuste la zone du recadrage.
- **Zoom dynamique** : zoom progressif et retour au cadre initial autour du pic audio detecte. Il ne suit pas encore le visage.
- **Coupe automatique** : pour les sources de plus de 45 secondes, choisit une fenetre de 15 a 45 secondes autour du pic. Si Whisper transcrit la parole, les pauses et fins de phrases peuvent affiner la fin de l'extrait. Desactive cette option si tu veux conserver toute la source.
- **Hook et contexte** : textes courts en anglais visibles au debut. Tu peux saisir tes propres textes ou laisser les valeurs generees.
- **Branding** : badge GTA VI et handle de la chaine.
- **Whoosh** : petit effet sonore original, discret, synchronise autour du moment fort. Tu peux le desactiver.
- **Miniature** : capture autour du pic avec un titre court.
- **Metadonnees** : `title.txt`, `description.txt` et `meta.json` sont enregistres avec le rendu.

## 4. Activer les sous-titres Whisper

Le modele seul ne suffit pas : il faut d'abord installer le moteur `whisper.cpp` pour Windows avec le backend Vulkan. Le plus simple est de telecharger une archive Windows x64 Vulkan precompilee depuis https://github.com/jiang1997/whisper.cpp-release/releases (build communautaire, non officielle), puis d'extraire tout son contenu dans `tools\whisper.cpp\` pour conserver les DLL a cote de `whisper-cli.exe`. Ouvre ensuite `Parametres` et actualise le diagnostic. Telecharge enfin `ggml-large-v3-turbo.bin` depuis cette page. Le modele pese environ 1,6 Go et reste stocke dans `models\whisper\`.

La version corrige la confusion entre `-ml` et les horodatages des mots : dans whisper.cpp, `-ml` signifie longueur maximale des segments en caracteres, pas word timestamps. Si ton binaire expose `-dtw` et `-ojf`, le studio demande les timestamps DTW par token, puis les regroupe en mots. Si ce support n'est pas disponible, le studio revient aux sous-titres SRT par segment et l'indique dans la file de traitement.

Le backend peut utiliser Vulkan si le binaire whisper.cpp installe a ete compile avec le support correspondant. Sinon le CPU est utilise. La presence du mot `Vulkan` dans le diagnostic ne garantit pas a elle seule que ce binaire est compile avec cette option.

## 5. Activer Ollama pour les metadonnees IA

Ollama est facultatif. Pour activer la generation locale de hooks, titres, descriptions et hashtags :

1. Installe Ollama depuis https://ollama.com/download/windows.
2. Ouvre PowerShell et execute `ollama pull qwen2.5:7b-instruct`.
3. Verifie avec `ollama list`.
4. Garde Ollama lance, puis va dans Parametres et clique sur `Actualiser`.

Sans Ollama, le rendu continue avec des textes de secours deterministes. Aucun service IA cloud n'est appele.

## 6. Fichiers crees pour chaque Short

Dans `out\shorts\<date>\<slug>\` :

- `video.mp4` : rendu vertical.
- `thumbnail.jpg` : miniature.
- `title.txt` et `description.txt` : metadonnees pour la publication.
- `meta.json` : provenance, options, encodeur, duree, pic, trim et etat de transcription.
- `captions.srt` et `captions.ass` : sous-titres et overlays lorsque disponibles.

Un rendu reste en attente de validation. Seuls les clips que tu valides sont ajoutes au Clip Bank.

## 7. Limites connues

- Le zoom est centre sur le cadre et declenche autour du pic audio global ; ce n'est pas encore un suivi IA de visage ou de sujet.
- La detection du moment fort se base sur l'energie audio : un cri, une musique ou un son fort peut etre choisi a la place de la blague la plus interessante.
- Les timestamps mot a mot dependent du support DTW de `whisper-cli.exe`. Le fallback SRT est par segment, pas mot par mot.
- Le Daily Best Of (scoring, interface de selection, assemblage horizontal, chapitres, Hall of Fame et miniature) reste a developper.
- Le watch folder permanent et l'export CSV complet ne sont pas encore termines.
- Aucun upload ou publication vers les plateformes n'est automatise.
- L'autorisation d'un streamer ne regle pas automatiquement les droits sur le jeu, la musique ou d'autres elements integres a une video. Verifie les droits applicables a chaque source.


## Mise à jour v0.3.2 depuis v0.3.1

Pour appliquer le correctif, ferme GTA Ranked Studio, extrais l'archive v0.3.2 dans un nouveau dossier temporaire, puis lance `UPDATE-FROM-ARCHIVE.bat`. Ne relance pas `INSTALL.bat` depuis l'archive temporaire. L'assistant retrouve l'installation mémorisée et remplace uniquement le code, les scripts d'installation, les tests et les fichiers de version. Il conserve `.venv`, `config.yaml`, les clips, les rendus, les modèles, les outils et les bases de données.

Cette version ajoute le diagnostic du moteur Whisper dans `Parametres`, la verification de la prise en charge DTW, la detection des peripheriques Vulkan lorsque le binaire le permet, et le controle de validite du fichier modele. Le moteur Windows Vulkan reste a installer dans `tools\whisper.cpp\` ; le modele large-v3-turbo se telecharge depuis `Parametres`.
