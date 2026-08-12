# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-12

**En cours** : **VOLET 34 — agent d'ordinateur personnel** (`docs/roadmap/VOLET_34.md`),
à **un chapitre par tour** (cadence demandée par l'utilisateur). Chapitres 01 à 12 faits.

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
  (`agents/organizer/`, `project_manager/`, `opportunity/`) — six spécialistes sur six —
  et le **style de travail** dérivé du signal consenti, appliqué aux invites, avec une
  mesure d'amélioration qui refuse de conclure sous 30 retours par fenêtre.
- Suite complète : **2599 tests passent**, 7 ignorés ; `ruff check .` propre.

**Prochaine étape** (cadence élargie, demandée le 2026-08-12)
**Chapitres 13 et 14 dans le même tour**, puis **ADR-018 passé en *Accepted* avec l'option B**,
que le propriétaire a tranchée. Ordre : ADR d'abord si les chapitres en dépendent, sinon après.

**Bloqué / à surveiller**
- **ADR-018 : décision prise — option B.** Le fichier est encore *Proposed* ; il reste à
  l'écrire comme décision acceptée. Ce n'est plus un blocage, c'est une tâche.
- **`git push origin v0.1.0`** : le proxy refuse les étiquettes (403). L'étiquette existe
  localement sur `383fcf7` ; à pousser depuis un clone normal.
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192.
- **Le corpus sénégalais** demande de vrais documents déclarés — il ne s'invente pas.
- **TEST 2 et TEST 6 non exécutés** : ils demandent un hôte Docker.
