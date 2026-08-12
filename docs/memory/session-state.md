# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-12

**En cours** : **VOLET 34 — agent d'ordinateur personnel** (`docs/roadmap/VOLET_34.md`),
à **un chapitre par tour** (cadence demandée par l'utilisateur). Chapitres 01 à 11 faits.

**Terminé dans cette session**
- Le backlog (persistance audit/approbation, validation des sorties d'agents, ADR-016 en
  trois étapes, le linter `ruff`) — détail dans `completed-work.md`.
- **VOLET 34** : état des lieux mesuré (`personal-agent-assessment.md`), deux études
  comparatives sourcées, **ADR-017** (les capacités manquantes arrivent comme outils),
  **ADR-018 proposé**, puis la vue (`src/tools/screen/`), la main sous portillon
  (`src/tools/gui/`), les racines et l'annulation (`src/storage/`), le bac à sable et ses
  tests d'évasion (`src/sandbox/`), **MCP** (`src/mcp/`) — serveur en liste blanche de huit
  outils, client épinglé — et la **compréhension du dépôt entier** (`repo_graph.py`,
  `symbol_index.py`), qui fait passer la boucle de code de 22 % à 87 % de modifications
  réellement vérifiées, puis les **trois agents manquants** du brief
  (`agents/organizer/`, `project_manager/`, `opportunity/`) — six spécialistes sur six.
- Suite complète : **2571 tests passent**, 7 ignorés ; `ruff check .` propre.

**Prochaine étape**
**Chapitre 12 — style de travail et amélioration continue**. Puis 13 (modèle de sécurité)
et 14 (matériel, pile logicielle, chemins de mise à niveau).

**Bloqué / à surveiller**
- **ADR-018 attend ta décision** : A / B / C sur la souveraineté. Recommandation : **B**.
- **`git push origin v0.1.0`** : le proxy refuse les étiquettes (403). L'étiquette existe
  localement sur `383fcf7` ; à pousser depuis un clone normal.
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192.
- **Le corpus sénégalais** demande de vrais documents déclarés — il ne s'invente pas.
- **TEST 2 et TEST 6 non exécutés** : ils demandent un hôte Docker.
