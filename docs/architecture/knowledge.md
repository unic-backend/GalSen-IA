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

## Validation (chapter 04), against the code

The chapter's five **validation levels** are the statuses of chapter 02 under other names
(see above). What it adds is six **quality checks** and a five-step review process.

| Quality check | What runs it | State |
|---------------|--------------|-------|
| Source credibility | rule 10 of `KnowledgeValidatorImpl` — P1/P2 require a traceable source | automated |
| Version consistency | rules 8 and the duplicate/priority warnings in `check_consistency()` | automated |
| Completeness | rules 1–2 — content length bounds, summary not longer than content | automated, minimal |
| Technical correctness | — | **human, by nature** |
| Business relevance | — | **human, by nature** |
| Clarity | — | **human, by nature** |

Three of the six cannot be computed, and the platform does not pretend otherwise: no
clarity score is fabricated. They are what the `UNDER_REVIEW` stage is for, and
`status_history` records who performed it.

| Review step | Where it happens |
|-------------|------------------|
| 1. Initial validation | `KnowledgeValidatorImpl`, on `add_knowledge()` and `update_knowledge()` |
| 2. Peer review | `set_status(… UNDER_REVIEW → REVIEWED …)`, actor recorded |
| 3. Expert approval | `set_status(… → APPROVED …)`, reachable only from `REVIEWED` |
| 4. Publication | not a step (see chapter 03) |
| 5. Periodic revalidation | `list_due_for_revalidation()` | **added (phase 4.1)** |

Revalidation reads the last `→ approved` entry in `status_history`; an item approved with
no history falls back to `updated_at`, the only real date available. The threshold is
`GALSEN_KNOWLEDGE_REVALIDATION_DAYS`, 180 days by default; an unreadable or zero value
falls back to the default rather than silently switching revalidation off.

The chapter's four governance requirements are met by phase 3.1: the validator's identity
is recorded, validation history is preserved, a rewrite returns the item to `DRAFT` so it
is revalidated after a significant change, and superseded knowledge is archived rather
than deleted.

## Retrieval pipeline (chapter 05), against the code

| Step | Where it happens | State |
|------|------------------|-------|
| 1. Receive request | `retrieve_for_prompt()`, `retrieve_reliable()`, `search_knowledge()` | present |
| 2. Analyse user intent | — | **absent**: the query is tokenised, not interpreted |
| 3. Search indexed knowledge | `InMemoryKnowledgeIndexer.search()` — term overlap | present |
| 4. Rank candidates | `KnowledgeRankerImpl`, priority / confidence / recency | present |
| 5. Filter by policy | `is_retrievable()` on the RAG paths | **added (phase 5.1)** |
| 6. Return most relevant | present | present |

Step 5 withdraws what the lifecycle withdrew: `ARCHIVED` and `DEPRECATED` never feed a
reasoning path, however well they match the query. Two decisions shape it:

- **The default excludes withdrawal, not non-approval.** Requiring `APPROVED` by default
  would make an entire base invisible until someone approves it — a different falsehood,
  but a falsehood. `statuses=[KnowledgeStatus.APPROVED]` is available for callers that
  want it, and `statuses=[KnowledgeStatus.DEPRECATED]` for an audit.
- **`search_knowledge()` stays exhaustive.** It is explicit exploration by an operator,
  not a reasoning path; hiding drafts from it would hide the base from the person
  curating it.

The RAG path over-fetches (`max_items * 3`) before filtering, so a withdrawn match does
not silently consume a slot in the answer.

Step 2 remains absent and is not faked: nothing analyses intent, and the ranking score is
term overlap from the indexer — never a value derived from rank position.

## Ranking and cache (chapter 05), measured

Measured on 500 items, 200 identical searches, in-memory backend:

| Path | Before phase 5.2 | After |
|------|------------------|-------|
| `search_knowledge_with_scores` | 0.50 ms per call | **0.234 ms** |
| `retrieve_for_prompt` (RAG) | same index walk per call | **0.226 ms** |
| Cache counters over the run | **0 hits, 0 misses** | 398 hits, 2 misses |

The cache existed and was never consulted by any search: it only held
`knowledge:{id}` entries for reads by ID. `_cached_search()` now covers both paths, and
the producer runs only on a miss — including `list_items(limit=10000)`, which the RAG
path used to pay on every call.

**Invalidation is the part that matters.** Every write — add, update, delete, and
therefore every status transition — drops all `query:` entries. A cached result that
outlives a write hides a knowledge item that was just added; that is worse than no cache.
Index and RAG entries carry distinct keys, so the RAG policy filter never leaks into the
exhaustive search.

Ranking is unchanged and honest about what it is: `KnowledgeRankerImpl` orders by
priority, confidence and recency, and the relevance score is term overlap from the
indexer. **Semantic search does not exist** — chapter 05 asks for "semantic and keyword
search together" and only the keyword half is built.

What still costs, and is not addressed here: `_increment_access_count()` writes to the
store for every result of every search, which is now the dominant cost of a cached query.

## Governance (chapter 06), against the code

The chapter opens with "assign an owner to every knowledge domain". Ownership is declared
in the environment, exactly as API keys are (ADR-010):

```
GALSEN_KNOWLEDGE_OWNERS="legal:aissatou,technical:moussa"
```

`governance_report()` answers who owns what from the base's real content: per domain in
use, the item count, the status breakdown and the declared owner; plus the domains in use
with **no** owner and the count of unclassified items. A malformed entry, an unknown
domain or an empty subject is skipped rather than guessed — the domain then shows up as
unowned, which is the truth. Domains nobody uses are not claimed: a reproach without an
object is noise.

The chapter's five roles map onto mechanisms that already exist rather than onto new ones:

| Role in the manual | Mechanism |
|--------------------|-----------|
| Knowledge Owner | `GALSEN_KNOWLEDGE_OWNERS`, reported per domain |
| Knowledge Reviewer | the `actor` recorded on every `UNDER_REVIEW → REVIEWED` transition |
| Knowledge Contributor | `KNOWLEDGE_WRITE` permission (`src/api/rbac.py`) |
| System Administrator | the `admin` role |
| AI Orchestrator (consumer only) | reads through `retrieve_for_prompt()`; no write path |

**Nothing is verified**, and that is deliberate: whoever writes `GALSEN_KNOWLEDGE_OWNERS`
asserts the ownership, and `set_status` records the actor it is handed. This is the same
limit ADR-010 accepted for identity — the platform has no directory. Approval is *not*
blocked on a domain having an owner: that would freeze every base where nobody has
configured the variable yet. The gap is reported instead of enforced.

## Security (chapter 07), against the code

The chapter asks for least-privilege access and restricted sensitive knowledge. Phase 7.1
maps the sensitivity of chapter 02 onto the platform's roles — the mapping promised there
instead of a second audience field.

| Role | Reads |
|------|-------|
| `readonly` | public |
| `user` | public, internal |
| `operator` | public, internal, confidential |
| `admin` | everything, including restricted |

Four properties hold, each with a test:

- **Refusal is the default.** No role, an empty role or an unknown role reads public only.
  An internal call that forgets to pass a role loses access, it does not gain it.
- **Filtering is silent.** Nothing reports "3 results hidden" — saying so would disclose
  the existence of what is protected.
- **Every retrieval path enforces it**: `search_knowledge`, `search_knowledge_with_scores`,
  `retrieve_for_prompt` and `retrieve_reliable`, plus `POST /knowledge/search`, which now
  passes the caller's role from its `RBACContext`.
- **The tables cannot drift.** `test_les_roles_de_la_plateforme_sont_tous_couverts` fails
  if a role exists in `src/api/rbac.py` and not in `READABLE_BY_ROLE`.

`knowledge_security.py` names roles by string rather than importing `Role`: the engine
must not depend on the API layer. The test above is what keeps that decoupling honest.

The chapter's other requirements were already met elsewhere and are not re-implemented:
encryption at rest (`src/storage/encryption.py`, applied to knowledge content), audit of
significant events (audit engine), and authentication before access (ADR-010).

## Integration (chapter 08), against the code

The chapter lists six internal integrations. Measured against the repository, three exist,
two are indirect, and one has no consumer at all.

| Integration the manual names | Real consumer | State |
|------------------------------|---------------|-------|
| AI Orchestrator | `src/agent/context.py` — `search_knowledge()`, used by 7 agents | direct |
| Search Engine | `src/tools/rag/tool.py` — search, RAG, reliable retrieval | direct |
| User Management | `src/api/rbac.py` — roles gate reads (phase 7.1) | direct |
| Memory Engine | none — both are engines behind the same registry, neither calls the other | **indirect** |
| Workflow Engine | reaches knowledge only through an agent's context | **indirect** |
| Analytics Services | none — no consumer reads the knowledge base | **absent** |

The chapter's five-step data flow, end to end:

| Step | Where it happens |
|------|------------------|
| 1. Request received | `POST /knowledge/search`, RAG tool, agent context |
| 2. Permissions verified | `require_permission(KNOWLEDGE_SEARCH)`, then the role filter |
| 3. Knowledge retrieved | manager, through the cached index |
| 4. Results enriched | `domain`, `sensitivity` and `status` now travel with every result |
| 5. Response delivered | route, tool or agent, per caller |

Step 4 was broken by the earlier phases of this VOLET: three fields had been added to the
model and none of them crossed the module boundary, so a caller received content without
knowing whether it was approved or who owns it. Both serialisers now carry them.

**Backward compatibility**, which the chapter asks for explicitly: `AgentContext` passes
`role` only when one is given, and reads the new fields with a fallback to `None`. A
knowledge engine or an item predating this VOLET keeps working; an absent field reads as
unknown rather than as a guessed value. This was found by a regression — the fake engine
in `test_audit_engine.py` failed on the new keyword argument, which is exactly the failure
a third-party implementation would have hit.

A second regression came from the same change and is worth recording: serialising the
three fields without writing the inverse conversion made a **read-modify-write round trip
through the RAG tool silently destroy a knowledge item**. The tool returned
`status: "draft"` as a string, `KnowledgeItem(**item_dict)` accepted the string, and the
item then failed every enum comparison in the retrieval filters — present in the store,
invisible to every search. `_convert_classification()` closes it, and an invalid value is
now refused instead of stored.

## Quality metrics (chapter 09), against the code

Six metrics are named. Four are computed by `quality_report()` from the base's real
content; two are declared unavailable **inside the report itself**, with the reason.

| Metric | Computed as | State |
|--------|-------------|-------|
| Completeness | share of items with a classified domain, a traceable source, a summary | computed |
| Freshness | median and oldest `updated_at` age, plus stale approvals (phase 4.1) | computed |
| Duplicate rate | identical content hashes: groups and redundant items | computed |
| Validation coverage | share of items reviewed or approved, and the full status breakdown | computed |
| Accuracy rate | — | **unavailable**: no ground truth. The platform knows a source's declared reliability (P1–P4), not whether the content is true |
| User feedback | — | **unavailable**: no feedback mechanism exists |

The two unavailable metrics carry no number, not even a placeholder — `accuracy_rate` is
absent from the report and named in `unavailable`, so a caller cannot mistake a default
for a measurement. A test asserts that no numeric key exists for either.

On an empty base every ratio is `0.0`, never `1.0`: "nothing to fault" is not "everything
is good", and a fresh deployment must not read as perfect quality.

## Engine governance (chapter 10), against the code

The chapter asks for documented policies, approval of major changes, monitored quality
metrics, audit trails and published governance metrics.

| Requirement | Where it lives |
|-------------|----------------|
| Documented policies | this file, plus the transition table in `knowledge_lifecycle.py` |
| Approve major changes | the lifecycle: nothing reaches `APPROVED` without passing review |
| Monitor quality metrics | `GET /knowledge/quality` |
| Publish governance metrics | `GET /knowledge/governance` |
| Audit trails | `metadata["status_history"]` per item, plus the audit engine on agent reads |
| Periodic review | `list_due_for_revalidation()`, 180 days by default |

Both routes require `ADMIN_AUDIT` — operator and admin. A `readonly` key can search the
base but cannot read who owns it or how healthy it is; those figures describe a
deployment's operation, not its architecture, the same line `/metrics` draws.

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

---

# The second manual (VOLET 21)

`VOLET_21.md` is a **second Knowledge Engine manual**, after VOLET 05. It restates most of
that one and adds an ambitious component list — Knowledge Graph, Ontology Manager,
Inference Engine, Semantic Search Engine, Synchronization Service. Only what it asks
beyond VOLET 05 was examined, and most of that list is absent and stays absent: semantic
search is already a ranked P1 in `docs/memory/pending-work.md`, and synchronisation
presupposes a second instance that ADR-009 says is not possible yet.

## Duplicate removal was already met, structurally

Chapter 03's practice "remove duplicate knowledge" — the same one VOLET 20 exposed as
missing for memory — is already satisfied here, and not by a maintenance routine: a
knowledge item's **id is its content hash**, so saving identical content three times yields
one id and one item. Measured: `identifiants distincts: 1`, `redundant_items: 0`.

Nothing was added for it. Adding a `deduplicate()` here would have been code with no defect
under it.

## The finding: three views of one item, two different answers

That same content-addressing has a consequence nobody had followed through.
`KnowledgeStore.save()` refuses to overwrite when an equal-or-newer version already exists
under the id — and it signals that refusal **by returning the id**, so "created",
"unchanged" and "rejected" are indistinguishable to the caller.

`add_knowledge()` then cached the object it had been handed, without checking whether the
store took it. Measured, on a caller who corrects a fact and re-adds it under the same id:

```
via get_knowledge (cache) : Le mil se sème en juillet.
via le magasin            : Le mil se sème en juin.
via la recherche          : Le mil se sème en juin.
```

The caller read back their own submission and had every reason to believe it was stored.
Chapter 03 makes knowledge-integrity validation and consistency verification two of its
quality controls; a cache that contradicts its store defeats both.

**Fixed**: `add_knowledge()` now indexes and caches **what the store holds**, re-read after
the write, and logs a warning naming the id and the remedy when the submitted content was
not the content kept. The three views agree.

## The second defect, found by the test written for the first

The obvious way to correct a knowledge item — read it, edit it, bump the version, call
`update_knowledge()` — did not work on the in-memory store, and the test for the remedy is
what exposed it. `InMemoryKnowledgeStore.get()` returned its internal reference, so
incrementing the version on the object you just read also incremented the stored one, and
`update()`'s `version > existing` check then refused the write.

The SQLite store does not have this behaviour: it deserialises on every read, so it hands
back a fresh object. Two implementations of one interface, disagreeing on whether a read is
a copy — the same class of bug as the notification stores in VOLET 13, where `save()` meant
"create" in one and "upsert" in the other. `get()` now returns a copy in both.

`list_items()` deliberately still returns references: several callers mutate what it hands
back and rely on that, and changing it is a larger job than this VOLET's scope. It is worth
knowing before writing the next caller.

## Chapters 04 to 10

Management, security, compliance, monitoring, quality and governance restate VOLET 05:
domains and sensitivity, role-gated reads, the lifecycle with its withdrawn statuses,
revalidation of stale approvals, the governance and quality reports. Chapters 08 and 10 are
both titled "Knowledge Engine Governance" and assign work to a board the project does not
have.

The lifecycle metrics chapter 03 asks for — acquisition rate, validation success rate,
retrieval accuracy, semantic consistency score — are not added. The first two need a
history that survives a restart, which is the same open storage decision already recorded
in `pending-work.md`; the last two need a ground truth nobody has written. `quality_report()`
already names what it cannot compute and why, and that list did not need lengthening with
figures nobody could stand behind.
