# O00 — Repository audit: the 27 subsystems of §2

**Measured**: 2026-08-19, against commit `29285b4`.
**Method**: read-only. No file was modified, and **nothing about OpenClaw was
researched** — §3 belongs to O01.

Every verdict below is **VERIFIED FROM REPOSITORY**: it names the path that
proves it. Where a path exists but its behaviour was not exercised in this
phase, the verdict says so rather than inflating to `EXISTING`.

Vocabulary is §2's own: `EXISTING` · `PARTIAL` · `MISSING` · `DUPLICATE` ·
`UNKNOWN`.

---

## O00.1 — subsystems 1 to 14

| # | Subsystem | Verdict | Proof |
|---|---|---|---|
| 1 | Orchestrator | `EXISTING` | `src/router/router_engine.py` + 15 sibling modules (`execution_planner`, `result_aggregator`, `retry_manager`, `decision_trace`, `output_validation`, `workflow_checkpoint/history/loader/validator`) |
| 2 | Agents | `EXISTING` | `agents/registry.yaml` — **17 agents** declared, each with a directory under `agents/` |
| 3 | Agent runtime | `EXISTING` | `src/agent/runtime.py` (`AgentRuntime.execute_task`), plus `base_agent`, `context`, `blackboard`, `health`, `legacy` |
| 4 | Tools | `EXISTING` | `tools/tools.yaml` — **24 declared**; **23 implemented packages** under `src/tools/`; engine at `src/tool/` (`tool_engine`, `tool_loader`, `tool_executor`, `capabilities`, `authorization`) |
| 5 | Skills | `PARTIAL` | `src/media/skills/registry.py` exists and is **scoped to the media engine**. There is no platform-wide skill system. Promotion requires a named validator and refuses the platform's own identity |
| 6 | Plugins | `EXISTING` | `src/plugins/` — `contract`, `manifest`, `registry`, `execution`, `review` |
| 7 | Workflows | `EXISTING` | `workflows/workflows.yaml` — **8 workflows**; loader and validator in `src/router/` |
| 8 | Task execution | `EXISTING` | `AgentRuntime.execute_task`, and **two orchestration paths only** — `src/router/orchestration_paths.py` states them: a person (`POST /process`) and a routine (`POST /routines/tick`), running the *same* engine |
| 9 | Memory | `EXISTING` | `src/memory_engine/` — 11 modules (manager, store, retriever, indexer, cache, ranker, summarizer, quality, layers) |
| 10 | Sessions | `EXISTING` | `src/auth/session_manager.py` for identity; `src/agent/context.py` and `MemoryItem.session_id` for execution context |
| 11 | Queues | `PARTIAL` | `src/media/queue/jobs.py` (`RenderQueue`) is **media-scoped**. No platform-wide queue |
| 12 | Jobs | `PARTIAL` | `RenderJob` (media) and `CreativeJob` / `CreativeJobBook` (`src/creative/jobs.py`) — **two job vocabularies, both engine-scoped**. Candidate `DUPLICATE`, recorded rather than resolved |
| 13 | Model routing | `EXISTING` | `src/model_engine/model_router.py`, `routing_policy.py`, `provider_selector.py`, and the policy **externalised to `config/model_routing.yaml`** (ADR-014) |
| 14 | Provider abstraction | `EXISTING` | `src/model_engine/providers/` — `base.py` plus anthropic, google, openai, openai_compatible, hosted, local, `provider_registry.py`, `derogations.py` (ADR-018) |

---

## O00.2 — subsystems 15 to 27

| # | Subsystem | Verdict | Proof |
|---|---|---|---|
| 15 | Security | `EXISTING` | `src/security/` — `trust.py` (the external-data boundary), `isolation.py`, `posture.py`, `redaction.py`, `checkpoints.py` |
| 16 | Authentication | `EXISTING` | `src/auth/` — `jwt_handler`, `oauth_providers`, `session_manager`, `user_manager`, `protection` (ADR-029) |
| 17 | Authorization | `EXISTING` | `src/api/rbac.py` (roles and permissions) + `src/tool/authorization.py` (per-tool ceiling by role and effect, with `REQUIRES_APPROVAL` as a third answer) |
| 18 | Sandboxing | `EXISTING` | `src/sandbox/policy.py` + `runner.py`. **Declares its own limits before its code**, and ships with escape tests (`tests/test_sandbox.py`) — ADR-017 §5 |
| 19 | Self-healing | `EXISTING` | `src/agent/self_healer.py` — `GalSenSelfHealer`, `Diagnosis`, `PatchContext` |
| 20 | Provenance | `EXISTING` | `src/acquisition/` — `record`, `metadata`, `manifest`, `gate`, `quality`, `parsing`; plus `src/audit_engine/` (`AuditEvent`, nine required fields) |
| 21 | Observability | `EXISTING` | `src/observability/trail.py` (a job followable end to end via `/observability/trail/{id}`), `src/api/metrics.py`, `tracing.py` |
| 22 | API | `EXISTING` | `src/api/server.py` — **143 route decorators**, plus rate limiting, security headers, threat detection, versioning, trusted proxies, scaling, instance lock |
| 23 | Frontend | `PARTIAL` | `src/web/static/` — `index.html`, `studio.html`, `css/`, `js/`. Two pages, no framework, no build step |
| 24 | Backend | `EXISTING` | 43 packages under `src/`; storage layer at `src/storage/` with SQLite stores for approvals, audit, users, knowledge, models, files, entities, notifications, calendar, email (ADR-005) |
| 25 | Tests | `EXISTING` | **332 test files**, **6 971 tests collected** (3 deselected). Guard tests exist over the repository's own published numbers (`tests/test_published_numbers.py`) and lint (`tests/test_lint.py`) |
| 26 | Deployment | `EXISTING` | `Dockerfile`, `docker-compose.yml`, `.github/workflows/tests.yml` and `release.yml` |
| 27 | Configuration | `EXISTING` | `config/` — `settings.yaml`, `model_routing.yaml`, `connectors/`, `notifications/`, `oauth/`; `src/config/environment.py` reads **18 `GALSEN_*` variables** |

---

## Counts, measured

| | |
|---|---|
| Packages under `src/` | **43** |
| Agents declared | **17** |
| Tools declared / implemented | **24 / 23** |
| Workflows | **8** |
| API route decorators | **143** |
| Test files / tests collected | **332 / 6 971** |
| Orchestration paths | **2**, and they run the same engine |

---

## The finding that changes this programme

**This repository already contains an OpenClaw analysis, and an ADR partly
informed by it.**

`docs/architecture/agent-foundations-comparison.md` — VOLET 34, phase 2.1,
header dated **researched on the web on 2026-08-12** — devotes section 3 to
OpenClaw, and `docs/architecture/decisions/017-computer-agent-is-tools-not-a-new-architecture.md`
cites it in its decision 5. `src/sandbox/policy.py` and `tests/test_sandbox.py`
carry the same reference **in their own docstrings**.

Two consequences, and they pull in opposite directions.

**It is not a shortcut.** That analysis is seven days old and §3 says *do not
rely on old information* and names official sources as the primary authority. A
claim inside this repository is **not** an official source — it is a prior
reading by this same project. O01 must therefore verify everything from official
sources and, where it cannot, record `UNKNOWN` with the exact failure. The
existing text is classified here as **VERIFIED FROM REPOSITORY (that the text
exists)** and its *content* as **UNVERIFIED pending O01**.

**But it does establish repository facts that O00 legitimately reports**, because
they are decisions this project already took:

- **ADR-017 already decided that a computer-using agent is "tools, not a new
  architecture."** That decision constrains what an OpenClaw adapter could be
  before this directive's §6 says anything.
- **ADR-017 §5 already imposes the rule an integration would have to meet**:
  *no new execution power ships without its escape test*, and the repository
  states the rule was learnt from OpenClaw's published escape literature.
- The comparison document already identifies what this repository **lacks** and
  attributes the idea to OpenClaw: *the trusted / constrained session
  distinction — a task today inherits the caller's permissions whole.*

That last line is the single most useful input O00 can hand to O02's duplication
matrix, and it is a repository fact rather than a claim about OpenClaw.

---

## Candidate duplications recorded, not resolved

O00 records these; §5's matrix (O02) decides them.

1. **Two job vocabularies** — `RenderJob` (media) and `CreativeJob` (creative).
   Both engine-scoped, no platform-wide job.
2. **Two retry managers** — `src/router/retry_manager.py` and
   `src/model_engine/retry_manager.py`. Same name, different layers; whether
   that is duplication or correct layering was **not** determined in this phase.
3. **Skills exist only inside the media engine.** A platform-wide skill system
   is `MISSING`, and this is the first place an external runtime could plausibly
   add something rather than duplicate.

---

## What O00 did not determine

- Whether the `PARTIAL` verdicts (skills, queues, jobs, frontend) are gaps or
  deliberate scoping. Naming them is O00's job; judging them is O02's.
- Whether the two retry managers overlap in behaviour. Reading both was outside
  this phase and is recorded rather than guessed.
- **Anything at all about OpenClaw's current state.** `UNKNOWN` until O01.
