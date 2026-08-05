# GalSen IA — Priorities

## Current Ranking (highest first)

1. Keep all test suites green — no module is "done" while its tests fail
2. **VOLET 02 Phase 3 — Intégrations externes** (connecteurs email, calendrier, cloud)
3. **VOLET 02 Phase 4 — Frontend minimal** (dashboard web, API Client SDK)
4. Decide provider credentials (ADR first) — the provider architecture is done
   (ADR-003), keys are the only thing blocking generation on hosted models
5. Extend SQLite persistence to the engines still in-memory (audit, approval,
   and the three backend services) — the backend itself is decided (ADR-005) and
   already wired into memory, model and knowledge
6. Build the first real feature for Senegalese users (the `agri_advice` tool is the seed)

## How to use this file
- Always check this file before starting new work.
- Update the ranking whenever priorities change.
- Keep only the most important items at the top.