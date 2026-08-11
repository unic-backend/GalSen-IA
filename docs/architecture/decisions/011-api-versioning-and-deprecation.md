# ADR-011: API Versioning and Deprecation — Announce, Do Not Prefix

## Status
Accepted

## Date
2026-08-11

## Context
VOLET_15 chapter 04 asks the gateway to "maintain version control" and to "retire
obsolete APIs safely"; chapter 08 repeats both as governance policies. Neither existed.

Measured on 2026-08-11: 63 routes, **no version prefix anywhere**, no version negotiation
header, and no mechanism to mark a route as going away. The only available retirement was
deletion, which a caller discovers as a 404 in production.

The obvious answer — prefix everything with `/v1` — is not free:

- Every client, the shipped web UI, the SDK and the documentation change at once.
- A `/v1` prefix is a **promise**. It says "this shape is stable, breaking changes will
  land in `/v2`". The platform is a prototype (`__release_type__ = "prototype"`), its main
  capability answers 503 for lack of a configured provider, and exit criterion C1 is not
  met. Announcing stability the project cannot honour is the same failure mode this
  repository has repeatedly paid for: a plausible answer instead of a real state.
- It costs a migration now and buys nothing until there is a second version to migrate to.

Meanwhile the real gap is narrower than versioning: a caller has no way to learn that a
route is going away **before** it goes.

## Decision

**No URL versioning while the platform is a prototype.** `/api/versions` states this
explicitly rather than leaving an implicit `/v1` to be assumed.

**Deprecation is announced through RFC 8594 headers.** A route in end of life answers with
`Deprecation: true`, plus `Sunset: <HTTP-date>` when a removal date is decided, plus
`Link: <replacement>; rel="successor-version"` when there is a replacement. These are
standard headers that existing clients already understand — nothing bespoke to teach.

The announcement is carried by a middleware, not a per-route dependency: it must cover
**every** response of a deprecated route, its errors included, and a forgotten dependency
would restore exactly the silence being removed.

**The deprecation registry starts empty**, because no route is deprecated. Registering a
sample entry to demonstrate the mechanism would fabricate a fact; the mechanism is proven
by tests instead.

**Deprecation is not removal.** A deprecated route keeps working and keeps returning its
normal status code. The headers are the notice period.

## Consequences

Positive:

- A breaking change can now be announced ahead of time, with a date and a successor.
- `/api/versions` gives an operator or a client one place to ask what is going away.
- No migration is imposed on any consumer today.

Negative, and accepted:

- Two versions of a route cannot be served concurrently. When that is genuinely needed —
  it is not today, there being one consumer — this ADR is superseded rather than
  stretched.
- Header-based announcements are invisible to a caller who never reads response headers.
  `/api/versions` exists for that reason, but nothing forces anyone to read it.
- `Sunset` is informational. Nothing in the platform enforces the date; removing the route
  on time remains a human decision, tracked like any other work.

## Alternatives considered

- **`/v1` prefix now** — rejected above: a stability promise the prototype cannot keep,
  paid for immediately.
- **Version negotiation by header** (`Accept: application/vnd.galsen.v1+json`) — same
  promise as a prefix, with worse discoverability and no cacheability, for the same
  non-existent second version.
- **Semantic versioning of the API separate from the platform version** — two numbers that
  drift is precisely the defect `src/version.py` was written to end.
