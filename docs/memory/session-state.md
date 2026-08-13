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
honnête (`src/knowledge_engine/languages.py`, `GET /knowledge/languages`). **Chapitre C
terminé** — l'évaluation factuelle mécanique (`factual_evaluation.py`) et le jeu de
référence sénégalais, **0 entrée vérifiée et le disant**. **Chapitre D terminé** — les
agents `verifier` et `senegal`, chacun défini par son refus. **Chapitre E terminé** —
entités et relations avec provenance obligatoire, sans base graphe. **Chapitre F
terminé** — dix axes attachés au plan existant, deux qui agissent. **Chapitre G terminé**
— `knowledge_architect` et `data_engineer` : proposer, jamais appliquer. **Chapitre H
terminé** — les capacités différées sont mesurées à chaque scan. **VOLET 36 TERMINÉ,
8 chapitres sur 8.**

**Terminé dans cette session**
- **A.1 → A.3** : l'enveloppe de confiance et ses neuf chemins (RAG, MCP, recherche web,
  navigateur, API tierce, ticket GitHub, PDF, OCR, fichier disque). Une donnée externe
  arrive **annoncée comme donnée, avec son origine** ; `/security/posture` le mesure.
- **B (L1 + L2)** : les trois langues nationales entrent dans `Language`, l'ingestion et le
  manifeste les acceptent et **refusent une langue inconnue**. Le rapport dit capacité par
  capacité ce qui est réel — et marque `unknown`, pas `no`, ce qui n'a jamais été mesuré ici.
- **C** : affirmations non étayées comptées, sources citées confrontées à ce qu'on leur
  fait dire, contradiction distinguée de l'absence. Ce qui demande un modèle est **nommé**,
  pas fait. Le jeu de référence ne porte que des questions `to_source` — aucune réponse
  écrite de mémoire, et `score_entry()` refuse de les noter.
- **D** : `verifier` porte un verdict et ne réécrit jamais la réponse — sans passage il
  dit `cannot_verify`, jamais `supported`. `senegal` refuse un sujet national sans source
  nationale. Chaînon corrigé : `search_knowledge()` ne rendait ni `scope` ni `subject`.
- **E** : les entités existent comme objets ; une relation porte **ses propres** sources
  et ses bornes de validité. Rien n'entre sans source — refus, pas signalement. Parcours
  jusqu'à la profondeur 3 ; au-delà, le refus cite le déclencheur « base graphe ».
- **F** : dix axes sur le plan existant — pas un second planificateur. `risk` recommande
  `verifier`, `geographic_scope` recommande `senegal` ; les huit autres sont **observés**
  avant d'être branchés, et `axes_effect` dit quel axe a ajouté quel agent.
- **G** : `knowledge_architect` propose l'entrée de manifeste en `DRAFT` et ne l'applique
  jamais ; `data_engineer` **refuse** une série sans unité, période ni source. Les
  marqueurs partagés ont quitté le planificateur (`src/knowledge_engine/markers.py`).
- **H** : rien construit, et c'est le résultat — base vectorielle, base graphe, stockage
  objet pour la connaissance, files, acquisition automatisée restent différés, avec leurs
  déclencheurs **mesurés** au lieu d'être écrits. Le détecteur se tait tant que rien n'est
  franchi.
- Suite complète : **2824 tests passent**, 8 ignorés ; `ruff` propre.

**Prochaine étape**
**Rien n'est en cours.** Le VOLET 36 est clos, verdict mesuré dans son plan (§14).
Proposition : **reprendre le VOLET 35** aux chapitres 03 + 04 + 05 — registre de sources,
récupération par portée, la réponse dit sa portée. En attente de décision.
**L3** (normalisation par langue) reste à faire ; **VOLET 35** est en pause après le tour 1
(chapitres 03, 04, 05).

**Bloqué / à surveiller**
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192. Il bloque la
  mesure de la génération et du récupérateur sémantique, en wolof comme ailleurs.
- **`git push origin v0.1.0`** : le proxy refuse les étiquettes (403). L'étiquette existe
  localement sur `383fcf7` ; à pousser depuis un clone normal.
- **Le corpus sénégalais** demande de vrais documents déclarés — il ne s'invente pas.
- **TEST 2 et TEST 6 non exécutés** : ils demandent un hôte Docker.
