# ADR-018: Sovereign by Default, With a Scoped Derogation

## Status
**Proposed** — awaiting the owner's decision. Nothing in the code changes until
this is accepted; `GALSEN_SOVEREIGN_MODE` still defaults to `true` and the test
that asserts it is untouched.

## Date
2026-08-12

## Context

The brief of 2026-08-12 asks for the *"ability to switch between cloud and local
models"*. ADR-014 refuses third-party providers by default: hosted providers are
**not registered at all** in sovereign mode, so no path can select one.

`.claude/rules/` is unambiguous — *"NEVER invent architecture that contradicts
existing ADRs"*, change the ADR first. Hence this document, and hence its status.

### What already exists, measured

```python
>>> ModelManagerImpl().sovereignty_report()
{'sovereign_mode': True, 'providers': ['local', 'openai_compatible'],
 'third_party_providers': [], 'reference': 'ADR-014'}
```

ADR-014 already carries an escape hatch: setting `GALSEN_SOVEREIGN_MODE=false` is
*"a deliberate, logged decision — useful for comparing an own model against a
reference during evaluation, and for nothing else."*

**So the question is not whether an exception may exist. It is what shape it
takes** — and the shape that exists today is the worst available one:

- **Global.** One flag turns third-party providers on for *everything*, including
  requests carrying a user's memories, files and knowledge.
- **Binary.** There is no "for this task only".
- **Scoped by intention, not by mechanism.** The ADR says "for evaluation and
  nothing else"; nothing enforces that. A sentence in a document is not a
  boundary.

An operator who wants a cloud model for one narrow job today has exactly one
lever, and pulling it opens everything.

## The three options

| | What it means | Cost |
|---|---|---|
| **A. Keep ADR-014 as is** | Cloud stays refused except via the global flag | Slower to reach quality; the founding position, intact |
| **B. Scoped derogation** *(this proposal)* | Sovereign by default; a named, configured, logged exception per task type; some categories refused unconditionally | Some complexity; the principle survives and the blunt lever is narrowed |
| **C. Drop sovereignty** | Cloud and local as peers | The thing that makes this project distinct disappears |

## Decision (proposed)

### 1. The derogation is configuration, never a request parameter

A caller may **not** ask for a cloud model. The derogation is declared by the
operator, in configuration, per task type.

This is not caution — it is a defect this repository measured last week. ADR-016
found `CloudFileItem.provider`: a field the caller filled in, recorded as fact,
and reported by `/cloud/stats` as though it described reality. A caller-supplied
"use cloud" flag would be the same defect with higher stakes: the platform would
record a belief about where a request went.

### 2. Three categories are refused unconditionally, whatever the configuration says

| Refused | Why |
|---|---|
| Any request carrying **user memories, files, or knowledge content** | ADR-010 makes these a subject's property. Sovereignty is why the project exists; sending them out is what it exists to prevent |
| **Screen captures** (VOLET 34, ch. 05) | An image of someone's screen is the most revealing payload the platform will ever hold. Phase 2.2 already decided perception is accessibility-first for this reason |
| **Training data export** | Already gated by an approval request (VOLET 33); a cloud path must not bypass a human decision |

What remains eligible is narrow and honest: **stateless reasoning on text the
platform itself produced** — a plan, a code fragment the user has already shared
for that purpose, an evaluation comparison.

### 3. Every derogated call is visible three ways

- an **audit event** naming the task type, the provider and the derogation that
  allowed it — the audit trail is persistent since 2026-08-12, so this survives a
  restart;
- the **response** says which family answered, the way retrieval already says
  whether it was semantic or lexical (ADR-015);
- `/health` lists the active derogations, not just the mode.

A derogation nobody can see is indistinguishable from a leak.

### 4. The global flag stays, and is documented as the blunt instrument

`GALSEN_SOVEREIGN_MODE=false` keeps its evaluation purpose and gains a warning at
start-up: it is wider than any derogation and disables the three refusals above.
Narrowing an existing lever is worth more than adding a new one beside it.

## Why B rather than A or C

**Against A.** The lever that exists is global; the honest choice is not between
"pure" and "compromised" but between one wide switch and several narrow ones.
Option B is *stricter* than today for the categories that matter, because the
three unconditional refusals do not exist yet.

**Against C.** The project's founding statement is that it depends on nobody —
*"cette IA est faite pour être libre"*. Dropping sovereignty removes the thing
that makes a Senegalese platform worth building rather than a wrapper. And it
would be premature: criterion C1 is still open, so the local path has never been
measured. **Abandoning a road nobody has walked is not a decision, it is a guess.**

## Consequences if accepted

- `src/model_engine/providers/provider_registry.py` gains a derogation table read
  from configuration, and the three unconditional refusals.
- `sovereignty_report()` grows a `derogations` field; `/health` surfaces it.
- Audit events record the derogation that allowed each third-party call.
- The existing test — sovereign mode on, every hosted key set, no external
  endpoint reachable — stays, and gains a sibling: **with a derogation active for
  one task type, a request carrying user content is still refused.**

## Consequences if refused

Nothing to undo. VOLET 34's chapters 05 onward hold under every option; only the
ceiling of what a local model can do changes, and phase 2.2 already recorded that
the top of the OSWorld table is proprietary.

## References

- ADR-014 (sovereignty), ADR-003 (providers), ADR-010 (identity and ownership),
  ADR-015 (say which path answered), ADR-016 (a caller-declared field records a
  belief, not a fact)
- `docs/architecture/computer-use-comparison.md` — why screen captures are in the
  unconditional list
- `docs/roadmap/VOLET_34.md` — chapter 04
