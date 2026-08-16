# ADR-027 — The original recording is the default; language knowledge is earned, not observed

**Status**: accepted
**Date**: 2026-08-16
**Directive**: Universal Creative Intelligence V4, §22, §23, §26–§33, §45, §58
**Volets**: C03 (decision), C08 and C13–C14 (implementation)

## Context

Two of the directive's requirements look like separate features and are the same
decision seen twice.

**§22** forbids the reflex pipeline *audio → transcription → TTS → generated
voice* and asks for *audio → understanding → video → lip sync → **original
audio***, preserving pronunciation, accent, rhythm, pauses, emotion, hesitation
and timing.

**§26** explains why it matters most where it is least convenient: for
under-resourced languages, **understanding and generation are separate
capabilities and the second is usually missing or poor**. Wolof, Serer, Pulaar,
Bambara, Diola and the rest are exactly the languages where a synthetic voice
will be worst — and exactly the ones where a speaker's own recording carries
information no model can reconstruct.

Measured: this repository's Wolof layer holds **2 105 sentences** in CLAD
orthography and an alias table of 16 concepts / 115 terms whose Wolof entries
carry `wo_reviewed: false` and name their source. **No speech synthesis exists
here at all** (the media engine reports `VOICE` as `ABSENT`), and no ASR can run
(`transcription` probe → `UNAVAILABLE`).

§27–§31 then ask for a language-knowledge loop that improves through use — and
§31 draws the line that makes it acceptable: *"learning from users" does NOT mean
silently training a foundation model on conversations.*

## Decision

**Preserving the user's recording is the default path, not a fallback. And a
linguistic observation is evidence that climbs a validation ladder; it never
becomes truth by repetition.**

### On voice

1. **The original audio is kept unless the user asks otherwise.** Replacing a
   human performance with a synthetic one is a decision the user makes, never a
   pipeline default.
2. **Understanding and generation are separate capabilities**, declared
   separately per language. A language may be `UNDERSTOOD` and not `SPEAKABLE`,
   and the system says so rather than degrading silently into a bad voice.
3. **Voice conversion is optional** (§23) and its provider carries a licence
   question of its own (Seed-VC is GPL-3.0). §22's default may make it
   unnecessary.
4. **Uncertain language understanding answers `UNKNOWN` or `LOW_CONFIDENCE`**
   (§33) and the recording is preserved. Nothing invents a translation, a
   meaning, a pronunciation or a cultural reading — the rule
   `src/knowledge_engine/` already enforces for Senegalese law and administration.
5. **A recording may hold several languages** (§25). Language is a property of a
   *segment*, with its own confidence and speaker, never of a file.

### On language knowledge

6. **Six states, and repetition never promotes**: `OBSERVED` → `CANDIDATE` →
   `CORROBORATED` → `VALIDATED` → `OFFICIAL`, plus `UNKNOWN`. Frequency moves an
   observation from `OBSERVED` to `CORROBORATED` and **no further**. `VALIDATED`
   requires a named human; `OFFICIAL` requires an authority that is not the
   platform. This is the ladder ADR-021 already implements for knowledge
   acquisition and `SourceTier` already ranks — reused, not re-invented.
7. **A user correction is an observation, not a global fact.** It carries its
   author, date, context and confidence, and it applies where it was made until
   someone validates it more broadly.
8. **Private conversations stay private** (§58). A private interaction never
   enters global language knowledge without explicit, recorded consent. Two
   stores, one boundary, the same separation the knowledge base already holds.
9. **No silent training, ever** (§31, §45, §73). Any future training pipeline is
   explicit, consent-aware, licence-reviewed, dataset-controlled, reproducible,
   isolated and auditable. Knowledge acquisition and model training are
   different acts and this ADR keeps them different.
10. **Visual context is evidence, not proof** (§32). A gesture may support a
    hypothesis about an unknown word; it never settles it. Multiple hypotheses
    are kept when the evidence does not choose.

## Alternatives considered

**Transcribe and re-synthesise by default.** Rejected. It is the industry
default and it is worst precisely where this platform starts: it would replace a
Wolof speaker's own voice with a synthetic approximation of a language the
synthesiser barely models.

**Promote frequently-observed expressions automatically.** Rejected by §28. A
frequent mistake is still a mistake, and a platform that turns repetition into
official meaning will encode the errors of its loudest users into a language's
record.

**One language field per recording.** Rejected by §25 and by the reality of
Dakar: Wolof and French alternate inside single sentences.

## Consequences

**Good**

- The speaker's performance survives, which for under-resourced languages is the
  only faithful option available today.
- A language's coverage is stated per capability, so a gap is visible instead of
  being filled with a bad voice.
- Language knowledge accumulates with provenance, and can be audited or
  reverted.

**Costs, stated**

- Keeping the original audio constrains editing: cuts must land on measured word
  boundaries. `src/media/transcription/words.py` already refuses estimated
  timings, so the constraint is inherited rather than new.
- The validation ladder needs humans. There is no automatic path to `VALIDATED`,
  by design, and that means the knowledge base grows slowly.

**Refused**

- No claim of universal language understanding (§20).
- No training on user conversations (§45).
- No synthetic voice presented as a person's own.

## Evidence

- `corpus/languages/aliases.yaml` — 16 concepts, 115 terms, `wo_reviewed: false`.
- `src/wolof/clad.py`, 2 105 sentences — `ë ñ ŋ` are letters, not accents.
- ADR-021, `src/acquisition/` — the observation → validation ladder that exists.
- `src/media/readiness.py` — `VOICE` is `ABSENT`, measured.
- `docs/creative/provider-research.md` — Seed-VC GPL-3.0; WAXAL noted as a
  dataset lead with its licence `UNKNOWN`.
