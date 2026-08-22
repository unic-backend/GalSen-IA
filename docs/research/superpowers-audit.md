# Superpowers — compatibility & integration audit

**Owner's brief**: 2026-08-22, 28 sections (§0–§27).
**Phase plan**: `docs/memory/phase-plan.md` — 17 chapters, 24 phases.
**Status of this document**: *in progress*. It is written phase by phase, as each
measurement is taken. No section is filled from recall; a section not yet reached
is absent rather than guessed.

**§0 and §27 bind every line below**: this is an audit. Nothing is installed,
copied, merged or modified. No decision is implemented before the gate.

---

## Subject and version examined

| | |
|---|---|
| Repository | `https://github.com/obra/superpowers` |
| Commit examined | **`b36e0829c6d0140e93cfef2ca599b1b07d4a7797`** |
| Date of that commit | 2026-08-12T09:53:21-07:00 |
| Release it carries | **v6.3.0** — *"Devin CLI and Hermes Agent support, brainstorming three-path router, SDD/Codex efficiency fixes (#2125)"* |
| How it was obtained | `git clone --depth 1` through this session's git proxy, into `/home/user/obra/superpowers`. `origin` verified as the repository above before anything was read. |
| Repository size | 3.2 MB (shallow clone) |

**§1 is satisfied: the version is measured, not `UNKNOWN`.** That was not a given.
Probing the three usual doors first:

| Endpoint | Result |
|---|---|
| `raw.githubusercontent.com/obra/superpowers/main/README.md` | **200** |
| `api.github.com/repos/obra/superpowers` | **403** |
| `github.com/obra/superpowers` | **403** |

So the content was readable file by file from the start, but **directory
enumeration through the API was not**, and neither was the commit SHA. An audit
that had stopped at `raw` would have had to write `UNKNOWN` for the version and
would have had to *guess* which files exist — which is how a survey ends up
describing the repository it expected rather than the one that is there. The git
proxy serves anonymous reads of public repositories, so the clone gave both the
tree and the SHA.

---

## PHASE 1.1 — GalSen IA reconnaissance: agents, skills, commands, hooks

Measured on the repository at `078e3ec`, not recalled.

### Agents — 17, declared in one registry

`agents/registry.yaml` holds 17 entries: one orchestrator and sixteen
specialists.

| | |
|---|---|
| Orchestration | `router` — Central Orchestrator |
| Software lifecycle | `planner`, `researcher`, `coder`, `reviewer`, `tester`, `security`, `documentation`, `deployment`, `monitor` |
| Project & product | `organizer`, `project_manager`, `opportunity` |
| Knowledge & data | `verifier` (Fact Verification), `senegal` (Senegal Intelligence), `knowledge_architect`, `data_engineer` |

The shape to notice for §11 later: GalSen IA's agents are **declared data**
(`registry.yaml`) loaded by `src/router/agent_loader.py`, not classes discovered
by convention.

### Skills — 14, and they are development-time, not runtime

`.claude/skills/` holds 14 skills: `debug-issue`, `explore-codebase`,
`refactor-safely`, `review-changes`, and ten `speckit-*`
(`analyze`, `checklist`, `clarify`, `constitution`, `converge`, `implement`,
`plan`, `specify`, `tasks`, `taskstoissues`).

Each is a `SKILL.md` with YAML front-matter (`name`, `description`) — **the same
file format Superpowers uses**. This matters more than it looks and is recorded
here for §7: the two systems already speak the same skill format, so "adopting a
skill" is a question of *content*, never of *machinery*.

**These skills are not part of the GalSen IA product.** They configure the coding
agent that builds it. Nothing under `src/` loads `.claude/skills/`. The
distinction §6 demands — development-time versus production-time — is therefore
already structural in this repository, not a policy someone has to remember.

### Commands — zero

`.claude/commands/` is empty. GalSen IA has no slash-command layer of its own.

### Hooks — two events

`.claude/settings.json` declares hooks on **`SessionStart`** and
**`PostToolUse`**. `.claude/settings.local.json` declares none.
`SessionStart` runs `scripts/session_bootstrap.py`, which injects
`docs/memory/session-state.md` and `docs/memory/phase-plan.md`.

### Rules — 15 files

`.claude/rules/` holds 15 markdown rule files, referenced from `CLAUDE.md`:
phase protocol, memory, response style, work cadence, verification,
post-integration validation, spec-driven governance, coding conventions and
standards, core rules, security, documentation, prompts, git workflow, testing.

**This is the finding that will shape the whole audit**: GalSen IA already has a
written engineering methodology, enforced by a session hook and by tests. The
question Superpowers raises is therefore not *"does GalSen IA need a
methodology?"* but *"is any part of this one weaker than its counterpart?"* —
a much narrower and much more answerable question.

### Subject side, same phase — what Superpowers ships

Counted from the clone, not from the README:

- **14 skills**, one `SKILL.md` each: `brainstorming`,
  `dispatching-parallel-agents`, `executing-plans`,
  `finishing-a-development-branch`, `receiving-code-review`,
  `requesting-code-review`, `subagent-driven-development`,
  `systematic-debugging`, `test-driven-development`, `using-git-worktrees`,
  `using-superpowers`, `verification-before-completion`, `writing-plans`,
  `writing-skills`.
- **`hooks/`** — `hooks.json`, `hooks-cursor.json`, `run-hook.cmd`,
  `session-start/`.
- **No `commands/` directory** anywhere in the tree.
- **Seven host-agent plugin manifests**: `.claude-plugin/`, `.codex-plugin/`,
  `.cursor-plugin/`, `.devin-plugin/`, `.hermes-plugin/`, `.kimi-plugin/`,
  `.opencode/`, plus `gemini-extension.json`, `AGENTS.md`, `CLAUDE.md`,
  `GEMINI.md`.
- `tests/` with per-host directories (`claude-code`, `codex`, `devin`, `hermes`,
  `kimi`, `antigravity`, `hooks`, …).

The directive's §7 listed eleven example skills and warned the list might be
incomplete. **It is not incomplete — it is a superset**: all eleven exist, and
three more (`receiving-code-review`, `using-superpowers`, `writing-skills`).
Recorded because §7 said to inspect rather than assume, and inspecting happened
to confirm the assumption this time. Next time it will not.

---

## PHASE 1.2 — GalSen IA reconnaissance: orchestration, memory, planning, tasks, self-healing

### Orchestration — `src/router/`, 16 modules

`agent_dispatcher`, `agent_loader`, `config_loader`, `decision_trace`,
`execution_planner`, `logger`, `orchestration_paths`, `output_validation`,
`result_aggregator`, `retry_manager`, `router_engine`, `workflow_checkpoint`,
`workflow_history`, `workflow_loader`, `workflow_validator`.

`workflows/workflows.yaml` declares **8 workflows**.

### Long-running work and resumption — already structural

`src/router/workflow_checkpoint.py` carries `RunStatus`, `StepRecord`,
`WorkflowRun`, with `resumable()`, `done_agents()` and `next_step()`.
A run knows which steps completed and where to resume — this is the subsystem
§24 ("long-running tasks") and §21 ("failure recovery") will be compared against.

### Memory — `src/memory_engine/`, 12 modules

`interfaces`, `layers`, `memory_cache`, `memory_indexer`, `memory_manager`,
`memory_quality`, `memory_ranker`, `memory_retriever`, `memory_store`,
`memory_summarizer`, `types`.

Beside it, a **second and separate** memory: `docs/memory/` — the project's
engineering memory, read and written by the assistant, injected at session start.
The two must not be conflated in §12: one is the product's memory of what users
told it, the other is the repository's memory of what was decided.

### Self-healing — real, and not where its name suggests

There is **no `src/self_healing/` directory**. The engine is
`src/agent/self_healer.py`, inside `src/agent/` (23 modules), with:

- `policies/immutability.py` — what an autonomous repair may never touch. Its own
  header states the rule this audit should hold Superpowers to: *"the value of
  that guarantee is exactly the quality of the list. So the list is **derived
  from the repository's own architecture**, not written from memory"*, and
  `protected_paths()` reports entries that no longer exist.
- `policies/integrity.py`, `guarded_editor.py`, `audit/journal.py`,
  `tools/commands.py` — where *"a command is a list, never a string"*, because in
  a self-healing engine the values reaching a command come from tracebacks, which
  come from anywhere.
- `repo_graph.py`, `repo_map.py`, `symbol_index.py`, `capabilities_reach.py`,
  `blackboard.py`, `runtime.py`, `health.py`, `context.py`.

**Correction recorded against my own first measurement**: grepping for a
`self_healing/` directory returned nothing, which would have supported "GalSen IA
has no self-healing system". It has one; the directory is named `agent/`. A
subsystem is found by reading, not by guessing its path — and §10's instruction
not to replace the existing self-healing system stands on something real.

### Planning

`src/router/execution_planner.py` (`ExecutionPlanner`) plans agent execution.
This is *runtime* planning — which agent runs when — and is a different thing
from the *engineering* planning Superpowers' `writing-plans` addresses. §4-C must
not compare them as if they were the same layer.

### Scale, for §18 later

| | |
|---|---|
| ADRs | 38 |
| Test files | 333 |
| Rule files | 15 |
| Declared workflows | 8 |
| CI workflows | `tests.yml`, `release.yml` |

---

## PHASE 1.3 — GalSen IA reconnaissance: testing, verification, review, CI, git, security, ADRs

### Testing — measured by collection, not by counting files

```
python -m pytest --collect-only -q
→ 7036/7039 tests collected (3 deselected)
```

333 test files: 242 at the top level, plus seven suites
(`agent/`, `creative/`, `darra_j/`, `live_context/`, `media/`, `research/`).

**Seven of them test the repository itself rather than the product**, and they
are the ones that matter most to this audit because they are the mechanism a
methodology needs in order to be more than advice:

`test_published_numbers.py` (documentation may not contradict the served API),
`test_release_check.py`, `test_model_sovereignty.py`,
`test_sovereignty_subordinate_runtimes.py`, `test_knowledge_governance.py`,
`test_search_governance.py`, `test_package_documentation.py`.

### Verification — a written rule, and a gate

Three rule files carry it: `.claude/rules/verification.md` (when *a phase* is
done), `.claude/rules/post-integration-validation.md` (when *the platform* is
still whole — sixteen checks, run after every phase), and
`.claude/rules/spec-driven-governance.md` (the scope half of the same gate).

`verification.md` names five ways of making a test pass that are forbidden, one
of which — *"pinning a fabricated value"* — is recorded with the four real cases
that reached `main` before it was written. That is a methodology with a scar,
not a checklist.

### CI — `tests.yml`

Lint (`ruff check .`) → an import check that mirrors how the Dockerfile starts
the API → `pytest -q --durations=10` → a coverage report on `src/services`.
Plus `release.yml`.

### Review, debugging, git

- Review: `.claude/skills/review-changes`, backed by the `code-review-graph` MCP
  server (`CLAUDE.md` §"MCP Tools") — a persistent knowledge graph giving
  callers, dependents and test coverage.
- Debugging: `.claude/skills/debug-issue`, same graph.
- Git: `.claude/rules/git-workflow.md` — never push to `main`, feature branches,
  Conventional Commits.

### Security, approval, observability

`src/security/` (`trust.py`, `checkpoints.py`, `isolation.py`, `posture.py`,
`redaction.py`), `src/sandbox/` (`policy.py`, `runner.py`),
`src/approval_engine/` (5 modules), `src/audit_engine/` (5 modules),
`src/observability/trail.py`.

**38 ADRs.**

---

## PHASE 2.1 — What Superpowers is: licence, metadata, category

### It says what it is, and the repository agrees

> *"Superpowers is a complete software development methodology for your coding
> agents, built on top of a set of composable skills and some initial
> instructions that make sure your agent uses them."* — `README.md`

Measured, and the measurement is the whole answer to §3:

| | |
|---|---|
| Markdown | **93 files, 29 322 lines** |
| JS + TS + Python + MJS | 20 files, **4 012 lines** |
| Shell | 41 files — 33 under `tests/`, 4 under `scripts/`, 3 inside skills |
| Skills directory | **39 `.md`**, and 8 non-markdown files in total |
| Declared dependencies | **none** — no `dependencies`, `devDependencies`, `peerDependencies`, `optionalDependencies` or `engines` in `package.json` |
| Lockfile / `node_modules` | none |

**Superpowers is prose.** Roughly seven lines of methodology for every line of
code, and the code that exists is host adapters, hook shims and its own test
harness — not a library GalSen IA would call.

**Category, stated precisely as §3 requires:** it is a **plugin distributing an
engineering methodology as markdown skills to coding-agent CLIs**. It is not an
AI model, not an inference engine, not a foundation model, not a video generator,
not a production AI runtime — and, importantly for §5, **not a library either**.
There is no import surface. Nothing in GalSen IA's runtime could depend on it
even if someone wanted that.

### Licence

| | |
|---|---|
| `LICENSE` | **MIT**, 21 lines, `Copyright (c) 2025 Jesse Vincent` |
| `.claude-plugin/plugin.json` | `"license": "MIT"`, author `Jesse Vincent <jesse@fsck.com>` |
| `package.json` | version `6.3.0`, no `license` field — the licence is asserted by `LICENSE` and by `plugin.json`, which agree |

Read from the clone at `b36e0829`, not from a summary. §14's full matrix —
including the question of whether every bundled component inherits MIT, which
§14 explicitly forbids assuming — is chapter 10 and is not answered here.

### Host targets — thirteen, and one of them matters for §6

The README documents installation for Claude Code, Antigravity, Codex App, Codex
CLI, Cursor, Devin CLI, Factory Droid, Gemini CLI, GitHub Copilot CLI, Grok Build
CLI, Kimi Code, OpenCode, Pi and Hermes Agent. The repository root carries a
matching manifest for each (`.claude-plugin/`, `.codex-plugin/`, `.cursor-plugin/`,
`.devin-plugin/`, `.hermes-plugin/`, `.kimi-plugin/`, `.opencode/`, `.pi/`,
`gemini-extension.json`).

**This is host-agnostic by construction, and that answers a §6 question early**:
Superpowers is not a Claude dependency. It targets thirteen harnesses, and its
payload is markdown that any of them reads. The Claude-specific part is one
manifest among nine.

The README also carries a **"Commercial Services"** section, noted here and read
properly in chapter 12 (§16) rather than characterised now.

---

*Phases 1.1, 1.2, 1.3 and 2.1 complete. Phase 2.2 — `skills/`, `hooks/`,
bootstrap and update mechanism — has not started, and nothing below chapter 02
exists in this document yet.*
