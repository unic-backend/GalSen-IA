# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **OPEN-SOURCE COMPONENT AUDIT #01 — `codebase-memory-mcp`**
                   Brief du propriétaire, 2026-08-22, phases 0 à 12 + rapport
Chapitres        : **13**
Phases           : **16**
Phase courante   : **10 (quatre options) — en attente de confirmation**
Terminées        : **0.1, 0.2, 1** — 3 sur 16. Sujet cloné à `010569fa`,
                   **1,3 Go, projet en C** (842 `.c`), **MIT**, 160 grammaires
                   tree-sitter, et **30 Mo de poids nomic-embed-code embarqués**.
                   **Ph2** : 14 types de nœuds, 8 relations, incrémental par
                   hachage, **aucun appel sortant trouvé dans `src/`**, mais il
                   **écrit dans les configs d'agent de `$HOME`**.
                   **Ph3** : 16 lignes sur 24 `KEEP` — **`code-review-graph` les
                   couvre déjà** ; 3 non couvertes (liens inter-services,
                   sémantique sans fournisseur, data flow).
                   **Ph4** : usage A pas démontré (CRG déjà là), **usage B rejeté
                   sur l'architecture**. **Ph5** : réellement indépendant des
                   fournisseurs — aucun client d'API, poids embarqués.
                   **Ph6** : **aucune licence incompatible**, aucun copyleft
                   (7 « MPL » = faux positif : *simplecpp*). **Ph7** : aucune
                   opération cachée ; **une opération privilégiée assumée** —
                   il écrit des fichiers d'instructions dans `$HOME`.
                   **Ph8** : banc défini, **`NOT_MEASURED`** — la mesure qui
                   déciderait est contre CRG, pas contre `grep`. **Ph9** : un
                   repli existe déjà (CRG) ; **le retrait n'est pas propre**
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente** : `.claude/rules/post-integration-validation.md`.

**Condition d'arrêt** : audit seulement. Aucune intégration, aucune modification
d'architecture, de schéma, d'API ou de test. Le VOLET s'arrête à la décision
(phase 11) ; la phase 12 ne produit qu'une conception, jamais du code.

---

## Le plan

```
Ch. 00  Ph0   État du dépôt GalSen IA, 16 points        → 2 phases
              0.1 mémoire, connaissance, graphe, MCP, indexation, recherche
              0.2 structure, impact, provenance, sécurité, self-healing,
                  tests, ADR, dépendances

Ch. 01  Ph1   Le dépôt officiel : sources, licence, CI  → 1 phase (indivisible)
Ch. 02  Ph2   Ce que le projet fait vraiment, 16 points → 2 phases
              2.1 indexation, graphe, nœuds, relations, requêtes, incrémental
              2.2 persistance, MCP, ce qui exige un LLM, dépendances

Ch. 03  Ph3   Matrice de comparaison, 24 capacités      → 2 phases
Ch. 04  Ph4   Deux usages : pendant vs après le déploiement → 1 phase (indivisible)
Ch. 05  Ph5   Indépendance vis-à-vis des modèles        → 1 phase (indivisible)
Ch. 06  Ph6   Licences : compatible / à surveiller / incompatible → 1 phase
Ch. 07  Ph7   Sécurité, 13 surfaces                     → 1 phase (indivisible)
Ch. 08  Ph8   Performance : leurs chiffres, puis les nôtres → 1 phase
Ch. 09  Ph9   Feasibility gates, 14 questions           → 1 phase (indivisible)
Ch. 10  Ph10  Quatre options A/B/C/D                    → 1 phase (indivisible)
Ch. 11  Ph11  Décision                                  → 1 phase (indivisible)
Ch. 12  Ph12  Si adaptation : conception seule, puis ARRÊT → 1 phase

Ch. 13        Rapport final, ses 25 points              → 1 phase (indivisible)
```

**Total : 16 phases.**

---

## Mesuré avant de planifier

`raw.githubusercontent.com/DeusData/codebase-memory-mcp` → **200**
`api.github.com/repos/DeusData/codebase-memory-mcp` → **403**

Contenu lisible fichier par fichier ; **arborescence et commit exact non**. Comme
pour l'audit Superpowers, la phase 1 clone via le proxy git — sinon la version
examinée est `UNKNOWN` et il faudrait **deviner** quels fichiers existent.

---

## Un point de contexte, pas une conclusion

Ce dépôt vise la mémoire de code, le graphe et MCP. GalSen IA a déjà, mesuré au
VOLET précédent : `src/memory_engine/` (12 modules), `src/knowledge_engine/` (19),
`src/agent/repo_graph.py` + `repo_map.py` + `symbol_index.py`, `src/mcp/`, et le
serveur MCP **`code-review-graph` déjà branché** sur ce dépôt.

Le chevauchement sera donc large. **Ça ne préjuge de rien** — c'est précisément
ce que la matrice de la phase 3 doit mesurer, capacité par capacité.

Trois audits de compatibilité sur quatre se sont conclus par *ne pas intégrer*.
Un audit dont la conclusion est écrite d'avance n'en est pas un.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **SUPERPOWERS** — audit 24 phases + implémentation 11 phases. **ADR-038** :
   6 concepts adoptés comme prose, **rien installé**.
2. **Les quatre constats de l'audit OSS** — PR #34 et #35 fusionnées.
3. **OPEN-SOURCE ECOSYSTEM AUDIT** — 22 phases. **ADR-037** : zéro `INTEGRATE`.
4. **OpenClaw** — ADR-034 : ne pas intégrer.
5. **DeepSeek Harness** — ADR-035 : implémentation non autorisée.
6. **Live Context** (ADR-033), **Creative Canvas** (ADR-031), **Research
   Orchestration** (ADR-032), **MoneyPrinterTurbo** (ADR-030),
   **Apache-2.0** (ADR-036).
