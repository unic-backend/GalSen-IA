# Darra J — final report

Programme: **DARRA J — national educational intelligence engine**, 20 volets,
28 phases. Frozen baseline `1a586bc` (4480 tests). Measured on the state of this
branch, not recalled.

## The state, in the directive's own words

> **ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING**

This is what `src/darra_j/readiness.py` returns when it counts the register, and
it is the only state it can return today. There is no flag, argument or override
that reaches `READY TO SERVE OFFICIAL CURRICULUM` without a published version
whose provenance is `TIER_A` and not marked `NON_OFFICIAL_TEST_DATA`. A register
holding only fixtures reports zero official versions, because it holds zero
official versions.

**No Senegalese curriculum has been integrated.** None was available to
integrate, and none was written from model memory. That is the requirement being
met, not a shortfall.

## What was built

21 modules under `src/darra_j/`, 19 test files, **377 tests** in that package
alone. Full suite: **4864 passed, 8 skipped**, `ruff` clean.

| Volet | Module | The rule it holds |
|---|---|---|
| 2 | `canonical.py` | Deterministic identity; `content_hash` separate from it; fixtures carry `NON_OFFICIAL_TEST_DATA` inside the authority string, so the mark survives serialisation |
| 3 | `registry.py` | Append-only; publication requires a named decider; a replaced version becomes `SUPERSEDED`, never deleted |
| 4 | `resolution.py` | By coordinates, never by similarity; `CLARIFICATION_REQUIRED` when they are incomplete |
| 5 | `ingestion.py` | Ten quality checks, trust boundary, proposals stop at `VALIDATION_REQUIRED` — parsing is a mechanical success, authority is an institutional decision |
| 6 | `firewall.py` | No canonical record → the model is **not called**, not merely labelled |
| 7 | `consistency.py` | Directive VI measured on `unit_id:content_hash` |
| 8 | `pedagogy.py` | Five declared levels; the explainer returns text only, so it has no shape in which to return a modified official field |
| 9 | `assessment.py` | Items anchored to official objectives verbatim; `grade` is always `None` |
| 10 | `teacher.py` | `authored_by` is always `None`; `Observation` has no verdict field; decisions need a named decider who is not the platform |
| 11 | `student.py` | The quiz view is **built** from a positive field list, not stripped |
| 12 | `parent.py` | The same official record as the child's; the guardian link is declared, never inferred |
| 13 | `access.py`, `privacy.py`, `api/rbac.py` | Six education roles; authorisation is a conjunction of permission **and** link |
| 14 | `graph.py` | Every edge names the official field it came from; dangling prerequisites and cycles are reported, never repaired |
| 15 | `mastery.py` | `NOT_MEASURED` and `INSUFFICIENT_EVIDENCE` are off the scale entirely |
| 16 | `multilingual.py` | The question travels; the record is never translated |
| 17 | `evaluation.py` | Measures the guarantees, since the knowledge is absent; `NOT_MEASURABLE` rather than 100 % on zero cases |
| 18 | `resilience.py` | Degrading means doing less, never substituting |
| 19 | `auditability.py` | The trail ends on a person, and missing links are named |
| 20 | `readiness.py` | The state is measured on the register, never declared |

## What was reused rather than rebuilt

Directive XLIX warned against assuming the architecture was absent. It mostly
was not. Reused unchanged: `SourceTier` and the acquisition states with human
validation (ADR-021), the approval gate (ADR-006), `src/security/trust.py`,
`redaction.py`, `isolation.py`, the memory layers, the storage contract
(ADR-005), the audit trail and `/observability/trail/{id}`, the degradation
vocabulary (`AVAILABLE`/`DEGRADED`/`UNAVAILABLE`), the alias table, and the
self-healing harness's isolation and rollback.

Eight components were genuinely new, and they are the eight the integration map
predicted on day one.

## Defects found — by running things, not by re-reading them

Each of these was caught by executing something, and each is pinned by a test.

| Volet | Defect | Why it mattered |
|---|---|---|
| 3 | `ingested_at` entered a version's hash | Two imports of the same decree looked different; the register refused the normal resume case |
| 7 | Comparing `unit_id` alone | Would have passed directive VI's own test while guaranteeing nothing — two records at the same coordinates share an identifier even with different titles |
| 8 | The no-explanation response returned fewer keys | A caller reading `language` failed **precisely** when the model had failed |
| 9–10 | `record_decision()` accepted the platform as its own decider | Darra J could decide, then record it under its own name — "does not decide" becomes "decides and notes it" |
| 9–10 | Attribution label was `GALSEN_IA_DARRA_J` | Exactly an environment-variable shape; the config check read it as an undocumented `GALSEN_*` variable |
| 11–12 | `child_progress()` returned counts without the evidence verdict | A parent reading "1 of 1 correct" would read mastery where there is no measurement |
| 13 | `Role.ADMIN` computed as *every* permission | Declaring `curriculum:publish` would have made GalSen IA able to publish official curriculum — what the directive denies it — with nobody deciding so |
| 16 | The alias table stored only folded terms | `translate()` is display-facing and handed back `mbey` for `mbéy`: misspelled Wolof, while `ë ñ ŋ` are CLAD letters, never accents |
| 16 | The unreviewed-Wolof reserve checked the matched term | A question asked in Wolof reaching a record via a French term rests entirely on the unreviewed list — the first step is the uncertain one |
| 18 | `.get("published", 0)` on a report with no such key | Would have read 0 silently forever |
| 19 | Journal lookup guessed `from`/`to` | The register writes `de`/`vers`; the search would never match, so every trail would silently claim no decider was recorded |

Two guards already in the repository caught omissions the moment six roles were
added — tool-authorization ceilings and the knowledge-sensitivity table — which
is precisely what they were written for.

One existing test was **tightened**, and it is named here because changing a
test deserves saying so: `test_admin_has_all_permissions` asserted admin holds
every permission. That invariant became false on purpose. It now asserts admin
holds every *platform* permission, with `PERMISSIONS_HORS_PLATEFORME` named and
pinned by a second test.

## What is measurable today, and what is not

Measurable now, on fixtures marked `NON_OFFICIAL_TEST_DATA`: hallucination rate
(on an **instrumented** generator — verifying it is not called), refusal
correctness, provenance coverage, cross-role consistency, grade leakage.

Not measurable, each named with its reason rather than omitted:
`curriculum_accuracy` (needs an official reference set), `explanation_quality`
(needs a model and human judgement), `learning_outcome` (needs a real cohort and
time).

Multilingual coverage is a count, not a promise: **16 concepts, 115 terms**
across French, Wolof and English, with `wo_reviewed: false` carried through to
every answer that depends on it.

## What is required next, and from whom

One thing, and it does not belong to this repository:

> At least one curriculum version published by a `TIER_A` authority, with
> verified provenance.

That is the whole meaning of *GalSen IA is not the authority that defines the
curriculum*. Until an authority provides it, the honest answer to every
curriculum question is `UNKNOWN`, and the system is built to be proud of it.
