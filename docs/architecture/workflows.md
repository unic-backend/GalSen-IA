# Workflow Engine

What VOLET_08 asks for, and what the workflow layer did before this VOLET looked. Measured
against the repository on 2026-08-11.

---

## There is no separate workflow engine (chapters 01 and 02)

The manual describes seven components. In this repository the workflow layer is
**declarative**: two YAML files and three small modules inside `src/router/`.

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| Workflow Manager | `WorkflowLoader` | present |
| Execution Engine | `RouterEngine` loop + `AgentDispatcher` | present |
| Rule Engine | `ExecutionPlanner` | present, reads the declaration only |
| Monitoring Module | `WorkflowHistory` | **added by this VOLET** |
| State Manager | — | **absent**: no workflow state survives a request |
| Event Dispatcher | — | **absent**: no events, no triggers |
| Integration Layer | the engine registry, shared by agents | indirect |

Four of seven exist. That is a defensible shape for a platform with two workflows, and it
is written down so "Workflow Engine" is not read as more than it is.

## Nothing validated anything (chapters 02, 03 and 04)

Chapter 02 puts "validate inputs" second in its flow; chapter 03 makes validation the
second lifecycle stage. Measured before this VOLET:

- a workflow citing **an agent that does not exist** loaded silently, and failed halfway
  through execution;
- a workflow with **no steps at all** loaded, produced an empty plan and — as VOLET 06
  established — returned **`success` having executed nothing**.

`workflow_validator.py` now separates two severities, because they call for different
reactions:

| Severity | Meaning | Reaction |
|----------|---------|----------|
| **error** | the workflow cannot run without producing a misleading result | the engine refuses to execute it |
| **warning** | the definition is incomplete | it runs; something the manual requires is missing |

Errors: no steps, unknown agent, default workflow not declared. Warnings: missing
`version` or `owner` (chapter 04's metadata), an agent repeated inside one list, an
unknown key — a typo loads normally and has no effect, which is the most expensive kind.

Duplicates are looked for **within** a list: an agent present in both `pipeline` and
`execution` is the same sequence expressed twice, not a repetition.

## Three declarations that configured nothing

Validating the real registry surfaced dead configuration:

1. **`execution:` at the root of `workflows.yaml`** declared `parallel_agents` and
   `sequential_agents`. The planner reads `execution` **inside** a workflow, so the root
   block was never read.
2. **`failure:` at the root** declared `retry`, `max_attempts` and `rollback`. The code
   reads `workflows.execution.failure.*` through `ConfigLoader`, which reads
   `config/settings.yaml` — where the key did not exist. Both settings silently fell back
   to code defaults.
3. Neither workflow carried `version` or `owner`.

Fixed: the failure settings now live in `settings.yaml` where they are actually read, with
the values that were really in force; the dead root blocks are gone; both workflows carry
their metadata. The validator warns if a root `execution` block ever comes back.

`rollback: true` keeps its name and gains a comment: it does not undo anything, it stops
the pipeline at the first failure (VOLET 06).

## Execution history (chapters 03 and 09)

Chapter 03 asks to "track execution history"; chapter 09 makes **success rate** its first
quality metric. Every run reported its status and vanished, so nobody could say whether a
workflow failed one time in ten or nine.

`WorkflowHistory` records each completed run — workflow, status, duration, agents
executed, failed agents, request id — and computes the success rate, the status breakdown
and the median and maximum durations, globally or per workflow.

Three decisions worth keeping:

- **Failures are recorded too.** A success rate that only observes successes is always
  100 %. The exception path records before returning the error response.
- **`success_rate` is `None` with no runs**, never `0.0` — zero executions does not mean
  everything fails.
- **The user's request is not stored.** Measuring a workflow is not archiving what people
  ask; same reasoning as the search analytics in VOLET 14.

The history is bounded (500 runs) and lives in process memory. It says so in its own
output: a restart clears it, and another instance has its own (ADR-009). An unbounded
history is the debt the platform's log already cost once.

---

# The second manual (VOLET 18)

`VOLET_18.md` is a **second Workflow Engine manual**, despite its folder being named
"Infrastructure & DevOps Engine". Like VOLET 17 for notifications, it restates most of
VOLET 08. Only what it asks beyond that one is treated here; re-measuring the rest would
duplicate the sections above.

## What it asks that VOLET 08 did not

| Chapter | New ask | Measured state |
|---------|---------|----------------|
| 02 | Task Scheduler, Event Bus, Workflow Repository | absent — see below |
| 03 stage 3 | Deployment | n/a — a workflow is a YAML entry, there is no deploy step |
| 03 stage 7 | **Version Management** | **declared and unused** |
| 03 stage 8 | Retirement and Archival | absent — a retired workflow is a deleted YAML block |
| 03 practices | Retry failed tasks safely | present — `RetryManager`, 3 attempts |
| 04 | Task Management, Rule Management | the pipeline is the only rule |
| 06 | Queue health | n/a — no queue |

## The finding: every workflow declares a version nobody reads

`workflows/workflows.yaml` gives each workflow a `version`, and `WorkflowValidator` lists
it among the metadata it requires — a workflow without one is flagged. Measured across
`src/router/`, the string `version` appears in exactly two places:

```
workflow_validator.py: METADONNEES_ATTENDUES = ("description", "version", "owner")
workflow_validator.py: CLES_CONNUES = {"description", "pipeline", "execution", "version", …}
```

Both are the validator checking that the field exists. **Nothing reads its value.** The
execution path (`RouterEngine.process_request`) loads the workflow config and never looks
at it, and `WorkflowHistory.record()` stores `workflow`, `status`, `duration_seconds`,
`agents_executed`, `failed_agents`, `request_id`, `at` — no version.

The consequence is precise, and it undoes the metric VOLET 08 built. Change a pipeline,
bump `version: "1.0"` to `"1.1"`, and the history keeps both under the same name: the
success rate now mixes runs of two different definitions. An operator reading "this
workflow fails 30 % of the time" cannot tell whether the old definition failed often and
the new one is fine, or the reverse. Chapter 03 makes version management a lifecycle stage
and chapter 06 makes failure analysis a quality control; conflating versions defeats both.

This is the pattern the platform keeps finding: a field that is validated as *present* and
never used as *data*. Required, checked, and inert.

The fix belongs to phase 3.1 of this VOLET, not to this measurement.

## What is absent, and stays absent

- **Task Scheduler**: nothing runs a workflow on a schedule; a run starts because a
  request arrived.
- **Event Bus**: no events, no triggers — already recorded under VOLET 08 as the absent
  Event Dispatcher, and this manual asks for the same thing under a different name.
- **Workflow Repository**: `workflows.yaml` is the repository. There is no store, no
  history of definitions, and therefore nothing to archive when one is retired.
- **Queue health** (chapters 04 and 06): there is no queue. Execution is synchronous.
