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
8 chapitres sur 8.** Puis **VOLET 35, tour 2** (ch. 03, 04, 05) : registre des sources,
récupération par portée, la réponse dit d'où elle vient. Puis **tour 3** (ch. 06, 07, 09) :
manques mesurés, sources candidates du registre, contradictions rapportées. Puis **tour 4**
(ch. 08, 10) : collecte décidée sous portillon, politique santé. **VOLET 35 : 10/12** — les
deux derniers chapitres demandent de vrais documents.

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
- **VOLET 35, tour 2** : la fiabilité vient du **registre** (`corpus/sources/senegal.yaml`)
  et plus du document qui la revendique — URL refusée avec sa raison, autorité usurpée
  impossible. La récupération lit la portée : sujet national sans source locale → pas de
  réponse ; sinon le local passe devant sans effacer le mondial. La réponse **dit** avec
  quelles sources elle est construite.
- **VOLET 35, tour 3** : un manque est un couple sujet × portée que de **vraies questions**
  ont touché sans réponse (journal d'audit existant, aucun second journal). La découverte
  propose depuis le **registre** et ne décide rien. Les contradictions sont **rapportées,
  jamais résolues** — aucun gagnant désigné, et deux pays ne se contredisent pas.
- **VOLET 35, tour 4** : la collecte est **décidée**, jamais exécutée par le module —
  registre, `robots.txt` appliqué, licence (inconnue → `reference_only`), approbation
  humaine. La santé a un **plancher de sources** plus haut, un avertissement partout, et
  **le refus de la posologie, du diagnostic et de la prescription est du code**, appliqué
  après la génération.
- **L3 (VOLET 36, ch. B)** : la règle du pluriel `-s` ne s'applique plus au wolof ni au
  pulaar. Le vrai risque était la **symétrie** — indexer sans amputer pendant qu'une
  requête reste française ferait disparaître des documents présents ; réglé par
  l'expansion de requête, pas par une détection inventée.
- Suite complète : **2891 tests passent**, 8 ignorés ; `ruff` propre.

**Prochaine étape**
**Rien n'est en cours.** VOLET 36 clos ; VOLET 35 avancé jusqu'au chapitre 05.
**Rien n'est en cours.** VOLET 36 clos (8/8), VOLET 35 à **10 chapitres sur 12**.
**Les deux derniers dépendent de toi** : ch. 11 le premier vrai corpus sénégalais, ch. 12
le corpus mondial. Ils demandent de **vrais documents déclarés dans un manifeste**
(`docs/knowledge/README.md`) — les faire ici reviendrait à fabriquer de la connaissance,
ce que le dépôt refuse. **L3 est fait** ; **L4** (mesurer la récupération sémantique en wolof) attend C1 et un
corpus.
**L3** (normalisation par langue) reste à faire ; **VOLET 35** est en pause après le tour 1
(chapitres 03, 04, 05).

**Bloqué / à surveiller**
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192. Il bloque la
  mesure de la génération et du récupérateur sémantique, en wolof comme ailleurs.
- **`git push origin v0.1.0`** : le proxy refuse les étiquettes (403). L'étiquette existe
  localement sur `383fcf7` ; à pousser depuis un clone normal.
- **Le corpus sénégalais** demande de vrais documents déclarés — il ne s'invente pas.
- **TEST 2 et TEST 6 non exécutés** : ils demandent un hôte Docker.
