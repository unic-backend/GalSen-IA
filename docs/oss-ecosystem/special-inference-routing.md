# E04.1 — §4A inference backends, §4B where LiteLLM sits

**Written**: 2026-08-20. Both questions are architectural, and both have an
answer that follows from what E02 and E03 already measured rather than from a
preference.

---

## §4A — Should GalSen IA support multiple inference backends behind one abstraction?

### It already does, and the abstraction is named

`src/model_engine/providers/` holds `base.py`, `local_provider.py` and
`openai_compatible_provider.py` (307 lines, *"Fournisseur pour toute API parlant
le protocole OpenAI"* — ADR-003). Under ADR-014 those two are the **only** ones
registered by default: `provider_ids() == ["local", "openai_compatible"]` even
with all three hosted keys set.

So the directive's question — *"determine whether GALSEN-IA should support
multiple inference backends behind ONE abstraction"* — is not open. **The answer
is in the repository, and it predates this audit.**

What the audit adds is which of the four candidates that abstraction already
reaches:

| Backend | How it is reached today | Named by the platform? |
|---|---|---|
| **vLLM** | `GALSEN_OPENAI_COMPATIBLE_URL` | **Yes** — the unavailability message names it *and its port* |
| **SGLang** | the same variable | No |
| **llama.cpp** | the same variable (`llama-server`), **or** already, one layer down, as what Ollama is built on | No |
| **Transformers** | not a server; it is the library the others are compared against | n/a |

**Three of the four are the same integration**, and that integration exists.
None of them requires a line of code.

### The comparison the directive asks for, with its columns marked honestly

| | vLLM | SGLang | llama.cpp | Transformers |
|---|---|---|---|---|
| Licence | Apache-2.0 | Apache-2.0 | MIT | Apache-2.0 |
| Unconditional deps | 97 decl. | 128 decl. | **4** | **9** |
| CUDA/NVIDIA declared | **yes** | **yes** | no | no |
| Runs on this host | **no** (no GPU) | **no** | **yes** | yes |
| Quantization | yes | yes | **GGUF, its purpose** | via extras |
| Throughput | **`UNKNOWN`** | **`UNKNOWN`** | **`UNKNOWN`** | **`UNKNOWN`** |
| Latency | **`UNKNOWN`** | **`UNKNOWN`** | **`UNKNOWN`** | **`UNKNOWN`** |
| Deployment complexity | a server + CUDA | a server + CUDA | a binary | a library |
| Fallback | `FailoverModelRouter`, threshold 3 / reset 300 s — **same for all four** | | | |

**Every performance cell is `UNKNOWN`, and that is the measurement.** §4A says
*"If benchmarks cannot be executed, state UNKNOWN. Never fabricate benchmark
numbers."* No GPU, no installed engine, no model reachable — Hugging Face is
**403 through this proxy**. Four rows of `UNKNOWN` are the honest output.

### What follows

**Nothing to build.** The recommendation for §4A is that the *deployment
documentation* should say what the error message already says — that any
OpenAI-compatible server serves this platform, and that vLLM, SGLang and
`llama-server` are three of them. That is a documentation gap, not an
architectural one, and **it is not in this programme's scope to write**.

---

## §4B — Above, below, beside, or outside?

The directive asks exactly this, so it gets exactly one answer.

### **OUTSIDE.**

**Why not BELOW.** Below the existing abstraction is where a *backend* sits — a
process the platform talks to. LiteLLM can run as a proxy, and in that shape it
is indistinguishable from any other OpenAI-compatible endpoint: it would be
reached by the provider that already exists, adding nothing the variable does
not already give. Below is not a place for it; it is a description of a
deployment somebody else might choose.

**Why not ABOVE.** Above means the platform calls LiteLLM and LiteLLM chooses
the provider. That inverts ADR-014. The sovereign default is not *"prefer
local"* — hosted providers are **not registered at all**. Handing model choice to
a library whose purpose is breadth across hosted vendors would make the
guarantee depend on that library's configuration rather than on this
repository's registry. And `tests/test_sovereignty_subordinate_runtimes.py`
exists precisely because a guarantee that moves outside `ModelRouter` stops
being visible to the test that proves it.

**Why not BESIDE.** Beside means two routing layers, each with its own fallback.
`FailoverModelRouter` counts failures per model with a threshold of 3 and a
300-second reset; LiteLLM has its own retry and fallback logic. Two independent
retry policies over one failing endpoint do not add resilience — they multiply
attempts and make the failure harder to attribute. ADR-034 already recorded
*two vocabularies for jobs and two `retry_manager`* as a defect found in this
repository. Adding a third deliberately would be strange.

**Why OUTSIDE.** LiteLLM solves *provider abstraction for a platform that does
not have one*. This platform has one, in 33 modules, with a policy externalised
to `config/model_routing.yaml`, a cost filter that actually filters, and a
sovereignty rule enforced at registration. **The problem LiteLLM solves is
already solved here, and solved more strictly.**

### Two facts that make this more than a preference

1. **`openai>=2.20.0` is one of LiteLLM's 13 unconditional dependencies.**
   Installing it puts a hosted-vendor client in the environment whether or not
   any key exists. That is the exact shape the sovereignty test was written to
   watch, and importing it would mean accepting the shape by choice.
2. **Its licence is not plain MIT** — the carve-out for `enterprise/` points at
   a file that returns **404** on the default branch (E03.2, fetched
   2026-08-20). §8 says an unverifiable licence term is `UNKNOWN`, and §7's
   question 6 asks whether the licence is compatible. It cannot be answered.

### Recommendation

**`DEFER`**, unchanged from E03.2, with the placement now settled: if it ever
enters, it enters **outside** — as a proxy someone deploys, reached through
`GALSEN_OPENAI_COMPATIBLE_URL` like any other endpoint, holding **no
credentials this platform issued**.

**And the installed copy stays a Ch. 07 observation.** `litellm==1.81.10` is
importable in this environment, declared by nothing and imported by nothing.
Deciding its fate is not this programme's call — §12 forbids implementation, and
the package was not installed by this repository.

---

## What E04.1 refuses to conclude

- **That one inference backend is better than another.** Eight `UNKNOWN` cells.
- **That LiteLLM is a bad library.** It is a good library for a problem this
  platform does not have.
- **That the deployment documentation should be written.** It is a real gap, it
  is named, and writing it is not what this directive asked for.
