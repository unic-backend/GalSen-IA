# Universal Media Intelligence Engine — phase plan

Programme: **GALSEN AI — UNIVERSAL MEDIA & VIDEO INTELLIGENCE ENGINE**
(owner directive, 42 sections). Baseline `1300a99`, 4864 tests, `ruff` clean.

**Cadence**: two volets per turn, as agreed for the previous programmes.
Nothing is executed until the plan is confirmed.

---

## What the audit measured (directive §39, before planning)

Read in the repository, not assumed. **Three sections of the directive are
already built here and must not be rebuilt.**

| Directive asks for | Already exists | Consequence |
|---|---|---|
| §12 transcription | `src/multimodal/` — provider interface, registry, Whisper adapter (VOLET 32, ADR-015 shape) | The media engine **calls** it; it does not open a second transcription path |
| §4 visual analysis | `src/vision_intelligence_engine/` — 16 modules, OpenCV 5.0 + Pillow 12.3, working | Frame analysis composes these; no second vision engine |
| §10/§35 provider registry | `src/model_engine/providers/`, `model_selector.py`, `capability_detector.py` | Video providers follow the same interface/registry shape |
| §24 agent tools | `src/tool/` (`capabilities.py`, `authorization.py` with `DataScope`/`Effect` ceilings) | Media tools declare capabilities; ceilings already gate them |
| §26 repair | `src/agent/` self-healing harness | Reused as-is, never modified |
| §30 security | `src/security/trust.py`, `isolation.py`, `redaction.py` | External media is data with an origin — the boundary already exists |
| §31 provenance | `src/acquisition/manifest.py`, entity provenance discipline | Asset provenance follows it |
| §18 persistence | ADR-005 (`GALSEN_STORAGE_BACKEND`, `GALSEN_DATA_DIR`) | Project manifests select their store the same way |
| §28 resumability | `src/router/workflow_checkpoint.py` | A render job resumes on the existing checkpoint machinery |
| §29 API | `src/api/server.py`, 124 routes, RBAC | Media routes join it |

**Genuinely absent:** a job **queue** (no `Queue`/`JobStatus` class anywhere in
`src/`), a project manifest, a timeline model, a motion-design layer, an asset
registry, media skills, and media QC.

### Measured environment constraints — these shape the plan

| Dependency | State here | Measured by |
|---|---|---|
| `ffmpeg` / `ffprobe` | **absent** | `which ffmpeg` → not found |
| `torch` | **absent** | `import torch` → ModuleNotFoundError |
| GPU / CUDA | **absent** | no `nvidia-smi` |
| `whisper` / `faster_whisper` | **absent** | `import whisper` → ModuleNotFoundError |
| OpenCV / Pillow | **present** | `cv2 5.0.0`, `PIL 12.3.0` |

So the deterministic media layer (§3: duration, FPS, codec, waveform, keyframes)
and generative video (§10, §11) **cannot execute in this environment**. That is
not a reason to fake them, and not a reason to skip them: it is the reason the
engine is built as **adapters with capability probes**, exactly like ADR-014's
model independence and `src/integration/degradation.py`.

Every stage produces structured intermediate data (§2), every unavailable
capability **reports its state** and never returns a plausible result, and the
test suite runs on deterministic fixtures and stubs — which §32 explicitly
requires ("do not depend on expensive generative inference for the entire test
suite").

The honest end state, in the same shape Darra J reached:

> **ENGINE READY — MEDIA RUNTIME DEPENDENCIES PENDING** (ffmpeg, GPU, models)

---

## The 20 volets, and their phases

```
M01  Integration map & capability probes (§39, §27)     → 1 phase   ✅
M02  Project core, manifest, versions, memory (§18,§38) → 2 phases
M03  Ingestion & media probe adapters (§3)              → 2 phases
M04  Analysis, scenes, structured representation (§4)   → 2 phases
M05  Transcription & word alignment (§12, reuse V32)    → 1 phase
M06  Deterministic timeline & auto-editing (§5)         → 2 phases
M07  Story intelligence & scene planner (§6, §7)        → 2 phases
M08  Motion design & render backends (§8, §9)           → 2 phases
M09  Video providers + WanGP adapter (§10,§11,§35,§36)  → 2 phases
M10  Audio, sound design, music (§12, §13, §14)         → 2 phases
M11  Subtitle intelligence (§15)                        → 1 phase
M12  Asset registry, licence, provenance (§16, §31)     → 1 phase
M13  Media skills & style memory (§17, §19)             → 1 phase
M14  Quality control & final render verification (§20)  → 2 phases
M15  Multi-format & multilingual adaptation (§22, §23)  → 1 phase
M16  Job queue, progress, cancellation, resume (§28)    → 1 phase
M17  Agentic media tools & natural language (§24, §25)  → 2 phases
M18  API surface & security boundary (§29, §30)         → 2 phases
M19  Tests, benchmarks, readiness report (§32,§33,§40)  → 2 phases
M20  Media Studio UI (§34, conditional on `src/web/`)   → 1 phase
```

**Total: 32 phases.** Completed: 1.

---

## The rules this programme is built on

Taken from the directive and from what this repository already enforces.

1. **The LLM never does what a deterministic tool does better** (§1). It decides
   *what* stays; the analysis layer decides *where* the cut can safely land.
   No model invents a timestamp.
2. **Render success is not production success** (§21). A finished encode is
   inspected, validated and compared before anything is called done.
3. **An unavailable capability reports its state** — never a plausible result.
   A fabricated transcript is put in someone's mouth; a fabricated benchmark is
   worse than no benchmark (§33).
4. **External media, filenames, prompts, subtitles and metadata are data**, never
   instructions (§30) — the existing trust boundary, not a second one.
5. **Provenance is never fabricated** (§31), and generated content stays
   distinguishable from sourced content.
6. **Nothing existing is rebuilt** (§39), and the self-healing harness, the
   security boundary and the tests are never weakened (§26, §42).

---

## What M01 found

`docs/media/integration-map.md` holds the full map. The finding that shaped the
module: a `which ffmpeg` boolean would have been wrong **in both directions** —
absent from the PATH here, yet present under `PLAYWRIGHT_BROWSERS_PATH` as a
`--disable-everything` build that answers `-version` like a full one.

Two distinctions cost a real failure each, both found by **running** an encode
rather than reading a configuration string:

- `image2` (numbered files on disk) is not `image2pipe` (frames on stdin). Only
  the second exists here, so a `-i frames/%04d.png` command never opens its
  input. A substring match conflated them — the approximate-matching mistake
  `find_country` already cost this repository once. Names are read by token now.
- **Encoding PNG is not decoding PNG.** This build has a PNG encoder and no PNG
  decoder: piping PNG frames fails, piping JPEG frames produces a valid WebM.
  `frame_pipe_format()` therefore names the format to produce, because failing
  at the last step wastes all the rendering work before it.

`frame_encode` is **AVAILABLE and verified by producing a real file** — the
motion-design path (§8, §9) renders and encodes video on this machine today.

An existing guard caught the new code immediately: `tests/test_requirements.py`
refused `torch` and `playwright` as imported-but-undeclared. They are now
tolerated with the reason (their absence *is* the measured signal) and the
counter-test was extended so that tolerance cannot become permanent.

---

**Next**: VOLET M02 — project core, manifest and versions. Then stop.
