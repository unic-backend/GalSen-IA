# L04.1 — LiveContextEngine architecture

Live Context Engine directive, **§5, §6, §13, §31 and §42**. Designed
2026-08-19, **after** the four audits and deliberately not before.

§46 is the sentence this design has to keep true: *Call.md is a research source
and an optional component. `LiveContextEngine` belongs to GalSen IA.*

---

## What the audits left to build

L02 answered §41's nine "do not duplicate" items: **six already exist**. L00 and
L02 also found that **two requirements the directive presents as new are already
implemented** — code-switching (`creative/language/switching.py`) and original
audio preservation (`creative/voice/scene.py`).

So the design covers four things, and no more:

```
src/live_context/
    state.py       LiveContextState, Observation — what is known, and how surely
    capture.py     the input surface, and the honest report of its absence
    fusion.py      ContextFusionEngine — combine without concluding
    readiness.py   per-stage state, computed, never written
```

**Everything else is a call into something that exists.**

---

## 1. `Observation` — nothing enters the state without a status

The directive's §6 lists twenty fields for `LiveContextState` and adds: *"Do not
assume all fields are always available. Each observation must contain
appropriate confidence/status."*

That sentence is the whole design. Every value in the state is an `Observation`,
never a bare value:

| Field | Meaning |
|---|---|
| `value` | what was observed, or `None` |
| `status` | `MEASURED` · `DECLARED` · `UNKNOWN` · `ABSENT` |
| `confidence` | `None` by default — **a number requires a basis** |
| `confidence_basis` | how the number was established; refused without it |
| `modality` | audio · screen · video · text · event |
| `provider` / `provider_version` | who produced it |
| `at` | when |

`confidence` follows the rule `research/sources.py` already enforces: **a value
cannot be set without saying how it was established**, and a basis without a
value is refused too.

**`ABSENT` is not `UNKNOWN`.** No microphone is `ABSENT` — measured, and it will
not change by waiting. An unidentified language is `UNKNOWN` — nobody knows yet.
Collapsing them would tell an operator to install something that would not help,
or hide something an installation would fix.

---

## 2. `LiveContextState` — rolling, append-only, and never self-promoting

A session's state holds observations, and **nothing in it promotes itself**.

Three rules, each inherited rather than invented:

1. **Conflicting observations stay distinguishable** (§13). Two providers
   disagreeing about a speaker are two observations, not an averaged one.
   `research/sources.py` already refuses to average sources; this does the same.
2. **A transcript segment never replaces the audio.** `voice/scene.py`'s
   `original_audio_path` is the source artefact; the state references it.
3. **Language is structured, not detected here.** Segments arrive labelled and
   `language/switching.py` derives switch points — it detects nothing, and this
   layer does not either.

The state is **not** a memory. Writing to memory is L11's decision, gated by
permission and consent.

---

## 3. `capture.py` — the layer whose job today is to say "no"

§7 lists eight inputs. L02 measured that **four cannot exist here**: no
`/dev/snd`, no `/dev/video*`, empty `DISPLAY`, no `ffmpeg` on `PATH`.

So the capture layer's first responsibility is **reporting its own absence**, in
the shape `media/readiness.py` already uses:

| Input | State here | How it is established |
|---|---|---|
| microphone | `ABSENT` | `/dev/snd` missing |
| system audio | `ABSENT` | same |
| camera | `ABSENT` | `/dev/video*` missing |
| screen | `ABSENT` | `DISPLAY` empty |
| uploaded audio | `AVAILABLE` | `services/file/` |
| existing media | `AVAILABLE` | `media/ingestion/` |
| text | `AVAILABLE` | — |
| external events | `AVAILABLE` | `routines/`, `proactive/` |

**Four of eight available makes §7's "determine dynamically which modalities are
available" testable rather than theoretical** — precisely because half are
missing.

**A capability is measured by interrogating the environment**, never by trusting
a flag. That is the media engine's rule, and the reason it caught an `ffmpeg`
built `--disable-everything` that answered `-version` like a complete one.

---

## 4. `ContextFusionEngine` — combine without concluding

§13 asks for fusion of audio, transcript, speakers, screen, video, text, user
context, tools and memory.

**Fusion here means assembling a view, not deciding a truth.** Concretely:

- observations are grouped by subject and kept side by side;
- a disagreement produces a **recorded conflict**, not a winner;
- an absent modality contributes `ABSENT`, not silence;
- **no observation is promoted by fusion.** `OBSERVED` stays `OBSERVED`; the
  ladder in `creative/language/observation.py` caps promotion at `CORROBORATED`
  and this layer does not exceed it.

The fusion result is a `LiveContextState`, and it carries the same
`NOT_MEASURED` honesty the research pipeline carries: a field nothing produced
is reported, never defaulted.

---

## 5. §31's five provider interfaces, answered with one

§31 proposes `LiveCaptureProvider`, `RealtimeTranscriptionProvider`,
`ScreenUnderstandingProvider`, `MediaContextProvider` and
`RealtimeContextProvider`.

**Four of the five duplicate something.** ADR-032 argued for a fourth provider
declaration and the argument had to be strong; a fifth needs at least as much.

| §31 proposes | Verdict |
|---|---|
| `RealtimeTranscriptionProvider` | **reuse `multimodal.TranscriptionProvider`** — it exists, with `TranscriptionUnavailable` as an enum of reasons |
| `MediaContextProvider` | **reuse `media/providers/`** and the creative registry |
| `RealtimeContextProvider` | **not a provider** — it is `LiveContextEngine` itself |
| `ScreenUnderstandingProvider` | **deferred to L10**, and constrained: ADR-018 refuses screen captures leaving the machine **unconditionally** |
| **`LiveCaptureProvider`** | **genuinely new** — nothing abstracts a capture device |

**One new provider concept, not five.**

---

## 6. Where the existing architecture is called, not copied

| Concern | Called |
|---|---|
| Transcription | `multimodal/registry.py`, `whisper_provider.py` |
| Code-switching | `creative/language/switching.py` |
| Original audio | `creative/voice/scene.py` |
| Trust boundary | `security/trust.py` — every live input is `EXTERNAL` |
| Provider privacy | `creative/canvas/privacy.py` |
| Provenance | `creative/jobs.py` (artefacts), `acquisition/` (facts) |
| Memory | `memory_engine/` |
| Summaries | `document_intelligence_engine/extractive_summarizer.py` |
| Nudges | **`src/proactive/`** — §20 would be it written twice |
| Agent loop | `agent/` + `router/` |
| MCP | `mcp/client.py`, `exposure.py` |
| Model routing | `model_engine/` + `derogations.py` |

---

## 7. The constraint that is not this programme's to lift

**ADR-014** — no external model at runtime. **ADR-018** — screen captures,
user content and training exports refused *whatever the configuration says*.

L01 measured that VideoDB carries capture, transcription **and** inference inside
Call.md. So the architecture is designed for **option B** (§26): existing
providers, local by default.

**Nothing here assumes an ADR amendment**, and nothing here proposes one. If the
owner amends ADR-014 or ADR-018, a `LiveCaptureProvider` pointing at a hosted
service becomes possible; until then it is `BLOCKED`, and the code says so
rather than the documentation.

---

## 8. What this design refuses

- **No second nudge engine, agent loop, memory, MCP orchestration, database or
  summary engine** (§41).
- **No fabricated transcription or translation** (§10). Unidentified language →
  `UNKNOWN`.
- **No silent recording, retention, upload, indexing or sharing** (§28).
- **No "real-time" claim without a measurement** (§33). Today: `NOT_MEASURED`.
- **No screen content treated as instruction** (§12, §29).
- **No live context becoming creative intent by itself** (§23) — the
  `CreativeEngine` decides what is relevant, and L12 wires the input, not the
  decision.

---

## What L04.2 records

ADR-033 fixes: four modules, one new provider concept, `Observation` carrying
its own status, `ABSENT` distinguished from `UNKNOWN`, fusion that records
conflicts instead of resolving them, and the ADR-014/ADR-018 constraint stated
as a boundary rather than a problem to route around.
