# GalSen IA — Claude Code Context

## Project
GalSen IA is a long-term AI platform starting in Senegal, expanding to Africa, then globally.  
Focus: practical AI agents, data platforms, and tools for African contexts first.

**Languages**
- User-facing explanations & code comments → French
- Technical documentation → English
- File & folder names → English
- Commit messages → English
- Prompt files → English

## Critical Behavior (MUST follow)
- ALWAYS answer the user in French, even if the user writes in English.
- Write all code comments in French.
- Before any architectural or priority decision → read `docs/memory/` files first.
- Prefer reusing existing architecture over creating new patterns.
- Never duplicate documentation. Update the existing file instead.
- Keep answers under 8 lines by default → `.claude/rules/response-style.md`.
- **One phase per turn. Never two, never a whole chapter** → `.claude/rules/phase-protocol.md`.
  Opening a VOLET starts with a phase plan (chapters → phases) and nothing else.
  Every phase ends with `Je continue ?` and waits for an explicit confirmation.
- Work in phases of ≤ 8 min; at 25 min elapsed, stop and ask → `.claude/rules/work-cadence.md`.
- Ask for clarification when requirements are ambiguous.
- Never call work done without running it → `.claude/rules/verification.md`.
- **Implement only what was requested** → `.claude/rules/spec-driven-governance.md`.
  A possible improvement is not a requirement; an optional suggestion never becomes a task.
- After completing significant work → update `docs/memory/` and `docs/changelog/CHANGELOG.md` following `.claude/rules/memory.md`.

## Memory System (consult first)
Read/write protocol → `.claude/rules/memory.md`

`docs/memory/session-state.md` is injected automatically at session start by the
`SessionStart` hook (`scripts/session_bootstrap.py`) — it already tells you where the
last session stopped. Keep it up to date; it is the project's continuity.

| File | Purpose |
|------|---------|
| `docs/memory/phase-plan.md` | The VOLET's phase plan and the one pending phase — auto-loaded |
| `docs/memory/session-state.md` | Where the last session stopped — auto-loaded |
| `docs/memory/priorities.md` | Current ranking of work — read first |
| `docs/memory/current-objectives.md` | Active goals |
| `docs/memory/pending-work.md` | Backlog |
| `docs/memory/vision.md` | Long-term vision & principles |
| `docs/memory/knowledge-index.md` | Index of domain knowledge |
| `docs/memory/multi-platform-directive.md` | Platform coverage constraints |
| `docs/memory/completed-work.md` | Append-only log — search it, never read it whole |

## Architecture & Decisions
- High-level: `docs/architecture/overview.md`
- All technical decisions: `docs/architecture/decisions/` (ADR format)

## Standards (load on demand)
- Phase protocol → `.claude/rules/phase-protocol.md`
- Memory → `.claude/rules/memory.md`
- Answer style → `.claude/rules/response-style.md`
- Work cadence & token economy → `.claude/rules/work-cadence.md`
- Verification & definition of done → `.claude/rules/verification.md`
- Coding → `.claude/rules/coding-conventions.md` + `docs/standards/coding.md`
- Security → `.claude/rules/security.md`
- Documentation → `.claude/rules/documentation.md`
- Prompts → `.claude/rules/prompts.md`
- Git → `.claude/rules/git-workflow.md`
- Testing → `.claude/rules/testing.md`
- Post-integration validation → `.claude/rules/post-integration-validation.md`
- Spec-driven governance & scope → `.claude/rules/spec-driven-governance.md`
- Spec Kit constitution (pointers only) → `.specify/memory/constitution.md`

## Hard Rules
- NEVER commit secrets or `.env` files.
- NEVER push directly to `main`.
- NEVER invent architecture that contradicts existing ADRs.
- ALWAYS update `docs/memory/completed-work.md` and `CHANGELOG.md` after meaningful progress.

## Current Status
*Measured 2026-08-17.* Foundation and core engines are done (ADR-001, ADR-002). Fifteen
engines **plus nine subsystems probed after the registry** (volets 47–64, probed by
`src/integration/degradation.py`), **17 agents**, **24 declared tools** (13 runnable
unattended), **143 API routes**, 41 ADRs (ADR-020 is `proposed`; ADR-024 to ADR-027 open the creative programme;
ADR-023 and ADR-028 add the interop and coding layers; ADR-030 and ADR-031 close the provider
and canvas programmes; ADR-032 opens the research layer;
ADR-033 opens the live-context layer; **ADR-034 audits OpenClaw and does not integrate it**;
**ADR-035 places DeepSeek Harness as a fourth coding backend, implementation not yet authorized**;
**ADR-036 licenses the platform under Apache-2.0** — it had no licence file at all;
**ADR-037 audits twelve open-source projects and integrates none of them**;
**ADR-038 adopts six Superpowers concepts as prose and installs nothing**;
**ADR-040 makes a local model declare what it can do, and say where that is known from** —
the router selected nothing before it, it took the first model in the list) — see
`docs/architecture/overview.md`, kept synchronized with the measured state.
**7148 tests pass**, 9 skipped, 3 deselected — *measured 2026-08-23*. The `v0.1.0` tag test passes only where
the tag exists locally; the tag has never been pushed, so it fails in CI and on `main` alike.

Unattended work is real: a routine can fire a workflow through the one orchestrator, and
**an approval is never granted by the absence of someone to refuse it**. One job is
followable end to end (`/observability/trail/{id}`), and
`python scripts/demonstration.py` runs the whole chain and reports what actually
happened — 5 steps `OK`, 2 `NOT_CONFIGURED`, 0 failed.

Persistence is decided and implemented (ADR-005, SQLite): every engine holding state —
audit and approval included — selects its store through `GALSEN_STORAGE_BACKEND`
(`in-memory` by default, `sqlite` to persist) and `GALSEN_DATA_DIR`.

**The knowledge architecture is where the design lives now** (VOLETs 35 and 36, see the
overview's *Knowledge architecture* section). Its rules are worth knowing before touching
`src/knowledge_engine/`:

- Two axes on every item: **scope** (where it holds) and **subject** (what it is about).
  Law, administration and languages **never** fall back to global knowledge.
- Reliability comes from `corpus/sources/senegal.yaml`, not from the document claiming it.
- Nothing enters without a source; entities *and* relations carry their own provenance.
- External text is **data with an origin**, never an instruction (`src/security/trust.py`).
- `unknown` is not `no`, and every report shows its own gaps.

## Acquisition and Senegalese knowledge (ADR-021)

A gated acquisition path now exists end to end (`src/acquisition/`,
`docs/architecture/senegal-knowledge-acquisition.md`): registry → discovery → decision →
**batch human approval** → polite fetch → trust boundary → ten quality checks → a `DRAFT`
manifest proposal. It ingests nothing on its own, and **no source is enabled**, so it can
reach nothing today. That is the rule working, not a failure.

Three knowledge layers are built and measured:

| Layer | State |
|---|---|
| Wolof (`src/wolof/`, `src/services/wolof/`) | **2105 sentences**, CLAD orthography, ë/ñ/ŋ preserved |
| Senegalese administration (`src/services/senegal/`) | **14 regions, 45 departments** derived from geoBoundaries — never written from memory |
| Sector knowledge | **8 datasets, 212 objects, 271 chunks, 100 % with provenance** |

**6 of 16 domains are populated.** The other ten carry the reason they are empty; the
retrieval answers `UNKNOWN` for them rather than the least-bad fragment. Queries work in
French, Wolof and English (`corpus/languages/aliases.yaml`, 16 concepts, 115 terms) at
0.1–0.5 ms.

Open, and depending on someone outside this repository: **C1** (`ollama serve`) gates
generation and semantic retrieval; **the nine Senegalese institutional domains are refused
by this environment's proxy** (`CONNECT → 403`, measured — not a site refusal), so
history, culture, agriculture, health, education and law hold nothing; the `v0.1.0` tag
has never been pushed and is the single red test in CI.

## Darra J — educational intelligence (ADR-021 discipline, `src/darra_j/`)

Twenty volets, 28 phases, 21 modules, 377 tests. Full report →
`docs/darra-j/final-report.md`.

**The state is `ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING`**, and
`readiness()` measures the register to say it — no flag reaches "ready to serve"
without a `TIER_A` published version, and a register holding only fixtures
reports zero official versions. **No Senegalese curriculum has been integrated:**
none was available, and none was written from model memory.

Rules worth knowing before touching `src/darra_j/`:

- **No canonical record → the model is not called** (`firewall.py`). Not
  labelled, not discouraged: not called. The evaluation lab measures it on an
  instrumented generator.
- Resolution is by **coordinates**, never similarity; incomplete coordinates
  answer `CLARIFICATION_REQUIRED`.
- Official fields are returned **verbatim and untranslated**. The question
  travels through the alias table; the record never does.
- Publishing requires a **named decider** who is not the platform
  (`is_platform_identity`), and a replaced version becomes `SUPERSEDED`.
- Learner data needs **permission *and* a declared link** (`access.py`,
  `privacy.py`). No permission exists for an unlinked learner. Six education
  roles live in `src/api/rbac.py`; `PERMISSIONS_HORS_PLATEFORME` keeps
  publishing and learner reads out of every platform role, admin included.
- `INSUFFICIENT_EVIDENCE` is **off the mastery scale**, never a low level, and a
  rate over zero cases is `NOT_MEASURABLE`, never 100 %.

## Live context — `src/live_context/` (ADR-033)

Sixteen volets, 27 phases, 16 modules, 376 tests. Full report →
`docs/live-context/final-report.md`.

**The state is computed, never written**: `readiness()` walks the chain and
answers `REPRESENTATION READY — NO LIVE PERCEPTION ON THIS MACHINE, 5 STAGE(S)
NOT IMPLEMENTED, 2 BLOCKED` — 9 `READY`, 2 `BLOCKED`, 5 `ABSENT`. The split is
total: every representation stage runs, no perception stage does. **Nothing can
be captured here**, and the engine says so instead of simulating a session.

Rules worth knowing before touching `src/live_context/`:

- **`ABSENT` is not `UNKNOWN`.** One is measured and will not change by
  waiting; the other is waiting for a measurement. An absence without its
  finding is refused — saying "absent" without saying *how* is a supposition.
- **Fusion records conflicts and resolves none.** Two providers disagreeing
  produce two observations and a recorded conflict, never an average. Nothing
  is promoted, and corroborated values are never ranked by voice count.
- **No speaker is numbered**, and **a channel is not a speaker**: an identity
  derived from a channel is `DECLARED`, never `MEASURED`.
- **Zero does not exist where nothing was counted**: `turns`, `switch_count`,
  `speaker_count` and every §33 latency are `None`, never `0`.
- **Consent is necessary, never sufficient.** ADR-018's unconditional refusals
  are evaluated *before* consent — a scope permitting `upload` still cannot
  send screen content off the machine.
- **Nothing observed in a session is a request.** The creative link stops at
  `offer()` and exposes no function that accepts.
- Screen content, speech and tool results enter at `EXTERNAL`; the caller
  cannot choose the level.

`golden.run_all()` runs the thirty §35 scenarios: 24 `VERIFIED`, 6 `BLOCKED`,
0 failed. `BLOCKED` asserts that the platform reports its own incapacity.

## Media engine — `src/media/`, and its studio

Twenty volets, 32 phases, 26 modules, 483 tests. Full report →
`docs/media/final-report.md`. Eight `/media` routes and a Media Studio at
`/ui/studio.html`.

**The state is computed, never written**: `src/media/readiness.py` walks the
seventeen stages of the production chain and answers `ENGINE READY — MEDIA
RUNTIME DEPENDENCIES PENDING, 1 STAGE(S) NOT IMPLEMENTED (VOICE)` — 10 `READY`,
6 `BLOCKED`, 1 `ABSENT`. **Speech synthesis does not exist here** and is
reported `ABSENT`, not as a missing dependency: no installation produces it.

Rules worth knowing before touching `src/media/`:

- **A capability is measured by interrogating the tool**, never by checking a
  binary exists. This machine's `ffmpeg` is built `--disable-everything` and
  answers `-version` like a full one; `frame_encode` is nonetheless `AVAILABLE`
  and was verified **by writing a real WebM**.
- An unavailable capability **reports its state**; it never returns a plausible
  result. No default duration, no invented transcript, no `0` for a benchmark
  that did not run.
- **A `Selection` has no time field.** A model says what to keep; the measured
  word timings decide where the cut lands. After a render the result is
  re-transcribed and compared — no re-transcription means `NOT_VERIFIED`.
- Reframing **repositions**, it never crops, and the cost of the crop it refuses
  is measured beside it. A language version copies the master timing exactly.
- Three QC outcomes, never two: `PASS`, `FAIL`, `NOT_CHECKED`.
  `PRODUCTION_SUCCESS` needs everything applicable passed **and** nothing
  unchecked.
- Progress is `done / total` of a counted unit; an unknown total is `None`.
- `media` and `media_generation` are **two** tool declarations: the second
  carries the external effect, so it requires a human.

## Cerveau Local (nouveau)
Le projet a maintenant un **Cerveau local** qui connecte les engines GalSen IA à Ollama.

| Composant | Détail |
|-----------|--------|
| **Serveur REST** | `serveur_cerveau.py` — FastAPI sur port 8000 |
| **Modèle local** | `qwen2.5-coder:14b` via Ollama (localhost:11434) |
| **Lanceur** | `Lancer_Claude_Gratuit.bat` — démarre le serveur puis Claude Code |
| **Prompts** | `prompts/systeme.md` — instruction système pour le Cerveau |
| **Mémorial** | `memorial.md` — description complète du projet pour un agent froid |

### Pour démarrer le Cerveau
- `Lancer_Claude_Gratuit.bat`
- API REST : `http://localhost:8000`
- Documentation API : `http://localhost:8000/docs`
- Endpoints : `/health`, `/chat`, `/engines`, `/models`, `/reinitialiser`

Le Cerveau est conçu pour fonctionner **même si certains engines sont indisponibles**
— chaque engine est chargé dans un `try/except`, et l'état est rapporté via `/health`.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes_tool` or `query_graph_tool` instead of Grep
- **Understanding impact**: `get_impact_radius_tool` instead of manually tracing imports
- **Code review**: `detect_changes_tool` + `get_review_context_tool` instead of reading entire files
- **Finding relationships**: `query_graph_tool` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview_tool` + `list_communities_tool`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes_tool` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context_tool` | Need source snippets for review — token-efficient |
| `get_impact_radius_tool` | Understanding blast radius of a change |
| `get_affected_flows_tool` | Finding which execution paths are impacted |
| `query_graph_tool` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes_tool` | Finding functions/classes by name or keyword |
| `get_architecture_overview_tool` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes_tool` for code review.
3. Use `get_affected_flows_tool` to understand impact.
4. Use `query_graph_tool` pattern="tests_for" to check coverage.
# CONTINUOUS EXECUTION & CONTEXT MANAGEMENT

GALSEN-IA est un projet de longue durée.

Lorsque tu travailles sur une tâche ou une phase :

1. Analyse d'abord le périmètre.
2. Travaille de manière autonome.
3. Si le contexte devient trop volumineux, utilise correctement la
   compression/résumé du contexte disponible.
4. Après compression, reprends exactement au dernier état connu.
5. Ne recommence pas inutilement les analyses déjà terminées.
6. Conserve un état de progression compact et persistant pour les
   longues tâches.

À chaque phase terminée :

- vérifier le résultat ;
- exécuter les tests pertinents ;
- corriger les problèmes détectés ;
- mettre à jour l'état/progression ;
- passer automatiquement à la phase suivante lorsque cela est prévu.

NE PAS demander une confirmation simplement parce qu'une phase est
terminée.

NE PAS afficher inutilement tout le contexte précédent.

NE PAS relire massivement les mêmes fichiers après une compression
de contexte.

Avant toute nouvelle lecture importante, vérifier si l'information
existe déjà dans l'état de travail ou dans les fichiers de suivi.

Créer/maintenir un état compact du travail, par exemple :

docs/WORK_STATE.md

Ce fichier doit contenir uniquement :

- phase actuelle ;
- phases terminées ;
- modifications réalisées ;
- tests réalisés ;
- problèmes connus ;
- prochaines étapes ;
- décisions importantes ;
- fichiers importants concernés.

Il doit rester court et être mis à jour après chaque étape majeure.

IMPORTANT :

Une compression de contexte ne signifie PAS que le projet doit
recommencer.

Après récupération du contexte :

WORK_STATE.md + git diff + git status + résultats des tests
doivent servir de source de reprise.

OBJECTIF :

Permettre à Claude Code de travailler sur GALSEN-IA pendant de
longues sessions sans perdre la progression, sans boucler et sans
recommencer inutilement le travail.