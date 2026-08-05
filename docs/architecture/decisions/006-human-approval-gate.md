# ADR-006: Human Approval Gate

## Status
Accepted

## Date
2026-08-04

## Context
The GalSen IA platform is built on a central principle stated in the Enterprise
Architecture Manual (VOLET_01, chapter 03, *Human Decision Policy*):
"Artificial Intelligence assists. Humans decide." Meaningful human control over
important decisions must never be removed, and uncertainty must be stated
clearly.

Before this ADR, the platform had no formal mechanism for a human operator to
review an agent action before it takes effect. Agents could already *refuse*
to act (an error-like status), but there was no way to:

- pause an action in a **pending** state while waiting for a human decision;
- let a human **approve** or **reject** the action explicitly;
- keep an auditable trace of the decision and its author.

The implementation roadmap (Track B « Humain ») requires a formal approval gate
as Phase 3, explicitly noting that a behavior change of this kind needs an ADR.
It must build on the structured audit system delivered in Phase 2: every
approval submission and every human decision must be traceable.

## Decision
Introduce a **Human Approval Gate** as a first-class engine of the platform
(`src/approval_engine/`), with the following characteristics:

- A dedicated `requires_approval` status for agent results. An agent whose
  action needs a human decision returns this status instead of `success`,
  `error` or `skipped`.
- An in-memory approval queue (`InMemoryApprovalStore`) managed by a
  best-effort `ApprovalManagerImpl`, mirroring the audit engine's
  interfaces (store contract + manager contract) so a persistent or external
  backend can be plugged later without changing the calling code.
- A formal gate in `BaseAgent`: a subclass declares `approval_required = True`
  (or calls the context shortcut `context.submit_approval(...)`) to enqueue an
  approval request. The request carries the agent id, the request id, the action
  being gated, a description, an optional confidence, and metadata.
- A decision flow (`approve` / `reject`) that records the decision, its reason
  and its author on the request, and stores the whole flow in the audit system
  (`AuditStatus.REQUIRES_APPROVAL` for the pending request, `SUCCESS` /
  `REJECTED`-style records for the decision).
- REST endpoints to list pending requests and to approve or reject them.

### Rationale
- The queue must be **modular and reusable**: a separate engine, with the same
  ABC contracts as `audit_engine`, keeps the code uniform and swappable.
- The gate is **backward compatible**: the default is `approval_required =
  False`, so none of the nine existing agents change behavior.
- The queue is in-memory for Phase 3, matching the current platform state
  (all engines in-memory today, per ADR-005 which already plans persistence as a
  later step). ADR-005's repository pattern will be applied to this engine too
  when persistence lands.

### Scope
Phase 3 delivers the in-memory gate, the status propagation through the
orchestrators (runtime and router), the API endpoints, and the audit wiring.
Persistence of the queue (SQLite), notification of operators, and automatic
expiry of stale requests are deferred to later phases.

## Consequences

### Positive
- **Human control**: important decisions can be reviewed before taking effect,
  directly implementing the VOLET_01 Human Decision Policy.
- **Traceability**: every gate event (submission, approval, rejection) is
  written to the audit engine with the requester, the decision and its author.
- **Uniform status semantics**: `requires_approval` is a first-class status
  propagated through `AgentRuntime` and `RouterEngine`, so callers know a
  request is waiting for a human without conflating it with a failure.
- **Extensible**: swapping the in-memory queue for SQLite or a remote service
  later requires no change to agents, orchestrators or endpoints.

### Negative
- **New status value**: `requires_approval` must be handled by every component
  that interprets statuses (retry manager, result aggregator, runtime, router,
  API). Any component that forgets it could misclassify a pending action as a
  failure.
- **Queue state is lost on restart** while the engine is in-memory.

### Mitigation
- The retry manager treats `requires_approval` as a terminal, non-failure
  status (an action awaiting a human decision must never be retried).
- The aggregator and orchestrators count pending approvals separately from
  failures, and the response status reflects the presence of pending requests.
- A comprehensive test suite (types, store, manager, context, registry, agent
  gate, orchestrators) guards every status path.
- Persistence of the queue is explicitly planned with the ADR-005 storage
  layer before any production deployment relies on it.

## Implementation Plan
1. Add `AuditStatus.REQUIRES_APPROVAL` to the audit engine so gate events are
   traceable with an unambiguous status.
2. Create the `src/approval_engine/` package:
   - `types.py` — `ApprovalStatus`, `ApprovalRequest`, `generate_approval_request_id()`;
   - `interfaces.py` — `ApprovalStore` and `ApprovalManager` contracts;
   - `approval_store.py` — thread-safe `InMemoryApprovalStore`;
   - `approval_manager.py` — best-effort `ApprovalManagerImpl`;
   - `__init__.py` — public exports.
3. Register `approval` in the engine registry (`EngineRegistry`), making it
   always available in memory like the audit engine.
4. Extend `AgentResult` with `requires_approval` and an `approval_request_id`,
   and `BaseAgent` with the `approval_required` gate.
5. Add `AgentContext` shortcuts: `approval`, `submit_approval`,
   `approve_approval`, `reject_approval` (best-effort, never raise).
6. Propagate the status through `RetryManager`, `ResultAggregator`,
   `AgentRuntime` and `RouterEngine`.
7. Add REST endpoints in `src/api/server.py`:
   - `GET /approval/pending`
   - `GET /approval/stats`
   - `GET /approval/{request_id}`
   - `POST /approval/{request_id}/approve`
   - `POST /approval/{request_id}/reject`
8. Write `tests/test_approval_engine.py` and run the full test suite.
9. Update `docs/memory/completed-work.md`, `CHANGELOG.md` and `TASKS.md`.

## Related Documents
- ADR-005: Persistent Storage Backend (planned persistence layer for this queue)
- VOLET_01 (chapter 03): Human Decision Policy — "Artificial Intelligence
  assists. Humans decide."
- Phase 3 of the implementation roadmap: Approbation humaine
