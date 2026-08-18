# Security

What VOLET_11 asks for, and what the platform's security mechanisms actually do. Measured
against the repository on 2026-08-11.

This file does not restate the security rules — they live in `.claude/rules/security.md`
and in ADR-010 (identity). What is recorded here is the **gap between a control and what
it controls**, which no rule file can contain about itself.

---

## What already existed

Security was the best-covered area of the repository before this VOLET, because three
earlier ones built it:

| Control | Where | Verified by |
|---------|-------|-------------|
| Authentication | `RBACManager`, SHA-256 digests, `hmac.compare_digest` | `tests/test_rbac.py` (28 tests) |
| Authorisation | `Permission`, `require_permission()` per route | VOLET 16 |
| Data isolation | another subject's data answers **404, not 403** | exit criterion C2 |
| Encryption at rest | `src/storage/encryption.py` | 21 tests |
| Rate limiting | `InMemoryRateLimiter`, per key and per IP | 23 tests |
| Security headers | `src/api/security_headers.py` | 17 tests |
| Key revocation | hot reload, `POST /auth/keys/reload` | VOLET 02 ch. 08 |
| Audit trail | audit engine, every agent and tool call | VOLET 01 ch. 03 |

Coverage measured on the critical paths: `rbac.py` 99 %, `rate_limiter.py` 96 %,
`encryption.py` 94 %.

## The gap: counting is not detecting (chapter 05)

Measured before this VOLET — twelve authentication attempts with **twelve different keys**
from one source, which is credential stuffing in its plainest form:

```
auth : {'attempts': 13, 'succeeded': 1, 'failed': 12, 'success_rate': 0.0769}
```

The platform knew that twelve attempts had failed. It did not know **who** had failed
them, when, or whether it was still happening — no source, no window, no threshold, no
signal. `/metrics` is a counter, and a counter never raises an alarm.

`src/api/threat_detection.py` adds the smallest honest thing: a **sliding window of
failures per source**, with a declared threshold (10 failures in 300 s, both
configurable), three severity levels tied to multiples of the threshold, and
`GET /security/threats` to read them.

**What it does not do is named in the response**, not omitted:

| Method the chapter names | Why it is absent |
|--------------------------|------------------|
| Behavioural analytics | needs a normal-usage profile per user; the platform has neither declared users nor retained history (ADR-009) |
| Threat intelligence correlation | needs an external indicator feed; none is configured, and this check makes no outbound call |
| Machine-assisted analysis | needs a model provider, which is not configured (criterion C1) |

A sliding window of failures is honest detection. Calling it anything else would not be.

## The bypass found while building it

The first version cleared a source's failures on successful authentication — the obvious
way to reduce false positives, and it was measurably wrong. Running the end-to-end check
returned **zero threats after twelve failures**, for two different reasons:

- an attacker who eventually finds a valid key erases the record of every attempt that led
  there;
- the operator reading `/security/threats` from the same address erases what they came to
  observe.

Successes are now recorded **beside** failures, never instead of them. The threat stays
visible and carries `succeeded_in_window`, which says "this may be a human who mistyped"
without letting anyone silence the signal. The false-positive reduction the chapter asks
for is kept; the bypass is gone.

## Privacy of the security data itself

A threat report names an **address**, never a key and not even a key fingerprint. A log of
who is attacking, listing credentials, becomes a target in its own right. A test searches
for a distinctive key string and asserts it appears nowhere in `/security/threats`.

The route requires `ADMIN_AUDIT`: knowing who is attacking the platform is not public
information. A `readonly` key gets 403, no key gets 401.

Two more bounds worth stating: the detector tracks at most 1 000 sources — a detector whose
memory follows the traffic *is* the denial of service — and everything lives in process
memory (ADR-009), which the response says rather than implies.

## Incident response (chapter 06)

The chapter's six-step process — detect, assess, contain, eradicate, recover, review —
now has its **first** step and part of the second: detection exists, and severity is
classified.

The rest does not, and is not simulated:

- **Contain**: nothing blocks a source. The rate limiter slows every client equally; it
  does not react to a threat.
- **Eradicate / recover**: no automated action, no runbook.
- **Post-incident review**: the audit trail supports forensics, but nothing records an
  incident as an object with a lifecycle.

Containment is the next real step, and it is deliberately not taken here: automatically
blocking an address is the kind of control that locks out a legitimate operator behind a
shared NAT on its first false positive. It needs a decision about who can be blocked, for
how long, and how to get out — an ADR, not a patch.
