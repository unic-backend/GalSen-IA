# E05 — Duplication matrix (§5)

**Built**: 2026-08-20, from what E01–E04 measured. No new claim enters here;
this chapter's job is to put twelve findings on one axis and apply §5's rule.

§5's rule, quoted: *"If DIRECT DUPLICATE: DO NOT INSTALL IT. If PARTIAL
OVERLAP: determine whether complementary integration is possible."*

---

## The matrix

| # | Capability | Existing GalSen IA | Candidate | Overlap | Decision |
|---|---|---|---|---|---|
| 1 | Model definition / weights loading | `scripts/training/train_adapter.py` imports it | **Transformers** | **PARTIAL** — training only, nothing in `src/` | `ALREADY_PRESENT` |
| 2 | High-throughput GPU serving | `openai_compatible_provider.py` (the *client*) | **vLLM** | **NO OVERLAP** — it is a backend below the seam | `ALREADY_PRESENT` |
| 3 | Structured / prefix-cached serving | same client, same seam | **SGLang** | **NO OVERLAP** | `OPTIONAL` |
| 4 | CPU-first quantized inference | `local_provider.py` → Ollama, **which is built on it** | **llama.cpp** | **PARTIAL**, one layer down and unnamed | `OPTIONAL` |
| 5 | Provider abstraction, routing, fallback | `src/model_engine/`, 33 modules, `FailoverModelRouter` (3 / 300 s), policy in `config/model_routing.yaml` | **LiteLLM** | **HIGH** | `DEFER` — and **outside** if ever |
| 6 | Workflow / agent orchestration | the one orchestrator; `ApprovalManager` (ADR-006) | **LangGraph** | **HIGH** | `KEEP_EXISTING` |
| 7 | RAG framework, retrieval | `src/knowledge_engine/`, 37 modules — scope, citations, contradictions, gaps, freshness, governance | **LlamaIndex** | **HIGH** | `REJECT` |
| 8 | Vector storage and search | `src/embeddings/vector_store.py` (SQLite + numpy) | **Qdrant** | **PARTIAL** | `DEFER` |
| 9 | Autonomous coding agent | `openhands_adapter.py`, **one of three declared adapters** | **OpenHands** | **DIRECT DUPLICATE** — of a seam built for it | `ALREADY_PRESENT` |
| 10 | Memory-efficient fine-tuning | `scripts/training/train_adapter.py` — QLoRA, ADR-006 gate, lineage | **Unsloth** | **PARTIAL** | `DEFER` |
| 11 | Local speech recognition | `src/multimodal/whisper_provider.py` + `faster-whisper` | **whisper.cpp** | **HIGH** | `KEEP_EXISTING` |
| 12 | Chat web interface | the platform's own UI, `/ui/studio.html` | **Open WebUI** | **DIRECT DUPLICATE** — UI *and* auth *and* accounts | `REJECT` |

**Counts**: 2 `NO OVERLAP`, 4 `PARTIAL`, 4 `HIGH`, **2 `DIRECT DUPLICATE`**.

---

## §5's rule applied to the two direct duplicates

**Open WebUI — do not install.** It duplicates the UI, and separately the
authentication and the user accounts ADR-029 decided. The licence makes it
decisive; the duplication would have made it correct anyway.

**OpenHands — the rule does not apply, and the reason matters.** §5 says a
direct duplicate must not be installed. OpenHands duplicates **a seam this
repository built for it**: `openhands_adapter.py` exists, is declared, and is
one of three engines `CodingEngineManager` routes over. It is not a duplicate
*of an alternative* — it is the thing the alternative was written to hold.

**A rule that fires on the wrong side of a seam is the rule mis-read.** Recorded
so that a later reading does not apply §5 mechanically and delete an adapter.

---

## The four `PARTIAL` rows, and whether complementary integration is possible

§5 requires an answer for each, not a shrug.

**#1 Transformers — already complementary, nothing to do.** It lives in
`requirements-training.txt` and is imported inside a function body at
`scripts/training/train_adapter.py:115`, so no import cost is paid by the
platform. Promoting it into `requirements.txt` would put a heavy library in the
production image for no runtime caller.

**#4 llama.cpp — complementary, and it is already there.** `local_provider.py`
targets Ollama, and Ollama is a llama.cpp wrapper. The complementary integration
is *already in the deployment chain*, one layer down. Naming it directly would
mean replacing Ollama's model management with nothing. **Possible, not
warranted.**

**#8 Qdrant — complementary integration is possible and is not yet justified.**
E04.2 measured the alternative: a cached matrix takes 100 000-vector search from
13 132 ms to **3.88 ms**, 3 388 ×, for 153.6 MB resident. The deficiency ADR-015
wrote its own reversal condition for is a **caching bug, not a datastore
problem**. Two conditions would reopen it — payload-filtered search over
millions of vectors, or a working set that no longer fits in RAM — and neither
holds.

**#10 Unsloth — complementary, and the occasion is missing rather than the
capability.** It would replace two imports in `train_adapter.py`, leaving the
ADR-006 gate and the lineage registry untouched. What is absent is a GPU host,
an authorised dataset, and a family to train — ADR-014 names SamP and ToP as
families that **do not exist yet**.

---

## The four `HIGH` rows, and why high is not the same as direct

| # | What overlaps | What does **not** |
|---|---|---|
| 5 LiteLLM | provider abstraction, routing, fallback | **ADR-014's registration-time refusal.** LiteLLM's value is breadth across hosted vendors; this platform does not register them at all |
| 6 LangGraph | graphs, conditional branching, checkpointed resume | **ADR-006.** LangGraph's `interrupt` is a pause resumed by the caller; an approval here requires a person to decide |
| 7 LlamaIndex | retrievers, chunking, embeddings, query engines | **scope, provenance and `UNKNOWN`.** Law, administration and languages never fall back to global knowledge; ten of sixteen domains carry the reason they are empty |
| 11 whisper.cpp | local CPU speech recognition | nothing of substance — the incumbent wins on **a decision already made with a written reason**, not on a measurement |

Rows 5, 6 and 7 share a shape worth stating once: **each candidate overlaps the
mechanism and misses the constraint.** The mechanism is the commodity half; the
constraint is what this repository spent its programmes on.

Row 11 is honestly weaker: `faster-whisper` is **not installed** either, no
model is reachable (Hugging Face → 403), and there is **no `ffmpeg`** on this
host. It is an incumbent-by-decision, not an incumbent-by-measurement, and it is
recorded that way.

---

## What the matrix says as a whole

**Nothing on this list is missing from GalSen IA.** Twelve candidates produced
zero `INTEGRATE`. Two are already present, two are reachable through a seam that
exists, four are deferred against named conditions, two are kept as-is, and two
are rejected.

That is not a defensive result. It is what §1's own question — *"Is it actually
needed?"* — answers when the repository is read before the candidates are.

**The two things this audit did find are not on the matrix**, because they are
not candidates:

1. `SQLiteVectorStore.search()` re-reads and re-parses every row per query —
   **3 388 × slower than the design ADR-015 wrote down**.
2. `Role.USER` reaches `POST /coding/task`, with any host directory as the
   workspace — **§4F's constraint, unmet**.

Both belong to Ch. 07 and to the final report. Neither is fixed here.
