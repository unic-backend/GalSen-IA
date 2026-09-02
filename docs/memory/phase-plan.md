# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **FUSION ARENA → GALSEN IA**
                   Décision du propriétaire, 2026-08-26
Chapitres        : **8**
Phases           : **12**
Phase courante   : 1.1 — en attente de confirmation
Terminées        : aucune
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Décisions du propriétaire, prises avant ce plan :**

- Les deux projets n'en font plus qu'un. ARENA rejoint GalSen IA, pas l'inverse.
  Motif donné : *« GalSen IA a eu une mauvaise aperçu, je peux pas l'utiliser
  depuis que je l'ai créé ; ARENA, sur 1 jour, je commence à travailler avec. »*
- Le projet unifié **reste public sous Apache-2.0**. Le propriétaire l'a
  explicitement choisi après que la conséquence lui a été présentée : ARENA
  devient donc utilisable par tous. Cela remplace sa décision du 2026-08-26
  matin (« personne ne doit l'utiliser »).

**Contrainte non négociable, et elle n'est pas un choix :**

L'historique Git d'ARENA contient **6 secrets en clair**, et les clés du
propriétaire **ne sont pas encore changées**. Le transfert se fait donc
**fichier par fichier, sans historique**. Aucun `git subtree`, aucun
`git remote add`, aucun merge d'historique. Cette contrainte tombe le jour où
la rotation des clés est faite et vérifiée — pas avant.

---

## Ce qui a été mesuré avant d'écrire ce plan

Un plan écrit de mémoire suppose ; celui-ci a compté. Mesuré le 2026-08-26 :

| Mesure | GalSen IA | ARENA |
|---|---|---|
| Fichiers Python | 958 | 109 |
| Lignes Python | 230 576 | 8 385 |
| Tests | 7 373 | 369 |
| ADR | 39 | 0 |

**Collisions réelles, comptées et non supposées :**

- Agents portant le même nom des deux côtés : **`coder`, `researcher`**
- Dossiers de premier niveau en commun : `agents/ config/ data/ docs/ scripts/
  tests/ tools/` — 7 sur 12
- Fichiers de test homonymes : **`test_sandbox.py`** (un seul)
- Imports racine à réécrire dans ARENA : **43** (`agents.`, `tools.`, `core.`,
  `apps.`)

**Emplacement retenu : `src/arena/`.** GalSen IA place chaque sous-système sous
`src/` (`src/darra_j/`, `src/media/`, `src/live_context/`). ARENA suit la même
règle plutôt que d'en inventer une — `.claude/rules/spec-driven-governance.md`,
*« Existing architecture has priority »*. Cela règle d'un coup les 7 collisions
de dossiers et les 2 collisions d'agents, sans renommer une seule capacité.

---

## Le plan

```
Ch. 01  Sécurité préalable        → 1 phase (indivisible)
Ch. 02  ADR et emplacement        → 1 phase (indivisible)
Ch. 03  Transfert du code         → 3 phases  (3.1 API, 3.2 agents, 3.3 outils)
Ch. 04  Dépendances               → 1 phase (indivisible)
Ch. 05  Tests                     → 2 phases  (5.1 portage, 5.2 passage au vert)
Ch. 06  Interface et services     → 2 phases  (6.1 frontend, 6.2 LibreChat/Docker)
Ch. 07  Documentation et mémoire  → 1 phase (indivisible)
Ch. 08  Validation complète       → 1 phase (indivisible)
```

**Total : 12 phases.**

### Détail

| Phase | Ce qu'elle fait | Comment elle se vérifie |
|---|---|---|
| **1.1** | Scanner les fichiers ARENA à transférer, prouver qu'aucun secret ne part dans un dépôt public | `gitleaks` sur l'arbre de travail → 0 fuite |
| **2.1** | Écrire l'ADR-040bis actant la fusion, l'emplacement `src/arena/`, la licence et l'interdiction d'historique | l'ADR existe, le garde-fou de comptage d'ADR de `CLAUDE.md` passe |
| **3.1** | `apps/backend/` → `src/arena/api/` — config, runtime, security, prompts, rate_limit, 3 routeurs | `python -c "import src.arena.api"` + table des routes figée |
| **3.2** | 13 agents → `src/arena/agents/` | chaque agent s'importe |
| **3.3** | 8 familles d'outils → `src/arena/tools/` | chaque outil s'importe |
| **4.1** | Fusionner `requirements.txt` — 6 dépendances nouvelles côté ARENA | `pip install --dry-run -r requirements.txt` résout |
| **5.1** | 369 tests → `tests/arena/`, `test_sandbox.py` désambiguïsé | pytest les collecte |
| **5.2** | Les faire passer avec les imports GalSen IA | `pytest tests/arena` → 369 passed |
| **6.1** | Frontend ARENA et Media Studio sous l'interface GalSen IA | les pages se chargent hors ligne |
| **6.2** | `librechat.yaml`, Open WebUI, `docker-compose.yml`, `.env.example` | `docker compose config` valide |
| **7.1** | `CLAUDE.md`, `docs/architecture/overview.md`, CHANGELOG, `docs/memory/` | garde-fous de documentation au vert |
| **8.1** | Suite entière des deux projets réunis, ruff, régression | `pytest` → 7 742 attendus, `ruff` → 0 |

### Ce que ce VOLET ne fait pas

- **Aucune capacité n'est réécrite.** ARENA est déplacé, pas refondu.
- **Aucune fusion de code entre capacités jumelles.** Le `coder` d'ARENA et
  celui de GalSen IA coexistent ; les rapprocher est une décision distincte, à
  prendre une fois que l'ensemble tourne.
- **Aucune suppression du dépôt `arena-personal-ai`.** Il reste tel quel jusqu'à
  ce que le propriétaire constate que la fusion fonctionne.
- **La rotation des clés reste due**, et n'est pas dans ce VOLET.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **AUDIT ARCHITECTURE NOYAU LINUX** — 13 chapitres, 18 phases →
   `docs/research/linux-kernel-architecture-audit.md`.
   `SELECTIVE ARCHITECTURAL IMPROVEMENTS RECOMMENDED` : 5 recommandations, aucune
   autorisée, aucune implémentée. **P10 (3 sites d'appel) devient plus urgente
   après ce VOLET.**
2. **REDESIGN CHAT-FIRST** — 8 chapitres, 11 phases. `POST /chat`, `/ui/` sert la
   conversation, `/ui/admin/` le tableau de bord, menu de 14 domaines.
3. **AUDIT #01 `codebase-memory-mcp`** — 16 phases, `KEEP FOR RESEARCH`.
4. **SUPERPOWERS** — **ADR-038**. **OPEN-SOURCE ECOSYSTEM** — **ADR-037**.
5. **OpenClaw** (ADR-034), **DeepSeek Harness** (ADR-035) : non intégrés.
6. **Live Context** (ADR-033), **Creative Canvas** (ADR-031),
   **Research Orchestration** (ADR-032), **MoneyPrinterTurbo** (ADR-030),
   **Apache-2.0** (ADR-036).
7. **CHAT — RÉPONSE FINALE RÉELLE** — 11 chapitres, 19 phases, brief du
   2026-08-23 → `docs/chat/final-response-report.md`, **ADR-039**. Le pipeline
   `/chat` rédige enfin une vraie réponse au lieu de rendre les données brutes
   des agents (« bonjour » : 1 092 → 77 ms). Les 19 phases ✅, 7 148 tests
   passent (44 ajoutés, 0 supprimé), lint vert. Fusionné via la PR #37 avant
   l'ouverture de ce VOLET fusion.
