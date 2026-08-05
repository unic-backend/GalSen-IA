# GalSen IA — Current Objectives

## Active Phase
Core platform phase (building the engines in `src/`).
The foundation phase is complete: memory system, standards, ADR-001 and ADR-002 are done.

## Current Objectives (ordered by priority)

1. Keep every engine and service working and tested (all suites must pass before any work is called done).
2. **VOLET 02 Phase 3 — Intégrations externes (Ch. 09) : connecteurs email, calendrier, cloud**
3. **VOLET 02 Phase 4 — Frontend minimal : dashboard web, API Client SDK**
4. Decide on a persistent storage backend — every engine is in-memory today, which is the
   single biggest gap between the current code and a usable platform. Requires an ADR.
5. Build the first real feature for Senegalese users.

## Success Criteria for this phase
- Claude Code can understand the full project vision and current state just by reading the memory files.
- All important project knowledge is stored in files (not only in conversation history).
- The project is ready to start real development without losing context.