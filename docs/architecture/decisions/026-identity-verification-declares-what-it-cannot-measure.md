# ADR-026 — Identity verification declares what it cannot measure

**Status**: accepted
**Date**: 2026-08-16
**Directive**: Universal Creative Intelligence V4, §48, §49, §17, §21, §50
**Volets**: C03 (decision), C11 (implementation)

## Context

§48 asks for an `IdentityVerificationEngine` producing a score, a confidence,
detected deviations, affected shots, severity and a recommended action. It then
adds the constraint that decides the design:

> Do NOT invent scientific meaning for a score. Every metric must be documented.
> If no scientifically validated metric exists for a particular dimension, mark
> it appropriately instead of presenting an invented score as objective identity
> truth.

Measured in this environment: **no face detection is available at all.**
`HaarCascadeFaceDetector.is_available()` returns `False` — headless OpenCV no
longer ships cascade files. So facial similarity cannot be computed here, and
nothing derived from it can either.

This repository has already shipped the wrong answer to exactly this question.
RAG relevance scores were computed from nothing, looked scientific, were
comparable across queries, and meant nothing; they reached `main` and a test
pinned them. The same trap is open here and it is wider, because an *identity*
score attached to a person's likeness will be believed more readily than a
retrieval score.

## Decision

**Identity verification is a set of named dimensions, each of which reports
`MEASURED` with its method or `NOT_MEASURABLE` with the capability that would
enable it. There is no composite identity score.**

1. **Per-dimension, never aggregated into one number.** Facial similarity,
   appearance similarity, proportion consistency, clothing consistency,
   distinctive-feature consistency, colour consistency, motion characteristics.
   A single number would hide the dimension that matters behind the average of
   the ones that do not — the same reason `src/security/posture.py` refuses to
   emit an overall security score.
2. **Three outcomes, never two**: `MEASURED`, `NOT_MEASURABLE`, `FAILED`.
   "Could not check" and "checked and fine" must be impossible to confuse. This
   is the rule `src/media/qc/checks.py` already holds with `PASS` / `FAIL` /
   `NOT_CHECKED`.
3. **Every measured dimension names its method and its scale.** What was
   compared, with what, and what the number means. A dimension without a
   documented method reports `NOT_MEASURABLE` even if a number could be
   produced.
4. **A verdict requires everything applicable to be measured.** If any
   applicable dimension is `NOT_MEASURABLE`, the verification is `INCOMPLETE` —
   not "passed with reservations". A green identity report over unmeasured
   dimensions is worse than no report: it will be trusted instead of watched.
5. **Drift is a comparison between shots, not against a promise** (§49). Shot
   two deviating from shot one is measurable *if* the dimension is measurable
   there. Drift on a `NOT_MEASURABLE` dimension is `UNKNOWN`, never zero.
6. **Regeneration is shot-level.** A detected deviation names the shots it
   affects, so correction does not require regenerating a whole production.

## Alternatives considered

**A composite similarity score from embeddings or colour histograms.**
Rejected. It would run today, produce a smooth number, be comparable across
shots, and mean nothing about identity. §48 forbids it in as many words, and the
repository's own history says the forbidding is necessary.

**Report `0.0` when a dimension cannot be measured.** Rejected: zero is a
measurement, and it reads as "no similarity". `NOT_MEASURABLE` is the only value
that cannot be mistaken for a finding.

**Defer identity verification until a face capability exists.** Rejected: the
*structure* is what makes the eventual measurement honest, and building it now
costs nothing and blocks nothing. What is deferred is the claim, not the design.

## Consequences

**Good**

- No invented metric can enter, because a dimension without a documented method
  cannot report a number.
- The report doubles as a capability list: every `NOT_MEASURABLE` names what
  would enable it.
- Drift and continuity inherit the same three-outcome discipline.

**Costs, stated**

- On this machine, **every visual dimension will report `NOT_MEASURABLE`** and
  the verdict will be `INCOMPLETE`. That is the correct output here, and it will
  look empty. It should.
- Callers must handle three outcomes rather than a threshold comparison.

**Refused**

- No claim of identity preservation (§17), consistency (§18) or continuity
  (§19) will be made anywhere in this programme.

## Evidence

- `HaarCascadeFaceDetector.is_available() == False`, measured 2026-08-16.
- `src/security/posture.py` — refuses an overall score, and says why.
- `src/media/qc/checks.py` — three outcomes; `PRODUCTION_SUCCESS` requires
  nothing unchecked.
- `docs/roadmap/roadmap.md`, *How something new enters the platform* — the four
  fabrications that reached `main`.
