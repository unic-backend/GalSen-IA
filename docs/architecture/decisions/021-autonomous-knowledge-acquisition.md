# ADR-021: Autonomous Knowledge Acquisition — Reopening a Capability That Was Deferred on a Circular Trigger

## Status

**Accepted** — 2026-08-13. Direction approved by the owner. Design:
`docs/architecture/senegal-knowledge-acquisition.md`. **No implementation exists yet**;
this ADR authorises it and bounds it.

## Date

2026-08-13

## Context

### What was measured

```
Senegalese documents in the knowledge base : 0
Senegalese sources declared in the registry : 9   (corpus/sources/senegal.yaml)
Automated acquisition                       : deferred
```

The knowledge base has shipped empty of Senegalese content since VOLET 28. The
repository's position, stated in `docs/knowledge/README.md` and enforced everywhere, is
that **nothing is written into the base from memory** — a corpus is built from real,
declared, citable documents. That rule is not in question here and is not weakened by
this ADR.

The implicit plan for satisfying it was: *a human declares documents in a manifest, and
the platform ingests them.* The ingestion side of that plan works, manifest included.
The human side never happened, and the owner has now stated why it cannot: **the founder
cannot manually collect Senegalese government, university, research-institute and
archival documents.** That is not a scheduling problem to be waited out.

### The defect this ADR exists to correct

`src/knowledge_engine/deferred_triggers.py` defers automated acquisition like this:

```python
{
  "capability": "automated_acquisition",
  "trigger":    "un corpus sénégalais existant qu'il faut tenir à jour",
  "measured":   senegalais,      # count of Senegalese knowledge items = 0
  "threshold":  1,
  "met":        bool(senegalais),
  "note":       "Le goulot n'est pas l'ingestion … Il est qu'aucun document
                 sénégalais n'est encore déclaré. Automatiser la collecte avant
                 d'avoir une source collecterait du vide, régulièrement."
}
```

**The trigger measures the result of the missing capability and uses it as the reason not
to build the capability.** Acquisition is gated on documents existing; documents exist
only if something acquires them. `met` could never become `True` by any path the
repository contained. VOLET 36 chapter H was written precisely to stop deferrals from
resting on prose instead of measurement — and this one is measured, which is why the
circularity is visible at all, but it measures the wrong quantity.

`src/knowledge_engine/collection.py` inherited the same premise and states it about
itself: *« Il ne va pas sur le réseau … l'acquisition automatisée est différée tant
qu'aucun corpus n'existe. »* It decides whether a collection is permissible — registry,
`robots.txt`, licence, human approval — and then does not collect.

### Why this needs an ADR rather than a commit

The project rule is explicit: *never contradict a written decision from memory; change
the decision first.* The deferral is written in code and repeated in three documents.
Writing an acquisition service without this record would leave the repository asserting
two contradictory things about itself, which is the failure mode the whole memory
discipline exists to prevent.

## Decision

### 1. Automated acquisition is no longer deferred, and its trigger is corrected

The trigger becomes a condition a path can actually satisfy:

> **A lawful, gated path exists by which a first document can be acquired** — the source
> is declared and enabled in the registry, `robots.txt` permits it, the licence status is
> established, and a human has approved the batch.

The old trigger is not merely replaced but **recorded as defective**, in the code and
here. A deferral whose trigger cannot fire is indistinguishable from a refusal, and
future deferrals must be checked against this failure: *does the thing I am measuring
depend on the capability I am deferring?*

### 2. Acquisition is a set of small services — not a crawler, and not a new agent

Six services (`fetcher`, `discovery`, `record`, `metadata`, `language`, `dedup`), each
independently testable, built on the existing registry, trust boundary, collection
decision, approval gate and ingestion. **Zero new agents**: `knowledge_architect` already
proposes a manifest entry in `DRAFT` and applies nothing.

Scope limits, binding:

- **Depth 1** from a declared entry point. No link-following from inside a fetched document.
- **Same-domain only.** A link off the registered domain is dropped, not queued.
- Five discovery modes enabled (curated, sitemap, declared index page, RSS/Atom, manual
  seeds). **Driving another site's search form is excluded** — at machine rate it is
  indistinguishable from the scraping this decision refuses.
- Per-run document ceiling, per-host rate limit, size ceiling, content-type allowlist.

### 3. The decision precedes the fetch, and two human gates bound the pilot

`collection.decide()` runs **before** any request leaves the machine. Deciding after
downloading makes the decision decorative.

The pilot (10–30 documents) is autonomy level **L0**: batch approval before fetching
(ADR-006), and human review of the manifest before ingesting. Both are mandatory, without
exception, for every source.

### 4. Autonomy is earned per source, granted by a human, revoked by the machine

Levels L0→L3 (`senegal-knowledge-acquisition.md` §13). Three properties are decided here,
not left to implementation:

- **Promotion is a reviewed commit.** The proactive scan may report that a source meets a
  level's criteria; it may not promote it. Automating promotion would make the level
  system self-widening, which removes every other guard at once.
- **Demotion is automatic**, on a changed `robots.txt`, a changed domain owner or
  certificate, any trust-boundary hit, or a quarantine rate above threshold. The
  asymmetry is deliberate: a false suspension costs a review, a false continuation costs
  the base's credibility.
- **There is no level at which a document enters the base with nobody able to see why.**
  Every auto-ingested item carries the conditions it satisfied and the values they were
  evaluated on, and is bulk-retractable by source and date.

`UNKNOWN` never takes the automatic branch. An undetermined licence, date, language or
authority is not "not an anomaly"; it is undecided, and undecided means a person.

### 5. Acquired content is `EXTERNAL` for life, and the registry is out of its reach

Every acquired document is wrapped at `TrustLevel.EXTERNAL` — data with an origin, never
an instruction — before any consumer reads it. Suspicious patterns quarantine the
document; they never delete it, because a legitimate document *about* prompt injection
would be destroyed by an auto-delete rule and an attempted attack would leave no evidence.

**No acquired content can alter the registry, the manifest, tool permissions, or any
`SYSTEM`/`DEVELOPER`/`USER` content.** The registry is a `DEVELOPER`-level file changed
only by a reviewed commit. This is the single most important line of this ADR.

### 6. Lawfulness is a precondition, not a setting

`robots.txt` fetched and applied; per-host rate limits; declared terms respected;
copyright respected; **no bypassing of technical protections and no authentication** — a
document behind a login is `REJECTED`, and the platform does not acquire an account for
this purpose. An unknown licence degrades to `reference_only` (citable by URL, quotable
in fragments, not republished whole) rather than blocking — the existing rule, unchanged.

### 7. The acquisition fetcher declares what it is

`src/tools/browser/tool.py` currently declares a `Chrome/91` user-agent it is not. That is
a false statement to every server it contacts, and it makes `robots.txt` compliance
meaningless — a site cannot apply a rule to an agent that disguises itself. The
acquisition fetcher declares a truthful identifier with a contact URL.

Whether `BrowserTool`'s own user-agent changes is **not** decided here: it has callers
that were not examined.

### 8. What stays deferred, with its trigger unchanged

Vector database, graph database, object storage for knowledge, and event queues remain
deferred. Their triggers in `deferred_triggers.py` are unaffected by this ADR and remain
unmet. Acquisition does not need any of them, and a pilot of 30 documents needs them less
than anything else in this repository.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| **Keep waiting for manually supplied documents** | It is the status quo, and it has produced 0 documents. The owner has stated it will not happen. Waiting is a decision with a cost, and the cost here is that the platform's Senegalese identity stays empty indefinitely. |
| **A general web crawler** | Solves a problem nobody has (breadth) and creates several nobody wants (legal exposure, load on institutional sites, provenance dilution, a large maintenance surface). The objective is proof of capability, not scale. |
| **Buy or import a third-party scraped dataset** | Provenance cannot be established after the fact. The registry rule — authority comes from the registry, never from the document claiming it — would be bypassed wholesale, and the resulting base would be exactly as trustworthy as a source we cannot name. |
| **Let a model write the Senegalese corpus** | Absolutely refused, and not a close call. Serving invented facts to a farmer or a health worker under a platform that presents them as knowledge is the most damaging thing this repository could do. |
| **Fetch first, evaluate afterwards** | Simpler to build and it inverts the gate: by the time the decision is made, the request has already been sent to someone else's server. |
| **One approval per document** | Thirty approvals get clicked through without being read. Batch approval per source and licence is a gate a person can actually exercise. |

## Consequences

### What becomes possible

- VOLET 35 chapters 11 and 12 — the first Senegalese corpus and the global corpus — stop
  being blocked on an action the owner cannot perform.
- The nine already-declared Senegalese institutions become reachable through a path with
  a decision, a gate and a record at every step.
- `automated_acquisition` gains a trigger that can be met, so the proactive scan starts
  reporting something actionable instead of a permanent 0.

### What gets harder, and must be accepted

- **The project starts touching third-party servers.** Until now it did not, and that was
  a real safety property. Rate limits, a truthful user-agent, `robots.txt` and a
  per-run ceiling are what replace it. They are weaker than "we never connect".
- **A legal surface appears**: terms of use, copyright, and the licence status of
  Senegalese official publications — which is **unknown** and, until read by a person,
  keeps everything at `reference_only`.
- **A fetcher is a maintenance burden.** Sites are rebuilt, sitemaps disappear, PDFs
  become scans. Some of the pilot will fail for reasons that have nothing to do with the
  code.
- **This ADR will be quoted to justify more than it says.** The scope limits in §2 exist
  to make widening them a visible diff rather than a re-reading of the word "acquisition".

### What does not change

Nothing enters without a source. Contradictions are reported, never resolved. `unknown`
is not `no`. Law, administration and languages never fall back to global knowledge. The
health policy applies whatever path the document arrived by. No test is weakened to make
an acquisition path look successful.

## What this ADR does not decide

- **The thresholds** of the autonomy levels (10, 30, 90 days, 10 %, 5 %). None was
  measured; the pilot measures them, and step 12 of the implementation order replaces
  them.
- **Whether the nine registered domains are reachable, publish sitemaps, or permit
  automated retrieval.** Deliberately unmeasured: the first outbound request happens
  under the approval this ADR authorises, not before it.
- **The licence of Senegalese official publications.** A person must read it.
- **Whether `BrowserTool`'s user-agent changes** (§7).
- **Whether the excluded subjects for auto-ingest are the right three** (health, law,
  administration).

## Revisit this ADR when

- The pilot completes and its measured numbers contradict the provisional thresholds.
- A source's terms of use forbid what this design permits — the terms win, and the source
  is disabled.
- A trust-boundary hit occurs on a real acquired document; the quarantine path will have
  been exercised for the first time, and what a reviewer actually needs will be known.
- Any proposal arrives to widen the scope limits of §2. Widening is a new decision, not
  an implementation detail.

## Notes

The general lesson is worth keeping separately from the specific decision: **a deferral
whose trigger depends on the deferred capability is a refusal wearing a measurement.**

The other four entries of `deferred_triggers.py` were re-read with that question in hand,
in this session. Result:

| Capability | Trigger | Verdict |
|---|---|---|
| `vector_database` | > 100 000 vectors to index | **Sound.** Knowledge items grow through an ingestion path that exists. |
| `graph_database` | > 100 000 entities **or** a traversal beyond depth 3 **or** a SQLite query over 200 ms | **Sound but half-unmeasured.** The entity count is measured; the other two clauses are not. `EntityStore.traverse()` raises `EntityRefused` above depth 3, so the demand *is* observable — as refusals — but nothing counts them. Not circular; incomplete. |
| `object_storage_for_knowledge` | A second instance or deployment | **Sound, unmeasurable here.** It is a fact about the deployment, not about this repository, and the report already says `measurable: false` rather than implying zero. |
| `event_streams` | An asynchronous consumer a direct call does not serve | **Sound, unmeasurable.** A consumer can appear without the queue existing. |

So the circularity was specific to `automated_acquisition`, not systemic. The one
follow-up it leaves is counting the depth-3 refusals, which is a small change and is not
part of this ADR.
