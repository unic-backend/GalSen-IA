# Performance Targets

VOLET_03 chapter 08 asks for measurement before optimisation, and `release_check.py` has
been refusing to tick "performance targets verified" for one honest reason: **no target
existed.** A measurement with no threshold informs no decision.

These targets are derived from measurements taken on 2026-08-10, not chosen in advance.

---

## What is being measured

**Server-side processing only** — the time between the request entering the API and the
response leaving it. Network latency is deliberately excluded: nothing is deployed yet
(exit criterion C4), so any end-to-end figure would be invented. The day the platform is
reachable, a second table gets added here for end-to-end latency; until then this file
says what it measures and no more.

Method: 100 calls per route through `fastapi.testclient`, rate limiter disabled (at 60
rpm it truncates the sample), knowledge base loaded with 200 items.

## Measured baseline

| Route | Median | p95 | Max |
|-------|--------|-----|-----|
| `GET /health` | 1.89 ms | 2.19 ms | 3.67 ms |
| `GET /metrics` | 1.82 ms | 2.31 ms | 2.54 ms |
| `POST /knowledge/search` | 2.49 ms | 2.88 ms | 3.72 ms |
| `POST /search` | 3.16 ms | 3.49 ms | 3.92 ms |
| `GET /search/status` | 3.07 ms | 3.55 ms | 4.28 ms |
| `GET /knowledge/quality` | 2.38 ms | 2.81 ms | 3.28 ms |

Engine-level measurements from earlier VOLETs, same machine:

| Operation | Measured |
|-----------|----------|
| Cached knowledge search | 0.234 ms |
| Uncached knowledge search | 0.50 ms |
| Index build, 1 000 documents | 8.0 ms |
| Index integrity check, 1 000 documents | 6.8 ms |
| Incremental indexing | 0.011 ms / document |

## Targets

| Class of route | Target (p95) | Rationale |
|----------------|--------------|-----------|
| Liveness and metrics (`/health`, `/metrics`, `/live`, `/ready`) | **≤ 50 ms** | 20× the current p95. These must answer while the platform is degraded, so the target has to hold when engines are slow |
| Read and search (`/knowledge/search`, `/search`, `/search/status`, reports) | **≤ 200 ms** | ~60× the current p95, which is the room a real knowledge base needs. Below 200 ms a search feels instantaneous to the person typing |
| Write (`/memory/store`, `/file/upload`, knowledge writes) | **≤ 500 ms** | writes fsync and re-index; the operator waits for a confirmation, not for a result to read |
| Model generation | **no target** | dominated by the provider, which the platform does not control. What is targeted is the platform's own overhead, ≤ 100 ms outside the provider call |

The multiples are large on purpose. A target set at twice the current measurement would
fail on a slower machine, on a loaded CI runner, or the first time the knowledge base
holds real documents — and a threshold that fails for reasons unrelated to a regression
gets disabled within a month.

**These are p95 targets, not averages.** An average hides the request that took two
seconds; the person who waited is not comforted by the mean.

## Regression rule

A change that pushes a route past its target is a regression, and the target is the thing
that says so. Two rules follow from it:

- **Measure before optimising** (chapter 08). The engine measurements above exist because
  each was taken before and after a change, and one of them — the query cache — turned out
  to be doing nothing at all until it was measured.
- **A target that is missed is either fixed or moved deliberately**, with the reason
  written here. Silently raising a threshold to make a check pass is the same failure as
  weakening a test assertion.

## What is not targeted, and why

- **End-to-end latency**: nothing is deployed (C4). Senegalese mobile networks will
  dominate any such figure, and inventing one before the first deployment would set the
  bar in the wrong place.
- **Throughput and concurrency**: one instance, no load test, no user. ADR-009 records the
  two subsystems that block a second instance; until they are shared, a throughput target
  would describe a configuration nobody runs.
- **Memory and CPU ceilings**: the container has no declared limit yet. This becomes
  measurable with C4.

Each of these is a "not yet", with the condition that makes it measurable — not an
omission.
