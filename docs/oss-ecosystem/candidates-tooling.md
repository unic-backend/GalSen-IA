# E03.4 — OpenHands, Unsloth, whisper.cpp, Open WebUI (§3, fields A–T)

**Read**: 2026-08-20, licence files from `raw.githubusercontent.com`, package
metadata from `pypi.org`. `api.github.com` → **403**; popularity **`UNKNOWN`**.

This phase holds the audit's two hardest findings, and neither is about
features. One candidate **cannot install on this platform's Python**. Another
**is not open source in the sense §8 warns about**.

---

## 9. OpenHands

| Field | Finding |
|---|---|
| **A. Repository status** | **ALREADY A DECLARED ENGINE.** `src/coding_engine/adapters/openhands_adapter.py` exists and is one of the three adapters `CodingEngineManager` declares, beside `aider` and `swe_agent`. It is **declared and unavailable**, and reports its own repair |
| **B. What it does** | An autonomous software-engineering agent: reads a repository, edits files, runs commands, opens changes |
| **C. Official source** | `All-Hands-AI/OpenHands`, PyPI `openhands-ai` **1.11.0** |
| **D. Licence** | **MIT**, filed. *"Copyright © 2025 OpenHands contributors"* |
| **E. Requirements** | **Python ≥ 3.12, < 3.14**; **85 unconditional dependencies** |
| **F. GPU** | None for the agent itself; the model it drives is elsewhere |
| **G. CPU/RAM** | Moderate; it also expects a container runtime for its sandbox |
| **H. Runtime** | A server the adapter talks to over HTTP, which is how this repository already models it |
| **I. Compatibility** | **This is the finding: it does not install here.** This platform is **Python 3.11.15** — `pyproject.toml` pins `target-version = "py311"` and CI runs `3.11`. `openhands-ai` requires **≥ 3.12**. The two do not intersect |
| **J. Overlap** | **DIRECT DUPLICATE** — of a seam this repository already built for it (ADR-028) |
| **K. Advantages** | Already integrated; nothing to design |
| **L. Disadvantages** | The version gap is a real blocker for in-process use, and irrelevant for the server model — **which is exactly why the adapter talks HTTP** |
| **M. Security** | Repository modification and command execution. §4F: *"Do not expose unrestricted repository modification capabilities to ordinary users"* — the existing `authorize()` gate and `ENVIRONMENT_TRANSMIS` allowlist already stand between it and the platform |
| **N. Privacy** | It reads the repository it is pointed at |
| **O. Maintenance** | Already carried, and carried as **a declaration**, which is the cheap form |
| **P. Performance** | **`UNKNOWN`** — the engine has never run here |
| **Q. Provider independence** | Preserved: the adapter passes a `ModelSpec` chosen by `ModelRouter` |
| **R. Integration difficulty** | **None to do** |
| **S. Testability** | Covered by `tests/test_coding_adapters.py` and by `tests/test_sovereignty_subordinate_runtimes.py` |
| **T. Recommendation** | **`ALREADY_PRESENT`** |

**The phase plan's opening question, answered.** §4F asked whether OpenHands
belongs inside, as a specialised agent, as an external tool, or nowhere. **The
repository answered before the audit started**: it is a specialised agent behind
a capability router, reached over HTTP, gated by authorisation. The remaining
question is not *whether* but *what the existing adapter does not do* — and the
answer is that it has never been run, because nothing has run it.

---

## 10. Unsloth

| Field | Finding |
|---|---|
| **A. Repository status** | **ABSENT.** `requirements-training.txt` exists and pins `transformers==5.1.0`, but names no Unsloth |
| **B. What it does** | Memory-efficient fine-tuning — LoRA/QLoRA with fused kernels |
| **C. Official source** | `unslothai/unsloth`, PyPI `unsloth` **2026.8.19** |
| **D. Licence** | **Apache-2.0**, filed |
| **E. Requirements** | Python ≥ 3.9, < 3.15; **484 declared**, **30 unconditional** |
| **F. GPU** | **Required, and this is not a soft requirement.** Fine-tuning without a GPU is not a slow path, it is not a path |
| **G. CPU/RAM** | **Cannot be exercised here** — no GPU |
| **H. Runtime** | A training script, not a service |
| **I. Compatibility** | It would sit in `scripts/training/`, beside the adapter trainer that already exists |
| **J. Overlap** | **PARTIAL** — `scripts/training/train_adapter.py` already imports `AutoModelForCausalLM`, `AutoTokenizer` and `BitsAndBytesConfig`, which is the quantized-fine-tuning shape |
| **K. Advantages** | Lower VRAM for the same run, on the hardware a training host would have |
| **L. Disadvantages** | **§4G: *"Do not introduce training infrastructure unless justified."*** No training is happening. ADR-014 names SamP and ToP as families that **do not exist yet** |
| **M. Security** | Training pulls weights and datasets — both are supply-chain surfaces |
| **N. Privacy** | **The sharpest risk of the twelve.** §4G: *"NEVER train on private user data without explicit authorization."* This platform holds per-subject data under ADR-010 |
| **O. Maintenance** | High, and pointless while nothing trains |
| **P. Performance** | **`UNKNOWN`** — no GPU, nothing measurable, and no fabricated VRAM figure |
| **Q. Provider independence** | Neutral |
| **R. Integration difficulty** | Moderate on a GPU host, **impossible here** |
| **S. Testability** | Not testable in CI without a GPU runner |
| **T. Recommendation** | **`DEFER`** |

**Why `DEFER` and not `REJECT`**: nothing about Unsloth is wrong. What is
missing is the *occasion* — a training host, a dataset with authorisation, and
a family to train. When those exist, this row is worth re-reading. Until then it
is infrastructure for work nobody has scheduled.

---

## 11. whisper.cpp

| Field | Finding |
|---|---|
| **A. Repository status** | **ABSENT — and its role is filled.** `requirements-audio.txt` pins **`faster-whisper==2.2.0`**, and `src/multimodal/whisper_provider.py` (200 lines) is the local transcription provider |
| **B. What it does** | Whisper inference in C/C++ — CPU-first, quantized, no Python runtime needed |
| **C. Official source** | `ggml-org/whisper.cpp`; bindings PyPI `pywhispercpp` **1.5.0** |
| **D. Licence** | **MIT**, filed. *"Copyright (c) 2023-2026 The ggml authors"* — the same authors as llama.cpp |
| **E. Requirements** | Python ≥ 3.8 for the bindings; **4 unconditional dependencies** |
| **F. GPU** | **Not required** |
| **G. CPU/RAM** | **Runnable on this host** in principle |
| **H. Runtime** | A binary or in-process bindings |
| **I. Compatibility** | `src/multimodal/registry.py` is a provider registry — the seam exists |
| **J. Overlap** | **HIGH OVERLAP** with `faster-whisper`, which is *also* a C++ reimplementation (CTranslate2) chosen for the same reason and **documented as such** in `requirements-audio.txt` |
| **K. Advantages** | Fewer dependencies; no CTranslate2; the model format is a single GGUF file |
| **L. Disadvantages** | **It would replace a decision already made, deliberately, with its reasoning written down.** The existing comment says why `faster-whisper` rather than `openai-whisper` |
| **M. Security** | Parses model files and audio — both are input surfaces |
| **N. Privacy** | **Fully local**, like the current choice |
| **O. Maintenance** | Low, but non-zero, and it would be **carried in addition to** the existing path unless one is removed |
| **P. Performance** | **`UNKNOWN` for both.** `faster-whisper` **is not installed here** either — the audio requirements are not in the production image, and Hugging Face is **403 through this proxy**, so no model can be fetched to compare them |
| **Q. Provider independence** | Preserved — `multimodal/registry.py` |
| **R. Integration difficulty** | Low |
| **S. Testability** | The provider seam is testable; a real transcription is not, here |
| **T. Recommendation** | **`KEEP_EXISTING`** |

**The honest asymmetry**: this is a comparison between an installed thing and an
absent thing, except **neither is installed**. The existing choice wins on the
strength of having been made with a written reason, not on a measurement — and
that is stated rather than dressed up.

---

## 12. Open WebUI

| Field | Finding |
|---|---|
| **A. Repository status** | **ABSENT.** The platform serves its own UI, including `/ui/studio.html` |
| **B. What it does** | A self-hosted web front end for chat with local and hosted models |
| **C. Official source** | `open-webui/open-webui`, PyPI `open-webui` **0.11.0** |
| **D. Licence** | **NOT A STANDARD OPEN-SOURCE LICENCE — read in full.** The file is titled *"Open WebUI License"*, opens *"All rights reserved"*, and is BSD-3-Clause **plus a clause 4** |
| **E. Requirements** | Python ≥ 3.11, < 3.13; **98 unconditional dependencies** of 119 |
| **F. GPU** | None |
| **G. CPU/RAM** | A web application plus its own store |
| **H. Runtime** | A server, with its own database and its own users |
| **I. Compatibility** | It is a **whole application**, not a component |
| **J. Overlap** | **DIRECT DUPLICATE** — of the existing UI, *and* of authentication, *and* of user accounts, which ADR-029 already decided |
| **K. Advantages** | A mature chat interface, far more polished than anything here |
| **L. Disadvantages** | **The licence, and it is decisive — see below** |
| **M. Security** | Its own auth stack beside this platform's RBAC and API keys: two authorities, which ADR-034 already named as the shape to avoid |
| **N. Privacy** | Its own datastore, outside `GALSEN_DATA_DIR` and outside `scripts/backup.py` |
| **O. Maintenance** | 98 unconditional dependencies for a component that duplicates one that exists |
| **P. Performance** | **`UNKNOWN`** |
| **Q. Provider independence** | Neutral |
| **R. Integration difficulty** | Low to deploy, **legally constrained to use** |
| **S. Testability** | Out of scope for this suite |
| **T. Recommendation** | **`REJECT`** |

### Clause 4, quoted, because it decides this row

> *"licensees are strictly prohibited from altering, removing, obscuring, or
> replacing any "Open WebUI" branding, including but not limited to the name,
> logo, or any visual, textual, or symbolic identifiers … except … (i)
> deployments or distributions where the total number of end users … does not
> exceed **fifty (50)** within any rolling thirty (30) day period; (ii) the
> licensee has obtained specific prior written permission …; or (iii) …
> a duly executed enterprise license…"*

PyPI classifies the package **`Other/Proprietary License`** — the project's own
published metadata agrees with the file.

**What that means concretely for this platform.** GalSen IA is meant to be
deployed by ministries, universities and NGOs, under its own name. Adopting
Open WebUI as the GalSen IA interface would mean one of three things: ship it
carrying **Open WebUI branding**, stay **under 50 users in any 30 days**, or buy
an **enterprise licence**. All three contradict the vision, and the first two
contradict it fatally.

§8's rule, which this row exists to demonstrate: *"Do not state 'open source =
unrestricted'."* Four of the twelve candidates published something other than a
clean permissive grant — this one, and LiteLLM's carve-out pointing at a **404**.

---

## What E03.4 refuses to conclude

- **That OpenHands works.** It is declared and **has never been run**. Present
  is not the same as proven.
- **That whisper.cpp is slower or faster than `faster-whisper`.** Neither is
  installed; the models cannot even be fetched through this proxy.
- **That Open WebUI is badly licensed.** It is licensed exactly as its authors
  intend. It is **incompatible with this platform's stated purpose**, which is a
  different statement and the only one the evidence supports.
