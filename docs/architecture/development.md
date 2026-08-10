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
