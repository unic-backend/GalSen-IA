# MoneyPrinterTurbo integration — final report

**Programme**: GALSEN-IA MASTER UPDATE DIRECTIVE V4 (44 sections).
**10 volets, 15 phases, all completed.** Plan → `docs/providers/phase-plan.md`.
Report shape → §42, its thirty-one points, in order.

**Date**: 2026-08-19. Every figure was measured on the day.

---

## The sentence this programme exists to have established

**MoneyPrinterTurbo does not generate video, and finding that out before writing
the adapter is the whole value of the nineteen audit steps §36 puts first.**

It composes stock footage retrieved from Pexels and Pixabay. Had the adapter been
written first — the natural instinct, given the directive's framing — it would
have been declared `text_to_video`, and a router would eventually have served
someone footage of a stranger for "a scene with my friend".

---

## 1. Repository state

`main` at `e88ac4a` when this began; the work sits on
`claude/unit-tests-notification-search-file-4z0ok1`. Nine commits, **29 files
changed, 2 773 insertions, 71 deletions**, 15 new files.

## 2. Existing video systems discovered

Seventeen media stages: **10 `READY`, 6 `BLOCKED`, 1 `ABSENT`**. One video
provider adapter (`wangp.py`, `ADAPTER_ONLY`). **Three** provider abstractions,
not the two the plan assumed — `model_engine/providers` selects language models
and shares only the word.

**Four of the six blocked stages are one missing `ffmpeg`, not a missing
provider.**

## 3. Existing systems preserved

All of them. §21 classification: **8 KEEP, 3 EXTEND, 1 ADAPT, 0 DEPRECATE,
0 REPLACE.** No evidence for any replacement was found, and "a newer provider
exists" is not evidence.

## 4. Files created

15 — one provider adapter, three test files, seven audit/research documents,
one ADR, one plan, plus corpus and env documentation.

## 5. Files modified

`src/media/providers/base.py` (+1 task), `src/creative/providers.py` (+1 task,
1 defect fix), `corpus/creative/providers.yaml` (+1 candidate), two count
guards, `.env.example`, `CLAUDE.md`, the overview, and memory documents.

## 6. Files not modified, and why

`wangp.py`, `media/readiness.py`, `media/story/`, `motion/`, `timeline/`,
`adapt/`, `qc/`, and all of `creative/reference/`, `world.py`, `verification.py`.
§1 forbids touching working systems without evidence, and none was found.
`readiness.py` in particular names the provider modules behind two public
verdicts; changing it would move a public statement about what the platform can
do.

## 7. Version audited

**`UNKNOWN`.** The GitHub tree API is not reachable from this session (`403`,
the session's repository scope), so no commit SHA was read. Files were read from
`raw.githubusercontent.com/.../main`, which answers `200`.

## 8. Capabilities verified

Twenty-six classified against source (§5). **12 `SUPPORTED`, 2 `PARTIAL`,
14 `UNSUPPORTED`** — full table in `moneyprinterturbo-research.md`.

## 9. Limitations

Does not generate video. Requires a real `ffmpeg`. Requires Pexels or Pixabay
keys. Has no reference conditioning, identity, continuity, camera control or lip
sync — §23 predicted this list and the source confirms it.

## 10. Providers already present

Nine candidates in the creative research dossier (C01–C02), zero commercially
cleared, eight weight licences `UNKNOWN` because `huggingface.co` has no route
here.

## 11. New provider integration

`src/media/providers/moneyprinterturbo.py` — declared, probed, and refusing.
Tenth candidate in the corpus. `health()` reports all three missing conditions
together with the gesture that repairs each; `generate()` raises, as
`wangp.generate()` does, because a placeholder is indistinguishable from a
composition that silently failed.

## 12. Routing changes

A new task, **`stock_assembly`**, in both vocabularies. This is the decision with
the most consequence: declaring `text_to_video` would have been a category error
with real effect.

Measured, three requests give three different answers:

| Request | Answer |
|---|---|
| `stock_assembly`, non-commercial | **`SELECTED` moneyprinterturbo** |
| `stock_assembly`, commercial | `NO_PROVIDER` — right not established |
| `text_to_video` | `NO_PROVIDER` — never offered as a generator |

**This is the first provider either programme's router has ever selected.**

## 13–15. Reference, identity, consent and privacy changes

**None.** Those subsystems were audited (M01.2) and left untouched. MoneyPrinter-
Turbo carries no reference, identity or consent concept, so it adds no obligation
and no capability there.

## 16. Tests added

**39** — 20 adapter, 12 routing, 7 golden.

## 17–20. Total, passed, failed, skipped

```
python -m pytest -q
1 failed, 6233 passed, 11 skipped, 3 deselected in 495.67s
```

*(This figure was written from deduction first — the previous programme's report
made exactly that mistake — then replaced by the run above. Two guard failures
had to be fixed between the two runs, so the deduction happened to be right;
that it was right is luck, and the run is the reason it can be stated.)*

The single remaining failure is `v0.1.0` — the tag has never been pushed. It
predates both programmes and fails identically on `main`.

## 21. Regression status

**No regression.** 6 191 → 6 233 as tests were added.

Three guards caught defects of mine during the programme, and all three were
right:

- the corpus loader refused the entry until `identity_consistency` named **how**
  it was established — a source reading, not a measurement;
- `test_published_numbers` refused the ADR count until 30 → **31**;
- `test_config_environment` refused three environment variables I had introduced
  without documenting them.

## 22. Performance measurements

| Operation | Time |
|---|---|
| MoneyPrinterTurbo health probe | **3.5 ms** |
| Integration report | **3.4 ms** |
| Research dossier load (10 candidates) | **17.2 ms** |
| Routing across 10 candidates | **0.44 ms** |

## 23. GPU / resource measurements

**None required.** MoneyPrinterTurbo is the only video path in either programme
that needs no GPU — it composes on CPU through moviepy and ffmpeg. Machine
unchanged: 4 cores, 15.7 GiB RAM, no GPU, VRAM `NOT_MEASURED`.

## 24. Licence findings

| | |
|---|---|
| Repository | **MIT**, read from source — the first candidate in either programme whose licence could be read |
| `edge-tts` (the TTS path) | **LGPL-3.0** |
| `azure-cognitiveservices-speech` | **Proprietary** |
| Everything else | MIT or Apache-2.0 |
| **Output rights** | **`UNKNOWN`** — Pexels and Pixabay terms unread |

**The capability the integration is actually for is copyleft, while the
repository is permissive.** That is the confusion §30 exists to prevent, and it
was found by reading rather than assuming.

## 25. Security status

No new boundary, no new dependency, no import of external code. Invocation is
`API` — a legal decision as much as a packaging one. The external repository was
treated as data (§31): nothing executed, and the linked `SKILL.md` not followed
as instruction.

## 26–27. Privacy and consent status

Unchanged. This provider handles no personal reference media.

## 28. `UNKNOWN` items

- MoneyPrinterTurbo's current version and maintenance state — tree API `403`
- Pexels / Pixabay output rights — terms unread
- Whether a third-party product may call the Edge TTS endpoint — a legal reading
- `faster-whisper`'s model weights licence — the model is configuration
- Every runtime behaviour: **nothing was executed**

## 29. Known limitations

The adapter refuses everything until an operator installs `ffmpeg`, runs the
service, and configures a stock library. That is a declaration, not an execution
path, and §37's smallest validated slice is exactly what it is.

## 30. Blockers

`ffmpeg`. The same one blocking four media stages. **One installation outside
this repository moves five things at once.**

## 31. Next phase

None in this programme. What is owed, and named rather than forgotten:

1. **A TTS decision of its own.** M02 found speech synthesis is this platform's
   `ABSENT` stage and MoneyPrinterTurbo's strongest offer. M04 measured that
   `edge-tts` is neither the only nor the most permissive option — `kokoro-tts`
   is MIT and local. Smuggling that choice in as a side effect of this
   integration would have been the wrong way to make it.
2. **`whisperx` covers speaker diarization**, which this platform reports
   `BLOCKED` with no implementation at all.
3. **The `None` discrepancy** between the media and creative layers
   (`golden-mapping.md`), recorded and deliberately not resolved.
4. **Reading the Pexels and Pixabay terms**, which is what would move the
   commercial status off `UNKNOWN`.

---

## What was refused, and stays refused

No claim that MoneyPrinterTurbo provides identity preservation, persistent
characters, WorldState, continuity, camera control or identity verification. It
provides none. **They remain GalSen IA's responsibility** — which is §23's own
conclusion, reached independently by reading the source.

GalSen IA did not become MoneyPrinterTurbo (§43). It gained one row in a
registry, one task name, and a licence question written where a router can act
on it.
