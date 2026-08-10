# Search Engine

What VOLET_14 asks for, what exists, and what answers nothing. Every figure here was
measured against the repository on 2026-08-10, not recalled.

---

## What the platform searches today (chapter 01)

Three mechanisms carry the word "search", and they do not know about each other.

| Mechanism | Where | State |
|-----------|-------|-------|
| Knowledge index | `InMemoryKnowledgeIndexer` (178 lines) | works: inverted index, term-overlap score |
| Unified search service | `src/services/search/` (410 lines), `POST /search` | **answers nothing — see below** |
| Web search tool | `src/tools/web_search/` | separate path, not part of this engine |

The chapter's six strategic capabilities, measured:

| Capability | State |
|------------|-------|
| Full-text search | built (keyword, inverted index) |
| Intelligent ranking | built (`KnowledgeRankerImpl`: priority, confidence, recency) |
| Search analytics | **absent** — no query is recorded anywhere |
| Multi-source indexing | **declared, never wired** |
| Semantic search | **absent** |
| Personalised search | **absent** — no per-caller signal is kept |

## The finding: `POST /search` cannot return a result

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
| Search Orchestrator | `SearchManagerImpl` | built, **no provider** |
| Ranking Engine | `KnowledgeRankerImpl` + per-source weights in the merge | built |
| Query Processor | `_tokenize()` — lowercase, French stop-words, length > 1 | minimal |
| Search API | `POST /search`, `POST /knowledge/search` | built |
| Analytics Module | — | **absent** |

Five of seven exist in some form. The orchestrator has nothing to orchestrate, and the
analytics module has no code at all.

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
| 6. Record analytics | — | **absent** |

Step 6 is the one the manual asks for twice (chapters 02 and 06) and the one nothing
implements: no query, latency or empty-result rate is kept. `execution_time_ms` is
computed per response and thrown away with it.

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
| 7. Usage Analytics | — | **absent** (chapter 06's job) |
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
