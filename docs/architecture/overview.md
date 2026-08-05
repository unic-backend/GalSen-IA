# GalSen IA — Architecture Overview

## Current Status
The project is building its **core engines**. Eight engines exist in `src/` and are covered
by their own test suites. No API layer, frontend or persistent storage backend exists yet:
every engine currently ships an in-memory implementation behind an interface.

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

## Integration Layer
The engines are independent, so something has to connect them. That is the job of
`src/integration/` and `src/agent/`, and it is the only place where an engine
learns about another one.

```
Router Engine / Agent Runtime
        │  creates one AgentContext per request
        ▼
   AgentContext ──────► EngineRegistry ──────► the 6 engines
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
- Storage, indexing and caching are in-memory today; the interfaces exist so that a database
  or vector store can be introduced without rewriting the engines.
- Optional third-party libraries (PyPDF2, python-docx, openpyxl, python-pptx, Pillow,
  pytesseract, markdown) are imported lazily. A missing library degrades one loader, never
  the whole engine.
- Each engine has a test suite at the repository root named `test_<engine>.py`.
  `test_integration.py` covers what those cannot see: that the engines are
  reachable from the agents and from the orchestrators.

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
| OpenAI, Anthropic, Google | Catalogue declared, generation unavailable | Credential handling not decided yet — needs its own ADR |
| Local (Ollama) | Fully implemented | Generates today if a server runs on `localhost:11434` |

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