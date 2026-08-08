# GalSen IA — Priorities

## Current Ranking (highest first)

1. Keep all test suites green — no module is "done" while its tests fail
2. ✅ **VOLET 02 Phase 3 — Intégrations externes** (connecteurs email, calendrier, cloud)
3. ✅ **VOLET 02 Phase 4 — Frontend minimal** (dashboard web, API Client SDK)
4. ✅ **ADR-005 + SQLite pour le stockage persistant** — ADR accepté, tous les stores
   implémentés (Memory, Model, Knowledge, Notification, Calendar, Email, Cloud, File).
   Backend sélectionnable via `GALSEN_STORAGE_BACKEND=sqlite` ou par injection.
   8 stores SQLite, 92 tests — tous verts.
5. ✅ **Provider credentials (ADR-004)** — `_call_api` implémenté pour OpenAI,
   Anthropic, Google. 24 tests verts.
6. ✅ **Outils `tools/tools.yaml`** — les 20 outils déclarés chargent tous.
   Correctif : `src/__init__.py` ajoute `src/` au `sys.path` (les modules internes
   utilisent des imports nus), ce qui débloquait le tool `memory`.
7. 🔄 **Première feature réelle pour les utilisateurs sénégalais — Conseil Agricole**
   - ✅ Slice API livrée : outil `AgriAdviceTool` réparé, endpoint `POST /agri/advice`,
     17 tests verts. Suite complète : 914 passed, 5 failed (échecs pré-existants).
   - ➡️ Reste : page « Conseil Agricole » dans le dashboard web (`src/frontend/`)
     qui appelle l'endpoint, ou clôturer la feature côté API.

## How to use this file
- Always check this file before starting new work.
- Update the ranking whenever priorities change.
- Keep only the most important items at the top.