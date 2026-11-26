# Instructions pour les agents de développement

Avant tout travail, lire \`docs/CONTINUATION.md\`, \`docs/WORKING-AGREEMENT.md\` et \`docs/PROJECT-MAP.md\`.

La source applicative est \`app/\`. La documentation canonique est dans \`docs/\`. Ne pas développer dans les archives ni recréer de copies de ces documents sous \`app/\`.

Travailler sur une branche dédiée, inspecter le périmètre concerné, regrouper les changements et éviter les audits/CI redondants. Ne jamais inclure les données locales, médias, bases, modèles, configuration personnelle ou secrets. Toute modification de comportement doit avoir des tests ciblés. Les changements transversaux doivent passer Linux et Windows, Ruff et pip-audit.

Après chaque lot, mettre à jour \`docs/CONTINUATION.md\`. Ne jamais prétendre qu'une validation CI prouve l'utilisation du GPU AMD physique.