# Knowledge Base — Filling It, and What Must Never Be Put In It

## State

The base ships **empty**, and one command fills it with the project's own
documentation — about 250 verifiable, citable passages:

```bash
GALSEN_STORAGE_BACKEND=sqlite python scripts/seed_knowledge.py
python scripts/seed_knowledge.py --etat        # what the base actually holds
```

Without `GALSEN_STORAGE_BACKEND=sqlite` the ingestion runs in memory and dies with the
process. The script says so at the end rather than letting it be discovered later.

## The rule that matters most

**Nothing is written into this base from memory.**

No agricultural, health or economic claim about Senegal was authored by a model and
stored here. Serving invented facts to a farmer or a health worker, under a platform that
presents them as knowledge, is the most damaging thing this repository could do. The
project's own rule — *an unfinished capability reports a status, it never returns a
plausible answer* — applies here with consequences outside the repository.

So the Senegalese corpus is built from **real documents**: official texts, research
institute publications, NGO guides, ministry circulars. They are declared, ingested, and
every passage keeps a link back to the document it came from.

## Adding a corpus

Write a manifest, then ingest it:

```yaml
# corpus/senegal-agriculture.yaml
documents:
  - path: sources/isra-guide-mil-2024.pdf
    title: "Guide de culture du mil"
    author: "ISRA — Institut sénégalais de recherches agricoles"
    url: "https://www.isra.sn/..."
    source_category: INSTITUTIONAL
    domain: OPERATIONAL
    scope: country:sn          # d'où cette connaissance vaut (VOLET 35, ADR-019)
    subject: agriculture       # de quoi elle parle
    tags: [agriculture, mil, senegal]
```

### Les deux axes : `scope` et `subject`

`scope` vaut `global` (le défaut) ou `country:xx`. `subject` prend une valeur
déclarée : `science`, `technology`, `engineering`, `health`, `economics`,
`history`, `culture`, `education`, `law`, `administration`, `agriculture`,
`fisheries`, `environment`, `geography`, `languages`, `business`, `society`,
`general`.

**Rien n'est deviné.** Une portée ou un sujet mal écrit **refuse le document** —
il n'entre pas en « mondial » ni en « non classé ». Un document sénégalais rangé
au mondial par charité deviendrait une réponse donnée au mauvais pays ; les
autres documents du manifeste s'ingèrent normalement, celui-là dit pourquoi il
ne s'ingère pas.

Trois sujets **ne retombent jamais sur le mondial** : `law`, `administration`,
`languages`. Pour eux, l'absence de source nationale se répond « je n'ai pas
cette information pour ce pays » — répondre le droit d'un autre pays serait
fluide, plausible, et faux là où ça coûte cher.

```bash
python scripts/seed_knowledge.py --manifeste corpus/senegal-agriculture.yaml
```

`path`, `title` and `source_category` are **required**. A document without declared
provenance is refused and the refusal is printed — that requirement is what separates a
knowledge base from a pile of text.

### Source categories, from most to least reliable

`OFFICIAL`, `GOVERNMENT`, `STANDARD`, `OFFICIAL_DOCUMENTATION`, `PEER_REVIEWED`,
`TRUSTED_DOCUMENTATION`, `INSTITUTIONAL`, `INDUSTRY`, `EXPERT_CONSENSUS`, `ESTIMATE`,
`OPINION`, `UNKNOWN`.

`retrieve_reliable()` uses them to decide what may support an answer. Declaring a blog
post as `GOVERNMENT` does not make it reliable — it makes the reliability report lie.

## What ingestion does

1. Reads the file (text and Markdown directly; richer formats through the document
   engine's loaders, which need their optional libraries).
2. **Chunks it** with `SimpleChunker` — 1000 characters, 200 of overlap. A whole document
   as one item cannot be cited usefully: a citation would point at fifty pages.
3. Attaches provenance to every chunk: title, author, URL, source category, file hash,
   and the passage number.
4. Stores it as **DRAFT**. Ingesting is not approving; the lifecycle exists to carry that
   decision. The project's own documentation is the exception — it enters `APPROVED`,
   because it is reviewed and versioned in the repository.

Re-ingesting the same file updates the same chunks instead of stacking duplicates: chunk
identity is derived from the file hash and the position.

## Citations

Every answer from `retrieve_reliable()` carries `sources` and `citation_coverage`:

```json
{
  "reliable": true,
  "sources": [{"title": "Guide de culture du mil", "author": "ISRA",
               "source_category": "institutional", "passages": ["…, passage 3/12"]}],
  "citation_coverage": {"items": 3, "with_source": 3, "coverage": 1.0}
}
```

A passage whose provenance cannot be established comes back with `known: false` and an
explanation, never under an invented title. A coverage below 1.0 means part of the answer
cannot be verified — which is exactly the thing worth knowing before acting on it.
