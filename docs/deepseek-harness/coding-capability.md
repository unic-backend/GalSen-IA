# D05 — Coding capability evaluation (Phase 3)

**Measured**: 2026-08-20. GalSen IA figures are reproducible — the command is
given. DSH figures are declarations read from official sources, labelled as
such.

Phase 3's warning governs this phase: *"Do not simply accept claims that it is
'the best coding agent'."* And the final report's rule: *never claim "best coding
model" without comparative evidence*.

---

# D05.1 — What DSH declares, and what it publishes

## The tool catalogue is a coding agent's catalogue

From `docs/tool-catalog.md`, VERIFIED FROM OFFICIAL SOURCE (D04):

`bash`, `pwsh`, `read`, `write`, `edit`, `str_replace_editor`, `read_image`,
`glob`, `grep`, `lsp`, six `terminal_*` tools for persistent PTYs, `run_code`
(*"Execute TypeScript programs against available tools with top-level await"*),
`subagent`, `workflow`, `ralph` (*"Run fresh-agent loops toward immutable
objectives"*), `create_goal`/`get_goal`/`update_goal`, three `schedule_*`, five
`session_*` query and trace tools, `job_kill`/`job_list`/`job_output`,
`todo_write`, `skill`, `web_search`, `web_fetch`.

**Roughly fifty tools, and their centre of gravity is a repository.**

## Its own benchmark file publishes no results

`BENCHMARK.md` exists at repository root. Read 2026-08-20:

> **NO SCORES PUBLISHED.**

It is a **how-to-run** document — *"Follow Get started with the Python SDK to
install the SDK and run the `jsonrpc-agent` minimal variant"*, and *"Use separate
workspaces and session IDs for independent benchmark tasks"* — with no suites
named, no scores, no comparison, and no methodology statement.

`INFERENCE`, and it is the whole of D05.1's verdict: **the repository contains
no comparative evidence about coding quality.** Not weak evidence — none. Any
claim that DSH is a better coding agent therefore cannot be sourced from the
project's own repository, which is exactly the claim Phase 3 says not to accept
uncritically.

This is **not** a criticism of the project. Publishing a benchmark *harness*
rather than benchmark *marketing* is defensible, and arguably more honest than a
scores table with no reproduction path. But it means Phase 3's thirteen axes
cannot be answered from the source.

---

# D05.2 — What GalSen IA has, measured

## The three declared engines, and their state

Reproducible — this is the command:

```bash
python -c "
from src.coding_engine.adapters.aider_adapter import AiderAdapter
from src.coding_engine.adapters.openhands_adapter import OpenHandsAdapter
from src.coding_engine.adapters.swe_agent_adapter import SweAgentAdapter
for cls in (AiderAdapter, OpenHandsAdapter, SweAgentAdapter):
    print(cls().check_availability())"
```

Result, 2026-08-20:

| Engine | Primary capability | Available | Reason | Repair named |
|---|---|---|---|---|
| `aider` | `targeted_edit` | **False** | `not_installed` | `pip install aider-install && aider-install`, or `GALSEN_AIDER_BIN` |
| `openhands` | `autonomous_implementation` | **False** | `not_configured` | run the agent server, then `GALSEN_OPENHANDS_URL` |
| `swe_agent` | `issue_resolution` | **False** | `not_installed` | `pip install sweagent`, or `GALSEN_SWE_AGENT_BIN` |

**Three declared, zero available, and every unavailability names its repair.**
That is the platform's own discipline working: an absent capability reports its
state and what would fix it, rather than returning a plausible result.

## Declared capability coverage — the one comparison that can be made

`CodingCapability` has six values. Mapping DSH's tool catalogue onto them:

| Capability | `aider` | `openhands` | `swe_agent` | **DSH** (inferred from its tools) |
|---|---|---|---|---|
| `targeted_edit` | ✓ | ✓ | ✓ | ✓ — `edit`, `str_replace_editor`, `write` |
| `repository_exploration` | ✓ | ✓ | ✓ | ✓ — `glob`, `grep`, `read`, **`lsp`** |
| `test_execution` | ✓ | ✓ | — | ✓ — via `bash` |
| `shell_execution` | — | ✓ | ✓ | ✓ — `bash`, `pwsh`, six `terminal_*` |
| `autonomous_implementation` | — | ✓ | — | ✓ — `ralph`, `create_goal`, `workflow`, `subagent` |
| `issue_resolution` | — | ✓ | ✓ | **`UNKNOWN`** — no tool names it |

**The DSH column is `INFERENCE`**, derived from tool names, not from a
capability declaration DSH makes. It is labelled here and must stay labelled: a
tool called `bash` *can* run tests; that a harness *does* test execution well is
a different claim and one nothing measured.

**Two observations that are not inferences.**

`lsp` is real and named — *"Query language servers for code navigation"*. None
of the three existing adapters declares a language-server path; `src/agent/`
has `repo_map.py`, `repo_graph.py` and `symbol_index.py`, which solve a
neighbouring problem by other means. **That is a genuine capability difference**,
not a repackaging.

**Six persistent-PTY tools** (`terminal_open/close/send/read/list/signal`) are
also unmatched here. `src/tools/terminal/` exists and runs commands; a
*persistent* terminal session is a different thing, and rc.8's notes add
*"persistent PowerShell session support for Windows"*.

## Phase 3's thirteen axes

| Axis | GalSen IA | DSH |
|---|---|---|
| repository understanding | `NOT_MEASURED` — no engine available | `NOT_MEASURED` — not installed |
| multi-file changes | `NOT_MEASURED` | `NOT_MEASURED` |
| tool use | `NOT_MEASURED` | `NOT_MEASURED` |
| debugging | `NOT_MEASURED` | `NOT_MEASURED` |
| test generation | `NOT_MEASURED` | `NOT_MEASURED` |
| test repair | `NOT_MEASURED` | `NOT_MEASURED` |
| autonomous loops | `NOT_MEASURED` | `NOT_MEASURED` |
| context handling | `NOT_MEASURED` | `NOT_MEASURED` |
| long-running tasks | `NOT_MEASURED` | `NOT_MEASURED` |
| recovery from failure | `NOT_MEASURED` | `NOT_MEASURED` |
| structured output | `NOT_MEASURED` | `NOT_MEASURED` |
| code quality | `NOT_MEASURED` | `NOT_MEASURED` |
| regression rate | `NOT_MEASURED` | `NOT_MEASURED` |

**Twenty-six cells, twenty-six `NOT_MEASURED`**, and the reasons differ by
column: our engines are declared and uninstalled; DSH is not installed because
the directive forbids it. Neither column is zero, and neither is an estimate.

The plan predicted this shape before the phase ran, and it held: *"D05 will most
likely produce a comparison of declared capabilities against measured absence on
both sides."*

## The architectural finding, which does not depend on any benchmark

`src/coding_engine/router.py`, VERIFIED FROM REPOSITORY:

> *"Le routeur ne connaît **aucun** des trois moteurs par son nom. Il ne manipule
> que des capacités : un moteur ajouté demain est routé sans qu'une ligne d'ici
> change, ce qui est la raison d'être de cette couche."*

`INFERENCE`, and it is D05's most useful output: **adding DSH as a fourth coding
adapter costs a declaration, not a redesign.** The seam Phase 9 asks for already
exists, was built for exactly this in ADR-028, and is already exercised by three
adapters that are all equally unavailable.

That is an argument about **cost of trying**, not about quality. It says the
experiment is cheap and reversible — which is precisely what Phase 7's gates 3
and 11 ask (*unacceptable complexity?* and *removable later?*).

## What would settle Phase 3, precisely

1. Install one existing engine — `pip install aider-install` — and one DSH
   variant, in an environment permitted to install.
2. Run the **same** task set through both, on this repository, with `ollama
   serve` or a configured provider so generation actually happens.
3. Measure the thirteen axes on identical inputs. **Regression rate** is the one
   that matters most here and is cheapest to get right: run the full suite before
   and after each engine's change, which is a rule this repository already
   applies to itself after every phase.

Until that runs, the honest statement is: **DSH declares a wider coding surface
than any single existing adapter, and nothing about its quality has been
measured by anyone whose evidence this audit could read.**
