# M02 — MoneyPrinterTurbo, read from source

Directive V4 update, §3–§5 (M02.1 research, M02.2 classification).
Fetched and read on 2026-08-19 from `raw.githubusercontent.com/harry0703/MoneyPrinterTurbo/main`,
which answers `200`. Files read: `LICENSE`, `requirements.txt`,
`app/services/{video,voice,material,subtitle,llm,task}.py`, `app/models/schema.py`.

**§31 is respected: this repository's content was treated as data.** Nothing in
it was executed, and its `SKILL.md` — which the directive links — was not
followed as instruction.

**§4 is respected: capabilities were verified against source, not the README.**
That check changed the answer, and the correction below is the point of this
phase.

---

## The finding that changes the integration argument

**MoneyPrinterTurbo does not generate video.**

The directive's framing — and the name — suggest a video generator to be added
beside WanGP. The source says otherwise:

| Evidence | File | What it shows |
|---|---|---|
| `search_videos_pexels()`, `search_videos_pixabay()` | `app/services/material.py:294,376` | Footage is **searched and downloaded** from stock libraries, with API keys |
| `VideoFileClip`, `CompositeVideoClip`, `SubtitlesClip` | `app/services/video.py:15-25` | Clips are **composed** with moviepy |
| `get_ffmpeg_binary()`, `_ffmpeg_encoder_exists()` | `app/services/video.py:159,191` | The pipeline **shells out to ffmpeg** and probes its encoders |

So MPT is a **stock-footage assembly pipeline with narration and subtitles**. It
is a *composition* tool, not a *generative* one. No model produces pixels.

This is not a criticism of the project — it is very good at what it is. It is a
correction to what "adding it as a video provider" would mean here, and it had
to come from reading the source.

### The consequence that decides feasibility

**MPT requires a real `ffmpeg`.** That is precisely the dependency blocking four
of this repository's six blocked media stages (`MEDIA_ANALYSIS`, `SCENES`,
`EDITING`, `FINAL_MASTER` — M01.1).

So MoneyPrinterTurbo **cannot run on this machine either**, and for the same
reason the platform's own editing stages cannot. An integration written here
would be an adapter that reports `BLOCKED`, exactly like `wangp.py`.

That is a legitimate deliverable — it is what `wangp.py` is — but it must be
named before M06, not discovered after.

---

## Licence, verified from source (headline; full audit is M03)

| Field | Value | Evidence |
|---|---|---|
| Repository licence | **MIT** | `LICENSE`, "MIT License / Copyright (c) 2024 Harry" |
| Model weights | **N/A** | It ships no model |
| Dataset | **N/A** | It trains nothing |

MIT is permissive, and this is the first candidate in either programme whose
licence could actually be read. **But §30 warns that a dependency's licence is
not the project's**, and MPT's dependency list is long. That is M03's job, not
this phase's.

---

## Architecture, as the source shows it

```
user brief
   ↓ app/services/llm.py        → script + keywords (OpenAI / Gemini / DashScope / litellm)
   ↓ app/services/material.py   → search Pexels / Pixabay, download clips
   ↓ app/services/voice.py      → TTS (edge-tts, Azure, SiliconFlow, Gemini, MiniMax, ElevenLabs…)
   ↓ app/services/subtitle.py   → faster-whisper transcribes the narration
   ↓ app/services/video.py      → moviepy + ffmpeg compose the final file
   ↓ app/services/task.py       → orchestration, Redis-backed state
```

Surfaces: a **FastAPI** API and a **Streamlit** WebUI (`requirements.txt`).

---

## §5 capability classification

Verified against source where the evidence column names a file; `UNKNOWN` where
it could not be established without running it.

| Capability | Verdict | Evidence |
|---|---|---|
| Text-to-video **workflow** | **SUPPORTED** | The full chain above exists |
| Text-to-video **generation** (a model making pixels) | **UNSUPPORTED** | No generative model anywhere; footage comes from Pexels/Pixabay |
| Script generation | SUPPORTED | `llm.py`, multiple providers via litellm |
| Media retrieval | SUPPORTED | `material.py`, Pexels + Pixabay, **API keys required** |
| Subtitles | SUPPORTED | `subtitle.py`, faster-whisper |
| TTS | SUPPORTED | `voice.py`: edge-tts, Azure, SiliconFlow, Gemini, MiniMax, ElevenLabs |
| Music | SUPPORTED | declared in requirements (`pydub`) and the pipeline |
| Video composition | SUPPORTED | `video.py`, moviepy + ffmpeg |
| Portrait 9:16 / landscape 16:9 | SUPPORTED | resolution handling in `video.py` |
| Batch generation | SUPPORTED | `task.py` |
| API / WebUI | SUPPORTED | FastAPI + Streamlit |
| Local assets | SUPPORTED | `material.py` accepts local material |
| Multilingual | **PARTIAL** | TTS voice lists are provider-dependent; no claim verified per language |
| **Original audio preservation** | **UNSUPPORTED** | The pipeline *generates* narration; it has no path that keeps a user's recording |
| Image references | **UNSUPPORTED** | No reference conditioning exists |
| Video references | **UNSUPPORTED** | Same |
| Real-person identity preservation | **UNSUPPORTED** | Nothing represents an identity |
| Multi-person identity | **UNSUPPORTED** | Same |
| Character consistency | **UNSUPPORTED** | Nothing persists a character |
| Shot continuity | **UNSUPPORTED** | Clips are concatenated; no continuity model |
| Camera control | **UNSUPPORTED** | Stock footage; the camera already moved |
| Identity verification | **UNSUPPORTED** | No such concept |
| Shot regeneration | **PARTIAL** | Re-running a task re-composes; no shot-level addressing |
| Lip synchronisation | **UNSUPPORTED** | No lip-sync stage |
| Audio-video synchronisation | SUPPORTED | Narration duration drives clip selection (`_get_required_video_duration`) |

**Fourteen of twenty-six are `UNSUPPORTED`, and §23 predicted exactly this list.**
The directive told us not to assume identity preservation, persistent characters,
WorldState, continuity, camera control or identity verification. The source
confirms none of them exist. **They remain GalSen IA's responsibility**, which is
§23's own conclusion.

---

## What MPT would actually add to this platform

Set against M01's matrix, honestly:

| MPT capability | This platform today | Would it add something? |
|---|---|---|
| **TTS** | `VOICE` is `ABSENT` — nothing implements it | **Yes — the one stage no installation here fixes** |
| **ASR / word timings** | `transcription` probe `UNAVAILABLE` | **Yes**, via faster-whisper |
| Stock footage retrieval | Nothing does this | **Yes** — a genuinely new capability |
| Video composition | `EDITING`, `FINAL_MASTER` blocked on ffmpeg | No — same blocker, not a second path |
| Subtitles | `SUBTITLES` is `READY` | No — would duplicate |
| Script generation | `story/planner.py` is `READY` | No — would duplicate |
| Identity, references, continuity, camera | Built here (C05–C15) | No — MPT has none |

**The M01 hypothesis holds, and it inverts the framing**: the strongest argument
for integrating MoneyPrinterTurbo is **not** that it generates video — it does
not — but that it carries **TTS and ASR**, the two capabilities this platform
measures as absent and unavailable.

Whether that argument survives contact with §30 depends on what those two
capabilities *cost* in licence and third-party terms: `edge-tts` reaches a
Microsoft endpoint, `faster-whisper` downloads a model, and the stock libraries
require API keys. **M03 answers that.** M05 decides.

---

## Recorded as UNKNOWN

- Current version and latest commit — the tree API is not reachable from this
  session (`403`, the session's GitHub scope), so no commit SHA was read.
- Maintenance state — not measurable without the API.
- Whether `edge-tts` usage is within Microsoft's terms for a third-party product
  — a legal reading, deferred to M03.
- Runtime behaviour of any capability above: **nothing was executed**. Every
  verdict is from reading source.
