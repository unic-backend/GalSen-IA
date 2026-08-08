# ADR-005: Persistent Storage Backend

## Status
Accepted

## Date
2026-08-27

## Context
All engines in GalSen IA are currently in‑memory only. This means that any state (memories, models, knowledge, etc.) is lost when the process terminates. For a production‑grade platform we need a durable storage solution that can survive restarts, enable horizontal scaling, and support backup/restore procedures.

The chosen storage must satisfy the following requirements:

- **Simplicity**: Easy to set up, operate, and backup for development and small‑to‑medium deployments.
- **Zero configuration for local development**: Should work out‑of‑the‑box without requiring external services.
- **ACID transactions**: To guarantee consistency of concurrent reads/writes.
- **Query capability**: Ability to retrieve records by key, range, or simple criteria without needing a full‑fledged query language for simple key‑value use cases.
- **Embeddable**: Preferably a library that can be linked into the Python process, avoiding a separate server process.
- **Cross‑platform**: Works on Windows, Linux, and macOS.
- **Licensing**: Permissive license compatible with the project's open‑source goals.

## Decision
We will adopt **SQLite** as the default persistent storage backend for all engines that require durability.

### Rationale
- SQLite is a self‑contained, server‑less, zero‑configuration SQL database engine.
- It provides full ACID compliance and supports complex queries if needed.
- The Python standard library includes the `sqlite3` module, eliminating external dependencies for basic usage.
- It stores the entire database in a single flat file, making backups and versioning trivial.
- It works identically across all major operating systems.
- Licensed in the public domain, which is compatible with any licensing model.

### Scope
Initially, SQLite will be used to persist:
- Memory Engine (short‑term, long‑term, user, agent‑shared, conversation, session, workspace/project, knowledge memories)
- Model Engine (model registry, provider availability cache)
- Knowledge Engine (knowledge graph, cache, index)
- Any future engine that requires durable state.

Each engine will manage its own SQLite database file (or a shared file with separate tables) under a configurable `data/` directory. Connection pooling and threading considerations will be handled per engine.

## Consequences

### Positive
- **Zero‑config dev**: Developers can run the platform without installing any external database.
- **Reliability**: Atomic writes protect against corruption; crash recovery is automatic.
- **Simplicity**: Backup is a file copy; migration can be done with `sqlite3 .dump`.
- **Performance**: Adequate for the expected read/write loads of a single‑node deployment.
- **Extensibility**: If future needs outgrow SQLite (e.g., high write concurrency, replication), we can migrate to a client/server DB (PostgreSQL) with minimal impact because the storage layer will be abstracted behind repository interfaces.

### Negative
- **Write concurrency**: SQLite allows multiple readers but only one writer at a time (due to a global write lock). For high‑throughput write workloads this could become a bottleneck.
- **Database size limit**: Theoretical limit of 140 TB, practical limit far below that; still more than enough for anticipated data volumes.
- **Lack of built‑in replication**: Horizontal scaling would require moving to a client/server DB or implementing application‑level sharding.

### Mitigation
- Write‑heavy workloads will be buffered (e.g., via async queues) to reduce lock contention.
- Monitoring of database size and lock contention will be added; if thresholds are exceeded, a decision to migrate to PostgreSQL can be revisited via a new ADR.
- For future HA requirements, we will abstract the storage layer behind a repository interface, allowing alternative implementations.

## Implementation Plan
1. Add a `src/storage/` package containing a thin SQLAlchemy‑like wrapper or direct `sqlite3` usage with connection handling.
2. Define base repository classes (`BaseRepository`) that provide CRUD operations.
3. Refactor each engine to receive a repository instance via dependency injection (constructor parameter).
4. Initialise the database schema on first run (create tables if not exists).
5. Provide a configuration option (`storage.path`) to set the directory for SQLite files.
6. Write unit tests using an in‑memory SQLite database (`:memory:`) to ensure correctness without touching the filesystem.
7. Update documentation (`docs/storage.md` if needed) and update `CHANGELOG.md`.

## Implementation Status (Phase 5 — 2026-08-05) — COMPLETE

All 8 stores are implemented and tested (92 tests — all green):

| Store | File | Tests |
|-------|------|-------|
| `SQLiteMemoryStore` | `src/storage/sqlite_store.py` | ✅ Legacy tests |
| `SQLiteModelStore` | `src/storage/sqlite_model_store.py` | ✅ Legacy tests |
| `SQLiteKnowledgeStore` | `src/storage/sqlite_knowledge_store.py` | ✅ Legacy tests |
| `SQLiteNotificationStore` | `src/storage/sqlite_notification_store.py` | ✅ `test_storage_service_stores.py` |
| `SQLiteCalendarStore` | `src/storage/sqlite_calendar_store.py` | ✅ `test_storage_service_stores.py` |
| `SQLiteEmailStore` | `src/storage/sqlite_email_store.py` | ✅ `test_storage_service_stores.py` |
| `SQLiteCloudStore` | `src/storage/sqlite_cloud_store.py` | ✅ `test_storage_service_stores.py` |
| `SQLiteFileStore` | `src/storage/sqlite_file_store.py` | ✅ `test_storage_service_stores.py` |

Backend selection via `GALSEN_STORAGE_BACKEND=sqlite` env var or explicit store injection
at manager construction. Default remains `"in-memory"`. Data directory configurable via
`GALSEN_DATA_DIR` (default `"data"`), resolved by `src/storage/paths.py`.

All stores exposed in `src/storage/__init__.py`.

Steps 1–5 were initially implemented for the Model and Knowledge engines:

- `SQLiteModelStore` and `SQLiteKnowledgeStore` under `src/storage/` persist the
  authoritative items of the Model and Knowledge engines (ADR-005 scope).
- The `Memory` engine already had `SQLiteMemoryStore` (step 1, prior work).
- Engine backends are selected by dependency injection at manager construction:
  an injected store wins, otherwise `GALSEN_STORAGE_BACKEND` (default
  `"in-memory"`), otherwise the in-memory store. The data directory is
  configurable via `GALSEN_DATA_DIR` (default `"data"`), resolved by
  `src/storage/paths.py`.
- Derived structures are NOT persisted: the knowledge index, graph and cache are
  rebuilt in memory when a manager is constructed over a SQLite store
  (`InMemoryKnowledgeIndexer` reads through the public `list_items()` contract).
  The graph (links between knowledge items) has no persistence yet and is
  therefore lost on restart — acceptable until the graph is materialized
  (pending Phase 5 / future work).

## Related Documents
- ADR-001: Choose Python as the primary implementation language
- ADR-002: Choose initial technology stack
- ADR-003: Model Provider Architecture
- ADR-004: Provider Credential Handling