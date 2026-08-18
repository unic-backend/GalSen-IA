# ADR-025 — A reference is consent-bearing, versioned, and revocable

**Status**: accepted
**Date**: 2026-08-16
**Directive**: Universal Creative Intelligence V4, §6–§13, §55, §58
**Volets**: C03 (decision), C05–C06 (implementation)

## Context

§8 lets a user provide photos, video and voice of themselves or authorised
collaborators so the platform can reproduce that visual identity in generated
scenes. §12 immediately constrains it: *uploading a person's image MUST NOT
automatically imply unlimited rights to use it*, and a reference must be
removable with deletion propagating.

Two failure modes are specific to this, and neither is hypothetical.

**The first is silent scope creep.** A reference uploaded for one project gets
reused in another, months later, by a system that has no idea the permission was
narrower than the storage. Nothing in an embedding remembers who agreed to what.

**The second is a deletion that does not delete.** The reference row goes; the
derived representation, the cached analysis, the generated frames and the
manifest entry stay. The user was told it was deleted. This repository already
holds the shape of the answer elsewhere: `src/media/core/project.py` has **no
delete method at all**, because a guarded delete eventually gets called with the
right argument.

The audit found the mechanisms already exist and are proven: `src/darra_j/`
requires **permission *and* a declared link** before any learner data is read —
there is no permission for an unlinked learner because none was created;
`src/approval_engine/` (ADR-006) gates sensitive actions on a human;
`src/acquisition/gate.py` batches human approval before any fetch.

## Decision

**A `ReferenceEntity` is a structured record with per-field provenance, an
explicit consent scope, and a lifecycle that includes revocation. It is never
reduced to an embedding, and it is never usable outside its declared scope.**

1. **Not one embedding** (§9). A reference is a structured record — entity type,
   visual identity, appearance, geometry, motion characteristics, voice, source
   media, provenance, consent, permissions, retention, versions. Each field
   carries a capability status: `SUPPORTED` / `PARTIAL` / `UNKNOWN` /
   `UNSUPPORTED`, because no provider supports every field and pretending
   otherwise makes the gap invisible.
2. **Consent is a scope, not a boolean.** It names who consented, to what use,
   for how long, and where the reference may travel. **Absence of a scope is
   absence of permission** — the Darra J rule, restated: there is no permission
   for an unlinked learner because none was created.
3. **Entity type is open** (§6). Human, animal, vehicle, product, object, robot,
   fictional creature, 2D, 3D, environment. The architecture must not assume
   references are people; §4 says examples are not architectural limits.
4. **Revocation is first-class and propagates.** A revoked reference is
   `REVOKED`, not absent: the record of the revocation survives, everything
   derived from it is marked, and nothing derived may be used afterwards. A
   deletion that leaves derived artefacts usable is a lie told to a person about
   their own image.
5. **Provenance travels with every derived artefact** (§55). A generated frame
   names the references that conditioned it. Without that link, "delete my
   reference" cannot be answered honestly.
6. **Private references stay private** (§58). A reference never enters a shared
   or global asset pool without an explicit, recorded authorisation — the same
   separation `src/knowledge_engine/` already enforces between private and
   global knowledge.

## Alternatives considered

**Consent as a boolean on upload.** Rejected. It answers "did they agree?" and
never "to what?", which is the only question that matters six months later.

**Reference as an embedding plus metadata.** Rejected by §9 and by evidence: an
embedding cannot express that the front view is well-observed and the rear view
is not, so the confidence of a reconstruction becomes unrepresentable — and
unrepresentable confidence gets reported as certainty.

**Hard delete only.** Rejected. It destroys the audit trail of a
privacy-relevant act. `REVOKED` plus propagation preserves both the user's
intent and the record that it was honoured; hard erasure of the media itself is
a separate, explicit operation.

## Consequences

**Good**

- A reference cannot be used outside what someone agreed to, because the scope
  is checked, not remembered.
- "Delete my face" has a real answer, and the answer is checkable.
- Non-human entities work from the start rather than being retrofitted.

**Costs, stated**

- More fields to fill, and most will be `UNKNOWN` at first. That is the point:
  `UNKNOWN` is information, and a sparse honest record beats a dense invented
  one.
- Propagation on revocation requires every derived artefact to name its
  references. That is a real constraint on the generation path, accepted
  deliberately.

**Refused**

- No claim of identity fidelity. §17 forbids it, and this environment cannot
  measure it: **no face detection is available here**
  (`HaarCascadeFaceDetector.is_available()` is `False`, measured).
- No composite "identity score" invented in its place — see ADR-026.

## Evidence

- `src/darra_j/access.py`, `privacy.py` — permission **and** declared link.
- `src/media/core/project.py` — no delete method exists; versions are never
  destroyed.
- `src/acquisition/gate.py`, ADR-006 — human approval before an external act.
- `docs/creative/feasibility.md` — face detection unavailable, measured.
