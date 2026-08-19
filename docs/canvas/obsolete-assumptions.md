# K03.1 — assumptions the audits made obsolete

Creative Canvas directive, §5 and §7. Written 2026-08-19, after K00 (what the
platform owns), K01 (what the five repositories are) and K02 (what may lawfully
be used).

§5 asks which assumptions are now obsolete. An assumption is listed here only
when a measurement contradicts it — including assumptions carried by **the
directive itself**, and including one carried by **this plan**.

---

## 1. "The five repositories are component sources."

**Obsolete.** K01 classified them: **0 KEEP, 0 ADAPT, 3 REFERENCE ONLY,
2 REJECT.** K02 confirmed the number of lines and dependencies entering GalSen
IA is **zero**.

The reason is not quality. It is that four of the five are browser or Electron
applications in JavaScript or TypeScript, and this platform is Python and
FastAPI (ADR-001). "Adopting a component" would mean shipping a second runtime.

**What replaces the assumption**: they are *design references*, and the canvas
is built from ideas, not from files.

## 2. "Two of the five are MIT."

**False, and it was the directive's own statement.** `clearsolid/open-higgsfield-ai`
and `troy1471-sys/open-higgsfield` carry no licence on any of four filenames
across two branches, and declare `"private": true`. Absence of a grant reserves
every right.

**What replaces the assumption**: K02 is a gate, and it closed on two
candidates before a single idea was extracted from them.

## 3. "The two unlicensed repositories are two implementations to compare."

**Obsolete.** Their `index.html` and `src/main.js` are **byte-identical**
(SHA-256). One is a repackaging of the other. §2 D asks which implementation is
technically superior; that question has no answer for a pair where one is a copy.

## 4. "A canvas needs a node-graph engine, so pick one."

**Obsolete.** The only real implementation among the five is React Flow
(`@xyflow/react`) inside an Electron desktop application. There is no
server-side graph library to adopt, and there does not need to be: a node graph
is nodes, typed ports, and an edge legality rule. That is a data model, and this
platform's contribution is the *orchestration*, not the rendering.

**What replaces the assumption**: the graph is modelled server-side and exposed
through the API; how it is drawn is a client concern and stays out of scope.

## 5. "§11's fifteen registry types have to be built."

**Obsolete, and it was the most expensive assumption in the directive.** K00
measured the platform against §11's list: `ProviderRegistry` exists **twice**,
`ModelRegistry`, `GenerationRequest`, `ProviderCapability`, `ProviderLicense`,
`ProviderCost`, `ProviderLatency`, `ProviderAvailability` all exist as types or
as fields on `CreativeProvider` (fifteen fields) and `LicenceRecord` (six).

Exactly **one** is genuinely absent: **`ProviderPrivacyPolicy`**. And K01 found
the case that makes it concrete — `higgsfield-ai/skills` sends user media and
prompts to a third-party host, and nothing in this platform can currently
record that fact where a router could act on it.

**What replaces the assumption**: one new type, not fifteen. A third registry
would repeat M00.2's finding as a mistake instead of a lesson.

## 6. "Camera control is a prompt-engineering problem."

**Obsolete — and the platform already rejected it, before this programme
started.** `src/creative/direction.py` holds `DirectorSpec` with `shot_size`,
`camera_height`, `movement`, `lens_mm`, `depth_of_field`, `lighting`,
`blocking`, `gaze`, `transition_in` — ten declared vocabularies, each value
refused when it is not in its tuple. Golden scenario 17 already asserts it:
*"Mouvement de caméra : structuré, jamais un adjectif ajouté au prompt."*

K01 measured what the alternative looks like in practice. `Higgsfield-Open`
concatenates camera, lens, focal and aperture into one English sentence and
appends `"cinematic lighting"`, `"professional photography"`,
`"ultra-detailed"`, `"8K resolution"`.

**`cinematic` and `professional` are both already in this platform's
`ADJECTIFS_SANS_DECISION`** — the list of words `check_intent()` flags as
deciding nothing. The reference implementation's quality tags are, word for
word, what this codebase already refuses to treat as a decision.

**What replaces the assumption**: §10's `CameraSpec` / `LensSpec` / `ShotSpec`
is an **extension of `DirectorSpec`**, not a new parallel structure. K06 adds
what is missing — a camera body concept, aperture as a value rather than a
string, and the four signed motion axes — and renders to a provider-specific
prompt **at the edge**, never storing prose as the specification.

## 7. "Presets are a convenience."

**Obsolete.** `LENS_MOTION_PRESET` applies pan, tilt, zoom and dolly values the
user never requested, as a side effect of choosing a lens. That is §6's
prohibition — *GalSen IA must not invent creative content the user did not
request* — implemented as a feature.

**What replaces the assumption**: a preset may be **offered**; it may never be
**applied**. The distinction is the same one C05's required / optional /
forbidden split already draws, and K05 is where it becomes code.

## 8. "An unhandled value can fall back to a neutral default."

**Obsolete, with a measured example.** `FOCAL_PERSPECTIVE[focalLength] || ""`
turns a 40 mm lens into silence: no perspective description, no warning, no
trace. Three keys cover aperture; everything else vanishes the same way.

**What replaces the assumption**: §7's rule, which this platform already applies
everywhere else — `UNKNOWN` is reported, never converted into an assumption, and
never rendered as an empty string that reads like a decision.

## 9. "The canvas will have working Image and Video nodes."

**Obsolete.** K00 re-measured the media engine: 17 stages, **10 READY,
6 BLOCKED, 1 ABSENT**; both provider adapters refuse; four of the six blocks are
one missing `ffmpeg`. **Nothing in this platform can generate an image or a
video today.**

**What replaces the assumption**: a node reports its own state, the way
`src/media/readiness.py` does. A canvas whose nodes claim a capability no
measurement supports would be the largest fabrication either programme has come
near.

## 10. "The security posture is background context."

**Obsolete for this programme specifically.** Three of the seven gaps
`src/security/posture.py` reports are load-bearing here: a child process reads
and writes wherever the user can (a canvas accepts uploaded photographs), no
network cut exists without namespaces (a node calls an external provider), and
the approval gate is in memory (a consent decision does not survive a restart).

**What replaces the assumption**: these are constraints the design states, not
conditions it waits for. `GALSEN_STORAGE_BACKEND=sqlite` already moves the third
one; the first two are recorded as limits of the environment.

---

## One assumption this plan itself carried

`docs/canvas/phase-plan.md` ordered the work as *audit → design → code* on the
argument that copying a node graph first is how an orchestrator becomes a cage.
The audits changed which risk that ordering was protecting against.

The expected risk was **importing too much**. The measured risk is the opposite:
there is **nothing importable at all**, and the real hazard is *rebuilding what
already exists* — a third registry, a second camera specification, a fourth
provenance system. K00 named the trap and K03.1 confirms it is the live one.

The ordering was still right; the reason it was right has changed, and a plan
that keeps its original reason after the evidence moves is a plan nobody
re-read.

---

## What K03.2 has to design, reduced to what is actually missing

1. A **graph model**: nodes, typed ports, an edge legality rule, server-side.
2. A **trust level per node type** — `src/security/trust.py` has the seven
   levels; no node maps to one yet.
3. **`ProviderPrivacyPolicy`** — where a provider sends data, whether it
   retains it, whether local execution is possible.
4. **Node readiness reporting**, in the shape `readiness()` already uses.

Everything else §5 through §17 asks for exists. The canvas is a composition
problem.
