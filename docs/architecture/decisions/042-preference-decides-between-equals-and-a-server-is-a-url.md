# ADR-042 — Preference decides between equals, and a server is a URL

- **Status**: accepted
- **Date**: 2026-08-24
- **Related**: ADR-014 (sovereignty), ADR-017 (no second framework),
  ADR-040 (a local model declares what it can do)

## Context

ADR-040 made the router select by capability. Measured again on 2026-08-24
against the fleet this phase targets — `qwen3.5:9b`, `qwen2.5:14b`,
`deepseek-r1:8b`, `qwen2.5-coder:14b`, `llava:7b` — a gap remained:

A `reasoning` task finds **three** models carrying the `reasoning` strength.
They are all local, therefore all free, so cost breaks nothing. The choice fell
back to list order — that is, to **the order the operator happened to install
them in**. Capability-based routing had done its job and then handed the
decision to an accident.

Separately, the phase had to answer a harder question: how does a platform on a
12 GB card reach a one-trillion-parameter model?

## Decision

### 1. Role preferences break ties, and only ties

`config/model_routing.yaml` gains a `role_preferences` section: per task type, an
ordered list of name patterns. `ProviderSelector` consults it **after** ranking
by capability and cost, among candidates whose feature count and price are
identical to the leader's.

It never promotes a less capable model. That restraint is the whole design: a
preference that could override capability would be hard-coded routing, which is
exactly what a configuration file exists to prevent.

A role with no preference keeps the previous behaviour. Nothing regresses by
omission.

### 2. Qwen3.5 is recognised, and its vision is not

`qwen3.5:9b` is declared with 262 144 tokens of context — the first local model
to clear `document_analysis`'s 100 000-token floor. Its pattern sits **before**
the generalist entry, which contains `qwen3` and would otherwise swallow it and
hand it 32 768.

Its multimodality is reported by secondary sources. It is **not declared**.
`/api/show` will measure it on the operator's machine; asserting it from a
search summary would route images to a model that may not read them, and
ADR-040's whole point is that a measured capability and a supposed one are not
interchangeable.

`qwen2.5:14b` stays. It is the model the platform was measured against, and
deleting the baseline would leave every future comparison unanchored.

### 3. A large model is a URL, not a new architecture

`OpenAICompatibleProvider` already speaks the OpenAI HTTP contract that vLLM and
SGLang serve. Reaching Kimi K2.5, DeepSeek-R1, Qwen3.5-397B or GLM-5.1 therefore
requires **no code**: a base URL, a model name, and the existing registry.

`config/models/` holds one file per family. Every `serve_command` in it was
**copied from the official vLLM recipes repository**, fetched in this session —
not reconstructed. A flag invented for a 400-billion-parameter deployment costs
an hour of rented GPU to discover.

### 4. The health check uses `/v1/models`

vLLM exposes a health endpoint, but its path **could not be verified here** —
`docs.vllm.ai` is refused by this environment's proxy. A check built on a
supposed path reports a server outage the day the path differs.

`/v1/models` is part of the contract every compatible server implements, and it
is what the provider already calls. Checking it checks the platform's real path.

### 5. The benchmark refuses three things

- A `SCRIPTED` run is never compared to a `REAL` one. Without that refusal, a
  number obtained against a test double eventually lands in a table comparing
  two real models, and no one can tell which.
- A run that did not execute yields `None`, never `0.0`. A null rate compares;
  an absence does not.
- A gap under one and a half tasks is reported as **ÉGALITÉ**, not a victory.
  This is the guard against concluding that the newer model is better.

## Consequences

Eleven roles now reach five distinct models by operator intent rather than
install order (`tests/test_model_deployment.py`, 36 tests).

**Nothing was measured against a model.** This environment has no GPU, no Ollama,
and every weight host is refused by the proxy — `registry.ollama.ai`,
`ollama.com`, `huggingface.co` and `cdn-lfs.huggingface.co` all return `000`,
measured. So this phase produced infrastructure, and the honest label on every
model claim is `PREPARED` or `REQUIRES GPU SERVER`, never `TESTED`.

What *was* tested is the refusals: `preflight.py` reports the missing server,
`serve_large.py` declines to launch an eight-GPU model on a machine with none,
`connect.py` reports no configured URL, and `bench.py` returns **no number at
all** rather than a zero.

**Training was not rebuilt.** `scripts/training/train_adapter.py` is already a
real QLoRA recipe with a lineage registry. Adding a second pipeline to look
productive would duplicate working infrastructure. The genuinely open item is
that the recipe targets a Qwen2.5-7B base — changing it is one line and a real
training run, and the run needs a GPU.

**The cost if the preferences are wrong.** A badly ordered preference sends a
task to a slightly worse model among equally capable ones — then the fallback
still reaches the others. The previous behaviour made that same mistake
permanently and with no way to correct it, which is why the ordering lives in
configuration.
