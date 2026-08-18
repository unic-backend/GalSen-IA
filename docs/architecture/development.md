# Development Practice

What VOLET_03 asks for, and what the repository actually enforces. Every figure here was
measured on 2026-08-10 by parsing the code, not by reading the rules.

This file does **not** restate the standards: they live in `.claude/rules/` and
`docs/standards/coding.md`, and duplicating them is what
`.claude/rules/documentation.md` forbids. What is recorded here is the **gap between the
declared and the enforced**, which no rule file can contain about itself.

---

## Declared versus enforced (chapter 01)

13 rule files, 979 lines, describe how this project is built. What runs on its own:

| Mechanism | What it enforces | When |
|-----------|------------------|------|
| CI (`.github/workflows/tests.yml`) | the suite passes; the API imports the way the Dockerfile starts it | every push to `main`, every PR |
| `scripts/release_check.py` | 8 checks: version, tag, clean tree, secrets, changelog, docs, startup, suite | run by hand before a release |
| `SessionStart` hook | loads project memory | at each agent session |
| `PostToolUse` hook | updates the code graph | on every edit |

**Nothing else is automated.** No linter, no formatter, no type checker, no pre-commit
hook is configured — `requirements.txt` declares pytest and coverage, and no `setup.cfg`,
`pyproject.toml`, `.flake8` or `.pre-commit-config.yaml` exists. The conventions in
`.claude/rules/coding-conventions.md` (PEP 8, snake_case, type hints, French comments)
are followed by agreement, and verified by whoever reads the diff.

That is a defensible position for a one-contributor repository, and it is worth stating
rather than leaving to be discovered: **the standards are respected because the same
author applies them, not because anything checks.**

## Conventions, measured (chapter 02)

Parsed across the 235 Python files of `src/`:

| Convention | Measured |
|------------|----------|
| Modules with a docstring | 231 / 235 — **98 %** |
| Functions with a docstring | 1 778 / 1 853 — **96 %** |
| Classes with a docstring | 370 / 386 — **96 %** |
| Functions with a return type hint | 1 625 / 1 853 — **88 %** |
| Function names in snake_case | 1 853 / 1 853 — **100 %** |

The manual asks to "document every public class and function" and to use type hints on
signatures. Documentation is close to complete; **return type hints are the weakest
convention at 88 %**, and 228 functions carry none. No name violates the naming rule.

These figures were produced by an AST walk, not by sampling, and can be reproduced the
same way.

## Project structure (chapter 03)

`.claude/rules/testing.md` requires tests in `tests/`. **27 test files sat at the
repository root** — collected and green, only misplaced, and recorded as P3 in the
backlog since VOLET 04.

They are now in `tests/`, which held 60 files and holds 87. The move was not a rename:
**20 path expressions broke silently in the process.** Every moved file computed the
repository root as `os.path.dirname(__file__)`, which after the move points at `tests/`;
three of them built `tools/tools.yaml` the same way. Both were rewritten to climb one
level, matching the convention the files already in `tests/` use.

Verified: **1 655 passed, 7 skipped** — the same counts as before the move, which is what
"only their location differs" has to mean to be true.

`tests/test_project_structure.py` keeps it that way: it fails if a `test_*.py` reappears
at the root, if a test in `tests/` adds its own directory to `sys.path` instead of the
root, or if a new loose module lands at the root. The second check earned its place
immediately — it caught `test_approval_engine.py`, which used
`dirname(abspath(__file__))` and had escaped the bulk rewrite. The suite still passed,
because pytest inserts the rootdir anyway; the file's own intent was broken, and only an
explicit check could see it.

## Testing levels (chapter 04), measured

**1 604 tests in 87 files** in `tests/`, classified by what they exercise:

| Level the manual names | Tests | Where |
|------------------------|-------|-------|
| Unit | 1 293 | the bulk of the suite |
| Integration | 156 + 46 | API routes (`test_api_*`), pipelines (`test_integration`, `test_workflow_revue`) |
| End-to-end | included above | `test_generation_end_to_end` (9), skips while no provider answers |
| Security | 109 | `test_rbac` (28), `test_scaling` (23), `test_storage_encryption` (21), `test_api_security_headers` (17), `test_api_auth` (7), `test_knowledge_security` (8), `test_search_security` (5) |
| **Performance** | **0** | nothing measures a duration and asserts on it |

Four levels of five exist. **Performance testing is the one absent**, and it is absent
for a reason that chapter 08 names: no target has ever been declared, so a performance
test would have nothing to assert against. Phase 8.1 is where that gets settled — writing
timing tests before there is a threshold would produce assertions chosen to pass.

The measurements taken during VOLETs 05 and 14 (0.234 ms per cached search, 8.0 ms to
build a 1 000-document index) live in documentation, not in the suite: they are
observations, and nothing fails when they drift.

## Startup configuration (chapter 05)

The chapter asks, in one line, to "validate environment variables at startup". Nothing
did, and the failure mode is quiet: `GALSEN_STORAGE_BACKEND=sqllite` fell back to
in-memory storage, so a deployment that believed it was persisting was not.

`src/config/environment.py` checks the variables that are **present** and cannot be
applied — 11 of them today, each with the consequence of ignoring it, not just the rule
it breaks. It runs in the API lifespan and **reports without blocking**: a platform that
refuses to boot over a malformed rate limit is less useful than one that boots and says
so. An absent variable is never a complaint: most are optional and their absence disables
a capability cleanly.

Secrets are never echoed — `to_dict()` masks any variable whose name contains `KEY`,
`TOKEN`, `PASSWORD` or `SECRET`, because a validation warning ends up in a log.

**Eight variables were read by the code and documented nowhere**, three of them added the
same day by VOLETs 05 and 14 — `GALSEN_DATA_DIR`, `GALSEN_INSTANCE_ID`,
`GALSEN_LOG_MAX_BYTES`, `GALSEN_LOG_BACKUP_COUNT`, `GALSEN_GITHUB_TOKEN`,
`GALSEN_KNOWLEDGE_OWNERS`, `GALSEN_SEARCH_OWNERS`,
`GALSEN_KNOWLEDGE_REVALIDATION_DAYS`. All are now in `.env.example`, and a test fails if
a variable read by `src/` is missing from it — documenting after the fact is exactly what
never gets done.

## Coverage (chapter 04), measured

`python -m pytest --cov=src` over the whole suite: **81 % of 15 397 statements**, 2 926
uncovered, across 237 modules. 89 modules are at 100 %.

`.claude/rules/testing.md` sets two thresholds. The general one — 80 % for new code — is
met. The second asks **95 % on critical paths** (authentication, security, data
validation), and that one is worth checking rather than assuming:

| Critical module | Coverage |
|-----------------|----------|
| `src/api/rbac.py` | **99 %** |
| `src/api/rate_limiter.py` | **96 %** |
| `src/knowledge_engine/knowledge_manager.py` | **95 %** |
| `src/storage/encryption.py` | 94 % |
| `src/api/server.py` | 77 % |

Three of five meet it, encryption is one point short, and `server.py` — 676 statements of
route wiring — is the outlier. Its uncovered part is mostly error branches on routes whose
happy path is tested.

**Where coverage actually collapses is the model engine.** Excluding the vision engine
(whose optional OpenCV dependencies make it a known case), the worst modules are:

| Module | Coverage |
|--------|----------|
| `src/model_engine/response_ranker.py` | 14 % |
| `src/model_engine/model_context_manager.py` | 17 % |
| `src/model_engine/response_validator.py` | 17 % |
| `src/tools/api/tool.py` | 17 % |
| `src/document_intelligence_engine/{xlsx,pptx,docx,pdf}_loader.py` | 18–20 % |
| `src/knowledge_engine/knowledge_loader.py` | 41 % |

The pattern is consistent and explains itself: **the untested code is the code that needs
something the platform does not have.** The model engine's ranking, validation and context
management run only when a provider answers — exit criterion C1, still open. The document
loaders need the optional dependencies of `requirements-optional.txt`. This is not
neglect; it is the same gap showing up in a different measurement.

## Rollback (chapter 05)

Rolling back this platform means redeploying an earlier image over the **same** SQLite
files. The code goes back on its own — `docker compose` and a versioned image handle
that. The question the chapter actually raises is data integrity: *does a database written
by the newer version stay readable by the older one?*

It does, for one reason: **migrations are additive and reads name their columns.**
`_add_missing_columns()` only ever runs `ALTER TABLE ... ADD COLUMN`; nothing is renamed
or dropped, and every `SELECT` lists the columns it wants, so a version that predates a
column simply never asks for it.

`tests/test_storage_rollback.py` proves both directions rather than asserting them: an
older reader on a newer base, a newer reader on an older base, a full
migrate → roll back → re-migrate cycle that keeps all five rows, and a check that
migration never removes or renames a column.

What is **not** covered: there is no documented operational procedure and no release tag
in the repository (`git tag` is empty), so "roll back to the previous version" currently
means "redeploy the previous image", identified by hand. That belongs with exit criterion
C4 — nothing is deployed yet.

## Version control (chapter 06), measured

| What the manual asks | What the repository does |
|----------------------|--------------------------|
| Protect `main` | never pushed to directly; work happens on a branch and merges by PR |
| Branch strategy (`feature/`, `fix/`, `release/`, `hotfix/`) | **not followed**: two branches exist, `main` and the current working branch |
| Conventional commits | **73 of the last 100** match `type: subject` |
| Review before merge | PRs are used; the reviewer is the author |
| Tag official releases | **no tag exists** |
| Never commit secrets | `release_check.py` scans for tracked secrets |

Of the 27 non-conforming commits, 24 are GitHub's own merge commits — unavoidable and not
a deviation. **Three are real**: `merge: reconcile the two development lines`, `Update
session-state.md` (the GitHub web editor's default message) and one commit whose message
is a single word, `diop`.

The absent branch strategy is honest rather than sloppy: `develop`, `release/` and
`hotfix/` describe a team shipping to production, and this repository has one contributor
and nothing deployed. Adopting the ceremony now would produce empty branches. The tags are
different — semantic versioning is already decided (`src/version.py`), `release_check.py`
checks for a tag, and **the first tag is simply overdue**.

## Module documentation (chapter 07)

The chapter asks each major module to document six things: purpose, responsibilities,
public interfaces, dependencies, configuration and known limitations.

Measured across the 18 packages of `src/`: **three had no module docstring at all**
(`memory_engine`, `router`, `tool`) and three more said nothing beyond their own name
("Package du moteur de connaissances GalSen IA."). All six were written to the chapter's
structure, including their *known limitations* — which is the field that makes such a
docstring worth reading and the one always omitted.

`tests/test_package_documentation.py` guards it: every package must have a docstring, no
docstring may be shorter than eight words, and the six rewritten packages must keep the
chapter's headings. The remaining twelve are not forced to the full structure — demanding
six headings from all of them at once would produce twelve docstrings written to satisfy
a test.

## Performance targets (chapter 08)

The single largest thing this VOLET closes. `release_check.py` had been refusing to tick
"performance targets verified" for an honest reason: **no target existed**, and a
measurement with no threshold informs no decision.

Targets now live in `docs/standards/performance.md`, derived from measurements taken the
same day (100 calls per route, rate limiter disabled, 200 knowledge items):

| Class | Target (p95) | Current p95 |
|-------|--------------|-------------|
| Liveness and metrics | ≤ 50 ms | 2.2–2.3 ms |
| Read and search | ≤ 200 ms | 2.9–3.6 ms |
| Write | ≤ 500 ms | not yet isolated |
| Model generation | none — provider-dominated | — |

The multiples are deliberately large: a threshold set at twice the current figure fails on
a loaded CI runner and gets disabled within a month. End-to-end latency is **not**
targeted, because nothing is deployed (C4) and a figure invented before the first
deployment sets the bar in the wrong place.

This also fills the fifth testing level. `tests/test_performance_targets.py` asserts the
two measurable classes and checks that search **does not degrade with base size** —
ten times the documents must not cost five times the time, which is what an inverted index
is for. Writing those tests earlier would have meant choosing assertions that pass;
writing them now means asserting a declared target.

`release_check.py` gains a ninth automated check: the targets document and its tests must
both exist and the document must declare targets. It fails if either disappears — never
because a human forgot to tick a box.

## Technical debt (chapter 09), re-measured

The register in `docs/roadmap/roadmap.md` held nine debts. Checking each against the
repository rather than against memory:

- **Four are paid**: log rotation (the file is at 3.5 MB under a 5 MB × 3 policy), the
  metrics tool now fed by request handling, the 27 root test files, and the performance
  target.
- **Three were missing**: no linter or type checker, no release tag, and — until this
  VOLET — no performance target at all.
- **One grew**: the orchestration suite was recorded at 97 s and now takes **105 s**, with
  three tests at ~34 s each.
- **One is unchanged and still real**: three implementations still write a file to disk
  (`LocalDiskStorageConnector`, `SQLiteFileStore`, `FileSystemCloudStore`), and nothing
  says which a caller should use.

A register nobody re-measures drifts both ways: it keeps debts that are settled and misses
the ones that appeared. That is the finding of this phase, more than any individual line.
