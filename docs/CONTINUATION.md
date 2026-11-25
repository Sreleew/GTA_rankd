# GTA Ranked Studio | Mémo maître de reprise

> À lire en premier dans toute nouvelle conversation sur le projet. Ce document est la mémoire durable de GTA Ranked Studio et doit être actualisé à chaque mise à jour.

- **Dernière mise à jour :** 25 novembre 2026
- **Version source de référence :** 0.7.8
- **État :** candidat reconstruit, testé et empaqueté par GitHub Actions. Pas encore une Release stable publiée.
- **Dépôt :** https://github.com/Sreleew/GTA_rankd
- **Branche de travail :** `feature/v0.7.8-shorts-retention`
- **Base publique au dernier audit :** `main`, v0.7.7
- **Dernier audit :** https://github.com/Sreleew/GTA_rankd/actions/runs/45666500907
- **Comparaison des sources :** `docs/source-audit-v0.7.8-v0.8.0-2026-11-25.md`

## 1. Objectif du produit

Application Windows locale qui analyse des clips et VOD GTA, repère les passages intéressants, produit des Shorts verticaux soignés et prépare les éléments de publication. La cible à terme est un flux largement automatisé : importer une VOD, classer les moments forts, proposer une sélection éditoriale, produire les Shorts, puis conserver vidéos, miniatures et métadonnées dans une bibliothèque exploitable.

Le projet doit rester local-first, sans abonnement ni API IA payante obligatoire. Les vidéos et médias ne doivent pas être envoyés vers un service cloud par le pipeline de traitement.

## 2. État actuel et fonctionnalités présentes en v0.7.8

- Import de vidéos locales et d'URLs de clips/VOD Twitch accessibles via yt-dlp.
- Téléchargement de plages horaires avec progression et gestion des erreurs/reprises.
- Analyse audio + transcription Whisper : énergie, densité de parole, expressions de réaction, classement heuristique et sélection manuelle des passages.
- Génération de Shorts 1080 × 1920. Le rendu par défaut conserve l'image source complète, centrée, avec fond flouté. Le zoom dynamique est désactivé par défaut.
- Transcription locale, sous-titres, filtre lexical de réactions et mode expérimental de voix dominante.
- Hooks, titres, descriptions et hashtags générés localement avec Ollama/Qwen facultatif et fallback déterministe.
- Miniatures composées depuis de vraies images du clip, habillage GTA Ranked, signature de chaîne et effets sonores.
- File de traitement, progression FFmpeg, annulation, prévisualisation, validation/rejet et bibliothèque de clips.
- **Correctif v0.7.8 :** après validation d'un Short, Prévisualiser, Télécharger, Miniature, Copier le titre, Copier la description, Copier les hashtags et Copier le post restent accessibles. La validation ne doit pas supprimer les métadonnées ni les fichiers associés.
- L'application prépare les contenus de publication mais ne publie pas automatiquement vers YouTube, TikTok ou Instagram.

## 3. Architecture technique et environnement

- Backend : Python 3.11, FastAPI, application web servie localement.
- Frontend : HTML/CSS/JavaScript dans `studio/web/static/`.
- Orchestration : `studio/web/worker.py`.
- Analyse des moments forts : `studio/web/highlights.py`.
- Rendu : `studio/web/short_renderer.py`, édition : `studio/web/short_editor.py`.
- Transcription : `studio/web/transcribe.py`, voix : `studio/web/speakers.py`.
- Métadonnées : `studio/web/metadata.py` et `prompts/`.
- Persistance : `studio/web/store.py`.
- Mise à jour : `studio/web/updater.py` et `installer/`.
- Profil matériel cible : Windows 10/11, AMD Radeon RX 9060 XT 16 Go, FFmpeg H.264 AMF avec fallback libx264, whisper.cpp Vulkan avec fallback CPU, Ollama/Qwen local facultatif.

**Débit à ne pas confondre :** la source v0.7.8 actuellement reconstruite définit `encoding.amf_bitrate: 12M`. Un ancien mémo mentionnait 9 Mbit/s, mais cette valeur n'est pas celle de la configuration reconstruite. Ne change pas le débit sans mesure sur le PC Windows réel.

## 4. Limites connues

1. La détection des moments forts est audio/texte. Elle ne comprend pas encore les événements visuels du gameplay et ne doit pas prétendre détecter avec certitude un kill, crash ou événement HUD.
2. Le filtre lexical ne sépare pas mathématiquement streamer et personnages lorsque leurs voix sont mélangées.
3. La diarisation est expérimentale : en cas d'ambiguïté, mieux vaut préserver les sous-titres que supprimer la mauvaise voix.
4. La CI Linux ne valide pas les performances réelles AMF/Vulkan de la RX 9060 XT sous Windows.
5. Les hooks, coupes de phrases, CTA et compositions doivent encore être jugés sur des Shorts réels. Éviter les CTA génériques en ouverture.
6. Les compilations Best Of, chapitres et Hall of Fame figurent dans l'ancienne roadmap mais leur état fonctionnel n'a pas été confirmé dans la source v0.7.8.
7. La publication sur les plateformes reste manuelle.

## 5. Source de référence et état des branches

### Candidat v0.7.8

La source a été reconstruite depuis le snapshot v0.4.0 avec les correctifs cumulatifs jusqu'à v0.7.8. Dernière validation GitHub Actions connue :
- reconstruction réussie ;
- **128 tests réussis, 1 ignoré** ;
- contrôle syntaxique JavaScript réussi ;
- paquet Windows candidat construit et uploadé.
- Le SHA-256 du paquet est consigné dans le fichier `SHA256SUMS.txt` de chaque artifact ; utiliser le checksum associé au run concerné plutôt qu'un hash recopié dans ce mémo.

C'est un candidat validé par CI, pas une Release stable et pas une validation GPU sur Windows réel.

### Snapshot v0.8.0 bloqué

Le dépôt contient 17 fragments `source/v0.8.0-source.part000.b64` à `part016.b64`. Les segments `part003` et `part004` sont strictement identiques : seulement 16 contenus uniques. L'archive reconstruite est invalide. L'historique Git consulté ne fournit pas d'ancienne version de `part004`.

**Ne pas utiliser, fusionner ou réparer par supposition le snapshot v0.8.0 actuel.** Restaurer le véritable segment depuis la source d'origine ou régénérer l'archive depuis un arbre source complet et vérifié.

La prochaine étape est de figer l'arbre applicatif v0.7.8 reconstruit en snapshot source canonique déterministe, accompagné d'un manifeste, d'un inventaire et d'un SHA-256. Les futures versions devront partir de cette base plutôt que rejouer les anciens correctifs depuis v0.4.0.

## 6. Fichiers importants

- `VERSION.txt` : numéro de version.
- `NOTES-vX.Y.Z.txt` : notes de chaque mise à jour.
- `README.md` : documentation produit.
- `docs/UPDATES.md` : guide utilisateur et historique des mises à jour.
- `docs/CONTINUATION.md` : ce mémo maître à lire en premier.
- `tools/check_project_memory.py` : vérifie l'alignement du mémo avec la version et les notes.
- `installer/build_release_package.py` : crée le ZIP de mise à jour.
- `studio/web/` : application et interface.
- `tests/` : tests de régression.

Ne jamais publier `config.yaml`, vidéos, rendus personnels, bases SQLite, modèles IA téléchargés, environnements virtuels, logs, tokens ou secrets. Les mises à jour doivent préserver les configurations et données utilisateur.

## 7. Commandes de contrôle

Depuis la racine source, dans PowerShell :

```powershell
Copy-Item config.yaml.default config.yaml
python -m pip install -r requirements.txt
python tools/check_project_memory.py
python -m pytest -q
node --check studio/web/static/app.js
python installer/build_release_package.py --version 0.7.8 --output-dir dist
```

La copie du fichier de configuration n'est valable que pour une installation neuve ou un environnement de test isolé. Ne jamais écraser le `config.yaml` existant de l'utilisateur.

## 8. Règles de travail pour toute nouvelle conversation

- Travailler directement depuis le dépôt GitHub `Sreleew/GTA_rankd` quand son accès est disponible. Ne pas redemander le ZIP à l'utilisateur.
- Lire ce mémo, puis vérifier le HEAD des branches, les commits, les Releases et les workflows avant toute modification.
- Ne pas confondre branche, candidat CI, artifact et Release stable.
- Modifier une branche de travail, tester, conserver des commits explicites, ne pas publier une version non validée.
- Préserver config, bases, projets, exports, médias et modèles locaux.
- À chaque version, mettre à jour ensemble `VERSION.txt`, `NOTES-vX.Y.Z.txt`, `README.md`, `docs/UPDATES.md` et ce mémo.
- Le contrôle CI doit échouer si la version du mémo ne correspond pas à `VERSION.txt), si la date ou des sections essentielles manquent, ou si les notes de version sont absentes.
- À chaque mise à jour, ajouter au mémo les fonctionnalités livrées, les tests et résultats, la branche/commit, le statut CI/Release, les limites et les prochaines tâches.
- Toujours distinguer « implémenté », « testé en CI », « testé sous Windows réel » et « publié ».

## 9. Prochaines étapes priorisées

1. Créer le snapshot canonique v0.7.8 déterministe avec SHA-256, manifeste et inventaire des fichiers.
2. Enregistrer le snapshot dans Git et faire repartir les futures versions de celui-ci.
3. Brancher le contrôle du mémo sur les workflows d'audit et de release.
4. Réconcilier proprement `main` et `feature/v0.7.8-shorts-retention`, sans intégrer les fragments v0.8.0 corrompus.
5. Tester sous Windows le cycle complet création > validation > fermeture/réouverture du Short et la persistance des métadonnées.
6. Valider AMF, Whisper Vulkan, Qwen et la qualité du rendu sur la machine réelle.
7. Améliorer ensuite le scoring, les coupes naturelles, les hooks et enfin l'analyse visuelle du gameplay.

## 10. Message de reprise prêt à copier

> Nous reprenons GTA Ranked Studio. Lis d'abord `docs/CONTINUATION.md` dans le dépôt `Sreleew/GTA_rankd`, puis vérifie les branches et derniers workflows GitHub. La base provisoire fiable est la source reconstruite v0.7.8, validée par CI avec 128 tests réussis et 1 ignoré. Le snapshot v0.8.0 actuel est corrompu car `part003` et `part004` sont identiques : ne l'utilise pas. Continue les étapes du mémo directement depuis GitHub sans me demander de ZIP, en préservant les données locales. Après chaque mise à jour, actualise ce mémo, les notes, le README et le changelog, puis fais vérifier leur cohérence par CI.
