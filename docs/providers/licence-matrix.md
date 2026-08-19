# M03 — licence audit: MoneyPrinterTurbo and its dependency tree

Directive V4 update, §30. Read on 2026-08-19 from `LICENSE` at
`raw.githubusercontent.com` (repository) and from PyPI's package metadata
(dependencies). Every row names where it was read.

**§30's rule, applied literally: a repository's licence is not its dependencies'
licences.** MoneyPrinterTurbo is MIT. Its dependency tree is not uniformly MIT,
and one entry is copyleft.

---

## The repository

| Field | Value | Source |
|---|---|---|
| Repository licence | **MIT** | `LICENSE`, "MIT License / Copyright (c) 2024 Harry" |
| Model-weight licence | **N/A** | ships no model (M02) |
| Dataset licence | **N/A** | trains nothing (M02) |
| Commercial restriction (repo) | **none** | MIT |

## The dependency tree

Read from each package's own PyPI metadata — the `license` field, or the
`license_expression` / `License ::` classifier when the field is empty.

| Package | Licence | Class | Note |
|---|---|---|---|
| `moviepy` | MIT | permissive | The composition engine |
| `faster-whisper` | MIT | permissive | The ASR wrapper — **downloads a model** |
| `fastapi` | MIT | permissive | |
| `litellm` | MIT | permissive | |
| `pydub` | MIT | permissive | |
| `redis` | MIT | permissive | |
| `streamlit` | Apache-2.0 | permissive | WebUI |
| `openai` | Apache-2.0 | permissive | client only |
| `google-genai` | Apache-2.0 | permissive | client only |
| `dashscope` | Apache-2.0 | permissive | client only |
| **`edge-tts`** | **LGPL-3.0** | **weak copyleft** | **The TTS path** |
| **`azure-cognitiveservices-speech`** | **Other/Proprietary** | **proprietary** | Microsoft SDK |

### The two rows that matter

**`edge-tts` is LGPL-3.0, not MIT.** M02 concluded that TTS is the strongest
argument for integrating MoneyPrinterTurbo, because speech synthesis is `ABSENT`
here and no installation fixes it. That argument now carries a licence
condition, and it is the exact confusion §30 exists to prevent: *the repository
being MIT says nothing about the licence of the capability you actually want.*

LGPL is weak copyleft: importing it as a library does not place this platform
under LGPL, provided the user can replace the library. This repository already
has the mechanism for that distinction — `CreativeProvider.invocation`
(`IN_PROCESS` / `OUT_OF_PROCESS` / `API`), introduced by ADR-024 precisely
because *"calling a GPL-3.0 tool as an isolated process is not the same act as
linking it into this repository, and the difference has legal consequences."*

**`azure-cognitiveservices-speech` is proprietary.** It is an optional TTS path,
governed by Microsoft's terms rather than an open licence. It cannot be treated
as a permissive dependency, and nothing in this platform should acquire it
implicitly.

---

## Third-party services — where the real terms live

None of these is a licence question, and none of them can be settled by reading
code. They are recorded as `UNKNOWN`, which §30 says is the correct answer when a
right is not established.

| Service | Reached by | Question | Status |
|---|---|---|---|
| **Pexels API** | `material.py:309` | Are downloaded clips usable in a commercial product? Attribution? | **UNKNOWN** — API terms not read |
| **Pixabay API** | `material.py:376` | Same | **UNKNOWN** |
| **Microsoft Edge TTS endpoint** | `edge-tts` | Is a third-party product allowed to call this endpoint, and may its audio be used commercially? | **UNKNOWN** — a legal reading, not a code reading |
| **Azure Speech** | optional | Commercial terms, per subscription | **UNKNOWN** |
| **OpenAI / Gemini / DashScope** | `llm.py` | Script generation, per account | **UNKNOWN** |
| **faster-whisper model weights** | downloaded at runtime | Which model, under which licence? | **UNKNOWN** — model choice is configuration (`model_size`, default `large-v3`) |

**The stock-footage question is the sharpest.** MoneyPrinterTurbo's output is
made of clips downloaded from Pexels and Pixabay. Whether the *resulting video*
may be sold is governed by those libraries' terms, not by MPT's MIT licence and
not by anything this platform does. A user of GalSen IA who generated a video
this way and sold it would be relying on terms nobody in this repository has
read.

That is not a reason to refuse the integration. It is a reason for the provider
to **declare its commercial status as `UNKNOWN`**, which the existing
`LicenceRecord` already supports, and which makes the creative router refuse it
for a commercial job until someone reads them.

---

## §40 feasibility gates, answered

| Gate | Answer |
|---|---|
| 1. Technically possible? | The adapter, yes. Running MPT here, **no** — it needs a real `ffmpeg` (M02) |
| 2. Is there a provider? | Yes, and it is MIT |
| 3. GPU feasible? | **Not required** — MPT composes, it does not generate. This is its one advantage over WanGP here |
| 4. Latency acceptable? | **NOT_MEASURED** — nothing was run |
| 5. Quality acceptable? | **NOT_MEASURED** |
| 6. Measurable? | Yes — a health probe can check `ffmpeg` and the configured API keys |
| 7. Failure detectable? | Yes — missing binary, missing key, HTTP failure are all observable |
| 8. Fallback possible? | Yes — `routing.py` already refuses rather than substituting silently |
| 9. Replaceable later? | Yes — it is one row in a registry |
| 10. **Licence acceptable?** | **Repository yes (MIT). Capability of interest: LGPL-3.0. Output rights: `UNKNOWN`** |

**Gate 10 is the one that is not green**, and it is not green in an interesting
way: the licence is fine for the code and unresolved for the thing the
integration is actually for.

---

## What this hands to M05

Three constraints the ADR has to answer, not inherit:

1. **`edge-tts` is LGPL-3.0.** If TTS is the reason to integrate, the invocation
   mode is a legal decision, not a packaging convenience. `OUT_OF_PROCESS` or
   `API` are the defensible modes; `IN_PROCESS` requires an argument.
2. **Output rights are `UNKNOWN`.** The provider must declare
   `commercial=UNKNOWN`, and the existing router will then refuse it for
   commercial jobs. That is the behaviour already built (ADR-024); it costs
   nothing to honour and would cost a great deal to discover later.
3. **MPT cannot run on this machine.** Any adapter written here is an adapter
   that reports `BLOCKED` on a missing `ffmpeg`. M05 must say whether that is
   worth building now, or whether the honest deliverable is the declaration
   without the execution path.
