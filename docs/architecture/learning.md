# Learning Engine

What VOLET_23 asks for, and what the platform actually learns from. Measured against the
repository on 2026-08-11.

---

## There is no learning engine, and none was built

The manual describes a ten-component engine — Learning Core, Experience Repository,
Feedback Engine, Pattern Recognition Engine, Model Improvement Engine, Reinforcement
Learning Module — over a twelve-stage lifecycle that includes model training,
learning validation and deployment.

None of it exists. Nothing was built here to make it look like it does, for the same reason
as VOLET 22's decision engine: an engine of that shape is a project, and standing one up
empty produces the failure `.claude/rules/verification.md` names — a capability that
reports plausible answers without doing the work. Stage 6 is *Model Training*, and exit
criterion **C1** is not met: no model provider is configured, so there is nothing to train
or retrain.

What plays the named roles today:

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| Experience Repository | `WorkflowHistory`, the audit engine | partial — bounded, process memory |
| Learning Analytics | `quality_report()`, `/analytics`, `metrics_snapshot()` | partial |
| Feedback Engine | the knowledge access counter | **the only feedback loop, and it was broken** |
| Learning Core, Pattern Recognition, Model Improvement, Reinforcement Learning | — | **absent** |

`consolidate_memory()` deserves a mention: it is the closest thing to "knowledge
adaptation" in the repository, and VOLET 07 made it raise `NotImplementedError` rather than
return a plausible result. That decision stands.

## The finding: the one feedback loop never worked, and I broke it further

The platform collects exactly one usage signal: how often a knowledge item is consulted.
It is not decorative — `KnowledgeRankerImpl` weights a `popularity` criterion computed from
it, so retrieval ordering depends on it.

`_increment_access_count()` read the item, incremented the counter and called
`store.update()`. But `update()` refuses a write whose version has not advanced, and the
counter did not advance it. The write was therefore always rejected. On the in-memory
store the increment survived anyway, by accident: `get()` returned the store's own object,
so the mutation had already landed. **On SQLite it never worked at all** — that store
deserialises on every read, so the mutation went to a copy and the rejected `update()`
discarded it.

Two consequences: the persistent backend had a permanently zero counter, and the ranker's
`popularity` criterion scored zero for every item, ranking nothing.

**And VOLET 21 made it worse.** Making `InMemoryKnowledgeStore.get()` return a copy — the
right fix for the cache-versus-store divergence — removed the aliasing this counter was
accidentally relying on. Measured before and after that change:

```
avant VOLET 21 (get rend la référence) : access_count = 5
après  VOLET 21 (get rend une copie)   : access_count = None
```

That is a regression I introduced, and it is what this VOLET's measurement caught. It did
not reveal a new bug so much as finish exposing an old one: the in-memory path had been
masking a defect that SQLite had all along.

### What it does now

`record_access(knowledge_id)` is an explicit store method, on the interface and both
implementations. It writes the counter **without touching the version**, because consulting
a knowledge item is not a new version of it — abusing the version to force the write would
have made every read produce a revision.

```
mémoire : access_count = 5 | version = 1
sqlite  : access_count = 5 | version = 1
```

Both backends now agree, which is the third time in this series that two implementations of
one interface were found disagreeing — notification `save()` in VOLET 13, knowledge `get()`
in VOLET 21, this counter here.

## What is not measured, and why

Chapter 03's lifecycle metrics — model accuracy, learning validation, pattern verification
— need a model and a ground truth, and the platform has neither. Chapter 01's capabilities
(reinforcement learning, cross-agent learning, behavioural optimisation) need an experience
store that survives a restart; the workflow history is bounded at 500 runs in process
memory (ADR-009), and whether to persist analytics data is already an open decision in
`docs/memory/pending-work.md`.

Nothing was invented to fill those. The one loop that exists now works on both backends,
and that is the whole of this VOLET's claim.

## Chapters 04 to 10

Management, security, compliance, monitoring, quality and governance describe an engine
that does not exist. What is real is documented elsewhere: audit trail, RBAC, retention,
`quality_report()` and its `unavailable` block. Chapters 08 and 10 are both titled
"Learning Engine Governance" and assign work to a board the project does not have.
