# AI Orchestration

What VOLET_06 asks for, what the router actually does, and the two places where the code
claims more than it performs. Measured against the repository on 2026-08-11.

---

## What the orchestrator does today (chapter 01)

**2 710 lines** across `src/router/` (10 modules) and `src/agent/` (5 modules), driving
**10 declared agents** (`agents/registry.yaml`) through **2 declared workflows**
(`workflows/workflows.yaml`).

`RouterEngine.process_request()` is the entry point: it plans, runs each agent through the
retry manager, enriches a shared `AgentContext` as it goes, aggregates and returns. The
pipeline works — `tests/test_integration.py` drives it end to end, and the `revue`
workflow runs `reviewer` then `security` on the real repository in 0.2 s.

## The seven components (chapter 02), against the code

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| Request Manager | `process_request()` | present |
| Intent Analyzer | `PlannerAgent._detect_intents()` — keyword rules | present, **not wired to routing** |
| Planning Engine | `ExecutionPlanner.plan_execution()` | present, **ignores the request** |
| Agent Router | `AgentLoader` + the ordered loop | present |
| Execution Manager | `AgentDispatcher` + `RetryManager` | present |
| Response Aggregator | `ResultAggregator` | present |
| Monitoring Module | audit engine per agent, `Logger` | partial |

Seven of seven exist in some form. Two of them do not do what their name implies, and
that is the substance of this VOLET's first finding.

## Finding 1 — the plan does not depend on the request

`plan_execution()` takes a `workflow_id` and nothing else:

```
signature : (workflow_id: str = None) -> Dict[str, List[str]]
plan("revue")   → {'parallel': [], 'sequential': ['reviewer', 'security']}
plan(défaut)    → {'parallel': [], 'sequential': []}
```

**The user's request is never read when building the plan.** The order of agents comes
entirely from the YAML declaration, so the same pipeline runs whether someone asks to
review code, research a market or deploy.

Intent detection *does* exist — `PlannerAgent.INTENT_RULES`, seven intents matched by
keyword, and it is honest about itself: the module docstring states the decomposition is
deterministic and comes from rules, "not from a language model". It produces
`detected_intents` and `agents_required`.

**Nothing consumes either.** `grep` across `src/` and `agents/` finds no reader of
`agents_required` or `detected_intents` outside the file that produces them. The planner
computes which agents a request needs, and the router runs the declared list regardless.

That is not a bug in either component; it is a wire that was never connected. Chapter 03's
planning process — *analyse intent → determine required capabilities → create execution
sequence* — stops after step one.

## Finding 2 — parallel execution is announced and never happens

`workflows.yaml` declares `parallel_agents: [researcher, security]`. `plan_execution()`
returns them under a `parallel` key. `RouterEngine` logs
`Plan d'exécution - Parallèle: [...]`. Its own module docstring says the engine "supports
parallel execution".

**No parallelism exists.** There is no `ThreadPool`, no `asyncio.gather`, no concurrency
primitive anywhere in `src/router/`. The loop is sequential, and the code says so in a
comment three lines below the log: *"Exécution séquentielle des agents (pour une première
version simple)"*. Worse, when a workflow has no explicit pipeline, the so-called parallel
agents are simply appended to the sequential list:

```python
ordered_agents = execution_plan['sequential'] + execution_plan['parallel']
```

This is the failure mode `.claude/rules/verification.md` names: a capability that reports
a plausible answer instead of its real state. An operator reading the log believes two
agents ran concurrently.

**Fixed here** (the claim, not the capability): the docstring no longer advertises
parallel execution, the plan carries `parallel_supported: False`, and the log says the
agents are executed sequentially. Building real parallelism is a separate job — it
touches the shared `AgentContext`, the order of `previous_results` and the retry manager —
and phase 5.2 is where it gets measured and decided. Announcing it was the defect;
implementing it is a feature.

## Agent selection (chapter 04), against the code

| What the manual asks | What happens |
|----------------------|--------------|
| Capability-based matching | **no**: agents come from the workflow declaration |
| Context-aware decisions | **no**: the request is not consulted |
| Performance-aware routing | **no**: no per-agent latency is recorded |
| Policy compliance | partial: `is_enabled()` skips disabled agents |
| Fallback routing | **no**: a failed agent stops the pipeline (rollback) or is skipped |
| Reassign tasks if necessary | **no**: retries re-run the same agent, never another |

The material for capability matching already exists on both sides and is unused: each
agent declares `required_engines` (`coder` needs tool, memory, knowledge, model;
`tester` needs tool and memory), and `registry.yaml` gives every agent a `priority`
(100 for router, 95 planner, 90 for researcher/coder/security, 70 documentation).
**Neither is read by the router** — `priority` appears in no Python file under
`src/router/`.

So the four selection strategies of chapter 04 reduce to one in practice: run the
declared sequence. That is a defensible starting point for two workflows; it is recorded
here so it is not mistaken for capability-based routing.

## What was fixed here, and what was left alone

Phases 1.1 to 4.1 changed **claims, not capabilities**:

| Claim | Before | After |
|-------|--------|-------|
| Module docstring | "supports parallel execution" | states sequential execution and the two limits |
| `plan_execution()` | returned `parallel` and `sequential` | adds `parallel_supported: False` |
| Runtime log | `Plan d'exécution - Parallèle: [...]` | says the declared parallel agents run sequentially |

Nothing about the pipeline's behaviour changed: the 30 orchestration tests
(`test_integration`, `test_agent_runtime`, `test_workflow_revue`) pass unchanged.

`tests/test_orchestration_claims.py` locks both findings **in both directions**. It fails
if a concurrency primitive appears in `src/router/` without `parallel_supported` being
updated, and it fails if anything starts reading `agents_required` — so wiring intent to
routing will be a deliberate, visible change rather than a side effect. A test that only
asserted "no parallelism exists" would become a brake on ever adding it; these assert that
the code and its claims agree.

Real parallel execution and request-aware planning are features, not repairs. They belong
to phases 5.2 and beyond, where they can be measured against the 105 s the orchestration
suite currently takes.

## What agents exchange (chapter 05)

A single `AgentContext` is built per request and shared by every agent in the pipeline.
Each result is appended to `context.previous_results` as it is produced, so an agent reads
what came before through the context rather than through a rewritten request — the request
text handed to each agent is the user's original words, unmodified.

Measured on the `revue` workflow (248 ms, two agents):

| Agent | Keys it produces |
|-------|------------------|
| `reviewer` | `files_reviewed`, `issues`, `issues_by_severity`, `issues_found`, `rules_checked`, `target` |
| `security` | `files_scanned`, `findings`, `findings_by_severity`, `findings_count`, `repository_protections`, `rules_enforced` |

There is no shared schema between agents: each returns its own dictionary and the next one
reads whatever it recognises. That is workable at two agents and is the thing to watch as
the number grows — nothing declares what `security` may rely on from `reviewer`.

## Sequential versus parallel (chapter 05), measured

Per-agent durations on the full nine-agent pipeline:

| Agent | Duration |
|-------|----------|
| `tester` | **97 417 ms** |
| `researcher` | 1 237 ms |
| `monitor` | 129 ms |
| `planner` | 87 ms |
| `documentation` | 72 ms |
| `security` | 70 ms |
| `reviewer` | 39 ms |
| `deployment` | 19 ms |
| `coder` | 7 ms |

**One agent is 98 % of the pipeline.** Everything else put together takes 1.66 s.
Parallelism would therefore buy almost nothing here — running the eight fast agents
concurrently saves about 1.5 s on a 99 s pipeline — while costing concurrent access to the
shared context and a non-deterministic `previous_results` order. That is the measured
answer to "should the router run agents in parallel": **not until an agent other than
`tester` is slow.** The declaration stays, the claim is gone (see Finding 2), and the
decision now rests on a number.

## Two defects in the `tester` agent (chapters 06 and 09)

**It reported suites it never ran.** The agent executed `python <suite>`, which only runs a
file's `__main__` block. **20 of the 92 suites have one**; the other 72 imported themselves,
ran no test, exited 0, and were counted as passing. A verdict of "92 suites green" where 72
verified nothing is precisely the fabrication `.claude/rules/verification.md` forbids.

Fixed: the agent runs `python -m pytest <suite> -q`, and a suite that collects **zero
tests is not green** — it reports `aucun test collecté`, whether pytest exits 0 or 5.

**It was slow for a mechanical reason.** One process per suite paid the platform's full
import 92 times. A single batched invocation pays it once:

| | Before | After |
|---|--------|-------|
| `tester` agent, 91 suites | **97.4 s** | **38.6 s** |

The batch keeps what matters: pytest names the file of every failure, so each suite still
gets its own verdict, and a failing suite keeps its output. A batch that times out or
cannot run falls back to per-suite execution — a detailed report beats no report. Tests
cover the failure attribution, the empty-batch case and the zero-test case.

Note the order of these two changes: the honesty fix made the agent **slower** (it now
runs the 72 suites it used to skip), and the batching fix made it faster than it ever was.
Fixing the lie first was the right order — a faster wrong answer is still wrong.

## Failure handling (chapter 06)

| What the manual asks | What happens |
|----------------------|--------------|
| Retry recoverable failures | `RetryManager`: 3 attempts, 1 s apart, configurable through `settings.yaml` |
| Terminal states | `success`, `skipped` and `requires_approval` stop the retries — retrying an approval request would spam the operator |
| Stop or continue on failure | `workflows.execution.failure.rollback` decides; `true` breaks the loop |
| Rollback | **the name is wrong**: nothing is undone. It stops the pipeline |
| Reassign to another agent | **no**: retries re-run the same agent |

The `rollback` flag deserves the note it now carries in this file: it does not roll
anything back. What an agent wrote to memory, to the knowledge base or to disk before
failing stays written. It is a *stop-on-failure* switch, and calling it rollback invites
the belief that a failed pipeline leaves no trace.

## Aggregation (chapter 07)

`ResultAggregator.aggregate()` is small and behaves consistently:

| Input | Status returned | Extra keys |
|-------|-----------------|------------|
| all successful | `success` | — |
| any error | `partial_success` (or `error` if nothing succeeded) | `errors` |
| any approval pending, no error | `requires_approval` | `approval_request_ids` |
| empty | `success` | — |

The empty case is worth a second look: **no agent ran, and the status is `success`.**
It is defensible (nothing failed) and misleading (nothing happened either), and it is
reachable — the default workflow has an empty pipeline and empty execution groups, so
`process_request()` without a workflow returns `success` having done nothing at all.

**Output validation does not exist.** Chapter 02's workflow step 6 is "validate outputs";
no schema, no contract and no check stands between an agent's dictionary and the
aggregated response. An agent returning `{"status": "success"}` with no result at all
aggregates as a success.

## Observability (chapter 08)

What an operator can see of a run, measured on the `revue` workflow:

- **Response metadata**: `total_agents_executed`, `successful_agents`, `failed_agents`,
  `pending_approval_agents`, `execution_time_seconds`, `request_id`, `workflow_used`.
- **Audit trail**: 20 events for a two-agent run — one per agent, one per tool call, one
  for the request itself — each carrying the agent, the action and the status.
- **Logs**: every agent start, retry and outcome.

What is **not** visible: nothing reports progress *during* a run (the response arrives at
the end), no per-agent duration is recorded anywhere durable, and `/metrics` counts HTTP
traffic and searches but not agent executions. An operator watching a 99-second pipeline
sees nothing until it finishes.

---

# The third orchestration manual (VOLET 19)

`VOLET_19.md` — *AI Agent Orchestration Engine* — is the third manual covering this
subsystem, after VOLET 06 (Orchestration) and VOLET 08/18 (Workflow). Only what it asks
beyond those is treated here.

## The seven components (chapter 02), against the code

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| Orchestration Core | `RouterEngine.process_request` | present |
| Agent Registry | `AgentLoader` + `agents.yaml` | present |
| Monitoring Service | `WorkflowHistory` | present |
| Decision Engine | `ExecutionPlanner` | **partial**: reads the declaration, decides nothing |
| **Communication Bus** | shared `AgentContext` | **absent as a bus**: agents share state, they do not send messages |
| **Task Scheduler** | — | **absent**: a run starts because a request arrived |
| **Resource Manager** | — | **absent**: see below |

## The finding: one agent ate 96 % of every request

The section above closes on "no per-agent duration is recorded anywhere durable". This
VOLET measured what that was hiding. On the shipped `standard` pipeline, with a trivial
request:

```
TOTAL 45.2s
  tester           43.48s  success     ← 96 %
  researcher        1.25s  success
  monitor           0.14s  success
  planner           0.09s  success
  … five more agents, 0.22s combined
```

The `tester` agent runs the project's full pytest suite. It does so on **every request**,
whatever the request asks — "bonjour" costs 45 seconds because the platform tests itself
before answering. Chapter 03 makes monitoring stage 5 and optimisation stage 7; you cannot
optimise what you do not measure, and the only number recorded was the 45.

### What it does now

Each agent's duration — retries included, because that is what the request actually waited
for — is recorded with the run, and `stats()` aggregates it:

```
agent_time:
  tester:     {executions: 1, total_seconds: 46.14, share: 0.9631}
  researcher: {executions: 1, total_seconds:  1.34, share: 0.0279}
```

The share is computed over the **sum of agent durations**, not over request duration: what
happens between two agents belongs to neither, and dividing by the total would invent idle
time that is not there.

This does not make the pipeline faster. It makes the cost visible and attributable, which
is the prerequisite: the fix — whether `tester` belongs in a request-time pipeline at all —
is a decision about the pipeline, not a measurement, and it is recorded in
`docs/memory/pending-work.md` rather than taken here.

## Resource Manager, and why no timeout was invented

Chapter 02 names a Resource Manager and chapter 03 makes resource allocation stage 3.
Neither exists: nothing bounds an agent's execution, so an agent that hangs hangs the whole
request, and the retry manager cannot help — it only sees results, and a call that never
returns produces none.

No timeout was added, and the reason is not oversight. Python cannot kill a thread: a
`future.result(timeout=…)` would free the caller while the runaway agent keeps running and
keeps its resources. That is a timeout in appearance only, and this repository has paid for
appearances before. A real bound needs process isolation, which changes how agents are
loaded and deserves an ADR rather than a phase.

What does exist: `RetryManager` bounds *attempts* (3 by default), and the `tester` agent
carries its own `BATCH_TIMEOUT` from VOLET 06. The gap is the general case.

## Lifecycle, security, governance (chapters 03, 05, 07, 08, 10)

Stages 1, 2, 4, 5 and 6 are covered above and in the VOLET 06 sections. Stage 3 is the
Resource Manager gap. Stage 8, retirement and archival, has the same answer as VOLET 18:
the bounded in-memory history is all there is, and it says so in its own output.

Security, compliance and governance restate VOLET 11 and the ADR-010 identity model, with
the same conclusion as elsewhere: the governance bodies these chapters assign work to do
not exist, and writing down a review cadence nobody performs would be a fabrication.

---

# Decision trace (VOLET 22)

The claim recorded above — *intent detection exists in `PlannerAgent` and is not used* —
was true until the backlog item that followed from it was taken. It is now measured **and
acted on**. `src/router/
decision_trace.py` compares the agents the planner recommends with the agents that run,
and puts the comparison in the response metadata with an explicit `applied: false`.

Reading `agents_required` to report on it is allowed; consuming it to choose what executes
is not, and `tests/test_orchestration_claims.py` keeps that line: the trace module is a
named exception, any other reader fails the guard, and a behavioural test asserts the trace
leaves the executed set untouched.

Full measurement and what it costs → `docs/architecture/decisions.md`.

---

# Planner-driven selection (backlog P1, taken 2026-08-11)

The `standard` workflow now declares `execution.agent_selection: planner`. The planner's
recommendation restricts the declared pipeline instead of being discarded.

Measured before and after, same requests:

| Requête | Avant | Après |
|---------|-------|-------|
| « bonjour » | 45,2 s — 9 agents | **1,5 s — 2 agents** |
| « surveille les logs et les métriques » | 45,2 s — 9 agents | **3,7 s — 4 agents** |
| « écris et teste une fonction » | 45,2 s — 9 agents | 50 s — 3 agents, `tester` compris |

The third row is the point: `tester` still runs when the request is about testing. The cost
did not move, it became attributable to a request that asked for it.

Three invariants hold the change:

- **Selection restricts, never extends.** `workflows.yaml` stays the authority on what
  *may* run; the planner decides what runs among that. A planner able to add an
  undeclared agent would bypass the human review that file carries.
- **An unusable recommendation keeps the whole pipeline.** No planner, or an empty
  recommendation, and the declared pipeline runs in full: executing nothing because a
  heuristic recognised nothing would be worse than doing too much.
- **It is declared, not implicit.** A workflow without the key behaves exactly as before —
  `revue` is the shipped counter-example — and removing the line restores full execution.

## Three defects the wiring exposed

Following a decision makes the decision's quality matter. Three things that were harmless
while the recommendation was ignored became consequential:

- **The fallback ran the test suite.** An unrecognised request fell back to `research` *and*
  `quality`, and `quality` mobilises `tester` — so "bonjour" spent 43 seconds verifying code
  nobody had produced. Understanding a request means researching it, not testing it. The
  fallback is now `research` only.
- **Accents decided which agents ran.** `deploiement` did not match `déploiement`, so an
  unaccented request lost its intent — and, now, lost the agent. Unaccented typing is the
  norm on a Senegalese deployment; the backlog had recorded this for search, and the planner
  had the same defect with a heavier consequence.
- **`veille` matched inside `surveiller`.** Every monitoring request also triggered a
  research agent, through a substring. Keywords must now start a word; they need not end
  one, so `application` still recognises `applications`.

## What deployment now costs, on purpose

`deployment` mobilises `tester`. Preparing a release without knowing whether the tests pass
is the speed-over-truth the constitution rejects (VOLET 01, ch. 04), and the deployment
agent already reads that verdict — it reports `test_state.known: false` without it. So a
deployment request pays the full suite, and that is the one place where it should.
