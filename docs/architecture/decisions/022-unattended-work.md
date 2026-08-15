# ADR-022 — Unattended work goes through the one orchestrator

**Status**: accepted
**Date**: 2026-08-15
**Volets**: 47–48 (routines), 64 (routines fire workflows), 65 (degradation),
66 (correlation), 67 (work budget), 69 (demonstration)

## Context

Volets 47–48 gave the platform routines: work it does with nobody watching.
A routine could call **tools**, and nothing else. That was a deliberate limit at
the time — `types.py` says it in its own comment: past ten actions "it is no
longer a routine but a workflow, which has its own engine with resume and
checkpoints, things a routine does not have."

The limit had a consequence nobody had stated. Scheduled work went straight to
the tool engine, so it never touched the orchestrator: no checkpoint, no
execution history, no agent retry, no `REQUEST` audit event. Two execution paths
existed, and one of them had none of the platform's guarantees — the parallel
implementation the expansion directive forbids in its first line.

Three further facts, each measured rather than assumed:

- The ten subsystems built after `EngineRegistry` appeared in **no availability
  report**; `/health` covered seven components, all predating them.
- `request_id` existed **nowhere** in `src/routines/`, `src/plugins/`,
  `workflow_checkpoint.py` or the notifications, so a job could not be followed
  across the boundaries it crossed.
- The routine budget counted **turns**, which stopped being a unit of cost the
  day a turn could run a whole workflow.

## Decision

**Unattended work uses the same orchestrator as a person's request.** A routine
action may name a workflow (`WorkflowAction`); firing it calls
`RouterEngine.process_request`, and it inherits the plan, the checkpoints, the
execution history, the agent retries and the audit event.

What differs is not the machinery but what may be **decided**:

1. **An approval is never granted by the absence of someone to refuse it.** A run
   that stops on `requires_approval` is reported `suspended` — never successful —
   carries its `run_id`, and waits for a human. Repeated suspensions stop the
   routine, like repeated failures: a routine whose approvals nobody answers is
   not watching anything.
2. **The owner is never inferred.** It comes from the routine's declaration;
   at three in the morning there is no session to read it from.
3. **The workflow is checked when the routine is written**, not discovered broken
   every night by nobody.

Three consequences follow, and they are part of this decision rather than
separate ones:

- **Degraded is not down** (volet 65). The nine subsystems built after the
  registry are probed in isolation; a probe that raises is reported, never
  propagated. A degraded subsystem does not flip the global status and does not
  cost readiness, because a subsystem that says what it is missing is working as
  designed. Probing costs ~70 ms against a 50 ms supervision target, so `/health`
  takes it on request.
- **One job carries one identifier** (volet 66). A routine turn's
  `correlation_id` — set before its guards run — becomes the fired workflow's
  `request_id`, hence the `request_id` of its audit events. The trail assembles
  the sources around it, calling the audit reader that already existed rather
  than writing a second one. An empty source and an unreadable one are never
  merged, and nothing is correlated by time.
- **Work is capped, not turns** (volet 67). Agents executed are counted after
  the run — a workflow's cost is not known before it has run — and counted even
  when the turn fails, since a budget that only records successes lets failures
  drain it silently.

## Alternatives rejected

**A second, lighter execution path for routines.** It is what already existed by
accident, and it is what this ADR removes. It would have meant maintaining two
orchestrators whose behaviour drifts, with the unattended one — the path nobody
watches — being the one without checkpoints or audit.

**Auto-approving steps in unattended runs.** It would make "nobody was there to
answer" mean "yes". Every approval exists because someone judged the action worth
a human decision; the absence of that human is not consent.

**Estimating a workflow's cost before running it.** Refusing on an estimate
refuses wrongly. Counting after the fact means an overrun stops the *next* turn,
which is the acceptable version of being late.

**Reporting degradation inside the global health status.** A delivery channel
without credentials is the normal state of this installation. Counting it as a
failure would light an alarm permanently, and an alarm always on is no longer
read.

## Consequences

- A routine can now consume real capacity, so `PUT /routines/{id}/budget` sets
  two ceilings and `GET /orchestrator/paths` publishes both entry paths and what
  the unattended one cannot decide.
- `GET /system/degradation` and `GET /observability/trail/{id}` require a key:
  they name internal dependencies, routines and owners. `/health` stays public.
- `python scripts/demonstration.py` runs the whole chain and reports what
  happened — it caught a real defect the first time it ran (the routing handed
  whole questions to a function expecting a country name), which is the argument
  for keeping it.
- The unattended path remains unable to reach anything outside: no source is
  enabled (ADR-021) and no model provider is configured. Those are named as
  `NOT_CONFIGURED`, never worked around.
