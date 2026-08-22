# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **aucun — au repos, décidé par le propriétaire le 2026-08-22**
Dernier terminé  : **les quatre constats de l'audit OSS**, 4 phases sur 4
                   PR #34 et #35 fusionnées, `main` à `078e3ec`
                   Avant lui : **OPEN-SOURCE ECOSYSTEM AUDIT & INTEGRATION**,
                   22 phases sur 22 → `docs/oss-ecosystem/final-report.md`, ADR-037
Phase courante   : aucune
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Ne pas ouvrir de VOLET de sa propre initiative.** Aucun fichier VOLET suivant
n'existe : les VOLETs 01–76 sont archivés, et les quatre derniers programmes
sont nés d'un brief du propriétaire. Un VOLET inventé ici serait exactement la
conversion `DESIRABLE → requested` qu'interdit
`.claude/rules/spec-driven-governance.md`. Quatre candidats mesurés ont été
proposés le 2026-08-22 et **écartés au profit du repos** : ADR-020 (seul ADR
encore `proposed`), la quatrième source de recherche (vision), la vérification
d'identité (P0), ou un brief. Ils restent dans `pending-work.md`.

**Règle permanente** : `.claude/rules/post-integration-validation.md` — toute
phase se termine par une validation de non-régression complète.

---

## La décision à ne pas re-déduire — ADR-037

**Zéro `INTEGRATE` sur douze.** 3 déjà présents (Transformers, vLLM, OpenHands),
2 atteignables par un seuil existant (SGLang, llama.cpp), 3 différés (LiteLLM,
Qdrant, Unsloth), 2 conservés (LangGraph, whisper.cpp), 2 rejetés (LlamaIndex,
Open WebUI).

**Quatre constats sur GalSen IA — les quatre sont corrigés** (2026-08-20/22,
PR #34). Ils avaient été consignés comme *suggestions, pas tâches* ; le
propriétaire a demandé de les traiter.
1. ~~`SQLiteVectorStore.search()` **3 388 × plus lent** que le design d'ADR-015.~~
   Matrice en cache, invalidée par un compteur de version écrit **dans la
   transaction de chaque écriture**. Mesuré : 49,4 → 0,463 ms à 271 vecteurs.
2. ~~`Role.USER` atteint `POST /coding/task`, n'importe quel dossier de l'hôte.~~
   Plafond de rôle existant sur les deux routes, **plus**
   `GALSEN_CODING_WORKSPACE_ROOTS` — variable absente = refus total.
3. ~~L'entraînement gardait l'exécution, pas le contenu du jeu de données.~~
   Empreinte SHA-256 du texte inscrite dans la demande, recalculée à l'export.
4. ~~`litellm` installé, non déclaré, non importé.~~ Trois gardes refusent qu'un
   paquet de moteur soit atteignable, déclaré ou importé.

**Zéro ligne de `src/`, zéro dépendance, zéro test touché** sur tout le VOLET
d'audit lui-même — les corrections ci-dessus sont venues après, sur demande.

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
