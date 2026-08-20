# E02.2 — Existing architecture: memory, knowledge, RAG, orchestration, security (§2)

**Measured**: 2026-08-20, by importing and calling the code, not by reading it.

This phase covers the four candidates that propose to replace a *subsystem*
rather than supply a backend: **LangGraph**, **LlamaIndex**, **Qdrant**, and —
for the UI question — **Open WebUI**.

---

## 1. What is actually there, sized

| Subsystem | Modules | Lines | Candidate that targets it |
|---|---:|---:|---|
| `src/knowledge_engine/` | **37** | **10 706** | LlamaIndex |
| `src/model_engine/` | 33 | 7 155 | LiteLLM |
| `src/agent/` | 23 | 6 406 | LangGraph, OpenHands |
| `src/router/` | 16 | 3 017 | LangGraph |
| `src/memory_engine/` | 12 | 2 429 | LlamaIndex |
| `src/security/` | 6 | 1 346 | — |
| `src/embeddings/` | **6** | **925** | **Qdrant** |
| `src/mcp/` | 4 | 652 | — |
| `src/observability/` | 2 | 329 | — |

**The asymmetry is the finding.** The knowledge engine is 10 706 lines; the
vector layer a candidate would replace is **925**. A verdict that treats
"knowledge" and "vector store" as one decision would be wrong by a factor of
eleven.

## 2. Orchestration — LangGraph's headline capability already has a carrier

LangGraph's distinguishing feature is a **checkpointed, resumable graph run**.
Measured here:

```python
src.router.workflow_checkpoint
→ classes: WorkflowCheckpoints, WorkflowRun, StepRecord, RunStatus,
           CheckpointRefused
→ RunStatus: ['running', 'completed', 'failed', 'cancelled']
→ EXECUTIONS_CONSERVEES = 200      REPRISES_MAXIMUM = 3
```

Its module docstring: *"Workflow checkpoints: what a long run remembers, and
**what it refuses to redo**."*

`RouterEngine` composes `AgentLoader`, `AgentDispatcher`, `ExecutionPlanner`,
`ResultAggregator`, `RetryManager`, `ConfigLoader`, `Logger`, and emits
`AuditEventType` / `AuditStatus`. `decision_trace.py` exports `decision_trace`,
`recommended_agents`, `selection_appliquee` — **the routing decision is
inspectable after the fact**, which is the property `/observability/trail/{id}`
depends on.

`ExecutionPlanner` carries a `Set`-based dependency plan over `WorkflowLoader` —
a DAG by another name.

**So the §4C question is not "does GalSen IA have graph orchestration".** It has
one, with resumption, a retry cap, an audit trail and a refusal path. The
question Ch. 04 must answer is narrower and harder: **what does LangGraph do
that `WorkflowCheckpoints` + `ExecutionPlanner` + `decision_trace` do not** —
and is that gap worth a framework that would own the control flow.

## 3. Knowledge — 37 modules, and none of them is a vector store

`src/knowledge_engine/` holds `citations`, `contradictions`, `domains`,
`entities`, `factual_evaluation`, `freshness`, `gaps`, `health_policy`,
`ingestion`, `knowledge_cache`, `knowledge_governance`, `knowledge_graph`,
`knowledge_indexer`, `knowledge_lifecycle`, `knowledge_loader`,
`deferred_triggers`, `collection`, `interfaces` and nineteen more.

Those names are the point. **`contradictions`, `gaps`, `freshness`,
`factual_evaluation`, `citations` and `knowledge_governance` are not retrieval
features** — they are the rules CLAUDE.md states as the knowledge architecture:
nothing enters without a source, `unknown` is not `no`, every report shows its
own gaps, law and administration never fall back to global knowledge.

LlamaIndex supplies ingestion, chunking, indexing and query pipelines. It does
not supply provenance-per-relation, a scope/subject axis, or a domain that
refuses to answer. **Ch. 04-D must therefore compare like with like**: the
overlap is with `ingestion.py` + `knowledge_indexer.py`, not with the engine.

## 4. Retrieval — where the 925 lines actually hurt

From E01, re-stated because it is the load-bearing number of this chapter:

| Vectors | Median | p95 |
|---|---:|---:|
| 271 *(today)* | 70.42 ms | **94.93 ms** |
| 10 000 | 1 943 ms | 2 186 ms |
| 100 000 | **27 944 ms** | 32 473 ms |

`src/embeddings/vector_store.py` re-reads and `json.loads` every line on every
query. **ADR-015 wrote its own reversal condition and both halves are met.**

Two candidates address this and they are not the same proposal:

- **Qdrant** replaces the store — an ANN index, a server, a network hop, a
  persistence format, an operational dependency.
- **A cached matrix** replaces the *loop* — no dependency, no server, and it is
  the baseline Qdrant must beat rather than the alternative to considering it.

Neither is decided here. Ch. 04-D measures the cheap one first, because a
candidate that cannot beat a fix worth twenty lines has not earned a server.

## 5. Security and MCP, since every candidate crosses them

```python
src.mcp.exposure  → OUTILS_EXPOSES, REFUS, expose(), refusal_reason(), report()
src.mcp.client    → PinnedServer, ServerNotPinned, ToolDescription,
                    inspect_description(), MOTIFS_SUSPECTS, MOTIFS_COMMUNS
src.observability → trail(), observability_report(), audit_fragment(),
                    checkpoint_fragment(), routine_fragment(), TROUVE/RIEN/ILLISIBLE
src.integration.degradation → 9 subsystems probed
```

Three properties any candidate inherits rather than negotiates:

1. **A server must be pinned** (`ServerNotPinned`), and tool descriptions are
   inspected for suspicious patterns — external text is data with an origin.
2. **Exposure is an allowlist with a stated refusal reason**, not a filter.
3. **Observability distinguishes `TROUVE` / `RIEN` / `ILLISIBLE`** — found,
   nothing there, and unreadable are three different answers. A candidate that
   collapses them loses information this repository spent programmes protecting.

## 6. What E02.2 refuses to conclude

- **That LangGraph is redundant.** Resumption exists; whether it is *equivalent*
  is unmeasured (`UNKNOWN` until Ch. 04-C).
- **That Qdrant is warranted.** The gap is real and measured; the cheapest fix
  has not been tried, so no candidate has a baseline to beat yet.
- **That LlamaIndex has no place.** Its overlap is with two modules of
  thirty-seven, and that is a `PARTIAL OVERLAP` argument, not a rejection.
- **That size is quality.** 10 706 lines of knowledge engine is a measurement of
  *investment*, not of correctness. Six of sixteen domains still hold nothing.
