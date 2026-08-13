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

## Hard Rules
- NEVER commit secrets or `.env` files.
- NEVER push directly to `main`.
- NEVER invent architecture that contradicts existing ADRs.
- ALWAYS update `docs/memory/completed-work.md` and `CHANGELOG.md` after meaningful progress.

## Current Status
*Measured 2026-08-13.* Foundation and core engines are done (ADR-001, ADR-002). Fourteen
engines, **17 agents**, **21 enabled tools**, 76 API routes, 21 ADRs (ADR-020 is `proposed`, not decided) — see
`docs/architecture/overview.md`, which is kept synchronized with the measured state.

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

Open, and depending on someone outside this repository: **C1** (`ollama serve`) gates
generation and semantic retrieval; the base holds **0 Senegalese documents**; the `v0.1.0`
tag has never been pushed and is the single red test in CI.

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
