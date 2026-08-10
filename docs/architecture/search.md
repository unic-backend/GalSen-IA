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
