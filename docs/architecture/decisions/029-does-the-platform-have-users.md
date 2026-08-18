# ADR-029: Does the platform have users?

## Status
**Accepted** — Option C. Decided by the project owner on 2026-08-18, after this
ADR was published as `Proposed` with the three options and their costs.

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
hashes**. It was rebased onto the current line as
`claude/auth-jwt-oauth-rebased`, where its tests pass and it is lint-clean.

Until this decision it was **not mounted** — no route reached it — because
mounting `/auth/register` would create the credential store at the first call,
and ADR-010 rejected exactly that:

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

## The decision taken

**Option C: accounts with passwords.** GalSen IA owns a credential store.

What that makes the platform responsible for, stated here so it is not
discovered later:

- **Password hashes are a secret the platform keeps.** bcrypt, 12 rounds, and a
  72-byte limit enforced explicitly rather than left to the library — older
  bcrypt versions truncated silently, and two passphrases sharing their first 72
  bytes authenticated each other.
- **The signing secret has no default.** `GALSEN_JWT_SECRET`, 32 characters
  minimum, or no token is issued and the routes answer 503 with the command that
  generates one. The original code shipped a default written in the repository
  and only logged a warning; anyone who read the source could forge an admin
  token.
- **A presented Bearer token is authoritative.** Invalid or expired means
  refused, never a silent fall back to `X-API-Key`.
- **A refresh re-reads the role from the store**, never from the token, so a
  demotion takes effect at the next renewal.
- **Login does not distinguish "unknown account" from "wrong password"**;
  distinguishing them would tell an attacker which addresses exist.
- Still owed, and not delivered by this ADR: password reset, lockout after
  repeated failures, and breach notification. Under the default in-memory
  backend the account store is SQLite but sessions are not; `GALSEN_STORAGE_BACKEND=sqlite`
  is what makes the whole thing survive a restart.

### The options that were on the table

**Does GalSen IA have accounts of its own?** Three answers are coherent; the
project must pick one, and each closes doors the others leave open.

#### Option A — No accounts. Keys only. *(not taken)*

The platform keeps no secret. Identity stays a declaration, verified by whoever
writes the environment. Multi-user products are built *in front of* GalSen IA,
by a caller that has its own users and holds its own key.

- **Costs**: no per-person workspace, no collaboration, no adoption metric that
  counts people. `src/auth/` is deleted, and 105 tests with it.
- **Keeps**: the strongest property this platform has — it stores nothing whose
  loss would be a breach of someone else's credentials.

#### Option B — Accounts, but no passwords. OAuth only. *(not taken)*

People enter through Google, GitHub or Microsoft. The platform stores an account
row and a provider identifier, **never a password hash**. Authentication is
delegated to a party already in that business.

- **Costs**: no offline use, no account without a third-party identity, and a
  dependency on providers whose availability is not ours. Requires the operator
  to register an application with each.
- **Keeps**: ADR-010's central argument intact — no password store, so no
  password breach. `SQLiteUserStore` survives with its hash column removed.

#### Option C — Accounts with passwords. **← taken**

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

## Consequences

- `/auth/register`, `/auth/login` and `/auth/refresh` are mounted. `/auth/me`
  now accepts both a Bearer token and an API key, and says which one served.
- ADR-010 is amended, not silently contradicted: its "no credential store"
  position held until this decision, and its own trigger — "when a self-service
  signup exists, a directory becomes necessary and this ADR is revisited" — is
  what opened this one.
- API keys keep working unchanged. Every existing route still authenticates the
  way it did; nothing was migrated.
- The platform now has something to lose. That is the cost of Option C, it was
  stated before the choice, and it is not reversible by deleting code — only by
  deleting the accounts.

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
