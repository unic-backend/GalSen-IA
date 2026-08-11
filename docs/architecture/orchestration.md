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
