# Identity and Authentication

What VOLET_16 asks for, what exists, and what is deliberately absent. Every figure here
was measured against the repository. The decision that shapes it is ADR-010: **a key
belongs to a subject.**

---

## The seven components, against the code

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| Authentication Service | `RBACManager.authenticate()` — SHA-256 digests, `hmac.compare_digest` | done |
| Authorization Engine | `Permission`, `require_permission()` on every route | done |
| Policy Engine | `_ROLE_PERMISSIONS`, four roles | done |
| Token Service | API keys are bearer tokens; revocation and hot rotation exist | done |
| Audit and Monitoring | audit engine, `/metrics`, `/health` | done |
| Identity Provider | the environment (ADR-004) declares who holds each key | partial |
| User Directory | — | **absent by decision** |

Five were already in place before this VOLET and were not built for it. One — the
directory — is absent because ADR-010 refuses to own a credential store before the
platform owns a user.

---

## Lifecycle (chapter 03)

The chapter names nine stages. Six are implemented, one is absent and named, two are
configuration rather than code.

| Stage | Where it happens |
|-------|------------------|
| 1. Registration | a line in `GALSEN_API_KEYS`: `secret:role:subject` |
| 2. **Verification** | **nothing.** Whoever writes the variable asserts the identity |
| 3. Authentication | `RBACManager.authenticate()` |
| 4. Authorization | `require_permission()` per route |
| 5. Token issuance | the key *is* the token — no separate issuance |
| 6. Access monitoring | `/metrics` (`auth.success`, `auth.failure`), audit engine |
| 7. Update | `POST /auth/keys/reload` — no restart |
| 8. Suspension / revocation | `POST /auth/keys/{fingerprint}/revoke`, `/restore` |
| 9. Secure retirement | remove the line, then reload |

Stage 2 is the honest gap and the trigger for a real directory: it stops being acceptable
the day the person setting the variable is not the person operating the platform.

---

## Security (chapter 05)

The chapter lists MFA, password policies, token protection, session security, anomaly
detection and audit logging. Three are met, three do not apply to this design, and saying
which is which matters more than the list.

**Met:**

- **No secret is stored.** The platform holds SHA-256 digests of keys supplied by the
  environment. There is nothing to leak from a database dump — a property a password store
  would remove.
- **Constant-time comparison.** `hmac.compare_digest`, so a timing measurement cannot
  recover a key one character at a time. A dictionary lookup would have been simpler and
  would have leaked.
- **Containment.** A revoked key stops working immediately, and the response says the
  revocation is instance-local (ADR-009) so an operator does not believe an incident
  closed that is not.

**Not applicable, by design rather than by omission:**

- **Password policies** — no password is stored, so there is no policy to enforce.
- **Session security** — the API is stateless; every request carries its key. Sessions
  would reintroduce the affinity ADR-009 avoids.
- **MFA** — there is no login flow to add a second factor to.

**The incident response the chapter asks for**, mapped to what exists:

1. Detect — `auth.failure` in `/metrics`, warnings in the log.
2. Validate — `GET /auth/keys` shows every fingerprint, its role, its subject.
3. Contain — `POST /auth/keys/{fingerprint}/revoke`, immediate.
4. Revoke durably — remove from `GALSEN_API_KEYS`, then reload or restart.
5. Recover — nothing else to restore; the platform holds no session.
6. Review — the audit engine keeps what was done, now under a name rather than a
   fingerprint.

Step 3 has a limit that is stated in its own response: revocation lives in process memory,
so with more than one instance a compromised key keeps opening the others.

---

## Monitoring (chapter 06)

The chapter's two headline metrics are the authentication success rate and the failed
login rate. Both are live:

```
GET /metrics → "auth": { "attempts": 4, "succeeded": 2, "failed": 2, "success_rate": 0.5 }
```

Three decisions in that block:

- **The counters name nobody.** Counting attempts per subject would turn an operational
  measurement into individual tracking. A test asserts no subject appears in a counter
  name.
- **`success_rate` is `null` with no attempts, not `0`.** Zero would read as "everything
  fails".
- **Failures are counted before the refusal is raised.** Otherwise the only category an
  investigation cares about would be the only one missing from the numbers.

What the chapter asks for and is **not** built: anomaly detection, proactive alerting,
session duration. The first two need a baseline nobody has yet; the third needs sessions,
which this design does not have.

---

## Compliance (chapter 07)

The compliance question that can be answered today is narrow and concrete: **what personal
data does the platform hold?**

| Data | Where | Why it is held |
|------|-------|----------------|
| Subject identifier | in memory, parsed from the environment | to attribute data and audit entries |
| Key digest | in memory | to authenticate without storing the key |
| Memory / file / notification content | store selected by `GALSEN_STORAGE_BACKEND` | it is the product |

Nothing else. No email, no phone number, no address, no password — the platform never
asks for them, so it cannot leak them. *Privacy by design*, in the chapter's words, is
here a consequence of ADR-010 rather than a policy on top of it.

**Retention is not implemented.** Data lives until deleted; nothing expires. That is a
real gap for any regulated deployment and it is recorded as one rather than glossed. It
becomes actionable the day the platform holds someone else's data — which is the same
trigger as identity verification.

Encryption at rest exists (`GALSEN_ENCRYPTION_KEY`, VOLET_02 ch. 08) and covers memory and
knowledge content.

---

## Governance (chapters 08 and 10)

**Chapter 10 repeats chapter 08.** Both are titled *Authentication & Identity Governance*;
10 restates 08 at "enterprise" scope, adding strategic oversight and cross-system
coordination. They are answered together because answering them separately would produce
the same text twice, and this project's rule is not to duplicate documentation.

The manual assigns six bodies: Identity Governance Board, Security Team, Identity
Administrators, Compliance Officers, System Owners, Audit Team. **This project has one
person.** As in VOLET_04 chapter 10, the roles are real but they are played by mechanisms:

| Role | What plays it |
|------|---------------|
| Identity policy definition | ADR-010, with its rejected alternatives |
| Approval of major changes | the phase protocol — one phase, then a stop |
| Identity administration | `GALSEN_API_KEYS`, plus `/auth/keys` to inspect it |
| Audit | the audit engine, and `auth.*` in `/metrics` |
| Compliance verification | `scripts/release_check.py` refuses a release with a tracked secret |

What has no mechanism: **access certification** — nobody periodically re-reads
`GALSEN_API_KEYS` to ask whether each key should still exist. `GET /auth/keys` makes the
review possible; nothing makes it happen.

---

## Quality (chapter 09)

| Metric the chapter asks for | Available |
|-----------------------------|-----------|
| Authentication success rate | yes — `/metrics` |
| Failed login rate | yes — derived from the same block |
| Authentication latency | yes — `http.latency.get.auth.whoami` and every other route |
| Identity service availability | no — nothing is deployed (criterion C4) |
| Incident resolution time | no — no incident has occurred |
| User satisfaction | no — no user |

Three of six, and the three missing are blocked by the same facts as the rest of the
platform's KPIs. The chapter's optimisation loop — measure, analyse, improve, validate —
has its first step now; the second needs a baseline, which needs traffic.

---

## What is deliberately not built

Recorded so it is not mistaken for an oversight, each with what would trigger it:

| Absent | Trigger |
|--------|---------|
| User directory with passwords | self-service signup |
| Identity verification | the declaring party is no longer the operator |
| MFA | a browser login flow exists |
| SSO / OIDC | an external identity provider to federate with |
| Session management | never — the stateless API is the design |
| Retention policy | the platform holds data belonging to someone else |
| Access certification | more keys than one person can review at a glance |
| Anomaly detection, alerting | a traffic baseline exists |

---

*VOLET 16 — the code is in `src/api/rbac.py`, `src/api/metrics.py` and the scoped routes
of `src/api/server.py`; the tests in `tests/test_identity.py` (33) and
`tests/test_api_metrics.py` (16).*
