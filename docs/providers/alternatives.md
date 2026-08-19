# M04 — current alternatives

Directive V4 update, §34. Read on 2026-08-19 from PyPI package metadata.

**§34 says not to assume existing providers remain optimal.** This phase is
deliberately narrow, and the narrowing is the finding of M01 and M02: the
platform's real gaps are **speech synthesis** (`ABSENT`) and **speech
recognition** (`UNAVAILABLE`). Video generation was researched by the previous
programme — nine candidates, `docs/creative/provider-research.md` — and nothing
measured since has changed its conclusion that zero are commercially cleared.

Re-researching video generation here would produce the same nine `UNKNOWN`
weight licences, because `huggingface.co` still has no route from this
container. Spending the phase on the two gaps that *can* be answered is the
better use of it, and it is recorded as a choice rather than an omission.

---

## Speech synthesis — the stage nothing here implements

| Candidate | Version | Licence | Runs offline? | Note |
|---|---|---|---|---|
| **`edge-tts`** (MPT's path) | 7.2.7 | **LGPL-3.0** | **No** — calls a Microsoft endpoint | Quality is good; the dependency is copyleft and the service terms are `UNKNOWN` |
| **`kokoro-tts`** | 2.3.1 | **MIT** | Yes, with weights | The only permissive-licensed candidate found |
| `piper-tts` | 1.7.0 | **GPL-3.0-or-later** | Yes | Strong copyleft — `OUT_OF_PROCESS` only, per ADR-024's reasoning |
| `coqui-tts` / `TTS` | 0.27.5 / 0.22.0 | **MPL-2.0** | Yes | File-level copyleft; usable, with obligations on modified files |
| `azure-cognitiveservices-speech` | — | **Proprietary** | No | Microsoft terms, per subscription |

**The finding worth acting on:** MoneyPrinterTurbo's TTS path is not the most
permissively licensed one available. `kokoro-tts` is MIT and runs locally, which
means it carries neither `edge-tts`'s copyleft nor its dependence on a
third-party endpoint whose terms nobody here has read.

That does **not** make it the right choice — no quality, latency or language
coverage was measured, and this platform's languages are the ones where synthetic
voice is worst (§26 of the previous directive). It makes it a candidate that M05
must not ignore while arguing for MPT's TTS.

**Wolof, Serer, Pulaar coverage: `UNKNOWN` for every candidate above.** None was
checked against the platform's validation languages, and assuming coverage from a
project's language count is exactly the error the language registry (C13) exists
to prevent.

## Speech recognition — `UNAVAILABLE` today

| Candidate | Version | Licence | Note |
|---|---|---|---|
| **`faster-whisper`** (MPT's path) | 1.1.0 | **MIT** | Wrapper; **downloads model weights**, licence of the chosen model is separate |
| `openai-whisper` | 20250625 | **MIT** | Reference implementation, heavier |
| `whisperx` | 3.8.6 | **BSD-2-Clause** | Adds word-level alignment and speaker diarization |

**`whisperx` is worth naming**, because it addresses two gaps at once: this
platform's `transcription` probe is `UNAVAILABLE` *and* speaker diarization is
`BLOCKED` with no module at all. MPT's `faster-whisper` covers only the first.

All three need `torch`, which is absent here. So none changes the measured state
of this machine — they change what an operator with a GPU could install.

## Video generation — unchanged

Nine candidates researched in C01–C02. Eight weight licences `UNKNOWN`, one
`OpenRail-M`, zero commercially cleared. `huggingface.co` remains unreachable
from this container, so re-reading them would produce the same absences.

**MoneyPrinterTurbo does not belong in this table**, and that is the correction
M02 established: it composes stock footage, it does not generate.

---

## What M04 hands to M05

- **MPT's TTS is not the only option, and not the most permissive one.** An ADR
  that integrates MPT *for its TTS* must say why `edge-tts` (LGPL-3.0, remote
  endpoint) over `kokoro-tts` (MIT, local).
- **`whisperx` covers a gap MPT does not** — speaker diarization, which this
  platform reports `BLOCKED` with no implementation.
- **Nothing here runs on this machine.** Every candidate needs either `torch`, a
  GPU, or a network service with unread terms. The integration remains a
  declaration, not an execution path.
