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

Phase 2.2 defines what "Core Platform complete" means concretely. Until then, the current
ranking of work stays in `docs/memory/priorities.md`, and the backlog in
`docs/memory/pending-work.md`.
