# E01 — Repository audit (§1, §13)

**Measured**: 2026-08-20, `Linux 6.18.5-fc-v20`, Python 3.11.15, 4 CPUs, no GPU.
**Rule followed**: §1 — *"Do not rely only on filenames. Trace actual imports,
execution paths and runtime usage."*

Every line below is a command's output, not a recollection.

---

## E01.1 — Are the twelve present?

Three separate questions were asked of each project, because they have three
different answers: **declared** in a manifest, **installed** in this
environment, and **used** by an execution path.

| # | Project | Declared | Installed | Imported by `src/` | Status |
|---|---|---|---|---|---|
| 1 | Transformers | `requirements-training.txt` → `transformers==5.1.0` | no | `scripts/training/train_adapter.py` only, **inside a function** | **PARTIALLY PRESENT** |
| 2 | SGLang | no | no | no | **MISSING** |
| 3 | llama.cpp | no | no | **named as a supported wire endpoint** | **MISSING as code, ADDRESSED as a protocol** |
| 4 | LangGraph | no | no | no | **MISSING** |
| 5 | OpenHands | no | no | **`src/coding_engine/adapters/openhands_adapter.py`, a declared engine** | **ALREADY PRESENT (as an adapter)** |
| 6 | vLLM | no | no | **`ModelKind.LOCAL_VLLM`, and the default URL hint** | **MISSING as code, ADDRESSED as a protocol** |
| 7 | LiteLLM | **no manifest declares it** | **`litellm==1.81.10`** | no — only named in *adapter error signatures* | **INSTALLED AND UNDECLARED** |
| 8 | LlamaIndex | no | no | no | **MISSING** |
| 9 | Qdrant | no | no | no — `src/embeddings/vector_store.py` holds the role | **MISSING, role occupied** |
| 10 | Open WebUI | no | no | no | **MISSING** |
| 11 | Unsloth | no | no | no | **MISSING** |
| 12 | whisper.cpp | no — `requirements-audio.txt` declares **`faster-whisper==2.2.0`** | no | — | **MISSING, role occupied by a different project** |

Commands: `grep -rniE … requirements*.txt pyproject.toml Dockerfile* docker-compose*.yml`,
`grep -rniE "^\s*(from|import)\s+…" src/ agents/ scripts/ tests/ workflows/ config/`,
`importlib.metadata.version()` per distribution, and `command -v` for
`llama-cli`, `llama-server`, `whisper-cli`, `qdrant`, `ollama` — **all five
absent**.

### The three findings of E01.1

**1. OpenHands is not a candidate. It is a declared engine.**
`src/coding_engine/manager.py` builds `[AiderAdapter(), SweAgentAdapter(),
OpenHandsAdapter()]` by default, and `openhands_adapter.py` is *"une
implémentation autonome de bout en bout (ADR-028)"* reaching a server over
**HTTP** — never imported, never sub-processed. §4F therefore does not ask
whether to integrate OpenHands. It asks **what the existing adapter does not
do**, which is a different and much cheaper question.

**2. `litellm==1.81.10` is installed here and nothing in this repository asks
for it.** No requirements file declares it, no distribution requires it
(checked across every installed distribution's `requires`), and no module
imports it. It is named in this repository **only as failure signatures** —
`litellm.APIConnectionError`, `AuthenticationError`, `RateLimitError`,
`NotFoundError`, `Timeout` — which `aider_adapter.py` matches in **another
program's stdout**. That is the opposite of a dependency: it is knowing what a
neighbour's errors look like. `INFERENCE`: it comes from the container image,
not from this project. Licence read: **MIT**.

**3. vLLM and llama.cpp are already reachable, and not as code.**
`openai_compatible_provider.py` documents *"vLLM, LM Studio, llama.cpp
`--server`, LocalAI"* as endpoints of one wire format, and
`provider_registry.py` states the principle: this *"n'est pas une dépendance à
OpenAI : c'est un **format de fil**"*. `ModelKind.LOCAL_VLLM` already exists in
`src/model_engine/types.py`. So the §4A question is **not** "which backend to
adopt" — an abstraction is already in place and already names three of the four.

---

## E01.2 — Execution paths, and the measurement that matters

### Transformers is imported inside a function, on purpose

`scripts/training/train_adapter.py:115` does the import **in a function body**,
not at module level. This repository has a counter-test for exactly that
(`test_une_dependance_optionnelle_est_chargee_en_lazy`), so the pattern is
enforced rather than incidental. Consequence: **Transformers being absent breaks
nothing**, and the training script reports rather than crashes.

### The vector store, measured against ADR-015's own trigger

ADR-015 chose SQLite + NumPy over a vector database and — unusually — **wrote
its own reversal condition**: *"more than ~100 000 vectors, or a p95 query
latency above 100 ms."* That condition is the only honest way to ask the Qdrant
question, so it was measured rather than argued.

384 dimensions, normalised vectors, 30 queries per scale, one process,
4 CPUs:

| Vectors | Insert | Median query | p95 query |
|---|---|---|---|
| 271 *(today's chunk count)* | 0.17 s | **70.42 ms** | **94.93 ms** |
| 10 000 | 6.57 s | **1 943 ms** | **2 186 ms** |
| 100 000 | *measurement running at time of writing* | — | — |

**The p95 half of ADR-015's trigger is already met at 271 vectors** — 94.93 ms
against a 100 ms threshold — and exceeded by a factor of twenty at 10 000, long
before the 100 000-vector half of the condition is approached.

### Why, precisely — and why the answer may not be Qdrant

`vector_store.py:253-266` re-reads **every row** of the collection on **every
search**, then rebuilds the matrix with `json.loads(ligne[1])` **per row**. The
dot product is milliseconds, as the ADR says. The JSON deserialisation of
N × 384 floats per query is not.

ADR-015's premise is *"un cosinus exhaustif sur une matrice **en mémoire**"*.
**There is no in-memory matrix.** It is rebuilt from JSON on each call. So the
measurement does not refute the ADR's reasoning — it shows the implementation
never met the reasoning's precondition.

`INFERENCE`, to be tested in Ch. 04-D and not concluded here: a cached matrix
invalidated on write would likely move 10 000 vectors from ~1 943 ms to single
digits, **without a new service to operate, secure, back up and supervise** —
which is the exact cost ADR-015 refused. A candidate must beat *that* baseline,
not the current one.

### Roles already occupied, which is what §5 will need

| Capability | Existing GalSen IA | Candidate that would claim it |
|---|---|---|
| Vector search | `src/embeddings/vector_store.py` (ADR-015) | Qdrant |
| Embedding provider | `src/embeddings/` — `interfaces.py`, `registry.py`, `sentence_transformers_provider.py` | LlamaIndex |
| Model routing / fallback | `ModelRouter`, `FailoverModelRouter`, `ProviderRegistry` (ADR-014) | LiteLLM |
| Coding agent | `src/coding_engine/` — three adapters (ADR-028) | OpenHands *(already one of the three)* |
| Speech recognition | `requirements-audio.txt` → `faster-whisper` | whisper.cpp |
| Orchestration | the platform's one orchestrator | LangGraph |
| Local inference endpoint | `openai_compatible_provider.py` | vLLM, SGLang, llama.cpp |

**Seven of the twelve would land on a role this repository already fills.** That
is not an argument against them; it is the reason §3's twenty fields exist.

---

## Baseline suite, recorded before anything (§13)

*(filled by the closing run of this phase — see the report line in the
commit)*
