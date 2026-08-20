# E03.3 — LangGraph, LlamaIndex, Qdrant (§3, fields A–T)

**Read**: 2026-08-20, licence files from `raw.githubusercontent.com`, package
metadata from `pypi.org`. `api.github.com` → **403**, so popularity is
**`UNKNOWN`**.

These three are the candidates that would touch **orchestration** and
**knowledge** — the two areas where this repository has the most code already,
and where E01 found the one measured weakness of the whole audit.

---

## 6. LangGraph

| Field | Finding |
|---|---|
| **A. Repository status** | **ABSENT.** No declaration, no import, no lockfile entry |
| **B. What it does** | Graph-structured agent orchestration: nodes, edges, conditional branching, persisted state, human-in-the-loop interrupts |
| **C. Official source** | `langchain-ai/langgraph`, PyPI `langgraph` **1.2.11** |
| **D. Licence** | **MIT**, filed. *"Copyright (c) 2024 LangChain, Inc."* |
| **E. Requirements** | Python ≥ 3.10; **6 declared dependencies, all unconditional** — the smallest tree of the twelve after llama.cpp's bindings |
| **F. GPU** | **None** |
| **G. CPU/RAM** | Negligible — it is a control-flow library |
| **H. Runtime** | In-process Python |
| **I. Compatibility** | Python-compatible. **Architecturally it is a second orchestrator** |
| **J. Overlap** | **HIGH OVERLAP.** `src/workflow_engine/` and the agent orchestration already run workflows, and the platform's own claim is that *a routine can fire a workflow through **the one** orchestrator* |
| **K. Advantages** | Explicit graph state and checkpointed resumption are a genuinely different shape from a step list. Its interrupt model is a named pattern for approval gates |
| **L. Disadvantages** | Adopting it wholesale means **two orchestrators**, which §41 of the previous programme and §5 here both forbid. It also pulls the LangChain conceptual vocabulary into a codebase that has its own |
| **M. Security** | Executes whatever a node contains — the risk is the graph author's, not the library's |
| **N. Privacy** | Neutral; checkpointing persists state, and *where* is the question |
| **O. Maintenance** | Low by dependency count, **high by concept count** |
| **P. Performance** | **`UNKNOWN`** |
| **Q. Provider independence** | Neutral — it does not choose models |
| **R. Integration difficulty** | Low to install, **high to justify** |
| **S. Testability** | Good — graphs are deterministic given inputs |
| **T. Recommendation** | **`KEEP_EXISTING`** |

**Why not `DEFER`**: §4C asks whether *concepts* could be adopted without the
framework. That is a real question and it belongs to E04.2. But the *package*
question is settled here: a second orchestrator is not a gap, it is a
duplication, and the directive's final rule is explicit — *"If GALSEN-IA already
performs the job well: KEEP THE EXISTING SYSTEM."*

---

## 7. LlamaIndex

| Field | Finding |
|---|---|
| **A. Repository status** | **ABSENT** |
| **B. What it does** | An ingestion-and-retrieval framework: loaders, node parsers, indices, retrievers, query engines over documents |
| **C. Official source** | `run-llama/llama_index`, PyPI `llama-index` **0.14.24** |
| **D. Licence** | **MIT**, filed. *"Copyright (c) Jerry Liu"* |
| **E. Requirements** | Python ≥ 3.10, < 4.0; **4 declared dependencies** — but they are meta-packages (`llama-index-core` and friends), so the real tree is larger than four |
| **F. GPU** | **None required** |
| **G. CPU/RAM** | Modest for the framework; embedding models are the cost |
| **H. Runtime** | In-process Python |
| **I. Compatibility** | Compatible in language, **colliding in ownership** |
| **J. Overlap** | **HIGH OVERLAP.** `src/knowledge_engine/` holds **37 modules** — ingestion, indexer, retriever, ranker, store, lifecycle, governance, quality, validator, citations, contradictions, gaps, freshness, scope, scoped retrieval |
| **K. Advantages** | Breadth of loaders; a large connector ecosystem this repository does not have |
| **L. Disadvantages** | **It would not respect the two axes.** `scope` and `subject` (ADR-021) are this platform's invention: law, administration and languages **never** fall back to global knowledge. A generic retriever has no such notion, and bolting it on means re-implementing the interesting half anyway |
| **M. Security** | Loaders read files and reach networks; each connector is its own surface |
| **N. Privacy** | Depends entirely on which loaders and which embedding backend |
| **O. Maintenance** | High — a fast-moving framework with a large surface |
| **P. Performance** | **`UNKNOWN`** |
| **Q. Provider independence** | **Negative pressure**: it has its own provider abstraction, which would sit beside `ModelRouter` |
| **R. Integration difficulty** | High, and the difficulty is conceptual rather than technical |
| **S. Testability** | Its own paths are testable; the interaction with provenance is the hard part |
| **T. Recommendation** | **`REJECT`** |

**Why `REJECT` and not `KEEP_EXISTING`**: the two are different verdicts.
`KEEP_EXISTING` says *ours is enough*. `REJECT` says **the candidate would
actively remove a property we have** — here, provenance on every item and the
scope/subject split that makes `UNKNOWN` answerable. That is not a feature
LlamaIndex lacks by accident; it is a different design.

---

## 8. Qdrant

| Field | Finding |
|---|---|
| **A. Repository status** | **ABSENT** |
| **B. What it does** | A vector database: HNSW indexing, payload filtering, hybrid search, persistence, clustering |
| **C. Official source** | `qdrant/qdrant` (server, Rust), PyPI `qdrant-client` **1.19.0** |
| **D. Licence** | **Apache-2.0**, filed — both server and client |
| **E. Requirements** | Client: Python ≥ 3.10, **11 unconditional dependencies**. Server: a Rust binary or a container |
| **F. GPU** | **None required** |
| **G. CPU/RAM** | The server is a separate process with its own footprint |
| **H. Runtime** | A service — HTTP/gRPC — or an embedded local mode |
| **I. Compatibility** | Would enter behind a `VectorStoreProvider` seam |
| **J. Overlap** | **DIRECT DUPLICATE of the storage half**, and **no overlap with the governance half.** `src/knowledge_engine/knowledge_store.py` stores vectors; Qdrant stores vectors better. Nothing in Qdrant knows what a `scope` is |
| **K. Advantages** | **This is the one candidate answering a measured deficiency.** E01 measured the current search: **70 ms median at 271 vectors, 1 943 ms at 10 000, 27 944 ms at 100 000** — because `search()` re-reads and re-parses every line on every query. ADR-015 wrote its own reversal condition, *"~100 000 vectors or a p95 beyond 100 ms"*, and **both halves are met** |
| **L. Disadvantages** | It is a **second datastore** beside SQLite (ADR-005), with its own lifecycle, backup and failure mode. `scripts/backup.py` would no longer capture everything |
| **M. Security** | A network service; default deployments are unauthenticated unless configured |
| **N. Privacy** | Local deployment is possible, so no data need leave the host |
| **O. Maintenance** | Moderate — one more process to run, upgrade and back up |
| **P. Performance** | **`UNKNOWN` for Qdrant itself** — not installed, not measured. **The baseline it would have to beat is measured**, and that asymmetry is the honest state |
| **Q. Provider independence** | **Preserved** if and only if it enters behind an interface that does not exist yet |
| **R. Integration difficulty** | Moderate: a provider seam, a migration path, a fallback when the service is down |
| **S. Testability** | Testable against a container; the fallback path is testable without one |
| **T. Recommendation** | **`DEFER`** |

**Why `DEFER` and not `INTEGRATE`**: the deficiency is real and measured, but
**the cause is not the absence of Qdrant.** The cause is a re-read-and-reparse
loop where ADR-015 assumed an in-memory matrix. A cached matrix is a much
smaller change than a second datastore, and **nobody has measured whether it
closes the gap**. §7's question 3 — *is the existing implementation weaker?* —
cannot be answered against an implementation that was never built as designed.
E04.2 measures that before anyone installs anything.

---

## What E03.3 refuses to conclude

- **That LangGraph has nothing to offer.** Its interrupt-and-resume model is a
  named pattern, and §4C asks about concepts, not packages. E04.2 answers that.
- **That Qdrant is the fix.** It is *a* fix for *a* problem whose cheapest fix
  has not been tried.
- **Anything about relative speed.** Three candidates, zero installed, zero run.
