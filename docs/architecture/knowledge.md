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

## Classification (chapter 02), against the code

The chapter classifies knowledge on five axes. Two existed, two were added in phase 2.2,
and one is deliberately not a field.

| Axis | What carries it | State |
|------|-----------------|-------|
| Source | `KnowledgeSource` — 11 fields, and `SourceCategory` | present |
| Reliability | `KnowledgePriority` P1–P4 (VOLET_01 ch. 04) and `confidence` | present |
| Sensitivity | `KnowledgeSensitivity` — public, internal, confidential, restricted | **added (phase 2.2)** |
| Status | `KnowledgeStatus` — draft, under review, reviewed, approved, archived, deprecated | **added (phase 2.2)** |
| Audience | — | **not a field, by decision** |

**Status is one axis for two chapters.** Chapter 02 lists Draft / Reviewed / Approved /
Archived, chapter 04 lists Draft / Under Review / Verified / Approved / Deprecated: the
same progression under two vocabularies. `REVIEWED` carries what chapter 04 calls
*Verified*, and there is no `verified` value. Two enums for one progression would be the
duplication chapter 02 forbids.

**Audience is not a field** because it would restate the same fact twice: sensitivity says
what must be protected, and the platform's roles (`src/api/rbac.py`) say who may read.
Phase 7.1 maps one onto the other; an independent audience list would be a second,
divergent answer to the same question.

Defaults protect nothing and validate nothing: an item is `PUBLIC` and `DRAFT` until
someone says otherwise, and rewriting the content sends it back to `DRAFT` — an approval
belongs to the text that was approved. Sensitivity, which belongs to the subject rather
than to the wording, is kept across versions.

## Lifecycle (chapter 03), against the code

The chapter names eight stages. Six are operations that already existed, one was added in
phase 3.1, and one is absent by decision.

| Stage | Where it happens | State |
|-------|------------------|-------|
| 1. Creation | `add_knowledge()`, the 7 loaders | present |
| 2. Review | `set_status(… UNDER_REVIEW …)` | **added (phase 3.1)** |
| 3. Validation | `KnowledgeValidatorImpl`, run on add and update | present |
| 4. Approval | `set_status(… APPROVED …)`, reachable only through review | **added (phase 3.1)** |
| 5. Publication | — | **not a stage here**: retrieval filters on status, nothing is "published" |
| 6. Maintenance | `update_knowledge()` — a rewrite returns the item to `DRAFT` | present |
| 7. Archiving | `set_status(… ARCHIVED …)`, reason required | **added (phase 3.1)** |
| 8. Retirement | `set_status(… DEPRECATED …)`, terminal; `delete_knowledge()` erases | **added (phase 3.1)** |

`knowledge_lifecycle.py` holds the permitted transitions and nothing else. Three rules
it enforces:

- **Review cannot be skipped.** `DRAFT → APPROVED` raises `InvalidStatusTransition`, and
  the message lists what was reachable instead.
- **Retirement is terminal.** Nothing leaves `DEPRECATED`; what must no longer be cited
  becomes citable again only by being rewritten, which is a new revision.
- **Every transition is a revision.** The version increments, and
  `metadata["status_history"]` records who moved it, from where, to where, when and why.
  `actor` is mandatory — a transition nobody signed cannot be governed (chapter 06) — and
  a reason is mandatory for archiving and retirement.

Who *may* perform a transition is not decided here: `set_status` records the actor it is
given and trusts it, exactly as ADR-010 trusts whoever declares a key. Binding it to
roles belongs to chapters 06 and 07.

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
