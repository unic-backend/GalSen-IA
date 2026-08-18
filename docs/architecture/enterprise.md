# Enterprise architecture

What VOLET_25 asks of the platform as a whole, and what the platform is. Measured against
the repository on 2026-08-11, at the close of the VOLET series.

---

## About the document itself

`VOLET_25.md` is the capstone manual, and it is the most damaged file of the series:
**chapter 07 appears twice**, **chapter 10 appears twice**, and **chapter 08 comes after the
first chapter 10**. Nothing was invented to reconcile that; the chapters were read as
written, duplicates included.

## The twelve global components (chapter 02)

| Component | What plays it | State |
|-----------|---------------|-------|
| Identity Engine | `RBACManager`, ADR-010 | present — no directory, identities are asserted |
| Security Engine | RBAC, headers, threat detection | present → `security.md` |
| Memory Engine | `MemoryManager` | present → `memory.md` |
| Knowledge Engine | `KnowledgeManagerImpl` | present, **empty base** → `knowledge.md` |
| Workflow Engine | `RouterEngine` + `workflows.yaml` | present → `workflows.md` |
| Notification Engine | `NotificationManagerImpl` | present → `notifications.md` |
| Integration Engine | `ConnectorRegistry` | present → `integration.md` |
| AI Agent Orchestration | `RouterEngine` loop | present → `orchestration.md` |
| Analytics Services | `/analytics`, `/metrics` | partial → `analytics.md` |
| **Decision Engine** | — | **absent** → `decisions.md` |
| **Learning Engine** | — | **absent** → `learning.md` |
| **Enterprise Dashboard** | `/ui` | partial — one page, not a dashboard |

Nine and a half of twelve, and the two that are absent were left absent on purpose: both
are projects, and both depend on exit criterion **C1**, which is not met.

## The finding: every engine existed twice

Chapter 02's directive is one sentence — *every engine shall communicate through
standardized enterprise interfaces*. There **is** such an interface: `EngineRegistry`,
which agents reach through `AgentContext`.

`server.py` did not use it. It constructed its own `MemoryManager`,
`NotificationManagerImpl`, `KnowledgeManagerImpl` and seven more, while the registry built
a second set for the agents. Measured, on the default configuration:

```
notification   même instance : False
memory         même instance : False
knowledge      même instance : False
… ten engines, ten duplicates
```

The consequence is not theoretical:

```
un agent signale un incident  → vu par le registre (agents) : 1
l'utilisateur lit /notification/list → vu par l'API : 0
```

**An alert raised by an agent was invisible on the route the user reads**, and a memory
written through the API was invisible to every agent. The platform ran as two halves that
did not know about each other.

It went unnoticed for a precise reason: with `GALSEN_STORAGE_BACKEND=sqlite` both copies
open the same database file, so the split disappears. It only bites on the **default**
configuration, in-memory — which is what every developer and every fresh deployment runs
first.

### What it does now

`server.py` takes its engines from the shared registry. When the registry cannot build one
— it constructs lazily and a missing dependency can fail — the API keeps a copy of its own
rather than losing the route, and **says so in the log**: a duplication that is announced
can be diagnosed, which is the whole difference with the one just fixed.

`tests/test_enterprise_single_engine.py` asserts identity for all ten engines and covers
both directions end to end: an agent's alert reaching the API, and an API write reaching an
agent.

## Governance (chapters 03, 07, 08, 10)

The manual assigns work to five bodies — Executive Board, AI Governance Board, Security
Board, Compliance Board, Architecture Board. **None exists**, and the answer is the same as
it has been for every governance chapter in this series: recording a review cadence nobody
performs would be a fabrication, and this repository has spent twenty-one VOLETs removing
exactly that kind of claim.

What stands in their place, and is real: ADRs for decisions, a test suite that enforces the
rules the project declared, `docs/memory/` for continuity, and measured documents — one per
engine — that say what works, what does not, and what was deliberately not built.

## The master directive, measured

Chapter 10 lists ten commitments. Against the repository:

| Commitment | State |
|------------|-------|
| Operate independently while collaborating | now true — one engine, one instance |
| Follow enterprise governance | partial — ADRs and tests, no bodies |
| Respect Zero Trust | partial — RBAC everywhere, identities unverified (ADR-010) |
| Share knowledge securely | mechanism present, **base empty** |
| Maintain complete traceability | audit engine, metrics, workflow history — all process-memory |
| Support explainable AI | no AI to explain (C1) |
| Enable continuous learning | one feedback loop, repaired in VOLET 23 |
| Remain modular and scalable | modular yes; a second instance is still blocked (ADR-009) |
| Preserve interoperability | connectors described and checked (ADR-007) |
| Deliver measurable business value | **not yet**: nothing is deployed (C4) |

Three of the ten are blocked on two things an operator must do, not on code: configure a
model provider (C1) and deploy the platform somewhere reachable (C4). Both are ranked in
`docs/memory/pending-work.md`, and both have been there since long before this VOLET.
