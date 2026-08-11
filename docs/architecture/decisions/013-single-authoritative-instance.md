# ADR-013: One Authoritative Instance, Enforced — and Why Not Redis Yet

## Status
Accepted

## Date
2026-08-11

## Context

ADR-009 established the posture: several subsystems keep their state in process
memory, so the platform runs as a **single instance**. `scaling_report()` names the two
that matter for security — API key revocations and rate-limit counters — and
`/health` publishes the verdict.

The posture was written down. Nothing enforced it. The deployment audit
(`docs/deployment/audit-2026-08-11.md`, D3) found that `docker compose up` started a
second instance by itself: `api-dev` ran alongside `api` with `restart: unless-stopped`.

The requirement driving this decision is narrow and absolute: **a revoked key must not
remain valid because another instance holds stale in-memory state.**

## Decision

### 1. Redis is not introduced

Ten questions were asked about distributed quota state. They have one answer:
**as long as there is a single instance, process memory *is* the single source of
truth.** Redis becomes necessary the moment a second instance exists — not before.

| Question | Answer in this architecture |
|---|---|
| Where are quotas stored? | Process memory, one token bucket per client. |
| Are increments atomic? | Yes — a `threading.RLock` in `InMemoryRateLimiter`. One process, so the lock is the whole story. |
| When are they reset? | Never explicitly: the bucket refills continuously at `rpm / 60` tokens per second. |
| How is a revocation represented? | A key digest in `RBACManager._revoked_digests`, checked on every authentication. |
| What happens on restart? | Counters and revocations are lost. Buckets refill — harmless. **Revocations do not survive** — see *Consequences*. |
| What if Redis is unavailable? | Redis is absent, so this failure mode does not exist. That is the point. |
| Can a revoked key stay valid elsewhere? | There is no elsewhere, and the lock below is what makes that true. |
| What is the single source of truth? | The process, plus the environment (`GALSEN_API_KEYS`) for the durable key list. |
| What breaks first with two instances? | Revocation, then quota — in that order of severity. |
| What would justify Redis? | See *The trigger* below. |

Introducing Redis now would buy nothing and cost three things: a service to secure
(Redis ships with no authentication), back up and monitor; a new failure mode with no
good answer (refuse all traffic, or fall back to memory and lose the guarantee
silently); and infrastructure that ADR-009 explicitly set aside.

### 2. The real risk is enforced instead

The risk is not "Redis is missing". It is **"a second instance can start without anyone
noticing"**. So:

**At startup the application takes an exclusive lock on the data directory.** A second
instance on the same directory refuses to start and names the one holding the place.
`src/api/instance_lock.py`, called from the API lifespan.

The lock is `flock`, and the choice matters: the kernel releases it when the process
dies, however it dies. There is no stale-lock heuristic to get wrong — and getting it
wrong in the permissive direction would mean two instances, which is the thing being
prevented. Two containers mounting the same volume contend on the same inode, which is
exactly the case to forbid.

`scripts/backup.py` asks the lock, not the file: a lock file left behind by a crash
must not forbid the restore that the crash made necessary.

**`api-dev` moved behind a Compose profile** (ADR-012) and uses its own data volume, so
a developer running both is not running two instances over one state.

### 3. Escape hatch

`GALSEN_ALLOW_MULTI_INSTANCE=true` skips the lock. It is the rollback for this decision
and it is logged as a warning at startup. An operator who sets it is choosing to lose
the revocation guarantee, and the log says so.

### The trigger that reverses this decision

Take Redis — and write the ADR that supersedes this one — when **any** of these is true:

- a second instance is actually needed (measured load, not anticipated load);
- an availability requirement makes a single process unacceptable;
- revocations must be shared across processes for a reason other than horizontal scale.

`APIRateLimiter` is already an abstract interface with an in-memory implementation
behind it. The Redis implementation is a new class, not a rewrite. That is the reason
this decision can be deferred without cost.

## Consequences

Positive:

- A second instance cannot silently create a competing authoritative state.
- `/health` reports whether the lock is held (`scaling.instance_lock`), so the guarantee
  is observable rather than assumed.
- No new service, no new failure mode, no new attack surface.

Negative, and accepted:

- The platform cannot scale horizontally. That was already true; it is now enforced.
- **Revocations still do not survive a restart.** The key returns to service when the
  process restarts, and `restart: unless-stopped` makes that automatic. This is why
  `POST /auth/keys/{fingerprint}/revoke` answers `persistent: false` and points at
  `GALSEN_API_KEYS`, which remains the only definitive gesture. Persisting the
  revocation list to the data directory is the obvious next step and is **not** done
  here; `tests/test_instance_lock.py::test_la_revocation_ne_survit_pas_au_redemarrage`
  measures the hole so it cannot be forgotten.
- `flock` is unreliable on network mounts (NFS). The same caveat already applies to
  SQLite, and `scaling_report()` carries it: both guarantees assume a local disk.
- Without `fcntl` (Windows), the lock degrades to the presence of the file: an abrupt
  stop leaves a file an operator must remove. Refusing is the safe direction, and
  `status()["enforced"]` reports which mode is in force.

## Alternatives considered

- **A PID file with a liveness check.** Cheap, and wrong in containers: each container
  has its own PID namespace, PID 1 always exists, and hostnames change on every
  recreate. Every heuristic here fails in the permissive direction.
- **Refusing to start when the lock file merely exists.** That is the Windows fallback,
  and it is not good enough as a default: it turns a crash into manual intervention.
- **Redis now, single instance later.** Rejected above — it answers a question nobody is
  asking yet, at the price of a service to secure and a failure mode with no good answer.

*Redis (BSD-3 / RSALv2 depending on version) was studied and not adopted at this stage.
No code from it is present in this repository.*
