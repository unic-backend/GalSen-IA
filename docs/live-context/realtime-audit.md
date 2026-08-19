# L02 — the real-time capabilities GalSen IA already has

Live Context Engine directive, **§7, §8 and §41**. Measured 2026-08-19.

§41 lists nine things not to build twice. This phase answers, for each, whether
it exists — because *"check whether GalSen IA already has one"* is only an
instruction if someone actually checks.

---

## §41 — the nine, checked

| Do not duplicate | Exists? | Where | Verdict |
|---|---|---|---|
| Transcription engine | **yes** | `multimodal/whisper_provider.py` + `interfaces.py` + `registry.py` | **EXTEND** |
| Speaker diarization | **no** | `pyannote-audio` declared in `corpus/creative/providers.yaml`, never implemented | **NEW_COMPONENT_REQUIRED** |
| Memory | **yes** | `memory_engine/` — short-term, long-term, user, session | **REUSE** |
| MCP orchestration | **yes** | `mcp/client.py`, `server.py`, `exposure.py` | **EXTEND** |
| Agent loop | **yes** | `agent/` + `router/` | **REUSE** |
| Database | **yes** | `storage/`, SQLite via `GALSEN_STORAGE_BACKEND` (ADR-005) | **REUSE** |
| Event bus | **no dedicated bus** | `proactive/journal.py`, `routines/journal.py`, `media/queue/jobs.py` | **UNKNOWN → L04 decides** |
| Context manager | **no** | nothing holds a rolling conversational state | **NEW_COMPONENT_REQUIRED** |
| Summary engine | **yes** | `document_intelligence_engine/extractive_summarizer.py` | **REUSE** |

**Six of nine already exist.** The programme's genuine content is therefore
three items: diarization, a context manager, and whatever `LiveContextState`
turns out to be.

---

## §8 — the audio pipeline, stage by stage

The directive's proposed chain, against what is here:

| Stage | State | Where |
|---|---|---|
| Audio capture | **ABSENT — no device** | no `/dev/snd`, measured |
| Voice activity detection | **ABSENT** | nothing found |
| Speaker segmentation | **ABSENT** | — |
| **Diarization** | **DECLARED, not implemented** | `pyannote-audio`, weights `UNKNOWN` (huggingface `403` here) |
| Language identification | **PARTIAL** | `acquisition/language.py` identifies document language; nothing does it on audio |
| **Transcription** | **IMPLEMENTED, unverified** | `multimodal/whisper_provider.py` — `faster-whisper` preferred; **the library is not installed, and its absence is reported rather than worked around** |
| Semantic understanding | **yes** | `knowledge_engine/`, `document_intelligence_engine/` |
| Context fusion | **ABSENT** | the programme's core |

**Nothing in the chain can run end to end today**, and the reason is stated at
each stage rather than as a single global "blocked".

---

## §10 and §11 — already implemented, and better than the directive assumes

Two modules already answer requirements the directive presents as new.

### `src/creative/language/switching.py` — code-switching is structured, not detected

Written for a directive that had asked the same thing: *"do not assume a
recording contains only one language."* Its own reasoning:

> *"À Dakar, une phrase commence en wolof, prend un mot français, revient au
> wolof. Un champ `langue` au niveau du fichier force un choix qui est faux pour
> la moitié de l'enregistrement, et tout ce qui est en aval hérite de
> l'erreur."*

And the discipline that matters here: **the module detects nothing.** It
structures what something else measured — segments arrive already labelled, and
it derives switch points, homogeneous spans and the languages present.
`intra_segment_switching` reports `UNKNOWN` rather than guessing.

**§10 is largely already satisfied.** What is missing is the *measurement* that
feeds it, not the representation.

### `src/creative/voice/scene.py` — original audio is already the source artefact

§11 asks that transcription never replace the recording. The module was written
against the same rule and states why it bites hardest where it is least
convenient:

> *"for under-resourced languages, understanding and generation are separate
> capabilities and the second is usually missing or poor… a speaker's own
> recording carries what no model can reconstruct — pronunciation, rhythm,
> hesitation, the pause before the word they chose."*

`AudioSegment.original_audio_path` is never dropped. **§11 is satisfied by an
existing module**; the live layer must feed it, not replace it.

---

## §7 — the input surface, measured

| Input | State here |
|---|---|
| Microphone | **ABSENT** — no `/dev/snd` |
| System audio | **ABSENT** |
| Camera | **ABSENT** — no `/dev/video*` |
| Screen | **ABSENT** — `DISPLAY` empty |
| Uploaded audio | **POSSIBLE** — `services/file/`, `media/ingestion/identify.py` |
| Existing video stream | **POSSIBLE** — `media/ingestion/` |
| Text | **POSSIBLE** |
| External events | **POSSIBLE** — `routines/`, `proactive/` |

**Four of eight inputs cannot exist in this environment; four can.** §7 says the
system should determine dynamically which modalities are available — that is
implementable and testable here, precisely because half are missing.

---

## What L02 concludes

**The live layer is not a perception problem here; it is a representation
problem.** Perception is blocked by hardware that is absent, and the two hardest
representation questions the directive raises — code-switching and original
audio — were already answered by two existing modules, for the same reasons.

What is genuinely missing, and what L04 must design:

1. **`LiveContextState`** — a rolling state with per-field confidence.
2. **`ContextFusionEngine`** — combining what is available without turning
   uncertain observations into facts.
3. **A capture abstraction that reports its own absence**, the way
   `media/readiness.py` reports seventeen stages.
4. **Diarization**, still `NEW_COMPONENT_REQUIRED` after four programmes.

And what must not be built: a second transcription engine, memory, MCP
orchestration, agent loop, database or summary engine.
