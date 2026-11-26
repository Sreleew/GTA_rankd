# Carte rapide du projet

## À lire avant de modifier
1. \`docs/CONTINUATION.md\` : version, état réel et prochaines étapes.
2. \`docs/WORKING-AGREEMENT.md\` : méthode de travail.
3. Ce fichier : emplacement du code et tests associés.

## Source active
- \`app/studio/cli.py\` : commandes CLI et lancement du serveur local.
- \`app/studio/config.py\` : lecture et résolution des chemins de configuration.
- \`app/studio/doctor.py\` : diagnostic des dépendances et du matériel.
- \`app/studio/web/app.py\` : routes FastAPI, API et contrôles d'entrée.
- \`app/studio/web/worker.py\` : orchestration des traitements locaux.
- \`app/studio/web/short_renderer.py\` : filtres FFmpeg, encodage et miniatures.
- \`app/studio/web/short_editor.py\` : hooks, captions et composition de miniature.
- \`app/studio/web/metadata.py\` : titres, descriptions, hashtags et Ollama.
- \`app/studio/web/highlights.py\` : analyse et classement des moments forts.
- \`app/studio/web/updater.py\` : recherche, téléchargement et intégrité des releases.
- \`app/installer/\` : installateur Windows, migration legacy et constructeur de package.
- \`app/tests/\` : tests de régression, API, rendu et installateur.

## Outillage et documentation
- \`docs/\` : source documentaire unique. Le ZIP embarque ces fichiers depuis cette source.
- \`tools/check_project_memory.py\` : cohérence des versions et du mémo.
- \`tools/verify_release_package.py\` : validation ZIP, contenu, exclusions et SHA-256.
- \`.github/workflows/audit-source.yml\` : tests Linux et package.
- \`.github/workflows/windows-smoke.yml\` : tests Windows, PowerShell et package.
- \`.github/workflows/release.yml\` : tests finaux et publication stable.
- \`.github/dependabot.yml\` : mises à jour mensuelles.

## Parcours de modification rapide
- Interface : modifier le fichier HTML/CSS/JS concerné, puis lancer \`node --check studio/web/static/app.js\`.
- Montage : modifier worker/editor/renderer et les tests associés.
- API : modifier \`app.py\` puis \`test_web.py\`.
- Installation/mise à jour : modifier le script PowerShell et ses tests, valider sur le runner Windows.
- Package : modifier le builder et le vérificateur commun, puis examiner les artefacts Linux et Windows.

Éviter un scan complet du dépôt pour une modification locale. Lire les dépendances directes et les tests du module touché, et élargir seulement si le changement traverse plusieurs couches.