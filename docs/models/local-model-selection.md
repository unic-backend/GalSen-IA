# Which local models to install, and for which role

*Written 2026-08-24. Hardware in view: Ryzen 7 Pro 5845, 32 GB RAM,
RTX A2000 with 12 GB VRAM.*

This document exists because the platform can now **choose** between local
models (ADR-040) and had nothing to choose between. It says which model to
install for each role the routing policy declares, and — just as importantly —
how much of what follows was actually verified.

## How to read the evidence column

The mission this work came from forbids presenting research as measurement.
Four levels are used, and they are not decorative:

| Level | Meaning |
|---|---|
| `VERIFIED` | An official source was fetched and read in this session. |
| `OBSERVED` | A search engine returned it; the source page could not be fetched. |
| `ESTIMATED` | Derived by arithmetic from an `OBSERVED` figure. |
| `UNKNOWN` | Not established. Not guessed. |

**No model quality claim in this document is above `OBSERVED`, and none is
`VERIFIED`.** No benchmark was run here, no model was downloaded, and no model
was loaded. Anyone reading this for a purchasing or deployment decision should
treat every quality ranking as a hypothesis to test with
`docs/evaluation/` once a server exists.

### What blocked stronger evidence

`huggingface.co` and `qwenlm.github.io` are **refused by this environment's
egress proxy** (`EGRESS_BLOCKED`, measured 2026-08-24). Model cards and vendor
blogs — the only sources that would raise a figure to `VERIFIED` — cannot be
read from here. `github.com` is reachable, which is why the one `VERIFIED` fact
below is an API contract rather than a model specification.

## The one thing that was verified

**Ollama's `POST /api/show` reports a model's real capabilities.**
Source: `ollama/ollama`, `docs/api.md`, fetched 2026-08-24. The response
carries:

- `capabilities` — an array such as `["completion", "vision"]`;
- `model_info` — GGML metadata including an architecture-prefixed context key
  (`llama.context_length`, `qwen2.context_length`, …).

`VERIFIED`. This is what `src/model_engine/local_catalogue.py` reads, and it is
why a running server replaces the declared profile with a measured one.

## The roles the platform routes to

These come from `config/model_routing.yaml` — they are not invented for this
document. Each role is a `preferred_features` set that `ProviderSelector`
matches against a model's declared strengths.

| Role | Serves | Feature |
|---|---|---|
| Fast | `conversation`, `translation` | `fast_response` |
| Coding | `code_generation`, `implementation`, `quality` | `code_generation` |
| Reasoning | `reasoning`, `planning`, `analysis`, `security` | `reasoning` |
| Vision | `vision` | `supports_vision` |
| Long context | `document_analysis`, `summarization`, `research` | `long_context` |

A role with no model installed is not a failure: routing falls back through the
remaining candidates, and the platform says which model it used. A role with the
*wrong* model installed is worse, which is why the mapping lives in
configuration where an operator can correct it.

## Candidates per role

Sizing assumes `Q4_K_M` quantisation, Ollama's default. `OBSERVED` figures
below come from third-party guides returned by search, not from vendors.

### Fast — the model that answers "bonjour"

The point of this role is **latency**, not quality. Before ADR-040, a greeting
could be routed to a 14-billion-parameter model; now it reaches the smallest
one installed.

| Candidate | Size | Evidence |
|---|---|---|
| `llama3.2:3b` | ~2 GB | `OBSERVED` — fits far inside 12 GB |
| `qwen2.5:3b` | ~2 GB | `OBSERVED` |
| `phi3:mini` | ~2.3 GB | `OBSERVED` |

All three are already recognised by the `local_models` patterns. Any one of them
is enough; installing all three wastes disk and changes nothing.

### Coding

| Candidate | Size | Evidence |
|---|---|---|
| `qwen2.5-coder:7b` | ~4.7 GB | `OBSERVED` — repeatedly named the reliable 12 GB pick; 80.1 % HumanEval pass@1 and 128k context are **`OBSERVED` claims from a commercial guide**, not verified |
| `qwen2.5-coder:14b` | ~9 GB | `ESTIMATED` from the 7B figure — fits 12 GB, leaves little headroom for context |
| `deepseek-coder-v2:16b-lite` | ~9 GB | `OBSERVED` — MoE, named for the 10–12 GB tier |

**Recommendation: `qwen2.5-coder:7b`.** The 14B variant fits, but the margin it
consumes is context window — and a coding task on a repository is precisely
where context is worth more than parameters. This is a judgement, not a
measurement; the cost of being wrong is one worse answer per coding request,
recoverable by `ollama pull` of the larger variant.

### Reasoning

`OBSERVED`: the Qwen3 family is Apache-2.0 and includes two MoE models
(235B-A22B, 30B-A3B) and six dense ones (32B, 14B, 8B, 4B, 1.7B, 0.6B), with
base pretraining at 4K context extended to 32K. Qwen3.6 exists as of this
writing, with a **262 144-token native context** and a 35B-A3B MoE variant.

The MoE shape matters more than the parameter count on this hardware: a model
with 3 B *active* parameters computes like a 3 B model while holding the
knowledge of a much larger one. It is the architecture that makes a 12 GB card
useful beyond its tier — **provided the weights fit in RAM**, which 32 GB makes
plausible for a 30–35 B MoE at 4-bit and which is `ESTIMATED`, not tested.

| Candidate | Shape | Evidence |
|---|---|---|
| `qwen3:8b` | dense | `OBSERVED` — Apache-2.0 |
| `qwen3:30b-a3b` | MoE, 3 B active | `OBSERVED` — needs system RAM, not just VRAM |
| `deepseek-r1:8b` / `:14b` | dense distill | `OBSERVED` |

**A reasoning model is slow by design** — it writes a reasoning chain before
answering. That is exactly why routing must not send a greeting to it, and why
the `reasoning` pattern in `local_models` is separate from the generalist one.

### Vision

| Candidate | Evidence |
|---|---|
| `llava:7b` / `:13b` | `OBSERVED` — recognised by the `local_models` vision pattern |
| `minicpm-v` | `OBSERVED` |
| a `-vl` variant (e.g. `qwen2.5-vl`) | `OBSERVED` |

Whichever is installed, its vision capability will be **measured** rather than
declared as soon as `ollama serve` runs: `/api/show` reports `vision` in
`capabilities`, and the measurement overrides the configuration file.

### Long context

| Candidate | Context | Evidence |
|---|---|---|
| `llama3.1:8b` | 128k | `OBSERVED` |
| `qwen3` variants | 32k, or 262k for Qwen3.6 | `OBSERVED` |
| `gemma3` | 128k | `OBSERVED` |

Long context is the role where the declared numbers in `config/model_routing.yaml`
are most likely to be wrong, because it is the one an operator changes with a
`num_ctx` setting. Start the server and let it be measured.

## A minimal fleet for this machine

Five models, one per role, roughly 20 GB of disk, none of them loaded
simultaneously — Ollama loads on demand and evicts:

```
ollama pull llama3.2:3b          # fast
ollama pull qwen2.5-coder:7b     # coding
ollama pull qwen3:8b             # reasoning
ollama pull llava:7b             # vision
ollama pull llama3.1:8b          # long context
```

After that, one command shows what the platform will actually do with them —
and it reports measured capabilities rather than the declared ones:

```
python -c "from src.model_engine.providers.local_provider import LocalProvider; \
[print(d.model_name, d.context_window, d.special_features, d.capability_sources) \
 for d in LocalProvider().list_models()]"
```

## Rented or remote GPUs

Nothing above limits the platform to this machine. `OpenAICompatibleProvider`
already speaks the OpenAI HTTP contract, which is what vLLM and SGLang serve, so
a remote inference server is a base URL and a model name — no code change. The
sovereignty rules of ADR-014 still apply to *where* that server runs, and
`src/model_engine/providers/derogations.py` is the gate that decides it.

`NOT EXECUTED`: no remote server was provisioned, contacted or benchmarked in
this session.

## What remains unknown

- **Every quality comparison.** No benchmark was run. `qwen2.5-coder:7b` being
  better than `deepseek-coder-v2:16b-lite` for this repository's code is a
  hypothesis.
- **Every VRAM figure marked `ESTIMATED`.** Quantised sizes vary by build.
- **Whether any of these models handles Wolof.** Nothing found in this session
  addresses it, and the platform's own Wolof knowledge (`src/wolof/`, 2105
  sentences) is retrieval, not model capability. Treat model-level Wolof as
  `UNKNOWN` until `docs/evaluation/` measures it.
- **Qwen3.6's real requirements.** Its existence and context length are
  `OBSERVED` from a search summary; the model card could not be read.

## Sources

- [ollama/ollama — docs/api.md](https://github.com/ollama/ollama/blob/main/docs/api.md) — `VERIFIED`, fetched
- [Qwen3: Think Deeper, Act Faster](https://qwenlm.github.io/blog/qwen3/) — `OBSERVED` via search; page blocked by egress proxy
- [Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) — `OBSERVED` via search; blocked by egress proxy
- [Best Ollama Models 2026 — Morph](https://www.morphllm.com/best-ollama-models) — `OBSERVED`, commercial guide
- [Best Local LLMs by VRAM Tier 2026](https://www.promptquorum.com/local-llms) — `OBSERVED`, commercial guide
- [Best Ollama Coding Models 2026](https://www.theaitechpulse.com/best-ollama-coding-models-2026) — `OBSERVED`, commercial guide
