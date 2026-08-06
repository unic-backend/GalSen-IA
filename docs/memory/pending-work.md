# GalSen IA — Pending Work

## High Priority
- Cover the hosted-provider generation path with tests. ADR-004 is accepted and
  `_call_api` is implemented for OpenAI, Anthropic and Google, but only the
  no-credentials branch is tested: a successful generation and the 401 / 400 / 429
  responses are not. Nothing else blocks generation — a key in the environment is
  enough.
- Extend SQLite persistence (ADR-005) to the engines still in-memory: audit, approval,
  and the notification / search / file services. The backend, the `BaseRepository`
  contract and the `GALSEN_STORAGE_BACKEND` / `GALSEN_DATA_DIR` selection already exist
  and are used by memory, model and knowledge.

- VOLET 02 ch. 09 — connectors, remaining phases: 3.3 calendar, 3.4 cloud storage
  (disk first, S3 later), 3.5 wiring into EngineRegistry, `/connectors` endpoints and
  an RBAC permission. The contract and registry landed in 3.1 (ADR-007), the SMTP
  email connector in 3.2.

## Medium Priority
- Add log rotation. `logs/application.log` reached 6 MB and had silently broken the
  monitor agent before a `tail` operation was added. Nothing caps its growth.
- Review the model catalogue periodically: context windows and prices are declared in
  code (`src/model_engine/providers/*_provider.py`) and drift as vendors change them
- Move the 27 root `test_*.py` files into `tests/`. They are collected and green as they
  are; only their location still contradicts `.claude/rules/testing.md`.
- Speed up the orchestration suites: `test_integration.py` takes ~4 minutes because the
  tester agent runs eight real suites on every pipeline execution
- Create deployment documentation
- Create API / dataset / research templates

## Low Priority
- Write contribution guidelines (the repository itself is live:
  `github.com/unic-backend/GalSen-IA`)

## Notes
This file is the backlog.  
Move items to `completed-work.md` when they are finished.
Update priorities in `priorities.md` when the order changes.