# GalSen IA — Roadmap

## Phase 0 — Foundation (Current)
**Status:** In progress  
**Goal:** Build a solid, long-term project structure that Claude Code can understand for years.

### Tasks
- [x] Create CLAUDE.md
- [x] Create permanent memory system
- [x] Create complete folder structure
- [ ] Finish all core documentation files
- [x] Create first Architecture Decision Records (ADRs)
- [x] Choose initial technology stack

## Phase 1 — Core Platform
**Status:** In progress  
**Goal:** Build the first working version of the AI platform focused on Senegal.

### Engines
- [x] Router Engine
- [x] Agent Runtime
- [x] Tool Engine
- [x] Memory Engine
- [x] Model Engine
- [x] Knowledge Engine
- [x] Document Intelligence Engine
- [x] Vision Intelligence Engine

### Integration
- [x] Engine registry and agent context
- [x] Nine agents calling real engines
- [x] filesystem, terminal, git and github tool connectors
- [x] Router Engine and Agent Runtime sharing one context per request

### Model Engine
- [x] Provider contract making providers interchangeable (ADR-003)
- [x] Provider registry and model catalogue
- [x] Capability detection and automatic provider selection
- [x] Local Ollama provider generating for real
- [ ] Credential handling for hosted providers (ADR required)

### Remaining
- [ ] Choose and implement a persistent storage backend (every engine is in-memory today)
- [ ] Expose the platform through an API layer
- [ ] Build the first useful AI features for Senegalese users/businesses
- [ ] Set up basic infrastructure

## Phase 2 — Expansion (Africa)
**Status:** Future  
**Goal:** Expand the platform to other African countries.

## Phase 3 — Global
**Status:** Future  
**Goal:** Make GalSen IA competitive internationally while keeping African roots.

## Notes
This roadmap will be updated regularly.  
Always check `docs/memory/priorities.md` for the current ranking of work.