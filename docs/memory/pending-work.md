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

- **This repository has no `LICENSE` file** (`ls LICENSE*` returns nothing, 2026-08-20).
  Found independently by ADR-034 and ADR-035, after five programmes spent refusing other
  projects' manifests on the grounds that *a manifest is a declaration and a file is a
  grant*. **Which licence is the owner's decision**, so this entry is a question waiting
  for an answer, not a task waiting for a session.
  *Deciding criterion:* strategic alignment — without it nobody may legally reuse this
  work, and the standard this repository applies to others it does not meet itself.

- **Build the Senegalese corpus.** The base now holds **250 verifiable passages** from the
  project's own documentation (VOLET 28), and the ingestion path chunks, keeps provenance
  per passage and cites sources. What is missing is the corpus that matters: agriculture,
  health, education. It is ingested from **real declared documents** — the manifest format
  is in `docs/knowledge/README.md`. Nothing is written from memory: fabricating knowledge
  served to farmers as fact is the most damaging thing this repository could do.
  *Deciding criterion:* strategic alignment — the Knowledge Leadership pillar still has no
  Senegalese evidence under it, and this one depends on documents, not on code.

- **One search source of four has no provider, and it never will** (vision).
  *Corrected on 2026-08-13:* this entry claimed **both** remaining sources were waiting on
  their engine to produce searchable text. That was true for vision and **false for
  documents** — `DocumentManagerImpl.search_documents()` has always indexed what it loads;
  only the provider was missing. It is written and registered now, so three sources of four
  answer.
  Vision analyses an image and produces no indexed text, so there is nothing to search:
  `/search` reports it in `sources_unavailable` **with that reason** rather than letting a
  caller believe four sources were queried.
  *Deciding criterion:* user impact — closed for documents; for vision the gap is the
  absence of searchable text, not the absence of code.

- **Deploy the platform somewhere reachable** (criterion C4). The Dockerfile, the compose
  file and CI exist; nobody has ever reached this API over a network.
  *Deciding criterion:* strategic alignment — nothing else on this list can be validated
  in production until this is true.

- **Push the `v0.1.0` tag.** It exists locally on `383fcf7` with its release notes, but the
  environment that prepared it cannot push tag refs (the git proxy answers 403), so
  `git fetch --tags` finds nothing. One command from a normal clone publishes it and
  triggers the image build: `git push origin v0.1.0`.
  *Deciding criterion:* maintenance cost — one command, and criterion C4 needs it.

- **Set a `Sunset` date on `/cloud/*`.** ADR-016 is applied: the duplicated design is
  gone and the routes are announced as deprecated. What remains is choosing a removal
  date, which ADR-011 says must be decided rather than invented — and it is only worth
  deciding once a deployment exists to have clients (C4).
  *Deciding criterion:* maintenance cost — small, and it closes ADR-016.
  *Deciding criterion:* maintenance cost — two route families do the same job until the
  next major version, which ADR-011 accepts on purpose. What made this P1 — *"nothing says
  which one a caller should use"* — is answered: a caller uses the file service.

## P2 — Medium · real value, no criterion waits on it

- **Decide whether analytics data is retained.** **ADR-020 is written and `proposed`**
  (2026-08-13): option A keep nothing, option B retain aggregates only on the existing
  SQLite store, option C retain events with a retention window. The recommendation is B,
  **after C4** — an aggregate answers "is the platform degrading?", and it keeps the
  privacy rule enforceable by shape rather than by vigilance. Nothing is implemented; the
  decision is the owner's.
  *Deciding criterion:* strategic alignment — worth taking **after C4**: before a
  deployment exists there is no operational history worth keeping.

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

- **Widen the linter, and add a formatter and a type checker.** `ruff check` runs in CI and
  in the suite (`pyproject.toml`), and the repository passes it. What is deliberately left
  out is written in the config: modernising annotations flags **3 183** places and sorting
  imports touches **216 files** — mass rewrites for zero defect that would make `git blame`
  unreadable. `ruff format` and a type checker belong to the same decision.
  *Deciding criterion:* maintenance cost — all three start paying the day a second
  contributor arrives, and that is the day to take the diff.

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
