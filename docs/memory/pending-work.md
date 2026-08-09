# GalSen IA — Pending Work

The backlog, ranked P0–P3 with the criteria of VOLET_04 chapter 04. What each level
means and which criterion decided each item → `docs/roadmap/roadmap.md`, section
*Prioritising*.

Each entry names the criterion that put it where it is. An item ranked without a reason
gets re-argued at every review.

---

## P0 — Critical · nothing else is scheduled until these move

- **Decide whether the platform has users.** API keys map to roles, not to people: no
  account, no identity, no per-user data. Phase 2's workspace, Phase 3's collaboration
  and every adoption metric rest on this.
  *Deciding criterion:* strategic alignment — it gates more work than anything else in
  this file, and it is a decision, not a build. Needs an ADR first (VOLET_13).

- **Make generation provable end to end.** No provider is configured, so the platform's
  only real feature answers 503 and exit criterion C1 cannot be checked. The task is the
  test that runs when a key is present and skips otherwise — configuring a key is the
  operator's move, writing the proof is ours.
  *Deciding criterion:* user impact — without it the platform is a test suite, not a
  product.

## P1 — High · a Phase 2 exit criterion depends on it, or it removes a demonstrated risk

- **Put something in the knowledge base.** It holds **0 items, 0 indexed documents, 0
  graph nodes**, and `docs/knowledge/` does not exist. The Knowledge Engine, the RAG tool,
  the search service and the retrieval ranking are all built and retrieving from nothing.
  *Deciding criterion:* strategic alignment — the vision says to prioritise African data
  and use cases, and the Knowledge Leadership pillar has no evidence under it at all. No
  code is wrong, which is why no test caught this.

- **Deploy the platform somewhere reachable** (criterion C4). The Dockerfile, the compose
  file and CI exist; nobody has ever reached this API over a network.
  *Deciding criterion:* strategic alignment — nothing else on this list can be validated
  in production until this is true.

- **Log rotation and a metrics route** (criterion C5). `logs/application.log` is 6.5 MB
  with nothing capping it; the `metrics` tool works but nothing feeds it from request
  handling.
  *Deciding criterion:* performance impact and a demonstrated failure — the unbounded log
  already broke the monitor agent once.

- **A second workflow, with an end-to-end test** (criterion C3). One workflow named
  `standard` proves the loader, not the capability.
  *Deciding criterion:* business value — workflow automation is a Phase 2 item that is
  currently asserted rather than shown.

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

- **Speed up the orchestration suite.** `test_integration.py` takes **97 s**, of which
  three tests take 31 s each because the tester agent runs real suites inside the
  pipeline.
  *Deciding criterion:* performance impact on the development loop. Previously recorded
  as "~4 minutes", which was stale by a factor of two and distorted its rank.

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

- **Move the 27 root `test_*.py` files into `tests/`**, as `.claude/rules/testing.md`
  requires. They are collected and green; only their location differs.
  *Deciding criterion:* maintenance cost, low.

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
