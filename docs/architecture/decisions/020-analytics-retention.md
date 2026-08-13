# ADR-020: Whether Analytics History Is Retained — and What It May Contain

## Status
**Proposed** — 2026-08-13. Written by the assistant, **decided by the owner**.
Nothing in this ADR is implemented; `/analytics` behaves today exactly as it did
before it was written.

## Date
2026-08-13

## Context

### What is measured, not remembered

`src/analytics/reporter.py` aggregates sources that already exist and creates
none of its own. Four of the seven sources named by VOLET 09 chapter 04 are
wired (HTTP counters, per-agent audit events, workflow history, search
counters); three are not (memory engine, system logs, external integrations).

Three capabilities are declared **unavailable**, each with its reason:

| Capability | Why it is unavailable |
|---|---|
| `trends` | no time series is kept — counters and workflow history live in process memory and restart at zero (ADR-009) |
| `anomaly_detection` | with no retained history there is no baseline to compare a run against |
| `dashboards` | no visualisation layer; the report is a JSON response |

The first two say the same thing twice: **the platform keeps no history**. That
is not an oversight — it follows from ADR-009 (a single instance, state in the
process) and it is reported rather than hidden.

### Why this is a decision and not a task

Retaining history is a storage decision, and this repository takes storage
decisions in an ADR before code (ADR-005). It is also a **privacy** decision:
the reporter refuses today to let a user query, a subject or a key identifier
enter a report — *"what is measured is the behaviour of the system, not what
people ask"*. Any retention has to say whether that rule survives, because a
retained series is exactly where such a rule quietly erodes.

### Why it is not urgent

`pending-work.md` ranks it P2 and says: worth taking **after C4** — before a
deployment exists there is no operational history worth keeping. Today's
measurement agrees: the platform has never been reached over a network, so the
history that would be retained is the history of test runs.

## The question to decide

**Does GalSen IA keep an analytics history that survives a restart, and if so,
what may that history contain and for how long?**

## Options

### Option A — Keep no history (status quo, and say so permanently)

`trends` and `anomaly_detection` stay `unavailable` with their reason. The
platform reports what it can count now.

- **Cost:** no trend, ever. A degradation is only visible to whoever is
  watching at that moment.
- **Benefit:** nothing to protect, nothing to expire, no privacy surface. The
  smallest possible truthful system.

### Option B — Retain aggregates only, on the existing SQLite store

One row per period (hour or day) per counter: request counts, per-agent
execution counts, error rates, search counts. **No identifier of any kind** —
no user, no key, no query text, no request id. Uses `GALSEN_DATA_DIR` and
`GALSEN_STORAGE_BACKEND` like every other store (ADR-005); no new dependency,
no new service, and the deferred triggers of VOLET 36 stay untouched.

- **Cost:** an aggregate cannot be drilled into. "Which request was slow" is
  unanswerable — only "that hour was slower than usual".
- **Benefit:** trends and a baseline become computable, and the privacy rule
  survives **by construction** rather than by discipline: there is nothing
  personal in the table to leak.

### Option C — Retain events, with a retention window

Keep the audit-level events and expire them after N days.

- **Cost:** the events carry request ids, agent ids and, depending on the
  event, the user request itself. Every future reader of that table becomes a
  privacy question, and the expiry job becomes a thing that must actually run —
  a retention window nobody enforces is a promise, not a control.
- **Benefit:** full drill-down.

## Recommendation

**Option B**, and not before C4 (a reachable deployment).

The reasoning is the one this repository applies everywhere else: build the
smallest thing that answers the question actually being asked. The question is
*"is the platform degrading?"*, and an aggregate answers it. Option C answers
a different question — *"what exactly happened in this request?"* — which the
audit trail already answers while the process lives, and which is precisely the
data whose retention needs a stated purpose.

Option B also keeps the privacy rule enforceable by shape rather than by
vigilance. That distinction has mattered in this codebase before: a rule the
code makes impossible to break survives a refactor; a rule written in a comment
does not.

## Consequences if B is chosen

- `trends` and `anomaly_detection` move out of `UNAVAILABLE_CAPABILITIES` **only
  once they are computed from a real series** — never on the day the table is
  created, when the series is empty and a trend would be an invention.
- The first retained series will be dominated by test traffic unless retention
  starts after C4, which is the reason for the ordering.
- A baseline needs a stated minimum before it means anything, in the way
  `src/training/improvement.py` already refuses to conclude under 30 feedbacks
  per window. The same refusal belongs here.

## What is decided today

**Nothing.** This ADR is `proposed`; `/analytics` is unchanged and still reports
its three unavailable capabilities with their reasons. The decision — A, B or C,
and when — belongs to the owner.
