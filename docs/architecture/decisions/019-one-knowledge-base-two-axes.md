# ADR-019: One Knowledge Base, Two Axes — Not a Global Base and a Senegalese One

## Status
**Accepted** — 2026-08-12. Implemented in `src/knowledge_engine/scope.py`
(VOLET 35, chapter 01).

## Date
2026-08-12

## Context

The owner's brief, 2026-08-12: *"An international AI with a world-class
knowledge base and exceptional expertise in Senegal."* Senegal as a **strength
and an identity**, never a limitation. The platform must answer a global
agriculture question with global knowledge, and a Senegalese one with validated
Senegalese knowledge and context.

### What existed, measured

```python
>>> KnowledgeManagerImpl().search_knowledge("", limit=10000)
0 éléments
```

Nineteen modules of knowledge engine, and an empty base. Provenance per passage,
a twelve-level source-reliability scale, a lifecycle, citation coverage — all
present. **Nothing anywhere distinguished where a piece of knowledge applies.**
`KnowledgeDomain` classifies documentation *about the platform* (business,
technical, legal); it says nothing about the world.

So the geography was not under-built. It did not exist.

## The decision

### 1. One base. Two independent axes.

```
scope   : global | country:sn        — where this knowledge holds
subject : agriculture, law, health…  — what it is about
```

### 2. Not two bases, and this is the load-bearing choice

The obvious design is a global base and a Senegalese one. **Refused.**

A question about millet in Kaolack needs both halves: the agronomy of pearl
millet, which is global, and the varieties, rainfall and prices of Senegal,
which are not. Two bases force the retriever to pick one before it knows what
the answer needs — and the failure is silent, because whichever base it picks
returns something.

One base with two labels lets a single query return both, and lets the answer
say which passage came from where. Splitting is always available later; merging
two bases that have drifted is not.

### 3. `KnowledgeDomain` is not touched

Two enums that both mean "domain" would be the duplication this repository has
paid for before. `domain` classifies the platform's own documentation; `subject`
classifies the world. They coexist because they answer different questions.

### 4. Nothing is guessed

A malformed scope or an unknown subject **refuses the write**. It does not fall
back to `global`, and it does not fall back to `unspecified`.

The reason is asymmetric cost. A Senegalese document silently filed as global
becomes an answer given to the wrong country; an unknown subject silently filed
as unclassified becomes knowledge nobody can find on the axis they will search.
Both are invisible failures, and this repository's rule is older than this ADR:
*an unfinished capability reports a status; it never returns a plausible answer.*

The default for an **undeclared** scope is `global` — never Senegal. Charity
toward the local corpus would corrupt exactly the corpus the project cares most
about.

### 5. Some subjects never fall back to global

`NATIONAL_SUBJECTS` — law, administration, national languages. For these, no
national source means *"I do not have this for this country"*. Answering a
Senegalese land-tenure question with French law would be fluent, plausible, and
wrong where it costs money. Chapter 04 enforces it; chapter 01 names it.

The list is deliberately short. Every entry buys a refusal to answer, and a long
list would turn an international AI into one that only answers about Senegal —
the opposite of the brief.

### 6. No ISO country registry is shipped

Scope validates the *shape* — two letters — and nothing else. Shipping an
incomplete country list would refuse valid countries, which is the hardest
defect to notice. A mistyped code stays visible another way: `scopes_report()`
surfaces it as a scope holding a single item, once the base is large enough for
that to mean something (twenty items; below it, one item per country is simply
a young base).

## Consequences

- `KnowledgeItem` gains `scope: str = "global"` and
  `subject: KnowledgeSubject = UNSPECIFIED`.
- The SQLite store gains two columns through the existing migration path. **A
  base written before this ADR reads back as global/unspecified**, verified by a
  test that builds the old schema by hand and opens it with today's store.
- Ingestion accepts both axes and resolves them *before reading the file*: a
  faulty scope must refuse the ingestion, not leave a hundred mislabelled chunks
  to hunt down afterwards.
- Manifests accept `scope:` and `subject:`; a faulty entry is refused
  document by document, with its reason, while the others ingest.
- Retrieval is **unchanged** by this chapter. Scope-aware ranking is chapter 04,
  and shipping ranking changes together with a schema change would make a
  regression impossible to attribute.

## Alternatives considered

| Option | Why not |
|---|---|
| Two separate bases | The retriever must choose before knowing what the answer needs, and the wrong choice returns something rather than nothing |
| A `senegal` boolean | Works for one country and blocks the "international AI" the brief asks for |
| Free-text country tags | `senegal`, `Senegal`, `SN`, `sn`, `sénégal` — five scopes for one country, and no query matches them all |
| Extending `KnowledgeDomain` | One enum with two meanings; owners and review cycles could no longer be assigned per domain |
| Scope inferred from content by a model | Knowledge labelled by inference is knowledge labelled by guess. The whole VOLET exists to avoid that |

## References

- `docs/roadmap/VOLET_35.md` — the architecture and the twelve chapters
- ADR-010 (ownership), ADR-015 (say which path answered), ADR-016 (a
  caller-declared field records a belief, not a fact)
- `docs/knowledge/README.md` — nothing is written into this base from memory
