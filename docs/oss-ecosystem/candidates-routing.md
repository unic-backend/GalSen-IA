# E03.2 — vLLM and LiteLLM (§3, fields A–T)

**Read**: 2026-08-20, from official sources — licence files from
`raw.githubusercontent.com`, package metadata from `pypi.org`.
`api.github.com` → **403** through this proxy, so popularity and release
cadence are **`UNKNOWN`**.

These two are grouped because they are the two candidates that would sit
**closest to the existing model engine** — one below it, one potentially across
it. And one of them is **already installed in this environment without being
declared** (E01).

---

## 4. vLLM

| Field | Finding |
|---|---|
| **A. Repository status** | **ABSENT as a package — and NAMED by this repository.** `ProviderRegistry().unavailability_summary()` says, verbatim: *"Renseignez `GALSEN_OPENAI_COMPATIBLE_URL`, par exemple `http://localhost:8000/v1` pour un serveur vLLM local."* |
| **B. What it does** | *"A high-throughput and memory-efficient inference and serving engine for LLMs"* |
| **C. Official source** | `vllm-project/vllm`, PyPI `vllm` **0.27.1** |
| **D. Licence** | **Apache-2.0**, filed |
| **E. Requirements** | Python ≥ 3.10, < 3.15; **97 declared dependencies** |
| **F. GPU** | **Effectively required.** `torch==2.13.0`, `torchvision`, `torchaudio`, `torchcodec`, `flashinfer-python==0.6.16.post3`, `nvidia-cudnn-frontend`, `nvidia-cutlass-dsl[cu13]` — declared, not extras |
| **G. CPU/RAM** | **Cannot be exercised here** — no GPU, 28 GB disk against a multi-GB CUDA stack |
| **H. Runtime** | A server, OpenAI-compatible on `:8000/v1` |
| **I. Compatibility** | **Already compatible.** The provider that speaks to it exists and names it |
| **J. Overlap** | **NO OVERLAP.** It sits below the provider seam — it is a *backend*, never a competitor to `model_engine/` |
| **K. Advantages** | Continuous batching and paged attention are its distinguishing claims; the throughput case for a served deployment |
| **L. Disadvantages** | 97 dependencies, a CUDA stack, and a GPU this project's target machines may not have |
| **M. Security** | A local server holding weights; no credential handling |
| **N. Privacy** | **Positive** — local inference, ADR-014's direction |
| **O. Maintenance** | **Zero as a deployment choice** |
| **P. Performance** | **`UNKNOWN`** — not installed, not run, not measurable on this host |
| **Q. Provider independence** | **Preserved**, and this is the strongest case of the twelve: it is consumed as a *protocol*, not as a library |
| **R. Integration difficulty** | **None.** One environment variable |
| **S. Testability** | Same seam as any OpenAI-compatible endpoint |
| **T. Recommendation** | **`ALREADY_PRESENT`** — as a supported deployment target, not as code |

**Why `ALREADY_PRESENT` and not `OPTIONAL`**: the distinction matters. SGLang is
*possible* through the same door; vLLM is **documented in the product's own error
message**, with its port. Someone already decided it was supported. That is
presence, not possibility.

---

## 5. LiteLLM

| Field | Finding |
|---|---|
| **A. Repository status** | **INSTALLED AND UNDECLARED.** `litellm==1.81.10` is importable in this environment; it appears in **no** requirements file and **nothing in `src/`, `agents/`, `scripts/` or `tests/` imports it** (E01, traced) |
| **B. What it does** | *"Library to easily interface with LLM API providers"* — a unified client and proxy across many hosted APIs |
| **C. Official source** | `BerriAI/litellm`, PyPI `litellm` **1.97.0** (installed here: **1.81.10**) |
| **D. Licence** | **MIT — with a carve-out, read in full.** The file opens: *"Portions of this software are licensed as follows: All content that resides under the `enterprise/` directory… is licensed under the license defined in `enterprise/LICENSE`. Content outside… is available under the MIT license."* |
| | **`enterprise/LICENSE` → 404 on the default branch** (fetched 2026-08-20). PyPI declares the package simply `MIT`. **The carve-out points at a file that is not there**, so what it covers is **`UNKNOWN`** |
| **E. Requirements** | Python ≥ 3.10, < 3.15; **13 unconditional dependencies**, including **`openai>=2.20.0`** |
| **F. GPU** | **None** |
| **G. CPU/RAM** | Negligible; it is a client |
| **H. Runtime** | In-process library, or a standalone proxy server |
| **I. Compatibility** | Technically trivial. **Architecturally it collides with ADR-014** |
| **J. Overlap** | **HIGH OVERLAP.** It offers provider abstraction, routing and fallback — three things `src/model_engine/` already holds across 33 modules, with `FailoverModelRouter` at threshold 3 / reset 300 s |
| **K. Advantages** | Breadth of hosted providers, and one uniform error surface |
| **L. Disadvantages** | Breadth of *hosted* providers is precisely what ADR-014 declines. It would import a component whose main value is the part this platform refuses to use |
| **M. Security** | **Its unconditional dependency on `openai` pulls a client for a hosted vendor into the install** — regardless of whether any key exists. That is the shape `tests/test_sovereignty_subordinate_runtimes.py` was written for |
| **N. Privacy** | Neutral in itself; the risk is credential-shaped |
| **O. Maintenance** | 13 dependencies, fast release cadence, and a licence carve-out that currently resolves to nothing |
| **P. Performance** | **`UNKNOWN`** |
| **Q. Provider independence** | **This is the crux.** LiteLLM *provides* provider independence — for a platform that does not already have it. This one does, and made a stricter choice: hosted providers are **not registered at all** |
| **R. Integration difficulty** | Low to install, **high to place** — §4B asks whether it sits above, below, beside or outside. That is E04.1 |
| **S. Testability** | Fixture-testable |
| **T. Recommendation** | **`DEFER`** — pending §4B's placement question and the licence `UNKNOWN` |

### The finding worth stating plainly

**A package that nothing declares and nothing imports is present in the
environment where this platform runs.** It is not a vulnerability and not a
dependency — it is *unowned*, most likely pulled in by a tool outside this
repository. But an inference library that ships an OpenAI client, sitting
importable inside a sovereign-by-default platform, is exactly the situation
ADR-034 and ADR-035 each described in the abstract.

**Nothing is done about it here.** §12 forbids implementation, and removing a
package this repository never installed is not this programme's call. It goes to
Ch. 07 as a security observation, and to the final report as a named item.

---

## What E03.2 refuses to conclude

- **That LiteLLM is unsafe.** Nothing imports it. An importable package is not
  an executed one, and saying otherwise would be the fabrication this method
  exists to prevent.
- **That vLLM is recommended.** *Supported as a deployment target* is a
  statement about the seam, not about throughput — which is `UNKNOWN`.
- **That the licence carve-out is a problem.** A missing `enterprise/LICENSE`
  on the default branch is an `UNKNOWN`, recorded with the exact failure
  (**404**, fetched 2026-08-20), not an accusation.
