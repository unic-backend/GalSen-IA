# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-13

**En cours** : **VOLET 36** (`docs/architecture/volet-36-plan.md`), 8 chapitres A→H.
**Chapitre A terminé** — les **9 chemins d'entrée externe** sont enveloppés par la barrière
de confiance (`src/security/trust.py`) ; il y en avait un seul. **Chapitre B terminé** —
`WO`, `FF`, `SRR` déclarables, filtrables et retrouvables, avec le rapport de capacités
honnête (`src/knowledge_engine/languages.py`, `GET /knowledge/languages`).

**Terminé dans cette session**
- **A.1 → A.3** : l'enveloppe de confiance et ses neuf chemins (RAG, MCP, recherche web,
  navigateur, API tierce, ticket GitHub, PDF, OCR, fichier disque). Une donnée externe
  arrive **annoncée comme donnée, avec son origine** ; `/security/posture` le mesure.
- **B (L1 + L2)** : les trois langues nationales entrent dans `Language`, l'ingestion et le
  manifeste les acceptent et **refusent une langue inconnue**. Le rapport dit capacité par
  capacité ce qui est réel — et marque `unknown`, pas `no`, ce qui n'a jamais été mesuré ici.
- Suite complète : **2713 tests passent** (A.3) ; `ruff` propre.

**Prochaine étape**
**Chapitre C — l'évaluation factuelle, moitié mécanique** : justesse des citations et
affirmations non étayées, mesurables sans modèle. En attente de confirmation.
**L3** (normalisation par langue) reste à faire ; **VOLET 35** est en pause après le tour 1
(chapitres 03, 04, 05).

**Bloqué / à surveiller**
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192. Il bloque la
  mesure de la génération et du récupérateur sémantique, en wolof comme ailleurs.
- **`git push origin v0.1.0`** : le proxy refuse les étiquettes (403). L'étiquette existe
  localement sur `383fcf7` ; à pousser depuis un clone normal.
- **Le corpus sénégalais** demande de vrais documents déclarés — il ne s'invente pas.
- **TEST 2 et TEST 6 non exécutés** : ils demandent un hôte Docker.
