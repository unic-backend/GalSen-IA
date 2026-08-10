# ADR-029: Does the platform have users?

## Status
**Proposed** — this ADR states the decision to be taken. It does not take it.

## Date
2026-08-18

## Context

`docs/memory/priorities.md` ranks this second, above every feature: *"Decide
whether the platform has users (P0). An ADR before any code — it gates Phase 2's
workspace, Phase 3's collaboration and every adoption metric."*

The code that would implement one answer already exists. A branch
(`feature/service-unit-tests`, one commit, 10 August) built a JWT and OAuth login
layer: `src/auth/` with a JWT handler, session manager, user manager and three
OAuth login providers, plus `SQLiteUserStore` holding accounts and **password
hashes**. It has been rebased onto the current line as
`claude/auth-jwt-oauth-rebased`, its 105 tests pass, and it is lint-clean.

**It is not mounted.** No route reaches it. That is deliberate, because mounting
`/auth/register` would create the credential store at the first call — and
ADR-010 rejected exactly that:

> A password store is a secret the platform must keep. Today it keeps none —
> adding password hashes, reset flows and lockout policies means owning a breach.

ADR-010 also names the trigger for revisiting itself: *"When a self-service
signup exists, a directory becomes necessary and this ADR is revisited."* This
ADR is that revisit, opened early because the code arrived before the decision.

### What exists today

Identity is a key that **declares** a subject (ADR-010). `GALSEN_API_KEYS` maps
`secret:role:subject`; an audit trail can say "awa did X" rather than "key
745df677f426 did X". Nobody verifies that awa is awa. That is stated, not hidden:
the operator who writes the variable asserts the mapping, and the platform keeps
no secret of its own.

The `/oauth/*` routes already on the platform are a different thing entirely, and
the names collide dangerously. They authorise **GalSen IA** to read a Google
account on the operator's behalf (`src/connectors/oauth`). The branch's OAuth
would let **a person** enter. Confusing the two would give a connector the rights
of a user.

## The decision to take

**Does GalSen IA have accounts of its own?** Three answers are coherent; the
project must pick one, and each closes doors the others leave open.

### Option A — No accounts. Keys only, as today.

The platform keeps no secret. Identity stays a declaration, verified by whoever
writes the environment. Multi-user products are built *in front of* GalSen IA,
by a caller that has its own users and holds its own key.

- **Costs**: no per-person workspace, no collaboration, no adoption metric that
  counts people. `src/auth/` is deleted, and 105 tests with it.
- **Keeps**: the strongest property this platform has — it stores nothing whose
  loss would be a breach of someone else's credentials.

### Option B — Accounts, but no passwords. OAuth only.

People enter through Google, GitHub or Microsoft. The platform stores an account
row and a provider identifier, **never a password hash**. Authentication is
delegated to a party already in that business.

- **Costs**: no offline use, no account without a third-party identity, and a
  dependency on providers whose availability is not ours. Requires the operator
  to register an application with each.
- **Keeps**: ADR-010's central argument intact — no password store, so no
  password breach. `SQLiteUserStore` survives with its hash column removed.

### Option C — Accounts with passwords, as the branch implements.

Full self-service: register, log in, refresh, reset. The platform owns the
credential store.

- **Costs**: password hashing policy, reset flows, lockout, breach
  notification, and the obligation ADR-010 named — owning a breach. In a
  single-instance deployment (ADR-013) with the default in-memory backend,
  sessions and revocations do not even survive a restart.
- **Keeps**: works with no third party, offline, anywhere.

## What is not being decided here

Which options are technically possible — all three are. This is a question about
what the platform is willing to be responsible for, and that is not an
engineering call.

## Consequences of leaving it open

The branch rots or the code rots around it. That is why it was rebased rather
than left at its 10 August base, 326 commits behind: whichever way this goes, the
work is either deleted deliberately or adopted deliberately, not lost to drift.

Until then:

- `src/auth/` ships but is **unreachable** — no route, no store created.
- `tests/test_auth_hybrid.py` is skipped, naming this ADR as its reason.
- `tests/test_auth_jwt.py` and `tests/test_auth_oauth.py` run: they need no route.
- The three dependencies (`PyJWT`, `bcrypt`, `requests`) are declared, because
  the code that imports them is present and the dependency guard is right to
  demand it.

## Notes

Two defects were found while rebasing, both in the branch's own code, both fixed:

- `SQLiteUserStore` wrote its SQLite PRAGMAs by hand instead of calling
  `prepare_connection`, and in doing so omitted `journal_mode=WAL` and
  `synchronous=NORMAL`. Without them readers and the writer block each other and
  a hot backup is not possible. A repository guard caught it — which is what a
  second copy of a rule always eventually costs.
- Eight lint violations, including two variables assigned and never read. Neither
  hid a missing assertion; both were checked before removal.

The branch's own commit message records a third, found by its author: a supplied
Bearer token used to fall back silently to `X-API-Key`, so an expired user token
combined with an admin key granted admin access. That was fixed there.
