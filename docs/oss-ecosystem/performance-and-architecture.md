# E08 — Performance audit (§10) · E09 — Provider independence and the minimum architecture (§6, §11)

**Written**: 2026-08-20, `Linux 6.18.5-fc-v20`, Python 3.11.15, 4 CPUs,
~15 GB RAM free, 28 GB disk free, **no GPU**.

§10's rule: *"Measure only what can actually be measured. Never fabricate
missing measurements."*

---

# E08 — What was measured, and what was not

## Measured

### 1. Vector search, three scales — the programme's central figure

| Vectors | Current `search()` median | **Cached matrix median** | Factor | Matrix RAM |
|---:|---:|---:|---:|---:|
| 271 *(today's corpus)* | 70.42 ms · p95 **94.93 ms** | — | — | — |
| 10 000 | 1 232 ms | **0.37 ms** | **3 360 ×** | 15.4 MB |
| 100 000 | 13 132 ms | **3.88 ms** | **3 388 ×** | 153.6 MB |

Cache construction: 1.2 s at 10 000, 13.7 s at 100 000 — **once**, not per
query. Insertion: 0.17 s / 6.57 s / 62.72 s.

*(E01 measured 1 943 ms and 27 944 ms medians on the same current path against
1 232 ms and 13 132 ms here. **Two runs on a shared 4-CPU host vary by about a
factor of two, and this is stated rather than averaged away.** The conclusion is
unaffected: both are three to four orders of magnitude above the cached path.)*

**ADR-015 wrote its own reversal condition** — *"~100 000 vectors, or a p95
beyond 100 ms."* The p95 half is met **at 271 vectors**, today's corpus size.

### 2. Declared dependency weight, read from published metadata

| Project | Declared | Unconditional | Unconditional CUDA/NVIDIA |
|---|---:|---:|---|
| llama.cpp bindings | 26 | **4** | 0 |
| whisper.cpp bindings | — | **4** | 0 |
| Transformers | 251 | **9** | 0 — `torch` is an *extra* |
| LiteLLM | 87 | **13** | 0 — but includes `openai>=2.20.0` |
| OpenHands | — | **85** | 0 |
| Open WebUI | 119 | **98** | 0 |
| vLLM | 97 | — | `torch==2.13.0`, `flashinfer`, `nvidia-cudnn-frontend`, `cutlass[cu13]` |
| SGLang | 128 | — | `cuda-python>=13.0`, `torch==2.11.0`, `nvidia-mathdx` |
| Unsloth | 484 | **30** | GPU required outright |

### 3. Host capability probes

`ls /dev/nvidia*` → **none** · `ffmpeg` → **`command not found`** ·
Hugging Face → **403** · `api.github.com` → **403** ·
`raw.githubusercontent.com` → **200** · `pypi.org` → **200**.

### 4. The suite, every phase

`1 failed, 6967 passed, 12 skipped, 3 deselected` — 5 to 8 minutes per run,
fourteen runs, **identical every time**. The failure is the `v0.1.0` tag.

## Not measured, and why — `UNKNOWN`, never estimated

| Figure | Reason |
|---|---|
| vLLM / SGLang throughput and latency | **no GPU**; neither installed; CUDA stack exceeds this disk |
| llama.cpp inference speed | not installed; **no model reachable** (HF 403) |
| Transformers inference speed | same |
| `faster-whisper` vs whisper.cpp | **neither installed**, no model, **no `ffmpeg`** to decode audio |
| Unsloth VRAM saving | **no GPU** |
| Qdrant query latency | not installed |
| LangGraph / LlamaIndex overhead | not installed |
| Startup and model-load times | nothing to start |

**Nine rows of `UNKNOWN`, one measurement that matters, and no number in
between.** §10 asked for exactly this shape.

---

# E09 — Provider independence and the minimum architecture

## §6's conceptual chain, checked against the repository

```
USER INTENT → TASK STATE → ORCHESTRATOR → CAPABILITY ABSTRACTIONS
            → PROVIDERS/ENGINES → VERIFICATION → OUTPUT
```

Each abstraction §6 names, and what already holds it:

| §6 abstraction | Present as |
|---|---|
| `LLMProvider` / `InferenceProvider` | `src/model_engine/providers/` — `base.py`, `local`, `openai_compatible`; `ProviderRegistry` refuses hosted ones under ADR-014 |
| `EmbeddingProvider` | `src/embeddings/` |
| `VectorStoreProvider` | `SQLiteVectorStore` — **one implementation, and the seam exists** |
| `VoiceProvider` | `src/multimodal/` — `TranscriptionProvider` ABC + registry |
| `VisionProvider` / `VideoProvider` / `ImageProvider` | `src/media/` |
| `ResearchProvider` | `src/research/` (ADR-032) |
| Coding engines | `src/coding_engine/` — `CodingCapability` router, *"ne connaît aucun des trois moteurs par son nom"* (ADR-028) |

**Every abstraction §6 asks for exists.** That is why twelve candidates produced
zero `INTEGRATE`: they would each enter behind a seam that is already there,
and none of them brings something the seam is missing.

## The minimum architecture that gains real value

**It is the current one.** Stated plainly rather than dressed up as a proposal:

- **Inference** — any OpenAI-compatible server, through
  `GALSEN_OPENAI_COMPATIBLE_URL`. vLLM, SGLang and `llama-server` are three of
  them; **vLLM is already named in the platform's own unavailability message,
  with its port**. Zero code.
- **Provider routing** — `src/model_engine/`, unchanged. LiteLLM stays
  **outside**.
- **Knowledge** — `src/knowledge_engine/` + `src/embeddings/`, with **the
  caching defect fixed** (S-finding, not this programme's task). Qdrant deferred
  against two named conditions.
- **Voice** — `src/multimodal/` + `faster-whisper`. whisper.cpp would enter
  **beside** it as a second `TranscriptionProvider`, never instead.
- **Orchestration** — the one orchestrator. LangGraph adopted in no part.
- **Training** — `scripts/training/`, ADR-006-gated. Unsloth on the day a GPU
  host, an authorised dataset and a family exist.
- **UI** — the platform's own. Open WebUI rejected on licence *and*
  architecture.

## The one gap this chapter names

**The deployment documentation does not say what the error message says.** A
reader of `docs/deployment/` cannot learn that any OpenAI-compatible server
serves this platform, or that vLLM, SGLang and `llama-server` are three of them.

That is a documentation gap, it is real, and **writing it is not in this
programme's scope** — §12 forbids implementation and
`.claude/rules/spec-driven-governance.md` forbids turning a suggestion into a
task. Recorded for the backlog.

---

## What E08 and E09 refuse to conclude

- **That any candidate is fast or slow.** Nine `UNKNOWN` rows.
- **That the 3 388 × figure is a service level.** It is one benchmark on a
  4-CPU host, with run-to-run variance stated.
- **That the architecture is good.** It is *sufficient for these twelve* — which
  is a narrower claim, and the only one the evidence supports.
- **That the documentation gap should be filled by this programme.**
