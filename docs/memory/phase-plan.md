# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **aucun**
Dernier terminé  : **OPEN-SOURCE ECOSYSTEM AUDIT & INTEGRATION**
                   **22 phases sur 22**, plan complet
                   Rapport → `docs/oss-ecosystem/final-report.md`
                   Décision → **ADR-037**
Phase courante   : aucune — le VOLET est clos, en attente du suivant
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente** : `.claude/rules/post-integration-validation.md` — toute
phase se termine par une validation de non-régression complète.

---

## La décision à ne pas re-déduire — ADR-037

**Zéro `INTEGRATE` sur douze.** 3 déjà présents (Transformers, vLLM, OpenHands),
2 atteignables par un seuil existant (SGLang, llama.cpp), 3 différés (LiteLLM,
Qdrant, Unsloth), 2 conservés (LangGraph, whisper.cpp), 2 rejetés (LlamaIndex,
Open WebUI).

**Quatre constats sur GalSen IA, aucun corrigé** — suggestions, pas tâches :
1. `SQLiteVectorStore.search()` est **3 388 × plus lent** que le design d'ADR-015
   (13 132 ms → 3,88 ms à 100 000 vecteurs, 153,6 Mo). Une base de données
   allait être accusée d'un défaut de cache.
2. `Role.USER` atteint `POST /coding/task`, n'importe quel dossier de l'hôte.
   **Latent** : aucun moteur disponible.
3. L'entraînement garde l'exécution (ADR-006), pas le contenu du jeu de données.
4. `litellm==1.81.10` installé, non déclaré, non importé.

**Zéro ligne de `src/`, zéro dépendance, zéro test touché** sur tout le VOLET.

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
