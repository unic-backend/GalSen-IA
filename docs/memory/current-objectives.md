# GalSen IA — Current Objectives

## Active Phase
Core platform phase (building the engines in `src/`).
The foundation phase is complete: memory system, standards, ADR-001 and ADR-002 are done.

## Current Objectives (ordered by priority)

1. Keep every engine and service working and tested (all suites must pass before any work is called done).
2. ✅ **VOLET 02 Phase 3 — Intégrations externes (Ch. 09) : connecteurs email, calendrier, cloud**
3. ✅ **VOLET 02 Phase 4 — Frontend minimal : dashboard web, API Client SDK**
4. ✅ **Stockage persistant (ADR-005)** — SQLite adopté, 8 stores concrets, 92 tests verts.
   Backend sélectionnable via `GALSEN_STORAGE_BACKEND=sqlite` ou par injection.
5. ✅ **Credentials providers (ADR-004)** — `HostedProvider._call_api` implémenté
   pour OpenAI, Anthropic, Google. 24 tests. Les 3 providers hosted peuvent générer
   si les clés API sont dans l'environnement.
6. ✅ **Tools `tools/tools.yaml`** — les 20 outils déclarés chargent tous.
7. 🔄 **Première feature réelle pour les utilisateurs sénégalais — Conseil Agricole**.
   Slice API livrée : outil `AgriAdviceTool` réparé, endpoint `POST /agri/advice`,
   17 tests verts. Reste : page « Conseil Agricole » dans le dashboard web.

## Success Criteria for this phase
- Claude Code can understand the full project vision and current state just by reading the memory files.
- All important project knowledge is stored in files (not only in conversation history).
- The project is ready to start real development without losing context.