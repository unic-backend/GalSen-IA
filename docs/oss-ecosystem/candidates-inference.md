# E03.1 — Transformers, SGLang, llama.cpp (§3, fields A–T)

**Read**: 2026-08-20, from official sources only —
`raw.githubusercontent.com` (licence files) and `pypi.org` (published package
metadata). `api.github.com` answers **403** through this environment's proxy, so
stars, release dates and issue counts are **`UNKNOWN`** and are not substituted
from memory.

§3's rule: *"Never choose INTEGRATE merely because the project is popular."*
Since popularity is not even readable here, the rule costs nothing to keep.

---

## The measurement that decides two of these three

Declared dependencies, read from each project's own published metadata:

| Project | Declared | **Unconditional** | Unconditional GPU/CUDA |
|---|---:|---:|---:|
| **llama.cpp** (`llama-cpp-python`) | 26 | **4** | **0** |
| **Transformers** | 251 | **9** | **0** |
| **SGLang** | 128 | — | **`cuda-python>=13.0`, `torch==2.11.0`, `flashinfer_python[cu13]`, `nvidia-cutlass-dsl[cu13]`, `nvidia-mathdx`, `nvidia-ml-py`, `torchao`** |

`llama-cpp-python`'s four: `typing-extensions`, `numpy`, `diskcache`, `jinja2`.
Transformers' nine: `huggingface-hub`, `numpy`, `packaging`, `pyyaml`, `regex`,
`tokenizers`, `typer`, `safetensors`, `tqdm` — **`torch` is not among them**;
it is an extra.

**This host has no GPU** (`ls /dev/nvidia*` → nothing), 4 CPUs, ~15 GB RAM,
28 GB disk. SGLang's declared stack is not optional and not small.

---

## 1. Hugging Face Transformers

| Field | Finding |
|---|---|
| **A. Repository status** | **PARTIALLY PRESENT.** `transformers==5.1.0` pinned in `requirements-training.txt`; imported **inside a function body** at `scripts/training/train_adapter.py:115`. Not in `requirements.txt`, not in the production image. |
| **B. What it does** | *"the model-definition framework for state-of-the-art machine learning models"* (its own summary) |
| **C. Official source** | `huggingface/transformers`, PyPI `transformers` |
| **D. Licence** | **Apache-2.0**, filed. Header: *"Copyright 2018- The Hugging Face team. All rights reserved."* above the Apache text — a copyright line, not a restriction |
| **E. Requirements** | Python ≥ 3.10; **9 unconditional dependencies**, none GPU |
| **F. GPU** | **Not required** to install. Required to be useful for inference at scale |
| **G. CPU/RAM** | Installable here; running a model is bounded by the model, not the library |
| **H. Runtime** | Python, in-process |
| **I. Compatibility** | Already compatible — it is already used |
| **J. Overlap** | **PARTIAL** — with `scripts/training/`, not with `src/`. Zero overlap with the model engine's 33 modules |
| **K. Advantages** | The reference implementation; already the training path's dependency |
| **L. Disadvantages** | Not a serving engine. Using it *as* one is the slow path both other candidates exist to replace |
| **M. Security** | Downloads weights from Hugging Face — **which answers 403 through this proxy** (measured, recorded in `whisper_provider.py` before this audit) |
| **N. Privacy** | Local execution; the download is the network event |
| **O. Maintenance** | Already carried |
| **P. Performance** | **`UNKNOWN`** — nothing was run |
| **Q. Provider independence** | Neutral |
| **R. Integration difficulty** | **None to do** |
| **S. Testability** | Its own path is fixture-testable; no model runs here |
| **T. Recommendation** | **`ALREADY_PRESENT`** |

**Why not `INTEGRATE`**: there is nothing to integrate. Whether it should be
*promoted* out of `requirements-training.txt` is a different question, and
nothing in the audit so far argues for it.

---

## 2. SGLang

| Field | Finding |
|---|---|
| **A. Repository status** | **ABSENT.** Zero declarations, zero imports, zero binaries |
| **B. What it does** | *"a fast serving framework for large language models and vision language models"* |
| **C. Official source** | `sgl-project/sglang`, PyPI `sglang` **0.5.17** |
| **D. Licence** | **Apache-2.0**, filed |
| **E. Requirements** | Python ≥ 3.10; **128 declared dependencies** |
| **F. GPU** | **Effectively required.** `cuda-python>=13.0`, `torch==2.11.0`, `flashinfer_python[cu13]`, `nvidia-cutlass-dsl[cu13]`, `nvidia-mathdx`, `nvidia-ml-py` are **declared, not extras** |
| **G. CPU/RAM** | **Cannot be exercised here** — no GPU |
| **H. Runtime** | A server process |
| **I. Compatibility** | **It already fits**, and that is the finding — it serves an OpenAI-compatible API, which `openai_compatible_provider.py` already speaks |
| **J. Overlap** | **NO OVERLAP** with the engine; it sits *below* the provider seam |
| **K. Advantages** | Structured generation and prefix caching are its distinguishing claims |
| **L. Disadvantages** | 128 dependencies and a CUDA stack, for a host that has neither GPU nor a use for one today |
| **M. Security** | A server that loads weights and accepts requests. Same class as any local inference server |
| **N. Privacy** | **Positive** — local inference is the sovereign direction (ADR-014) |
| **O. Maintenance** | **Zero if treated as a deployment choice**, high if vendored |
| **P. Performance** | **`UNKNOWN`.** Its throughput claims were not measured and cannot be measured here |
| **Q. Provider independence** | **Preserved** — reached through the existing provider |
| **R. Integration difficulty** | **None**: `GALSEN_OPENAI_COMPATIBLE_URL` |
| **S. Testability** | Not testable here |
| **T. Recommendation** | **`OPTIONAL`** |

**Why `OPTIONAL` and not `INTEGRATE`**: nothing needs to be built. SGLang is
already reachable through a provider that exists. Writing an adapter for it
would **create** the coupling the architecture currently avoids.

---

## 3. llama.cpp

| Field | Finding |
|---|---|
| **A. Repository status** | **ABSENT as a package**, and **already reachable as a wire format** — `llama-server` speaks the OpenAI protocol |
| **B. What it does** | CPU-first LLM inference in C/C++, with quantization (GGUF) |
| **C. Official source** | `ggml-org/llama.cpp`; bindings PyPI `llama-cpp-python` **0.3.35** |
| **D. Licence** | **MIT**, filed. *"Copyright (c) 2023-2026 The ggml authors"* |
| **E. Requirements** | Python ≥ 3.8 for the bindings; **4 unconditional dependencies** |
| **F. GPU** | **Not required.** This is its entire point |
| **G. CPU/RAM** | **The only candidate of the three that this host could actually run** |
| **H. Runtime** | A binary, or in-process bindings |
| **I. Compatibility** | Two doors: the provider seam, or `llama-cpp-python` in-process |
| **J. Overlap** | **NO OVERLAP** with the engine; **PARTIAL** with `local_provider.py`, which today means Ollama — and **Ollama is built on llama.cpp** |
| **K. Advantages** | Quantized CPU inference, 4 dependencies, MIT |
| **L. Disadvantages** | Slower than GPU serving by design; GGUF conversion is its own step |
| **M. Security** | Loads model files; a malformed GGUF is an input-parsing surface |
| **N. Privacy** | **Fully local** |
| **O. Maintenance** | Low for the server; the bindings pin a compiled artifact |
| **P. Performance** | **`UNKNOWN`** — not run. Ch. 08 will state what could be measured |
| **Q. Provider independence** | **Preserved** |
| **R. Integration difficulty** | **None** for the server path |
| **S. Testability** | The server path is testable the same way Ollama is |
| **T. Recommendation** | **`OPTIONAL`** |

**The uncomfortable observation**: the platform's local provider targets Ollama,
which *is* a llama.cpp wrapper. So llama.cpp is already in the dependency chain
of the intended deployment — **one layer down, and unnamed**.

---

## What E03.1 refuses to conclude

- **That SGLang is unsuitable.** It is unmeasurable *here*. A GPU host would
  change the measurement and not the licence, the dependency count or the seam.
- **That llama.cpp should replace Ollama.** Ollama is a packaging and model-
  management layer over it. Replacing one with the other is a deployment
  decision nobody has asked for.
- **Anything about speed.** Three serving engines, zero benchmarks run. §4A
  says `UNKNOWN` and §10 forbids fabrication.
