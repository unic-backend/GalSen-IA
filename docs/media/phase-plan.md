# Universal Media Intelligence Engine — phase plan

Programme: **GALSEN AI — UNIVERSAL MEDIA & VIDEO INTELLIGENCE ENGINE**
(owner directive, 42 sections). Baseline `1300a99`, 4864 tests, `ruff` clean.

**Cadence**: two volets per turn, as agreed for the previous programmes.
**Status: complete — 20 volets, 32 phases.** Final report →
`docs/media/final-report.md`.

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
M05  Transcription & word alignment (§12, reuse V32)    → 1 phase  ✅
M06  Deterministic timeline & auto-editing (§5)         → 2 phases  ✅
M07  Story intelligence & scene planner (§6, §7)        → 2 phases  ✅
M08  Motion design & render backends (§8, §9)           → 2 phases  ✅
M09  Video providers + WanGP adapter (§10,§11,§35,§36)  → 2 phases  ✅
M10  Audio, sound design, music (§12, §13, §14)         → 2 phases  ✅
M11  Subtitle intelligence (§15)                        → 1 phase  ✅
M12  Asset registry, licence, provenance (§16, §31)     → 1 phase  ✅
M13  Media skills & style memory (§17, §19)             → 1 phase  ✅
M14  Quality control & final render verification (§20)  → 2 phases  ✅
M15  Multi-format & multilingual adaptation (§22, §23)  → 1 phase  ✅
M16  Job queue, progress, cancellation, resume (§28)    → 1 phase  ✅
M17  Agentic media tools & natural language (§24, §25)  → 2 phases  ✅
M18  API surface & security boundary (§29, §30)         → 2 phases  ✅
M19  Tests, benchmarks, readiness report (§32,§33,§40)  → 2 phases  ✅
M20  Media Studio UI (§34, conditional on `src/web/`)   → 1 phase  ✅
```

**Total: 32 phases. Completed: 32 — the programme is finished.**

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

## What M08 built — the first real video

`src/media/motion/scene.py` and `render.py`, 27 tests. This volet produces video
rather than describing it: `frame_encode` is the one capability measured
AVAILABLE here, and a 24-frame animation encodes to a real 6.7 kB WebM.

**A scene is entirely data, so a render is a pure function of it.** That is the
same demand as §8's "do not hardcode one visual style", stated twice: if the
description is data and the identity is data, the same input produces the same
bytes. Verified — two renders of the same frame are byte-identical, and two
visual identities over the same scene give different pixels with identical
structure. Without that property a quality control has nothing to compare.

**Time is a frame index at a declared rate.** Frame *n* is at exactly `n / fps`,
computed. A renderer that reads the wall clock produces a different video every
run, and nobody notices until two QC diffs are compared. Easing curves are
declared and an undeclared one is refused, because a hidden default easing is a
style decision made by whoever wrote the framework rather than whoever is making
the film.

**§9's browser pipeline is one backend, not the engine.** A media engine welded
to Chromium can only animate what a browser draws and inherits all of its
non-determinism — font substitution, subpixel AA, GPU rasterisation. So backends
are a registry: `pillow` is deterministic and available, `browser` is declared
and reports unavailable here (Chromium present, no driver), which is exactly how
an absent capability should look.

The encode path uses M01's measurement rather than the obvious command — frames
piped as MJPEG, because this ffmpeg reads `image2pipe` not `image2` and decodes
MJPEG but not PNG. And `render_video()` reports what was **written**, never a
verdict: an encoder exiting zero says nothing about what the file contains
(§21). A cross-check reads the output back through M03's identifier, so the two
volets verify each other.

What is not implemented — particles, masks, 3D, object tracking — is named with
its reason rather than implied.

---

## What M09 built

`src/media/providers/base.py` and `wangp.py`, 22 tests.

**The failure closed is the helpful selector.** Asked for 1080p and finding only
720p, it returns the 720p one — reasonably, and silently. The caller gets
something other than what they asked for with no way to notice. So
`select_provider()` returns a refusal listing why *each* provider was excluded,
and never a nearest match: a downgrade is a decision, and decisions belong to
whoever is making the film.

Three declarations are nullable and `None` never means zero: `min_vram_gb=None`
is "no GPU needed", not 0 GB; an unknown `cost_per_second` is **excluded** from
a cheapest-first ranking rather than sorted first, which is how a bill arrives;
an unmeasured latency is excluded from fastest-first, because inventing one
turns a queue estimate into a promise (§33). Required VRAM is compared against
*measured* VRAM, and unmeasurable means unavailable rather than "possibly fine".

### WanGP integration status — measured, not chosen

**`ADAPTER_ONLY`.** §11's own contingency clause is what applies, for two
independent reasons:

- **The licence could not be inspected.** §36 requires reading it before
  integrating. This environment's proxy refuses GitHub repositories outside the
  session scope — `api.github.com` answers *"GitHub access to this repository is
  not enabled for this session"*. So the licence is `UNKNOWN`, and that blocks
  on its own: vendoring code whose terms nobody read is a legal decision taken
  by a machine.
- **Nothing could run.** `gpu_compute` is UNAVAILABLE — no torch, no CUDA.

The repository is **not** copied into `src/` (a test asserts it). The listed
capabilities are what the public documentation describes, carried as
`capabilities_verified: False` — expectations, not measurements. `generate()`
refuses rather than writing a placeholder: a black slate encodes without error,
passes duration checks, and fails only in front of a viewer. When a GPU and a
reviewed licence exist, this one file gains an implementation and nothing else
in the engine changes — which is what "isolated behind an adapter" was for.

---

## What M10 built

`src/media/audio/sound_design.py` and `music.py`, 29 tests.

**"Do not randomly place sounds" (§12)** — and "randomly" is generous. What
actually happens is worse and looks better: a system places a riser "at the
reveal" by asking a model where it is, gets a confident 4.2 s, and drops the
sound there. It lands half a second before the cut every time, and the edit
sounds vaguely wrong in a way nobody can name in a review. So every cue carries
`derived_from` — the event that caused it and where that event's time came
from — and an event with no declared source is refused outright. An event no
sound family serves stays **silent and named**, because proposing a neighbouring
family is an editing decision.

Ducking is the one part of a mix genuinely computable without decoding audio: it
needs the speech regions, which come from M05's measured word timings. Windows
that touch are merged, since leaving them apart makes the music rise between two
words — audible as pumping.

**§14's ranking sentence is "never claim unknown copyright status", and it
outranks every analysis field.** Getting BPM wrong makes a video feel off;
getting this wrong produces a takedown, an invoice, or a client who cannot
broadcast what they paid for. So `UNKNOWN` **blocks use** rather than warning,
and "cleared" without a named licence is refused — writing it that way is what
ensures nobody looks again.

`audio_decode` is UNAVAILABLE here, so BPM, energy and vocal presence are `None`
with a reason and never 120. Section-to-scene sync still works, because it needs
only M04's measured scene boundaries; **beat** alignment is refused without a
measured BPM, since a supposed tempo puts every cut slightly off — audible
without being nameable.

---

## What M11 and M12 built

`src/media/subtitles/cues.py` and `src/media/assets/registry.py`, 33 tests.

**§15 names Wolof and Arabic, and each brings a constraint this repository
already knows.** `ë`, `ñ` and `ŋ` are letters of the CLAD standard, not accented
variants — Darra J paid for exactly this when the alias table kept only the
folded form and a display function returned `mbey` for `mbéy`. A subtitle is
display by definition, so folding stays on the matching side. Arabic runs
right-to-left, and direction is **declared per language** rather than sniffed
per string: a sentence mixing Arabic with a Latin proper noun flips on a
heuristic and holds on a declaration, and the declaration is what a translator
can argue with.

Cues are built from **measured** word timings, never cross a scene boundary — a
caption surviving a cut belongs to the shot it no longer covers — and a cue
exceeding the declared reading speed is **flagged, never extended**: stretching
it desynchronises it from the speech it captions, trading a visible problem for
an invisible one.

**§16's first sentence sounds like a style note and is not.** A generated logo
is nearly right — proportions drift, the colour is a shade off — so it passes
review, ships, and reaches the one person who knows that mark by heart, while
the brand's own file sat in the registry the whole time. So `resolve()` returns
`may_generate: False` for a protected kind whether or not the registry holds
one: if it does, use it; if it does not, ask the brand. A registered logo whose
rights are unknown does not unlock generation either — generating one would not
fix the rights problem, it would create a second.

Nothing enters without a source (§31): a sourced asset missing source, licence
or hash is *incomplete*, never usable. An `AI_GENERATED` origin is permanent,
not a label to clean up before delivery — the day someone asks whether a frame
was generated, the answer must come from the record.

---

## What M13 and M14 built

`src/media/skills/registry.py` and `src/media/qc/checks.py`, 38 tests.

**§17's binding rule guards a silent failure.** A client asks for larger
captions on a Tuesday; the system helpfully records the preference; three months
later a different client on another continent gets larger captions and nobody
can say why — the rule has no author, no date and no reason, so nobody can argue
with it either. So a correction becomes a **candidate**: visible, countable, and
doing nothing. Promotion requires a named validator who is not the platform
(same word-by-word identity check as Darra J — "ia" is inside "Mariama"). Scope
is the second guard: a project rule stays in its project, and reaching global
needs its own promotion, because "this worked for one client" and "this is how
we work" are different claims.

**§21 only survives if a check that could not run is impossible to confuse with
one that passed.** So there are three outcomes, never two: `PASS`, `FAIL`,
`NOT_CHECKED` — the last naming the capability that would enable it.
`PRODUCTION_SUCCESS` requires everything applicable to pass **and** nothing to
remain unchecked; otherwise `INCOMPLETE`, not "passed with notes". A pipeline
reporting "12 checks passed" when four never ran is more dangerous than one with
no checks: it produces a green report a human trusts instead of watching the
video.

The end-to-end test renders a real video and asserts the honest verdict for this
machine: video checks pass, audio checks are `NOT_CHECKED` for want of a codec,
verdict `INCOMPLETE`. An empty report is not a success either — it is the
absence of control.

---

---

## What M15 and M16 built

`src/media/adapt/formats.py` and `src/media/queue/jobs.py`, 34 tests.

**§22 ends on an instruction rather than a list: *do not simply crop*.** A centre
crop is one line, produces a file of exactly the right shape, and removes
whatever sat near the edges — in practice the logo, the lower third, and the
speaker's head when they are off-centre. Every dimensional check passes. So
placements are held in **relative coordinates** and repositioned inside the
target's safe area, and `centre_crop_survivors()` measures what the forbidden
one-liner *would* have lost. That second half is what makes the refusal
checkable instead of merely stated: the test asserts the logo survives reframing
and would not have survived the crop. An element too large for the safe area is
**reported, never shrunk** — reducing a logo changes a brand identity, and doing
it silently makes that change nobody's decision.

**§23's symmetrical temptation is quieter.** A translated line runs long, so the
cue is stretched to fit; it drifts from the picture it captions and every later
cue inherits the drift. Timing is copied **exactly**; a translation that will not
fit is flagged, because shortening a sentence is a translator's decision and
stretching a window is a decision nobody made. An untranslated cue stays
untranslated and is **named**: falling back to the source language hands the
Arabic viewer a French line with no way to tell whether that was intended.

**§28's first lie is progress.** Queues compute a percentage from elapsed time
against an estimate; it reaches 90 % and stays there, and what the user is
watching is an animation, not a measurement. Progress here is `done / total` of a
**counted** unit, and an unknown total reports `None` — not 0, and certainly not
90. Attempts are bounded and every one is kept with its error, because a job that
succeeded on attempt three is not a job that succeeded, and the difference is
what tells an operator something is wrong upstream. Cancellation is terminal.
None of that is a new vocabulary: `RunStatus` from
`src/router/workflow_checkpoint.py` already made `CANCELLED` terminal and
`RUNNING`/`FAILED` resumable, so this module reuses it — a second vocabulary for
the same idea drifts, and this repository has already paid for that four times.
Resource reservation is **declared, not enforced**: nothing here can stop another
process from taking a GPU, but an operator can see two jobs claiming the same
12 GB before both fail.

---

---

## What M17 and M18 built

`src/media/tools/` (catalog, intent), `src/media/security/boundary.py`, eight
`/media` routes in `src/api/server.py`, 67 tests.

**§24's real content is the last sentence: *the main AI should be able to chain
these tools.*** Chaining is where an agentic media pipeline fails, and it fails
quietly — a model asked for a video calls `render_video` before
`create_edit_plan`, the call is well-formed, its arguments are plausible, and
what comes back is a file nobody planned. The error surfaces three steps later
as "the render does not match the brief". So each tool declares what it
**consumes** and **produces**, and `plan_chain()` refuses the first link nothing
has fed, naming the tool that would have fed it. One consequence is worth
stating on its own: `create_edit_plan` consumes a *measured* transcript, so §5's
"no model invents a timestamp" is now structural rather than advisory.

Two registry declarations, not one. `media` reads someone's footage and writes
on this machine — the shape `memory` already had. `media_generation` sends that
footage to a provider, and user-private plus an external effect is the
exfiltration shape `src/tool/capabilities.py` refuses to run unattended. The
existing coverage guards fired on the new count and were **re-measured**, not
loosened: 22 → 24 declared tools, and the published route and tool numbers in
`CLAUDE.md`, `overview.md` and `personal-agent-assessment.md` were brought back
to what the repository actually serves.

**§25 fails at completion, not at parsing.** A request that says nothing about
duration gets 60 seconds; one that names no domain gets the first structure in
the table; and the plan that comes back describes a video nobody asked for —
convincingly, with a duration and a structure, so nobody questions it until
delivery. An unstated field is `UNSPECIFIED` and becomes a **question**, and no
tool chain is proposed while a question is open. Two domains in one sentence
("turn this **interview** into a **documentary**") are settled by a *declared*
marker or reported ambiguous — a declared rule can be argued with, a silent
first-match cannot.

**§30 said to reuse the boundary, so the traversal decision was not rewritten.**
`src/agent/tools/workspace.py` already resolves before judging, because
`a/b/../../../etc/passwd` is not detectable by spelling and a symlink inside the
root pointing at `/etc` is exactly what a prefix check misses. The media layer
gives it the media root and adds what is media-specific: a filename beginning
with `-` is refused, because to a codec that is an **option**, not a file. What
holds against arbitrary codec execution is not escaping — no shell is involved
anywhere in this engine — it is that the container and codec are fixed in the
code, and the report says so rather than claiming a protection that is not the
one working.

The boundary sits at the entry, not in the primitive: `render_video()` still
takes the path it is given, because a second gate would mean two rules about one
thing, and this repository has watched two copies of a rule disagree the day one
was fixed. Over HTTP, an absent capability answers `503` with what is missing,
a submitted render answers `202` (the queue accepted work, it produced nothing),
and a refused path is **named** in the refusal instead of being quietly
rewritten into one that resolves.

---

---

## What M19 built

`src/media/benchmarks/harness.py` and `src/media/readiness.py`, 29 tests.

**§33 ends on "never invent benchmark results", and nobody invents them on
purpose.** What actually happens is quieter: render time reads `0.0 ms` because
the renderer was skipped, transcription latency is `null` and prints as an empty
cell, GPU memory is `0` because no GPU answered. Each of those reads as a
measurement — the first describes a fast renderer, the last a machine under no
memory pressure, and both are false. So a benchmark whose capability is absent
returns `NOT_MEASURED` with the capability named, and is never coerced into a
number on the way out.

Two smaller decisions carry weight. The **median**, not the mean: one garbage
collection pause moves a mean and does not move a median, and reporting the mean
of five runs where one was 40× the others describes an event that happened once
as if it were normal. And the **machine travels with the number** — "scene
detection: 3 ms" is half a result. A bug found by running it: the registry calls
each benchmark with one positional argument, and `bench_queue_throughput` took
`jobs` first, so it measured three jobs while reporting two hundred.

Measured on this machine, `Linux-6.18.5 x86_64`, 4 CPU, 15.7 GB RAM, **no GPU**,
Python 3.11.15, OpenCV 5.0.0, Pillow 12.3.0 — five samples each:

| Benchmark | Median | Range | Samples |
|---|---|---|---|
| `render` (12 frames → WebM) | 52.28 ms | — | 1 |
| `intent_to_plan` | 18.91 ms | 18.27–24.97 | 5 |
| `scene_detection` (24 frames) | 3.05 ms | 2.99–23.07 | 5 |
| `queue_throughput` (200 jobs) | 1.05 ms | 1.02–1.29 | 5 |
| `motion_frame` | 0.67 ms | 0.55–13.16 | 5 |
| `edit_plan` | 0.37 ms | 0.34–0.39 | 5 |
| `subtitle_segmentation` (120 words) | 0.26 ms | 0.25–0.34 | 5 |
| `transcription` | `NOT_MEASURED` | capability `transcription` absent | — |
| `media_probe` | `NOT_MEASURED` | capability `media_probe` absent | — |

**The readiness report walks §40's seventeen stages and computes its own
verdict.** Each stage names the module implementing it — *checked on disk* — and
the capabilities it needs — *checked by the probes*. Three outcomes, and the
third is the one that matters: `ABSENT` is not `BLOCKED`, because a blocked
stage names something to install and an absent one names something to write.
Calling the first the second sends an operator looking for a package that was
never the problem.

Walking it found the thing the report exists to find: **speech synthesis does
not exist in this repository**. Nothing turns text into voice; the planner's
`voice` slot holds the text *to be said*, not its audio. It is reported `ABSENT`
with that reason rather than folded into the missing-dependency list.

```
READY   10  IDEA · SCRIPT · STORYBOARD · MOTION_DESIGN · MUSIC · SOUND_DESIGN
            SUBTITLES · QUALITY_CONTROL · MULTI_FORMAT · MULTILINGUAL
BLOCKED  6  MEDIA_ANALYSIS · SCENES · VISUAL_GENERATION · VIDEO_GENERATION
            EDITING · FINAL_MASTER   → media_probe, video_decode, video_encode,
                                       transcription, gpu_compute
ABSENT   1  VOICE
```

State, computed and not written: **`ENGINE READY — MEDIA RUNTIME DEPENDENCIES
PENDING, 1 STAGE(S) NOT IMPLEMENTED (VOICE)`**. It is served at
`GET /media/capabilities` beside the measured capability report, and the fifteen
test areas of §32 are mapped to the files covering them — each file verified on
disk, because a coverage table resting on a file that does not exist still reads
like coverage.

---

---

## What M20 built

`src/web/static/studio.html`, `css/studio.css`, `js/studio.js`, 13 tests.

**A studio is the easiest thing in this programme to fake.** A black frame with
a play button, a timeline of coloured blocks, a progress bar that climbs — all
of it draws in an hour and needs no engine at all, which is exactly the problem.
A person looking at those elements concludes the platform does what they show.

So every zone is driven by what the server measured. The preview names the
missing capabilities instead of exposing an empty player. The timeline stays
explicitly trackless while scene detection is blocked, and says why —
decorative blocks read as detected shots, and nobody can tell they are
decorative. A render with an unknown total shows "inconnu", never `0 %`, which
would read as started. An incomplete request shows its **questions**, because
`CLARIFICATION_REQUIRED` is an answer, not an error.

The existing architecture supported it without a new pattern (§34's condition):
static files under `/ui`, `api-client.js` as the only module that knows a route,
and a CSP allowing nothing but `self`. The three source guarantees of
`tests/test_web_ui.py` — no remote dependency, no direct `fetch`, no `innerHTML`
— now run on **every** page rather than one, because a guarantee checked on a
single page stops being one the day a second page appears.

**It was rendered, not assumed.** Headless Chromium
(`/opt/pw-browsers/chromium_headless_shell-1194`) loaded the page against a live
server and the dumped DOM carried the real state:

```
ENGINE READY — MEDIA RUNTIME DEPENDENCIES PENDING, 1 STAGE(S) NOT IMPLEMENTED (VOICE)
aperçu   : « Capacités absentes de cette machine : gpu_compute, media_probe,
            transcription, video_decode, video_encode. »
timeline : « Aucune piste : rien n'a été mesuré. SCENES : video_decode ·
            EDITING : transcription. »
```

---

## Programme complete

**20 volets, 32 phases on 32.** Final report in the thirteen points of §42 →
`docs/media/final-report.md`.
