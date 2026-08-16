# Universal Media & Video Intelligence Engine — final report

Programme: **GALSEN AI — UNIVERSAL MEDIA & VIDEO INTELLIGENCE ENGINE**, owner
directive, 42 sections. **20 volets, 32 phases, all completed.**
Phase-by-phase record and the findings behind each decision →
`docs/media/phase-plan.md`. Integration audit → `docs/media/integration-map.md`.

The thirteen points below are the ones §42 asks for, in its order.

---

## 1. Files created

**Engine — `src/media/`, 26 modules (10 508 lines with their reasoning):**

| Area | Modules |
|---|---|
| Core | `core/capabilities.py`, `core/project.py`, `core/store.py` |
| Ingestion | `ingestion/identify.py`, `ingestion/inspect.py` |
| Analysis | `analysis/scenes.py`, `analysis/scene_model.py` |
| Transcription | `transcription/words.py` |
| Timeline | `timeline/edit_plan.py`, `timeline/verify.py` |
| Story | `story/structures.py`, `story/planner.py` |
| Motion | `motion/scene.py`, `motion/render.py` |
| Providers | `providers/base.py`, `providers/wangp.py` |
| Audio | `audio/sound_design.py`, `audio/music.py` |
| Subtitles | `subtitles/cues.py` |
| Assets | `assets/registry.py` |
| Skills | `skills/registry.py` |
| QC | `qc/checks.py` |
| Adaptation | `adapt/formats.py` |
| Queue | `queue/jobs.py` |
| Agent tools | `tools/catalog.py`, `tools/intent.py` |
| Security | `security/boundary.py` |
| Benchmarks | `benchmarks/harness.py` |
| Readiness | `readiness.py` |

**Tool surface:** `src/tools/media/tool.py` (`MediaTool`, `MediaGenerationTool`).

**Interface:** `src/web/static/studio.html`, `css/studio.css`, `js/studio.js`.

**Tests:** 21 files in `tests/media/`, **483 tests**.

**Documentation:** `docs/media/phase-plan.md`, `docs/media/integration-map.md`,
this report.

## 2. Files modified

| File | Change |
|---|---|
| `tools/tools.yaml` | Two declarations, `media` and `media_generation` |
| `src/api/server.py` | Eight `/media` routes and their models (+241 lines) |
| `src/web/static/js/api-client.js` | The `media` route group — the only module that knows a route |
| `src/web/static/index.html` | A link to the studio |
| `tests/test_web_ui.py` | The three source guarantees now run on **every** page, not one |
| `tests/test_tool_capabilities.py`, `tests/test_tool_authorization.py`, `tests/test_api_tool_capabilities.py` | Tool count re-measured 22 → 24 |
| `tests/test_personal_agent_assessment.py` | Active tools re-measured 21 → 23 |
| `tests/test_requirements.py` | `torch` and `playwright` tolerated **with a reason**, and the counter-test extended so the tolerance cannot become permanent |
| `CLAUDE.md`, `docs/architecture/overview.md`, `docs/architecture/personal-agent-assessment.md` | Published numbers brought back to what the repository serves |

No existing test was weakened. Four repository guards fired during the work and
all four were honoured by correcting the code or the document, never the test.

## 3. Architecture implemented

Ten declared capabilities, each **probed by interrogating the tool** rather than
by checking a binary exists — `src/media/core/capabilities.py`. Everything else
composes on top: adapters that report their state, and refuse rather than
degrade into a plausible answer.

Reused, not rebuilt (§39): `src/multimodal/` for transcription,
`src/vision_intelligence_engine/` for image analysis, `src/model_engine/providers/`
for the provider shape, `src/tool/` for capabilities and ceilings, `src/agent/`
for self-repair, `src/security/trust.py` and `src/agent/tools/workspace.py` for
the boundary, ADR-005 for storage, `src/router/workflow_checkpoint.py` for
`RunStatus`.

## 4. Media capabilities, measured on this machine

| Capability | State | Measured by |
|---|---|---|
| `frame_encode` | **AVAILABLE** | a real WebM written from piped MJPEG frames |
| `image_analysis` | **AVAILABLE** | OpenCV 5.0.0, Pillow 12.3.0 |
| `media_probe`, `video_decode`, `video_encode` | DEGRADED | an `ffmpeg` built `--disable-everything`, no `ffprobe` |
| `browser_render` | DEGRADED | a headless shell with no driver |
| `audio_decode`, `audio_analysis`, `transcription`, `gpu_compute` | UNAVAILABLE | no codec, no `whisper`, no CUDA |

Two distinctions each cost a real failure, both found by **running** an encode
rather than reading a configuration string: `image2` is not `image2pipe`, and
encoding PNG is not decoding PNG. A `which ffmpeg` boolean would have been wrong
in **both** directions here.

## 5. Model providers and adapters

`providers/base.py` selects on declared capability, measured VRAM and declared
cost. There is **no nearest match**: a provider that cannot serve the request is
refused with the reason, and an unknown cost or latency is excluded from the
ranking rather than treated as zero.

## 6. WanGP integration status

**`ADAPTER_ONLY`, and nothing was vendored** (§11). Three blockers are recorded
by name in `providers/wangp.py`: the licence has not been inspected, there is no
GPU here, and the repository is not vendored. `generate()` **always raises** —
it cannot return a placeholder, because a placeholder would be indistinguishable
from a generation that worked.

## 7. Editing, motion, audio and subtitle status

- **Editing** — a `Selection` carries a quote and a reason and has **no time
  field**: the structure makes it impossible for a model to supply a timestamp.
  Cuts land on measured word boundaries; an estimated timing refuses the plan.
  After a render the result is **re-transcribed and compared** mechanically, and
  with no re-transcription the verdict is `NOT_VERIFIED`, never "probably fine".
- **Motion** — deterministic Pillow rendering (no clock, no randomness, so two
  runs produce identical bytes) piped to a real encoder. Particles, masks and 3D
  are **named as not implemented** with the reason.
- **Audio** — sound effects are anchored to real timeline events and carry
  `derived_from`; music with `UNKNOWN` rights is refused, and beat alignment
  without a measured BPM is refused rather than approximated.
- **Subtitles** — cues never cross a measured scene boundary, `ë ñ ŋ` survive as
  CLAD letters rather than accents to strip, and a cue that runs too fast is
  **flagged, not stretched**.

## 8. Skills and media memory status

A correction becomes a **candidate** that does nothing. Promotion needs a named
validator who is not the platform — the identity check compares word by word,
because "ia" is inside "Mariama". Project scope and global scope are separate
promotions: "this worked for one client" and "this is how we work" are different
claims.

## 9. Automated QC status

Three outcomes, never two: `PASS`, `FAIL`, `NOT_CHECKED` — the last naming the
capability that would enable it. `PRODUCTION_SUCCESS` requires everything
applicable to pass **and** nothing to remain unchecked; otherwise `INCOMPLETE`.
The end-to-end test renders a real video and asserts the honest verdict for this
machine: video checks pass, audio checks `NOT_CHECKED`, verdict `INCOMPLETE`.

## 10. Tests before and after

| | Tests |
|---|---|
| Before (`1a586bc`) | **4864** passed, 8 skipped |
| After | **5369** passed, 8 skipped |
| Added by this programme | **505**, of which 483 in `tests/media/` |

`ruff check src tests` → clean. All fifteen test areas of §32 are mapped to the
files covering them, and each file is **verified on disk** by
`readiness.coverage_map()`.

## 11. Benchmark results

Measured on `Linux-6.18.5 x86_64`, 4 CPU, 15.7 GB RAM, **no GPU**,
Python 3.11.15, OpenCV 5.0.0, Pillow 12.3.0. Medians over five samples:

| Benchmark | Median | Range |
|---|---|---|
| `render` (12 frames → WebM, 1 sample) | 52.28 ms | — |
| `intent_to_plan` | 18.91 ms | 18.27–24.97 |
| `scene_detection` (24 frames) | 3.05 ms | 2.99–23.07 |
| `queue_throughput` (200 jobs) | 1.05 ms | 1.02–1.29 |
| `motion_frame` | 0.67 ms | 0.55–13.16 |
| `edit_plan` | 0.37 ms | 0.34–0.39 |
| `subtitle_segmentation` (120 words) | 0.26 ms | 0.25–0.34 |
| `transcription` | `NOT_MEASURED` | capability absent |
| `media_probe` | `NOT_MEASURED` | capability absent |

Nothing here is estimated. A benchmark whose capability is absent reports
`NOT_MEASURED` with the capability named — `0` would describe an instantaneous
operation, and an empty cell reads like a measurement that does not exist.

## 12. Known limitations

1. **Speech synthesis does not exist** (`VOICE`, `ABSENT`). Nothing in this
   repository turns text into voice. It is not a missing dependency and no
   installation will produce it; the planner's `voice` slot holds the text *to
   be said*, not its audio.
2. **No `ffprobe`, no full `ffmpeg`, no GPU, no `whisper` on this machine.**
   Six of the seventeen stages are `BLOCKED` on `media_probe`, `video_decode`,
   `video_encode`, `transcription` and `gpu_compute`.
3. **WanGP is an adapter with no implementation behind it** — by decision, until
   its licence is inspected and a GPU exists.
4. **Resource reservations are declarative**, never enforced: nothing here can
   stop another process from taking a GPU.
5. **The studio's JavaScript has no automated test runner** (ADR-008 already
   states this gap). It was rendered in headless Chromium during this volet and
   verified to display measured state; its source is pinned by tests, its
   behaviour is not.
6. **The chain has never run end to end on real footage**, because no capability
   on this machine can decode any.

## 13. Final system readiness

```
ENGINE READY — MEDIA RUNTIME DEPENDENCIES PENDING, 1 STAGE(S) NOT IMPLEMENTED (VOICE)

READY   10   IDEA · SCRIPT · STORYBOARD · MOTION_DESIGN · MUSIC · SOUND_DESIGN
             SUBTITLES · QUALITY_CONTROL · MULTI_FORMAT · MULTILINGUAL
BLOCKED  6   MEDIA_ANALYSIS · SCENES · VISUAL_GENERATION · VIDEO_GENERATION
             EDITING · FINAL_MASTER
ABSENT   1   VOICE
```

The verdict is **computed** by `src/media/readiness.py` on every call, from
modules checked on disk and capabilities checked by the probes. It is served at
`GET /media/capabilities`. A report whose conclusion is a constant says the same
thing the day the engine works and the day it does not — which is the failure
this entire programme was built to avoid.

---

## Next highest-value volet

**Installing a real `ffmpeg` build and `ffprobe`.** It is a single change
outside this repository and it moves five stages at once —
`MEDIA_ANALYSIS`, `SCENES`, `EDITING` (with a transcription backend),
`FINAL_MASTER` and `VISUAL_GENERATION`'s inspection path — from `BLOCKED` to
`READY`. Nothing inside the engine needs to be written for that to happen, which
is the point of having built it as adapters with probes: the day the capability
exists, the report changes on its own.

After that, in order of value: a **speech synthesis adapter** (the one stage
nothing implements), then **`ollama serve`** for the semantic paths, then
**WanGP's licence inspection** — which is a reading task, not an engineering one,
and blocks generation more firmly than the missing GPU does.
