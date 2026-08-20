# E04.2 — §4C orchestration, §4D knowledge and RAG

**Written**: 2026-08-20. §4D carries the one **experiment** of this programme:
the cheaper fix that E03.3 said nobody had tried was tried here, and it settles
the Qdrant question.

---

## §4D — LlamaIndex and Qdrant against the existing knowledge architecture

### The measurement, run today

E01 measured that `SQLiteVectorStore.search()` re-reads every row and calls
`json.loads` per row on **every query**, because ADR-015's premise — *"une
matrice en mémoire"* — is not what the code does. E03.3 said the cheaper fix had
never been measured. It has now.

**Method**: the same store, the same data, the same cosine. The only difference
is that the matrix is built once instead of per query. Nothing in `src/` was
changed; the benchmark lives outside the repository.

| Vectors | Current `search()` median | **Cached matrix median** | Factor | Matrix RAM |
|---:|---:|---:|---:|---:|
| 10 000 | 1 232 ms | **0.37 ms** | **3 360 ×** | 15.4 MB |
| 100 000 | 13 132 ms | **3.88 ms** | **3 388 ×** | 153.6 MB |

Cache construction costs one pass — 1.2 s at 10 000, 13.7 s at 100 000 — paid
once, not per query.

*(E01's run of the same current path reported 1 943 ms and 27 944 ms medians
against 1 232 ms and 13 132 ms here. Two runs on a shared 4-CPU host vary by
about a factor of two. **The conclusion does not depend on which run is right**:
both are three to four orders of magnitude above the cached path.)*

### What that settles

ADR-015 set its own reversal condition: *"~100 000 vectors, or a p95 beyond
100 ms."* At 100 000 vectors the cached path answers in **3.88 ms**, with a
worst case of 5.99 ms across the sample.

**The deficiency is real and the diagnosis was wrong.** It was never a vector-
database problem. It is a caching bug against a design that already specified
the cache — and a database was about to be blamed for it.

### Qdrant — verdict unchanged, and now for a stated reason

**`DEFER`.** §7's question 3 asks whether the existing implementation is weaker.
Against the code as written, yes, by three thousand times. **Against the code as
designed, the gap disappears.** Installing a second datastore — with its own
process, backup path outside `scripts/backup.py`, and failure mode — to solve a
problem a cache solves in-process would be the opposite of the directive's final
rule.

What would genuinely reopen Qdrant: **filtered** search at scale (payload
filters over millions of vectors), or a working set that no longer fits in RAM.
153.6 MB at 100 000 says that point is far away. Neither condition holds today,
and neither is invented here to justify a later decision.

### LlamaIndex — `REJECT`, restated at the architectural level

`src/knowledge_engine/` holds **37 modules**. The ones that matter for this
question are not the retriever — any framework has a retriever — but
`scope.py`, `scoped_retrieval.py`, `citations.py`, `contradictions.py`,
`gaps.py`, `freshness.py`, `knowledge_governance.py`.

The platform's rule, from ADR-021: **law, administration and languages never
fall back to global knowledge**, and the retrieval answers `UNKNOWN` for an
unpopulated domain rather than the least-bad fragment. **Ten of sixteen domains
carry the reason they are empty.**

A generic retriever ranks by similarity and returns the best available match.
Applied to an empty domain, *"the best available match"* is exactly the wrong
answer, and it is the answer this architecture was built to refuse. Adopting
LlamaIndex would mean re-implementing scope, provenance and the `UNKNOWN` path
on top of it — which is the interesting half — while inheriting a second
provider abstraction beside `ModelRouter`.

**No overlap is missing that matters. The overlap that exists is the boring
half.**

---

## §4C — LangGraph against the existing orchestrator

### What each side actually has

| | GalSen IA | LangGraph |
|---|---|---|
| Unit of work | workflow steps, jobs, routines | graph nodes and edges |
| Branching | conditional steps | conditional edges, first-class |
| State | job/workflow state, persisted per ADR-005 | a typed state object threaded through nodes |
| Resume | job orchestration | **checkpointed resumption**, first-class |
| Human gate | **`ApprovalManager`** — ADR-006, and *"an approval is never granted by the absence of someone to refuse it"* | `interrupt`, a pause the caller resumes |
| Audit | `AuditEvent`, `request_id` carried end to end, `/observability/trail/{id}` | not its concern |
| Dependencies | — | **6, all unconditional** |

### The question §4C actually asks

*"whether selected concepts could be adopted without importing the entire
framework."*

**The package: no.** A second orchestrator is a duplication, and the platform's
own claim is that a routine fires a workflow through **the one** orchestrator.
`KEEP_EXISTING`, as E03.3 recorded.

**The concepts: one is worth naming, and it is not the one that looks obvious.**

- **Conditional branching** — already present.
- **Typed state through a graph** — a shape difference, not a capability
  difference. Adopting it would be a rewrite for aesthetics.
- **Checkpointed resumption** — the platform persists job state (ADR-005). The
  difference is granularity, and nothing has demonstrated the finer grain is
  needed.
- **`interrupt` / resume as the *same* mechanism as approval** — **this one is
  worth noting.** In LangGraph, a pause for a human and a pause for anything
  else are one mechanism. Here, `ApprovalManager` is a distinct subsystem with
  its own storage and its own rule about absence. Those are two designs, and
  **ours is the stricter one**: an approval that is merely *a paused graph* is
  granted by resuming, whereas ADR-006 requires someone to actually decide.

**So the concept most worth borrowing is the one this repository should
deliberately not borrow**, and knowing why is the output of §4C.

### Recommendation

**`KEEP_EXISTING`**, with no concept adopted. Not because nothing was found, but
because what was found is a weaker guarantee wearing a nicer interface.

---

## What E04.2 refuses to conclude

- **That the cache should be implemented.** It was **measured**, not written.
  §12 forbids implementation, and the measurement belongs to the audit, not the
  fix. `src/embeddings/vector_store.py` is untouched.
- **That Qdrant is never right.** Two conditions would reopen it, both named,
  neither true today.
- **That LangGraph is worse.** It is different, and one of its differences is a
  guarantee this platform holds more strictly.
- **That the 3 388× figure is a promise.** It is a measurement of a benchmark on
  a 4-CPU host, with the run-to-run variance stated. What it establishes is an
  order of magnitude, not a service level.
