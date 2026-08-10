# Knowledge Engine

What VOLET_05 asks for, what exists, and what is empty. Every figure here was measured
against the repository — not recalled. Measurements taken 2026-08-10 with
`KnowledgeManagerImpl().get_stats()` on the default (in-memory) backend.

---

## The vision (chapter 01), against the code

The chapter states five objectives. The engine is built for all five; four of them
cannot be observed because the base is empty.

| Objective | What implements it | State |
|-----------|--------------------|-------|
| Centralize knowledge | `KnowledgeManagerImpl`, one store behind `GALSEN_STORAGE_BACKEND` | built, **holds 0 items** |
| Ensure accuracy and consistency | `KnowledgeValidatorImpl`, `KnowledgePriority` P1–P4 | built, never exercised on real content |
| Enable intelligent retrieval | indexer + ranker + retriever + TTL cache | built, **retrieves from nothing** |
| Support continuous learning | 7 loaders (text, JSON, CSV, web page, API, PDF, DOCX) | built, no source is configured |
| Scale across industries and countries | 11 languages declared, incl. `ar`, `sw`, `ha`, `yo`, `zu`, `af`, `am` | declared in `types.py`, unused |

**The engine is not the gap. The content is.**

## Measured state

```
store    : 0 items, average content length 0, average confidence 0
indexer  : 0 unique terms, 0 indexed documents, 0 postings
graph    : 0 nodes, 0 edges
cache    : 0 / 1000 entries, 0 hits, 0 misses
```

Code: **12 modules, 2372 lines** in `src/knowledge_engine/`.
Tests: **8** in `test_knowledge_engine.py` — at the repository root, not in `tests/`.
`docs/knowledge/` does not exist.

## Who consumes it

Six modules already depend on the engine and therefore already retrieve nothing:

| Consumer | What it asks for |
|----------|------------------|
| `src/tools/rag/tool.py` | the retrieval-augmented generation tool |
| `src/agent/context.py` | knowledge injected into an agent's context |
| `src/api/server.py` | the knowledge routes |
| `src/api/health.py` | engine liveness |
| `src/integration/engine_registry.py` | registration among the engines |
| `src/storage/sqlite_knowledge_store.py` | the persistent store (ADR-005) |

Seven agents declare `knowledge` among their capabilities (`docs/architecture/overview.md`):
`planner`, `researcher`, `coder`, `reviewer`, `security`, `documentation`, `deployment`.

## Organization (chapter 02), against the code

The chapter names seven structural levels. Six were already carried by `KnowledgeItem`;
the first one did not exist and was added in phase 2.1.

| Level | What carries it | State |
|-------|-----------------|-------|
| Domains | `KnowledgeDomain` — the chapter's seven values plus `UNSPECIFIED` | **added (phase 2.1)** |
| Categories | `categories: List[str]`, free-form | present, **no call site sets it** |
| Topics | — | folded into tags and categories; no separate level |
| Documents | one `KnowledgeItem` per loaded document | present |
| Tags | `tags: List[str]`, filterable | present |
| References | `source` (11 fields) and `relations: List[str]` | present |
| Versions | `version: int` — a number, not a history (see below) | partial |

`KnowledgeDomain` is a **closed** enum: an unknown domain raises rather than being
accepted, because a domain nobody can name cannot receive an owner or a review cycle
(chapter 06). `UNSPECIFIED` is the default and means "not classified yet" — it is never
a classification. Both stores filter on `domain`, by enum or by value; `SQLiteKnowledgeStore`
persists it and migrates a base written before the column existed, whose rows read back
as `UNSPECIFIED` rather than being guessed.

## The gap the vision names and the code does not close

- **"Information must be versioned"** is half true. `KnowledgeItem.version` is an integer,
  `update_content()` increments it, and both stores refuse to overwrite a newer version.
  But `cleanup_old_versions()` documents the real behaviour in both
  `InMemoryKnowledgeStore` and `SQLiteKnowledgeStore`: **one version per ID is kept.**
  There is a version *number*, not a version *history*.

## What this means for the rest of the VOLET

Chapters 02 to 10 describe organization, lifecycle, validation, retrieval, governance,
security, integration and quality — all of which act on knowledge items. Measuring them
against an empty base measures the code, not the platform. Each following phase states
which of the two it is checking.
