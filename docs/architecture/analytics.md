# Analytics

What VOLET_09 asks for, and what the platform could measure about itself before this
VOLET. Measured against the repository on 2026-08-11.

---

## There was no analytics engine (chapters 01 and 02)

`src/` contained no analytics package. What existed was **collection without
aggregation**: the audit engine recorded events, `/metrics` counted HTTP traffic, and
nothing turned either into an indicator.

The manual names seven components:

| Component | What plays it | State |
|-----------|---------------|-------|
| Event Collector | audit engine, `RequestMetricsMiddleware` | present |
| Metrics Engine | `MetricsTool`, `/metrics` | present |
| Analytics Processor | `src/analytics/reporter.py` | **added by this VOLET** |
| Reporting Service | `GET /analytics` | **added by this VOLET** |
| Data Pipeline | — | **absent**: no ingestion, no enrichment stage |
| Dashboard Layer | — | **absent**: the report is JSON |
| Governance Module | — | **absent** |

Four of seven. The two added ones were built as an **aggregation layer over existing
sources**, not as a new collector: a second count of the same executions would create two
truths and no way to say which is right.

## Data sources (chapter 04): four of seven

| Source the manual names | Fed by |
|-------------------------|--------|
| User interactions | HTTP counters (`RequestMetricsMiddleware`) |
| AI services | audit events, per agent |
| Workflow Engine | `WorkflowHistory` (VOLET 08) |
| Knowledge Engine | search counters (VOLET 14) |
| **Memory Engine** | **nothing** |
| **System logs** | **nothing**: written to a file, never aggregated |
| **External integrations** | **nothing** |

`source_coverage()` returns this table at runtime, so the manual's list is never mistaken
for an inventory of what exists.

## What the report says

`GET /analytics` (restricted to `ADMIN_AUDIT`) aggregates:

- **agents**: executions, status breakdown, success rate and median/max duration **per
  agent**, from audit events. Only `agent` events are counted — mixing in tool calls
  would inflate the execution count, and one two-agent run produces 20 audit events.
- **workflows**: the success rate from `WorkflowHistory`, reused as-is.
- **requests** and **search**: taken verbatim from `/metrics`.
- **coverage** and **unavailable**.

**An absent source returns `null`, never `0`.** Zero reads as a measurement — "no agent
ran" — when the truth is "nothing was measured". The API process holds no `RouterEngine`,
so `workflows` is `null` there today, and the report says so instead of reporting a
success rate of zero.

## Three capabilities the chapter asks for and this cannot deliver

Named in `unavailable`, each with its reason:

- **Trends** — no time series is retained. Counters and history live in process memory and
  restart at zero (ADR-009).
- **Anomaly detection** — without retained history there is no baseline to compare a run
  against.
- **Dashboards** — there is no visualisation layer; the report is a JSON response.

These are not omissions to fill by writing plausible numbers. A "trend" computed over a
counter that resets on every deploy would be worse than no trend, because someone would
act on it.

## Privacy (chapter 01, "privacy by design")

No user request, subject or key fingerprint enters a report. What is measured is the
system's behaviour, not what people ask — the same line drawn for search analytics in
VOLET 14. A test searches for a distinctive string through `/knowledge/search` and asserts
it appears nowhere in `/analytics`.

## What would make this real

The single change that unlocks trends, anomaly detection and everything chapter 05 calls
"processing" is **retention**: analytics data that survives a restart. That is a storage
decision (an ADR), not a coding task, and it is worth taking after exit criterion C4 —
before a deployment exists, there is no operational history worth keeping.
