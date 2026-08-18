# VOLET 35 — An International AI With Senegalese Depth

Owner's brief, 2026-08-12: *"An international AI with a world-class knowledge
base and exceptional expertise in Senegal."* Senegal as a **strength and an
identity**, never a limitation.

This document is the architecture, the workflow and the phase plan. **No code
has been written for it yet** — that is the next turn, one chapter at a time.

---

## 1. What already exists — measured, not remembered

```python
>>> KnowledgeManagerImpl().search_knowledge("", limit=10000)
0 éléments
```

The engine is substantial and the base is **empty**. Nineteen modules exist
(`src/knowledge_engine/`): ingestion with manifests, chunking with provenance,
a lifecycle (DRAFT → REVIEWED → APPROVED), a twelve-level source-reliability
scale, citation coverage, governance, quality scoring, a knowledge graph.

| Asked by the brief | State |
|---|---|
| Provenance kept per passage | **present** — title, author, URL, file hash, passage number |
| Source credibility assessed | **present** — `SourceCategory`, twelve levels, used by `retrieve_reliable()` |
| Nothing written from memory | **present and enforced** — a document without declared provenance is refused |
| Organised by domain | **partial** — `KnowledgeDomain` classifies the *project* (business, technical, legal…), not the *world* |
| Organised by country | **absent** — nothing distinguishes global knowledge from Senegalese knowledge |
| Gap identification | **absent** |
| Source discovery and collection | **absent** — everything depends on the owner writing a manifest |
| Senegalese sources prioritised | **absent** |
| Health safety limits | **absent** |

**The structural gap is the geography.** Everything else is an extension of what
exists; the country axis does not exist at all, and the whole vision rests on it.

---

## 2. The architecture

### 2.1 Two axes, one base — not two bases

The temptation is a "global base" and a "Senegal base". **Refused**, for a
reason that will not change: a question about millet in Kaolack needs *both* —
the agronomy of pearl millet (global) and the rainfall, varieties and prices of
Senegal (local). Two bases would force the retriever to choose, and it would
choose wrong.

One base, every item carrying **two independent labels**:

```
scope     : GLOBAL | COUNTRY:<ISO-3166 alpha-2>        e.g. COUNTRY:SN
subject   : AGRICULTURE | HEALTH | LAW | HISTORY | …   (open to extension)
```

`KnowledgeDomain` stays as it is — it classifies documentation *about the
platform*, which is a different question, and merging the two would give one
enum with two meanings.

### 2.2 The retrieval rule

```
question → détection de portée → récupération → réponse qui dit d'où elle vient
```

| Question | What answers |
|---|---|
| "How does drip irrigation work?" | Global knowledge |
| "Quelles variétés de mil au Sénégal ?" | **Senegalese sources first**, global agronomy as background |
| "Quelle est la loi sur le foncier ?" | `COUNTRY:SN` **only** — a law is not portable, and answering with French law would be worse than not answering |

Three consequences, each a rule in code:

1. **Country-scoped subjects never fall back to global.** Law, administration,
   official statistics, national languages. For these, no Senegalese source
   means *"je n'ai pas cette information pour le Sénégal"* — never a global
   answer wearing a local coat.
2. **For everything else, local enriches, it does not replace.** The answer
   carries both, and says which passage came from where.
3. **The answer states its scope**, the way retrieval already states whether it
   was semantic or lexical (ADR-015). A reader must be able to see that an
   answer about Senegal was built from Senegalese sources — or that it was not.

### 2.3 The source registry

A declared, versioned list of authoritative sources, per country and subject —
the thing that turns "prioritise reliable sources" into something a machine can
apply.

```yaml
# corpus/sources/senegal.yaml
- name: "ANSD — Agence Nationale de la Statistique et de la Démographie"
  scope: COUNTRY:SN
  subjects: [economics, demography]
  category: GOVERNMENT
  base_url: https://www.ansd.sn
  licence: "à vérifier par document"
```

Reliability comes from the **registry**, not from the document that claims it.
`SourceCategory` already exists and is already used by `retrieve_reliable()`;
the registry is what maps a domain name to a category, so that declaring a blog
as `GOVERNMENT` becomes impossible rather than merely dishonest.

**The deny-list is part of the registry, and it is explicit**: unverified social
media, video platforms, anonymous content, content farms. An ingestion whose URL
matches the deny-list is refused **with its reason** — not silently down-ranked.

### 2.4 Health, and the limit the brief itself asks for

Health knowledge is ingested like the rest, and answered **differently**:

- only `OFFICIAL`, `GOVERNMENT` and `PEER_REVIEWED` sources may support a health
  answer — the general reliability threshold is not enough here;
- every health answer carries a safety notice and the instruction to consult a
  professional;
- **no diagnosis, no dosage, no prescription**, whatever the sources say. This
  is a refusal in code, not a phrase in a prompt: a model that has read the
  right document can still produce a dangerous sentence.

---

## 3. The acquisition workflow

The brief is explicit: the system must not depend on the owner handing over
documents. Six steps, each with a rule that keeps it honest.

```
1. constater le manque   → ce que la base ne couvre pas, mesuré
2. proposer des sources  → depuis le registre, jamais depuis une recherche libre
3. collecter             → sous approbation, licence vérifiée, robots.txt respecté
4. évaluer               → catégorie de source, fraîcheur, contradiction
5. organiser             → portée + sujet + provenance par passage
6. intégrer              → DRAFT ; l'approbation reste une décision humaine
```

**1. Gap detection is measured, not imagined.** A gap is a subject × scope pair
that real questions hit and the base cannot support with a reliable source. The
signal already exists: `citation_coverage` per answer, and the questions the
platform actually received. A gap nobody ever asked about is not a gap, it is a
guess about the future.

**2. Discovery proposes, it does not decide.** Candidate documents come from the
registry's declared domains. A source outside the registry can be *proposed*,
never used: adding an authority is a human decision, and it is the decision that
makes the registry worth having.

**3. Collection is gated and lawful.** Downloading is an outward action on
someone else's server: it goes through the approval gate (ADR-006), respects
`robots.txt`, records the licence, and refuses what it may not redistribute.
**A document whose licence is unknown is ingested as reference-only** — citable
by URL, not reproducible in full.

**4. Evaluation includes contradiction.** When a new document contradicts an
approved item on the same subject and scope, the conflict is **reported**, not
resolved automatically. The most recent source is not automatically the right
one, and silently overwriting a validated fact is how a knowledge base rots.

**5–6. Nothing enters APPROVED without a human.** The lifecycle already carries
this. Automation fills DRAFT; it never promotes.

---

## 4. What this VOLET refuses to do

- **No scraping of the open web into the base.** Collection is limited to the
  declared registry. "Search the internet and learn" is the fastest way to fill
  a knowledge base with confident nonsense, and this repository has already
  written the rule: *an unfinished capability reports a status; it never returns
  a plausible answer.*
- **No model-authored knowledge.** Not one passage. The rule from
  `docs/knowledge/README.md` holds without exception: serving invented facts to
  a farmer or a health worker is the most damaging thing this platform could do.
- **No "Senegal mode" toggle.** Scope is a property of the question and of the
  knowledge, not a switch someone flips.
- **No translated-and-forgotten corpus.** A French translation of a Wolof source
  keeps the original reference; the translation is a convenience, the source is
  the truth.

---

## 5. Chapters

| # | Chapter | Phases |
|---|---|---|
| 01 | Scope and subject axes: types, migration of existing items, retrieval unchanged | 2 |
| 02 | ADR-019 — one base, two axes, and why not two bases | 1 (indivisible) |
| 03 | The source registry: schema, Senegalese sources, deny-list, reliability mapping | 2 |
| 04 | Scope-aware retrieval: detection, local-first ranking, "no global fallback" subjects | 2 |
| 05 | The answer says its scope and its sources (extends ADR-015's honesty rule) | 1 |
| 06 | Gap detection, measured from real questions and citation coverage | 2 |
| 07 | Source discovery: proposes candidates from the registry, decides nothing | 1 |
| 08 | Gated collection: approval, licence, robots.txt, provenance | 2 |
| 09 | Contradiction detection between sources, reported never resolved | 1 |
| 10 | Health policy: source floor, safety notice, refusals in code | 2 |
| 11 | The first real Senegalese corpus, ingested and measured | 1 |
| 12 | Global corpus: subjects, sources, first ingestion | 1 |

**Total: 12 chapters → 18 phases.**

Chapters 01–05 make the platform *capable* of the vision. 06–09 make it
*autonomous* in filling itself. 10 makes it *safe* where it must be. 11–12 make
it *real* — and they are the only two that depend on documents the owner or a
partner must provide.

### The order is not negotiable at one point

**Chapter 01 comes first and alone.** Every later chapter reads the scope axis;
adding it after the corpus exists would mean re-labelling every passage by hand,
which is exactly the migration nobody ever finishes.

---

## 6. What the owner must provide, and when

| When | What | Why it cannot be automated |
|---|---|---|
| Chapter 03 | Validation of the Senegalese source list | Naming a national authority is a sovereign choice, not a technical one |
| Chapter 08 | Approval of the first collections | Downloading from someone's server, at scale, in the platform's name |
| Chapter 11 | Access to documents that are not public | Some ISRA, ANSD or ministry material is not on an open URL |

Everything else runs without you.

---

## 7. What would make this VOLET wrong

- **If real questions never mention Senegal**, the scope axis is complexity for
  nothing. Chapter 06 measures it: it counts what people actually ask.
- **If the source registry stays at ten entries**, discovery has nothing to
  propose and the acquisition loop is a shell. That is a content problem, and
  chapter 12 will say so plainly rather than let the code pretend.
- **If C1 stays open** — no model answers — none of this is visible to a user.
  The knowledge base would be excellent and unreachable. `ollama serve` remains
  the highest-value action available.
