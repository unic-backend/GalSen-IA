# API Gateway

What VOLET_15 asks of the API Gateway, and what the platform actually runs.
Measured against the repository on 2026-08-11.

---

## What the gateway is here

There is no separate gateway process. The gateway **is** the FastAPI application
(`src/api/server.py`), and its controls are middleware plus per-route dependencies.

That is worth stating before anything else, because the manual's vocabulary — "route
requests to target services", "balance traffic across services", "deliver request to
target service" — describes a proxy in front of several backends. This platform has one
process and no backend to proxy to. Routing means dispatching to a Python function, not
forwarding to a service.

So the honest reading of VOLET 15 is: *the entry point's controls*, not *the reverse
proxy*. Everything below is measured against that reading, and the components that only
make sense with multiple backends are named as absent rather than reinterpreted until
they look present.

## The seven components (chapter 02), against the code

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| API Gateway Core | the FastAPI app — 63 routes | present |
| Authentication Service | `require_auth` (`src/api/rbac.py`) | present |
| Authorization Engine | `require_permission`, RBAC roles | present |
| Rate Limiter | `InMemoryRateLimiter` + `rate_limit_dependency` | present |
| Monitoring and Analytics | `RequestMetricsMiddleware`, `metrics_snapshot()` | present |
| Logging Service | rotating application log | present |
| **Routing Engine** | FastAPI's own dispatch | **n/a**: no target service to route to |

Six of seven, with the seventh not applicable rather than missing.

## The request flow (chapter 02), measured

The manual's flow is *receive → authenticate → authorize → route → respond → record*.
What actually runs, in order:

```
CORSMiddleware             ← le plus externe
RequestMetricsMiddleware
SecurityHeadersMiddleware  ← le plus proche de la route
   → rate_limit_dependency
   → require_auth / require_permission
   → la fonction de route
```

Execution order is the **reverse** of the `add_middleware` calls — Starlette inserts each
new middleware at the head of the stack. That inversion is invisible when reading
`server.py` top to bottom, and two properties depend on it.

**The metrics layer wraps the security headers**, so it observes the status code actually
returned. A metrics layer that measures a response nobody receives is worse than no
metrics. Measured: an unauthenticated `GET /metrics` answers 401, that 401 carries
`X-Content-Type-Options` and `X-Frame-Options`, and the counters record one request at an
error rate of 1.0. An error response is still a response — headers posted only on
successes leave the most common case unprotected.

**Rate limiting runs before authentication.** This is the one place where the running
order deviates from the manual's flow, and deliberately: an unauthenticated flood must be
cheap to reject, and making the limiter wait for authentication would mean every abusive
request pays for a key lookup first. Measured with a two-per-minute budget and no key:

```
5 appels sans clé → [401, 401, 429, 429, 429]
```

`tests/test_gateway_request_flow.py` locks all three: the headers on an error, the status
code the counters see (with a counter-test on a successful call, so marking everything as
an error would not pass), the 401-then-429 sequence, and the middleware order the first
two depend on. Written first against the wrong assumption about `user_middleware` — the
list is already in execution order, not in insertion order — and the failing test is what
said so.

## Coverage of the two controls, and why it is now a test

Every control here is opt-in per route. That kind of arrangement does not fail loudly; it
fails the day someone adds a route and forgets a dependency, and nothing says so.

Measured on 63 routes:

| | Covered | Exceptions |
|---|---------|------------|
| Authentication or permission | 59 | `/`, `/health`, `/ready`, `/live` |
| Rate limiter | 62 | `/` |

The four exceptions are deliberate. The three probes must answer without a key — an
orchestrator restarting a container does not authenticate, and a liveness probe gated on
an expired key restarts a perfectly healthy application. `/` only redirects to the
dashboard.

`tests/test_gateway_surface.py` enumerates the application's real routes and asserts both
properties on every one of them, with the exceptions named in a list that a fourth test
keeps from quietly growing. Verified that the guard bites: adding a route with no
dependency makes it fail, naming that route.

This is the same shape as the structural guards from VOLET 03 — a rule the project
declared and nothing enforced becomes a rule the test suite enforces.

## The lifecycle (chapter 03), stage by stage

| Stage | State |
|-------|-------|
| 1. Request Reception | FastAPI / Uvicorn |
| 2. Authentication | `require_auth`, API key → subject (ADR-010) |
| 3. Authorization | `require_permission`, RBAC roles |
| 4. Request Validation | Pydantic models on every body — no route takes an untyped `dict` |
| 5. Routing | dispatch to a function; no target service |
| 6. Response Delivery | **fixed by this phase** — see below |
| 7. Logging and Analytics | rotating log + `metrics_snapshot()` |
| 8. Monitoring | `/health`, `/ready`, `/live`, `/metrics` |
| 9. **Lifecycle Review and Retirement** | **absent**: no versioning, no deprecation |

### The finding: four routes handed the caller the inside of the machine

Stage 6 is *deliver the response*, and the chapter's quality controls include error
detection. Four routes built their 500 out of the exception text:

```python
raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche : {str(e)}")
```

Measured, with a search failing on a connection error:

```
500 {'detail': 'Erreur lors de la recherche : connexion refusée vers
     http://interne:11434 (fichier /home/user/GalSen-IA/data/knowledge.sqlite)'}
```

An internal hostname, a port and a filesystem path, returned to anyone who could make the
call fail. An exception message is not written for a client to read: it routinely carries
a path, a host, a SQL fragment or a service URL. Chapter 07 asks to protect sensitive API
data; this was the opposite.

`erreur_interne()` now logs the exception **with its traceback** under an incident id and
returns that id to the caller:

```
500 {'detail': 'Erreur lors de la recherche (incident d979057377c5)'}
```

The cause is not lost, it changes recipient. Silencing the error without giving anything
back would have made support impossible — the caller can quote the id, the operator greps
it in the log and finds the real exception.

Validation errors are untouched: a malformed request still answers 422 with the precise
reason. It is the caller's mistake and telling them exactly what it is helps. Only the
internal failure became opaque.

`tests/test_gateway_error_delivery.py` covers the leak, the incident id, its uniqueness,
the log carrying the real cause, and the 422 that must stay readable. A sixth test reads
`server.py` and fails if any route ever builds a 500 detail from an exception again —
verified to catch it on a deliberately faulty source.

## Versioning and retirement (chapters 04 and 08)

Both chapters ask for version control and for retiring obsolete APIs safely. Measured:
**no version prefix anywhere**, no negotiation header, no way to mark a route as going
away. The only available retirement was deletion, which a caller discovers as a 404 in
production.

The decision is recorded in **ADR-011**, and it is deliberately not `/v1`. A version
prefix is a *promise* — "this shape is stable, breaking changes land in `/v2`" — and this
platform is a prototype whose main capability answers 503 for lack of a provider.
Announcing stability the project cannot honour is the same failure this repository has
paid for repeatedly.

What was actually missing is narrower: a caller had no way to learn a route was going away
**before** it went. `src/api/versioning.py` adds that, using RFC 8594 rather than anything
bespoke:

| | |
|---|---|
| `Deprecation: true` | the route is in end of life |
| `Sunset: <HTTP-date>` | only when a removal date is decided — an invented date is worse than none, because it would be believed |
| `Link: <…>; rel="successor-version"` | only when there is a replacement |
| `GET /api/versions` | the version served, the deprecation list, and an explicit statement that **there is no URL versioning** |

Three properties, all tested:

- **The registry is empty.** No route is deprecated today. Registering a sample to show
  the mechanism works would fabricate a fact; the tests prove it instead.
- **Deprecated is not removed.** The route keeps working and keeps its status code. A
  deprecation that broke the route would be a disguised deletion, learned exactly as
  before — in production.
- **The announcement covers error responses too.** That is why it is a middleware and not
  a per-route dependency: a caller who only ever hits a route in error, because their
  parameters have been wrong for months, is precisely the one who needs the notice.

## Traffic controls (chapter 05)

| Control the chapter names | State |
|---------------------------|-------|
| Rate limiting | present — token bucket, per key fingerprint or per IP |
| Throttling | present — the bucket's `burst_multiplier` is the burst allowance |
| **Load balancing** | **n/a**: one process, no backend pool |
| **Circuit breaking** | **absent** |
| **Retry policies** | **absent** |

The limiter is better than the chapter requires on one point and worse on another. Better:
a 429 carries `Retry-After` and the three `X-RateLimit-*` headers, so a well-behaved
client can back off instead of guessing. It also counts against a key *fingerprint*, never
the key itself — a limiter's buckets end up in logs and metrics.

Worse: the buckets live in process memory, so **the quota actually granted is multiplied
by the number of instances**. That is not a new finding — `scaling_report()` already
records it as blocking under ADR-009 — and it stays true here.

Circuit breaking and retries are absent and were not improvised. Every outbound provider
call has a timeout (30 s for the hosted providers, configurable for the local one), so a
hanging dependency cannot block a request forever; a breaker would save paying that
timeout repeatedly, which is an optimisation, not a missing safety net. Adding one that
guessed at failure thresholds would be inventing policy.

## Monitoring (chapter 06)

Six key metrics are named. Four were already measured, one was computable but nobody
computed it, and two cannot be produced from inside this process:

| Metric | State |
|--------|-------|
| Request latency | histograms per method and route template |
| Error rate | derived in `metrics_snapshot()`, not left to consumers to disagree over |
| Authentication success rate | two counters, no subject recorded |
| Throughput | **added**: `throughput_rps` over `uptime_seconds` |
| **Availability** | **named as unavailable** |
| **Resource utilization** | **named as unavailable** |

Availability is the interesting one. A process cannot measure its own availability: an
instance that is down reports nothing, so a self-reported figure is always 100 %. That
number would be exactly the plausible answer `.claude/rules/verification.md` forbids. It
is named in an `unavailable` block, with what it would take — an external probe polling
`/live` and keeping the history. Resource utilization would need `psutil`, which is not in
the environment.

Throughput is an average since the counters were last reset, not an instantaneous rate,
and the field says so. Resetting the counters also resets the measurement window;
otherwise the rate would collapse toward zero without any change in traffic.

## Security (chapter 07)

Nothing new here — the chapter restates what VOLET 11 built and what chapters 02 and 03
above already measure. `docs/architecture/security.md` is the reference; the gateway's
share of it is: API key authentication with digests and `hmac.compare_digest`, RBAC on
every route, security headers on every response including errors, CORS closed by default,
threat detection on authentication failures, and — added by phase 3.1 — 500 responses that
no longer hand over the inside of the machine.

The one control the chapter names that the platform does not implement is **TLS
termination**. That is deliberate: TLS belongs to the deployment (reverse proxy, ingress),
and a Python process terminating its own TLS would be a worse answer than the one every
deployment already has. It is listed under exit criterion C4, which is open.

## Governance and quality (chapters 08, 09, 10)

Chapter 10 restates chapter 08 almost entirely — both are titled "API Gateway Governance"
— so they are treated as one subject.

What exists: version control of the code, audit trails, `/api/versions` for the API
inventory, `/metrics` and `/analytics` for the KPIs, ADRs for the decisions, and the
structural guards in `tests/test_gateway_surface.py` that make "enforce access controls"
a test rather than a policy nobody applies.

What does not exist, and is not simulated: there is no API Governance Board, no Operations
Team, no Compliance Team — the roles the chapters assign belong to an organisation this
project does not have. Recording a review cadence that nobody performs would be the same
fabrication as an invented sunset date. Chapter 09's optimisation loop has one real
foothold: `docs/standards/performance.md` sets the targets and `scripts/release_check.py`
checks them.

## What is still missing

- **No URL versioning**, by decision (ADR-011). Two versions of a route cannot be served
  side by side; when that is genuinely needed, the ADR is superseded, not stretched.
- **No circuit breaker, no retry policy** — timeouts bound each outbound call instead.
- **The limiter does not survive a second instance**: quotas multiply per process
  (ADR-009).
- **No availability measurement**, which needs an external probe.
- **No TLS at the application layer**, by design; it belongs to the deployment (C4).
