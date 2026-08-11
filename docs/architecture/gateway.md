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
SecurityHeadersMiddleware ─┐  (ajouté en premier, exécuté en dernier)
RequestMetricsMiddleware  ─┤  Starlette exécute les intergiciels
CORSMiddleware            ─┘  dans l'ordre inverse de leur ajout
   → rate_limit_dependency
   → require_auth / require_permission
   → la fonction de route
```

The ordering is deliberate and load-bearing: `RequestMetricsMiddleware` is added *after*
`SecurityHeadersMiddleware` so that it wraps it and observes the status code actually
returned. A metrics layer that measures a response nobody receives is worse than no
metrics.

One deviation from the manual's flow: **rate limiting runs before authentication**. That
is the right order — an unauthenticated flood must be cheap to reject, and making the
limiter wait for authentication would mean every abusive request pays for a key lookup
first.

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

## What comes next in this VOLET

Chapters 04, 05, 06, 08, 09 and 10 are not covered by this phase. What is already known
to be missing, and will be measured rather than assumed:

- **No API versioning at all**: no `/v1` prefix, no version negotiation. Chapters 04 and
  08 both ask for version control and for retiring obsolete APIs safely; there is
  currently no way to deprecate a route except deleting it.
- **Traffic controls beyond rate limiting**: no throttling tier, no circuit breaker, no
  retry policy, no load balancing — the last two being meaningless without a backend.
- **Chapter 10 restates chapter 08** almost entirely (both are titled "API Gateway
  Governance"); it will be treated as one subject, not two.
