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
M02  Project core, manifest, versions, memory (§18,§38) → 2 phases  ✅
M03  Ingestion & media probe adapters (§3)              → 2 phases  ✅
M04  Analysis, scenes, structured representation (§4)   → 2 phases  ✅
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

**Total: 32 phases.** Completed: 12.

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

## What M02 built

`src/media/core/project.py` and `store.py`, 50 tests. §18's rule — *never
destroy previous versions* — is structural rather than a convention:

- **No delete method exists**, on the project or on either store. Not guarded:
  absent. A guarded delete is eventually called with the right argument.
- **A version is frozen**; a new state is an appended version derived from the
  previous one. A status change replaces the entry and leaves `content_hash()`
  identical — a change of state is not a change of work.
- **Identity and content are separate hashes**, and `created_at` stays out of
  the content hash. Darra J paid for that conflation once.
- **An artifact declares its origin.** A sourced artifact without source and
  licence is `provenance_complete: False` — incomplete, never "probably fine".
- **A correction is evidence, not a rule** (§17): recorded with its author,
  never promoted on its own.

Persistence reuses ADR-005 and adds no second switch. A round trip is lossless
or it fails: versions, statuses, artifacts, licences, corrections and content
hashes all survive, and a record with zero versions is refused rather than
repaired — fabricating one would hide the loss.

A fourth existing guard fired: `test_persistence_deployment.py` greps for the
literal backend-variable read and found it in this module's **docstring**, where
it was quoting the historical mistake. The guard's bluntness is what makes it
reliable, so the prose was rewritten rather than the test weakened.

---

## What M03 built

`src/media/ingestion/identify.py` and `inspect.py`, 27 tests. Two temptations
closed, each producing an error that **looks like a fact**.

**Trusting the extension.** Wrong for correctness — a file renamed once by a
well-meaning human is mislabelled forever — and wrong for safety (§30): the
filename is external input, so routing by extension routes by what an attacker
chooses. The extension is recorded as a claim, the signature is the evidence,
and a disagreement is *reported* rather than silently resolved either way.
Verified on real files produced by Pillow, and on the WebM the engine itself
encoded in M01. `webm` and `matroska` share a signature and are separated by
document type; `mp4` and `mov` share `ftyp` and are separated by brand.

**Filling missing fields with defaults.** `duration = 0.0` and `fps = 25` read
exactly like measurements, and the edit planner cannot tell the difference — it
would cut at second 12 of a file whose duration nobody read. So a field is
measured (with the tool named) or unknown (with the reason and the capability
that would supply it), never in between. `require_for_editing()` refuses rather
than computing on an absence.

Defect found by a test: the generic fallback loop **overwrote** the specific
reason, so a corrupt image reported "the capability would supply it" — which is
both wrong (`image_analysis` is available) and sends the operator looking in the
wrong place. The fallback now fills, it does not overwrite.

Also fixed: `tests/media/test_ingestion.py` collided with
`tests/darra_j/test_ingestion.py` — same basename, no `__init__.py`, so pytest
failed at collection in the full run while passing when run alone. Renamed to
`test_media_ingestion.py`.

---

## What M04 built

`src/media/analysis/scenes.py` and `scene_model.py`, 25 tests. This is §1 at its
sharpest and §4 at its most dangerous.

**Boundaries are measured, not proposed.** A model asked where the cuts are
answers with timestamps immediately and fluently, and they are invented. The
detector computes Bhattacharyya histogram distance between consecutive frames —
verified on real frames: within-shot distance ~0.01, cut distance 1.00, clean
separation. The declared threshold and the raw distances come back with every
result, so a disagreement is checkable rather than a matter of opinion.

**A boundary stays a frame index until an FPS is measured.** With no `ffprobe`
here there is none, so emitting `t = 2.4 s` from an assumed 25 fps would be a
fabricated timestamp wearing a measurement's clothes — and a cut placed on it
lands mid-word. Times appear only when someone measured the frame rate.

**`importance_score` is the field that invites a lie.** Every implementation
reaches for `0.5`, or asks a model for a float, and a number appears that reads
like a measurement. The auto-editor then sorts by it and drops the bottom; a
director asks why their best take was cut, and the honest answer is that a
default value sorted it last. So importance is composed of named measured
signals or it is `None` with the reason. A signal that was not measured
**contributes nothing** rather than contributing zero — and the score is
renormalised over the signals present, so missing measurements are reported
rather than punished.

Every scene field declares its origin (`MEASURED` / `AI_DERIVED` / `ABSENT`),
because merging a model's description and a detector's output into one
"analysis" blob destroys that distinction permanently.

---

## What M05 built

`src/media/transcription/words.py`, 16 tests. One shortcut closed, and it is the
most tempting in the whole engine.

A transcriber returns segments — *"il faut comparer deux fractions", 4.10 s →
6.30 s* — whose words are known but whose individual times are not. One line of
arithmetic spreads 2.2 seconds across five words and the result gets called word
timings. It even looks right on a waveform.

It is wrong exactly where it matters. Speech is not uniform: a speaker pauses,
stresses, hesitates. An interpolated boundary lands **inside** a word about as
often as between two, so a cut snapped to it removes half a syllable — audible
immediately to a listener, invisible to an engineer reading timestamps that look
measured.

So word timings are extracted only when the transcriber supplied them.
Interpolation remains available as an explicit opt-in, marked `ESTIMATED`, and
`safe_cut_points()` refuses it anyway — a single estimated word among measured
ones is enough to refuse, because that mixture is the dangerous case: it looks
mostly measured.

`snap_to_word_boundary()` is directive §1 made executable: the model says
roughly where, this module decides where the cut can actually land, moving it
into the nearest silence and reporting which word it would have crossed. With no
safe point it refuses rather than falling back on the requested instant — the
fallback would make exactly the cut the function exists to prevent.

Transcription itself is not reimplemented: `src/multimodal/` (VOLET 32) owns it,
and its rule is inherited — an audio file that cannot be transcribed is refused
out loud, never treated as silence.

---

## What M06 built — the pivot

`src/media/timeline/edit_plan.py` and `verify.py`, 28 tests.

**The interface has no shape in which a timestamp can be returned.** Every
implementation agrees with §1 and then breaks it in the same place: by defining
a response where the model returns `{"start": 4.2, "end": 9.8}`. Once that field
exists the rule is a comment — the model fills it fluently and nobody downstream
can tell an invented 4.2 from a measured one. A `Selection` carries a **quote
and a reason**, and nothing else. Same closure `pedagogy.explain()` uses in
Darra J.

Locating the quote is then exact. A near-match would keep words the model did
not choose while reporting success; a quote appearing twice is `AMBIGUOUS` and
refused, because picking the first occurrence silently keeps a different take
than the one that was reviewed — the "bad take selection" failure §5 asks to
detect, manufactured by the editor itself. A quote appearing nowhere means the
model cited a sentence never said, which is worth surfacing rather than
approximating away.

**Render success is not production success.** Everything upstream can be correct
and still produce a cut that removes the word "pas": the encoder reports
success, the file plays, the sentence says the opposite. Only re-reading the
words catches it. So `verify_render()` returns `NOT_VERIFIED` — never a pass —
when no re-transcription exists, and the comparison is mechanical: asking a
model whether two transcripts mean the same thing would replace a measurement
with an opinion produced by the same kind of system that made the error. What
the comparison cannot see (identical mishearing, prosody, picture) is named
rather than omitted.

Defect found while reviewing: `min_silence` was threaded through the boundary
computation and **decided nothing**. It now flags edges whose neighbouring
silence is too short — the cut stays between two words but close enough to clip
a consonant. Catching that before the render is worth a whole render; the
after-the-fact detection (`boundary_losses`) costs one.

---

## What M07 built

`src/media/story/structures.py` and `planner.py`, 32 tests.

**§6 lists a structure and then says not to force it.** That second sentence is
the volet, because the list — hook, context, argument, evidence, CTA — is a
**marketing** structure. Applied to a documentary it produces an advert with
archive footage; applied to a lesson, a sales pitch about photosynthesis. The
engine would not misbehave: it would do exactly what it was built to do, to
material that never asked for it.

So structures are declared per domain — documentary, education, news, interview,
sports analysis, scientific, marketing, social — and an undeclared domain gets
**no structure at all**. Falling back to the marketing shape is the named error
arrived at through a sensible-looking default. A call to action is a marketing
device, not a narrative universal, and is refused everywhere else: a documentary
that ends by asking viewers to subscribe has become an advert. Two roles are
domain-specific and load-bearing: `attribution` in news (information without a
source is not broadcastable) and `limitation` in scientific (a result without
its limits is an assertion, not science).

A role is filled with material that exists. An empty role is **named**, because
"this documentary has no evidence section" is a fact the director needs, and
generating a plausible one is how a machine starts writing the argument instead
of arranging it.

**The planner keeps two duration fields that never merge.** A `target_duration`
is a request, a `measured_duration` is a fact, and a scene planned at 8 s
holding 14 s of speech will overrun or cut someone off mid-sentence — reported
before the render, since noticing at render time costs a render.

And §7's "visual design should communicate ideas instead of repeating spoken
words" is treated as checkable rather than as taste: `check_redundancy()`
measures how much of the on-screen text is already in the voice. That failure is
invisible in a plan and obvious in a finished video.

---

**Next**: VOLET M08 — motion design and render backends (2 phases). `frame_encode`
is the one capability measured AVAILABLE on this machine, so this volet produces
real video. Then stop.
