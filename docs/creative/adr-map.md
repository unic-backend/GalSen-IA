# Directive V4 ADR list → this repository's ADRs

Directive §68 lists twenty-three ADRs numbered from `ADR-001`. **Those numbers
already exist in this repository** — `ADR-001` is *Choose Python*, accepted
2026-07-28. Per §75 the repository is authoritative for what exists, so this
programme continues the repository's sequence and this file holds the mapping.

§68 also says: *do not create an ADR merely for formality.* An ADR records a
decision that was actually taken, with alternatives that were actually weighed.
Four have been; the rest are listed with the volet that will decide them, and
writing them before then would be recording a decision nobody made.

| Directive § | Subject | This repository | Status |
|---|---|---|---|
| ADR-001 | Provider abstraction | **ADR-024** | ✅ accepted — one contract, extended; not a fourth family |
| ADR-022 | Provider capability registry | **ADR-024** | ✅ same decision, same ADR |
| ADR-005 | Reference Entity architecture | **ADR-025** | ✅ accepted |
| ADR-006 | Reference representation | **ADR-025** | ✅ same decision |
| ADR-020 | Privacy / consent | **ADR-025** | ✅ same decision |
| ADR-007 | Identity verification | **ADR-026** | ✅ accepted |
| ADR-008 | Identity drift | **ADR-026** | ✅ same decision |
| ADR-011 | Voice preservation | **ADR-027** | ✅ accepted |
| ADR-012 | Voice conversion | **ADR-027** | ✅ same decision (optional, licence-gated) |
| ADR-013 | Language Knowledge | **ADR-027** | ✅ same decision |
| ADR-014 | Language learning / privacy | **ADR-027** | ✅ same decision |
| ADR-002 | Model routing | ADR-028 *(reserved)* | C15 — needs a measurable capability to route on |
| ADR-003 | CreativeRepresentation | ADR-029 *(reserved)* | C07 |
| ADR-004 | WorldState | ADR-030 *(reserved)* | C09 |
| ADR-009 | Character Memory | ADR-030 *(reserved)* | C09 — same decision as WorldState |
| ADR-010 | World Memory | ADR-030 *(reserved)* | C09 |
| ADR-015 | Multimodal pipeline | ADR-031 *(reserved)* | C08 |
| ADR-016 | GPU orchestration | ADR-032 *(reserved)* | C16 — undecidable until a GPU host exists |
| ADR-017 | Continuity | ADR-033 *(reserved)* | C11 |
| ADR-018 | Crowd / background | ADR-034 *(reserved)* | C12 |
| ADR-019 | Provenance | — | **Already decided**: ADR-021 and `src/media/core/project.py` cover asset provenance; ADR-025 extends it to references. A new ADR would restate it. |
| ADR-021 | Job orchestration | — | **Already decided**: `src/media/queue/jobs.py` reuses `RunStatus` from `workflow_checkpoint.py`. Revisit only if `PAUSED` proves necessary. |
| ADR-023 | Verification and quality loop | ADR-035 *(reserved)* | C11 — depends on ADR-026's outcome vocabulary |

## Why four, and not twenty-three

Eleven of the directive's twenty-three entries collapse into four decisions,
because they are the same decision seen from different sections. Reference
architecture, reference representation and privacy/consent are one design
question: *what is a reference, and what may be done with it.* Voice
preservation, voice conversion, language knowledge and language learning are one
question too: *whose performance is authoritative, and how does knowledge about
a language earn the right to be called true.*

Two entries were already decided by work that shipped, and restating them as new
ADRs would create two documents for one rule — the drift this repository has
paid for before.

The remaining nine are genuinely open. Each needs something that does not exist
yet: a measurable capability to route on, a first consumer for the creative
representation, or a GPU. Writing them now would mean inventing the context.
