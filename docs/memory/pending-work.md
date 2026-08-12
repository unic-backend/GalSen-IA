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

- **Build the Senegalese corpus.** The base now holds **250 verifiable passages** from the
  project's own documentation (VOLET 28), and the ingestion path chunks, keeps provenance
  per passage and cites sources. What is missing is the corpus that matters: agriculture,
  health, education. It is ingested from **real declared documents** — the manifest format
  is in `docs/knowledge/README.md`. Nothing is written from memory: fabricating knowledge
  served to farmers as fact is the most damaging thing this repository could do.
  *Deciding criterion:* strategic alignment — the Knowledge Leadership pillar still has no
  Senegalese evidence under it, and this one depends on documents, not on code.

- **Two search sources of four still have no provider** (document, vision). Memory was
  wired on 2026-08-11, and the unjustified merge weights were **removed** rather than
  justified: scores from two engines are not comparable, and the response now says so.
  *Deciding criterion:* user impact — both remaining sources need their engine to produce
  searchable text first, which neither does today.

- **Deploy the platform somewhere reachable** (criterion C4). The Dockerfile, the compose
  file and CI exist; nobody has ever reached this API over a network.
  *Deciding criterion:* strategic alignment — nothing else on this list can be validated
  in production until this is true.

- **Push the `v0.1.0` tag.** It exists locally on `383fcf7` with its release notes, but the
  environment that prepared it cannot push tag refs (the git proxy answers 403), so
  `git fetch --tags` finds nothing. One command from a normal clone publishes it and
  triggers the image build: `git push origin v0.1.0`.
  *Deciding criterion:* maintenance cost — one command, and criterion C4 needs it.

- **Finish applying ADR-016.** One step remains: retire `CloudFileItem` in favour of
  `FileItem` and delete the cloud stores, which removes the second half of the duplicated
  design. `/cloud/*` already announces its end of life, so a `Sunset` date can be set once
  this is done.
  *Deciding criterion:* maintenance cost — two route families do the same job until the
  next major version, which ADR-011 accepts on purpose. What made this P1 — *"nothing says
  which one a caller should use"* — is answered: a caller uses the file service.

## P2 — Medium · real value, no criterion waits on it

- **Decide whether analytics data is retained.** Trends and anomaly detection are the
  chapter 09 capabilities `/analytics` declares unavailable, and both need history that
  survives a restart — counters and workflow history are process-memory only (ADR-009).
  This is a storage decision, so an ADR before code.
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
