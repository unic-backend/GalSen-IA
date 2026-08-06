# GalSen IA — Current Objectives

## Active Phase
Core platform phase (building the engines in `src/`).
The foundation phase is complete: memory system, standards, ADR-001 and ADR-002 are done.

## Current Objectives (ordered by priority)

1. Keep every engine and service working and tested (all suites must pass before any work is called done).
2. **Pick the next VOLET.** VOLET 02 is finished — its ten chapters are covered,
   the last two by ADR-008 (frontend) and ADR-009 (scaling posture). VOLET 03
   (Development Manual) and VOLET 04 (Roadmap) are the natural successors.
3. Extend SQLite persistence (ADR-005) to the engines that are still in-memory: audit,
   approval, and the notification / search / file services. Memory, model and knowledge
   already select their backend through `GALSEN_STORAGE_BACKEND`.
4. Build the first real feature for Senegalese users.

## Success Criteria for this phase
- Claude Code can understand the full project vision and current state just by reading the memory files.
- All important project knowledge is stored in files (not only in conversation history).
- The project is ready to start real development without losing context.