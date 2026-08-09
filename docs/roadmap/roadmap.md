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
| Country-specific modules | absent — the authority is VOLET_01 ch. 05, not a dedicated manual |
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

### C2 — A user exists, and their data is theirs — **met for memory**

An account can be created, and two accounts cannot see each other's memories, files or
notifications.

*Check:* `tests/test_identity.py::TestCritereC2` — one subject stores a memory, another
gets 404 on it and nothing from a search that matches it.
*Today:* **met for memory**, open for files and notifications. ADR-010 gives a key a
subject; `/memory/store` takes its owner from the authenticated subject instead of the
request body, `/memory/retrieve` answers 404 rather than 403 on someone else's data, and
`/memory/search` filters. Files and notifications carry no owner yet, so the same
treatment has to reach them before C2 is fully closed.

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
single `[Unreleased]` section — which is accurate: **nothing has been released**.

---

## Cutting a release

Chapter 03 lists five requirements before any official release: core features complete,
critical defects resolved, security checks done, documentation updated, performance
targets verified. A checklist nobody runs is a document, so this one runs:

```
python scripts/release_check.py
```

It exits non-zero when something blocks. Everything a machine can decide, it decides;
everything needing judgement is **printed and never ticked automatically** — a box that
ticks itself without being checked is worse than no box.

### What it checks

| Check | Chapter 03 requirement | Blocks on |
|-------|------------------------|-----------|
| Version | documentation updated | malformed number, Dockerfile drift, major ≥ 1 on a non-stable type |
| Git tag | traceability | `v<version>` already exists |
| Working tree | reproducibility | uncommitted files |
| Secrets | security checks | any tracked `.env`, `*.sqlite`, `*.key`, `*.pem` |
| Changelog | release notes | no `[Unreleased]` section, or an empty one |
| Documentation | documentation updated | a required document missing or empty |
| Startup | critical defects | the application does not boot, or `/health` is not 200 |
| Test suite | critical defects | pytest fails |

`--sans-tests` skips the suite for a quick pass. It reports a warning, never a success:
skipping a check must not look like passing one.

### What it refuses to decide

Two of the chapter's five requirements need a person, and the script says so:

- **Core features complete** — only whoever scoped the release can say whether what was
  promised is delivered rather than started.
- **Performance targets verified** — *no performance target exists for this project yet*.
  Chapter 09 has to set them. Until it does, this requirement cannot be met, and marking
  it verified would be a lie. It is listed precisely so the gap stays visible.

### Cutting the version, once the checklist passes

1. Move `[Unreleased]` under a dated `## [x.y.z] — YYYY-MM-DD` heading, leaving a fresh
   empty `[Unreleased]` above it.
2. Bump `src/version.py` — and `__release_type__` if the type changed.
3. Commit, then tag `v<version>`.
4. Push the tag; CI runs the suite on it.

Step 2 before step 3 matters: the tag must point at the commit that declares the version,
otherwise `/health` on a deployed build reports a number that does not match its tag.


---

## Prioritising

Chapter 04 gives seven criteria (user impact, business value, technical feasibility,
security implications, performance impact, maintenance cost, strategic alignment) and four
levels (P0–P3), but not what makes something critical *here*. Without that, P0–P3 is a
relabelling of the High / Medium / Low buckets it replaces, decided by feel.

### What each level means for this project

| Level | Meaning |
|-------|---------|
| **P0 — Critical** | The platform is unusable or unsafe without it, **or** it is a decision that blocks other work. Nothing else is scheduled until these move. |
| **P1 — High** | A Phase 2 exit criterion depends on it, or it removes a risk that has already shown itself. |
| **P2 — Medium** | Real value, but no criterion waits on it. |
| **P3 — Low** | Worth doing; nothing waits on it. |

Two properties matter more than the levels themselves.

**Every entry names the criterion that decided it.** An item ranked without a stated
reason gets re-argued at every review, and the argument is won by whoever spoke last. Most
items score on two or three of the seven criteria, not all seven — pretending otherwise
produces a scoring table nobody trusts.

**A priority can carry a trigger instead of a date.** Sharing key revocations across
instances is P3 today and becomes P0 the moment a second instance runs; persisting the
audit trail is P2 and becomes P1 the day the platform is deployed. A trigger survives a
change of circumstances; a date does not.

### What the ranking produced

Two P0s, both about the same thing from opposite ends: the platform has **no user** and
**cannot generate**. Everything else is a Phase 2 criterion (P1), a real improvement
nothing waits on (P2), or genuinely deferrable (P3).

Two findings came out of ranking rather than out of the items:

- **The single largest gap was not in the backlog at all.** Making generation provable end
  to end — exit criterion C1, the difference between a test suite and a product — was
  nowhere in `pending-work.md`. It is P0 now.
- **One entry was ranked on a stale number.** The orchestration suite was recorded as
  taking "~4 minutes"; measured, it takes 97 seconds. A backlog carrying wrong figures
  ranks by fiction.

### What is deliberately not ranked

One entry — *"Create API / dataset / research templates"* — states no problem. The
chapter's own decision framework opens with *"does it solve a real problem?"*, and this
one cannot answer. It stays in the backlog **unranked and unscheduled** until someone
names the problem: deleting it would lose the intent, ranking it would pretend the intent
is understood.


---

## Strategic objectives and pillars

Chapter 05 names six pillars and five measurable goals. Restated as a list they would be
six words and five aspirations, so each pillar is answered here with what exists, the
evidence, and the one next move. Measurement itself belongs to chapter 09; this section
says what is being pursued, not how it is counted.

| Pillar | Where it stands | Evidence | Next move |
|--------|-----------------|----------|-----------|
| **Product Excellence** | one real feature, unable to answer | *Conseil agricole* built end to end, returns 503 | exit criterion C1 |
| **AI Innovation** | architecture done, capability idle | four providers behind one contract (ADR-003), none configured | same — C1 |
| **Security and Trust** | the strongest pillar | keys hashed, CORS closed, security headers, encryption at rest, revocation and rotation, four suites in CI | keep it from regressing (C6) |
| **Operational Efficiency** | partial | 1438 tests, CI, an executable release checklist | observability (C5) |
| **Global Scalability** | deliberately deferred | single instance, stated at runtime (ADR-009) | nothing, until a deployment needs it |
| **Knowledge Leadership** | **nothing** | knowledge base: **0 items, 0 indexed documents, 0 graph nodes** | see below |

### The pillar with nothing behind it

The knowledge base is empty. Not sparse — empty: `get_stats()` reports zero items, zero
indexed documents, zero graph edges, and `docs/knowledge/` does not exist.

That matters more than the other five rows put together, because the project's own vision
says *"always prioritize African data, languages and use cases when possible"*. The
Knowledge Engine, the RAG tool, the search service and the retrieval ranking are all
built, tested, and retrieving from nothing. A platform for Senegalese contexts that knows
nothing about Senegal is an engine without fuel.

This is not a defect — no code is wrong — which is exactly why no test caught it and why
it took a strategic review to surface. It is recorded as such rather than filed as a bug.

### The measurable goals, honestly

Chapter 05 lists five. Two can be pursued today, three cannot:

| Goal | Pursuable now? |
|------|----------------|
| Increase platform reliability | yes — the suite and CI already measure it |
| Reduce operational complexity | yes — the three-file-writing-paths decision is exactly this |
| Accelerate feature delivery | yes, once there is a baseline (chapter 09) |
| Improve user satisfaction | **no — there is no user** |
| Strengthen ecosystem integrations | partly — connectors exist; no one integrates with them |

Two of five rest on people who do not exist yet. Saying so is more useful than reporting
zero against them quarter after quarter, and it points at the same P0 the backlog already
carries: decide whether the platform has users.

### Review cycle

Chapter 05 asks for a regular review that adjusts on evidence. The mechanism already
exists and is not duplicated here: `docs/memory/phase-plan.md` stops the work at every
phase, `pending-work.md` carries the criterion behind every rank, and chapter 10 defines
who may change the roadmap. What this section adds is the trigger — **a pillar with no
evidence under it is the signal to re-plan**, and Knowledge Leadership is that signal
today.


---

## How something new enters the platform

Chapter 06 asks for continuous innovation that does not cost reliability, and gives a
six-step process: research, prototype, evaluation, pilot deployment, full integration,
continuous review. Adopting it wholesale would be easy and useless — this project has
already run that loop several times without naming it, and has already failed it in one
specific, repeated way.

### The failure mode is fabrication, not instability

Four experiments reached `main` behaving as if they were finished, and `completed-work.md`
records each removal:

| What it did | What it returned |
|-------------|------------------|
| Calendar tool | two invented meetings, and `status: success` on a create that created nothing |
| RAG tool | relevance scores computed as `1.0 - rank × 0.05`, while the indexer's real score was discarded |
| Face detector | always an empty list — a photo of ten people got "no faces detected" |
| Model router | `"Réponse simulée du modèle X"` returned as a model's answer |

None of these destabilised anything. Every one passed its tests — `test_calendar_tool.py`
asserted `result[0]["title"] == "Réunion d'équipe"`, so the suite *protected* the
invention. That is what makes this failure mode dangerous and why the chapter's generic
"experiment safely" needs a project-specific meaning.

### So an experiment must be able to say it is one

The rule this project needs is not "prototype in a branch". It is:

> **An unfinished capability reports its state; it never returns a plausible answer.**

The platform already implements this and it is the single most valuable thing it does:
`generate()` returns `status: UNAVAILABLE` with an empty string and an actionable reason;
`generate_text()` is typed `-> str` and therefore *raises* rather than substituting;
connectors distinguish `not_configured` from `unreachable` from `unauthorized`;
`/agri/advice` turns a non-ready status into 503 rather than a 200 with an empty answer.

Empty output with a status is detectable downstream. A plausible sentence nobody generated
is not, which is why it is worse than no answer at all.

### What entry actually looks like here

The chapter's six steps map onto mechanisms that already exist, except one:

| Step | Mechanism | State |
|------|-----------|-------|
| Research | read the VOLET, measure the repository | in use |
| Prototype | behind an existing interface — provider, connector, store, tool | in use |
| Evaluation | an ADR, with the alternatives that were rejected and why | in use — nine of them |
| Pilot deployment | — | **impossible today: nothing is deployed (C4)** |
| Full integration | registered in the registry, reachable, covered | in use |
| Continuous review | phase plan, backlog with a stated criterion, chapter 10 | in use |

Pilot deployment is the missing step, and its absence is not cosmetic: without it, "full
integration" and "pilot" are the same event, so every experiment goes straight from a test
suite to `main`. That is precisely how four fabrications got in.

### The three conditions

Before anything new becomes the default path:

1. **It sits behind an interface that already exists.** New providers, connectors, stores
   and tools all have a contract. Something that needs a new contract needs an ADR first.
2. **It reports honestly when it cannot work.** Unconfigured is a status, not a crash and
   not a fake success. This is the condition the four fabrications broke.
3. **Its test asserts the honest behaviour, not the convenient one.** A test that pins a
   fabricated value makes the fabrication permanent — that is a mistake this repository
   has made and can name.

### Where innovation would land

Chapter 06 lists seven areas. Ranked by what this platform would gain today:

- **Knowledge Management** — the largest gap: the knowledge base is empty.
- **AI** — four providers built, none configured; the capability is one key away.
- **Developer Productivity** — the release checklist and the phase protocol are recent
  wins here; the orchestration suite at 97 s is the next.
- **Automation** — one declared workflow, so the area is unexplored rather than mature.
- **Security** — the strongest pillar; innovation here means keeping it, not extending it.
- **Performance** — nothing to optimise until something is measured (chapter 09).
- **UX** — one dashboard, no user to observe using it.


---

## Global expansion

Chapter 07 asks for a strategy to reach several countries and markets while keeping one
platform: keep a global core, localise without fragmenting it, respect regional law, reuse
common modules, validate each market before expanding.

None of it is actionable yet — the platform has no user, is deployed nowhere, and its one
feature cannot answer. Writing a market-entry plan in that state would be fiction. What
this section does instead is record the two things that *are* decidable now, and one
defect the chapter exposed.

### What is already decided, and holds

Two properties the chapter asks for exist, and they were not built for expansion — they
came from other constraints, which is why they are trustworthy:

- **One global core.** Every provider, connector and store sits behind a contract
  (ADR-003, ADR-005, ADR-007). A country-specific integration enters as another
  implementation, not as a fork.
- **Configuration, not code, per deployment.** Credentials, storage backend, CORS origins,
  connector settings and the instance identity all come from the environment (ADR-004).
  Two countries are two environments, not two branches.

The consequence worth stating: **the localisation that would be expensive is the one
nobody has started** — language. `Conseil agricole` takes `fr`/`wo` as a parameter of one
feature; the interface, the API messages and the error details are French only. That is a
per-string cost across the whole platform, and it grows with every string added between
now and the day it matters.

### What the chapter cannot get yet

Market research, regulatory assessment, pilot deployment, user feedback, full rollout: all
five steps require users and a deployment. They are recorded as unaddressed rather than
answered with a plan nobody could execute. The trigger is the same C4 the rest of this
document keeps meeting.

### A defect this chapter uncovered

`docs/architecture/` carries **two contradictory numbering schemes**. Twenty-five folders
are named after subjects (`Country Expansion. Vôet 8`, `User Management Engine. V13`,
`Connectors & Partners. Volet 7`) and twenty-five `VOLET_NN.md` files carry the same
numbers with **different subjects**:

| Number | Folder claims | The file actually contains |
|--------|---------------|----------------------------|
| 7 | Connectors & Partners | Memory Engine Manual |
| 8 | Country Expansion | Workflow Engine Manual |
| 13 | User Management Engine | Notification Engine Manual |

The folder contents match the files, not the folder names — `User Management Engine. V13/`
holds the Notification Engine manual. So the **folder names are the wrong half**, and any
reference written from them points at the wrong document.

This is not theoretical: two references in this repository were written from the folder
names and were wrong. The user-model decision pointed at "VOLET_13 (User Management
Engine)" when the manual it needs is **VOLET_16, Authentication & Identity**; country
modules pointed at "VOLET_08" when the only authority on country expansion is **VOLET_01
chapter 05**. Both are corrected.

There is no dedicated country-expansion manual among the numbered files. Chapter 07 of
this VOLET and VOLET_01 chapter 05 are the whole of it, and that is enough for a platform
that has not left one country yet.


---

## Technical debt register

Chapter 08 asks to *"minimise technical debt"* and to *"replace temporary solutions with
robust implementations"*. A list of principles would not survive contact with this
repository, so this is the actual register: every debt currently carried, what it costs,
and what triggers paying it. Measured, not recalled.

| Debt | Measured | What it costs | Trigger to pay |
|------|----------|---------------|----------------|
| **Unbounded log** | `logs/application.log`: 6.7 MB, 43 638 lines, no rotation | already broke the monitor agent once, before a `tail` was added | P1 — criterion C5 |
| **No metrics fed** | the `metrics` tool works; nothing calls it from request handling | `/health` reports what is *configured*, never what is *happening* | P1 — criterion C5 |
| **Three ways to write a file** | `LocalDiskStorageConnector`, `SQLiteFileStore`, `FileSystemCloudStore` | a caller has no way to choose; every future change touches three implementations | P1 — decided, not scheduled |
| **27 test files at the repository root** | 27 `test_*.py` outside `tests/` | contradicts `.claude/rules/testing.md`; they are collected and green | P3 — cosmetic while green |
| **Slow orchestration suite** | `test_integration.py`: 97 s, three tests at 31 s | slows every full run; the tester agent runs real suites inside the pipeline | P2 |
| **JavaScript untested** | `dashboard.js`, `api-client.js`: no unit runner | three rendering defects were caught only by driving a browser | accepted by ADR-008; the trigger is the interface outgrowing one page |
| **Hand-maintained scaling inventory** | `src/api/scaling.py`, 7 entries | a new store added without an entry makes `/health` lie | accepted by ADR-009; a test catches removal, not omission |
| **Single-instance state** | revocations and rate-limit counters in process memory | a revoked key still opens another instance | P3 → **P0 the moment a second instance runs** |
| **Two numbering schemes in `docs/architecture/`** | 25 folders vs 25 `VOLET_NN.md`, contradicting on at least 3 numbers | two references in this repository were written wrong from it | unscheduled — see chapter 07 above |

### What this register says about the project

Nine debts, and the shape matters more than the count:

- **None of them is a shortcut taken to ship faster.** The usual origin of debt — "we will
  clean it up after the deadline" — is absent, because there has been no deadline and no
  ship. They come instead from *merging two branches*, from *deferring deliberately*
  (ADR-008, ADR-009), and from *growth without maintenance* (the log).
- **Three are accepted rather than owed.** The JavaScript gap, the hand-maintained
  inventory and the single-instance state are recorded in ADRs with their trigger. An
  accepted debt with a named trigger is a decision; the same debt undocumented is a trap.
- **The two most expensive are the cheapest to fix.** Log rotation and feeding the metrics
  tool are both small, and both are criterion C5.

### The debt this register cannot show

Chapter 08 also asks to *"preserve critical knowledge"* and *"invest in documentation"*.
By that measure the largest liability is not in the table: **the knowledge base is empty**
and the platform's domain — Senegalese agriculture, and whatever follows — exists nowhere
in the repository. That is not debt in the usual sense; nothing has to be undone. It is
simply an asset the project claims to have and does not.

### Rule going forward

A temporary solution enters with its replacement trigger written down, in an ADR when it
shapes the architecture and in this table otherwise. A trigger is a condition, not a date:
*"when a second instance runs"*, *"when the interface outgrows one page"*. Dates on a
one-maintainer project are wishes; conditions still mean something in a year.


---

## Metrics and KPIs

Chapter 09 lists nineteen indicators across three groups. Adopting all nineteen would
produce a dashboard of zeros, and *"metrics exist to improve decisions, not to optimise
numbers"* is the chapter's own closing line. So each one was checked against what this
platform can actually observe today.

### What is measurable now

| Indicator | Source | Value today |
|-----------|--------|-------------|
| System performance | `GET /metrics` — request count, error rate, per-route latency | live |
| Test coverage | `pytest --cov=./src` | measured on demand |
| Defect rate | fixes recorded in `CHANGELOG.md` under *Fixed* | countable |
| Feature delivery rate | commits and changelog entries per period | countable |
| Technical debt trend | the register above — nine entries, each with a trigger | 9 |
| Security posture | four security suites in CI, plus the release check for tracked secrets | green |

Six of nineteen. That is not a poor result: they cover the two questions worth asking
before there are users — *does it work* and *is it getting harder to change*.

### What is not measurable, and why

| Indicator | Blocked by |
|-----------|-----------|
| User adoption, retention, satisfaction, customer feedback, active organizations | **no user exists** |
| Platform availability, MTTR, deployment frequency, change failure rate | **nothing is deployed** (C4) |
| AI response quality | **no provider configured** — generation answers 503 |
| Regional expansion, partner integrations | no deployment, no partner |

Thirteen of nineteen are blocked by exactly three facts, and all three are already P0 or P1
in the backlog. Reporting zero against them quarter after quarter would create the
appearance of measurement; naming the blocker is what actually moves them.

### What `/metrics` reports

`GET /metrics` answers *what is happening*, where `/health` answers *what is configured*.
It feeds the `metrics` tool that already existed and that nothing had ever called:

```
{ "requests_total": 5,
  "error_rate": 0.4,
  "counters":   { "http.requests.total": 5, "http.requests.2xx": 3, "http.requests.4xx": 2 },
  "latency_ms": { "http.latency.get.health": { "count": 2, "mean": 3.1, "max": 4.8 } },
  "scope": "instance" }
```

Four decisions are worth stating because each one is a trap avoided:

- **Series are named by route template, not by URL.** `/memory/retrieve/{item_id}` is one
  series. Using the requested path would create one per identifier, so a URL scan would
  turn the measurement into the outage. A test asserts four different identifiers produce
  one series.
- **A failed measurement never fails the request.** The middleware swallows its own errors
  and logs them. Without that property, instrumenting every route would be reckless.
- **`/metrics` requires a key; `/health` does not.** Traffic volumes and error rates
  describe a deployment's usage; health describes its architecture. Read-only is enough —
  a monitoring scraper has no business being an administrator.
- **The reading does not count itself.** The middleware records after the response, so
  `/metrics` reports the traffic that preceded it. Self-counting would produce a total
  that grows every time someone looks at it.

The counters live in process memory and the response says so (`scope: "instance"`). A
restart loses them and a second instance would keep its own — the same constraint ADR-009
already exposes, stated where it can mislead rather than left to be discovered.

### What this does not cover

The other half of criterion C5 — bounding `logs/application.log`, currently 6.7 MB and
43 638 lines with no rotation — is untouched here and stays P1 in the backlog. And no
performance *target* exists yet: `/metrics` makes latency observable, but nothing declares
what an acceptable latency is. Until a target is set, the release checklist keeps refusing
to tick *"performance targets verified"*, which remains the correct answer.


---

## Governance

Chapter 10 assigns five roles: Product Leadership defines direction, Architecture
Leadership validates technical alignment, Engineering plans implementation, Stakeholders
give feedback, Governance approves major changes.

This project has **one person**. Writing those five roles as if they were staffed would be
the clearest possible example of the failure this whole document has been avoiding: a
structure that describes an organisation nobody has.

### The roles exist — as mechanisms, not people

What is interesting is that the separation the chapter wants is real here. It is enforced
by artefacts rather than by job titles, which is why it survives a single maintainer:

| Role | What plays it | Where |
|------|---------------|-------|
| Architecture Leadership | an ADR, with the rejected alternatives and why | `docs/architecture/decisions/` — nine |
| Engineering planning | the phase plan: chapters split into verifiable phases | `docs/memory/phase-plan.md` |
| Governance approval | the stop-and-confirm gate — one phase, then wait | `.claude/rules/phase-protocol.md` |
| Release approval | eight automatic checks, two refused to a human | `scripts/release_check.py` |
| Prioritisation | a rank that must name the criterion that set it | `docs/memory/pending-work.md` |
| Product Leadership, Stakeholder | the maintainer, in person | — |

The gate that matters most is the cheapest: **work stops at every phase boundary and waits
for an explicit word.** One person cannot review their own decisions in bulk after the
fact; they can review one phase at a time, before the next begins.

### What has no mechanism

Nobody reviews the roadmap on a schedule. The review is event-driven: a phase ends, and
the state is re-checked against the repository. For a one-maintainer project that is the
right trade — a calendar review is a meeting with oneself — but it has a failure mode
worth naming: **a document nobody opens does not get corrected.**

Three defects found during this VOLET were all of that kind, and none would have been
caught by a test:

- `vision.md` still claimed "no application code yet" while the platform ran 1400 tests.
- `docs/architecture/` carries two contradictory numbering schemes, and two references
  written from the wrong half were wrong.
- The scaling inventory declared files and notifications process-local after a merge had
  given them SQLite stores.

The trigger is therefore not a date but a condition: **whenever a phase touches a document,
that document is checked against the repository, not against memory.** Every section above
was written that way, and each one found something.

### When the manual and the repository disagree

They did, repeatedly, and the rule the whole VOLET applied deserves to be stated:

> **The manual sets the direction; the repository sets the facts. Where they conflict, the
> deviation is recorded with its reason — never silently resolved in either direction.**

Chapter 10 of VOLET_02 asked for queues, replicas and distributed caching; ADR-009
recorded a single-instance posture and said why. Chapter 09 here asked for nineteen KPIs;
six were adopted and thirteen were refused with their blocker named. Chapter 10 asks for
five roles; they are mapped onto mechanisms and the gap is written down.

None of those is disobedience — each is the chapter's final directive applied honestly.
Pretending otherwise would produce documents that pass review and describe nothing.

### Change control

Git preserves the history, so the chapter's *"preserve historical versions"* needs no
process. What needs one is revision without instability, and the pattern is already in use:

- **An ADR is amended, not rewritten.** ADR-008 carries *Confirmed under pressure*, ADR-009
  carries *Amended*. The original reasoning stays readable; the change is dated and
  explained. Rewriting would erase why the first decision looked right.
- **A superseded decision is marked, not deleted.** Nothing in this project has been
  superseded yet; when it is, the ADR gets a status, not a `git rm`.
- **This file changes with the repository, not ahead of it.** Every figure in it was
  measured. That is what makes it worth opening.

---

*VOLET 04 complete — ten chapters, thirteen phases.*
