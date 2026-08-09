# GalSen IA — Roadmap

The four macro-phases come from `docs/architecture/VOLET_04.md` chapter 02. This file
says where the platform actually stands against them, item by item, checked against the
repository rather than recalled.

Legend: **done** · **partial** — exists but does not yet deliver the item ·
**absent** — nothing built.

---

## Phase 1 — Foundation · complete

| Item | State | Evidence |
|------|-------|----------|
| Establish core architecture | done | 14 engines and services behind `EngineRegistry`, 9 ADRs |
| Build authentication | done | API keys hashed, 4 RBAC roles, permissions, revocation and hot rotation |
| Implement AI Orchestrator | done | `RouterEngine`, `AgentRuntime`, `AgentDispatcher`, 9 agents |
| Create Knowledge and Memory engines | done | `src/knowledge_engine/`, `src/memory_engine/`, SQLite-backed (ADR-005) |
| Deliver stable infrastructure | partial | `Dockerfile`, `docker-compose.yml` and CI exist; **nothing is deployed anywhere** |

Infrastructure is the honest asterisk on this phase: the artifacts to run the platform
exist and are tested, but no environment runs it. Nobody has ever reached this API over a
network.

## Phase 2 — Core Platform · current, roughly one third

| Item | State | Evidence |
|------|-------|----------|
| Develop user workspace | absent | **There is no user.** API keys map to roles, not to people — no account, no identity, no per-user data. `/ui` is an operator dashboard, not a workspace |
| Add workflow automation | partial | `workflows/workflows.yaml` declares exactly **one** workflow, `standard`. The loader and the planner exist; automation as a capability does not |
| Expand AI capabilities | partial | Four providers implemented, **zero configured** — generation answers 503 until a key is in the environment |
| Improve administration tools | done | `/ui`, `/auth/keys`, `/connectors`, `/health` `/ready` `/live`, 60 routes |
| Strengthen security and monitoring | partial | Security done (VOLET 02 ch. 08: hashed keys, closed CORS, security headers, encryption at rest). Monitoring is three probes and a `monitor` agent — no metrics, no log rotation |

**The blocking item is the missing user model.** A workspace, per-user data, collaboration
and adoption metrics all rest on a notion of person that does not exist. Every other Phase 2
item can advance around it; that one cannot be worked around.

## Phase 3 — Ecosystem · partly done, out of order

| Item | State | Evidence |
|------|-------|----------|
| Integrate third-party services | done | Connector layer (ADR-007): SMTP, local disk, S3 |
| Support multiple AI providers | done | Provider contract (ADR-003), four providers, automatic selection |
| Expand APIs | done | 60 routes across 21 areas |
| Improve collaboration features | absent | requires the user model |
| Enable advanced analytics | absent | — |

Three of five Phase 3 items are finished while Phase 2 is a third done. The chapter's own
principle is *"Complete one phase before expanding"*, so this is a deviation and is
recorded as one — not smoothed over.

It is defensible, and the reason matters: the connector layer and the provider abstraction
are **architecture Phase 2 needs anyway**. Retrofitting either into a platform that had
grown around a single hard-coded provider is the redesign the roadmap exists to avoid.
What is *not* defensible is treating those three ticks as progress toward Phase 3 —
collaboration and analytics both wait on the same missing user model as Phase 2.

## Phase 4 — Global Expansion · absent

| Item | State |
|------|-------|
| Multi-language support | absent — *Conseil agricole* accepts `fr`/`wo`, which is one feature's parameter, not platform internationalisation. The interface is French only |
| Multi-region deployment | absent — single instance by design today (ADR-009) |
| Country-specific modules | absent — see VOLET_08 |
| Enterprise capabilities | absent |
| Large-scale performance optimization | absent — no load has ever been measured |

---

## Where this leaves the roadmap

The platform is **in Phase 2**, with Phase 1 complete except for a deployment that has
never happened, and with three Phase 3 items already banked as architecture.

Two facts decide what comes next, and both are named above rather than left implicit:

1. **No model provider is configured**, so the platform's only real feature cannot
   answer. This is one environment variable away, not one project away.
2. **No user exists**, so half of Phase 2 and half of Phase 3 have nothing to attach to.

The current ranking of work stays in `docs/memory/priorities.md`, and the backlog in
`docs/memory/pending-work.md`.

---

## Exit criteria for Phase 2 — Core Platform

The chapter asks to *"validate each milestone"* and to *"complete one phase before
expanding"*. Neither is possible while "Core Platform complete" is a feeling. Six
conditions define it. Each one is written so that someone other than its author can check
it and get a yes or a no — a command, a route, or a test. An item that cannot be checked
is not a criterion, it is an intention.

### C1 — The platform answers a real question

`POST /agri/advice` returns **200** with a non-empty `answer` and a `model_used` naming a
real model, against at least one configured provider.

*Check:* a test that runs when a provider key is in the environment and skips otherwise —
so CI stays green without secrets while the criterion stays honest.
*Today:* 503. Four providers implemented, none configured. This is one environment
variable away, not one project away.

### C2 — A user exists, and their data is theirs

An account can be created, and two accounts cannot see each other's memories, files or
notifications.

*Check:* a test where user A stores a memory and user B lists memories without seeing it.
*Today:* impossible to write. API keys map to roles, not to people. Needs an ADR before
any code (VOLET_13).

### C3 — Automation is demonstrated, not merely loadable

`workflows/workflows.yaml` declares **at least two** workflows, and a test executes one end
to end producing a result that differs from `standard`.

*Check:* the test.
*Today:* exactly one workflow, named `standard`. A loader and a planner exist; that proves
the mechanism, not the capability.

### C4 — The platform has been reached over a network

`/health` answers `status: healthy` from a machine that did not build it, at a documented
address.

*Check:* `curl https://<address>/health` from anywhere else.
*Today:* never done. This is Phase 1's asterisk, and it stays open into Phase 2 because
nothing else on this list can be validated in production without it.

### C5 — Health is answerable without reading logs

A route reports request count, error rate and latency, and `logs/application.log` is
bounded.

*Check:* the route returns non-zero counters after traffic; the log file stops growing
without limit.
*Today:* three probes (`/health`, `/ready`, `/live`) answer *what is configured*, not
*what is happening*. The `metrics` tool exists (`increment`, `set_gauge`,
`record_histogram`, `get_metrics`) and **nothing feeds it** from request handling. The log
file is 6.5 MB with no rotation.

### C6 — The suite stays the gate

CI green on `main`, and the security suites — RBAC, security headers, key rotation,
encryption at rest — all passing.

*Check:* the CI run on the merge commit.
*Today:* met. It is listed so it cannot regress silently while the other five are chased.

### Deliberately not required to exit Phase 2

Naming these matters as much as the criteria: without it, the phase never ends.

| Excluded | Where it belongs |
|----------|------------------|
| Multi-instance readiness | deferred by ADR-009, triggered by a real deployment need |
| Collaboration, advanced analytics | Phase 3 — and both wait on C2 anyway |
| Internationalisation, multi-region | Phase 4 |
| Generation proven on all three hosted vendors | one provider satisfies C1 |

### Where the phase actually stands

Met: **C6**. Open: **C1, C2, C3, C4, C5**.

C2 is the one with a decision in front of it rather than work: everything else is
buildable today, while a user model needs an ADR first. C1 and C4 are the cheapest, and
between them they turn the platform from a test suite into something a person can use.


---

## Versioning and release types

Chapter 03 asks for semantic versioning, release notes, compatibility information and
archived releases. Two things stood in the way, and both are settled here.

### The version had two values

`src/api/server.py` declared `0.1.0`; the Dockerfile labelled the image `0.2.0`. A version
that depends on where you read it cannot answer *what is running*, which is the only
question a version exists to answer.

`src/version.py` is now the single source. The application imports it. The Dockerfile
cannot import Python, so it redeclares the value as `ARG GALSEN_VERSION` — and
`tests/test_version.py` fails if the two drift apart, along with any attempt to hard-code
a version back into `FastAPI(...)`.

### The release type is *prototype*

Of the five types the chapter defines — prototype, alpha, beta, stable, LTS — this
platform is a **prototype**, and `__release_type__` says so.

Chapter 03 requires, before any official release: core features complete, critical defects
resolved, security checks done, documentation updated, performance targets verified. Two
of those five are met (security, documentation). The platform has never been deployed, has
no user, its one real feature answers 503, and no performance target has ever been
measured. Calling that an alpha would be a promise nothing keeps.

The series stays at `0.x` while the type is prototype, alpha or beta — a test enforces it.
In `0.x`, semantic versioning promises nothing about compatibility, which is the honest
signal to send while the exit criteria above are open.

### What moves the type forward

Each step is an exit criterion from Phase 2, so the release type and the roadmap advance
together instead of drifting:

| Type | Requires | Missing today |
|------|----------|---------------|
| **prototype** *(current)* | it builds, it is tested | — |
| **alpha** | C1 (generation answers) + C4 (reachable over a network) | both |
| **beta** | C2 (users), C3 (automation), C5 (observability) | all three |
| **stable — 1.0.0** | all six criteria, plus a deployment with real users | — |
| **LTS** | a stable release someone depends on | — |

`1.0.0` is therefore not a date. It is the moment the six criteria hold, and it commits
the project to backward compatibility from that point on.

### Release notes

`docs/changelog/CHANGELOG.md` is the release log. Until the first release it carries a
single `[Unreleased]` section — which is accurate: **nothing has been released**. Cutting
a version means moving that section under a dated heading and tagging the commit, and that
procedure is phase 3.2's subject.
