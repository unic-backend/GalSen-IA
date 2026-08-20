# O11 — Adapter architecture (§6)

**Built**: 2026-08-19. This is a **design on paper**. §20 forbids implementation
during the audit, and nothing here was written to `src/`.

Every constraint below arrived from an earlier volet, and the design's only real
job is to hold all of them at once. Where a constraint cannot be held, the
document says so instead of loosening it.

---

# O11.1 — The design

## The shape, and where the boundary sits

```
GalSen IA orchestrator  (authoritative — src/router/)
        │
        │  1. creates the task, the subject, the request_id, the AuditEvent
        ▼
OpenClawAdapter        (src/interop/ — GalSen IA's code, not OpenClaw's)
        │
        │  2. creates a session per task, holds the identity itself
        ▼
OpenClaw Gateway       (foreign process, one provider, no skills)
        │
        │  3. asks for a tool
        ▼
OpenClawAdapter        4. allowlist → authorize(tool_id, actor) → run → validate
        │
        ▼
GalSen IA tool         (one of four)
```

**The adapter is on both edges**, and that is the design. OpenClaw never reaches
a GalSen IA tool directly and never reaches a model directly; both directions
pass through code this repository owns.

## §6's fifteen controls, each with where it lives

| §6 requires GalSen IA to control | How | From |
|---|---|---|
| task creation | the orchestrator creates it; the adapter never originates work | O09 |
| task authorisation | `authorize(tool_id, actor)` **per call** | O03 |
| user identity | the adapter assigns the subject; an OpenClaw session ID is **never** read as one | O04 |
| permissions | role, effect and data-scope ceilings, unchanged | O03 |
| allowed tools | four: `rag`, `embeddings`, `web_search`, `metrics` | O03 |
| **allowed skills** | **none**, and `security.installPolicy` set to block as a second lock | O07 |
| resource limits | container limits — **see the blocker** | O03 |
| timeout | the adapter's own deadline; the task is cancelled on expiry | this phase |
| network policy | one egress: GalSen IA's own endpoint. **See the blocker** | O03, O06 |
| filesystem policy | no host binds — **see the blocker** | O03 |
| sandbox policy | GalSen IA's, not OpenClaw's off-by-default one | O03 |
| output validation | `src/router/output_validation.py`, already used for agent output | O08 |
| provenance | `AuditEvent` written **before** the call, `request_id` carried across | O08 |
| cancellation | per-task session; ending the session ends the work | O09 |
| error handling | structured error → self-healer → `RETRY`/`FALLBACK`/`CANCEL`/`ESCALATE`/`FAIL` | O09 |

**Twelve of fifteen are satisfied by mechanisms that already exist.** Three —
resource limits, network policy, filesystem policy — depend on a container
boundary, and that is the blocker O03 measured.

## The three rules the design adds

**1. One provider, and the adapter owns the configuration.**
OpenClaw is configured against GalSen IA's own OpenAI-compatible endpoint, so
`ModelRouter` stays authoritative and ADR-014's sovereign default is not
bypassed (O06). The configuration file is written by the adapter and is not
writable by the gateway's own process.

`UNKNOWN` that must close before implementation: **can OpenClaw be constrained
to exactly one provider, with configuration the agent cannot edit?** Recorded in
O06, unresolved. *"Configured with one provider"* is worth nothing if a skill
can add a second — and O07 already removes skills, which narrows but does not
close it.

**2. A session per task, created and destroyed by the adapter.**
Three volets required this independently: O04 for identity, O06 for memory
boundaries, O09 for recovery. It also makes OpenClaw's automatic post-restart
re-dispatch inert, since there is no surviving marked session to re-dispatch.

Its cost is `UNKNOWN` (O10) and is the single number a future benchmark must
produce first.

**3. Nothing crosses from OpenClaw's store into GalSen IA's memory except
through the existing gate.**
`live_context/memory.py` already refuses a write without permission **and** a
declared link, and refuses a consent naming somebody else (O06). OpenClaw's
SQLite is session scratch; `memory_engine` is the source of truth.

## What the adapter refuses, structurally

- **It exposes no OpenClaw skill or plugin** (O07). Not "audited ones" — none.
- **It never treats an OpenClaw identifier as a subject or a `request_id`**
  (O04, O08).
- **It never merges the two provenance ledgers** (O08).
- **It carries no fallback to a second provider** (O06).
- **It cannot widen its own allowlist**: the four tools are a table, and every
  call still passes `authorize()`, so widening the table does not bypass the
  ceiling.

---

# O11.2 — What it costs, and the alternative

## The blocker, restated because it decides the phase

§6 says the adapter *"must isolate OpenClaw from the core architecture"*, and §8
requires a real isolation layer since OpenClaw's own is off by default and
described by its authors as *"not a perfect security boundary"*.

**That layer is a container boundary around the whole gateway process**, and
`src/sandbox/policy.py`'s own `NON_GARANTI` records that the platform lacks the
namespaces and cgroups to build one — *"des privilèges que la plateforme n'a
pas"*. The `docker` tool is declared and **disabled** because the obvious
implementation hands out host root (ADR-017).

So: **three of §6's fifteen controls cannot be delivered by this platform
today.** Not "would be difficult" — cannot, with the reason measured and already
written down before this programme started.

`INFERENCE`: the adapter is implementable; **the deployment is not**, until an
operator provisions a container runtime the platform may drive, or a separate
host. An adapter shipped without those three controls would be an adapter whose
own design document lists what it does not do — which is worse than none.

## The alternative nobody had costed, now costed

O02 found that **thirteen of §5's fourteen capabilities already exist here**,
and that the one genuine asymmetry is **bidirectional conversational
channels** — WhatsApp, Telegram, Signal, Slack — against
`config/notifications/channels.yaml`'s three, all one-way and operator-facing.

**GalSen IA already has the shape for that**, and it is not the adapter.
`src/connectors/` answers exactly the two questions a channel raises, and its
own contract says why:

> *"**What class of data does this connector reach?** The isolation boundary
> derives ownership from that answer, so a caller cannot label a private message
> as public. **On whose behalf?** A connector reading one mailbox is bound to one
> subject. A connector that reaches private data without being bound to anyone
> cannot isolate anything — there is no one to isolate it for."*

Both answers are *"mandatory and checked at registration"*, in the same
vocabulary as the tool registry. `SubjectBoundConnector`, `SubjectBinding` and
`AuthorizationState` already exist (`lifecycle.py`), as does a privilege model
(`safety.py`).

**A WhatsApp connector under that contract**:

| | Adapter route | Connector route |
|---|---|---|
| New foreign process | yes — Node runtime | **no** |
| Container privileges needed | **yes — blocked** | **no** |
| Subject binding | adapter must impose it | **already mandatory** |
| Skills/licence exposure | rejected, but the surface exists | **none** |
| Provider sovereignty risk | must be configured away | **none** |
| Multi-user isolation | §9 fails on branch A, blocked on B | **per-call, as everywhere else** |
| What it delivers | agent loop we already have **+ channels** | **channels** |

`INFERENCE`, and it is O11's main conclusion: **the connector route delivers the
only thing OpenClaw uniquely offers, without any of the six costs.** It is more
work in one narrow place — a WhatsApp Business API integration is real
engineering — and it is less work everywhere else, because it needs no
container boundary, no sovereignty workaround, no session identity mapping, and
no second provenance ledger.

**This phase does not decide between them.** O12 does, and the owner does. What
O11 refuses to do is present the adapter as the natural conclusion of the audit
when the audit kept pointing elsewhere.

## What O11 hands to O12

1. **A design that holds twelve of §6's fifteen controls** using mechanisms that
   already exist.
2. **Three controls that cannot be delivered here** — resource, network and
   filesystem policy — for a measured reason predating this programme.
3. **One `UNKNOWN` that must close before any implementation**: can OpenClaw be
   pinned to a single, adapter-owned provider configuration?
4. **One number a benchmark must produce first**: the cost of a per-task session.
5. **A costed alternative** that delivers the unique capability without the six
   costs, and that fits a contract this repository already enforces.
