# ADR-010: Identity Model — A Key Belongs to a Subject

## Status
Accepted

## Date
2026-08-09

## Context
VOLET_16 (Authentication & Identity Engine) asks for identity management,
authentication services, authorization policies, Single Sign-On, Multi-Factor
Authentication and identity analytics, over a seven-component architecture:
Identity Provider, Authentication Service, Authorization Engine, User Directory,
Token Service, Policy Engine, Audit and Monitoring.

Half of that already exists, and it was not built for this VOLET:

| Component the chapter names | What plays it today |
|-----------------------------|---------------------|
| Authentication Service | `RBACManager.authenticate()` — SHA-256 digests, `hmac.compare_digest` |
| Authorization Engine | `Permission`, `require_permission()` on every route |
| Policy Engine | `_ROLE_PERMISSIONS`, four roles |
| Token Service | API keys are bearer tokens; revocation and hot rotation exist |
| Audit and Monitoring | the audit engine, `/metrics`, `/health` |
| Identity Provider | — |
| **User Directory** | **— nothing** |

The gap is precise and it is the platform's oldest P0: **a key designates a role,
not a person.** `RBACContext` carries a key fingerprint and a role. There is no
account, no identity, and therefore no per-user data. Exit criterion C2 — *two
accounts cannot see each other's memories, files or notifications* — cannot even
be written as a test, and every adoption metric chapter 09 asks for rests on the
same absence.

That is what has to change. What must **not** change is the property that makes
the current design safe and cheap: credentials come from the environment
(ADR-004), instances are configured identically, and no secret is stored by the
platform at all.

## Decision
**A key belongs to a subject.** The declaration format gains a third, optional
field:

```
GALSEN_API_KEYS="cle-admin:admin:awa, cle-terrain:user:moussa, cle-scrutin:readonly"
                 └ secret ┘ └ role ┘ └ subject ┘
```

`RBACContext` gains `subject`. Every authenticated request therefore knows *who*
as well as *what they may do*. A key without a subject keeps working and is
attributed to an anonymous subject, so no existing deployment breaks.

That is the whole change. Its size is the point: it adds identity without adding
a credential store.

### Why not a user table with passwords

Because it would create a liability and remove a property, for a platform with
no user yet:

- **A password store is a secret the platform must keep.** Today it keeps none —
  it holds SHA-256 digests of keys supplied by the environment. Introducing
  password hashes, reset flows and lockout policies means owning a breach
  surface before owning a single user.
- **It would fork the configuration story.** Every other credential in this
  platform comes from the environment (ADR-004, ADR-007). A user directory in
  SQLite would be the first piece of configuration that lives somewhere else,
  and the first that differs between two instances.
- **Nothing needs it yet.** There is no browser login, no self-service
  registration, no password reset request. Building the mechanism before the
  need is what ADR-009 refused for scaling and what chapter 06 of VOLET_04 named
  as this project's failure mode.

When a self-service signup exists, a directory becomes necessary and this ADR is
superseded — with the trigger named rather than a date.

### What is deliberately not built

| Asked by VOLET_16 | Why not now |
|-------------------|-------------|
| Multi-Factor Authentication | there is no login flow to add a second factor to |
| Single Sign-On | one deployment, no external identity provider to federate with |
| Session Management | the API is stateless by design; sessions would reintroduce the affinity ADR-009 avoids |
| Password and credential policies | no password is stored, so there is no policy to enforce |
| Identity analytics | thirteen of nineteen KPIs are already unmeasurable for want of users |

Each is recorded as unaddressed, not as done. `/health` and this file say so.

### What it makes possible immediately

- **Exit criterion C2 becomes writable.** Two subjects, one memory each, and a
  test that one does not see the other's.
- **Audit gains a name.** An audit entry saying "the key ending 745df677f426 did
  X" is forensically weak; "awa did X" is what an operator needs.
- **Per-subject data scoping has an anchor.** Memory, files and notifications can
  filter on a stable identifier that already exists on every request.

## Consequences

### Positive
- Identity arrives without a credential store, so the platform still keeps no
  secret of its own.
- One configuration story, unchanged: the environment declares everything.
- Backward compatible — a two-field key keeps working.
- The gap between what VOLET_16 asks and what exists is now one decision, not a
  vague absence.

### Negative
- **A subject is only as trustworthy as the environment that declared it.** There
  is no identity *verification* — the chapter's lifecycle stage 2. Whoever sets
  `GALSEN_API_KEYS` asserts who each key belongs to, and nothing checks it. That
  is acceptable while the person setting the variable and the person operating
  the platform are the same; it stops being acceptable the day they are not, and
  that is the trigger for a real directory.
- Two people sharing one key are one subject. The platform cannot tell them
  apart, and will not pretend to.
- Rotating a key without preserving its subject silently reassigns the data. The
  reload path keeps the subject bound to the declaration, not to the secret, so
  this is a configuration mistake rather than a code one — but it is possible.

### Neutral
- The anonymous subject (`anonymous`) is a real value, not `None`. Filtering on
  it is meaningful: it groups exactly the keys nobody attributed.

## Alternatives Considered

**A `users` table with password authentication.** Rejected for now — see above.
It is the successor, not a discarded option, and its trigger is self-service
signup.

**OAuth / OIDC against an external provider.** Rejected: it requires an identity
provider to federate with, an internet-facing deployment, and a browser flow.
The platform has none of the three. It also contradicts nothing here — a subject
would then come from a token claim instead of an environment variable, and
`RBACContext.subject` is the seam that makes that a substitution.

**Derive a subject from the key fingerprint.** Rejected as fake identity: it
would make every key look attributed while naming nobody, which is the
fabrication pattern chapter 06 of VOLET_04 forbids.

## Related
- ADR-004 — credentials come from the environment; this ADR extends its format
  rather than competing with it.
- ADR-009 — revocation is instance-local; a subject changes nothing there.
- `docs/roadmap/roadmap.md` — exit criterion C2.
- `src/api/rbac.py` — the implementation; `tests/test_identity.py` — its tests.

---

## Amendment — 2026-08-18 (ADR-029)

The position below — *no credential store, and none planned before self-service
signup* — held until 2026-08-18. **ADR-029 supersedes it**: the project chose
accounts with passwords, and the platform now keeps password hashes.

This ADR predicted its own revision and named the trigger: *"When a self-service
signup exists, a directory becomes necessary and this ADR is revisited."* That is
what happened. Everything else here still stands — a key still declares a
subject, the platform still verifies no identity behind an API key, and the audit
trail still names subjects rather than key digests.

Read the two together: this ADR describes how a **key** carries an identity;
ADR-029 describes how a **person** obtains one.
