# GalSen IA — Pending Work

The backlog, ranked P0–P3 with the criteria of VOLET_04 chapter 04. What each level
means and which criterion decided each item → `docs/roadmap/roadmap.md`, section
*Prioritising*.

Each entry names the criterion that put it where it is. An item ranked without a reason
gets re-argued at every review.

---

## P0 — Critical · nothing else is scheduled until these move

- **Verify identities, or accept that nobody does.** ADR-010 closed C2, but stage 2 of
  the chapter's lifecycle is absent: whoever writes `GALSEN_API_KEYS` asserts who each key
  belongs to and nothing checks it. Fine while that person operates the platform; the
  trigger for a real directory is the day they do not.
  *Deciding criterion:* security implications — an unverified identity is still better
  than none, but the gap must not be forgotten once it stops being acceptable.

- **Configure a model provider.** The proof now exists
  (`tests/test_generation_end_to_end.py`): it skips while no provider answers and runs the
  moment one does. What remains is the operator's move, and the free path needs no money:
  `ollama serve` with a model whose context is **at least 8192** — a smaller one is
  refused by the selector, and the API now says so.
  *Deciding criterion:* user impact — this is the last step between a test suite and a
  product, and exit criterion C1 falls the same day.

## P1 — High · a Phase 2 exit criterion depends on it, or it removes a demonstrated risk

- **Put something in the knowledge base.** It holds **0 items, 0 indexed documents, 0
  graph nodes**, and `docs/knowledge/` does not exist. The Knowledge Engine, the RAG tool,
  the search service and the retrieval ranking are all built and retrieving from nothing.
  VOLET 05 added the surrounding discipline (domains, lifecycle, role-gated reads,
  governance and quality reports) — every one of those reports currently describes an
  empty base.
  *Deciding criterion:* strategic alignment — the vision says to prioritise African data
  and use cases, and the Knowledge Leadership pillar has no evidence under it at all. No
  code is wrong, which is why no test caught this.

- **Semantic search does not exist.** Only the keyword half is built, nothing analyses
  intent, and the ranking score is term overlap. VOLET 14 measured what it would take:
  `EmbeddingsTool` already turns text into vectors and **nothing indexes them** — this is
  a wiring and modelling job, not research. One of the five index types in the manual is
  built.
  *Deciding criterion:* user impact — retrieval quality caps out at exact term matching,
  which matters the day the base holds real documents, not before.

- **The query processor ignores accents and plurals.** `pluviometrie` finds nothing when
  `pluviométrie` is indexed, and `arachides` misses `arachide`; stop-words are French only.
  *Deciding criterion:* strategic alignment — unaccented typing is the norm on a Senegalese
  deployment, so this is a relevance defect before it is a linguistic one.

- **Three search sources of four have no provider** (memory, document, vision), and the
  per-source merge weights (1.0 / 0.9 / 0.85 / 0.8) come from no measurement. They are
  inert while one source is wired and will silently reorder results once a second is.
  *Deciding criterion:* maintenance cost — the numbers must be justified or removed before
  they matter.

- **Deploy the platform somewhere reachable** (criterion C4). The Dockerfile, the compose
  file and CI exist; nobody has ever reached this API over a network.
  *Deciding criterion:* strategic alignment — nothing else on this list can be validated
  in production until this is true.

- **Tag the first release.** `git tag` is empty while `release_check.py` expects `v0.1.0`
  and semantic versioning is already decided. A rollback target has to be nameable.
  *Deciding criterion:* maintenance cost — cheap, and criterion C4 needs it.

- **Cover the hosted-provider generation path with tests.** `_call_api` is implemented for
  OpenAI, Anthropic and Google; only the no-credentials branch is tested. A successful
  generation and the 401 / 400 / 429 responses are not.
  *Deciding criterion:* technical feasibility — untested vendor code is where a silent
  break hides, and this is the path C1 depends on.

- **Decide between three ways to write a file to disk.** `LocalDiskStorageConnector`
  (ADR-007), `SQLiteFileStore` and `FileSystemCloudStore` arrived from two branches, they
  overlap, and nothing says which one a caller should use.
  *Deciding criterion:* maintenance cost — three implementations of one job is the debt
  that compounds, and the decision framework's *"does it introduce unnecessary
  complexity?"* is already answered yes.

## P2 — Medium · real value, no criterion waits on it

- **Extend SQLite persistence (ADR-005) to the audit and approval engines.** The other
  five services already have their store.
  *Deciding criterion:* security implications — an audit trail that vanishes on restart
  is worthless for forensics. It stays P2 only because there is nothing to audit yet;
  **it becomes P1 the day C4 is met.**

- **Report connector health inside `/health`**, alongside the engines. An unconfigured
  connector must not make the platform unhealthy.
  *Deciding criterion:* user impact for an operator — one call should answer "what is
  wrong", not two.

- **Deployment documentation.** Pairs with C4: a deployment nobody can reproduce is a
  one-off.
  *Deciding criterion:* maintenance cost.

- **`_increment_access_count()` writes to the store on every search result**, which is now
  the dominant cost of a cached query (measured in VOLET 05 phase 5.2).
  *Deciding criterion:* performance impact — the read path writes, which also makes a
  read-only deployment impossible.

- **Validate agent outputs.** Chapter 02 of VOLET_06 lists "validate outputs" as a
  pipeline step and nothing implements it: no schema stands between an agent's dictionary
  and the aggregated response, and an empty pipeline returns `success` having run nothing.
  *Deciding criterion:* technical feasibility — the aggregator cannot report what it
  cannot check.

## P3 — Low · worth doing, nothing waits on it

- **Share the two subsystems that block a second instance** (ADR-009): key revocations,
  then rate-limit counters. Files, notifications and engine state are already cleared by
  `GALSEN_STORAGE_BACKEND=sqlite`.
  *Deciding criterion:* strategic alignment — but **this entry carries a trigger, not a
  date: it becomes P0 the moment a second instance runs.** A revoked key that still opens
  another instance is a security hole; it is only harmless while there is exactly one.

- **A calendar connector** (CalDAV or an API). The calendar tool answers `unavailable`
  until one exists.
  *Deciding criterion:* user impact — nobody uses the calendar tool today.

- **No linter, formatter or type checker is configured.** No `setup.cfg`,
  `pyproject.toml`, `.flake8` or pre-commit hook exists; the conventions in
  `.claude/rules/coding-conventions.md` hold because one author applies them, not because
  anything checks. Return type hints are the weakest at 88 % of functions.
  *Deciding criterion:* maintenance cost — the cost of adding one is low, and it only
  starts paying the day a second contributor arrives.

- **Review the model catalogue periodically.** Context windows and prices are declared in
  `src/model_engine/providers/*_provider.py` and drift as vendors change them.
  *Deciding criterion:* maintenance cost. This is a recurring review, not a task that
  completes — it belongs to the governance cycle (chapter 10).

- **Contribution guidelines.** The repository is public.
  *Deciding criterion:* business value, low while there is one contributor.

## Not ranked — the problem is not stated

- **"Create API / dataset / research templates".** The decision framework asks *"does it
  solve a real problem?"* and this entry does not say which. It stays here, unranked and
  unscheduled, until someone names the problem — deleting it would lose the intent, and
  ranking it would pretend the intent is understood.

---

## Notes
Move items to `completed-work.md` when they are finished.
`priorities.md` holds the current ranking of active work; this file holds everything that
is queued.
