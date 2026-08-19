# Live Context Engine — final report

**Programme**: GALSEN-IA — LIVE CONTEXT ENGINE / CALL.MD INTEGRATION DIRECTIVE
(48 sections, 16 directive phases).
**Executed**: 16 volets, **27 phases**, cadence two phases per turn.
**Decision**: [ADR-033](../architecture/decisions/033-live-context-is-observations-with-a-status.md).
**Measured**: 2026-08-19, on the machine described by
`src/live_context/measurements.machine()`.

---

## The one-line state

```
REPRESENTATION READY — NO LIVE PERCEPTION ON THIS MACHINE,
5 STAGE(S) NOT IMPLEMENTED, 2 BLOCKED
```

**This string is computed, not written.** `src/live_context/readiness.py` walks
the chain, checks each module on disk and each requirement with the probes, and
derives the verdict at the end. A test replaces the stage list and asserts the
verdict changes — because a report whose conclusion is a constant says the same
thing on the day the engine works and the day it does not.

---

## What was built

| | Count |
|---|---|
| Modules (`src/live_context/`) | **16**, 4 805 lines |
| Test files (`tests/live_context/`) | **14** |
| Tests | **376**, all passing |
| Executable scenarios (§35) | **30** — 24 `VERIFIED`, 6 `BLOCKED`, 0 failed |
| New ADRs | **1** (ADR-033) |
| New dependencies | **0** |
| New registries, memories, journals | **0** |

| Module | What it holds |
|---|---|
| `state.py` | `Observation` with four statuses; `ABSENT` ≠ `UNKNOWN`; no arbitration |
| `capture.py` | the eight §7 inputs, probed; the shared environment probe |
| `fusion.py` | nine §13 streams assembled without deciding a truth |
| `speakers.py` | who speaks, when nobody knows — and no speaker is numbered |
| `languages.py` | three cases, three statuses; no fabricated translation |
| `assistance.py` | three detectors feeding `src/proactive/` |
| `intent.py` | intent proposes; three gates decide; nothing executes |
| `screen.py` | ADR-018's unconditional refusal, called rather than rewritten |
| `retention.py` | the five acts of §28, none of them silent |
| `memory.py` | permission **and** a declared link, or no write |
| `creative.py` | a session offers; only a person accepts |
| `providers.py` | one new interface out of §31's five |
| `readiness.py` | the computed state of the chain |
| `golden.py` | the thirty scenarios, runnable |
| `measurements.py` | what is measurable, and what is not |

---

## The chain, stage by stage

| Stage | Nature | State |
|---|---|---|
| CAPTURE | perceive | `ABSENT` — nothing captures; no device either |
| VOICE_ACTIVITY_DETECTION | perceive | `ABSENT` |
| SPEAKER_SEGMENTATION | perceive | `ABSENT` |
| DIARIZATION | perceive | `ABSENT` — installing `pyannote` leaves nothing to call it |
| LANGUAGE_IDENTIFICATION | perceive | `ABSENT` — on audio; documents are a different thing |
| TRANSCRIPTION | perceive | `BLOCKED` — `faster_whisper` not importable |
| SCREEN_READING | perceive | `BLOCKED` — no graphical session |
| SPEAKER_REPRESENTATION | represent | `READY` |
| LANGUAGE_REPRESENTATION | represent | `READY` |
| SCREEN_REPRESENTATION | represent | `READY` |
| CONTEXT_FUSION | represent | `READY` |
| SEMANTIC_UNDERSTANDING | represent | `READY` |
| ASSISTANCE | represent | `READY` |
| TOOL_INTENT | represent | `READY` |
| MEMORY_WRITE | represent | `READY` |
| CREATIVE_LINK | represent | `READY` |

**9 `READY`, 2 `BLOCKED`, 5 `ABSENT`**, and the split is total: every
representation stage runs, no perception stage does. L02 measured this before a
line was written — *the live layer is not a perception problem here, it is a
representation problem* — and the readiness module counts the two natures
separately, because an average between "represents everything" and "perceives
nothing" would say nothing true about either.

**`ABSENT` is not `BLOCKED`.** The second installs; the first has to be written.
Diarization is the entry worth reading twice: installing `pyannote` would supply
the capability and still leave nothing to call it, so filing it under `BLOCKED`
would send an operator after a package that was never the problem.

---

## What the audits changed

Four audit volets ran before any code, and each one **reduced** the programme.

**L00 — two accepted ADRs already decide §12 and §26.** ADR-014 (no external
model at runtime) and ADR-018 (three categories refused whatever the
configuration says, screen captures among them). §26's option A was therefore
incompatible before it was evaluated, and this programme amends neither ADR.

**L01 — Call.md does not record on Linux.** Its own platform table says the app
*"will reject recording before launch because no capture binary is available"*;
the VideoDB capture SDK ships `darwin-arm64`, `darwin-x64` and `win32-x64` only.
And VideoDB is not an optional provider inside it — it carries capture,
dual-channel transcription and even LLM calls. Its `"Local-First"` claim covers
**storage**, not processing.

**L02 — six of §41's nine "do not duplicate" items already existed**, and two
requirements presented as new were already implemented:
`creative/language/switching.py` (code-switching, structured and never guessed)
and `creative/voice/scene.py` (the original recording stays the source
artefact). The `NudgeEngine` of §20 would have been `src/proactive/` written
twice — and its evidence-fingerprint suppression is more precise than Call.md's
two-minute cooldown, because a suggestion returns when the situation changed
rather than when time passed.

**L03 — licensing is not the obstacle.** 54 npm packages: 48 MIT, 5 Apache-2.0,
1 ISC, no copyleft — the cleanest tree of the five external projects audited
across four programmes. What blocks adoption is architecture, platform support
and sovereignty. Note the shape of the licence record: `package.json` declares
MIT and **no `LICENSE` file exists** on either branch, so it is filed
`MIT DECLARED`, never `AUTHORITATIVE`.

---

## The rules this programme added, and why each exists

**`ABSENT` is not `UNKNOWN`.** No microphone is measured and will not change by
waiting; an unidentified language is waiting for a measurement. Collapsing them
sends an operator to install something that cannot help, or hides something an
installation would fix.

**An absence carries its finding.** `state.absent()` refuses a blank one:
"absent" without saying *how* it was established is a supposition.

**Fusion records conflicts and resolves none.** An average would erase exactly
the information that matters — that something does not add up — and nobody would
know it had been erased.

**Nothing is promoted, and nothing is ranked by count.** Sorting corroborated
values by how many providers carry them is arbitration without saying so, and a
hurried reader takes the first line for the right one.

**No speaker is numbered.** Cutting a recording into `SPEAKER_1`, `SPEAKER_2`
produces output with exactly the shape of a diarization and none of its content.
**A channel is not a speaker**: it says where the sound came from, not who
spoke.

**Zero does not exist where nothing was counted.** `turns: None`,
`switch_count: None`, `speaker_count: None`, `latency: None`. Zero asserts
something about the meeting or the machine; `None` says nobody measured, which
is a claim about us.

**A suggestion never rests on an `UNKNOWN`.** Advice from an unknown is more
convincing than a wrong value, therefore worse.

**Consent is necessary, never sufficient.** ADR-018 provides no exception for a
person who agrees; letting consent lift it would ask somebody to waive a
guarantee the platform gave them elsewhere. Unconditional refusals are evaluated
*before* consent, so a valid scope never appears to authorise.

**Nothing observed in a session is a request.** Someone speaking Wolof in a
meeting has not asked for a video in Wolof.

**No claim of real time.** `realtime_claim()` answers neither yes nor no: yes is
the claim §33 forbids, no asserts a measurement that did not happen either.

---

## What is measured, and what is not

Six of §33's latencies cannot exist here and are returned as `None` — never
zero — each with the measured reason. What can be measured is the **cost of
deciding**, not of perceiving: eight operations, all under a millisecond on this
machine, the most expensive being `capture_surface` at ~0.23 ms. That figure
does not mean live context is fast; it means assembly is not the bottleneck.

Every figure carries the machine that produced it.

---

## What this programme did not build

Recorded rather than silently skipped:

- **A live memory, a live agent loop, a live summary engine, a live nudge
  engine.** §41 forbids each and L02 measured that all four exist.
- **Four of §31's five provider interfaces.** Only `LiveCaptureProvider` had
  the argument; the table in `providers.py` says what serves each of the others,
  so a later reading does not add the fifth believing it was missing.
- **Screen understanding** (§12) — bounded by ADR-018 and reported `ABSENT`
  rather than approximated.
- **Any intent detector.** A keyword matcher would return the expected output
  without being a measurement.

**OPTIONAL SUGGESTION — NOT IMPLEMENTED**: pin outbound connections to the
addresses `check_url` approved (Call.md closes the DNS-rebinding window that
`research/safety.py` declares open). It belongs to the research layer and
generates no task here.

---

## Verification

| Check | Result |
|---|---|
| `pytest tests/live_context/` | **376 passed** |
| `ruff check .` | clean |
| Full suite, closing run | **6 958 passed**, 12 skipped, **1 failed** |
| `golden.run_all()` | 30 cases — 24 `VERIFIED`, 6 `BLOCKED`, **0 failed** |

The single failure is `tests/test_release_check.py::test_l_etiquette_de_la_version_courante_existe_bien`:
the `v0.1.0` tag has never been pushed. `git ls-remote --tags origin` returns
nothing, so it fails identically on `main` and is not caused by this programme.

A full regression ran after **every** phase of this programme, as
`.claude/rules/post-integration-validation.md` requires — fourteen runs, all
`PASS` with that same single failure.

---

## What is waiting on somebody outside this repository

- `git push origin v0.1.0` — the one red test in CI.
- A capture device, and a `LiveCaptureProvider` implementation for it.
- `pip install faster-whisper` — unblocks the transcription stage.
- `ollama serve` — gates intent detection and semantic retrieval.
- A decision on ADR-014 / ADR-018 if hosted live capture is ever wanted. **This
  programme does not ask for it**, and the code says `BLOCKED` rather than the
  documentation saying "planned".
