# ADR-024 — One provider contract, extended; not a fourth family

**Status**: accepted
**Date**: 2026-08-16
**Directive**: Universal Creative Intelligence V4, §34, §35, §2, §46, §74
**Volets**: C03 (decision), C04 (implementation)

## Context

Directive V4 §34 lists twenty provider interfaces to create or evolve:
`VideoGenerationProvider`, `ImageToVideoProvider`, `LipSyncProvider`,
`SpeechRecognitionProvider`, `SpeakerDiarizationProvider`,
`IdentityVerificationProvider` and fourteen more. Its next sentence is the one
that matters: *do NOT create duplicate interfaces if equivalent abstractions
already exist.*

The audit (`docs/creative/repository-audit.md`) found **three provider families
already in this repository**, each with its own base class, its own registry
shape and its own idea of what a capability is:

| Family | Base | Registry | Capability model |
|---|---|---|---|
| `src/model_engine/providers/` | `ModelProvider` (ABC) | `ModelManagerImpl` + `model_selector.py` | `capability_detector.py`, per-model |
| `src/multimodal/` | `TranscriptionProvider` (ABC) | `registry.py` | none — availability only |
| `src/media/providers/` | `ProviderCapability` (dataclass) | `select_provider()` | declared capability + measured VRAM + declared cost |

Adding a fourth family for twenty more interfaces would produce four vocabularies
for one idea. This repository has already paid for that failure mode four times,
and the correction is written into `src/media/queue/jobs.py`: *a second
vocabulary for the same idea drifts.*

Three further facts constrain the decision, all measured (C01–C02):

- **No candidate provider can execute here.** No GPU, no `torch`, no
  `transformers`. Every provider is an adapter that reports its state.
- **Zero candidates are cleared for commercial use.** Eight of nine weight
  licences are `UNKNOWN` because `huggingface.co` has no route from this
  container.
- **One candidate is copyleft** (Seed-VC, GPL-3.0), which makes *how* a provider
  is invoked — in-process or out-of-process — a legal question and not only a
  technical one.

## Decision

**One contract, `CreativeProvider`, extended from the shape
`src/media/providers/base.py` already uses. Tasks are declared data, not
subclasses. The three existing families stay where they are and are adapted
into the registry, not rewritten.**

Four parts:

1. **A provider declares tasks, it does not inherit them.** `text_to_video`,
   `lip_sync`, `speaker_diarization` and the rest are values in a declared
   vocabulary, and a provider names the ones it serves. Twenty interfaces would
   mean twenty import sites, twenty registries to keep in step, and a new class
   every time the ecosystem invents a task — which it does roughly quarterly.
2. **Capability is declared, availability is probed.** A declaration says what a
   provider *claims*; a probe says what this machine can *reach*. They are
   different and both are needed: today every probe answers `UNAVAILABLE`, and
   that is the honest state, not a bug.
3. **Licence and invocation mode are first-class provider fields.** Not
   metadata: routing inputs. A provider whose commercial status is `UNKNOWN`
   cannot be selected for a commercial job, and a copyleft provider declares
   `invocation: OUT_OF_PROCESS` because calling it and vendoring it are
   different acts.
4. **The existing families are adapters into the new registry.** `ModelProvider`
   and `TranscriptionProvider` keep their interfaces and their tests; a thin
   adapter declares each as a `CreativeProvider` with its tasks. Nothing that
   works today is rewritten, which is §31 and §75.

## Alternatives considered

**Twenty interfaces as §34 lists them.** Rejected: it is a literal reading of a
directive that itself forbids duplicate abstractions in the same section. Twenty
ABCs whose only difference is a method name is a taxonomy, not a design, and each
one becomes a place where the registry and the router can disagree.

**Unify the three existing families into one now.** Rejected as premature and
destructive. `model_engine` serves text generation with six live providers and
its own tests; `multimodal` serves transcription. Rewriting either to fit a
contract whose first real consumer does not exist yet would risk working code for
a symmetry nobody has needed. Adapters cost little and can be replaced by
unification later, when a second consumer proves the shape.

**Extend `model_engine/providers/base.py` instead of `media/providers/base.py`.**
Rejected: `ModelProvider` is built around a text-in/text-out generation call.
`media/providers/base.py` already models what this directive needs — declared
capability, measured VRAM, declared cost, and an explicit refusal to pick a
nearest match when nothing fits.

## Consequences

**Good**

- One vocabulary. A task added to the ecosystem is a value, not a class.
- Licence becomes a routing constraint rather than a footnote — which is the
  only way §40 survives contact with a router.
- The three existing families keep their tests and their behaviour.
- A provider that cannot run reports its state; nothing returns a plausible
  result. This is the rule the whole repository already holds.

**Costs, stated**

- An adapter layer is indirection, and indirection has to be read to be
  understood. Mitigated by keeping adapters declarative — they map, they do not
  decide.
- A declared task vocabulary can grow stale relative to the ecosystem. Mitigated
  by the vocabulary being one list in one file, checked by a test.
- Unification of the three families is **deferred, not cancelled**. If a second
  consumer appears and the adapters start carrying logic, that is the trigger to
  revisit — recorded here so the deferral is a decision and not an oversight.

**Refused explicitly**

- No provider is *selected* by this ADR. Selection needs a licence cleared and a
  capability measured; today neither exists for any candidate.
- No provider is vendored. Seed-VC's copyleft question is not resolved here, and
  §22 may make voice conversion unnecessary anyway.

## Evidence

- `docs/creative/repository-audit.md` — the three families, measured.
- `docs/creative/provider-research.md` — nine candidates, 8/9 repository licences
  read authoritatively, 8/9 weight licences `UNKNOWN`.
- `corpus/creative/providers.yaml` + `src/creative/research.py` — the record and
  the loader that refuses inferred permissions.
- `src/media/providers/base.py` — the shape being extended, already in use.

## Note on numbering

Directive V4 §68 lists its own ADR numbers starting at `ADR-001 Provider
abstraction`. **Those numbers collide with this repository's existing ADRs**
(`ADR-001` is *Choose Python*, accepted 2026-07-28). Per §75, the repository is
authoritative for what exists, so this programme continues the repository's
sequence from `ADR-024`. The mapping to the directive's list lives in
`docs/creative/adr-map.md`.
