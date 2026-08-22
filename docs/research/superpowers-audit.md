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

## PHASE 2.2 — skills, hooks, bootstrap, update mechanism

### The bootstrap — one hook, and it is the same idea GalSen IA already uses

`hooks/hooks.json` declares **exactly one hook**: `SessionStart`, matching
`startup|clear|compact`, running `hooks/run-hook.cmd session-start`.

`hooks/session-start` (49 lines of bash) does one thing: it reads
`skills/using-superpowers/SKILL.md` from disk, escapes it for JSON, and prints it
wrapped in `<EXTREMELY_IMPORTANT>` as the host's context-injection field. It
branches on three host conventions (`additional_context` for Cursor,
`hookSpecificOutput.additionalContext` for Claude Code, top-level
`additionalContext` for Copilot CLI and the SDK standard) because — its own
comment says — Claude Code reads both without de-duplicating.

**No network call. No state written. One local file read.**

This is worth stating plainly because it is the closest structural match in the
whole audit: GalSen IA's `SessionStart` hook runs `scripts/session_bootstrap.py`
and injects `docs/memory/session-state.md` and `docs/memory/phase-plan.md`. Same
event, same mechanism, different payload — Superpowers injects *how to work*,
GalSen IA injects *where the work stopped*. They are not competitors; they are
two uses of one hook.

`run-hook.cmd` is a bash/batch polyglot so Windows hosts find Git Bash. On no
bash it exits 0 silently rather than failing — a deliberate degradation.

### Update mechanism

The README's entire answer: *"Superpowers updates are somewhat coding-agent
dependent, but are often automatic."* For Claude Code it is the plugin
marketplace (`/plugin install superpowers@claude-plugins-official`).

**This is an integration-relevant fact, not a footnote.** An auto-updating source
of instructions is a supply-chain surface: the text that steers a coding agent
can change without a review. §13 will weigh it; recorded here where it was found.

### Telemetry — found while reading the update section, verified in code

The README declares it, so the README is not the evidence. Read at
`skills/brainstorming/scripts/server.cjs:106-112, 244-249`:

```js
const SUPERPOWERS_BRAND_IMAGE_URL =
  'https://primeradiant.com/brand/superpowers-visual-brainstorming-logo.png';
const TELEMETRY_DISABLE_ENV_VARS = [
  'SUPERPOWERS_DISABLE_TELEMETRY', 'DISABLE_TELEMETRY',
  'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'];
…
: '<img class="brand-logo" src="' + SUPERPOWERS_BRAND_IMAGE_URL + '?v='
  + encodeURIComponent(SUPERPOWERS_VERSION) + '" … referrerpolicy="no-referrer">'
```

Measured, precisely:

- It is **one remote `<img>`**, in **one skill** (`brainstorming`'s optional
  visual companion), carrying **the Superpowers version** as `?v=` and nothing
  else the page controls.
- `referrerpolicy="no-referrer"` is set — which matters more than it looks: the
  companion's own URL carries a per-session secret key, and no-referrer keeps it
  out of the outbound request.
- The three opt-outs exist in code and are **covered by four tests**
  (`tests/brainstorm-server/branding.test.js`).
- Grepping every executable file for outbound URLs found **six**, and apart from
  this one they are all `github.com/obra/superpowers` links inside a release
  script.

**The README's claim survives verification.** What still leaves the machine when
enabled is what any HTTP GET carries — source IP, browser user-agent, timestamp,
version — which is not nothing, and §16's judgement belongs in chapter 12.

### Skill shape

39 markdown files under `skills/`, plus 8 non-markdown (2 `js`, 3 `sh`, 1 `ts`,
1 `cjs`, 1 `html`, 1 `dot`, and three extensionless scripts under
`subagent-driven-development/scripts/`). Sizes range from 63 lines
(`using-superpowers`) to 568 (`subagent-driven-development`).

---

## PHASE 3.1 — Architectural comparison, areas A to H

Each area answers §4's nine questions. Where the answer is the same across
several areas it is said once, not repeated to look thorough.

### A. Agent architecture

| | |
|---|---|
| GalSen IA | 17 agents declared in `agents/registry.yaml`, loaded by `src/router/agent_loader.py`, dispatched by `agent_dispatcher.py`, aggregated by `result_aggregator.py`. **Runtime agents of a product.** |
| Superpowers | No agent registry. Its "agents" are the host CLI itself, steered by prose. `.agents/plugins` is host wiring. |
| Better? | **Not comparable.** These are different layers: GalSen IA's agents serve users at runtime; Superpowers steers the developer's coding agent. |
| Duplication | None. |
| Conflict | None. |
| Native? | N/A |
| Import needed? | **No.** |

### B. Skill architecture

| | |
|---|---|
| GalSen IA | 14 skills, `SKILL.md` + YAML front-matter, `.claude/skills/`. |
| Superpowers | 14 skills, `SKILL.md` + YAML front-matter, `skills/`. |
| Better? | **The format is identical.** The difference is content and one mechanism: Superpowers' `using-superpowers` skill is force-injected at session start, so the agent is told the skills exist before it can forget. GalSen IA's skills wait to be invoked. |
| Duplication | Format: total. Content: near-zero overlap — GalSen IA's are graph-navigation and Spec Kit; Superpowers' are methodology. |
| Conflict | None. Both are development-time. |
| Native? | **Yes, trivially** — a skill is a markdown file in a directory that already exists. |
| Import needed? | **No.** |

### C. Planning

Two different meanings of the word, and conflating them would be the easiest
error in this audit.

| | |
|---|---|
| GalSen IA, runtime | `src/router/execution_planner.py` — which agent runs when. |
| GalSen IA, engineering | `.claude/rules/phase-protocol.md` — VOLET → chapters → phases, one phase per turn, plan written to `docs/memory/phase-plan.md`, injected at session start, ending every phase with an explicit stop. |
| Superpowers | `writing-plans` (171 lines) + `executing-plans` — spec to plan to execution. |
| Better? | **GalSen IA's is stronger on one axis and weaker on another.** Stronger: its plan is persisted, injected at session start, and survives an interrupted session — this document exists because of it. Weaker: it says nothing about how a plan is *written* from a spec, which is exactly `writing-plans`' subject. |
| Duplication | Partial and complementary, not redundant. |
| Native? | Yes. |

### D. Specification workflow

| | |
|---|---|
| GalSen IA | Ten `speckit-*` skills (specify, clarify, plan, tasks, analyze, implement, checklist, constitution, converge, taskstoissues) plus `.specify/memory/constitution.md` and `.claude/rules/spec-driven-governance.md`. |
| Superpowers | `brainstorming` (250 lines) — a *pre-spec* phase: explore the problem before creating anything. |
| Better? | Different position in the pipeline. Spec Kit starts at "write the spec"; `brainstorming` starts before that. GalSen IA's governance rule says *"When a request is ambiguous and the ambiguity materially changes the implementation, ask"* — the intent exists; the method does not. |
| Duplication | Low. |

### E. TDD

| | |
|---|---|
| GalSen IA | `.claude/rules/testing.md` — pytest, fixtures, 80 % target, "write tests before or alongside implementation (TDD/TDD-like)". |
| Superpowers | `test-driven-development` (320 lines) — a hard sequence, not an aspiration. |
| Better? | **Superpowers is stricter.** "TDD-like" is a preference; a red-green gate is a rule. |
| Native? | Yes — it is prose. |

### F. Debugging

| | |
|---|---|
| GalSen IA | `.claude/skills/debug-issue` (graph-powered navigation) + `.claude/rules/verification.md`'s regression clause: *"If something that worked stops working after your change, that is your change until proven otherwise. Find the cause; do not work around the symptom."* |
| Superpowers | `systematic-debugging` (283 lines): an Iron Law, four named phases (root-cause investigation → pattern analysis → hypothesis and testing → implementation), red flags, and a section on common rationalisations. |
| Better? | **GalSen IA has the principle; Superpowers has the procedure.** One sentence versus four phases. This is the clearest single gap found so far. |
| Duplication | The principle, yes. The method, no. |
| Native? | Yes. |

### G. Verification

| | |
|---|---|
| GalSen IA | Three rule files — `verification.md` (definition of done, four items), `post-integration-validation.md` (sixteen checks after every phase), `spec-driven-governance.md` (the scope half). Plus seven repository-level tests that *enforce* rather than advise. |
| Superpowers | `verification-before-completion` (120 lines): *"NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE"*, a five-step gate function, and a table of claims against what actually proves them. |
| Better? | **GalSen IA is stronger overall — it has tests, and Superpowers has only prose.** But Superpowers has one thing GalSen IA does not write down: the *freshness* requirement. *"If you haven't run the verification command in this message, you cannot claim it passes."* GalSen IA's rule says run it "in this session". A session is long. |
| Duplication | High. |
| Native? | Yes — a one-line amendment to an existing rule. |

### H. Code review

| | |
|---|---|
| GalSen IA | `.claude/skills/review-changes` + the `code-review-graph` MCP server: callers, dependents, test coverage, risk-scored change detection. |
| Superpowers | `requesting-code-review` (95 lines) and `receiving-code-review` — the *social* protocol: how to ask, and how to take an answer without defending. |
| Better? | **Orthogonal.** GalSen IA has the machinery for finding what a change touches; Superpowers has the discipline for what to do with a review once it exists. Neither replaces the other. |
| Duplication | None. |

---

## PHASE 3.2 — Architectural comparison, areas I to P

### I. Subagent orchestration

| | |
|---|---|
| GalSen IA | `src/router/agent_dispatcher.py` dispatches declared agents; `result_aggregator.py` merges; `src/agent/blackboard.py` gives them a shared work state — publish under a subject, with sender and optional recipient, so an agent reads what concerns it instead of guessing a position in a list. |
| Superpowers | `subagent-driven-development` (568 lines) — the most elaborate skill in the repository. Per task: dispatch implementer → implementer implements, tests, commits, self-reviews → generate review package → dispatch task reviewer → **bounded fix loop, 5 rounds, and at round ≥ 4 a fresh implementer on a more capable model** → adjudicate residual findings → append completion to a **ledger**. |
| Better? | **Superpowers is materially stronger here, and it is the single largest gap in the audit.** GalSen IA dispatches agents and merges results. It has no reviewer-of-the-implementer, no bounded retry with escalation, no adjudication of findings that survive the loop. |
| Duplication | The dispatch mechanism, yes. The *loop around it*, no. |
| Conflict | **One, and it is real.** See "human approval" (area T) below. |
| Native? | Yes — it is a procedure, expressible as a workflow in `workflows/workflows.yaml` plus a skill. |
| Import needed? | **No.** |

### J. Parallel execution

| | |
|---|---|
| GalSen IA | Measured, not assumed: `src/router/execution_planner.py:61` sets `'parallel_supported': False`. Workflows may *declare* `parallel_agents`; nothing runs them in parallel. |
| Superpowers | `dispatching-parallel-agents` (167 lines): identify independent domains → focused agent tasks → dispatch in parallel → review and integrate, with a prescribed prompt structure. |
| Better? | **Yes, on a capability GalSen IA does not have.** |
| Honest caveat | The gap is not the *procedure*, it is the runtime. A skill describing parallel dispatch cannot make `parallel_supported` true. Adopting the skill without building the runtime would document a capability that does not exist — precisely what this repository's rules forbid. |

### K. Git / worktree workflow

| | |
|---|---|
| GalSen IA | `.claude/rules/git-workflow.md`: never push to `main`, feature branches, Conventional Commits. No worktree practice. |
| Superpowers | `using-git-worktrees` — detect existing isolation first, native tools preferred, git-worktree fallback, directory selection, safety verification. `finishing-a-development-branch` — verify tests → detect environment → determine base → present options → execute. |
| Better? | **Superpowers is more complete**, and `finishing-a-development-branch` step 1 is *verify tests*, which is the step this session has been performing by hand every time. |
| Native? | Yes. |

### L. Memory

| | |
|---|---|
| GalSen IA | Two distinct memories: `src/memory_engine/` (12 modules — the product's memory of user content) and `docs/memory/` (the repository's engineering memory — `session-state.md`, `phase-plan.md`, `completed-work.md`, `pending-work.md`, `priorities.md`, injected at session start by a hook, governed by `.claude/rules/memory.md`). |
| Superpowers | **Nothing comparable.** Grepping every skill for memory or persistence returns the ledger and the brainstorming server's session files. The ledger is per-plan working state, deleted when the plan's workspace is deleted. |
| Better? | **GalSen IA, decisively.** Its engineering memory survives sessions, containers and context exhaustion. Superpowers' ledger survives one plan. |
| Duplication | None. |
| §12's instruction — "do not introduce redundant memory systems" — is satisfied by doing nothing here. |

### M. Context management

| | |
|---|---|
| GalSen IA | Context isolation per agent (`src/agent/context.py`); the session hook re-establishes state after a compaction. |
| Superpowers | Context isolation is the *point* of subagent-driven development: each implementer starts fresh, and the ledger carries what must survive. `using-superpowers` is force-injected on `startup\|clear\|compact` — deliberately including compaction. |
| Better? | Comparable, by different means. |
| Useful complement | **One, small and real**: GalSen IA's hook matches session start; Superpowers' also matches `clear` and `compact`. A methodology that evaporates on compaction is a methodology for short sessions. |

### N. Hooks

| | |
|---|---|
| GalSen IA | Two events — `SessionStart` (inject memory), `PostToolUse`. |
| Superpowers | One event — `SessionStart`, matching `startup\|clear\|compact`. |
| Better? | GalSen IA uses more events; Superpowers uses one event more thoroughly. |
| Duplication | **Direct.** Both inject context at session start. They would coexist — the host concatenates — but the payloads must not contradict each other. |

### O. Security

| | |
|---|---|
| GalSen IA | `src/security/` (`trust.py` — external text is data with an origin, never an instruction; `checkpoints.py`, `isolation.py`, `posture.py`, `redaction.py`), `src/sandbox/` (`policy.py`, `runner.py`), `src/agent/policies/immutability.py` (what an autonomous repair may never touch, derived from the architecture rather than written from memory), `guarded_editor.py`, an audit journal, and ADR-018's unconditional refusals. |
| Superpowers | No security model. It is markdown. Its only security-relevant artefacts are the brainstorming server's per-session key, loopback default and `chmod 600`. |
| Better? | **GalSen IA, by an enormous margin — and the comparison is not really fair, because Superpowers is not trying to have one.** |
| Conflict | Adopting Superpowers' *prose* introduces no security surface. Adopting its *distribution mechanism* — an auto-updating marketplace plugin injecting `<EXTREMELY_IMPORTANT>` instructions at every session start — introduces one, and §13 will name it. |

### P. Permissions

| | |
|---|---|
| GalSen IA | `src/api/rbac.py` — 10 roles, 24 permissions, `PERMISSIONS_HORS_PLATEFORME`; `src/tool/authorization.py` — role ceilings over declared tool capabilities. |
| Superpowers | None, and none is expected. |
| Better? | Not comparable. |
| Import needed? | **No.** |

---

## PHASE 3.3 — Architectural comparison, areas Q to X

### Q. Observability

GalSen IA: `src/observability/trail.py` (one job followable end to end via
`/observability/trail/{id}`), `src/audit_engine/` (5 modules),
`src/router/decision_trace.py`, `workflow_history.py`.
Superpowers: the ledger, and prose telling the agent to report.
**GalSen IA, decisively.** No gap.

### R. Self-healing

GalSen IA: `src/agent/` — 23 modules, `self_healer.py`, immutability and
integrity policies, a guarded editor, an audit journal, commands passed as lists
so a traceback cannot become shell syntax.
Superpowers: `systematic-debugging` is a *method for a human-supervised agent*,
not an autonomous repair engine. **Different things.**
The useful complement is the one already named in area F: four named phases where
GalSen IA has one sentence. §10 forbids replacing the engine; nothing here
suggests replacing it.

### S. Autonomous execution

GalSen IA: routines fire workflows through the one orchestrator; unattended tool
execution is gated by declared `unattended` capability, and *"an approval is never
granted by the absence of someone to refuse it"*.
Superpowers: *"Do not pause to check in with your human partner between tasks…
'Should I continue?' prompts and progress summaries waste their time."*
**This is a direct philosophical conflict with `.claude/rules/phase-protocol.md`**,
which mandates one phase per turn, each ending in `Je continue ?`.
Recorded here, adjudicated in area T.

### T. Human approval

| | |
|---|---|
| GalSen IA | `src/approval_engine/` (5 modules), ADR-006, ADR-018's unconditional refusals evaluated *before* consent, tools declaring `requires_approval`, role ceilings, and the phase protocol's stop after every phase. |
| Superpowers | *"Rulings, not stalls."* Four things stop the agent and only these: an irreversible or destructive operation; a security-sensitive action; a side effect outside the worktree that norms say you ask about (merge, push to a shared branch, publish); a plan so broken every path forward is a guess. Everything else: decide, record `Ruling: <what> — <why> — <what it costs if wrong>`, continue. |

**This is the audit's sharpest finding, and it cuts both ways.**

Superpowers' four stop conditions are *well chosen* — they are close to what
ADR-018 and the approval engine already enforce, arrived at independently. And
its ledger entry format is better than anything GalSen IA writes down: naming
**what it costs if the ruling is wrong** is a discipline this repository does not
currently require.

But *"do not pause between tasks"* is the exact opposite of the phase protocol,
which the owner made permanent and which is not the assistant's to renegotiate.
`.claude/rules/spec-driven-governance.md` settles it: *"If a proposed change
conflicts with an existing architectural rule: stop, document the conflict, and
do not silently override it."*

**So: the ruling format is adoptable; the no-stopping cadence is not.** Any
integration candidate touching this area must separate the two, and a candidate
that imports `subagent-driven-development` wholesale would import the conflict.

### U. Failure recovery

GalSen IA: `retry_manager.py`, `workflow_checkpoint.py` with `resumable()`,
`done_agents()`, `next_step()` — a run resumes where it stopped.
Superpowers: the bounded fix loop (5 rounds, escalating model), and adjudication
of what survives it.
**Complementary.** GalSen IA recovers *runs*; Superpowers recovers *quality*.
Neither does the other's job.

### V. Testing

GalSen IA: 7 036 tests, 333 files, seven of which test the repository itself;
`.claude/rules/verification.md` names five forbidden ways to make a test pass.
Superpowers: `test-driven-development` (320 lines, a red-green gate) and
`writing-skills/testing-skills-with-subagents.md` — **testing a skill by
dispatching a subagent to follow it**, which is a technique GalSen IA has no
equivalent of and which is directly relevant to its own 15 rule files.
**GalSen IA is stronger on product tests; Superpowers has one technique GalSen IA
lacks entirely.**

### W. Documentation

GalSen IA: 38 ADRs, `.claude/rules/documentation.md`, `test_package_documentation.py`,
`test_published_numbers.py` — documentation that contradicts the served API fails CI.
Superpowers: no documentation discipline of its own beyond its skills being prose.
**GalSen IA, decisively.** No gap.

### X. Long-running tasks

GalSen IA: checkpointed resumable runs, plus `docs/memory/` and the phase plan,
which is why an interrupted session resumes at the right phase.
Superpowers: the ledger, per plan.
**GalSen IA, decisively**, and it is the same strength as area L.

---

## Interim tally, areas A–X

Not a conclusion — chapters 04 to 16 have not run. Stated so the shape is visible:

| | Count | Areas |
|---|---|---|
| GalSen IA already stronger | **9** | L memory, O security, P permissions, Q observability, R self-healing (engine), U (runs), V (product tests), W documentation, X long-running |
| Superpowers materially stronger | **5** | I subagents, J parallel dispatch, K git/worktree, and the *procedures* in F debugging and E TDD |
| Orthogonal / complementary | **6** | A agents, C planning, D spec, H code review, M context, U (quality) |
| Direct conflict | **1** | S/T — autonomous cadence versus the phase protocol |
| No comparison possible | **3** | B format (identical), N hooks (same mechanism), G verification (same intent, one freshness clause differs) |

---

## PHASE 4.1 — The real skill inventory

Counted from the clone. Sizes matter here: a 63-line skill and a 679-line skill
are not the same kind of object, and §7 asked for the inventory rather than a
list of names.

| Skill | SKILL.md | Auxiliary files |
|---|---:|---:|
| `writing-skills` | **679** | 6 |
| `subagent-driven-development` | **568** | 6 |
| `test-driven-development` | 320 | 1 |
| `systematic-debugging` | 283 | 10 |
| `brainstorming` | 250 | 7 |
| `finishing-a-development-branch` | 225 | 0 |
| `receiving-code-review` | 205 | 0 |
| `writing-plans` | 171 | 1 |
| `dispatching-parallel-agents` | 167 | 0 |
| `using-git-worktrees` | 167 | 0 |
| `verification-before-completion` | 120 | 0 |
| `requesting-code-review` | 95 | 1 |
| `executing-plans` | 64 | 0 |
| `using-superpowers` | 63 | 5 |

**Two observations that change how the next phase reads.**

The two largest skills are **about the system itself** — how to write skills, and
how to run subagents. Nearly a quarter of the prose is meta. That is not padding:
it is where a methodology keeps itself from decaying.

And `executing-plans` (64 lines) opens by telling the agent to use a *different*
skill if subagents are available. Several skills are entry points that delegate.
Adopting one in isolation can therefore silently pull in its `REQUIRED SUB-SKILL`
chain — `executing-plans` requires `finishing-a-development-branch`;
`testing-skills-with-subagents` requires `test-driven-development`. **A candidate
list must name the closure, not the skill.**

---

## PHASE 4.2 — Skill by skill: equivalent → gap → value → compatibility → cost → recommendation

`RECOMMENDATION` uses §5's vocabulary: **A** reuse the concept · **B** adapt ·
**C** reimplement natively · **D** integrate a small isolated component ·
**E** import the whole component · **F** do nothing.

No candidate below is `E`. Nothing in this repository can import markdown; the
only meaningful acts are *adopt the idea natively* or *do nothing*.

### The five worth adopting

**1. `systematic-debugging` — 283 lines**
GalSen equivalent: `.claude/rules/verification.md`'s regression clause (one
sentence) + `.claude/skills/debug-issue` (graph navigation, not method).
Gap: **the procedure**. Four named phases, red flags, and a table of common
rationalisations. GalSen IA states the principle and leaves the method to
judgement.
Value: **high** — this session's own vector-store fix followed roughly these
phases by instinct, and a written procedure would have made that repeatable
rather than lucky.
Compatibility: total, no conflict.
Cost: **low** — one skill or one rule section.
**RECOMMENDATION: C (reimplement natively).**

**2. `verification-before-completion` — 120 lines**
GalSen equivalent: three rule files *and* seven repository-level tests. GalSen IA
is stronger overall.
Gap: **exactly one clause** — *"If you haven't run the verification command in
this message, you cannot claim it passes."* `verification.md` says "in this
session". A session is long; the gap is real and narrow.
Value: **medium-high**, out of proportion to its size.
Cost: **one sentence** amending an existing rule.
**RECOMMENDATION: A (reuse the concept) — the freshness clause only.** The rest
duplicates what already exists and would dilute it.

**3. `writing-skills/testing-skills-with-subagents` — a technique, not a skill**
GalSen equivalent: **none.** GalSen IA has 15 rule files and no way to know
whether any of them changes behaviour.
Gap: RED-GREEN-REFACTOR applied to process documentation — run the scenario
*without* the rule, document the exact rationalisations, write the rule against
those, verify compliance, then hunt new loopholes. *"If you didn't watch an agent
fail without the skill, you don't know if the skill prevents the right failures."*
Value: **the highest single item in this audit**, and the least obvious. This
repository's whole discipline is *sabotage the guard before believing it* — this
is that discipline applied to prose instead of code. The rules have never been
subjected to it.
Compatibility: total.
Cost: **medium** — needs subagent dispatch, which exists.
**RECOMMENDATION: C (reimplement natively).**

**4. `subagent-driven-development` — 568 lines, adopted in parts**
Gap: reviewer-of-the-implementer; bounded fix loop (5 rounds, fresh implementer
on a stronger model at R ≥ 4); adjudication of surviving findings; the ledger
entry format `Ruling: <what> — <why> — <what it costs if wrong>`.
Value: **high** for the loop and the ruling format.
**Conflict: yes, and it is load-bearing.** *"Do not pause to check in between
tasks"* contradicts `.claude/rules/phase-protocol.md`, which the owner made
permanent.
Cost: medium.
**RECOMMENDATION: B (adapt) — the review loop and the ruling format, with the
cadence explicitly excluded.** Importing the skill whole would import the
conflict, which is why the recommendation is B and not A.

**5. `finishing-a-development-branch` — 225 lines**
GalSen equivalent: `.claude/rules/git-workflow.md` — branch naming and commit
style, nothing about *ending* a branch.
Gap: verify tests → detect environment → determine base → present options →
execute. Step 1 is *verify tests*.
Value: **medium**, and concrete: every merge in this session performed these
steps by hand, and the one thing that made them safe was doing them in the same
order every time.
Cost: low.
**RECOMMENDATION: C (reimplement natively).**

### Three worth considering, none urgent

**6. `test-driven-development`** — GalSen IA's `testing.md` says "TDD or
TDD-like", which is a preference. Superpowers' is a gate. Value medium;
**RECOMMENDATION: A**, tightening one sentence rather than adding 320 lines.

**7. `receiving-code-review`** — a response pattern (read → understand → verify →
evaluate → respond → implement) and a list of forbidden responses, *"You're
absolutely right!"* among them. GalSen equivalent: none; `response-style.md` bans
praise but says nothing about how to take a review. Value medium.
**RECOMMENDATION: A.**

**8. `writing-plans`** — GalSen IA's phase protocol governs plan *structure* and
*persistence* and is stronger there; `writing-plans` covers how a plan is derived
from a spec, which the protocol does not. Narrow, real gap.
**RECOMMENDATION: B (adapt into the existing phase protocol), low priority.**

### Six where GalSen IA should do nothing

| Skill | Why |
|---|---|
| `using-superpowers` | Its whole purpose is bootstrapping Superpowers. Adopting it without Superpowers is meaningless. **F.** |
| `executing-plans` | 64 lines that mostly delegate; the phase protocol already covers execution and is stronger (persisted plan, resumable). **F.** |
| `dispatching-parallel-agents` | The procedure is sound and `parallel_supported` is `False`. Adopting it would document a capability that does not exist — the exact failure `.claude/rules/verification.md` forbids. **F until the runtime exists**, then reconsider. |
| `using-git-worktrees` | Genuinely useful, and this environment is a single ephemeral container with one checkout. The value is real and unrealised *here*. **F for now**, recorded rather than dismissed. |
| `requesting-code-review` | `code-review-graph` + `review-changes` cover the mechanics better. The social half is in `receiving-code-review`, already listed. **F.** |
| `brainstorming` | 250 lines plus a Node visual companion — and **the only telemetry surface in the repository**. Its pre-spec exploration is a real gap beside Spec Kit, but the component carrying it is the one component with a network call. **F for the component; the concept alone could return as B later.** |

---

## CHAPTER 05 (§9) — Testing methodology

### What each side actually tests

| | GalSen IA | Superpowers |
|---|---|---|
| Tests of the product | **7 036**, 333 files, pytest | none — there is no product |
| Tests of the repository's own rules | **7 files** (published numbers, release check, model sovereignty, subordinate runtimes, knowledge & search governance, package documentation) | **60 files** under `tests/`, per host harness |
| Tests of *whether an instruction changes behaviour* | **zero** | present, and this is the finding |

### The technique GalSen IA does not have

Beside `skills/systematic-debugging/SKILL.md` sit `test-pressure-1.md`,
`test-pressure-2.md`, `test-pressure-3.md`, `test-academic.md` and a
`CREATION-LOG.md`. The pressure tests are scenarios written to make an agent
*want* to break the rule. Pressure test 1 opens:

> *"Production API is down… Error rate: 100%. Revenue loss: \$15,000/minute…
> Your manager pings you: 'FIX IT NOW.'… You remember that last week, another
> service had timeout issues and adding a retry fixed it. That took 2 minutes."*

The scenario supplies the rationalisation, then measures whether the skill holds.
`writing-skills` states the method as TDD:

| TDD | Skill creation |
|---|---|
| Test fails (RED) | Agent violates the rule **without** the skill — baseline |
| Test passes (GREEN) | Agent complies with the skill present |
| Refactor | Close loopholes while maintaining compliance |

> *"If you didn't watch an agent fail without the skill, you don't know if the
> skill prevents the right failures."*

### The judgement §9 asks for

**Does it improve GalSen IA's unit, integration, regression, provider,
orchestration or end-to-end tests? No.** Those are Python tests of a Python
product, 7 036 of them, and Superpowers has nothing to say about them. On every
category §9 lists except one, GalSen IA is ahead and there is nothing to take.

**Does it improve *skill and agent-behaviour* tests? Yes — from zero.** GalSen IA
has 15 rule files, 14 skills and a `CLAUDE.md`, and **not one line of evidence
that any of them changes what an agent does.** They were written, committed, and
believed.

That asymmetry is the whole chapter. This repository's core discipline is that a
guard is not trusted until it has been sabotaged and seen to go red — applied
rigorously to code, and never once applied to the prose that governs the code.
`.claude/rules/verification.md` forbids *"pinning a fabricated value"* and cites
four real cases; nobody has ever checked whether that rule prevents anything.

Superpowers' own artefacts show the method is affordable: three pressure files
and a creation log beside one skill.

**No test may be deleted or weakened** (§9). Nothing here proposes touching an
existing test; the candidate is an entirely new category.

---

## CHAPTER 06 (§10) — Debugging methodology

### The four phases, and what GalSen IA has instead

Superpowers' `systematic-debugging`: **Phase 1 Root-cause investigation** (read
the error completely; reproduce consistently — *"if not reproducible → gather
more data, don't guess"*; check recent changes; in multi-component systems,
instrument every boundary **before** proposing a fix) → **Phase 2 Pattern
analysis** → **Phase 3 Hypothesis and testing** → **Phase 4 Implementation**.
Plus red flags, rationalisations, and `find-polluter.sh` (a real script, with its
own test) for locating the test that pollutes another.

GalSen IA has: one sentence in `verification.md` — *"If something that worked
stops working after your change, that is your change until proven otherwise. Find
the cause; do not work around the symptom"* — and `.claude/skills/debug-issue`,
which is graph navigation rather than method.

**The principle is identical. The procedure exists on one side only.**

### Does GalSen IA need it? Measured against its own history

This session produced three cases, and they answer the question better than an
opinion would:

1. **The vector store.** Measured before (49.4 ms), formed a hypothesis about
   why, ran a five-line experiment to settle `PRAGMA data_version` rather than
   reading documentation about it, fixed, re-measured (0.463 ms). That is
   Phase 1 → 3 → 4, executed by instinct.
2. **The 40 failures.** The tempting move was to assume the change caused them.
   Instead: stash, measure the untouched baseline on the same machine, find
   `bcrypt` missing. That is Phase 1's *"check recent changes"* and
   *"reproduce consistently"*, again by instinct.
3. **The failed sabotage.** A guard did not fire; the first conclusion available
   was "the test is wrong". It was not — the appended line had glued onto the
   previous one because the file lacked a trailing newline. Phase 1's *"read the
   error completely"* is exactly what caught it.

Three for three by instinct is not a process. **The gap is repeatability, not
capability** — and an instinct that works when the operator is careful is the
kind of thing that fails on the day they are not.

### §10's constraint, honoured

*"Do NOT replace the existing self-healing system."* Nothing here proposes to.
`src/agent/` is an **autonomous repair engine** — immutability policies, guarded
editor, audit journal, commands as lists. `systematic-debugging` is a **method
for a supervised agent**. They occupy different layers, and the useful move is to
give `src/agent/`'s human-facing companion a written procedure it currently
lacks — not to touch `self_healer.py`.

### Where it would land

`.claude/rules/verification.md` already owns the regression clause; the procedure
belongs beside it or as a skill invoked by it. `find-polluter.sh` is a separate,
smaller question: a shell script with a real test, MIT-licensed, solving a problem
(*which test pollutes this one?*) that a 7 036-test suite will eventually have.
**That is the only candidate in this entire audit for §5's option D — integrate a
small isolated component** — and it is recorded, not recommended, until chapter 10
clears its licence individually.

---

*Phases 1.1 → 06 complete (12 of 24). Chapter 07 (§11 — subagents) has not
started.*
