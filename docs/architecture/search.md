# Search Engine

What VOLET_14 asks for, what exists, and what answers nothing. Every figure here was
measured against the repository on 2026-08-10, not recalled.

---

## What the platform searches today (chapter 01)

Three mechanisms carry the word "search", and they do not know about each other.

| Mechanism | Where | State |
|-----------|-------|-------|
| Knowledge index | `InMemoryKnowledgeIndexer` | works: inverted index, term-overlap score |
| Unified search service | `src/services/search/`, `POST /search` | answered nothing before phase 4.1 — see below |
| Web search tool | `src/tools/web_search/` | separate path, not part of this engine |

The chapter's six strategic capabilities, at the state this VOLET leaves them:

| Capability | State |
|------------|-------|
| Full-text search | built (keyword, inverted index) |
| Intelligent ranking | built (`KnowledgeRankerImpl`: priority, confidence, recency) |
| Search analytics | **added (phase 6.1)** — volume, latency, empty rate in `/metrics` |
| Multi-source indexing | **one source of four wired** (knowledge, phase 4.1) |
| Semantic search | **absent** |
| Personalised search | **absent** — no per-caller signal is kept |

## The finding: `POST /search` could not return a result

`SearchManagerImpl` merges results from registered providers. **No provider is ever
registered**, anywhere in `src/`:

```
providers enregistrés : {}
résultats: 0 | sources utilisées: [] | ms: 0.004
```

`register_provider()` exists, `SearchProvider` is exported from `src/services/__init__.py`,
and **no class in the repository implements it**. The route is authenticated, rate-limited,
documented, and structurally unable to answer: it returns `total: 0` and
`sources_used: []` for every query, in 4 microseconds — the time it takes to iterate an
empty dictionary.

This is not a bug in the merge logic, which is correct and tested. It is a wiring that
was never done. The failure mode is what matters: the route did not report "search
unavailable", it reported "no result" — indistinguishable from an empty base.

**Fixed in phase 2.2**: `registered_sources()` exposes what is actually wired, and
`POST /search` answers **503 with the reason** while nothing is, pointing the caller at
`/knowledge/search`. The route works unchanged the moment a provider is registered, which
a test proves with a stub provider rather than by asserting the 503 alone.

Writing the providers is not this phase's job — it is a wiring decision that belongs to
chapter 04 (source registration). What this phase refused to leave in place is a route
that answers plausibly while being unable to answer at all.

## Architecture (chapter 02), against the code

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| Data Sources | knowledge, memory, document, vision — declared in `SearchSource` | declared |
| Indexing Engine | `InMemoryKnowledgeIndexer`, knowledge only | partial |
| Search Orchestrator | `SearchManagerImpl` | built; **one provider since phase 4.1** |
| Ranking Engine | `KnowledgeRankerImpl` + per-source weights in the merge | built |
| Query Processor | `_tokenize()` — lowercase, French stop-words, length > 1 | minimal |
| Search API | `POST /search`, `POST /knowledge/search` | built |
| Analytics Module | `record_search()` + the `search` block of `/metrics` | **added (phase 6.1)** |

Five of seven existed when the VOLET opened; the orchestrator had nothing to orchestrate
and the analytics module had no code at all. Both were closed in phases 4.1 and 6.1.

**The per-source weights are a hazard worth naming.** `_get_score_weight()` multiplies
knowledge by 1.0, memory by 0.9, document by 0.85, vision by 0.8 — constants nothing
justifies and no measurement produced. They are inert today because no provider feeds
them; the day one does, they will silently reorder results according to numbers nobody
chose deliberately.

## Data flow (chapter 02), end to end

| Step | Where it happens | State |
|------|------------------|-------|
| 1. Collect content | knowledge loaders (7 formats) | present |
| 2. Index data | `add()` / `update()` / `delete()` on every knowledge write | present |
| 3. Process queries | `_tokenize()` | minimal |
| 4. Rank results | ranker, then per-source weights | present |
| 5. Return responses | `SearchResponse.to_dict()` | present |
| 6. Record analytics | `record_search()` | **added (phase 6.1)** |

Step 6 is the one the manual asks for twice (chapters 02 and 06) and the one nothing
implemented: no query, latency or empty-result rate was kept, and `execution_time_ms` was
computed per response and thrown away with it. See *Search analytics* below.

## Lifecycle (chapter 03), against the code

Nine stages. Six exist, one was wired in phase 4.1, two are absent.

| Stage | Where it happens | State |
|-------|------------------|-------|
| 1. Content Collection | 7 knowledge loaders | present |
| 2. Data Validation | `KnowledgeValidatorImpl` on every write | present |
| 3. Index Creation | `_rebuild_index()` at construction, incremental on each write | present |
| 4. Query Processing | `_tokenize()` | minimal |
| 5. Result Ranking | ranker, then per-source weights | present |
| 6. Response Delivery | `SearchResponse`, `KnowledgeSearchProvider` | **wired in phase 4.1** |
| 7. Usage Analytics | `record_search()`, `/metrics` | **added (phase 6.1)** |
| 8. Index Maintenance | `check_integrity()` reports; **no scheduled rebuild** | partial (phase 5.1) |
| 9. Archive and Secure Deletion | `delete()` removes from index, store, graph and cache | present, not "secure" |

Stage 9 deletes; it does not overwrite or prove erasure. Calling that "secure deletion"
would be a claim nothing backs, so it is recorded as ordinary deletion.

## Source registration (chapter 04) — the wiring

`KnowledgeSearchProvider` (`src/services/search/providers.py`) is the first real provider.
It adapts the knowledge engine to the service contract and re-implements nothing: the
engine's own rules, access control included, still decide what comes back.

**Searching does not grant reading.** `SearchQuery` now carries `role`, `POST /search`
fills it from the caller's `RBACContext`, and `_build_provider_query()` copies it when it
rebuilds the per-source query — dropping it there would have made every unified search
anonymous, which is precisely the bypass this wiring could have introduced.

Memory, document and vision remain declared in `SearchSource` with no provider. A test
asserts that gap rather than leaving it to be rediscovered.

## Index types (chapter 05), against the code

| Type the manual names | State |
|-----------------------|-------|
| Full-text indexes | built — inverted index, term → document ids |
| Metadata indexes | **partial**: filtering happens in the store, not in an index; every item is scanned |
| Semantic indexes | **absent** |
| Vector indexes | **absent** — `EmbeddingsTool` exists and nothing indexes what it produces |
| Hybrid indexes | **absent** — needs the two missing halves first |

One of five is built. The embeddings tool is worth naming: the platform can already turn
text into vectors and has nowhere to put them, which is why "semantic search" is a wiring
and modelling job rather than a research one.

### Index integrity (chapter 05, quality controls)

`check_integrity()` compares the index to the store it indexes and names three
divergences, each with a test that provokes it:

- **missing** — in the store, absent from the index (a direct store write)
- **orphaned** — indexed, gone from the store (a delete that bypassed the index)
- **stale** — present in both, but the indexed terms no longer match the content

Lists are capped at 50 identifiers; past that the count is what decides a rebuild.
Nothing schedules that rebuild yet — the check reports, the operator acts.

### Index performance and freshness (phase 5.2), measured

On 1 000 documents, in-memory backend:

| Operation | Cost |
|-----------|------|
| Full index build | 8.0 ms (1 030 unique terms, 7 990 postings) |
| `check_integrity()` | 6.8 ms |
| Incremental indexing | 0.011 ms per document |

Freshness is not a delay: indexing is synchronous with the write, so a knowledge item is
searchable on the call that follows its creation, and integrity holds after an add and
after a delete. There is no queue to fall behind.

**Two silent truncations were found at 10 000 documents and fixed:**

- `count()` returned `list_items(limit=10000)`'s length in both stores. A store holding
  10 050 items reported **10 000** — a wrong count nothing could detect. It is now a real
  count: `len` of the dictionary in memory, `SELECT COUNT(*)` in SQLite.
- `_rebuild_index()` read the same 10 000. Past that, documents were **never indexed and
  never findable**, with no signal at all. The bound is now a named constant shared with
  the integrity check, reaching it logs a warning, and `check_integrity()` reports
  `truncated: true` and refuses to call the index consistent.

Measured after the fix: 10 050 stored, 10 050 indexed, consistent.

### What the query processor actually does

Measured on one indexed sentence — *"La pluviométrie à Kaolack conditionne la récolte
d'arachide."*:

| Query | Results |
|-------|---------|
| `pluviométrie` | 1 |
| `PLUVIOMÉTRIE` | 1 — case is handled |
| `pluviometrie` | **0 — accents are not** |
| `récolte arachide` | 1 |
| `arachides` | **0 — no stemming: a plural misses its singular** |

A Senegalese deployment is exactly where unaccented typing is the norm, so this is a
relevance problem before it is a linguistics one. Stop-words are French only; a query in
Wolof, English or Arabic keeps its own filler words as search terms.

The score is the share of query terms present in the document, and nothing else: no term
frequency, no document length, no field weighting. Two documents matching the same terms
score identically, however different their content.

## Search analytics (chapters 02, 06 and 09)

Step 6 of the data flow existed nowhere: no query, latency or empty-result rate was kept,
and `execution_time_ms` was computed per response and thrown away with it.

`record_search()` feeds the collector `/metrics` already uses — no second mechanism — and
`GET /metrics` gains a `search` block:

```json
"search": { "queries": 42, "empty": 7, "empty_rate": 0.1667 }
```

Plus one latency histogram per source queried (`search.latency.knowledge`).

**What is measured is behaviour, never content.** A query is what someone wanted to know;
storing it would turn an operational measurement into a log of everyone's questions. A
test searches for a distinctive string and asserts it appears nowhere in `/metrics`.

`empty_rate` is `null` rather than `0.0` when no search has run — the chapter 09 quality
metric that can be computed without a human jury is *how often the platform found
nothing*, and zero searches must not read as perfect coverage.

## Search security (chapter 07)

An index is built **before** any access control: everything is in it, including what a
given caller may not read. Filtering therefore has to hold on every path out, and the
tests check each one:

- the **results** exclude what the role cannot read (phase 4.1);
- the **total** counts permitted results only — a total of 2 next to a single result
  would announce the existence of a hidden document;
- **exact terms** from a restricted document return nothing, so the index cannot be
  probed word by word;
- the **response body** contains no fragment of restricted content, not even its
  sensitivity label;
- a search **without a role** reads public only — forgetting the role loses access rather
  than granting it.

## Source governance and search quality (chapters 08 and 09)

Both chapters answer the same practical question — *what do we search, and does it work* —
so one report carries them: `GET /search/status`, restricted to `ADMIN_AUDIT`.

Ownership is declared in the environment, as elsewhere on this platform:

```
GALSEN_SEARCH_OWNERS="knowledge:aissatou,memory:moussa"
```

The report separates **declared** from **wired** — three of the four sources in
`SearchSource` still have no provider, and a declared source must never read as available.
Only wired sources are claimed as unowned: demanding a responsible party for a source that
does not exist is noise.

It also carries the index integrity check (chapter 05) and the search counters
(chapter 06), so an operator reads one page rather than three.

**Relevance is not scored.** Precision, recall and user satisfaction are named in
`unavailable_metrics` with their reason: precision and recall need a query set with
expected results judged by a human, and none exists in this repository; a recall figure
without that denominator would be arbitrary. What *is* measured without a jury is the
empty-result rate — how often the platform found nothing — and index integrity.

## What this VOLET did not do

- **Semantic and vector search remain absent.** `EmbeddingsTool` produces vectors and
  nothing stores or queries them. This is a wiring and modelling job, and it is the single
  largest gap left in the engine.
- **Intent analysis (pipeline step 2) is still nothing.** Queries are tokenised, not
  interpreted.
- **Accents and stemming.** `pluviometrie` finds nothing when `pluviométrie` is indexed,
  and `arachides` misses `arachide`. On a Senegalese deployment, unaccented typing is the
  norm — this is a relevance defect before it is a linguistic one.
- **Memory, document and vision have no provider.** One source of four is wired.
- **No scheduled index rebuild.** `check_integrity()` reports; a human acts.
- **Stage 9 is deletion, not secure deletion.** Nothing overwrites or proves erasure.

None of these received a placeholder value or a plausible-looking score.

---

# Accents and plurals (backlog P1, 2026-08-11)

Measured on a base holding « La pluviométrie du Sénégal varie selon les régions » and
« Les arachides se récoltent en octobre » :

```
pluviométrie → 1    pluviometrie → 0
Sénégal      → 1    senegal      → 0
arachides    → 1    arachide     → 0
```

Unaccented typing is the norm on a keyboard used in Senegal, so a platform that finds
nothing without accents finds nothing for its users. The plural case is the most ordinary
search there is: looking up the singular of something written in the plural.

`src/text_normalization.py` applies two transformations — accents removed, a simple final
`s`/`x` dropped on words longer than four letters — **on both sides**, indexing and query
alike. That symmetry is what makes a lossy transformation safe: it cannot prevent a match,
only create one too many. Stop words are normalised too, so `où` and `ou` are the same
word to the filter.

What it deliberately does not do, and would need a real morphological analyser for:
`-aux` plurals (journal/journaux), irregulars, conjugated verb forms, and languages other
than French. Naming those is cheaper than pretending they work.

## The finding next door: memory search returned everything

Fixing the query side surfaced a heavier defect in `MemoryRetriever.retrieve()`. It does
score by Jaccard similarity, but the default `min_score` was `0.0` and the test was
`score >= min_score` — so a score of **zero**, meaning not one term in common, passed.

```
search_memory(query="xyzzy") → 2 mémoires sur 2, notées 0.0
```

Every caller asking for memories about something received all of that subject's memories,
and an agent's context filled with unrelated memories presented as relevant. A zero-score
item is not a result; `list_items()` remains the way to get everything. Memories whose
content is not text fall in the same case — a dictionary cannot be matched against a
query, so it is not a search hit.
