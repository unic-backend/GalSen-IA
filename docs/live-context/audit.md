# L00 — what GalSen IA already owns for live context

Live Context Engine directive, **§1**. Measured on 2026-08-19 at `2bc3c33`, by
reading the code and the ADRs — not by recalling them.

§1's instruction is literal: *"Determine what already exists"*, classify it, and
**do not modify implementation during the first reconnaissance stage.** Nothing
was modified.

Classification: **EXISTING / EXTENSION_REQUIRED / NEW_COMPONENT_REQUIRED /
DUPLICATE / DEPRECATED / UNKNOWN**.

---

## The finding that reshapes the programme

**Two accepted ADRs already decide most of what §12 and §26 propose to
evaluate**, and one of them refuses part of it *unconditionally*.

**ADR-014 — Model Sovereignty**: *GalSen IA depends on no external model at
runtime.*

**ADR-018 — Sovereign by default, with a scoped derogation** (option B, decided
by the owner). A derogation is **configuration, never a request parameter**, and
three categories are refused **whatever the configuration says**:

| Refused unconditionally | The ADR's reason |
|---|---|
| Any request carrying **user memories, files or knowledge content** | ADR-010 makes these a subject's property |
| **Screen captures** | *"An image of someone's screen is the most revealing payload the platform will ever hold"* |
| Training-data export | a cloud path must not bypass a human decision |

What remains eligible is *"stateless reasoning on text the platform itself
produced"*.

### What that means for this directive, stated rather than worked around

- **§12 (screen context) cannot send a screen capture to any hosted provider.**
  Not as an option, not with a flag, not with consent — ADR-018 refuses it
  unconditionally. Screen understanding here is **local or absent**.
- **§26 (VideoDB) is not an open evaluation.** Its own three options are
  A (VideoDB as optional provider), B (existing providers), C (hybrid).
  **Option A collides with ADR-014 and ADR-018** for live audio, because live
  audio is a user's voice, and `multimodal/whisper_provider.py` already states
  the reasoning in its own docstring: a hosted transcription service *"would
  receive users' voices — their timbre, their language, what they say at
  home… a more intimate export than a text prompt"*.

**This is documented, not decided.** §0 of the directive and
`.claude/rules/spec-driven-governance.md` both say the same thing: a conflict
with an existing architectural rule stops the work and is written down; the ADR
is amended first, by its owner, or the design stays inside it. **L03 and L13
inherit this constraint**; L00 does not resolve it.

---

## L00.1 — perception, models, agents, tools

| §1 asks about | Status | Where, and what it does |
|---|---|---|
| **Speech recognition** | **EXISTING** | `src/multimodal/whisper_provider.py` — `faster-whisper` preferred over `openai-whisper` for a measured reason (same model on CTranslate2, ~4× faster on CPU). Local by design, ADR-014. |
| Transcription contract | **EXISTING** | `multimodal/interfaces.py` — `TranscriptionProvider`, `TranscriptionResult`, `TranscriptionProviderInfo`, and `TranscriptionUnavailable` as an **enum of reasons** |
| Transcription registry | **EXISTING** | `multimodal/registry.py` — `set_transcriber`, `active_transcriber`, `transcription_status()` |
| **Speaker diarization** | **NEW_COMPONENT_REQUIRED** | `pyannote-audio` is a *declared candidate* in `corpus/creative/providers.yaml` (MIT repo, weights `UNKNOWN`), never implemented |
| Streaming | **EXTENSION_REQUIRED** | `model_engine/stream_handler.py` — `SimpleStreamHandler` streams **model responses**, not audio frames |
| **Live capture** (mic, system audio, camera, screen) | **NEW_COMPONENT_REQUIRED**, and **BLOCKED here** | no `/dev/snd`, no `/dev/video*`, empty `DISPLAY`, `ffmpeg` not on `PATH` — all four measured |
| Agents / agent loop | **EXISTING** | `src/agent/` (runtime, context, base agent), `src/router/` (dispatch). §15 must not add a second one |
| **MCP** | **EXISTING** | `src/mcp/` — `server.py`, `client.py` (refuses to connect to anything, and defends against **tool poisoning** first), `exposure.py` (a deliberate subset, not all 24 tools) |
| Tool execution | **EXISTING** | `src/tool/`, `tools/tools.yaml` — 24 declared, 13 unattended |
| ModelRouter | **EXISTING** | `model_engine/model_manager.py`, `provider_selector.py`, `derogations.py` |
| Provider registries | **EXISTING, four** | creative, media, `model_engine`, research |
| **Proactive observation** | **EXISTING** | `src/proactive/` — `observations.py`, `detectors.py`, `journal.py`, `scan.py`. **A detector that cannot measure says nothing**, and a dismissed suggestion does not return unless the evidence fingerprint changed |
| Routines | **EXISTING** | `src/routines/` — registry, journal, safety |
| Summarisation | **EXISTING** | `document_intelligence_engine/extractive_summarizer.py`, `DocumentSummarizer` |
| Video generation | **EXISTING, and refusing** | `src/media/providers/` — both adapters blocked (K00, M02) |
| CreativeEngine chain | **EXISTING** | `src/creative/` — representation, world, direction, reference, verification, canvas |
| **Event bus** | **UNKNOWN** | no dedicated bus found. `proactive/` and `routines/` each keep a journal; `media/queue/jobs.py` holds a job queue. L02 establishes whether §13's fusion needs one or reuses these |

### The most important reuse, and the trap beside it

**`NudgeEngine` (§20) would be `src/proactive/` written twice.** That module
already implements rate limiting by evidence fingerprint, non-repetition of
dismissed suggestions, and the rule that *a detector which cannot measure says
nothing rather than assuming*. §41 forbids the duplicate explicitly.

The same applies to §15's `LiveAgentLoop` against `src/agent/` + `src/router/`,
and to §22's summarisation against
`document_intelligence_engine/extractive_summarizer.py`.

---

## L00.2 — storage, security, privacy, provenance, operations

| §1 asks about | Status | Where |
|---|---|---|
| API | **EXISTING** | `src/api/server.py`, **142 routes**, versioning (ADR-011) |
| Database / storage | **EXISTING** | `src/storage/`, SQLite via `GALSEN_STORAGE_BACKEND` (ADR-005), one file-storage design (ADR-016) |
| Authentication | **EXISTING** | API key or JWT (ADR-029), `src/auth/` |
| Authorization | **EXISTING** | `src/api/rbac.py`, with `PERMISSIONS_HORS_PLATEFORME` |
| **Security boundary** | **EXISTING** | `src/security/trust.py` — seven levels; external content is data, hostile by default. §29 **is** this module |
| Sandboxing | **EXISTING** | `src/sandbox/`, ADR-017 (the computer agent is tools, not a new architecture) |
| SSRF guard | **EXISTING** | `src/research/safety.py` (R06) — literal **and** resolved addresses |
| **Privacy per provider** | **EXISTING** | `src/creative/canvas/privacy.py` — `data_destination`, `UNKNOWN` failing safe to `EXTERNAL` |
| Consent | **EXISTING** | `src/creative/reference/` — consent on reference entities |
| **Provenance** | **EXISTING, twice** | `src/acquisition/` (facts), `src/creative/jobs.py` (artefacts). §30 says reuse; §41 forbids a third |
| Memory | **EXISTING** | `src/memory_engine/` — short-term, long-term, user, session |
| Knowledge status ladder | **EXISTING** | `OBSERVED → CANDIDATE → CORROBORATED`, capped |
| Notifications | **EXISTING** | `src/services/notification/` |
| Jobs / queues | **EXISTING** | `src/media/queue/jobs.py`, `src/creative/jobs.py` |
| Observability | **EXISTING** | `src/observability/trail.py` — one job followable end to end |
| Self-healing | **EXISTING** | `src/agent/self_healer.py` — `diagnose`, `propose_patch`, `apply_patch`, `run_validation`, `rollback` |
| Tests | **EXISTING** | **6 582 passing**, 318 files, 1 failing (`v0.1.0`) |
| Frontend | **EXISTING, minimal** | `/ui` buildless dashboard (ADR-008), `/ui/studio.html` |

### What §28 asks for, and what already answers it

§28 lists recording, microphone, screen, camera permissions, processing consent,
retention, deletion, export and sharing controls.

**The consent machinery exists** (`creative/reference/`), and the **privacy
policy per provider exists** (K07). What does **not** exist is a permission
model for *capture devices* — because no capture device exists here. That is
`NEW_COMPONENT_REQUIRED`, and it is also the one part of §28 that cannot be
tested against reality in this environment.

---

## What L00 concludes

**Most of §1's list already exists.** The pattern holds for a fourth programme
running: the directive assumes a platform with less than it has.

Three things are genuinely new, and they are the programme's real content:

1. **`LiveContextState` and `ContextFusionEngine`** (§6, §13) — no equivalent.
2. **A capture layer** (§7) — no equivalent, and **blocked in this
   environment**: no microphone, no camera, no screen.
3. **Speaker diarization** (§9) — declared as a candidate, never implemented.

Two things look new and are not: **`NudgeEngine` is `src/proactive/`**, and
**`LiveAgentLoop` is `src/agent/` plus `src/router/`**.

And one thing is not an open question at all: **whether a hosted service may
receive live audio or a screen capture is already decided by ADR-014 and
ADR-018** — the second refusing screen captures unconditionally. L03 records
the licence and dependency consequences; amending an ADR is the owner's
decision, not this programme's.
