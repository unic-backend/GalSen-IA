# Memory Engine

What VOLET_07 asks for, and what the engine did before this VOLET looked. Measured against
the repository on 2026-08-11.

---

## State (chapters 01 and 02)

**1 632 lines** across 9 modules. Seven architecture components, seven present:

| Component the manual names | What plays it |
|----------------------------|---------------|
| Memory Manager | `MemoryManager` |
| Memory Storage | `InMemoryMemoryStore`, `SQLiteMemoryStore` (ADR-005) |
| Retrieval Engine | `InMemoryMemoryRetriever` — Jaccard similarity on terms |
| Indexing Service | `InMemoryMemoryIndexer` |
| Context Processor | `AgentContext` — memories are written and read per request |
| Synchronization Module | `GALSEN_STORAGE_BACKEND=sqlite`, shared across processes |
| Memory Governance Layer | `quality_report()`, `list_inactive()` — **added by this VOLET** |

The model was already rich: six memory types, four priorities, four statuses
(`ACTIVE`, `ARCHIVED`, `DELETED`, `EXPIRED`), owner, session, tags, expiry, version.
The gap was not in the vocabulary — it was that **three of those declarations did
nothing**.

## Four defects, all of the same family

Each was a declared rule that nothing applied, so a memory survived what should have
removed it.

### 1. "Forgetting" destroyed instead of archiving

`forget_memory()` was `return self.delete_memory(item_id)`. The `ARCHIVED` status existed
and was never set by anything. Chapter 03 separates archiving (stage 7) from deletion
(stage 8) precisely because they are different promises — and no caller expects the
gentlest verb in the API to erase permanently.

Now: `forget_memory()` sets `ARCHIVED`, de-indexes, and keeps the memory readable by its
identifier. `delete_memory()` still erases.

### 2. Archiving would have changed nothing anyway

The retriever passed `status=None` with the comment *"we don't filter by status here"*.
An archived memory kept coming back in every search, so the status would have been a label
with no effect. The retriever now considers `ACTIVE` memories only.

### 3. Expiry only applied if someone ran the cleaner

A memory past `expires_at` was served normally by `get_memory()` and by search. The
retention date meant nothing until `cleanup_expired()` happened to be called — and nothing
calls it on a schedule. Expiry is now honoured **at read time**, which is what makes it a
rule rather than an intention.

### 4. `cleanup_expired()` reported deletions the cache undid

It returned an exact count of removed memories while the cache kept serving them under
`item:{id}`. Measured before the fix: `cleanup_expired()` → `1`, and the memory was still
readable. Same failure as the knowledge query cache in VOLET 05 — a cache that outlives the
data it describes. The manager now clears the cache when the cleaner removed anything.

## `consolidate_memory()` said nothing was to be done

It returned `0` with a comment listing what a real implementation would do. `0` is
indistinguishable from "nothing needed consolidating", so a caller could believe short-term
memories were being promoted, summarised and decayed. It now raises `NotImplementedError`
naming what is missing: no rule exists for what moves from short to long term, what gets
summarised, or under which forgetting curve. Nothing in the repository called it.

This is the project's own rule applied literally: an unfinished capability reports its
state, it never returns a plausible answer.

## Isolation (chapter 07)

Measured: `search_memory(user_id=...)` filters correctly, and `search_memory()` without a
user sees everything. `get_memory(id)` does **not** filter — the engine trusts its caller.

That is not a hole, because the boundary is one layer up: `GET /memory/retrieve/{id}`
checks ownership and answers **404, not 403**, for another subject's memory (VOLET 16,
exit criterion C2). Distinguishing "exists but not yours" from "does not exist" would let
someone enumerate identifiers. The engine-level behaviour is recorded here so nobody
mistakes it for authorisation.

## Quality and retention (chapters 08 and 09)

`quality_report()` computes four of the chapter's six metrics from real content:

| Metric | Computed as |
|--------|-------------|
| Memory freshness | median and oldest `updated_at`, plus memories inactive past a threshold |
| Duplicate rate | identical content **per owner** — the same sentence for two users is not a duplicate |
| Metadata completeness | share with an owner, with tags, with an expiry |
| Consistency | full breakdown by status and by type |
| Retrieval accuracy | **unavailable**: no judged query set exists |
| User satisfaction | **unavailable**: no feedback is collected |

Access latency is deliberately not recomputed here — `/metrics` and
`docs/standards/performance.md` already own it.

`list_inactive()` answers chapter 08's "review inactive memories" by **naming** them, at a
configurable threshold (90 days by default). It archives nothing: taking a memory out of
use is a decision, not a side effect of running a report.

On an empty engine every ratio is `0.0`, never `1.0`.
