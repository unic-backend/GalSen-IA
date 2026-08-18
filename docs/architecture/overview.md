# GalSen IA — Architecture Overview

## Current Status
*Measured 2026-08-16. Every number below was counted, not remembered.*

The platform runs. Fifteen engines and services are registered in `EngineRegistry`, and
**nine more subsystems** built after it (volets 47–64) are probed separately — see
*Subsystems and degradation* below. All of it is reachable through a REST API
(`src/api/server.py`, **142 routes**, authenticated by API key or JWT (ADR-029) and
authorised by RBAC) and covered
by their own test suites — **274 test files, 5 369 tests passing**, 8 skipped.
17 agents, 24 declared tools (13 of which may run unattended), 30 ADRs.
Persistence exists and now covers the audit and approval engines too: every engine
holding state selects a SQLite store through `GALSEN_STORAGE_BACKEND` (ADR-005), which
defaults to `in-memory`.

The knowledge architecture is the part that grew most (VOLETs 35 and 36). It is
described in its own section below, and its rule is one sentence: **nothing enters or
leaves without saying where it comes from, and what cannot be measured is named rather
than guessed.**

A buildless web dashboard is served at `/ui` (ADR-008): the *Conseil agricole* page —
the platform's first real feature — plus platform health, external connectors and API
keys, with no build step and nothing to install. A dependency-free Python client
(`src/client/`) covers the same routes for programmatic callers.

Not there yet: no configured model provider — generation reports `unavailable` until a
key is present in the environment. The platform also runs as a **single instance**
(ADR-009): every subsystem holding state keeps it in the process under the default
backend, and `/health` says so rather than leaving it to be discovered in production.

## High-Level Vision
GalSen IA will be a modular AI platform composed of several systems:

- **Agent System** — Intelligent agents specialized for different tasks
- **Data Platform** — Collection, storage and processing of African/Senegalese data
- **API Layer** — Public and internal APIs
- **Frontend / Interfaces** — Web and possibly mobile interfaces
- **Knowledge System** — Domain knowledge about Senegal and Africa
- **Infrastructure** — Hosting, monitoring, security and deployment

## Implemented Engines
Every engine follows the same shape: an `interfaces.py` declaring abstract contracts, a
`types.py` holding the data model, one module per concrete component, and a manager class
as the single entry point. Components are injected into the manager, so any implementation
can be replaced without touching the callers.

| Engine | Location | Entry point | Responsibility |
|--------|----------|-------------|----------------|
| Router Engine | `src/router/` | `RouterEngine` | Routes a request to agents and workflows |
| Agent Runtime | `src/agent/` | `AgentRuntime` | Runs agents sequentially or in parallel |
| Tool Engine | `src/tool/` | `ToolEngine` | Loads and executes tools declared in `tools/tools.yaml` |
| Memory Engine | `src/memory_engine/` | `MemoryManager` | Stores short-term, long-term, user and session memories |
| Model Engine | `src/model_engine/` | `ModelManagerImpl` | Selects and calls AI models across interchangeable providers |
| Knowledge Engine | `src/knowledge_engine/` | `KnowledgeManagerImpl` | Knowledge base and retrieval for RAG |
| Document Intelligence Engine | `src/document_intelligence_engine/` | `DocumentManagerImpl` | Loads, chunks, indexes, summarizes and compares documents |
| Vision Intelligence Engine | `src/vision_intelligence_engine/` | `VisionManagerImpl` | Analyses images without OCR or generation |
| Audit Engine | `src/audit_engine/` | `AuditManagerImpl` | Structured trace of what agents and engines did |
| Approval Engine | `src/approval_engine/` | `ApprovalManagerImpl` | Human decision gate for sensitive actions (ADR-006) |
| Coding Engine | `src/coding_engine/` | `CodingEngineManager` | Repository-level software engineering through OpenHands, Aider and SWE-agent (ADR-028) |
| Notification Service | `src/services/notification/` | `NotificationManagerImpl` | Sends and lists platform notifications |
| Search Service | `src/services/search/` | `SearchManagerImpl` | Unified search merging several sources by relevance |
| File Service | `src/services/file/` | `FileManagerImpl` | Uploads, lists and validates files |
| Calendar Service | `src/services/calendar/` | `CalendarManagerImpl` | Events, status and visibility |
| Email Service | `src/services/email/` | `EmailManagerImpl` | Composes and sends messages through a transport |
| Cloud Service | `src/services/cloud/` | `CloudManagerImpl` | Object storage across memory, filesystem and S3 |

## Integration Layer
The engines are independent, so something has to connect them. That is the job of
`src/integration/` and `src/agent/`, and it is the only place where an engine
learns about another one.

```
Router Engine / Agent Runtime
        │  creates one AgentContext per request
        ▼
   AgentContext ──────► EngineRegistry ──────► the 14 engines
        │                (lazy, shared)
        │  passed to every agent by AgentDispatcher
        ▼
   BaseAgent subclasses (agents/*/agent.py)
```

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `EngineRegistry` | `src/integration/engine_registry.py` | Builds each engine once, on first use, and shares it. An engine that fails to build is reported unavailable instead of raising. |
| `AgentContext` | `src/agent/context.py` | What an agent receives: the request, the results of earlier agents, and shortcuts onto every engine. |
| `BaseAgent` | `src/agent/base_agent.py` | Result shape, error containment, timing, memory tracing. Concrete agents only implement `perform`. |
| `AgentDispatcher` | `src/router/agent_dispatcher.py` | Loads an agent module and calls it, with the context when the module exposes a `BaseAgent`, or through the legacy `execute()` otherwise. |

### Rules that hold across the layer
- **One registry per platform.** The Router Engine, the Agent Runtime and the
  agents all use `get_shared_registry()`, so a request writes to one memory and
  one knowledge base, not several.
- **A missing engine is data, not a crash.** `context.use_tool()` and the other
  shortcuts return an error value. An agent keeps working with the engines it has.
- **Agents receive the original request.** Earlier results reach them through
  `context.previous_results`, so the request is not deformed at each step.
- **Text generation is honest.** `context.generate()` returns
  `status: "unavailable"` with an empty string when no model is registered.
  Agents fall back to deterministic work rather than presenting invented output.

### Shared conventions
- **One import convention: `src.<module>`.** Every import inside `src/` uses it, and the
  repository root is what must be importable. Mixing it with top-level absolute imports
  (`from storage...`) creates two copies of the same class in memory, so `LOW != LOW`.
  `src/__init__.py` must therefore stay empty of logic: adding `src/` to `sys.path` makes
  bare imports resolve, which hides the violation instead of fixing it. The rule has been
  broken twice, so `tests/test_import_convention.py` now walks every module in `src/` and
  fails on the first bare internal import.
- Eight subsystems select their store through `GALSEN_STORAGE_BACKEND` (`in-memory` by
  default, `sqlite` to persist) and `GALSEN_DATA_DIR` (ADR-005): memory, model, knowledge,
  notification, calendar, email, cloud and file. Indexing and caching remain in memory; the
  interfaces exist so a vector store can be introduced later. Audit and approval are still
  in-memory only.
- Optional third-party libraries (PyPDF2, python-docx, openpyxl, python-pptx,
  pytesseract, markdown, sentence-transformers) are imported lazily. A missing library
  degrades one loader, never the whole engine. What is *not* optional is declared in
  `requirements.txt`: Pillow and opencv are imported at module level by the vision engine.
- Each engine has a test suite named `test_<engine>.py`; the newer suites live in `tests/`.
  `test_integration.py` covers what those cannot see: that the engines are
  reachable from the agents and from the orchestrators. `tests/test_api_startup.py` boots
  the application for real — `TestClient(app)` without `with` does not run the lifespan,
  and that blind spot once let a non-starting API reach `main`.

## Identity
A key belongs to a **subject** (ADR-010): `GALSEN_API_KEYS="secret:role:subject"`. Writes
take their owner from the authenticated subject rather than the request body, reads of
another subject's data answer 404 rather than 403, and every listing filters — which is
what closes exit criterion C2 on memory, files and notifications. `GET /auth/whoami` tells
a caller who they are; `/metrics` reports the authentication success rate.

No credential store exists and none is planned before self-service signup: the platform
holds SHA-256 digests of keys supplied by the environment and no secret of its own. The
gap that follows is stated rather than implied — **nothing verifies an identity**, the
declaring party is trusted. Full picture: `docs/architecture/identity.md`.

## Scaling posture
One instance, stated at runtime rather than assumed (ADR-009). `src/api/scaling.py`
inventories every subsystem holding state, and `/health` carries the verdict:

```
GET /health → "scaling": { "instance": "...", "multi_instance_ready": false,
                           "blocking": ["api_key_revocations", ...] }
```

Five subsystems block under the default backend; `GALSEN_STORAGE_BACKEND=sqlite`
(ADR-005) clears three of them — files, notifications and engine state — because their
scope is derived from the configuration rather than declared. What no storage backend
fixes, and what therefore comes first in the repair order, is **API key revocations** (a
revoked key still opens the other instances — the security one) and **rate-limit
counters** (the quota is multiplied by the instance count). The connector and engine
registries are per-process by design and break nothing.

Nothing prevents horizontal scaling structurally — no session affinity, stores behind
interfaces, configuration from the environment. What is missing is a shared store, and
that decision belongs to the first deployment that needs one.

## Model Engine provider layer
The Model Engine reaches models through a single contract, so no code above the
provider package knows which vendor is in use. See ADR-003 for the reasoning.

```
     ModelManagerImpl
            │
   ProviderSelector ──── ModelRegistry (catalogue: what exists)
            │                    │
     ProviderRegistry ───────────┘
       (who can answer now)
            │
   ┌────────┼────────┬──────────┐
 OpenAI  Anthropic  Google    Local
                             (Ollama)
```

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `ModelProvider` | `providers/base.py` | The contract: catalogue, availability, generation |
| `ProviderRegistry` | `providers/provider_registry.py` | Which providers exist, which can answer now |
| `ModelRegistry` | `model_registry.py` | Catalogue of known models with capabilities and price |
| `CapabilityDetector` | `capability_detector.py` | Asks the provider; falls back to the static table |
| `ProviderSelector` | `provider_selector.py` | Picks provider and model from task requirements |

Three model-related concepts exist and must not be collapsed:
- **`ModelRegistry`** — the catalogue: what models exist anywhere. Readable with
  no provider configured, which is what lets the platform explain what is missing.
- **`ProviderRegistry`** — which providers can serve a request right now.
- **`ModelStore`** — models registered at runtime for use. Pre-existing, untouched.

### Provider state today
| Provider | State | Reason |
|----------|-------|--------|
| OpenAI, Anthropic, Google | Implemented | Generate once their key is in the environment (ADR-004) |
| Local (Ollama) | Fully implemented | Generates today if a server runs on `localhost:11434` |
| OpenAI-compatible | Fully implemented | Any service speaking `/v1/models` and `/v1/chat/completions`: vLLM, LM Studio, llama.cpp, LocalAI, OpenRouter, Groq, or a rented GPU server. Inactive until `GALSEN_OPENAI_COMPATIBLE_URL` is declared |

The compatible provider is what makes the trajectory *laptop → own server →
hosted* cost nothing in code: only the URL changes. Its key is optional (a local
server asks for none) and its catalogue is **discovered** through `/v1/models`
rather than declared, so it stays truthful when the operator swaps models.

### Unavailability is a status, not a failure
- `generate()` returns `status: UNAVAILABLE`, empty `text`, a machine-readable
  `reason` and an actionable `detail`.
- `generate_text()` is typed `-> str` and therefore raises
  `ProviderUnavailableError` rather than returning a substitute.
- `context.generate()` maps that to `status: "unavailable"`, so agents fall back
  to deterministic work.

Empty text with a status is the honest answer. A plausible sentence nobody
generated cannot be detected downstream, and is worse than no answer.

## Agents
The seventeen agents in `agents/` each call real engines. None of them fabricates a
result: what an agent cannot establish, it reports as a gap.

| Agent | What it actually does | Engines used |
|-------|----------------------|--------------|
| `planner` | Detects intents in the request and produces an ordered, reproducible task list | memory, knowledge, model |
| `researcher` | Searches knowledge, memory and web; reads referenced documents and images | knowledge, memory, tool, document, vision |
| `coder` | Locates target modules, reads the conventions in use, specifies the change | tool, memory, knowledge, model |
| `reviewer` | Static analysis against the project coding rules, with file and line | tool, memory, knowledge |
| `tester` | Runs the test suites through the terminal tool and reads exit codes | tool, memory |
| `security` | Scans for hardcoded secrets, dangerous calls and unprotected `.env` | tool, memory, knowledge |
| `documentation` | Compares the memory files against what exists in `src/` | document, tool, knowledge, memory |
| `deployment` | Checks repository state, required artifacts and the tester verdict | tool, memory, knowledge |
| `monitor` | Reports engine availability, log errors and pipeline health | all six |
| `organizer` | Proposes a file tidy-up; **moves nothing** without an approved request | tool, storage |
| `project_manager` | Reports task state from what agents actually returned — no estimates, no percentages | memory |
| `opportunity` | Surfaces sourced signals; `insufficient_evidence` rather than an invented analysis | knowledge, tool, memory |
| `verifier` | Confronts claims with retrieved passages; `cannot_verify` with no passage, and never rewrites the answer | knowledge |
| `senegal` | Prefers national sources and **refuses** a national subject with no national source | knowledge |
| `knowledge_architect` | Proposes a manifest entry as `DRAFT`; never applies it | knowledge |
| `data_engineer` | Describes a statistical series; **refuses** one without declared units, period and source | — |

Agents that would change something outside the process (deploying, pushing,
writing documentation) report what should be done instead of doing it. Those
actions have consequences a human should own.

The `tester` agent refuses to run `test_router.py` and `test_agent_runtime.py`,
and detects nested execution through an inherited environment variable. Without
both guards it would run the orchestrator that is running it, endlessly.

## Tools
`tools/tools.yaml` declares 22 tools, 21 of them enabled, and **every declared tool
imports** — a test asserts it, because a catalogue entry that cannot be loaded is a
capability announced without proof. `docker` is the single disabled one: from the
production container it would need the host's Docker socket, which is root on the host.

| Tool | State | Safety constraint |
|------|-------|-------------------|
| `filesystem` | Implemented | Confined to the project root, including through symlinks. Writing disabled by default. |
| `terminal` | Implemented | No shell, so arguments cannot inject a command. Executable allowlist. Timeout. |
| `git` | Implemented | Read-only by default. Pushing to `main`/`master` and force pushing refused in code. |
| `github` | Implemented | Read-only. Token read from `GITHUB_TOKEN` at call time, never stored. |
| `web_search` | Implemented | Short timeout so an offline network does not stall the pipeline. |
| `model` | Implemented | Exposes the Model Engine. Generation returns a status, never fabricated text. |
| `screen`, `gui` | Implemented | Seeing and acting are two tools: an agent can be given eyes without a hand. The hand goes through the approval gate. |
| `browser`, `api`, `pdf`, `ocr`, `rag`, … | Implemented | Everything they bring back is wrapped as **data with its origin** (`src/security/trust.py`); nine entry paths, all covered. |
| `docker` | Disabled | Would need the host's Docker socket. Re-enabling it is a written decision, not a flag. |

## Knowledge architecture (VOLETs 35 and 36)

The knowledge engine is no longer "a base and a search". It carries the rules that
decide **what may be said, from what, and with what admitted uncertainty**. Every
module below refuses rather than guesses, and each names what it cannot measure.

| Concern | Module | The rule it holds |
|---|---|---|
| Two axes | `scope.py` | Where knowledge holds (`global` / `country:sn`) and what it is about. Law, administration and languages **never** fall back to global |
| Who has authority | `source_registry.py`, `corpus/sources/senegal.yaml` | Reliability comes from a declared registry, not from the document claiming it. Denied URLs are refused **with their reason**; an authority category needs a registered domain |
| Retrieval | `scoped_retrieval.py` | A policy over the existing retriever, never a second one. Local first; a national subject with no local source gets **no answer** |
| The answer's honesty | `scoped_retrieval.scope_notice` | The answer says which sources built it — an answer about Senegal built from none says so |
| Languages | `languages.py`, `text_normalization.py` | `wo`, `ff`, `srr` are declarable. Labelling is not understanding: nine capabilities are reported per language, and what was never measured says `unknown`, not `no` |
| Factual measurement | `factual_evaluation.py` | Unsupported claims counted, cited sources checked, contradiction distinguished from absence. The evaluator never asks the model whether it was right |
| Entities | `entities.py`, `storage/sqlite_entity_store.py` | Nothing enters without a source — entities *and* relations, which carry their own provenance and validity dates. No graph database; the trigger that would justify one is written and measured |
| What is missing | `gaps.py` | A gap is a subject × scope pair **real questions** hit without an answer |
| Finding sources | `source_discovery.py` | Candidates come from the registry and nowhere else. Proposing is not deciding |
| Disagreement | `contradictions.py` | Reported, never resolved. No winner is named; the most recent source is not automatically right |
| Collection | `collection.py` | Registry + `robots.txt` applied + licence + human approval. **Nothing is downloaded here** |
| Health | `health_policy.py` | A higher source floor, a safety notice on every answer, and no dosage, diagnosis or prescription — a refusal in code, applied after generation |
| External text | `security/trust.py` | The nine entry paths announce their content as **data with its origin**. Data never becomes an instruction |
| Deferred capabilities | `deferred_triggers.py` | Vector database, graph database, queues, automated acquisition: deferred **with their triggers measured at every proactive scan**, silent until one is crossed |

Two habits run through all of it and are worth keeping when extending:

- **`unknown` is not `no`.** A measurement nobody made closes no question.
- **A report shows its gaps.** `unavailable`, `not_detected`, `blocked_on`,
  `entities_without_source` — a report that only showed what works would reassure
  wrongly, which is worse than showing nothing.

## Unattended work (VOLETs 47–67)

A routine is work the platform does with nobody watching, and everything expensive is
checked when it is **declared**, not when it fires at three in the morning. Declaring is
not enabling. A routine belongs to someone or to the platform, never to nobody.

Since VOLET 64 a routine can fire a **workflow** through the one orchestrator — the same
plan, checkpoints, execution history and `REQUEST` audit event as a person's request. A
second execution path without those guarantees would have been the parallel
implementation the directive forbids. What differs is not the machinery but what can be
decided: **an approval is never granted by the absence of someone to refuse it**. A run
that stops on `requires_approval` is reported `suspended` with its `run_id`, and a human
resumes it.

Cost follows the same reasoning. The budget used to count **turns**; a turn stopped
being a unit of cost the day it could run a whole workflow, so work is capped separately
in agents executed — counted after execution, because a workflow's cost is not known
before it has run.

`GET /orchestrator/paths` publishes both entry paths and what the unattended one cannot
decide.

## Subsystems and degradation (VOLET 65)

`EngineRegistry` isolates its fourteen engines: one that cannot be built is recorded and
never propagates. The nine subsystems built afterwards — routines, checkpoints, delivery
channels, world knowledge, routing, plugins, memory layers, source registry,
orchestration — are probed (the sandbox is measured inside the plugin probe) by `src/integration/degradation.py`, each in isolation. A
probe that raises is reported `UNAVAILABLE`, never propagated.

**Degraded is not down.** A subsystem that says what it is missing works as designed: it
does not flip the global status and does not cost readiness. Each state carries *what
still works without it*, because "degraded" alone does not say whether to act tonight or
on Monday. Probing all nine costs ~70 ms against a 50 ms supervision target, so
`/health` takes it on request (`?subsystems=true`); the full report lives on
`GET /system/degradation` and requires a key.

## Following one job (VOLET 66)

A routine turn carries a `correlation_id`, set before its guards run, and the workflow it
fires takes that identifier as its `request_id` — hence the `request_id` of its audit
events. `GET /observability/trail/{id}` assembles what each store knows about that one
job, calling the audit trace that has existed since VOLET 19 rather than writing a second
reader. An empty source and an unreadable one are never merged, and nothing is correlated
by time.

## Demonstration (VOLET 69)

`python scripts/demonstration.py` runs the real chain end to end and reports what
happened — including the steps that cannot run here, with the reason, verified at run
time. It caught a real defect on its first run: the routing was handing whole questions
to `answer_country()`, which expects a country name. Details →
`docs/demonstration/README.md`.

## Design Principles
- Start simple and grow gradually
- Prefer modular architecture (easy to change one part without breaking others)
- Optimize for low cost and maintainability
- Make the system understandable by Claude Code over many years
- Keep clear separation between documentation, configuration and code

## Coding Engine (ADR-028)
`src/coding_engine/` drives three external open-source engines behind an
interface the platform owns: **Aider** (Apache-2.0, targeted edits, subprocess),
**SWE-agent** (MIT, issue resolution, subprocess, needs Docker) and
**OpenHands** (MIT, autonomous implementation, HTTP to its agent server
container).

None of them is a dependency and none of their code is vendored — `requirements.txt`
is unchanged. Each is installed in its own virtualenv
(`scripts/install_coding_engines.sh`) after installing `aider-chat` into the
platform environment downgraded numpy and broke the Vision Engine. The platform
runs with zero, one, two or three of them available; a missing engine reports how
to fix it and the router never selects it.

Execution goes through **`src/sandbox`**, not through a second subprocess loop:
kernel limits, group cleanup, and the environment whitelist are the platform's,
with a coding-sized policy in `src/coding_engine/execution.py`. Approvals use the
Approval Engine (ADR-006) and every run is recorded under the `coding` audit
event type. A task needing approval is **refused** when the Approval Engine is
unavailable — a missing gate is not an open gate.

Guide: `docs/architecture/coding-engine.md`.

## Interoperability (ADR-023)
`src/interop/opengap.py` publishes the 17 registry agents in the OpenGAP format
(`interop/opengap/<agent>/{agent.yaml,SOUL.md}`), readable by any tool that
implements it. The **specification** is implemented, the upstream TypeScript code
is not vendored; `third_party/opengap/` carries the MIT licence and the field
reference, so the platform survives the upstream repository being deleted.

`src/code_edit/edit_blocks.py` applies model-proposed changes deterministically —
the model names the exact text to replace, the platform applies it, nothing
outside the given root is written, and a batch is all-or-nothing.

## Architecture Decision Records (ADRs)
All important technical decisions must be recorded in:
`docs/architecture/decisions/`

Each decision will have its own file (example: `001-choose-tech-stack.md`).

## Next Architecture Steps
*Both former items are decided: storage is ADR-005, sovereignty and the framed derogation
are ADR-014 and ADR-018. What follows is what is genuinely open, and none of it is a
decision — it is work waiting on someone or something outside this repository.*

1. **C1 — a local model that answers.** `ollama serve` with a context of 8 192 or more.
   It gates generation, semantic retrieval, and L4 of the language plan.
2. **Real Senegalese institutional documents.** *Updated 2026-08-14.* The gated
   acquisition path is built (ADR-021, `src/acquisition/`) and a Senegalese knowledge
   layer exists — 14 regions, 45 departments and 212 sector objects, all derived from
   acquired sources with full provenance. What is still missing is the **institutional**
   corpus: the nine `.sn` domains in the registry are refused by this environment's proxy
   (`CONNECT → 403`, measured by `scripts/activate_senegal_sources.py`), and that is an
   environment policy, not a site refusal. Six of sixteen domains are populated; history,
   culture, agriculture, health, education and law hold nothing, and say so.
3. **The `v0.1.0` tag** has never been pushed; it is the single red test in CI.
3. Expose the engines through an API layer