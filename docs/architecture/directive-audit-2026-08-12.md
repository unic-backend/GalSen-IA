# PHASE 0 — Audit of the Master Directive Against the Repository

The directive of 2026-08-12 opens with its own Principle 1 (*understand before
modifying*), Principle 2 (*architecture before implementation*) and PHASE 0
(*full system analysis*). This document is that analysis, and nothing was
written or changed before it.

**Method:** every verdict below is measured — a file listed, a symbol found, a
command run. Where the directive names something this repository already does,
it says so and names the file; where it names something absent, it says absent.

**Measured baseline, 2026-08-12:**

```
src/          305 fichiers Python, 30 paquets
agents/       13 agents déclarés
tests/        155 fichiers, 2 689 tests passent
docs/…/decisions/  20 ADR
base de connaissances : 0 élément
modèle sélectionnable : aucun  (critère C1 ouvert)
```

---

## 1. The headline, and it has not changed

The directive describes a cognitive architecture in fourteen layers. **Twelve of
them exist.** What does not exist is a model that answers:

```
$ python scripts/proactive_scan.py
[blocking] Aucun modèle ne peut répondre : les capacités de génération sont hors service.
```

Every layer below the orchestrator is built, tested and running. The layers
above it produce a `503`. `ollama serve` remains the single highest-value action
available, and no amount of architecture replaces it.

---

## 2. Section-by-section verdict

| § | Directive asks | State | Evidence |
|---|---|---|---|
| 3 | Layered cognitive architecture | **present** | `src/router/`, `src/agent/`, `src/knowledge_engine/`, `src/tool/`, `src/memory_engine/` |
| 4 | Intelligence orchestrator | **present** | `RouterEngine` + `ExecutionPlanner` + `AgentDispatcher`; workflows in `workflows/workflows.yaml` |
| 5 | Intent engine | **partial** | `PlannerAgent` detects intents and selects agents; no explicit risk/freshness/precision axes |
| 6 | Task planning engine | **present** | decomposition, assignment, dependencies (`depends_on`), decision trace (VOLET 29) |
| 7 | Multi-agent intelligence | **partial** | 13 agents; see §7 discussion below — this is where I disagree with the directive |
| 8 | Structured agent communication | **present** | `AgentContext`, `Blackboard`, `output_validation`, bounded delegation |
| 9 | Knowledge architecture, separated domains | **partial** | scope/subject axes landed today (ADR-019); user/project/temporary separation absent |
| 10 | Senegal knowledge graph | **absent** | `knowledge_graph.py` exists but holds no entity typology (PERSON, LAW, HERITAGE SITE…) |
| 11 | Knowledge acquisition pipeline | **partial** | ingestion, chunking, provenance, quality scoring exist; discovery, claim extraction, cross-validation absent |
| 12 | Source reliability engine | **partial** | twelve-level `SourceCategory` used by `retrieve_reliable()`; no corroboration, bias or primary/secondary axis |
| 13 | Contradiction engine | **absent** | measured: no module detects conflicting claims |
| 14 | Research engine | **absent** as a pipeline | `ResearcherAgent` + `web_search` exist; no strategy → triage → claim → cross-validation flow |
| 15 | Hybrid retrieval | **partial** | lexical + semantic + metadata filtering (ADR-015); **no reranking**, no query expansion, no multi-query |
| 16 | Memory architecture | **partial** | six memory types (`SHORT_TERM`, `LONG_TERM`, `KNOWLEDGE`, `AGENT_SHARED`, `SESSION`, `WORKSPACE`), retention and privacy present; the episodic/semantic/procedural taxonomy is not the one implemented |
| 17 | Tool system with permissions, logging, sandbox | **present** | 21 tools, RBAC, audit, timeouts, `src/sandbox/` with escape tests |
| 18 | Software engineering intelligence | **present** | repo map, import graph, symbol index, guarded edit loop, review/security/QA agents |
| 19 | Autonomous coding environment | **present, gated** | `GuardedEditor` + `src/sandbox/`; every write needs an approved decision (ADR-006) |
| 20 | Model routing | **present** | cost/task policy in configuration, SamP/ToP families (VOLET 30) |
| 21 | Multimodal | **partial** | image, PDF, OCR, audio interfaces; transcription never verified (no weights reachable here) |
| 22 | Multilingual, local languages first-class | **absent — and pointedly so** | `Language` holds `fr, en, es, de, ar, sw, ha, yo, zu`. **No Wolof, no Pulaar, no Serer.** A Senegalese platform cannot currently label a Wolof document as Wolof |
| 23 | Safety layers (medicine, law, finance) | **partial** | health floor is VOLET 35 ch. 10, written not built; approval gate covers irreversible actions |
| 24 | Observability | **present** | audit engine, `/metrics`, `/trace/{request_id}`, per-agent durations, cost per route |
| 25 | Evaluation system | **partial** | retrieval evaluation with a measured baseline (0.40 lexical); no factual-accuracy or citation-validity suite |
| 26 | Self-critique without self-deception | **partial** | `reviewer` and `security` agents are independent of `coder`; no evidence-check stage |
| 27 | Continuous learning, controlled | **present** | consented capture, working-style derivation, improvement measured or refused (VOLET 34 ch. 12) |
| 28 | Human-in-the-loop | **present** | ADR-006, persistent, applied to code writes, GUI gestures, file moves, training export |
| 29 | Security architecture | **present** | RBAC, ownership, encryption, sandbox, secrets by environment, audit, rate limiting, `/security/posture` |
| 30 | Prompt-injection resistance | **partial** | MCP tool-poisoning defence exists (VOLET 34 ch. 09); no general separation of external data from instructions across all tool outputs |
| 31 | Data architecture (relational, vector, object, streams) | **deliberately not built** | ADR-005, ADR-009, ADR-013 — the triggers are written and unmet. See §3 below |
| 32 | API as a platform | **present** | FastAPI, versioned deprecation (ADR-011), conversations/agents/tools/knowledge/memory/security routes |
| 33 | Product architecture on a shared core | **absent** | one API, no product surfaces |
| 34 | Project execution model | **partial** | plan, tasks, agents, artifacts and status exist per request; nothing persists a long-running project |
| 35 | Failure engineering | **present** | retries, graceful degradation, every engine reports unavailability rather than faking |
| 36 | Cost intelligence | **present** | cost per route, model selection by cost, token economy rules |
| 37–39 | Workflow, folders, ADRs | **present** | this document is itself the audit step; 20 ADRs |
| 40–42 | Knowledge / research / software standards | **present and enforced** | provenance required at ingestion, `verification.md`, "no success claim without a run" |

**Count: 12 present, 14 partial, 6 absent, 1 deliberately deferred.**

---

## 3. Where I disagree with the directive, and why

The directive asks for challenge rather than compliance. Three points.

### 3.1 Twenty agents contradicts the directive's own Principle 3

§7 lists twenty agents. §Principle 3 says *"a system with 100 agents is not
inherently intelligent — prefer fewer, well-designed, high-capability
components"*. Both cannot be followed.

Measured: this repository has thirteen agents, and three were added yesterday
*because a brief asked for them*. Of the twenty listed, seven would be genuinely
new decisions and the rest would be renaming:

| Worth adding | Why it is a distinct decision |
|---|---|
| **Fact Verification Agent** | Verifying a claim against sources is a different job from producing it — §26 requires the reviewer to be independent |
| **Senegal Intelligence Agent** | It applies the national-source rule (ADR-019) and knows when to refuse rather than answer globally |
| **Knowledge Architect Agent** | Decides scope, subject and source category at ingestion — today a human writes them in a manifest |
| **Data Engineer Agent** | Structured data is a different pipeline from documents |

| Not worth adding | Why |
|---|---|
| Frontend / Backend / Database Engineer | `coder` + repo map + guarded loop already do this; three names for one capability |
| Software Architect + Product Architect | `planner` decomposes; a second planner competes with the first |
| Global Knowledge Agent | That is retrieval, not an agent |
| Document Intelligence, Creative, Scientific Research | Two are tools (`pdf`, `ocr`, `web_search`); "creative" has no decision to make that `coder` or `researcher` does not |

**Proposal: four new agents, not eleven.** Each one earns its place by owning a
decision no existing agent owns.

### 3.2 §31's data architecture would be services to operate for nothing

Vector database, object storage, event streams, relational database. The
triggers are already written: ~100 000 vectors (there are 0), a second instance
(ADR-009 allows one), a second deployment. Building them now adds operational
surface with no user. **Deferred, with the trigger restated, not refused.**

### 3.3 The missing language layer is more urgent than most of §22

`Language` has nine values and none of them is spoken in Senegal as a first
language. Before multilingual "intelligence", the platform needs to be able to
*say* a document is in Wolof. That is a small change with a large consequence,
and it belongs at the front of the queue rather than in a later phase.

---

## 4. How this folds into the plan

Nothing in the directive invalidates VOLET 35; most of §9–15 **is** VOLET 35.

| Directive | Where it lands |
|---|---|
| §9, §11, §12, §15 partial | VOLET 35 ch. 03–05 (source registry, scope-aware retrieval, answer says its scope) |
| §11 discovery, §13 contradiction, §14 research | VOLET 35 ch. 06–09 |
| §23 safety | VOLET 35 ch. 10 |
| §10 Senegal knowledge graph | **new** — VOLET 36 |
| §22 languages | **new** — first item of VOLET 36, and small |
| §5 intent axes, §25 evaluation, §26 evidence check, §30 injection defence | **new** — VOLET 36 |
| §7 four justified agents | **new** — VOLET 36 |
| §31, §33, §34 | deferred with written triggers |

**VOLET 35 does not change.** VOLET 36 will carry what the directive adds, and
it will be planned the same way: chapters, phases, one turn at a time, each
verified before the next.

---

## 5. The one thing this audit cannot do

It cannot make the platform intelligent. Every layer described above is
machinery for handling knowledge, tools, agents and verification — and all of it
sits idle until a model answers. The directive's own §45 PHASE 1 is
"intelligence foundation"; the foundation is built and unpowered.

`ollama serve`, one command, closes it.
