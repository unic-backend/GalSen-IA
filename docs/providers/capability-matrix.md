# M01 — the capability matrix §1 asks for

Directive V4 update, §1 and §21 (phase M01.1: video), §36 STEP 5–6 (phase M01.2:
reference, identity, audio). Measured on 2026-08-19 at `7d0a5a0`.

**§21's rule governs every row: replacement requires evidence, and "a newer
provider exists" is not evidence.** Nothing below is classified `REPLACE`,
because nothing measured here justifies it.

---

## M01.1 — existing video systems

The media engine computes its own verdict rather than declaring one, and it
reads today:

> `ENGINE READY — MEDIA RUNTIME DEPENDENCIES PENDING, 1 STAGE(S) NOT IMPLEMENTED (VOICE)`

Seventeen stages: **10 `READY`, 6 `BLOCKED`, 1 `ABSENT`**.

### The seventeen stages, and what blocks each

| Stage | State | Module | Blocked on |
|---|---|---|---|
| IDEA | READY | `media/tools/intent.py` | — |
| SCRIPT | READY | `media/story/planner.py` | — |
| MEDIA_ANALYSIS | BLOCKED | `media/ingestion/inspect.py` | a real `ffprobe` |
| STORYBOARD | READY | `media/story/structures.py` | — |
| SCENES | BLOCKED | `media/analysis/scenes.py` | a real `ffmpeg` |
| **VISUAL_GENERATION** | **BLOCKED** | `media/providers/base.py` | no cleared provider |
| **VIDEO_GENERATION** | **BLOCKED** | `media/providers/wangp.py` | GPU **and** WanGP's licence |
| MOTION_DESIGN | READY | `media/motion/render.py` | — |
| VOICE | **ABSENT** | — | nothing implements it |
| MUSIC | READY | `media/audio/music.py` | — |
| SOUND_DESIGN | READY | `media/audio/sound_design.py` | — |
| SUBTITLES | READY | `media/subtitles/cues.py` | — |
| EDITING | BLOCKED | `media/timeline/edit_plan.py` | a real `ffmpeg` |
| QUALITY_CONTROL | READY | `media/qc/checks.py` | — |
| MULTI_FORMAT | READY | `media/adapt/formats.py` | — |
| MULTILINGUAL | READY | `media/adapt/formats.py` | — |
| FINAL_MASTER | BLOCKED | `media/core/project.py` | a real `ffmpeg` |

**This is the row that matters for this programme**: four of the six blocked
stages are blocked on **one missing `ffmpeg`**, not on a provider. A video
provider does not unblock `MEDIA_ANALYSIS`, `SCENES`, `EDITING` or
`FINAL_MASTER`. Whatever MoneyPrinterTurbo turns out to be, it addresses at most
two stages of seventeen.

### The existing video provider, per §21's required fields

| Field | Value |
|---|---|
| Path | `src/media/providers/wangp.py`, 203 lines |
| Purpose | Adapter for Wan2GP (`https://github.com/deepbeepmeep/Wan2GP`) |
| Provider / model | WanGP — **not vendored**, `third_party/` holds only aider, opengap, openhands, swe_agent |
| API | `health()`, `is_available()`, `generate()`, `integration_report()` |
| Status | `ADAPTER_ONLY` — the module declares this itself as `NON_INTEGRE` |
| Behaviour | `generate()` **always refuses**, naming exactly what is missing |
| Tests | within `tests/media/` — 483 tests, 20 files |
| Dependencies | none added; the adapter imports nothing external |
| Limitations | licence never inspected (proxy refuses it); no GPU |
| **Classification** | **KEEP** |

`generate()` raising rather than returning a placeholder is the deliberate
choice the project report records: *a placeholder is indistinguishable from a
generation that silently failed*. Nothing in this programme should change that.

### The generation contract that already exists

`src/media/providers/base.py` declares the task vocabulary:

```
text_to_video, image_to_video, video_to_video, text_to_image, upscale, interpolate
```

**This is the vocabulary a new provider declares into.** It is six tasks, not
twenty interfaces — ADR-024's decision that tasks are data, not subclasses.

### Video systems classified

| Component | Classification | Why |
|---|---|---|
| `media/providers/base.py` | **KEEP** | The contract everything else extends |
| `media/providers/wangp.py` | **KEEP** | Honest refusal; removing it removes the record of *why* video is blocked |
| `media/story/`, `motion/`, `timeline/`, `adapt/`, `qc/` | **KEEP** | 10 stages `READY`; none depends on a generation provider |
| `creative/providers.py`, `routing.py`, `pipelines.py` | **EXTEND** | Where a new provider is declared and routed |
| `media/readiness.py` | **ADAPT (carefully)** | Naming a new provider module here moves a public verdict |
| Anything | ~~REPLACE~~ | **No evidence for any replacement was found** |

---

## M01.2 — reference, identity and audio systems

### Reference and identity (built by C05, C06, C11)

| Module | Lines | What it holds |
|---|---|---|
| `creative/reference/entity.py` | 525 | `ReferenceEntity`, entity types beyond human, source media |
| `creative/reference/ingestion.py` | 383 | Media analysis, and what it refuses to extract |
| `creative/reference/memory.py` | 327 | Privacy levels, sharing, revocation |
| `creative/reference/consent.py` | 303 | Scope, retention, revocation, platform refused as consenter |
| `creative/verification.py` | 553 | Identity dimensions, drift, `NOT_MEASURABLE` |

**§9–§17 are already built.** This programme verifies them; it does not rewrite
them.

### What reference ingestion can actually measure here

| Probe | State |
|---|---|
| `image_analysis` | **AVAILABLE** |
| `video_decode` | DEGRADED |
| `audio_decode` | UNAVAILABLE |

| Measurable today | Blocked |
|---|---|
| `dimensions`, `aspect_ratio`, `dominant_colours` | `facial_characteristics`, `body_characteristics`, `geometry`, `motion_characteristics` |

This is the honest state of §10's real-person pipeline: **the ingestion stage
runs and extracts what an image genuinely yields, and refuses the four fields
that would need face and body analysis.** Identity verification reports seven
dimensions, all `NOT_MEASURABLE`, none carrying a value.

So §16's "SCORE → CONFIDENCE → DEVIATION REPORT" cannot be produced here, and
the engine says so rather than producing one. **No provider integration changes
that** — it needs a face/landmark capability, not a video generator.

### Audio systems

| Module | State |
|---|---|
| `media/audio/music.py` | READY |
| `media/audio/sound_design.py` | READY |
| `media/subtitles/cues.py` | READY |
| `media/transcription/words.py` | present; refuses estimated timings |
| Speech recognition | **UNAVAILABLE** (probe measured) |
| Speaker diarization | **BLOCKED** — no module, and pyannote needs `torch` + a gated licence |
| Speech synthesis (TTS) | **ABSENT** — nothing implements it; no installation fixes it |
| `creative/voice/scene.py` | READY — original audio preserved by default (§24) |

**§26's audio provider abstraction is therefore partly moot today**: three of the
eight capability slots it names have no implementation to abstract over.

### The finding that matters most for M02

MoneyPrinterTurbo is documented as having a TTS system and a subtitle system.
This repository has **subtitles READY** and **speech synthesis ABSENT**.

If MPT's TTS turns out to be a wrapper around a third-party service, then what
it would add here is not "a video generator" but **the one stage nothing else
implements** — and that is a materially different integration argument than the
one the directive's title suggests.

**M02 must check this against source, not the README.** It is recorded as a
hypothesis, not a finding.

---

## Classification summary (§21)

| Verdict | Count | Components |
|---|---|---|
| **KEEP** | 8 | media contract, wangp, story, motion, timeline, adapt, qc, reference/identity |
| **EXTEND** | 3 | creative providers, routing, pipelines |
| **ADAPT** | 1 | media readiness (a public verdict) |
| **DEPRECATE** | 0 | — |
| **REPLACE** | 0 | **no evidence found for any replacement** |
| **UNKNOWN** | 1 | what MPT actually provides — M02 |
