# ADR-030 — MoneyPrinterTurbo is a declared provider, called as a service, and it is not a video generator

**Status**: accepted
**Date**: 2026-08-19
**Directive**: Master Update Directive V4, §2, §6, §7, §23, §30, §37, §43
**Volets**: M00–M04 (evidence), M05 (this decision), M06–M07 (implementation)

## Context

The directive asks for MoneyPrinterTurbo to be added as an additional provider,
and forbids it becoming the core (§2, §43). Four audit volets produced the
evidence this decision rests on.

**It does not generate video** (M02, read from source). `material.py` searches
Pexels and Pixabay and downloads clips; `video.py` composes them with moviepy and
shells out to `ffmpeg`. No model produces a pixel. Fourteen of twenty-six
capabilities in §5's list are `UNSUPPORTED`, and §23 predicted the list exactly.

**It cannot run here** (M02). It requires a real `ffmpeg` — the same dependency
that blocks four of this repository's six blocked media stages.

**Its repository is MIT; its dependency tree is not** (M03). `edge-tts`, the TTS
path, is **LGPL-3.0**. `azure-cognitiveservices-speech` is proprietary. And the
rights over the *output* are `UNKNOWN`, because they belong to Pexels' and
Pixabay's API terms, which nobody in this repository has read.

**Three provider abstractions already exist** (M00.2), and §6 forbids creating a
fourth.

## Decisions

### 1. It joins the creative registry, declaring into the media vocabulary

`src/creative/providers.py`, not `src/media/providers/` directly and never
`src/model_engine/providers/` — which selects language models and shares only the
word.

The creative registry is the only one that **reads a licence before selecting**.
Given that M03 made licence the central unresolved question, putting this
provider anywhere else would put it where its main risk is invisible.

It declares its capability in the media `TACHES` vocabulary, because
`creative/providers.py` extends `media/providers/base.py` rather than replacing
it (ADR-024).

### 2. A new task name, because declaring `text_to_video` would be a category error

**This is the decision with the most consequence, and it is not cosmetic.**

If MoneyPrinterTurbo declares `text_to_video`, the router may select it for
*"generate a scene of my friend in a Dakar shop"*. It would return stock footage
of a stranger. That is a silent substitution — the precise failure
`src/creative/routing.py` was built to refuse, where it says *"servir autre chose
que ce qui est demandé est une substitution silencieuse, et le demandeur n'a
aucun moyen de s'en apercevoir."*

So the media task vocabulary gains one value:

```
stock_assembly   — compose an edit from retrieved stock footage and narration
```

It is a different act from `text_to_video`, and naming it differently is what
keeps a router from confusing them. A caller who wants generation will not be
served composition, and a caller who wants composition will not be told no
because no generator is cleared.

**Cost, stated**: one more value in a shared vocabulary, and every existing
consumer of `TACHES` must tolerate it. That is checked by test, not by hope.

### 3. Invocation mode is `API`, and this is a licence decision

MoneyPrinterTurbo ships a FastAPI service. GalSen IA calls it over HTTP; it does
**not** import it.

Two reasons, and the first is legal:

- **`edge-tts` is LGPL-3.0.** ADR-024 already established that *"calling a
  GPL-3.0 tool as an isolated process is not the same act as linking it into this
  repository, and the difference has legal consequences."* The same reasoning
  applies to weak copyleft, and `API` is the mode that makes the distinction
  structural rather than remembered.
- **No dependency is added.** Importing MPT would pull moviepy, streamlit, redis,
  edge-tts, the Azure SDK and a dozen clients into this platform. §37 asks for the
  smallest validated slice; twenty transitive dependencies is its opposite.

### 4. Commercial status is `UNKNOWN`, and the router will refuse it

The provider declares `commercial=UNKNOWN` because the output rights are unread
(M03). The existing selector then refuses it for any commercial job, with no new
code.

This is not caution for its own sake. Someone will eventually sell a video made
of clips whose terms nobody read, and the moment to prevent that is while the
provider is being declared — not after.

### 5. The adapter is written now, as a declaration and a probe — not an execution path

It cannot execute: no `ffmpeg`, no configured service, no API keys. So it follows
the shape `src/media/providers/wangp.py` already established and this repository
already trusts: **`health()` reports what is missing, `generate()` refuses.**

What that buys, concretely:

- the capability graph records that stock assembly exists as an option, and under
  what conditions;
- the licence record makes the router refuse it commercially, permanently;
- an operator reading `health()` is told exactly what to install and configure;
- when someone does install `ffmpeg` and run the service, the execution path is a
  small, reviewable addition rather than a new integration.

**What it must never do**: return a plausible result. A placeholder is
indistinguishable from a composition that silently failed — the reason
`wangp.generate()` raises.

## Alternatives considered

**Import MoneyPrinterTurbo as a library.** Rejected: twenty transitive
dependencies including LGPL-3.0 and proprietary ones, into a platform whose
`requirements.txt` discipline is one of its stronger properties.

**Declare it as `text_to_video`.** Rejected — see decision 2. It is the kind of
shortcut that works until the day it silently serves the wrong thing.

**Integrate its TTS instead of the whole thing.** Genuinely tempting: M02 found
TTS is the platform's `ABSENT` stage and MPT's strongest offer. Rejected *here*
because M04 measured that `edge-tts` is neither the only nor the most permissive
option — `kokoro-tts` is MIT and local. Choosing a TTS provider is its own
decision with its own evidence, and smuggling it in as a side effect of this
integration would be the wrong way to make it. **Recorded as owed.**

**Do nothing until `ffmpeg` exists.** Rejected: the declaration is useful without
the execution path, and the audit that produced it would otherwise decay.

## Consequences

**Good**

- The capability graph gains an option that needs no GPU — the only such video
  path in either programme.
- The licence risk is expressed where a router can act on it.
- No dependency, no import, no new architecture.

**Costs, stated**

- One new value in a shared task vocabulary, which every consumer must tolerate.
- An adapter that refuses everything until an operator does three things:
  install `ffmpeg`, run the MoneyPrinterTurbo service, configure Pexels or
  Pixabay keys.
- The output-rights question stays open, and is now written down where it will be
  seen.

**Refused**

- No claim that MoneyPrinterTurbo provides identity preservation, persistent
  characters, continuity, camera control or lip sync. It provides none (M02).
- No `IF VIDEO THEN MPT` (§7).
- No replacement of `wangp.py`, which answers a different question.

## Evidence

- `docs/providers/audit.md` — three provider abstractions, not two
- `docs/providers/capability-matrix.md` — 10 READY / 6 BLOCKED / 1 ABSENT; four
  blocks are one missing `ffmpeg`
- `docs/providers/moneyprinterturbo-research.md` — read from source: Pexels,
  Pixabay, moviepy, ffmpeg
- `docs/providers/licence-matrix.md` — MIT repo, LGPL-3.0 TTS, `UNKNOWN` output
- `docs/providers/alternatives.md` — `kokoro-tts` MIT, `whisperx` BSD-2
