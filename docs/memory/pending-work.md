# GalSen IA — Pending Work

## High Priority
- **Decide whether the platform has users.** API keys map to roles, not to people:
  there is no account, no identity, no per-user data. The Phase 2 workspace,
  collaboration, and every adoption metric rest on this. It needs an ADR before any
  code — see `docs/roadmap/roadmap.md` and VOLET_13 (User Management Engine).
- Cover the hosted-provider generation path with tests. ADR-004 is accepted and
  `_call_api` is implemented for OpenAI, Anthropic and Google, but only the
  no-credentials branch is tested: a successful generation and the 401 / 400 / 429
  responses are not.
- Extend SQLite persistence (ADR-005) to the audit and approval engines. The
  notification, calendar, email, cloud and file services already have their store.
- Decide whether `LocalDiskStorageConnector` (ADR-007) and `SQLiteFileStore` /
  `FileSystemCloudStore` should coexist. Three ways to put a file on disk arrived
  from two branches; they overlap and nothing says which one a caller should use.

- Report connector health inside `/health`, alongside the engines. The connectors are
  exposed on their own routes but a single health call still does not mention them.
  An unconfigured connector must not make the platform unhealthy.
- Write a calendar connector (CalDAV or an API): the calendar tool answers
  `unavailable` until one exists.
- Share the two subsystems that block a second instance whatever the storage
  backend (ADR-009): API key revocations, then rate-limit counters. Files,
  notifications and engine state are already cleared by
  `GALSEN_STORAGE_BACKEND=sqlite`. `/health` reports `multi_instance_ready` and
  names what remains. The trigger is the first deployment that needs more than
  one instance — not a date.

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