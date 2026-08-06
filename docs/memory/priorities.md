# GalSen IA — Priorities

## Current Ranking (highest first)

1. Keep all test suites green — no module is "done" while its tests fail
2. **Choose the next VOLET** — VOLET 02 is closed (10/10 chapters)
3. Test the hosted-provider generation path — ADR-004 is applied and `_call_api`
   is implemented for the three vendors; only the no-credentials branch is covered
4. Extend SQLite persistence to the engines still in-memory (audit, approval,
   and the three backend services) — the backend itself is decided (ADR-005) and
   already wired into memory, model and knowledge
5. Build the first real feature for Senegalese users (the `agri_advice` tool is the seed)

## How to use this file
- Always check this file before starting new work.
- Update the ranking whenever priorities change.
- Keep only the most important items at the top.