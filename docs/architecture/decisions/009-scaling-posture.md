# ADR-009: Scaling Posture — Single Instance, Stated Explicitly

## Status
Accepted

## Date
2026-08-06

## Context
The Architecture Manual (VOLET_02, chapter 10, *Scalability*) asks for horizontal
scaling before vertical, stateless services, load balancing, containerized
deployments, background job processing, async task queues, auto-scaling,
database indexing, read replicas, distributed caching and request queuing. Its
final directive: *"Every architectural decision should allow GalSen IA to grow
from a small deployment into a global platform without requiring a complete
redesign."*

Read literally, that chapter is a shopping list: Redis, a task queue, a
container orchestrator, replicas. Building any of it today would mean operating
infrastructure for a platform that has **no configured model provider, no user
traffic and one maintainer**. The cost is not the code — it is that every
subsequent change has to keep the queue, the cache and the replicas consistent,
paid every week, for load that does not exist.

But the chapter's directive is not a shopping list. It says *without requiring a
complete redesign*. So the question that matters is narrower and answerable
today: **what would actually break if a second instance were started right now?**

That was measured rather than assumed. Seven subsystems hold state; six of them
hold it in the process:

| Subsystem | State lives in | What a second instance does to it |
|-----------|----------------|-----------------------------------|
| API key revocations | `RBACManager`, in memory | A revoked key keeps opening the other instances |
| Rate-limit counters | `InMemoryRateLimiter` | The real quota is multiplied by the instance count |
| Uploaded files | `InMemoryFileStore` | A file exists only on the instance that received it |
| Notifications | `InMemoryNotificationStore` | A user sees only what their instance holds |
| Engine state (memory, models, knowledge) | In memory, or SQLite with ADR-005 | Divergent state unless `GALSEN_STORAGE_BACKEND=sqlite` |
| Connector registry | Rebuilt per instance | Nothing — configuration comes from the environment (ADR-007) |
| Engine registry | One per process | Nothing — working objects, not business state |

The first one was demonstrated, not reasoned about. Two manager instances, one
key revoked on the first: the second still authenticates it. An operator
responding to a compromised key would believe the incident closed while the key
still works.

## Decision
**GalSen IA is a single-instance platform today, and says so at runtime.**

Three consequences follow, and they are the whole decision:

1. **No scaling machinery is introduced now.** No Redis, no task queue, no
   replicas, no orchestrator. Load that does not exist does not justify
   infrastructure that must be maintained.

2. **The constraint is exposed, not documented.** `/health` carries a `scaling`
   section built by `src/api/scaling.py`: the instance identity, a
   `multi_instance_ready` verdict, and every subsystem with where its state
   lives and what breaks. The revoke response and `/auth/keys` state
   `scope: "instance"` in the payload. An operator reads the limit at the moment
   it could hurt them, not in a file they may never open.

3. **The order of repair is fixed in advance**, so growth is incremental rather
   than a redesign:
   1. **API key revocations** — a security gap, not a capacity one. First.
   2. **Rate-limit counters** — the quota is a protection; multiplying it
      silently removes the protection.
   3. **Files** then **notifications** — both already sit behind a store
      interface (`FileStore`, `NotificationStore`), so a shared implementation
      replaces the in-memory one without touching the managers.
   4. **Engine state** — already solved by ADR-005 for anyone who sets
      `GALSEN_STORAGE_BACKEND=sqlite`.

The trigger to act on step 1 is not a date: it is the first deployment that runs
more than one instance, and `multi_instance_ready` is the field that answers
whether that is safe.

### What already satisfies the chapter
- **Stateless request handling.** No session affinity, no server-side session:
  every request carries its API key. Nothing in the routing layer prevents a
  load balancer from distributing requests.
- **Replaceable stores.** Each store sits behind an interface. That is what
  makes steps 3 and 4 above substitutions rather than rewrites — the property
  the chapter's final directive actually asks for.
- **Database indexing.** The SQLite stores declare 15 indexes across memory,
  models and knowledge.
- **Environment-driven configuration.** Instances are configured identically
  from the environment (ADR-004, ADR-007), so a second one needs no bespoke
  setup.

### What is deliberately not done
Background job processing, async task queues, auto-scaling, read replicas and
distributed caching are recorded as unaddressed. They are not forgotten, and
they are not pretended to exist: `multi_instance_ready` returns `false` and
names the reason.

## Consequences

### Positive
- An operator cannot deploy a second instance believing it is supported: the
  platform says otherwise, in the response they are already reading.
- A revoked key can no longer create a false sense of safety — the limit is in
  the revoke response itself.
- The repair order is decided while there is time to think, not during an
  incident.
- No infrastructure is operated for traffic that does not exist.

### Negative
- The platform genuinely does not scale horizontally today. This ADR makes that
  visible; it does not fix it.
- `scaling_report()` is an inventory maintained by hand. A new in-memory store
  added without an entry makes the report incomplete — a test asserts the known
  subsystems are listed, which catches removal but not omission.
- `/health` grows a section. It is unauthenticated, and it names subsystems and
  their weaknesses. That is accepted: it describes an architecture, not a
  secret, and it names no key, path or credential.

### Neutral
- `GALSEN_INSTANCE_ID` is introduced to name an instance. Unset, the report
  falls back to `<host>:<pid>`, which is enough to tell two processes apart.

## Alternatives Considered

**Build the chapter's stack now (Redis, Celery, replicas).** Rejected: it adds
operational surface with no load to justify it, and each subsequent change would
have to keep it coherent. The chapter asks that growth not require a redesign,
not that the end state be built first.

**Say nothing and treat scaling as future work.** Rejected: this is what makes
the revoked-key gap dangerous. The failure is silent — the API returns
`revoked: true` and the key keeps working elsewhere. An undocumented constraint
is discovered in production, by the person least able to act on it.

**Make revocation persistent immediately (write it to SQLite).** Rejected *for
now*, but it is step 1 of the repair order rather than a discarded option. It
only shares state between instances if they share the database file, which
brings the SQLite-on-network-filesystem caveat the report already carries. Doing
it properly means choosing a shared store, and that decision belongs to the
first real multi-instance deployment — with its constraints known, not guessed.

## Related
- ADR-004 — credentials come from the environment, which is what makes
  instances interchangeable.
- ADR-005 — persistent storage for memory, models and knowledge.
- ADR-007 — connectors configured from the environment.
- `src/api/scaling.py` — the inventory; `tests/test_scaling.py` — its tests.

## Amended (2026-08-08)

The reconciliation with a parallel branch brought SQLite stores for the
notification, calendar, email, cloud and file services. Two entries of the
inventory above — `uploaded_files` and `notifications` — were therefore written
against a state of the code that no longer holds: they are process-local under
the default backend and **shared** under `GALSEN_STORAGE_BACKEND=sqlite`.

`state_inventory()` now derives their scope from the configuration, exactly as it
already did for engine state. The report is stricter about what it claims:

| Backend | Blocking subsystems |
|---------|--------------------|
| `in-memory` (default) | key revocations, rate-limit counters, files, notifications, engine state |
| `sqlite` | key revocations, rate-limit counters |

This is the ADR's own failure mode, caught early: an inventory maintained by hand
goes stale when the code moves under it. The consequence is recorded in the
Negative section above and is the reason the tests assert the scope *follows the
backend* rather than asserting a fixed value.

The repair order is unchanged, and steps 3 and 4 are now done: what remains
before a second instance is safe is the pair that no storage backend fixes —
revocations and rate limiting.
