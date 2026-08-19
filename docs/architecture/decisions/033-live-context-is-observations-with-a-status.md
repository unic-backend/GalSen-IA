# ADR-033 — Live context is a set of observations carrying their own status, and capture reports its own absence

**Status**: accepted
**Date**: 2026-08-19
**Directive**: Live Context Engine / Call.md Integration, §5, §6, §7, §12, §13, §26, §31, §38, §41, §46
**Volets**: L00–L03 (evidence), L04 (this decision), L05–L15 (implementation)

## Context

The directive asks for a `LiveContextEngine` built with reference to
`video-db/call.md`, and forbids GalSen IA becoming a meeting application. Four
audit volets produced the evidence.

**Call.md does not record on Linux** (L01). Its own platform table states the app
*"will reject recording before launch because no capture binary is available"*;
the VideoDB capture SDK ships `darwin-arm64`, `darwin-x64` and `win32-x64` only.
GalSen IA runs on Linux.

**VideoDB is not an optional provider inside Call.md — it is the spine** (L01).
Capture, dual-channel transcription over WebSocket, and even LLM calls through
*"VideoDB's OpenAI-compatible API"*. Its `"Local-First"` claim covers **storage**
of settings, history and transcripts; it does not cover **processing**.

**Two accepted ADRs already decide §26 and §12** (L00). ADR-014: no external
model at runtime. ADR-018: the derogation is configuration rather than a request
parameter, and three categories are refused *whatever the configuration says* —
user memories/files/knowledge, **screen captures**, training-data export.

**Six of §41's nine "do not duplicate" items already exist** (L02):
transcription, memory, MCP orchestration, agent loop, database, summary engine.
And two requirements the directive presents as new are already implemented —
`creative/language/switching.py` (code-switching, structured and never guessed)
and `creative/voice/scene.py` (the original recording is the source artefact).

**This environment has no live input**: no `/dev/snd`, no `/dev/video*`, empty
`DISPLAY`, no `ffmpeg` on `PATH` — four measurements.

**Licensing is not the obstacle** (L03). 54 npm packages: 48 MIT, 5 Apache-2.0,
1 ISC, no copyleft — the cleanest tree of the five external projects audited
across four programmes. What blocks adoption is architecture, platform support
and sovereignty.

## Decisions

### 1. Four modules, and nothing else

`src/live_context/` — `state.py`, `capture.py`, `fusion.py`, `readiness.py`.

**Rejected**: a live memory, a live agent loop, a live summary engine, a live
nudge engine. §41 forbids each, and L02 measured that all four already exist.
`NudgeEngine` in particular would be `src/proactive/` rewritten — that module
already suppresses repetition by hashing the *evidence*, which is strictly more
precise than Call.md's two-minute cooldown, because a suggestion returns only
when the situation actually changed.

### 2. Every value is an `Observation` carrying its own status

Never a bare value. `status` is one of `MEASURED`, `DECLARED`, `UNKNOWN`,
`ABSENT`; `confidence` is `None` unless a `confidence_basis` says how it was
established, and a basis without a value is refused too — the rule
`research/sources.py` already enforces.

**`ABSENT` is not `UNKNOWN`, and this is the decision with the most daily
consequence.** No microphone is `ABSENT`: measured, and waiting will not change
it. An unidentified language is `UNKNOWN`: nobody knows yet. Collapsing them
would send an operator to install something that cannot help, or hide something
an installation would fix.

### 3. Fusion records conflicts; it does not resolve them

Two providers disagreeing about a speaker produce **two observations and a
recorded conflict**, not an average. An absent modality contributes `ABSENT`,
not silence. **Fusion promotes nothing**: `OBSERVED` stays `OBSERVED`, and the
ladder in `creative/language/observation.py` caps promotion at `CORROBORATED`
whatever the count.

### 4. Capture's first job is to report its own absence

Measured by interrogating the environment, never by trusting a flag — the media
engine's rule, which is why it caught an `ffmpeg` built `--disable-everything`
that answered `-version` like a complete one.

Four of eight inputs are `ABSENT` here and four are available. That makes §7's
*"determine dynamically which modalities are available"* testable rather than
theoretical, **precisely because half are missing**.

### 5. One new provider concept, not §31's five

| §31 proposes | Decision |
|---|---|
| `RealtimeTranscriptionProvider` | **reuse** `multimodal.TranscriptionProvider` |
| `MediaContextProvider` | **reuse** `media/providers/` |
| `RealtimeContextProvider` | **not a provider** — it is the engine |
| `ScreenUnderstandingProvider` | **deferred to L10**, and bounded by ADR-018 |
| `LiveCaptureProvider` | **new** — nothing abstracts a capture device |

ADR-032 argued for a fourth provider declaration; a fifth needed at least as
strong an argument, and only capture has one.

### 6. Option B, and no ADR is amended by this programme

§26's options: A (VideoDB as optional provider), B (existing providers),
C (hybrid). **A conflicts with ADR-014 and ADR-018** for live audio, and
unconditionally for screen captures. The architecture is designed for **B**.

**This ADR does not amend ADR-014 or ADR-018 and does not ask to.** If the owner
amends either, a hosted `LiveCaptureProvider` becomes possible; until then it is
`BLOCKED`, and **the code says so rather than the documentation**.

### 7. Live inputs are `EXTERNAL`, always

Speech, transcript, screen content, documents, tool results and model output
enter through `security/trust.py` at `EXTERNAL` — *hostile by default*. Screen
content never becomes an instruction. The caller cannot choose the level, the
same way `research/safety.as_data()` exposes no level parameter.

## Consequences

**Positive.** Four modules against twelve reused subsystems. No dependency added,
no second registry, no second memory. The two hardest representation problems —
code-switching and original audio — were already solved, so the design inherits
them instead of re-deciding them.

**Negative, stated rather than softened.** **Nothing can be captured here.** The
engine will plan, fuse, report and test, and it will produce no live session on
this machine. Capture latency, transcription latency, speaker-identification
latency and every other §33 figure will read `NOT_MEASURED`, and L05's slice must
report that rather than simulate it. A design can be built and tested; a
microphone cannot be invented.

**Neutral.** Call.md's ideas are taken — dual-channel separation as a
first-class concept, the transcript buffer, the split between live metrics and
post-session extraction, MCP intent detection separated from tool execution. Its
code is not, and not for licence reasons: there is no Python to take.

## What this ADR does not decide

- **Diarization** (§9) — still `NEW_COMPONENT_REQUIRED` after four programmes;
  `pyannote-audio` is declared with weights `UNKNOWN` because `huggingface.co`
  answers `403` here.
- **Screen understanding** (§12) — L10, inside ADR-018's unconditional refusal.
- **Memory writes** (§14) — L11, gated by permission and consent.
- **Whether live context becomes creative intent** (§23) — L12 wires the input;
  the `CreativeEngine` keeps the decision.
- **DNS-rebinding pinning** — Call.md closes a window `research/safety.py`
  declares open. Recorded in L01 as `OPTIONAL SUGGESTION — NOT IMPLEMENTED`; it
  belongs to the research layer.
