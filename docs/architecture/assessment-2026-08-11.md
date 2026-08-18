# Architecture Assessment — 2026-08-11

Written before the platform-evolution work (VOLETs 26–32) so that the plan builds on what
is measured, not on what is assumed. Method: the repository was inspected, the tool
engine was loaded, the agents were read. Every number below comes from a command run
today, not from memory.

The deployment-side assessment already exists and is not repeated here →
`docs/deployment/audit-2026-08-11.md` and `docs/deployment/production-readiness.md`.

---

## A. What exists, measured

| Area | Size | State |
|---|---|---|
| Model engine | 6 423 lines, 23 modules | Router, selector, cost tracker, health monitor, retry, streaming, token tracking, response ranker/validator, parallel executor. **Substantial and mostly unused: no provider answers.** |
| Tools | 5 522 lines, **20 tools enabled** | filesystem, terminal, git, github, web_search, browser, api, database, model, memory, **rag**, **embeddings**, ocr, pdf, email, calendar, docker, logging, metrics, agri_advice |
| API | 5 124 lines, 66 routes | RBAC, quotas, threat detection, security headers, health/ready/live, metrics |
| Services | 5 188 lines | file, notification, cloud, email, calendar |
| Document intelligence | 3 690 lines | Parsing, extraction |
| Knowledge engine | 3 285 lines | Domains, lifecycle, governance, quality reports — **over 0 items** |
| Storage | 2 999 lines | SQLite per service, encryption at rest, WAL, backup/restore |
| Memory engine | 1 941 lines | Manager, store, retriever, indexer, LRU cache, summarizer, ranking |
| Vision engine | 1 845 lines | OpenCV + Pillow: detection, classification, quality |
| Router (orchestration) | 1 815 lines | Agent loader/dispatcher, execution planner, workflow loader/validator/history, decision trace |
| Agent runtime | 1 610 lines | `BaseAgent`, context, runtime, legacy |
| Agents | 9 × ~200 lines | planner, researcher, coder, reviewer, tester, security, documentation, deployment, monitor |
| Tests | 2 170 passing, 7 skipped | CI on push/PR; release workflow on `v*` |

**This is not an early-stage repository.** The chapters that follow are about closing
gaps in a large existing system, not about building one.

---

## B. Strengths worth preserving

1. **Interfaces before implementations.** `APIRateLimiter`, the storage stores, the model
   providers and the knowledge ranker are abstract, with in-memory implementations behind
   them. Swapping in Redis, Qdrant or Postgres is a new class, not a rewrite. This is the
   single most valuable property of the codebase and every plan below relies on it.
2. **The platform reports what it cannot do.** `/health`, `scaling_report()`,
   `UnavailabilityReason`, `persistent: false` on revocation. The project's rule —
   *an unfinished capability reports a status, it never returns a plausible answer* — is
   applied, not just written.
3. **Decisions are recorded.** 13 ADRs, and they are consulted rather than decorative.
4. **The test suite is real.** 2 170 tests that have repeatedly caught regressions in this
   very session, including ones introduced by the work in flight.

---

## C. Weaknesses, ranked by what they cost

### C1 — Nothing generates text (blocking everything downstream)

The model engine is the largest subsystem in the repository and no provider answers. Exit
criterion **C1** has been open since the beginning. Every phase of the requested roadmap —
agents, RAG, coding agent, model routing — produces *nothing observable* until a model
answers, because each of them ends in a generation call.

**Consequence for the plan:** a provider must answer before agent work is worth doing, or
the work cannot be verified and the project's own rules forbid pretending otherwise.

### C2 — The knowledge base is empty, and the whole RAG stack sits on it

`RAGTool` (725 lines), the knowledge engine (3 285 lines), the search service, the
retrieval ranking, the governance reports: all built, all operating on **0 items**. This
is the largest quantity of code in the repository doing nothing.

### C3 — Retrieval is lexical, not semantic

`MemoryRetriever` scores with **Jaccard similarity on tokens**. `EmbeddingsTool` exists
and is declared enabled, but `sentence-transformers` is **not installed and not declared
in `requirements.txt`** — so the tool reports an error and every retrieval path in the
platform is bag-of-words. For French, Wolof and mixed-language content this is a hard
ceiling, and it is exactly what Phases 3 and 4 of the brief ask to lift.

*(Noted while checking: `tests/test_requirements.py` did not catch this undeclared
dependency, because it maps imports through installed distributions. An undeclared **and**
uninstalled package is invisible to it. That gap is a phase in VOLET 26.)*

### C4 — Two orchestrators, one of them unreachable

`RouterEngine` (exposed at `POST /workflow/run`) and `AgentRuntime` (`src/agent/runtime.py`,
no route) overlap. This was recorded as the fourth duplication of the VOLET series and was
never resolved. **Any agent architecture built now must resolve it first**, or it becomes
the third orchestrator.

### C5 — The agents do not reason

Nine agents of ~200 lines each. Only `planner` and `coder` reference a model at all; the
others are procedural. There is no goal decomposition, no delegation, no inter-agent
communication, no shared working state. The brief's "Agent Manager" does not exist in any
form — `execution_planner.py` sequences a *declared* workflow, it does not plan one.

### C6 — No observability beyond counters

`/metrics` counts requests and latency. There is no per-request trace across
router → agent → tool → model, so a slow or wrong answer cannot be attributed. The moment
agents call agents, this stops being a nice-to-have: a multi-agent system without tracing
is not debuggable, and the brief asks for exactly that system.

### C7 — Multimodal is half-present and unrouted

The vision engine and OCR are real code. There is **no audio path at all** — no Whisper,
no speech-to-text, nothing in `src/` referencing audio beyond file-type declarations. The
document intelligence engine exists but is not wired to knowledge ingestion.

---

## D. Technology evaluation — the brief's candidates

Each was assessed against one question: *does it remove more work than it adds, given what
this repository already has?*

| Candidate | Verdict | Reasoning |
|---|---|---|
| **LangGraph** | **No, not now** | It brings a graph runtime, checkpointing and a state model. This repository already has an execution planner, a retry manager, a workflow validator, a decision trace and a workflow history — 1 815 lines that do most of that. Adopting LangGraph means either rewriting on top of it or running two orchestrators (C4 already has that problem). Its genuinely useful idea — **explicit state passed between nodes, persisted, resumable** — is portable without the dependency. |
| **AutoGen** | **No** | Conversational multi-agent with a heavy Microsoft-ecosystem surface. Its model is agents chatting until consensus, which is expensive in tokens and hard to bound. For a platform whose stated constraint is cost efficiency in African contexts, this is the wrong default. |
| **Qdrant** | **Later, and probably yes** | The right answer *when there is a corpus*. Today the knowledge base holds 0 items; a vector database over nothing is a service to run for no benefit. The decision point is corpus size: SQLite + a NumPy dot-product over a few thousand vectors is faster to deploy and adequate; beyond ~100k vectors it stops being. **NumPy is already a dependency.** |
| **Sentence Transformers** | **Yes** | This is the missing piece of C3, the tool already targets it, and `paraphrase-multilingual-MiniLM-L12-v2` covers French. It runs locally, on CPU, with no API cost — which matches the project's cost constraint better than any hosted embedding API. Cost: ~90 MB of model weights and a PyTorch dependency, which is the real price and must be a deliberate ADR. |
| **Haystack** | **No** | A full RAG framework whose components duplicate the knowledge engine, the document intelligence engine and the search service. Adopting it would orphan 7 000 lines of working code. |
| **Whisper** | **Yes, but last** | The correct choice for speech-to-text, and `faster-whisper` on CPU is viable. It is last because nothing upstream of it is finished. |
| **OpenHands / Aider** | **Study, do not adopt** | Their valuable ideas — a repository map, edit-then-test loops, structured diffs — are patterns, not dependencies. Both assume they *are* the application; this platform already has a tool engine and an approval gate (ADR-006) that a coding agent must go through. |
| **PostgreSQL** | **Not yet** | ADR-005 chose SQLite and the single-instance posture (ADR-013) makes it correct. Postgres becomes right when there are two instances — the same trigger as Redis in ADR-013. |
| **Redis** | **No** — already decided | ADR-013, with the trigger written. |

**The pattern in these verdicts:** this repository's problem is not a lack of frameworks.
It is that large, well-built subsystems have nothing flowing through them. Adding
frameworks makes that worse; connecting what exists makes it better.

---

## E. What the plan must therefore do

In this order, because each step makes the next verifiable:

1. **Make something answer** (a provider), so agent and RAG work can be tested at all.
2. **Resolve the duplicate orchestrator**, before adding an agent layer on top of it.
3. **Make retrieval semantic**, because memory and RAG both depend on it.
4. **Fill the knowledge base**, because RAG over 0 items proves nothing.
5. **Then** build the agent manager, the coding agent and the multimodal paths.

The requested Phase 1 (production engineering) is largely **already done** — CI, tests,
security, logging, Docker, deployment and release engineering were the last four chantiers.
What remains of it is real but narrow: distributed tracing (C6) and the dependency-guard
gap found above. It is folded into VOLET 26 rather than given a volet of its own, because
inventing work to fill a heading is exactly what wastes the time this brief asks to save.
