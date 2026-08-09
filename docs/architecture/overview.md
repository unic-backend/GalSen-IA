# GalSen IA — Architecture Overview

## Current Status
The platform runs. Fourteen engines and services are registered in `EngineRegistry`, reachable through a
REST API (`src/api/server.py`, 60 routes behind API-key authentication and RBAC) and
covered by their own test suites. Persistence exists: memory, model, knowledge and the
notification, calendar, email, cloud and file services select a SQLite store through
`GALSEN_STORAGE_BACKEND` (ADR-005); the audit and approval engines are still in-memory
only.

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
The nine agents in `agents/` each call real engines. None of them fabricates a
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

Agents that would change something outside the process (deploying, pushing,
writing documentation) report what should be done instead of doing it. Those
actions have consequences a human should own.

The `tester` agent refuses to run `test_router.py` and `test_agent_runtime.py`,
and detects nested execution through an inherited environment variable. Without
both guards it would run the orchestrator that is running it, endlessly.

## Tools
`tools/tools.yaml` declares 18 tools; five are implemented. The rest are declared
for the roadmap and fail to load with an explicit message.

| Tool | State | Safety constraint |
|------|-------|-------------------|
| `filesystem` | Implemented | Confined to the project root, including through symlinks. Writing disabled by default. |
| `terminal` | Implemented | No shell, so arguments cannot inject a command. Executable allowlist. Timeout. |
| `git` | Implemented | Read-only by default. Pushing to `main`/`master` and force pushing refused in code. |
| `github` | Implemented | Read-only. Token read from `GITHUB_TOKEN` at call time, never stored. |
| `web_search` | Implemented | Short timeout so an offline network does not stall the pipeline. |
| `model` | Implemented | Exposes the Model Engine. Generation returns a status, never fabricated text. |
| 12 others | Declared only | Loading fails with `Could not load class`. |

## Design Principles
- Start simple and grow gradually
- Prefer modular architecture (easy to change one part without breaking others)
- Optimize for low cost and maintainability
- Make the system understandable by Claude Code over many years
- Keep clear separation between documentation, configuration and code

## Architecture Decision Records (ADRs)
All important technical decisions must be recorded in:
`docs/architecture/decisions/`

Each decision will have its own file (example: `001-choose-tech-stack.md`).

## Next Architecture Steps
1. Decide how provider credentials are supplied (ADR required). The provider
   architecture is in place; keys are the only thing standing between the
   platform and working text generation on hosted models.
2. Decide on the persistent storage backend for the engines (ADR required)
3. Expose the engines through an API layer