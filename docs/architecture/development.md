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
