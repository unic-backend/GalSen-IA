# Running models: the development machine, and the GPU server

*Written 2026-08-24. Complements `docs/models/local-model-selection.md`, which
covers **which** model to install; this one covers **how to run it** and how to
reach the large models.*

## Read the labels

| Label | Meaning |
|---|---|
| `TESTED` | Executed in this session, output observed. |
| `PREPARED` | Written and runnable, but not executed against a model. |
| `NOT TESTED` | Neither executed nor verified. |
| `REQUIRES GPU SERVER` | Cannot run on the development machine at all. |

**Nothing in this document is `TESTED` against a model.** No model was
downloaded, loaded, or benchmarked. The scripts were run and their refusals
observed — which is a different and much smaller claim.

### Why, measured

This session's environment: **no GPU** (`nvidia-smi` absent), 15 GB RAM, no
Ollama binary, nothing listening on `11434`. And every weight host is refused by
the egress proxy — measured 2026-08-24:

```
200  https://pypi.org/simple/          200  https://raw.githubusercontent.com/...
000  https://registry.ollama.ai/v2/    000  https://huggingface.co
000  https://ollama.com                000  https://cdn-lfs.huggingface.co
```

No weights can be fetched here. That is why this phase produced *infrastructure*
and not *measurements*, and why saying so plainly matters more than a score.

## A — The development machine (12 GB VRAM, 32 GB RAM)

### The model

`qwen3.5:9b`. Facts, `OBSERVED` (search engine; model cards unreachable):
9 B dense parameters, **262 144-token native context**, Apache-2.0, released
early 2026. Sizes at common quantizations: ~5.5 GB at `Q4_K_M`, ~7.4 GB at
`Q6_K`, ~9.6 GB at `Q8_0`.

**On a 12 GB card, `Q6_K` is the judgement call**: it leaves roughly 4 GB for
KV cache, which is what a long context actually consumes. `Q4_K_M` is Ollama's
default and fits with far more room; `Q8_0` fits but leaves little for context,
which wastes the model's main advantage.

```
ollama pull qwen3.5:9b          # Q4_K_M by default
ollama pull qwen2.5:14b         # the baseline, kept — do not delete it
```

**The baseline is kept deliberately.** `qwen2.5:14b` is the model the platform
was measured against; removing it would make every future comparison
unanchored.

### Backend: Ollama, and why not llama.cpp directly

Ollama *is* llama.cpp underneath, with three things the platform already
depends on: a model catalogue over HTTP, on-demand load and eviction, and
`/api/show`, which reports a model's **measured** capabilities (ADR-040). Going
to llama.cpp directly would mean rebuilding those three — a second model
architecture, which ADR-017 refuses.

`PREPARED`. Not tested: no Ollama here.

### Verify the chain on your own machine

```
python scripts/models/preflight.py            # profiles + routing, no generation
python scripts/models/preflight.py --generer  # asks each model one sentence
```

`TESTED` — it runs, and reports `INJOIGNABLE` here with the exact reason. What
it will report on a machine with a server is `NOT TESTED`.

It answers three questions no other command does: what the server says about
each model, whether each capability is **measured** or merely **declared**, and
which model each role will actually reach.

### Which role reaches which model

Measured here against a frozen fleet (`tests/test_model_deployment.py` pins it):

| Role | Model |
|---|---|
| `conversation`, `translation` | the smallest installed |
| `code_generation`, `implementation`, `quality` | `qwen2.5-coder:14b` |
| `reasoning`, `planning`, `analysis`, `security` | `deepseek-r1:8b` |
| `document_analysis`, `summarization`, `research` | `qwen3.5:9b` |
| `vision` | `llava:7b` |

Ties are broken by `role_preferences` in `config/model_routing.yaml` — an
operator decision, not install order. **Preference acts only between models that
are already equally capable**; it never promotes a less capable one, or it would
become hard-coded routing.

## B — The GPU server (large models)

Four families are prepared. `config/models/` holds one file each, and every
`serve_command` was **copied from the official vLLM recipes repository**
(`vllm-project/recipes`, `main`, read 2026-08-24) rather than reconstructed.

| Model | Shape | Minimum | Evidence |
|---|---|---|---|
| Kimi K2.5 | MoE, 1 T total / 32 B active | 8×H200 (~640 GB) BF16 | command `VERIFIED`, sizes `OBSERVED` |
| Qwen3.5-397B-A17B | MoE, 397 B / 17 B | 8×H200 or 8×MI300X | `VERIFIED` |
| DeepSeek-R1-0528 | MoE | 8 GPU, TP8 + EP | command `VERIFIED`, VRAM `NOT VERIFIED` |
| GLM-5.1-FP8 | MoE | 8 GPU, TP8 | command `VERIFIED` |

**None runs on 12 GB.** That is not a matter of patience — the weights do not
fit — and `scripts/models/serve_large.py` refuses the launch rather than letting
vLLM fail across several hundred lines of traceback.

### The workflow, when the server exists

```
# 1. On the GPU server
uv venv && source .venv/bin/activate
uv pip install vllm --torch-backend auto

# 2. See the exact command, and whether this machine can run it
python scripts/models/serve_large.py kimi-k2.5

# 3. Start it
python scripts/models/serve_large.py kimi-k2.5 --execute

# 4. From the GalSen IA machine, join the server to the platform
export GALSEN_OPENAI_COMPATIBLE_URL=http://SERVER:8000/v1
python scripts/models/connect.py --generer

# 5. Measure, against the local baseline
python scripts/models/bench.py --serveur http://SERVER:8000/v1 \
    --modele moonshotai/Kimi-K2.5
```

Steps 1–3 and 5 are `REQUIRES GPU SERVER`. Steps 2 and 4 are `TESTED` — they run
here and report exactly what is missing.

### No code change is needed to add a server

`OpenAICompatibleProvider` already speaks the OpenAI HTTP contract that vLLM and
SGLang serve. A remote model is a base URL and a model name. This is the reason
the platform does not need a vLLM client, an SGLang client, or a second model
architecture (ADR-017).

### Health check: `/v1/models`, not `/health`

vLLM exposes a health endpoint, but **its path could not be verified here** —
`docs.vllm.ai` is refused by the proxy. Building a health check on a supposed
path produces a test that reports a server outage the day the path differs.

`/v1/models` is part of the OpenAI contract every compatible server implements,
and it is what `OpenAICompatibleProvider` already calls. Checking it therefore
checks **the platform's real path**, not a parallel one.

### Sovereignty is not waived by convenience

ADR-014 governs *where* a model runs, not only which one. A rented GPU is a
third-party runtime, and `src/model_engine/providers/derogations.py` decides
whether it is permitted. Preparing a deployment does not authorise it.

## Benchmarking

`python scripts/models/bench.py --modele A --contre B`

Twelve tasks across seven categories — math, reasoning, coding, French,
instruction-following, hallucination resistance, long context — each with a
**deterministic** check. Coarse, and that is the price of reproducibility: a
model-as-judge would give finer scores that no one could reproduce, and would
judge with the same weakness as the thing it judges.

Every run records mode, model, backend, quantization, context window,
temperature, hardware, latency, tokens and errors. Two scores obtained at
different quantizations do not compare, and without those fields nothing would
say so six months later.

**Three refusals are built in**, and they matter more than the score:

- a `SCRIPTED` run is never compared to a `REAL` one;
- a run that did not execute yields `None`, never `0.0` — a null rate compares,
  an absence does not;
- a gap under one and a half tasks is reported as **ÉGALITÉ**, not a victory.
  That last one is the guard against "the newer model is better".

`TESTED` — the harness runs and refuses correctly here. `NOT TESTED` — no model
has ever passed it.

## Training

**Already prepared, and not rebuilt.** `scripts/training/train_adapter.py` is a
real QLoRA recipe (4-bit base + LoRA adapter, consent-filtered pairs, manifest,
lineage registry). `src/training/` holds evaluation, feedback and lineage.

Adding a second training pipeline to look productive would duplicate working
infrastructure, which this repository's rules forbid. What is genuinely open:
the recipe targets a Qwen2.5-7B base, and Qwen3.5 would be a different base —
that is a one-line change plus a real training run, and the run needs a GPU.

`REQUIRES GPU SERVER`.

## Sources

- [vllm-project/recipes — moonshotai/Kimi-K2.5.md](https://raw.githubusercontent.com/vllm-project/recipes/main/moonshotai/Kimi-K2.5.md) — `VERIFIED`, fetched
- [vllm-project/recipes — Qwen/Qwen3.5.md](https://raw.githubusercontent.com/vllm-project/recipes/main/Qwen/Qwen3.5.md) — `VERIFIED`, fetched
- [vllm-project/recipes — DeepSeek/DeepSeek-V3.md](https://raw.githubusercontent.com/vllm-project/recipes/main/DeepSeek/DeepSeek-V3.md) — `VERIFIED`, fetched
- [vllm-project/recipes — GLM/GLM5.md](https://raw.githubusercontent.com/vllm-project/recipes/main/GLM/GLM5.md) — `VERIFIED`, fetched
- [ollama/ollama — docs/api.md](https://github.com/ollama/ollama/blob/main/docs/api.md) — `VERIFIED`, fetched
- [Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) — `OBSERVED` via search; blocked by proxy
- [Qwen 3.5 9B VRAM requirements](https://willitrunai.com/blog/qwen-3-5-9b-vram-requirements) — `OBSERVED`, commercial guide
- [Kimi K2.5 specifications](https://apxml.com/models/kimi-k25) — `OBSERVED`, commercial guide
