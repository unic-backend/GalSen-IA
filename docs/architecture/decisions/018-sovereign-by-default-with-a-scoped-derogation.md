# ADR-018: Sovereign by Default, With a Scoped Derogation

## Status
**Accepted — option B**, decided by the owner on 2026-08-12.

`GALSEN_SOVEREIGN_MODE` still defaults to `true`, and the test asserting it is
untouched: **B does not loosen the default, it narrows the exception.** The three
unconditional refusals below did not exist before this ADR, so a platform under
option B refuses strictly more than the one that preceded it.

Implemented in `src/model_engine/providers/derogations.py`.

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
| **B. Scoped derogation** *(chosen)* | Sovereign by default; a named, configured, logged exception per task type; some categories refused unconditionally | Some complexity; the principle survives and the blunt lever is narrowed |
| **C. Drop sovereignty** | Cloud and local as peers | The thing that makes this project distinct disappears |

## Decision

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

## What was built (2026-08-12)

- **`src/model_engine/providers/derogations.py`** — `GALSEN_SOVEREIGN_DEROGATIONS`,
  read as `task_type:provider_id`, **configuration only**. A malformed entry is
  dropped with an error rather than guessed, and declaring one of the three
  refused categories is itself refused and logged: an operator error is not an
  authorisation.
- **`ProviderRegistry.register`** admits a hosted provider only when a derogation
  names it. Admission is not permission: `allow()` still decides per call, per
  task type.
- **`allow(task_type, provider_id, carries_user_content)`** returns a decision
  *and its reason*, in both directions — the reason is what the audit records and
  what the response can carry. `carries_user_content=True` refuses whatever the
  configuration says, and **a doubt counts as true**: erring that way costs a
  slower answer; erring the other way costs someone's data.
- **`sovereignty_report()["derogations"]`** — surfaced by `/health` and by
  `/security/posture` (VOLET 34, ch. 13), because a derogation nobody can see is
  indistinguishable from a leak.

Tests: `tests/test_sovereign_derogations.py`. The pre-existing sovereignty test is
unchanged, and now has the sibling this ADR promised — a derogation active for one
task type still refuses a request carrying user content.

## References

- ADR-014 (sovereignty), ADR-003 (providers), ADR-010 (identity and ownership),
  ADR-015 (say which path answered), ADR-016 (a caller-declared field records a
  belief, not a fact)
- `docs/architecture/computer-use-comparison.md` — why screen captures are in the
  unconditional list
- `docs/roadmap/VOLET_34.md` — chapter 04
