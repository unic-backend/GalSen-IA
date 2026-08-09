## Engines (source code)
Each engine lives in `src/` and exposes a single manager class as its entry point.
- `src/router/` → Router Engine (orchestration, agent dispatch, workflows)
- `src/agent/` → Agent Runtime (sequential and parallel agent execution)
- `src/tool/` → Tool Engine (dynamic tool loading and execution)
- `src/memory_engine/` → Memory Engine (short/long term, user, agent shared, conversation, session, workspace/project, and knowledge memories)
- `src/model_engine/` → Model Engine (multi-provider AI model management)
  - `providers/` → the provider contract and the OpenAI, Anthropic, Google and local
    implementations. Add a provider here; nothing else changes.
  - `model_registry.py` → catalogue of known models (distinct from `ModelStore`)
  - `provider_selector.py` → automatic provider and model selection
  - `capability_detector.py` → capabilities from providers, static table as fallback
- `src/knowledge_engine/` → Knowledge Engine (knowledge base and RAG)
- `src/document_intelligence_engine/` → Document Intelligence Engine (document processing)
- `src/vision_intelligence_engine/` → Vision Intelligence Engine (image understanding)
- `src/tools/` → Concrete tools: `filesystem`, `terminal`, `git`, `github`, `web_search`, `browser`, `api`, `model`, `database`, `memory`, `rag`, `embeddings`, `ocr`, `pdf`, `email`, `calendar`, `docker`, `logging`, `metrics` (all tools declared in `tools/tools.yaml` are implemented)
- `src/api/` → API Layer (RESTful API exposing platform functionality)

## Identity and authentication
`docs/architecture/identity.md` — what VOLET_16 asks, what exists, what is deliberately
absent with its trigger. Decision: ADR-010 (a key belongs to a subject).

## Architecture Decision Records (ADRs)

- ADR-001: Choose Python as the primary implementation language
- ADR-002: Choose initial technology stack
- ADR-003: Model Provider Architecture
- ADR-004: Provider Credential Handling
- ADR-005: Persistent Storage Backend (SQLite)