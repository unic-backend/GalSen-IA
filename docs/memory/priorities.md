# GalSen IA — Priorities

## Current Ranking (highest first)

1. Keep all test suites green — no module is "done" while its tests fail
2. **Finish the Conseil Agricole feature** — the API slice is delivered
   (`AgriAdviceTool`, `POST /agri/advice`, 17 tests). What remains is the page
   in the web dashboard, which after the reconciliation belongs in `src/web/`
   (ADR-008), not in the abandoned `src/frontend/`
3. **Choose the next VOLET** — VOLET 02 is closed (10/10 chapters)
4. Test the hosted-provider generation path — ADR-004 is applied and `_call_api`
   is implemented for the three vendors; only the no-credentials branch is covered
5. Build on the first real feature for Senegalese users

## How to use this file
- Always check this file before starting new work.
- Update the ranking whenever priorities change.
- Keep only the most important items at the top.
