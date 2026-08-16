# GalSen IA — full project report

*Measured on 2026-08-16 at commit `6d0e9a1`, branch `claude/galsen-ia-phases-ukwz7p`.
Every number in this report was counted by running something, not remembered.
Where a thing could not be measured, it says so and names what would settle it.*

---

## 0. What this is

GalSen IA is a modular AI platform: agents, memory, models, tools, workflows, a
REST API, a web interface, and a knowledge layer built for Senegal first, then
Africa, then elsewhere. It is a **prototype** in the release sense — version
`0.1.0`, never deployed, no users — and a substantial one: 473 Python modules,
101 421 lines of source, 5 369 passing tests.

The single most important thing to understand about this repository is not its
architecture. It is the failure mode it was built to resist.

### The failure mode: fabrication

Four capabilities once reached `main` behaving as if they were finished. A
calendar tool returned a meeting nobody had scheduled — and a test asserted
`result[0]["title"] == "Réunion d'équipe"`, pinning the fabrication in place. A
RAG scorer returned plausible relevance numbers computed from nothing. Face
detection reported faces. A model provider answered "Réponse simulée". All four
passed their tests, because the tests **protected the invention**.

So the rule that governs everything here: **an unfinished capability reports its
state; it never returns a plausible answer.** `UNKNOWN` is a valid answer.
`None` is not zero. "Not measured" is not "measured as absent". A green report
over an empty system reads as a green light, which is worse than a red one.

Nearly every design decision in this report is downstream of that sentence.

---

## 1. Measured state, at a glance

| Thing | Count | Measured by |
|---|---|---|
| Python modules in `src/` | **473** | `find src -name '*.py'` |
| Lines of source | **101 421** | `cat` over the same set |
| Test files | **274** | pytest collection |
| Tests passing | **5 369** (8 skipped) | `python -m pytest -q` |
| API routes | **131** | `APIRoute` instances on the live app |
| Agents | **17** | `agents/registry.yaml` |
| Declared tools | **24** (13 may run unattended) | `tools/tools.yaml` + capability registry |
| Engines in `EngineRegistry` | **14** | the registry itself |
| Subsystems probed after it | **9** (volets 47–64) | `src/integration/degradation.py` |
| ADRs | **27** | `docs/architecture/decisions/` |
| Git commits | 317, from 2026-08-05 to 2026-08-16 | `git log` |
| `ruff check src tests` | clean | run |

### Size by subsystem

| Subsystem | Files | Lines |
|---|---:|---:|
| `knowledge_engine/` | 37 | 10 706 |
| `media/` | 48 | 10 508 |
| `services/` | 45 | 7 853 |
| `tools/` | 45 | 7 243 |
| `api/` | 13 | 7 170 |
| `model_engine/` | 33 | 7 155 |
| `agent/` | 23 | 6 406 |
| `darra_j/` | 21 | 6 065 |
| `connectors/` | 22 | 4 694 |
| `storage/` | 16 | 4 104 |
| `document_intelligence_engine/` | 31 | 4 076 |
| `acquisition/` | 11 | 3 086 |
| `router/` | 16 | 3 017 |
| `memory_engine/` | 12 | 2 429 |
| `routines/` | 7 | 1 939 |
| `vision_intelligence_engine/` | 16 | 1 872 |
| everything else (19 packages) | 127 | 11 093 |

---

## 2. Architecture

Every engine follows one shape: `interfaces.py` declaring abstract contracts,
`types.py` holding the data model, one module per concrete component, and a
manager class as the single entry point. Components are injected, so any
implementation can be replaced without touching callers.

### The fourteen registered engines

| Engine | Location | Entry point | Responsibility |
|---|---|---|---|
| Router | `src/router/` | `RouterEngine` | Routes a request to agents and workflows |
| Agent runtime | `src/agent/` | `AgentRuntime` | Runs agents sequentially or in parallel |
| Tool | `src/tool/` | `ToolEngine` | Loads and runs tools declared in `tools/tools.yaml` |
| Memory | `src/memory_engine/` | `MemoryManager` | Short-term, long-term, user and session memory |
| Model | `src/model_engine/` | `ModelManagerImpl` | Selects and calls models across interchangeable providers |
| Knowledge | `src/knowledge_engine/` | `KnowledgeManagerImpl` | Knowledge base and retrieval |
| Document intelligence | `src/document_intelligence_engine/` | `DocumentManagerImpl` | Loads, chunks, indexes, summarises, compares |
| Vision intelligence | `src/vision_intelligence_engine/` | `VisionManagerImpl` | Image analysis, no OCR, no generation |
| Audit | `src/audit_engine/` | `AuditManagerImpl` | Structured trace of what ran |
| Approval | `src/approval_engine/` | `ApprovalManagerImpl` | Human decision gate (ADR-006) |
| Notification | `src/services/notification/` | `NotificationManagerImpl` | Sends and lists notifications |
| Search | `src/services/search/` | `SearchManagerImpl` | Unified search across sources |
| Storage | `src/storage/` | ADR-005 contract | One store selection rule for every engine |
| Analytics | `src/analytics/` | `build_report` | Usage reporting (ADR-020, proposed) |

### The nine later subsystems

Built after the registry (volets 47–64) and probed separately by
`src/integration/degradation.py`, which answers `AVAILABLE` / `DEGRADED` /
`UNAVAILABLE` and — this is the point — **says what still works without each
one**. Measured now: **9 AVAILABLE, 0 DEGRADED, 0 UNAVAILABLE**.

`routines` (v47) · `workflow_checkpoints` (v49) · `notification_channels` (v50)
· `source_registry` (v51) · `world_knowledge` (v52) · `knowledge_routing` (v57)
· `plugins` (v58) · `memory_layers` (v60) · `orchestration` (v64)

### The API surface — 131 routes

| Tag | Routes | Tag | Routes |
|---|---:|---|---:|
| health | 15 | approval | 5 |
| knowledge | 15 | connectors | 5 |
| routines | 11 | file | 5 |
| notification | 8 | email | 5 |
| media | 8 | memory | 4 |
| workflow | 7 | oauth | 3 |
| auth | 7 | search | 2 |
| calendar | 7 | model · agri · router · agents · documents | 1 each |
| tool | 6 | cloud (deprecated) | 6 |
| plugins | 6 | root redirect | 1 |

All behind API-key authentication and RBAC. A dependency-free Python client
(`src/client/`) covers the same routes, and a buildless web dashboard is served
at `/ui` (ADR-008) with a Media Studio at `/ui/studio.html`.

---

## 3. What actually runs, end to end

`python scripts/demonstration.py` executes the real chain and reports what
happened. Measured now:

```
subsystems               OK             9 disponibles, 0 dégradés, 0 indisponibles
knowledge_routing        OK             sujet « law », portée country:sn → couches ['senegal']
world_knowledge          OK             statut FOUND, pays GHA
routine_fires_workflow   OK             3 agents exécutés ; exécution run_2b2b963fdee5
trail                    OK             retrouvé dans routine_runs, audit_events, workflow_runs
generation               NOT_CONFIGURED aucun fournisseur de modèle configuré → 503
acquisition              NOT_CONFIGURED 23 sources inscrites, aucune activée
                                        Verdict : PARTIAL
```

Two things in that output matter more than the five `OK`s.

**The verdict is `PARTIAL`, not `SUCCESS`.** Two steps are `NOT_CONFIGURED` and
the script says so rather than skipping them. A demonstration that hides its
unconfigured steps is a sales pitch.

**Unattended work is real, and bounded.** A routine can fire a workflow through
the one orchestrator, and one job is followable end to end at
`/observability/trail/{id}`. The rule that makes that safe is written into
ADR-022: **an approval is never granted by the absence of someone to refuse
it.** No human present means no approval, not automatic approval.

---

## 4. Knowledge architecture (ADR-019, VOLETs 35–36)

Two axes on every item: **scope** (where it holds) and **subject** (what it is
about). Law, administration and languages **never** fall back to global
knowledge — a French administrative fact is not a Senegalese one, and answering
with it is worse than answering `UNKNOWN`.

- Reliability comes from `corpus/sources/senegal.yaml`, never from the document
  claiming it about itself.
- Nothing enters without a source; entities **and relations** carry their own
  provenance.
- External text is **data with an origin**, never an instruction
  (`src/security/trust.py`).
- Every report shows its own gaps.

### Senegalese knowledge, measured

| Layer | State |
|---|---|
| Administration | **14 regions, 45 departments**, 45 attached, **0 approximated** — derived from geoBoundaries, never written from model memory |
| Sector knowledge | **271 chunks, 271 with provenance (100 %)** across 16 declared domains |
| Domains populated | **6** — administration, economy, geography, languages, public institutions, transport |
| Domains empty | **10**, each carrying the reason it is empty |
| Wolof | **2 105 sentences**, CLAD orthography, `ë ñ ŋ` preserved as letters |
| Multilingual aliases | 16 concepts, 115 terms, fr/wo/en, queries at 0.1–0.5 ms |

The Wolof terms carry `wo_reviewed: false` and name their source (the project
owner, a speaker). That is a vocabulary table, not a fact table: an error there
makes a query miss, it never fabricates a claim.

### Acquisition (ADR-021)

A gated path exists end to end: registry → discovery → decision → **batch human
approval** → polite fetch → trust boundary → ten quality checks → a `DRAFT`
manifest proposal. **23 sources are registered and none is enabled**, so it can
reach nothing today. That is the rule working, not a failure — registering is
not enabling.

---

## 5. Darra J — educational intelligence (`src/darra_j/`)

20 volets, 28 phases, 21 modules, **377 tests**. Full report →
`docs/darra-j/final-report.md`.

**State, measured on the register:
`ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING`.** Official versions: 0.
Units: 0. **No Senegalese curriculum has been integrated** — none was available,
and none was written from model memory.

The central guarantee is mechanical rather than declarative:

- **No canonical record → the model is not called** (`firewall.py`). Not
  labelled, not discouraged: not called. An instrumented generator measures it.
- Resolution is by **coordinates**, never similarity; incomplete coordinates
  answer `CLARIFICATION_REQUIRED`.
- Official fields are returned **verbatim and untranslated**. The question
  travels through the alias table; the record never does.
- Publishing requires a **named decider who is not the platform**
  (`is_platform_identity`, compared word by word — "ia" is inside "Mariama").
- Learner data needs **permission *and* a declared link**. No permission exists
  for an unlinked learner, because none was created.
- `INSUFFICIENT_EVIDENCE` is **off the mastery scale**, never a low level, and a
  rate over zero cases is `NOT_MEASURABLE`, never 100 %.

Six education roles live in `src/api/rbac.py`, and `PERMISSIONS_HORS_PLATEFORME`
subtracts what belongs to someone outside the platform — publishing a curriculum
and reading a child's work — from **every** platform role, admin included.

---

## 6. Universal media & video intelligence engine (`src/media/`)

20 volets, 32 phases, 26 modules, **483 tests**, 8 `/media` routes, a Media
Studio. Full report → `docs/media/final-report.md`.

**State, computed on every call by `src/media/readiness.py`:**

```
ENGINE READY — MEDIA RUNTIME DEPENDENCIES PENDING, 1 STAGE(S) NOT IMPLEMENTED (VOICE)
READY 10 · BLOCKED 6 · ABSENT 1
```

`ABSENT` is kept distinct from `BLOCKED` because they are fixed differently: one
names something to **write**, the other something to **install**. Confusing them
sends an operator looking for a package that was never the problem. **Speech
synthesis is `ABSENT`** — nothing in this repository turns text into voice, and
the planner's `voice` slot holds the text *to be said*, not its audio.

Rules worth knowing before touching it:

- **A capability is measured by interrogating the tool**, never by checking a
  binary exists. This machine's `ffmpeg` is built `--disable-everything` and
  answers `-version` like a full one. `frame_encode` is nonetheless `AVAILABLE`,
  verified **by writing a real WebM**.
- **No model supplies a timestamp**: a `Selection` carries a quote and a reason
  and has **no time field**. Cuts land on measured word boundaries; the render is
  re-transcribed and compared afterwards, and with no re-transcription the
  verdict is `NOT_VERIFIED`.
- Reframing **repositions**; it never crops, and the cost of the crop it refuses
  is measured beside it. A language version copies the master timing exactly.
- Three QC outcomes, never two: `PASS`, `FAIL`, `NOT_CHECKED`.
  `PRODUCTION_SUCCESS` requires everything applicable passed **and** nothing
  unchecked.
- Progress is `done / total` of a counted unit; an unknown total is `None`.
- **WanGP was not vendored**: licence not inspected, no GPU. `generate()` always
  raises, because a placeholder is indistinguishable from a generation that
  worked.

### Benchmarks, measured on this machine

`Linux-6.18.5 x86_64`, 4 CPU, 15.7 GB RAM, **no GPU**, Python 3.11.15,
OpenCV 5.0.0, Pillow 12.3.0. Medians over five samples:

| Benchmark | Median |
|---|---|
| `render` (12 frames → WebM, 1 sample) | 52.28 ms |
| `intent_to_plan` | 18.91 ms |
| `scene_detection` (24 frames) | 3.05 ms |
| `queue_throughput` (200 jobs) | 1.05 ms |
| `motion_frame` | 0.67 ms |
| `edit_plan` | 0.37 ms |
| `subtitle_segmentation` (120 words) | 0.26 ms |
| `transcription`, `media_probe` | `NOT_MEASURED` — capability absent |

---

## 7. Security posture

`src/security/posture.py` measures ten dimensions and **refuses to produce an
overall score**: "a single number would hide the one gap that matters behind the
average of the ones that do not." It reports **7 gaps**, named.

| Dimension | State |
|---|---|
| execution | allow-listed commands, **no shell** |
| perception | screen reads gated, GUI actions require approval |
| exposure | tool whitelist of eight, not the catalogue of twenty-four |
| trust | enforced on MCP descriptions, retrieved knowledge, web results, media |
| identity | RBAC per key, 10 roles |
| approval | enforced, **not persistent** under the default backend |
| audit | recorded, **not persistent** under the default backend |
| sovereignty | sovereign mode, providers `local` and `openai_compatible` |
| recovery | undoable moves; **nothing survives a restart in-memory** |
| filesystem | no declared roots yet (`GALSEN_STORAGE_ROOTS`) |

The named gaps are honest ones: identities are not verified (a key proves an
attribution, not a person, ADR-010); the approval gate and the audit trail are
in memory unless `GALSEN_STORAGE_BACKEND=sqlite`; the sandbox cannot cut network
access without namespaces.

Hard rules enforced across the repository: no secrets or `.env` in git, no
hardcoded credentials, no direct push to `main`, all external input treated as
hostile until proven otherwise.

---

## 8. Persistence (ADR-005)

Every engine holding state — **audit and approval included** — selects its store
through `GALSEN_STORAGE_BACKEND` (`in-memory` by default, `sqlite` to persist)
and `GALSEN_DATA_DIR`. One rule, one place, no engine deciding for itself.

The platform runs as a **single authoritative instance** (ADR-009/013): under
the default backend every subsystem keeps state in the process, and `/health`
says so rather than leaving it to be discovered in production.

---

## 9. Tests — 5 369, and what they are for

274 test files. The largest concentrations are the ones that guard surfaces
rather than units: `test_gateway_surface.py` (264 cases) checks every route's
contract, `test_services.py` (135), `test_storage_service_stores.py` (75).

Four categories of test in this repository do work that unit tests do not:

1. **Published-number guards.** `tests/test_published_numbers.py` compares the
   numbers written in `CLAUDE.md` and `docs/architecture/overview.md` against
   what the repository actually serves. A stale number in the document an agent
   reads first is worse than no number: it gets cited, it makes decisions, and
   nothing contradicts it. This guard fired twice during the media programme and
   both times the **document** was wrong.
2. **Capability-coverage guards.** Every tool must declare its capability;
   an undeclared tool is treated as the most restrictive case. `undeclared` is
   not `harmless`.
3. **Counter-tests on tolerances.** When `torch` and `playwright` were tolerated
   as imported-but-undeclared, the counter-test was **extended** so the
   tolerance cannot silently become permanent.
4. **Interface source guards.** No page may load a remote dependency, call
   `fetch` directly, or write `innerHTML` — checked on **every** page, because a
   guarantee verified on one page stops being one the day a second appears.

### What is never done to make a test pass

Deleting or skipping it · weakening an assertion to match wrong output ·
catching an exception to hide it · mocking the thing under test · **pinning a
fabricated value**. Across the two large programmes in this repository, existing
guards fired repeatedly and were honoured every time — by fixing the code or the
document, never the test. Two existing tests were **tightened**
(`test_admin_has_all_permissions`, and the web interface source guards); none was
loosened.

---

## 10. What is blocked, and on whom

| Blocked | Depends on | Consequence |
|---|---|---|
| **Generation** (C1) | `ollama serve`, or a provider key | The platform's headline capability answers `503`. Not a fault — an unconfigured capability. |
| **Semantic retrieval** | same | Falls back to lexical retrieval, and says so |
| **9 Senegalese institutional domains** | the network proxy — `CONNECT → 403`, **measured** | History, culture, agriculture, health, education and law hold nothing. Not a site refusal. |
| **Official curriculum** | a `TIER_A` authority publishing one | Darra J stays `ARCHITECTURE READY`. Not this repository's to produce. |
| **5 media stages** | a real `ffmpeg` + `ffprobe` | One install outside the repo moves `MEDIA_ANALYSIS`, `SCENES`, `EDITING`, `FINAL_MASTER` and the inspection path to `READY`, with no code change |
| **Video generation** | a GPU **and** WanGP's licence inspected | The licence is a reading task, and it blocks more firmly than the missing GPU |
| **Speech synthesis** | nothing — **it has to be written** | The one stage no installation fixes |
| **`v0.1.0` tag** | `git push origin v0.1.0` | The single red test in CI |
| ADR-020, `/cloud/*` end of life, deployment target | a decision | Open |

---

## 11. Priorities, as ranked in `docs/memory/priorities.md`

1. **Keep the suite green.** No module is done while its tests fail — exit
   criterion C6, and the only one currently met.
2. **Decide whether the platform has users** (P0). An ADR before any code: it
   gates the workspace, collaboration and every adoption metric.
3. **Make generation provable end to end** (P0). The only real feature answers
   `503`; the task is the test that proves it works when a key is present.
4. **Put content in the knowledge base.** Several volets have now built
   discipline around content that does not exist; every governance and quality
   report describes 0 items.

Highest-value next moves that do **not** depend on a decision: install a real
`ffmpeg`/`ffprobe` (five media stages at once), start `ollama serve` (generation
and semantic retrieval), inspect WanGP's licence, write a speech-synthesis
adapter.

---

## 12. Architecture decisions — 27 ADRs

`docs/architecture/decisions/`. ADR-020 is `proposed`; the rest are accepted. ADR-024 to ADR-027 open the Universal Creative Intelligence programme; the mapping to that directive's own ADR numbering is in `docs/creative/adr-map.md`.

| # | Decision | # | Decision |
|---|---|---|---|
| 001 | Choose Python | 013 | Single authoritative instance |
| 002 | Choose technology stack | 014 | Model sovereignty |
| 003 | Model provider architecture | 015 | Embeddings and semantic retrieval |
| 004 | Provider credential handling | 016 | One-file storage design |
| 005 | Persistent storage backend | 017 | Computer agent is tools, not a new architecture |
| 006 | Human approval gate | 018 | Sovereign by default, with a scoped derogation |
| 007 | External connector layer | 019 | One knowledge base, two axes |
| 008 | Frontend approach | 020 | Analytics retention *(proposed)* |
| 009 | Scaling posture | 021 | Autonomous knowledge acquisition |
| 010 | Identity model | 022 | Unattended work |
| 011 | API versioning and deprecation | 024 | Creative provider abstraction |
| 012 | TLS termination | 025 | Reference entity and consent |
| | | 026 | Identity verification declares what it cannot measure |
| | | 027 | Original performance and language knowledge |

---

## 13. Repository map

```
src/
  api/            REST server, RBAC, rate limiting, security headers, versioning
  agent/          Agent runtime + self-healing harness + guarded editor
  router/         Routing, workflows, checkpoints (RunStatus)
  model_engine/   Providers, selection, capability detection
  memory_engine/  Short-term, long-term, user, session
  knowledge_engine/  Knowledge base, retrieval, two-axis routing
  document_intelligence_engine/ · vision_intelligence_engine/ · multimodal/
  acquisition/    Gated knowledge acquisition (ADR-021)
  darra_j/        Educational intelligence
  media/          Universal media & video intelligence engine
  services/       Notification, search, email, calendar, file, Senegal, Wolof
  security/       Trust boundary, isolation, redaction, posture, checkpoints
  storage/        ADR-005 store selection, reversible operations
  tool/ · tools/  Tool engine, capabilities, authorization + 24 tool implementations
  connectors/ · plugins/ · mcp/ · routines/ · proactive/ · observability/
  client/         Dependency-free Python SDK
  web/            Buildless dashboard + Media Studio (ADR-008)
agents/           17 agent definitions + registry.yaml
tools/tools.yaml  Tool registry with declared capabilities
corpus/           Language aliases, source registry
docs/
  architecture/   Overview + 27 ADRs + assessments
  memory/         Session state, priorities, objectives, backlog, completed work
  darra-j/ · media/   Programme phase plans and final reports
  roadmap/ · standards/ · changelog/ · tasks/
tests/            274 files, 5 369 tests
.claude/rules/    The working discipline: phases, verification, memory, security
```

---

## 14. The discipline, in one page

These are not style preferences. Each one exists because its absence cost
something in this repository.

- **Measure, do not remember.** Every number in a document is checked against
  the repository by a test. Stale numbers get cited and make decisions.
- **Run it, do not read it.** Most defects found in the last two programmes were
  found by executing something — replaying an import, encoding frames, running
  the demonstration, comparing a report's claim against its own code.
- **An unfinished capability reports its state.** Never a plausible answer.
- **`UNKNOWN` is an answer.** Refusing to answer beats the least-bad fragment.
- **Structural refusal beats convention.** No delete method exists on a project
  (not guarded — absent). A `Selection` has no time field. A guarded operation
  eventually gets called with the right argument; an absent one cannot.
- **Reuse before rebuild.** A second vocabulary for one idea drifts, and this
  repository has paid for that four times.
- **A refusal names its reason.** A silent refusal sends the caller looking in
  the wrong place.
- **One phase at a time, verified before the next.** Long autonomous runs that
  end on a timeout leave nothing behind.
- **Never weaken a test to make it pass.** A failing test is information;
  removing it destroys the information and keeps the bug.

---

*Generated from the repository state on 2026-08-16. To regenerate the live
figures: `python -m pytest -q`, `python scripts/demonstration.py`, and the
`readiness()` functions in `src/media/readiness.py` and
`src/darra_j/readiness.py`.*
