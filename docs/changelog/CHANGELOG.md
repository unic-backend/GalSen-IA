# Changelog — GalSen IA

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.
This project follows Semantic Versioning; the version lives in `src/version.py` and
nowhere else. Versioning policy and release types → `docs/roadmap/roadmap.md`.

Nothing has been released yet: the platform is a **prototype** at `0.1.0`.

## [Unreleased]
### Fixed
- **VOLET 25 — every engine existed twice, and the two halves did not know about each
  other.** Measured state → `docs/architecture/enterprise.md`
  - Chapter 02's directive is one sentence: *every engine shall communicate through
    standardized enterprise interfaces*. That interface exists — `EngineRegistry`, which
    agents reach through `AgentContext` — and `server.py` did not use it. It built its own
    `MemoryManager`, `NotificationManagerImpl`, `KnowledgeManagerImpl` and seven more,
    while the registry built a second set for the agents. All ten were duplicated
  - The consequence was not theoretical: an agent raising an alert put it in one inbox and
    `/notification/list` read the other — **1 seen by agents, 0 seen by the API**. A memory
    written through the API was invisible to every agent
  - It went unnoticed because `GALSEN_STORAGE_BACKEND=sqlite` makes both copies open the
    same file, hiding the split. It only bit on the **default** in-memory configuration —
    the one every developer and every fresh deployment runs first
  - `server.py` now takes its engines from the shared registry. If the registry cannot
    build one — it constructs lazily and a missing dependency can fail — the API keeps its
    own copy rather than losing the route, and logs it: an announced duplication can be
    diagnosed, which is the whole difference with the one just removed
  - Nine and a half of the manual's twelve global components exist. The Decision and
    Learning engines stay absent on purpose — both are projects, both depend on exit
    criterion C1. Of the master directive's ten commitments, three are blocked not by code
    but by two operator actions: configure a provider (C1) and deploy (C4)
  - `VOLET_25.md` is the most damaged file of the series: chapter 07 appears twice,
    chapter 10 twice, and chapter 08 comes after the first chapter 10. Nothing was invented
    to reconcile it
  - 13 new tests; full suite 2 022 passing, 7 skipped

### Added
- **VOLET 24 — two storage backends no configuration could select.** Measured state →
  `docs/architecture/integration.md`
  - `FileSystemCloudStore` and `S3CloudStore` are implemented, exported and covered by
    tests, and `CloudManagerImpl` only ever built the in-memory or SQLite store. No
    environment variable reached them: a deployment could not choose them, only a caller
    injecting a store could, and nothing in the platform does. Two working integrations
    kept alive by their tests and unreachable by anyone deploying — while chapter 03 makes
    configuration stage 4 and deployment stage 5
  - `GALSEN_CLOUD_BACKEND` selects `in-memory` (default), `sqlite`, `filesystem` or `s3`,
    taking precedence over `GALSEN_STORAGE_BACKEND` for this service only, since
    `filesystem` and `s3` are meaningless for the other stores
  - The default did not change — making `filesystem` default would start writing to disk on
    deployments that never asked. An unknown value is reported, never guessed: reading
    `filesytem` as `filesystem` would write files somewhere other than where the operator
    believes. S3 construction imports boto3 lazily, so configuring it cannot break startup,
    and an unreachable bucket fails on upload with a real error instead of silently falling
    back to memory — a file "stored" in RAM is worse than the failure. An injected store
    still wins
  - The test writes through the filesystem backend and reads it back from a second manager:
    making a store reachable without checking that it stores would prove nothing
  - 8 new tests; full suite 2 009 passing, 7 skipped

### Fixed
- **VOLET 23 — the platform's only feedback loop never worked, and VOLET 21 finished
  breaking it.** Measured state → `docs/architecture/learning.md`
  - The knowledge access counter is not decorative: `KnowledgeRankerImpl` weights a
    `popularity` criterion computed from it. `_increment_access_count()` read the item,
    incremented the counter and called `update()` — which refuses a write whose version has
    not advanced, and the counter did not advance it. The write was always rejected
  - **It never worked on SQLite**, which deserialises on every read. In memory the
    increment survived only by accident, because `get()` returned the store's own object
  - **VOLET 21's fix removed that accident.** Making `get()` return a copy — the right fix
    for the cache-versus-store divergence — left the counter writing to a discarded copy.
    Measured: `access_count = 5` before, `None` after. That is a regression introduced in
    this session and caught by this VOLET's measurement; it finished exposing a defect the
    in-memory path had been masking all along
  - `record_access(knowledge_id)` is now an explicit store method on the interface and both
    implementations, writing the counter **without touching the version** — consulting an
    item is not a new version of it, and forcing the write through the version would make
    every read produce a revision. Both backends agree: `access_count = 5, version = 1`
  - Third time in this series that two implementations of one interface were found
    disagreeing: notification `save()` (VOLET 13), knowledge `get()` (VOLET 21), this
    counter
  - **No learning engine was built.** Ten components and twelve stages including model
    training, with exit criterion C1 unmet — there is nothing to train
  - 6 new tests; full suite 2 001 passing, 7 skipped

### Added
- **VOLET 22 — the one decision the platform takes was thrown away.** Measured state →
  `docs/architecture/decisions.md`
  - The manual describes an eleven-component Decision Engine over a fourteen-stage
    lifecycle. **None of it exists and none of it was built**: standing one up empty would
    produce exactly what `.claude/rules/verification.md` forbids. The AI-reasoning stages
    also depend on exit criterion C1, which is not met
  - `PlannerAgent` does decide: it detects intents and derives the agents a request needs.
    Measured on "surveille les logs de production" — **3 agents recommended, 9 executed**,
    the declared pipeline in full. Six agents run that the platform's own analysis said
    were unnecessary, including `tester`, measured at 96 % of request time in VOLET 19
  - Chapter 03 makes decision recording stage 10 and explainability a quality control; a
    decision taken and lost is neither. `src/router/decision_trace.py` compares the
    recommendation with the execution in the response metadata, with `applied: false`
    stated explicitly rather than left to inference, "the planner did not run" kept
    distinct from "it recommended nothing", and both directions of the gap reported
  - **Following the recommendation was deliberately not done** — it would change what every
    request executes. That is the P1 already recorded after VOLET 19, and this measurement
    sharpens it: the platform already computes which agents a request needs
  - The VOLET 06 guard forbidding any reader of `agents_required` failed, as designed. It
    was not weakened but tightened to its real intent — reading to *report* is allowed and
    named, reading to *decide* stays forbidden — and paired with a behavioural test
    asserting the trace leaves the executed set untouched
  - 7 new tests, 1 renamed and tightened; full suite 1 995 passing, 7 skipped

### Fixed
- **VOLET 21 — three views of one knowledge item gave two different answers.** Measured
  state → `docs/architecture/knowledge.md`
  - `KnowledgeStore.save()` refuses to overwrite when an equal-or-newer version exists
    under the id, and signals that refusal **by returning the id** — "created", "unchanged"
    and "rejected" are indistinguishable. `add_knowledge()` then cached the object it had
    been handed without checking whether the store took it. Measured, on a caller
    correcting a fact: `get_knowledge()` returned "… en juillet." while the store and
    search returned "… en juin."
  - The caller read back their own submission and had every reason to believe it was
    stored. Chapter 03 makes integrity validation and consistency verification two of its
    quality controls; a cache contradicting its store defeats both
  - `add_knowledge()` now indexes and caches **what the store holds**, re-read after the
    write, and warns with the id and the remedy when the submitted content was not kept
  - **A second defect, exposed by the test written for the first**: read → edit → bump
    version → `update_knowledge()` did not work on the in-memory store, because `get()`
    returned its internal reference, so incrementing the version on the object you read
    also incremented the stored one and `update()` refused the write. The SQLite store
    deserialises on every read and hands back a fresh object — two implementations of one
    interface disagreeing on what a read is, the same class of bug as the notification
    stores in VOLET 13. `get()` now returns a copy in both. `list_items()` deliberately
    still returns references, which several callers rely on
  - **Nothing was added for duplicate removal**: a knowledge id is its content hash, so the
    practice chapter 03 asks for is already met structurally. A `deduplicate()` here would
    have been code with no defect under it
  - 5 new tests; full suite 1 987 passing, 7 skipped

### Added
- **VOLET 20 — duplicates were detected and nothing could remove them.** Measured state →
  `docs/architecture/memory.md`
  - Chapter 03 lists "remove duplicate knowledge" among its management practices. Only
    detection existed: saving the same content three times produced three memories,
    `quality_report()` reported `redundant_items: 2`, **and retrieval returned all three** —
    the caller got the same answer three times and the agent's context filled with
    repetitions
  - `MemoryManager.deduplicate(user_id=None, dry_run=False)` groups active memories by
    owner and exact content, keeps the **oldest** (it carries the date the knowledge
    appeared) and **archives** the rest. Never deletes: nothing authorises erasing what a
    user saved on the grounds that they saved it twice. Same criterion as the report, or
    report and action would disagree. Idempotent, with a dry run
  - **A second defect surfaced while building it**: `quality_report()` counted duplicates
    across all statuses, so after deduplication it still reported two redundant items and
    an operator would have concluded the operation did nothing. The rate now covers active
    memories only — the set `deduplicate()` acts on — and says so with
    `"scope": "active_only"`
  - It is a method, not a schedule; no API route was added, since `quality_report()` has
    none either and shipping half the pair would be worse than neither
  - `VOLET_20.md` **has no chapter 02** — it runs 01, 01, then 03. Nothing was invented to
    fill the gap; VOLET 07's component inventory stands
  - 10 new tests; full suite 1 982 passing, 7 skipped
- **VOLET 19 — one agent ate 96 % of every request, and nothing said so.** Measured state
  → `docs/architecture/orchestration.md`
  - On the shipped `standard` pipeline, with the request "bonjour": total 45.2 s, of which
    **43.5 s in the `tester` agent**, which runs the project's full pytest suite before the
    platform answers — on **every** request, whatever it asks. The other eight agents come
    to 1.7 s combined
  - Only the total duration was recorded, so the cost existed but could not be attributed.
    Each agent's duration — retries included, because that is what the request actually
    waited for — is now stored with the run, and `stats()` aggregates it as `agent_time`
    with each agent's share. The share is computed over the **sum of agent durations**, not
    over request duration: what happens between two agents belongs to neither, and dividing
    by the total would invent idle time. Verified end to end at 96.3 %
  - **The fix itself was not taken here.** Moving `tester` out of the pipeline, making it a
    separate workflow, or scoping it to changed files are different enough decisions that
    picking one is not a phase's call. Recorded as **P1** in `pending-work.md` with the
    measurement
  - **No per-agent timeout was invented.** Nothing bounds an agent's execution and a
    hanging agent hangs the request, but Python cannot kill a thread: a
    `future.result(timeout=…)` would free the caller while the runaway agent keeps running
    and holding its resources — a timeout in appearance only. A real bound needs process
    isolation, which deserves an ADR
  - 6 new tests, 1 adapted; full suite 1 972 passing, 7 skipped

### Fixed
- **VOLET 18 — every workflow declared a version that nothing read.** Measured state →
  `docs/architecture/workflows.md`
  - `VOLET_18.md` is a **second Workflow Engine manual**, despite its folder being named
    "Infrastructure & DevOps Engine" — the same mismatch VOLET 17 had. Only what it asks
    beyond VOLET 08 was treated
  - `workflows.yaml` gives each workflow a `version` and `WorkflowValidator` requires it.
    Across `src/router/`, the string appeared exactly twice, both times the validator
    checking the field exists. Nothing read its value, and `WorkflowHistory.record()` did
    not store it
  - The consequence undid the metric VOLET 08 built: bump `1.0` to `1.1` and the history
    kept both runs under the same name, so the success rate mixed two definitions.
    "This workflow fails 30 % of the time" could not say which one
  - `WorkflowLoader.get_version()` reads it, every run records it, and `stats()` breaks the
    numbers down by version. The global rate is still served — it is not wrong, only
    insufficient. `unversioned` (the workflow declares none) and `unrecorded` (the caller
    did not pass one) stay distinct, because merging them would hide one
  - Verified end to end on the real registry: a run of the shipped `standard` workflow
    records `workflow_version: "1.0"`
  - **Failure analysis now names the agent** (chapter 06): `failed_agents: 3` says how
    many, never which. Runs record the failing agents' names and `stats()` ranks them; an
    agent retried three times in one run counts once
  - 11 new tests, 1 adapted — the guard locking the history's field set, which is exactly
    its job; full suite 1 966 passing, 7 skipped

### Added
- **VOLET 17 — Notification templates and a delivery report that does not flatter
  itself.** Measured state → `docs/architecture/notifications.md`
  - `VOLET_17.md` is a **second Notification Engine manual**, despite its folder being
    named "Agent Framework Engine". Only the three things it asks beyond VOLET 13 were
    treated; re-measuring the rest would have duplicated existing documentation
  - **Template Manager** (chapters 02 and 04) did not exist: every caller composed title
    and message by hand, so the same event announced itself differently depending on which
    part of the code reported it — and deduplication, which compares exact strings, could
    not bring those variants together. `src/services/notification/templates.py` adds a
    registry and `send_from_template()`. A missing parameter **sends nothing**, because a
    message with holes looks like a real alert and says nothing; the registry ships empty,
    because providing templates would fabricate messages nobody asked for; substitution
    goes through `string.Template`, not `str.format`, which accepts `{a.__class__}` and
    would hand out attribute access from a configuration-supplied template
  - **Delivery analytics** (chapters 06 and 09): the manual's three metrics — delivery
    success rate, queue latency, failed deliveries — do not apply to an internal inbox,
    where creating the notification *is* the delivery. Returning them would report a
    100 % that measures only that tautology, so they are named in an `unavailable` block.
    `delivery_report()` measures what happens **after** delivery instead: acknowledgement
    rate, age of the oldest unread (the signal an inbox is no longer read), and the most
    repeated incidents — the last only measurable thanks to VOLET 13's grouping. Served by
    `GET /notification/stats`
  - No retry mechanism: a send either lands in the store or raises. Retries become
    meaningful when an external channel exists, and the e-mail service is where delivery
    can genuinely fail
  - 18 new tests; full suite 1 955 passing, 7 skipped
- **VOLET 15 — API Gateway: a way to announce that a route is going away.** Decision →
  `docs/architecture/decisions/011-api-versioning-and-deprecation.md`, measured state →
  `docs/architecture/gateway.md`
  - Chapters 04 and 08 ask for version control and safe retirement of obsolete APIs.
    There was no version prefix, no negotiation header and no deprecation mechanism: the
    only available retirement was deletion, discovered as a 404 in production
  - ADR-011 deliberately does **not** add a `/v1` prefix. A version prefix is a promise of
    stability, and this platform is a prototype whose main capability answers 503 for lack
    of a provider. Deprecation is announced through RFC 8594 headers instead —
    `Deprecation`, `Sunset` only when a date is decided, `Link: rel="successor-version"`
    only when there is a replacement
  - Carried by a middleware, not a per-route dependency, so the notice covers **error
    responses too**: a caller who only ever hits a route in error is precisely the one who
    needs warning. Deprecated is not removed — the route keeps working and keeps its
    status code
  - `GET /api/versions` serves the version, the deprecation list, and an explicit
    statement that there is no URL versioning. **The registry is empty**, because no route
    is deprecated; registering a sample would fabricate a fact
  - `metrics_snapshot()` gains `throughput_rps` and `uptime_seconds` (chapter 06), and
    names the two key metrics it cannot produce: availability — a process cannot measure
    its own, a self-reported figure is always 100 % — and resource utilization
  - `tests/test_gateway_surface.py` locks the whole surface: of 63 routes, 59 require
    authentication and 62 pass the rate limiter, with 4 named exceptions. Verified the
    guard fails on an unprotected route

### Fixed
- **VOLET 15 — four routes handed the caller the inside of the machine on a 500.**
  Measured, with a search failing on a connection error, the response body carried an
  internal hostname, a port and a filesystem path. `erreur_interne()` now logs the
  exception with its traceback under an incident id and returns only that id — the cause
  changes recipient rather than being lost. Validation errors still answer 422 with the
  precise reason; only internal failures became opaque. A test reads `server.py` and fails
  if any route builds a 500 detail from an exception again
- **VOLET 13 — Notification Engine: the same alert five times produced five
  notifications.** Measured state → `docs/architecture/notifications.md`
  - Chapter 03 lists duplicate prevention among its quality controls and nothing applied
    it. A "disk full" alert repeating every minute buried the recipient's inbox — that
    is, the notifications they had **not yet read**
  - An identical, **unread** notification inside a configurable window (300 s) now
    increments `metadata["occurrences"]` and returns the **same identifier**.
    `created_at` never moves — it says when the problem started; `last_occurrence_at`
    carries the latest. A read notification is never grouped, and identity requires type,
    title, message **and** recipient, so two incidents never merge and two recipients each
    keep their own copy
  - **Lifecycle stage 9 (retention and secure deletion) did not exist.** `purge_expired()`
    deletes **read** notifications past the retention period (90 days by default);
    `include_unread` defaults to `False`, because deleting what nobody has seen decides on
    their behalf that it did not matter. It is a method, not a schedule — nothing calls it
    periodically, and that is stated rather than faked with a background task
  - **Two implementations of one contract, disagreeing.** Grouping wrote back via
    `store.save()`: the in-memory store **raises** on a known id, the SQLite store does
    `INSERT OR REPLACE`. The manager's `try/except` swallowed the exception, so in memory
    the mutation only landed because the object is shared by reference. `save()` keeps
    meaning **create**, and an explicit `update()` was added to `NotificationStore` and
    both stores; it returns `False` when the notification is gone, and the manager then
    counts nothing rather than counting into the void. Verified against **both** backends
  - 3 of 7 components exist. Absent: rules engine, channel connectors, delivery queue,
    user preferences. No placeholders
  - New: `GALSEN_NOTIFICATION_DEDUP_SECONDS`, `GALSEN_NOTIFICATION_RETENTION_DAYS`,
    documented in `.env.example` and validated at startup
  - 10 new tests; full suite 1 783 passing, 7 skipped
- **VOLET 12 — Communication Engine: "sent" named messages nobody received.** Measured
  state → `docs/architecture/communication.md`
  - With no SMTP configured, `send_email()` returned `success=True`, "Email envoyé à 1
    destinataire(s)" and stored the message as `sent` — **no server was ever contacted**.
    The default `NoopTransport` returned `(True, "")`, justified in a comment as
    "historically equivalent" behaviour: a lie preserved for compatibility
  - **Six tests asserted that lie**, including one requiring `(True, "")` from the
    transport that does nothing. `.claude/rules/verification.md` forbids exactly this —
    pinning a fabricated value makes the fabrication permanent. All six were rewritten to
    assert the real behaviour
  - The transport now says it sent nothing **and what to do about it**; the stored status
    becomes `failed`; `POST /email/send` answers **503, not 400** — a 400 accuses the
    caller of an error they did not make
  - **The composed message is still stored**: what a user wrote must not vanish because
    the infrastructure is missing. Only the status changed, because the status was lying
  - Notifications do not have this defect: they are an internal inbox, and creating one
    *is* the delivery
  - 7 new tests, 6 rewritten; full suite 1 773 passing, 7 skipped

### Added
- **VOLET 11 — Security Engine: counting is not detecting.** Measured state →
  `docs/architecture/security.md`
  - Twelve authentication attempts with **twelve different keys** from one source produced
    `failed: 12` and **no signal at all** — the platform knew attempts had failed, not who,
    when, or whether it was still happening
  - **`src/api/threat_detection.py`**: a sliding window of failures per source (10 in
    300 s, configurable), three severity levels, and `GET /security/threats`. Behavioural
    analytics, threat-intelligence correlation and machine-assisted analysis are **named in
    the response as unavailable**, with their reason
  - **A bypass found while building it**: the first version cleared a source's failures on
    successful authentication. End-to-end that returned **zero threats after twelve
    failures** — an attacker who finds a valid key erased their trail, and the operator
    reading the route erased what they came to see. Successes are now recorded beside
    failures with `succeeded_in_window`
  - A threat report names an **address**, never a key or its fingerprint; the route
    requires `ADMIN_AUDIT`; the detector is bounded at 1 000 sources
  - **Incident response** (chapter 06) has detection and severity; containment, eradication
    and recovery do not exist and are not simulated — auto-blocking an address needs an ADR
  - 18 new tests; full suite 1 766 passing, 7 skipped
- **VOLET 10 — Integration Engine: `/health` ignored the integration layer.** Measured
  state → `docs/architecture/integration.md`
  - The platform had two ways to answer "what is wrong" — `/health` for engines,
    `/connectors/status` for integrations — and nothing said so. `/health` now carries a
    `connectors` component (closes a P2 backlog entry)
  - **An unconfigured connector does not degrade anything**, which is the opposite of the
    intuition: most deployments configure none, and an endpoint that turns `degraded`
    because SMTP is absent is red permanently, therefore ignored. Only a connector that is
    configured *and* failing degrades the platform, and the component says so in a note
  - The check reads configuration and **contacts nobody**; `/connectors/status` remains the
    route that reaches out
  - **Five of seven components** exist; the message broker and synchronisation service are
    absent, and versioning and retirement are missing from the integration lifecycle
  - 6 new tests; full suite 1 748 passing, 7 skipped
- **VOLET 09 — Analytics Engine: collection existed, aggregation did not.** Measured state
  → `docs/architecture/analytics.md`
  - `src/` had no analytics package: the audit engine recorded events and `/metrics`
    counted traffic, and nothing turned either into an indicator
  - **`src/analytics/` is an aggregation layer, not a second collector** — a second count
    of the same executions would create two truths with no way to choose. It reuses audit
    events, `WorkflowHistory` and the `/metrics` snapshot without recomputing them
  - **`GET /analytics`** (`ADMIN_AUDIT`): per-agent executions, success rate and durations
    from audit; workflow success rate; traffic and search counters; source coverage
  - **An absent source returns `null`, never `0`** — zero reads as "no agent ran" when the
    truth is "nothing was measured"
  - **Four of the seven data sources** in chapter 04 are wired; memory, system logs and
    external integrations feed nothing, and `source_coverage()` says so at runtime
  - **Trends, anomaly detection and dashboards are named unavailable with their reason**:
    no time series survives a restart (ADR-009), so there is no baseline to compare against
  - No user request, subject or key fingerprint enters a report
  - 8 new tests; full suite 1 742 passing, 7 skipped

### Fixed
- **VOLET 08 — Workflow Engine: nothing validated a workflow.** Measured state →
  `docs/architecture/workflows.md`
  - A workflow citing **an agent that does not exist** loaded silently and failed halfway
    through; one with **no steps at all** returned `success` having executed nothing.
    `workflow_validator.py` separates blocking errors from warnings, and the engine now
    refuses to run a workflow that would produce a misleading result
  - **Three declarations configured nothing**: the root `execution:` block (the planner
    reads `execution` *inside* a workflow), the root `failure:` block (the code reads it
    from `config/settings.yaml`, where the key did not exist, so `max_attempts` and
    `rollback` always fell back to code defaults), and no workflow carried `version` or
    `owner`. The failure settings now live where they are read, the dead blocks are gone,
    and the metadata is in place
  - **Added `WorkflowHistory`**: execution history and the success rate chapter 09 asks
    for. Failures are recorded too — a rate that only observes successes is always 100 %.
    `success_rate` is `None` with no runs, never 0.0; the user's request is not stored;
    the history is bounded at 500 runs and says it dies with the process (ADR-009)
  - 19 new tests; full suite 1 734 passing, 7 skipped
- **VOLET 07 — Memory Engine: four declared rules that nothing applied.** Measured state →
  `docs/architecture/memory.md`
  - **"Forgetting" deleted permanently**: `forget_memory()` called `delete_memory()`, and
    the `ARCHIVED` status was never set by anything. It now archives; `delete_memory()`
    still erases
  - **Archiving would have changed nothing**: the retriever passed `status=None`, so an
    archived memory kept appearing in every search. It now considers `ACTIVE` only
  - **Expiry only applied if someone ran the cleaner**, and nothing runs it on a schedule.
    It is now honoured at read time
  - **`cleanup_expired()` reported deletions the cache undid** — it returned an exact count
    while the memory stayed readable from `item:{id}`
  - **`consolidate_memory()` returned 0**, indistinguishable from "nothing to consolidate".
    It now raises `NotImplementedError` naming the rules that do not exist
  - **Added** `quality_report()` and `list_inactive()`: freshness, per-owner duplicate rate,
    metadata completeness and status breakdown; retrieval accuracy and user satisfaction
    are named unavailable with their reason
  - 15 new tests
- **The `tester` agent reported suites it never ran.** It executed `python <suite>`, which
  only runs a file's `__main__` block — **20 of 92 suites have one**; the other 72 imported
  themselves, ran no test, exited 0 and were counted as passing. It now runs
  `python -m pytest`, and a suite collecting zero tests is no longer green
- **The `tester` agent is 2.5× faster**: one process per suite paid the platform's import
  92 times. A single batched pytest invocation pays it once — **97.4 s → 38.6 s** for 91
  suites — while keeping a per-suite verdict, since pytest names the file of each failure.
  A batch that fails or times out falls back to per-suite execution
- **The router announced parallel execution it never performed.** Its docstring claimed
  "supports parallel execution", the log printed a parallel plan, and no concurrency
  primitive exists in `src/router/` — the "parallel" agents were appended to the sequential
  list. The claims are corrected (`parallel_supported: False`); the behaviour is unchanged
  and the decision is now backed by measurement: `tester` is 97.4 s of a 99 s pipeline and
  the eight other agents total 1.66 s, so parallelism would buy ~1.5 s

### Added
- **VOLET 03 — Development Manual, 10 chapters in 12 phases.** Measured state →
  `docs/architecture/development.md`
  - **Performance targets** (`docs/standards/performance.md`): the oldest P1 in the
    backlog. Derived from same-day measurements, not round numbers — ≤ 50 ms for liveness,
    ≤ 200 ms for reads and search, ≤ 500 ms for writes, at p95. End-to-end latency is
    deliberately **not** targeted while nothing is deployed
  - **The fifth testing level** (`tests/test_performance_targets.py`), which was absent
    for a legitimate reason: without a declared target, a timing assertion is a number
    chosen to pass. It also asserts that search does not degrade with base size
  - **`release_check.py`** gains a ninth automated check and no longer leaves
    "performance targets verified" to a human
  - **Startup configuration validation** (`src/config/environment.py`): 11 variables that
    are present and unusable are reported with the consequence of ignoring each.
    `GALSEN_STORAGE_BACKEND=sqllite` used to fall back to in-memory storage silently
  - **Eight environment variables** read by the code and documented nowhere are now in
    `.env.example`, with a test that fails if another one goes missing
  - **Backward-compatible storage proved both ways** (`tests/test_storage_rollback.py`):
    an older reader on a newer base, a newer reader on an older base, and a full
    roll-back cycle that loses nothing
  - **Six of eighteen packages documented**: three had no docstring at all, three repeated
    their own name. Rewritten to the chapter's structure, known limitations included
  - 32 new tests; full suite 1 687 passing, 7 skipped

- **VOLET 14 — Search Engine, 10 chapters in 12 phases.** Full measured state →
  `docs/architecture/search.md`
  - **`POST /search` could not return a result**: no class implemented `SearchProvider`
    and nothing called `register_provider()`, so the route answered `total: 0` to every
    query — indistinguishable from an empty base. It now answers 503 with a reason while
    nothing is wired, and `KnowledgeSearchProvider` wires the knowledge source for real
  - **Searching does not grant reading**: `SearchQuery` carries the caller's role through
    the merge down to each provider
  - **Search analytics** (`record_search`): volume, per-source latency and empty-result
    rate in `/metrics`. Query *contents* are never recorded
  - **`GET /search/status`**: declared versus wired sources, their owner
    (`GALSEN_SEARCH_OWNERS`), index integrity and search counters. Precision, recall and
    user satisfaction are named as unmeasurable with their reason
  - **Index integrity** (`check_integrity`): missing, orphaned and stale documents, each
    with a test that provokes it
  - 33 new tests; full suite 1655 passing, 7 skipped

- **VOLET 05 — Knowledge Engine, 10 chapters in 12 phases.** The engine was built and the
  base was empty (0 items, 0 indexed terms, 0 graph nodes); the VOLET added the discipline
  around the content. Full measured state → `docs/architecture/knowledge.md`
  - **Organisation**: `KnowledgeDomain` (the chapter's 7 domains, closed), plus
    `KnowledgeSensitivity` and `KnowledgeStatus`. Both stores filter and persist them, and
    SQLite migrates an older base additively — pre-existing rows read as unclassified
    rather than guessed
  - **Lifecycle** (`knowledge_lifecycle.py`): review cannot be skipped, retirement is
    terminal, and every transition is a revision recorded with actor, reason and time.
    Rewriting content returns an item to `DRAFT`
  - **Retrieval policy**: archived and deprecated knowledge never feeds a reasoning path;
    `search_knowledge()` stays exhaustive for operators
  - **Query cache**: repeated searches went from 0.50 ms to 0.234 ms; every write drops
    the cached results, so nothing outlives the data it describes
  - **Security**: reads are gated by role against sensitivity — no role, empty role or
    unknown role reads public only, and filtering is silent
  - **Reports**: `GET /knowledge/governance` (owners per domain, orphan domains) and
    `GET /knowledge/quality` (completeness, freshness, duplicates, validation coverage).
    Accuracy rate and user feedback carry **no number** and are named as unavailable with
    their reason
  - 78 new tests; full suite 1622 passing, 7 skipped

### Changed
- **The 27 root `test_*.py` files now live in `tests/`**, as `.claude/rules/testing.md`
  requires. The move broke 20 path expressions that computed the repository root as
  `dirname(__file__)`; all were rewritten, and `tests/test_project_structure.py` now fails
  if a test file reappears at the root or points `sys.path` at its own directory
- **The debt register in `docs/roadmap/roadmap.md` was re-measured**: four of nine debts
  are paid, three were missing, and the orchestration suite grew from 97 s to 105 s
### Fixed
- **Two silent truncations at 10 000 items.** `count()` returned the length of
  `list_items(limit=10000)` in both knowledge stores, so a store holding 10 050 items
  reported 10 000 with nothing able to detect it; `_rebuild_index()` read the same bound,
  leaving every document past it **unindexed and unfindable without any signal**. Counting
  is now real (`len`, `SELECT COUNT(*)`), the index bound is a named constant shared with
  the integrity check, and reaching it is logged and reported as `truncated`
- **OpenAI-compatible provider** (`src/model_engine/providers/openai_compatible_provider.py`)
  — one provider for every service speaking `/v1/models` and
  `/v1/chat/completions`: vLLM, LM Studio, llama.cpp, LocalAI, OpenRouter, Groq,
  Together, or a rented GPU server. Moving a model from a laptop to a server to
  a host costs **no code**: only `GALSEN_OPENAI_COMPATIBLE_URL` changes
  - the key is optional — a local server asks for none, and `HostedProvider`
    refuses to work without credentials, which is why this is a distinct class
  - the catalogue is **discovered**, not declared: a hard-coded list would lie
    the moment the operator swaps models
  - inactive until the URL is declared; it never guesses an address
  - HTTP codes become distinct reasons — 401 asks for a key, 429 asks to wait,
    and confusing them leaves the operator without a lead
  - `tests/test_openai_compatible_provider.py`: 20 tests against a real HTTP
    server speaking the protocol
- **Exit criterion C3 met — a second workflow, executed**. `workflows/workflows.yaml`
  declares `revue` (`reviewer` then `security`), which runs the full pipeline in
  0.2 s and produces real output: 40 files reviewed, 26 findings, 0 security
  issues. It carries its own `execution` block, which is what lets two workflows
  use different strategies. `tests/test_workflow_revue.py`: 12 tests, and they
  never execute `standard` — it contains `tester`, which would run the suite
  inside the suite
- **Exit criterion C5 met — the log is bounded.** `RotatingFileHandler` replaces
  `logging.FileHandler`: 5 MB × 3 archives, so 20 MB maximum instead of the
  6.7 MB and 43 638 lines it had reached with nothing capping it.
  `GALSEN_LOG_MAX_BYTES` and `GALSEN_LOG_BACKUP_COUNT` adjust it; an unreadable
  value falls back to the default rather than reopening unbounded growth.
  `tests/test_log_rotation.py`: 18 tests, which write enough to trigger several
  rotations rather than inspecting the handler's type
- **Identity (VOLET 16, ADR-010)** — a key belongs to a subject
  - `GALSEN_API_KEYS` gains an optional third field: `secret:role:subject`.
    `RBACContext` carries `subject`; a key without one is anonymous, so no
    existing deployment breaks
  - `GET /auth/whoami` tells a caller who they are — a misattributed key was
    otherwise discovered by reading audit traces, too late
  - `GET /metrics` reports the authentication success rate (`auth.attempts`,
    `succeeded`, `failed`, `success_rate`), the metric VOLET 16 ch. 06 and 09
    both ask for. The counters name no subject: per-person counting would turn
    an operational measurement into individual tracking
  - `docs/architecture/identity.md`: what the manual asks, what exists, and what
    is deliberately absent with the trigger for each
  - No credential store, and none planned before self-service signup. The
    platform still holds no secret of its own

### Security
- **Exit criterion C2 met — data belongs to its subject.** Three stores leaked
  the same way and now enforce ownership:
  - `/memory/store` and `/file/upload` took their owner from the request body,
    so any key holder could write in someone else's name. The owner is now the
    authenticated subject; an administrator may still name another
  - `/memory/retrieve`, `/file/{id}`: another subject's data answers **404, not
    403** — a 403 confirms an id exists and belongs to somebody, which is enough
    to enumerate it. A test asserts refusal and absence are indistinguishable
  - `/memory/search`, `/file/list`, `/notification/list` filter by subject, and
    an explicit filter naming someone else is not honoured
  - `/notification/mark-all-read` accepted an arbitrary recipient: any key
    holder could empty another subject's inbox
  - Notifications are constrained on **reading**, not writing — `recipient` is
    the addressee, and sending to someone else stays legitimate, which is what
    the approval engine does when it asks an operator to decide
- **Proof for exit criterion C1** (`tests/test_generation_end_to_end.py`) — the
  end-to-end generation tests skip with an actionable reason while no provider
  answers, and run unchanged the moment one does. The "runs" path is covered too:
  a stub HTTP server speaking Ollama's protocol drives tool → manager → selector
  → provider → HTTP, so the file cannot silently become vacuous
- **`GET /metrics` (VOLET 04 ch. 09, half of exit criterion C5)** — request count,
  error rate and per-route latency. `/health` answers what is configured; this
  answers what is happening. It feeds the `metrics` tool that already existed and
  that nothing had ever called, rather than adding a second mechanism
  - series are named by route template, so a URL scan cannot grow the collector
  - a failed measurement never fails the measured request
  - requires a key (read-only is enough); `/health` stays open
  - the reading does not count itself, and the response states `scope: "instance"`
  - `tests/test_api_metrics.py`: 12 tests
- **Versioning and release procedure (VOLET 04 ch. 03)**
  - `src/version.py` is the single source for the version and the release type.
    The application imports it; the Dockerfile redeclares it as
    `ARG GALSEN_VERSION` and `tests/test_version.py` fails if the two drift
  - `scripts/release_check.py`: eight executable checks (version, git tag,
    working tree, tracked secrets, changelog, documentation, startup, test
    suite), non-zero exit when one blocks. The two requirements needing
    judgement — features complete, performance targets verified — are printed
    and never ticked automatically
  - The release type is recorded as `prototype`; the series stays `0.x` while it
    is prototype, alpha or beta, and a stable label is refused while `/health`
    does not report healthy
- **Scaling posture made explicit (VOLET 02 ch. 10, ADR-009)** — closes VOLET 02
  - `src/api/scaling.py`: inventory of every subsystem holding state, with where
    it lives, what a second instance would do to it, and whether that is a loss
    of correctness or harmless duplication. Recomputed on each call so a change
    of `GALSEN_STORAGE_BACKEND` is reflected instead of frozen at import
  - `/health` carries a `scaling` section: instance identity,
    `multi_instance_ready` verdict and the names of the blocking subsystems
  - `POST /auth/keys/{fingerprint}/revoke`, `/restore` and `GET /auth/keys` now
    state `scope: "instance"` — a revoked key keeps opening any other instance,
    and an operator responding to a compromise must not learn that afterwards
  - `GALSEN_INSTANCE_ID` names an instance; unset, `<host>:<pid>` is used
  - `tests/test_scaling.py`: 20 tests, including a demonstration that a key
    revoked on one manager still authenticates on another

- **Conseil Agricole page on `/ui`** (ADR-008) — `api.agri.conseil()` in the API
  client, a full-width section rendered with `textContent`, line breaks
  preserved. `tests/test_web_agri.py` (18 tests) replaces the removed
  `tests/test_dashboard_agri.py`
- `tests/test_import_convention.py` — walks every module under `src/` and fails
  on the first internal import written without the `src.` prefix, and on any
  logic in `src/__init__.py`. The convention had been broken twice, both times
  invisibly, because the tests imported by the bare name too

### Changed
- Two development lines reconciled. `src/frontend/` (Jinja2, mounted on
  `/admin`) is removed: ADR-008 stands, and its page was rebuilt on `/ui`
- `src/api/scaling.py` derives the scope of files and notifications from
  `GALSEN_STORAGE_BACKEND` instead of declaring them process-local. Under
  `sqlite`, only key revocations and rate-limit counters still block a second
  instance
- `data/` is no longer tracked; five `*.sqlite` databases and
  `.claude/settings.json.bak` were removed from version control

### Fixed
- **A reachable provider with a too-small model gave a dead-end message.** With
  Ollama running and a 4096-context model, `/agri/advice` answered 503 with
  "Aucun modèle sélectionnable" — the real reason (minimum context 8192) was
  logged by `select_model_for_task()` and thrown away, and
  `unavailability_reason()` only knew how to report "no provider at all". The
  manager now keeps the selector's reason and returns it, clearing it on every
  new selection so a stale explanation cannot outlive the configuration that
  fixed it. This is the most likely local failure and it said nothing useful
- **`POST /agri/advice` answered 200 with an empty answer** when no model
  provider is configured: only exceptions were translated to 503, and the tool
  reports unavailability as a status. Any non-`ready` status now yields 503
  carrying the tool's own detail
- **The `src.` import convention was broken again** by the five services merged
  from the parallel branch, and hidden by `src/__init__.py` inserting `src/`
  into `sys.path`. The same file was importable under two names, so Python
  built two distinct classes and `isinstance` failed. Ten modules and six test
  files converted; `src/__init__.py` emptied of logic
- Three dashboard rendering defects, all found by driving a real browser and
  invisible to HTTP tests: identifiers broken mid-word, a table column silently
  cut off, and overlapping column headers
- `tests/test_api_startup.py`: seven integration tests that actually boot the
  application (`with TestClient(app)`), covering the lifespan, the late binding
  of the tool engine into the health checker, resilience to a broken tool engine
  and a real end-to-end tool execution. No test booted the app before, which is
  why the two startup defects above went unnoticed
- **Backend services test coverage (VOLET 02 Phase 2)**
  - `tests/test_services.py` extended from 93 to 135 unit tests: notification
    serialization edge cases (`read_at`, omitted optional fields, enum instances
    in `from_mapping`), advanced store filters (`min_priority`, role, tags,
    content type), search source weighting, offset pagination, `DATE_ASC` sort,
    provider-query construction and single-source failures, file base64
    round-trip and best-effort failure handling of `FileManagerImpl`
  - `src/services/` statement coverage raised from 92% to 99%

### Fixed
- **The API could not start.** `uvicorn src.api.server:app` — the command the
  Dockerfile runs — failed with `ModuleNotFoundError: No module named 'storage'`
  because `memory_manager.py`, the three `src/storage/sqlite_*_store.py` modules
  and the deferred imports in `knowledge_manager.py` / `model_manager.py` used
  top-level absolute imports assuming `src/` was on `sys.path`. Every import
  inside `src/` now uses the single `src.<module>` convention, which also fixes
  the duplicate-module identity bug (two distinct `MemoryPriority` classes)
- **The startup handler was dead code.** `startup_event()` called
  `tool_loader.load_tools()`, `ToolEngine(tools)` and
  `tool_engine.set_executor()` — none of which exist. It now builds the engine
  from the registry path and logs a failure instead of taking the API down
- **`/tool/execute` never worked**: it called `tool_engine.execute()` (absent —
  the method is `execute_tool()`) and passed `config` as a positional dict, so
  the tool never received its options
- `ToolLoader.get_tool_class()` no longer swallows `ImportError` /
  `AttributeError` silently; the cause is logged. All 20 tools in
  `tools/tools.yaml` now load
- `test_embeddings_tool.py`: the three tests that patch `sentence_transformers`
  are now skipped when that optional dependency is absent, so the suite is green
  out of the box. The behaviour without the dependency stays covered by
  `test_embeddings_tool_missing_sentence_transformer`
- `requirements.txt` now declares two dependencies the code already required:
  `opencv-python-headless` (imported at module level by four
  `src/vision_intelligence_engine/` modules — without it the `vision` engine is
  unavailable in the registry) and `httpx` (required by
  `starlette.testclient.TestClient`, without which four API test files cannot be
  collected)
- Three pre-existing `NameError` failures that prevented the full pytest suite
  from being collected: missing `Optional` import in
  `src/memory_engine/memory_summarizer.py` and
  `src/vision_intelligence_engine/vision_analyzer.py`, and a forward reference to
  `ColorAnalyzer` in `src/vision_intelligence_engine/interfaces.py` (now a string
  annotation)

### Added
- **Priorité #7 — Conseil Agricole (première feature réelle)** : outil
  `AgriAdviceTool` réparé (passage à l'API synchrone `select_model_for_task()` +
  `generate()`, corrigeait un bug d'appel de coroutine asynchrone et une méthode
  inexistante), endpoint `POST /agri/advice` dans `src/api/server.py` (question
  agricole en fr/wo, options model_id/max_tokens, protégé par RBAC
  `model:generate`), 17 tests unitaires dans `tests/test_agri_advice.py` — tous
  verts. Génération réelle vérifiée via Ollama (qwen2.5-coder:14b).
- **Credentials providers (ADR-004)** : `_call_api` implémenté pour OpenAI,
  Anthropic et Google (stdlib urllib, zéro dépendance). Lecture des clés via
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`. Correctifs : imports
  manquants dans `openai_provider.py` et `google_provider.py`, enum `UNAUTHORIZED`,
  commentaires arabes → français. 24 tests unitaires — tous verts.
- **Stockage persistant complet (ADR-005)** : 8 stores SQLite pour Memory, Model,
  Knowledge, Notification, Calendar, Email, Cloud, File. 92 tests — tous verts.
  Backend sélectionnable via `GALSEN_STORAGE_BACKEND=sqlite` ou injection. Correctif
  `:memory:` mode sur `SQLiteFileStore` (connexion persistante).
- **Connecteur S3/Minio + FileSystem pour le service Cloud** : `S3CloudStore` (`src/services/cloud/store_s3.py`) avec upload/download via boto3 (lazy import, configuration par variables d'environnement `CLOUD_S3_*`). `FileSystemCloudStore` (`src/services/cloud/store_fs.py`) pour un stockage persistant local zéro dépendance (index JSON + fichiers binaires). 19 nouveaux tests. **185 tests pour les 3 services externes — tous verts**.
- **Connecteur SMTP pour le service Email** : `SmtpTransport` (`src/services/email/transport.py`) avec support STARTTLS et SSL, configuration par variables d'environnement, construction MIME complète. `ConsoleTransport` et `NoopTransport`. 18 nouveaux tests.
- **Dashboard web (`src/frontend/`)** : 5 templates Jinja2 (base, accueil, santé, services, modèles, mémoire), monté comme sous-application FastAPI sur `/admin` dans `src/api/server.py`. Interface sombre avec sidebar et badges de statut.
- **SDK Client Python (`src/client/`)** : Client REST sans dépendances externes (stdlib `urllib`), couvrant tous les endpoints (santé, mémoire, modèles, notifications, fichiers, cloud, calendrier, email). Retourne des objets Pydantic, pattern best-effort (pas d'exception levée). **48 tests — tous verts**.
- **VOLET 02 Phase 2 — Services Backend (Ch. 03, 07, 09)**
  - **Notification Service** (`src/services/notification/`): types.py, interfaces.py, store.py, manager.py. 8 types de notification (info, warning, error, approval_request, approval_decided, system, task_completed, task_failed), 4 niveaux de priorité, stockage en mémoire thread-safe avec filtres (type, destinataire, rôle, priorité minimale), marquage de lecture individuel et groupé, statistiques agrégées
  - **Search Service** (`src/services/search/`): types.py, interfaces.py, manager.py. Recherche unifiée multi-source (knowledge, memory, document, vision) avec fusion pondérée par source, tri par pertinence/date, filtrage par score minimum. Architecture extensible : tout moteur implémentant `SearchProvider` peut être branché
  - **File Service** (`src/services/file/`): types.py, interfaces.py, store.py, manager.py. Upload avec validation (taille max 10 Mo, nom requis, contenu non vide), mapping automatique type MIME → catégorie (12 catégories), stockage mémoire thread-safe, mise à jour des métadonnées, statistiques par catégorie/type
  - **Integration EngineRegistry** : 3 nouveaux moteurs (notification, search, file) dans ENGINE_NAMES avec builders lazy, propriétés et availability()
  - **API REST** : 14 nouveaux endpoints — notification (POST /notification/send, POST /notification/list, POST /notification/mark-read, POST /notification/mark-all-read, GET /notification/stats, DELETE /notification/{id}), search (POST /search), file (POST /file/upload, GET /file/{id}, POST /file/list, GET /file/stats, DELETE /file/{id})
  - **Tests** : 93 tests unitaires dans `tests/test_services.py` couvrant les 3 services (types, store, manager, cas d'échec, résilience aux pannes store)
- **Phase 4 — Generalized Persistence (VOLET_01, chapitre 03, PERSISTENCE; ADR-005)**
  - `SQLiteModelStore` (`src/storage/sqlite_model_store.py`): replicates the
    `InMemoryModelStore` semantics (same filters, same `updated_at` descending
    sort, same limit) with a verbatim Python filter loop over `list_items`
    (`rowid` order = insertion order); serialization through
    `ModelItem.to_dict()/from_dict()`; `RLock` + `PRAGMA busy_timeout = 5000`;
    `cleanup_expired()` removes DEPRECATED models
  - `SQLiteKnowledgeStore` (`src/storage/sqlite_knowledge_store.py`): 26 columns
    covering the Phase 1 reliability hierarchy (source_category, priority,
    confidence, citation, retrieved_at…); enums serialized as `.value`, datetimes
    as `isoformat()`, lists/dicts as JSON; `list_items` faithfully replicates the
    in-memory filter loop; `cleanup_old_versions()` returns 0 (one version per ID)
  - Configurable data directory: `GALSEN_DATA_DIR` (default `"data"`) resolved by
    `src/storage/paths.py` → `default_sqlite_path(filename)`; backend selected by
    `GALSEN_STORAGE_BACKEND` ("in-memory" by default, "sqlite" for durability)
  - Engine wiring via environment-variable dependency injection in
    `ModelManagerImpl` and `KnowledgeManagerImpl`: injected store wins → else
    sqlite env var → else in-memory store. Deferred **absolute** imports
    (`from storage.sqlite_*_store import ...`) inside `__init__` (avoids the
    circular import AND stays compatible with the project's top-level package
    convention)
  - Fixed `InMemoryKnowledgeIndexer._rebuild_index()`: it accessed the in-memory
    store's private `_data` dict (crashed with `AttributeError` on a SQLite
    store) → now uses the public `list_items()` interface. The index (a derived
    structure) is still rebuilt in memory at manager construction
  - Concurrency: per-instance `RLock` + `PRAGMA busy_timeout = 5000`; shared
    `:memory:` base via `cache=shared` for test isolation
  - `tests/test_storage_engines.py`: 43 unit tests covering CRUD, version
    semantics, filters, cleanup, persistence across reopen, `:memory:`,
    serialization round-trips (enums, dates, JSON, priority) and engine backend
    selection (env var + explicit injection + `GALSEN_DATA_DIR`)
  - Aligned `src/memory_engine/memory_manager.py` with the project convention:
    the module-level relative import `from ..storage.sqlite_store import
    SQLiteMemoryStore` became the absolute `from storage.sqlite_store import
    SQLiteMemoryStore` — the last remaining `..storage` relative import in an
    engine manager (same bug class fixed in Model/Knowledge managers); memory
    and storage tests still pass (96 tests)
- **Phase 3 — Human Approval Gate (VOLET_01, chapitre 06, GOVERNANCE; ADR-006)**
  - `src/approval_engine/` package: `types.py`, `interfaces.py`,
    `approval_store.py`, `approval_manager.py`, `__init__.py`
  - `ApprovalStatus` enum (pending, approved, rejected) and `ApprovalRequest`
    dataclass (id, agent_id, action, description, reason, confidence, timestamps,
    decided_by, status) with serialization
  - `generate_approval_request_id()` producing unique `appr_<hex>` identifiers
  - `InMemoryApprovalStore`: thread-safe store (RLock), unique submission,
    idempotent approve/reject, filtered and ordered listing, pending-queue
    (oldest first), aggregated stats, clear
  - `ApprovalManagerImpl`: best-effort manager that never raises (every method is
    guarded and returns an empty default)
  - Registered as the `approval` engine in `EngineRegistry` (purely in-memory,
    always available — satisfies the dynamic registry test comparison)
  - `AgentContext`: `approval` property plus `submit_approval()`,
    `approve_approval()` and `reject_approval()` delegating best-effort to the
    registry
  - `BaseAgent`: `approval_required`, `approval_description` and
    `approval_confidence` attributes; execution returns status
    `requires_approval` when the gate is required, and a controlled error when
    the approval engine is unavailable
  - `RetryManager`: terminal statuses extended with `requires_approval`
    (never re-executed); only genuine errors are retried
  - `ResultAggregator`: priority `errors > requires_approval > success`;
    `failed_agents = len - successful - pending`; `requires_approval` re-evaluated
    to `partial_success` once all actions eventually succeed
  - `AgentRuntime.execute_task()` and `RouterEngine.process_request()`: global
    status `requires_approval`, collected `approval_request_ids`, aggregation
    consistent with the router
  - API: 5 approval endpoints in `src/api/server.py` — `GET /approval/pending`,
    `GET /approval/stats`, `GET /approval/{request_id}`,
    `POST /approval/{request_id}/approve`, `POST /approval/{request_id}/reject`
    (404/409 handled)
  - `test_approval_engine.py`: 33 unit tests covering types, store, manager,
    registry, context, BaseAgent, RetryManager and ResultAggregator
- **Phase 2 — Structured Audit System (VOLET_01, chapitre 03, AUDITABILITY)**
  - `src/audit_engine/` package: `types.py`, `interfaces.py`, `audit_store.py`,
    `audit_manager.py`, `__init__.py`
  - `AuditEventType` enum (request, agent, tool, generation, knowledge) and
    `AuditStatus` enum (success, partial_success, failure, unavailable, skipped,
    running)
  - `AuditEvent` dataclass logging timestamp, request_id, agent_id, user_request,
    model_id, confidence, knowledge_sources, execution status and execution time
    — the nine fields required by the AUDITABILITY spec
  - `KnowledgeSourceRef` for provenance/citation of knowledge sources used
  - `generate_request_id()` producing unique `req_<hex>` identifiers
  - `InMemoryAuditStore`: thread-safe store (RLock), event_type/status/agent_id/
    request_id/since/until filters, case-insensitive full-text search, aggregated
    stats (by status/type/agent, average execution time)
  - `AuditManagerImpl`: best-effort manager that never raises (every method is
    guarded and returns an empty default), JSON export with accents preserved
    (`ensure_ascii=False`)
  - Registered as the `audit` engine in `EngineRegistry` (purely in-memory, always
    available — satisfies the dynamic registry test comparison)
  - `AgentContext.record_audit()` plus automatic audit tracing of `search_knowledge`,
    `add_knowledge`, `use_tool` and `generate` (SUCCESS/FAILURE/SKIPPED/UNAVAILABLE
    statuses, confidence and knowledge sources recorded, sensitive arguments
    redacted as `key=***`)
  - `BaseAgent`: every agent execution (success and failure) is audited with
    `action=agent:<id>`, engines used and duration
  - `AgentRuntime.execute_task()` and `RouterEngine.process_request()`: request_id
    generated up front, a summarizing REQUEST event on success and failure, and
    request_id present in both success and error responses
  - `test_audit_engine.py`: 35 unit tests covering types, store, manager, context
    integration and registry integration
- Architecture manual consolidation
  - `scripts/merge_architecture_volets.py`: merges the chapter files of all 26 manual
    folders in `docs/architecture/` into 25 single Markdown documents
    (`VOLET_01.md` → `VOLET_25.md`, 10 chapters each), preserving the original
    content byte-for-byte and the original chapter order. Source folders and
    chapter files are left untouched. Integrity is verified per file (each source
    present in the merge + exact byte count).
- Embassions Tool for generating text embeddings using sentence-transformers models
  - `EmbeddingsTool` (`src/tools/embeddings/tool.py`): provides interface for generating embeddings for one or more texts
  - Supports lazy loading of models, configurable model name, device, and normalization
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- OCR Tool for optical character recognition
  - `OCRTool` (`src/tools/ocr/tool.py`): provides interface for extracting text from images using Tesseract OCR
  - Supports lazy loading of dependencies (Pillow, pytesseract), configurable language and Tesseract command path
  - Returns extracted text, confidence scores, and optional bounding boxes
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Database Tool for SQLite database operations
  - `DatabaseTool` (`src/tools/database/tool.py`): provides simple SQL execution, table listing, and schema inspection
  - Supports executing raw SQL with parameters, fetching results, listing tables, retrieving table schema
  - Includes proper connection handling, autocommit mode, and foreign key enforcement
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Memory Tool for GalSen IA memory engine
  - `MemoryTool` (`src/tools/memory/tool.py`): provides interface for memory operations (store, retrieve, search, update, delete, list)
  - Supports short-term, long-term, user, agent shared, conversation, session, workspace/project, and knowledge memories
  - Integrates with the Memory Engine via the MemoryManager
  - Integrated with the Tool Engine via the tools registry
- Browser Tool for web browsing capabilities
  - `BrowserTool` (`src/tools/browser/tool.py`): provides web browsing capabilities to fetch and interact with web pages
  - Supports visiting URLs, extracting text content, extracting links, and getting page titles
  - Includes error handling, retry mechanisms, and proper HTTP headers
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
  - This is one of the remaining tools declared in `tools/tools.yaml` to be implemented.
- PDF Tool for PDF text extraction
  - `PDFTool` (`src/tools/pdf/tool.py`): provides interface for extracting text from PDF files using PyPDF2
  - Supports lazy loading of PyPDF2 dependency, configurable page selection (specific pages or all pages)
  - Returns extracted text, total page count, and list of pages that were processed
  - Includes proper error handling for missing files, invalid paths, and missing dependencies
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Email Tool for sending emails via SMTP
- Calendar Tool for managing calendar events
  - `CalendarTool` (`src/tools/calendar/tool.py`): provides interface for managing calendar events (list, add, delete)
  - Supports listing events, adding new events with validation, deleting events by ID
  - Includes proper error handling for invalid parameters and missing data
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Docker Tool for Docker container management
  - `DockerTool` (`src/tools/docker/tool.py`): provides interface for managing Docker containers (list, run, stop, remove)
  - Supports listing containers, running containers with options, stopping containers, and removing containers
  - Includes proper error handling for Docker daemon unavailability and API errors
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Logging Tool for managing application logs
  - `LoggingTool` (`src/tools/logging/tool.py`): provides interface for managing application logs (list, add, clear)
  - Supports listing logs, adding log entries with levels, clearing logs
  - Includes proper error handling for invalid parameters
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Metrics Tool for collecting and retrieving metrics
  - `MetricsTool` (`src/tools/metrics/tool.py`): provides interface for collecting and retrieving metrics (counters, gauges, histograms)
  - Supports incrementing counters, setting gauges, recording histogram values, retrieving all metrics, resetting
  - Includes proper error handling for invalid parameters
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)

- Model Engine provider layer, making providers interchangeable (see ADR-003)
  - `ModelProvider` (`src/model_engine/providers/base.py`): the single contract —
    declared catalogue, availability check, generation. No code above this file
    refers to a specific vendor.
  - `ProviderRegistry`: which providers exist and which can answer right now
  - `ModelRegistry` (`src/model_engine/model_registry.py`): catalogue of every known
    model with context window, capabilities and price. Readable with no provider
    configured, so the platform can explain what a task would need.
  - `CapabilityDetector`: asks the provider that serves the model, falling back to
    the pre-existing `StaticCapabilityDiscoverer` for hand-registered models
  - `ProviderSelector`: derives requirements from the task type and complexity,
    then picks the cheapest capable model among available providers
  - Providers: `OpenAIProvider`, `AnthropicProvider`, `GoogleProvider` (catalogues
    declared, generation unavailable until credits are decided) and
    `LocalProvider` (Ollama, fully implemented and generating today when a server runs)
  - `GenerationResponse` carries a status, an empty text on failure, a machine
    readable `reason` and an actionable `detail`
  - `ModelManagerImpl.generate()`: structured generation API; `get_provider_status()`,
    `list_catalogue()`, `select_provider_for_task()`, `explain_selection()`,
    `register_provider()`, `sync_catalogue_to_store()`
- `model` tool exposing the Model Engine through the Tool Engine
- `tail` operation on the filesystem tool, reading the end of a file without a
  size limit
- ADR-003 recording the model provider architecture
- Nine provider tests in `test_model_engine.py` covering the registry, provider
  interchangeability, unavailability reporting, the catalogue, capability
  detection, automatic selection, cost preference, the local probe and the
  cross-engine integrations
- Engine integration layer connecting the engines to the agents and orchestrators
  - `EngineRegistry` (`src/integration/engine_registry.py`): builds each engine once,
    lazily, and shares the instance across the platform. An engine that cannot be
    built is reported unavailable rather than raising into unrelated code.
  - `AgentContext` (`src/agent/context.py`): the object handed to every agent,
    carrying the request, the results of earlier agents, and shortcuts to memory,
    knowledge, documents, vision, tools and models
  - `BaseAgent` / `AgentResult` (`src/agent/base_agent.py`): result shape, error
    containment, timing and memory tracing, so agents only implement `perform`
  - `src/agent/legacy.py`: preserves the historical `execute(input_data)` contract
- Nine agents rewritten to call real engines instead of returning formatted strings
  - `planner`, `researcher`, `coder`, `reviewer`, `tester`, `security`,
    `documentation`, `deployment`, `monitor`
  - Agents that would act outside the process (deploy, push, rewrite docs) report
    what should be done instead of doing it
- Four Tool Engine connectors, previously declared in `tools/tools.yaml` but missing
  - `filesystem`: 13 operations, confined to the project root including through
    symbolic links, writing disabled by default
  - `terminal`: executes without a shell, with an executable allowlist and a timeout
  - `git`: read-only by default; pushing to a protected branch and force pushing are
    refused in code, per `.claude/rules/git-workflow.md`
  - `github`: read-only REST client reading its token from `GITHUB_TOKEN` at call time
- `test_integration.py`: 18 tests covering the registry, the context, the four tool
  connectors, all nine agents, error containment and both orchestrators
- Knowledge Engine for unified knowledge management and RAG capabilities
  - KnowledgeManagerImpl: Main orchestrator with dependency injection for all components
  - KnowledgeStore: In-memory storage with thread-safe operations
  - KnowledgeLoaderFactory: Automatic loader selection by file extension/source type
    - TextFileLoader, JSONFileLoader, CSVFileLoader, WebPageLoader, APIDatasourceLoader
    - PDFLoader, DocxLoader (with graceful degradation if dependencies missing)
  - KnowledgeIndexer: In-memory inverted index for fast keyword search with TF-like scoring
  - KnowledgeRetriever: Semantic retrieval using TF-IDF cosine similarity
  - KnowledgeValidator: Input validation (content length, confidence, date consistency, spam detection)
  - KnowledgeGraph: In-memory directed graph for knowledge relationships with BFS path finding
  - KnowledgeCache: LRU cache with TTL support for frequently accessed knowledge
  - KnowledgeRanker: Configurable weighted ranking algorithm (confidence, recency, length, popularity, custom functions)
- Support for multiple input formats: TXT, JSON, CSV, PDF, DOCX, HTML, Markdown, web pages, APIs, databases
- Features: CRUD operations, full-text search, knowledge graph relationships, validation, caching, ranking, versioning, multi-language support (English, French, Spanish, etc.)
- Comprehensive test suite covering all components and integration scenarios
- Model Engine (unified AI model management system)
  - Model Manager, Model Store (in-memory), Model Loader, Model Selector, Model Router
  - Model Context Manager, Prompt Optimizer, Response Validator, Token Tracker
  - Rate Limiter, Retry Manager, Stream Handler, Parallel Executor, Response Ranker
  - Health Monitor, Capability Discoverer
- Support for multiple providers (OpenAI, Anthropic, Google, etc.)
- Intelligent model selection based on task requirements
- Fallback mechanisms, load balancing, and health monitoring
- Prompt optimization per model type, response validation, hallucination detection
- Token usage tracking, cost tracking, rate limiting, retry mechanisms
- Streaming support, parallel execution, and response ranking
- Web Search Tool for intelligent web search
  - WebSearchTool: Multi‑provider search engine with caching, rate limiting, retry, parallel execution
  - Supports web, news, image, video search; suggestions; filters; language/country selection; safe search
  - Features: duplicate removal, ranking, metadata/snippet extraction, citation generation
  - Integrates with Tool Engine, Memory Engine, Model Engine, Knowledge Engine
- Document Intelligence Engine for unified document processing and understanding
  - DocumentManagerImpl: Main orchestrator with dependency injection for all components
  - DocumentStore: In‑memory storage with thread‑safe operations
  - DocumentLoaderFactory: Automatic loader selection by file extension/source type
  - Features: document loading, chunking, indexing, search, retrieval, summarization, question answering, comparison, duplicate detection, metadata/table/image extraction, versioning, caching, validation
- Vision Intelligence Engine for image understanding and analysis
  - Supports image formats: JPG, JPEG, PNG, WEBP, BMP, TIFF
  - Features: metadata extraction, quality analysis, object detection via provider interface, scene description, face detection without identification
  - Integrated with Router Engine, Agent Runtime, Tool Engine, Memory Engine, Model Engine, Knowledge Engine
- Embeddings Tool for generating text embeddings using sentence-transformers models
  - `EmbeddingsTool` (`src/tools/embeddings/tool.py`): provides interface for generating embeddings for one or more texts
  - Supports lazy loading of models, configurable model name, device, and normalization
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- ADR-005: Select SQLite as persistent storage backend
  - Added SQLite memory store (`src/storage/sqlite_store.py`) implementing the `MemoryStore` interface for persistent storage.
  - Modified `MemoryManager` to accept an optional `MemoryStore` dependency, enabling persistence while maintaining backward compatibility with in-memory storage. The storage backend can be selected via the `GALSEN_STORAGE_BACKEND` environment variable (values: "in-memory" or "sqlite", default: "in-memory").
- API Layer for exposing platform functionality via RESTful API
  - Created `src/api/server.py`: FastAPI-based server exposing memory, model, knowledge, and tool endpoints.
  - Provides endpoints for memory storage/retrieval/search, model generation, tool execution, and knowledge search.
  - Integrates with existing engines: MemoryManager, ModelManagerImpl, KnowledgeManagerImpl, ToolEngine.
  - Includes Pydantic models for request/response validation.
  - Updated requirements.txt with fastapi, uvicorn, pydantic.
  - Verified basic functionality with manual tests.
- Agricultural Advisory Tool for providing crop advice in Wolof/French
    - `AgriAdviceTool` (`src/tools/agri_advice/tool.py`): provides interface for generating agricultural advice using AI models.
    - Supports generating advice in French or Wolof based on user query.
    - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- API Authentication via API Key
    - Added API key authentication middleware (dependency) loaded from environment variable GALSEN_API_KEYS.
    - Protected all sensitive endpoints (memory, model, tool, knowledge) while keeping /health public.
    - Returns 401 for missing/invalid keys.
    - Created unit tests in tests/test_api_auth.py.
- Production-Grade API Rate Limiting
    - `src/api/rate_limiter.py`: Token bucket algorithm (InMemoryRateLimiter) with abstract
      `APIRateLimiter` interface enabling future migration to Redis without code changes.
    - `src/api/__init__.py`: Public API exports for all rate limiting components.
    - Configurable via environment variables: `GALSEN_RATE_LIMIT_ENABLED`, `GALSEN_RATE_LIMIT_AUTHENTICATED_RPM`
      (default 60), `GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM` (default 30),
      `GALSEN_RATE_LIMIT_BURST_MULTIPLIER` (default 2.0).
    - Different limits for authenticated (API key) and unauthenticated (IP) clients.
    - Burst multiplier allows short traffic bursts above the RPM average.
    - Thread-safe implementation with `threading.RLock()`.
    - FastAPI dependency `rate_limit_dependency` applied to all protected endpoints;
      rate limiting runs before authentication (429 before 401).
    - HTTP 429 responses include standard headers: `Retry-After`, `X-RateLimit-Limit`,
      `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
    - Client identification: API key for authenticated clients, IP address
      (including `X-Forwarded-For` for reverse proxies) for unauthenticated clients.
    - Singleton pattern with double-checked locking ensures one rate limiter instance per process.
    - Integrated with existing API key authentication in `src/api/server.py`.
    - 34 comprehensive unit tests in `tests/test_api_rate_limiter.py` — all passing.
- Production-Grade Health & Monitoring Endpoints
    - `src/api/health.py`: Abstract `HealthChecker` interface and `ComponentHealthChecker` implementation
      for monitoring all platform components.
    - Three Kubernetes-compatible endpoints in `src/api/server.py`:
      - `GET /health` — Detailed health report of all components (API, memory engine, model engine,
        knowledge engine, tool engine, storage) with metadata (version, uptime, storage backend,
        configured providers). Always returns HTTP 200; overall status in response body.
      - `GET /ready` — Readiness probe verifying required components (API, tool engine) are available.
        Returns 200 when ready, 503 otherwise.
      - `GET /live` — Liveness probe (minimal check that the process is alive). Always returns 200.
    - `ComponentHealth` and `HealthReport` dataclasses with `to_dict()` for clean JSON serialization.
    - Per-component health checks: memory engine (write → read → delete test item), model engine
      (provider availability counts), knowledge engine (get_stats()), tool engine (list_tools()),
      storage (GALSEN_STORAGE_BACKEND env var).
    - Proper HTTP status codes: 200 for healthy, 503 when required dependencies unavailable.
    - Abstract `HealthChecker` interface designed for future Prometheus/Grafana integration without
      modifying calling code.
    - Singleton pattern with `threading.RLock()` and double-checked locking, identical to rate limiter.
    - Late binding via `set_tool_engine()` for tool engine initialized during FastAPI startup event.
    - Overall status computation: any unhealthy → unhealthy, else any degraded → degraded, else healthy.
    - `src/api/__init__.py` updated to export all health module components.
    - Integrated with existing rate limiting dependency on all health endpoints.
    - 58 comprehensive unit tests in `tests/test_api_health.py` — all passing.
- Production-Grade Docker & Deployment Foundation
    - `Dockerfile` — Image de production multi-stage avec `python:3.11-slim`, utilisateur
      non-root `galsen`, healthcheck Docker intégré via `/health`, et couche de
      dépendances séparée pour minimiser la taille de l'image.
    - `docker-compose.yml` — Deux services : `api` (production, port 8000) et `api-dev`
      (développement avec rechargement automatique, port 8001). Volumes nommés pour la
      persistance des données SQLite et des logs. Healthcheck Docker Compose intégré.
      Limites de ressources CPU/mémoire configurables. Réseau bridge dédié `galsen-network`.
    - `.env.example` — Documentation complète de toutes les variables d'environnement :
      stockage, sécurité, limiteur de taux, ports, fournisseurs de modèles IA,
      dépendances optionnelles.
    - `.dockerignore` — Exclusion du contexte Docker : secrets, caches, tests, docs,
      IDE files, virtualenvs, Git.
    - `docs/deployment/docker.md` — Guide complet de déploiement Docker : démarrage
      rapide, construction d'image, exécution avec et sans Compose, variables
      d'environnement, persistance des données, optimisation de taille, compatibilité
      Kubernetes avec exemple de Deployment, troubleshooting.
    - Compatibilité Kubernetes : endpoints `/health`/`/ready`/`/live` pour les probes,
      configuration entièrement par variables d'environnement, utilisateur non-root,
      signal handling via uvicorn.
- Persistent Storage Package (ADR-005) — `src/storage/`
    - `BaseRepository[T]` — Interface abstraite générique définissant le contrat CRUD
      (save, get, update, delete, list_items, clear, count, exists) pour tout backend
      de stockage, permettant de remplacer SQLite par PostgreSQL sans modifier le code
      appelant.
    - `SQLiteMemoryStore` — Implémentation concrète de `MemoryStore` avec persistance
      SQLite. Supporte les bases fichier et `:memory:` (cache partagé avec connexion
      persistante). Gère la sérialisation JSON pour le contenu, les tags et les
      métadonnées.
    - `cleanup_expired()` — Suppression des mémoires expirées basée sur `time.time()`.
    - `src/storage/__init__.py` — Package exportant `BaseRepository` et `SQLiteMemoryStore`.
    - `tests/test_storage.py` — 50 tests unitaires (8 classes) : BaseRepository, CRUD,
      filtrage, pagination, clear, cleanup_expired, cas limites (Unicode, contenu long,
      concurrence), persistance fichier et exports du package.
- **Phase 1 — Verifiable Knowledge Hierarchy (VOLET_01, chapitre 04)**
  - `KnowledgePriority` (IntEnum) : hiérarchie de fiabilité P1 → P4 (P1 = textes
    officiels, publications gouvernementales, normes et documentation officielles ;
    P2 = recherche évaluée par les pairs, documentation technique de confiance,
    institutions réputées ; P3 = références industrielles fiables, consensus d'experts ;
    P4 = estimations ou opinions clairement étiquetées). Classe utilitaire
    `KnowledgePriority.from_source_category()` qui dérive la priorité par défaut
    depuis la catégorie de source.
  - `SourceCategory` (Enum) : 12 catégories de sources (OFFICIAL, GOVERNMENT,
    STANDARD, OFFICIAL_DOCUMENTATION, PEER_REVIEWED, TRUSTED_DOCUMENTATION,
    INSTITUTIONAL, INDUSTRY, EXPERT_CONSENSUS, ESTIMATE, OPINION, UNKNOWN).
  - `KnowledgeSource` enrichi : `source_category`, `title`, `author`, `url`,
    `citation`, `retrieved_at` — traçabilité et citation complètes.
  - `KnowledgeItem.priority` : champ avec valeur par défaut P3 ; préservé par
    `update_content()`.
  - Validation renforcée (`knowledge_validator.py`) : type de source obligatoire
    pour P1/P2 (source traçable avec `id` et `location` définis), vérification des
    types de `source_category`/`retrieved_at`, priorité doit être un
    `KnowledgePriority`, avertissement de cohérence priorité/source.
  - Classement par priorité (`knowledge_ranker.py`) : critère `priority`
    (score `1.0 - (priority-1)/3.0`), méthode `rank_by_priority()`, poids
    équilibrés mis à jour (confidence 0.35, priority 0.25, recency 0.2, ...).
  - Filtres de priorité dans le store (`knowledge_store.py`) : `priority`,
    `min_priority`, `max_priority`, `source_category`.
  - `KnowledgeManager.retrieve_reliable()` : récupération fiable uniquement,
    retourne `{items, reliable, best_priority, best_confidence, reason}` ; renforce
    le comportement « Je ne sais pas » quand aucune connaissance fiable n'est
    disponible.
  - Outil RAG mis à jour (`src/tools/rag/tool.py`) : conversion P1–P4, provenance
    et citation sérialisées, option `require_reliable`/`min_priority` sur
    `retrieve_for_prompt`.
  - Nouveaux tests : 4 tests knowledge engine (hiérarchie P1–P4, provenance,
    filtrage de fiabilité, validation priorité) + 1 test RAG
    (round-trip priorité/provenance).

### Fixed
- Suite de tests stabilisée — 213 tests passent, 0 échecs
  - `test_vision_engine.py::test_image_classification` : `np.float32` n'est pas une sous-classe de `float` Python — corrigé avec `isinstance(score, (float, np.floating))`
  - `test_integration.py::test_terminal_tool` : `echo` n'existe pas comme exécutable standalone sur Windows — remplacé par `python -c "print(...)"`
  - `test_model_engine.py::test_model_engine` : fonction async sans décorateur `@pytest.mark.asyncio` — ajouté
  - `test_rag_tool.py::test_add_and_retrieve` : variable `update_data` non définie après mise à jour + échec de mise à jour car la version n'était pas incrémentée — corrigé
  - `src/tools/rag/tool.py::_op_update` : `KnowledgeItem` créé sans incrémenter la version, causant le rejet de la mise à jour par le store — corrigé
  - `src/knowledge_engine/knowledge_manager.py` : méthode `get_store()` manquante, appelée par `_op_list` du RAGTool — ajoutée
- Infinite recursion in the agent pipeline: `test_router.py` runs every agent,
  including `tester`, which ran `test_router.py` again. Nested execution is now
  detected through an inherited environment flag, and orchestration suites are
  excluded from agent-driven runs because running them there is circular.
- Orchestration suites went from 222s to 34s once the circular runs were removed
  and the web search timeout was shortened
- Reviewer agent reported declarations found inside docstrings as undocumented code
- Missing docstrings on the three `_HTMLTextExtractor` callbacks
- Dead `pass` block in `csv_loader.py` header handling
- Fourteen over-long lines in the document engine loaders and interfaces
- Document Intelligence Engine could not be imported at all: 9 loaders used `from ..types import`,
  which raised `ImportError: attempted relative import beyond top-level package`
- `html_loader` imported `html.parser.Parser`, which does not exist (correct name is `HTMLParser`)
- `ocr_loader` referenced an undefined variable `st` and shadowed the `format` builtin
- `DocumentLoaderFactory()` instances registered no loader; only the module-level singleton did,
  so a directly constructed factory silently failed to recognise most formats
- `DocumentManagerImpl.load_document()` called `DocumentItem.from_dict()` on an object that was
  already a `DocumentItem`
- `CompositeMetadataExtractor` raised `NameError` on an undefined `me`
- `DocumentMetadata` was missing the `line_count` field that its own extractor wrote to
- Document IDs derived from `time.time()` collided when several documents were saved within the
  same millisecond; they now use UUIDs
- `SimpleChunker` could emit chunks up to 100 characters larger than requested and could loop
  forever when the overlap left no progress
- `LRUDocumentCache` accepted a TTL argument and ignored it
- New document versions were built but never stored, so they could not be retrieved by ID
- `unregister_document` deleted the document but left it in the search index
- `json_loader` used the JSON `name` field as document title, which is an entity name, not a title
- Removed `text_loader.py`, an unregistered duplicate of `txt_loader.py`
- Document engine test suite crashed on Windows before running any assertion, because its own
  ✓ output characters are not encodable in cp1252
- KnowledgeIndexer.search() now returns List[tuple[KnowledgeItem, float]] instead of List[str]
- KnowledgeManagerImpl.search_knowledge() and retrieve_for_prompt() updated to correctly unpack search results
- KnowledgeManagerImpl stats output format changed to match test expectations ("store" instead of "knowledge_store")
- KnowledgeManagerImpl now exposes ranking methods: rank_by_confidence, rank_by_recency, rank
- Fixed date handling in tests to use timezone-aware datetime objects
- Fixed knowledge item setup in tests to properly set both created_at and updated_at for age simulation
- KnowledgeValidator date comparison now works with timezone-aware datetime objects
- Fixed missing imports and updated credential detail message in hosted providers to enable environment‑based credential handling (ADR-004)

## [0.2.0] - 2026-07-31
### Added
- Project foundation structure
- Root `CLAUDE.md` with permanent memory system
- Core memory files (`vision`, `current-objectives`, `completed-work`, `pending-work`, `priorities`, `knowledge-index`)
- Complete folder structure for long-term development
- Router Engine (core orchestration component)
- Agent Loader, Workflow Loader, Config Loader, Execution Planner, Result Aggregator, Retry Manager, Logger, Agent Dispatcher
- Agent Runtime (parallel/sequential execution engine with retry handling)
- Placeholder agents for all agent types (Planner, Researcher, Coder, Reviewer, Tester, Security, Documentation, Deployment, Monitor)
- Updated agent registry with module paths for dynamic loading
- Tool Engine architecture (dynamic tool loading and execution)
- Tool Loader, Tool Executor, Tool Engine, and BaseTool interface
- Updated tools registry with module and class information for each tool
- Memory Engine (unified memory management system)
  - Memory Manager, Memory Store (in-memory), Memory Retriever, Memory Indexer, Memory Cache (LRU), Memory Summarizer, Memory Ranking
  - Designed for future storage backends (vector databases, SQL, local, cloud)
  
### Changed
- Nothing yet

### Fixed
- Nothing yet

## [0.1.0] - 2026-07-28
- Initial project foundation created