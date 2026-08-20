# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **OPEN-SOURCE ECOSYSTEM AUDIT & INTEGRATION**
                   12 chapitres → **22 phases**
Phase courante   : **E03.3 — en attente de confirmation**
Terminées        : E01.1, E01.2, E02.1, E02.2, E03.1, E03.2 — `docs/oss-ecosystem/`
Repère           : **1 failed, 6967 passed, 12 skipped** (l'étiquette `v0.1.0`)
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente** : `.claude/rules/post-integration-validation.md` — toute
phase se termine par une validation de non-régression complète, jamais par une
compilation.

---

## Le plan

| Chapitre | Sujet (§ de la directive) | Phases |
|---|---|---|
| Ch. 01 | Audit du dépôt : les 12 sont-ils là ? (§1, §13) | 2 — `E01.1` manifestes, verrous, imports tracés · `E01.2` chemins d'exécution + relevé de la suite avant tout |
| Ch. 02 | Audit de l'architecture existante (§2) | 2 — `E02.1` inférence, fournisseurs, routage, voix · `E02.2` mémoire, connaissance, RAG, orchestration, sécurité, observabilité |
| Ch. 03 | Analyse projet par projet, 12 × 20 champs A–T (§3) | 4 — `E03.1` Transformers, SGLang, llama.cpp · `E03.2` vLLM, LiteLLM · `E03.3` LangGraph, LlamaIndex, Qdrant · `E03.4` OpenHands, Unsloth, whisper.cpp, Open WebUI |
| Ch. 04 | Analyses spéciales A–H (§4) | 4 — `E04.1` A+B · `E04.2` C+D · `E04.3` E+F · `E04.4` G+H |
| Ch. 05 | Matrice de duplication (§5) | 1 (indivisible) |
| Ch. 06 | Matrice de licences, sources officielles (§8) | 2 — six projets par phase |
| Ch. 07 | Audit de sécurité (§9) | 1 (indivisible) |
| Ch. 08 | Audit de performance — ce qui est mesurable ici (§10) | 1 (indivisible) |
| Ch. 09 | Indépendance vis-à-vis des fournisseurs + architecture minimale (§6, §11) | 1 (indivisible) |
| Ch. 10 | Portes de faisabilité — les 14 règles (§7) | 1 (indivisible) |
| Ch. 11 | Plan d'intégration et ordre d'implémentation (§11, §12) | 1 (indivisible) |
| Ch. 12 | ADR + rapport final, les 22 points (§14) | 2 — `E12.1` l'ADR · `E12.2` le rapport |

**Total : 22 phases.** Documents sous `docs/oss-ecosystem/`.

## Ce que la directive interdit, et qui tiendra

- **§12 : ne rien implémenter.** Zéro ligne de `src/`, zéro dépendance, zéro
  test ajouté ou modifié — comme pour ADR-034 et ADR-035.
- **Jamais `INTEGRATE` par popularité** (§3, règle finale).
- **Jamais de chiffre inventé** : §4A, §7 et §10 disent `UNKNOWN` plutôt que
  d'estimer.

## Deux contraintes de cet hôte, connues d'avance

Elles ne sont pas une excuse, elles bornent ce que le programme pourra conclure.

1. **Aucun GPU** (`ls /dev/nvidia*` → rien), 4 CPU, ~15 Go de RAM libre, 28 Go de
   disque — mesuré le 2026-08-20. vLLM, SGLang et Unsloth ne pourront pas être
   mesurés ici : ce sera `UNKNOWN`, jamais une estimation.
2. **Le mandataire refuse un nombre de domaines** (`CONNECT → 403`, mesuré).
   Toute source officielle illisible est consignée `UNKNOWN` **avec l'échec
   exact**, jamais remplacée par la mémoire du modèle.

## Une chose que E01.1 doit confirmer ou infirmer en premier

`src/coding_engine/adapters/openhands_adapter.py` existe dans ce dépôt. Si
**OpenHands est déjà un adaptateur déclaré**, la question du §4F n'est pas
« faut-il l'intégrer » mais « qu'est-ce que l'existant ne fait pas ». La même
vérification vaut pour les onze autres : rien n'est présumé absent.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **Universal Creative Intelligence** — 44 phases. `docs/creative/final-report.md`
2. **Master Update Directive V4 (MoneyPrinterTurbo)** — 15 phases. ADR-030.
3. **Creative Canvas & Cinema Orchestration** — 17 phases. ADR-031.
4. **Research Orchestration Integration** — 18 phases. ADR-032.
5. **Live Context Engine / Call.md** — 27 phases. ADR-033. **PR #31 fusionnée.**
6. **OpenClaw Compatibility & Safe Integration** — 19 phases. ADR-034 :
   **ne pas intégrer**.
7. **DeepSeek Harness Compatibility Audit** — 14 phases. ADR-035 : quatrième
   back-end de codage, **implémentation non autorisée**.
8. **Finalisation** — ADR-036 (Apache-2.0), test de souveraineté des runtimes
   subordonnés, mémoire réalignée. **PR #32 fusionnée.**
