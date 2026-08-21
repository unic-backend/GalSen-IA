# ADR-015: Embeddings Are a Local Provider, and Retrieval Says Which Path It Took

## Status
Accepted

## Date
2026-08-12

## Context

Every retrieval path in the platform is lexical. `MemoryRetriever` scores with **Jaccard
similarity over token sets** — the size of the intersection divided by the size of the
union. `KnowledgeSearchProvider` and `MemorySearchProvider` score by proportion of query
terms found.

That has a hard ceiling, and it is not a matter of tuning:

- *« Comment soigner le mil malade ? »* and *« traitement des maladies du sorgho »* share
  almost no tokens and are the same question for a farmer.
- French inflection, Wolof, and the code-switching people actually write in Senegal all
  break token equality.
- A score of zero is returned for a document that answers the question perfectly, because
  it uses other words.

`EmbeddingsTool` already exists (`src/tools/embeddings/tool.py`), is declared **enabled**
in `tools/tools.yaml`, and targets `sentence-transformers`. That library is **neither
installed nor declared** — the tool reports an error when called, which is honest, but the
catalogue advertises a capability nothing can serve. Phase 26.4 found it; this ADR decides
what to do about it.

## Decision

### 1. Embeddings are a provider, exactly like models

`src/embeddings/` defines an `EmbeddingProvider` interface and a registry, mirroring
ADR-003. The engine never imports a model library directly; it asks the registry for a
provider, and gets `None` when none is available.

This is not symmetry for its own sake. It is what lets the platform ship without
`sentence-transformers`, and gain semantic retrieval by installing one package — with no
call site changed.

### 2. Only local providers. No hosted embedding API. Ever.

A hosted embedding API would send **every stored memory and every indexed document** to a
third party — a larger and more continuous export than sending a prompt. ADR-014 already
rules that out for generation; it rules it out here a fortiori.

`SentenceTransformersEmbedder` runs the model in-process, on CPU, with no key and no
network at inference time. Default model:
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` — multilingual, covers
French, ~470 MB of weights on disk in its full form and ~90 MB in its quantised
distribution.

**The real price, stated rather than glossed over:** `sentence-transformers` pulls
**PyTorch**, which is ~200 MB (CPU wheel) to ~2.5 GB (CUDA). That is why it is *not* in
`requirements.txt`: an operator who wants semantic retrieval installs
`requirements-embeddings.txt` deliberately, and the production image stays as light as the
v0.1.0 release made it. Embedding a corpus is a one-off cost of roughly a few milliseconds
per short text on CPU; querying adds one encode per query.

### 3. No vector database yet — and the trigger is written

Vectors live in SQLite next to everything else (ADR-005), and similarity is a NumPy
dot product over normalised vectors. NumPy is **already a dependency**.

At the scale the knowledge base will have for a long time — thousands, not millions — a
brute-force cosine over a matrix in memory is on the order of a millisecond, and it needs
no service to run, secure, back up and monitor. **Trigger to revisit (Qdrant, ADR to
follow): more than ~100 000 vectors, or a p95 query latency above 100 ms.**

#### Amendment, 2026-08-20 — the code did not do what this section describes

The OSS ecosystem audit measured `SQLiteVectorStore.search()` against the design
written above and found they were not the same thing. "A brute-force cosine over
a matrix in memory" was accurate about the cosine and wrong about the matrix:
the matrix was **rebuilt on every query**, re-reading the table and re-parsing
every `values_json`. What the trigger condition was measuring, therefore, was
not the cost of similarity but the cost of JSON parsing.

Measured on a 4-CPU host, medians over 15 queries, before and after keeping the
matrix:

| Vectors | Before | After | p95 after |
|---:|---:|---:|---:|
| 271 *(today's corpus)* | 49.4 ms | **0.463 ms** | 0.627 ms |
| 10 000 | 1 856.8 ms | **0.830 ms** | 1.327 ms |

*(The audit measured 70.42 ms and 1 232 ms on the same untouched code. Two runs
on a shared host differ by about a factor of two; both numbers are stated rather
than averaged into one that neither run produced.)*

Two corrections to how the audit's finding should be read. It reported the p95
half of this trigger as "met at 271 vectors" on a measurement of **94.93 ms** —
which is below the 100 ms written here, not beyond it, though close enough that
a slower run crosses it. And the fix does not move the trigger: **it removes an
overhead that was never part of the decision**, so the 100 000-vector figure now
measures roughly what this section always claimed it did.

The matrix is cached per (collection, model) and validated by a version counter
written inside each write's transaction — not by an in-memory flag, because a
cache only its own process can invalidate serves a stale answer the moment
another writes. A collection above a declared ceiling is served **without**
cache rather than growing the process quietly, and `stats()` reports which.

### 4. Retrieval says which path it took

This is the part that matters most, and it is the project's rule applied to search: a
result must not be presentable as semantic when it was lexical.

Every retrieval answer carries the method used — `semantic`, `lexical`, or `hybrid` — and,
when semantic was unavailable, the reason. A caller who cannot tell the difference will
eventually build on the assumption that similarity is understood, and be wrong exactly
when it matters.

**Lexical retrieval is not removed.** It stays as the path taken when no embedder is
present, and as the complement when one is: exact terms — a variety name, a village name, a
reference number — are precisely what embeddings blur.

## Consequences

Positive:

- Semantic retrieval becomes an installation choice, not a rewrite.
- Memory, knowledge and search share one embedding path instead of three.
- Nothing leaves the machine, and the sovereignty of ADR-014 extends to retrieval.
- The vector store is the substrate VOLET 33 needs to *measure* a fine-tuned embedding
  model: retrieval hit-rate is the score that needs no human judgement.

Negative, and accepted:

- An operator who wants semantics installs ~200 MB+ of PyTorch. Deliberate, documented,
  and outside the production image by default.
- Two retrieval paths exist, so two behaviours must be understood. Mitigated by reporting
  which one ran, every time.
- Vectors are recomputed when the model changes. The store records the model name and
  dimension with every vector, so a mismatch is detected instead of silently comparing
  vectors from two different spaces.

## What this environment could and could not verify

Stated because the project's rules require it, and because a reader will otherwise assume
more was proven than was.

- **Verified here:** the provider interface, the SQLite vector store, cosine ranking,
  dimension-mismatch detection, the fallback to lexical retrieval, and the reporting of
  which path ran — all against a deterministic in-process embedder.
- **Not verified here:** `SentenceTransformersEmbedder` actually encoding text.
  `huggingface.co` answers **403** through this environment's proxy, so the weights cannot
  be fetched. The provider reports `MISSING_DEPENDENCY` and that reporting *is* tested.
  Whoever installs the package and runs the model closes this gap; until then it is open,
  and the platform says so rather than assuming.

## Alternatives considered

- **A hosted embedding API** (OpenAI, Cohere, Voyage). Rejected on sovereignty: it exports
  the entire corpus, continuously.
- **Keeping Jaccard and tuning it.** Stemming, synonyms and stop-word lists move the
  ceiling a little and cost real maintenance in every language served. The ceiling stays.
- **A vector database now.** Answered above: a service to operate for a corpus that
  currently holds zero items.
- **Hash-based or TF-IDF vectors as a stand-in.** They would let the code path exist
  without PyTorch — and they are not semantic. Naming them so would be the fabrication
  this project forbids; naming them honestly would leave the platform exactly where it is.
