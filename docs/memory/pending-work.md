# GalSen IA — Pending Work

## High Priority
- Cover the hosted-provider generation path with tests. ADR-004 is accepted and
  `_call_api` is implemented for OpenAI, Anthropic and Google, but only the
  no-credentials branch is tested: a successful generation and the 401 / 400 / 429
  responses are not.
- Extend SQLite persistence (ADR-005) to the audit and approval engines. The
  notification, calendar, email, cloud and file services already have their store.

- Report connector health inside `/health`, alongside the engines. The connectors are
  exposed on their own routes but a single health call still does not mention them.
  An unconfigured connector must not make the platform unhealthy.
- Write a calendar connector (CalDAV or an API): the calendar tool answers
  `unavailable` until one exists.
- Back the file service with the storage connector, now that `SQLiteFileStore`
  and `LocalDiskStorageConnector` both exist and overlap.
- Share the state that blocks a second instance (ADR-009), in this order:
  API key revocations, rate-limit counters, uploaded files, notifications.
  `/health` reports `multi_instance_ready: false` and names them. The trigger is
  the first deployment that needs more than one instance — not a date.
- Remove the temporary probes left at the repository root: `probe_agri.py` and
  `tests/probe_test.py`.

## Medium Priority
- Add log rotation. `logs/application.log` reached 6 MB and had silently broken the
  monitor agent before a `tail` operation was added. Nothing caps its growth.
- Review the model catalogue periodically: context windows and prices are declared in
  code (`src/model_engine/providers/*_provider.py`) and drift as vendors change them
- Move the 27 root `test_*.py` files into `tests/`, as `.claude/rules/testing.md`
  requires. They are collected and green as they are; only their location differs.
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