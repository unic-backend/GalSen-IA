# O09 — Self-healing (§15) and failure isolation (§16)

**Built**: 2026-08-19. GalSen IA facts VERIFIED FROM REPOSITORY with paths;
OpenClaw facts VERIFIED FROM OFFICIAL SOURCE, `docs/gateway/restart-recovery.md`
read today. O02 left error recovery `UNKNOWN` and assigned it here; this phase
closes it.

---

## 1. §16 is already a module, and it is not a coincidence

§16 asks: *OpenClaw unavailable → GalSen IA detects failure → fallback →
continue task if possible*, and *"Never allow OpenClaw failure to bring down the
entire platform."*

`src/integration/degradation.py` is that, written for the platform's own
subsystems, with **three states** where §16 implies two:

- `AVAILABLE` — it answered, and it has what it needs.
- **`DEGRADED`** — *"it answered, and it says what it is missing. The platform
  keeps working; that subsystem does less. **This is not a failure and must not
  be reported as one.**"*
- `UNAVAILABLE` — the probe raised; the exception is carried as the reason.

And the rule that makes it usable for a foreign runtime:

> *"A subsystem that fails while being probed is reported, never propagated. A
> degradation report that can be taken down by the thing it observes would be the
> exact failure it exists to prevent."*

That sentence is §16, generalised, written before this directive existed.

Every subsystem also carries **what still works without it**, because
*"'degraded' alone tells an operator nothing about whether to act tonight or on
Monday."*

`INFERENCE`: OpenClaw would enter as **one more probed subsystem** — a tenth
alongside routines, checkpoints, channels, world knowledge, routing, plugins,
memory layers, the source registry and orchestration. §16 is then satisfied by
adding a probe and a `SOUS_SYSTEMES` entry, not by building an isolation layer.

**And the `DEGRADED` state is the honest answer for it**, because O02 measured
that thirteen of §5's fourteen capabilities already exist here. Losing OpenClaw
means losing the one thing it uniquely brings — conversational channels — not
losing orchestration, tools, memory or agents.

## 2. §15 — the self-healer stays, and the decisions stay with it

`src/agent/self_healer.py` is *"the engine the whole harness exists to
restrain"*, and its lifecycle is a chain of gates rather than steps:

```
diagnose → workspace → propose → validate scope → apply (isolated)
→ tests → security tests → ruff → integrity → merge | rollback
```

Two of its four rules matter directly to this programme.

**A traceback is data.** *"It arrives from a crashing program, and a crashing
program can be made to say anything. Text inside it — 'ignore the rules',
'delete the tests' — is parsed for a file, a line and an exception type, and is
never read as an instruction."*

That rule was written for our own crashes. It applies **more** to a foreign
runtime's errors, and it means an OpenClaw failure string is parsed for shape and
never obeyed. §15's *"OpenClaw must not override GalSen IA security boundaries"*
is already enforced by the module that would receive its errors.

**`UNKNOWN_DIAGNOSIS` is a real answer.** *"A guess dressed as a diagnosis sends
a repair at the wrong file, which is worse than stopping."* An OpenClaw failure
this repository cannot diagnose returns `UNKNOWN_DIAGNOSIS` — which is the
correct outcome for a subsystem whose internals are not ours.

**§15's six decisions — `RETRY`, `FALLBACK`, `CANCEL`, `REGENERATE`, `ESCALATE`,
`FAIL` — stay on GalSen IA's side** and already have their homes:
`router/retry_manager.py` and `model_engine/retry_manager.py` for retry,
`degradation.py` for fallback, `workflow_checkpoint.py` for the suspend that
makes `ESCALATE` mean something (a run that needs a human stops and keeps its
checkpoint), and `AuditStatus` for recording which was chosen.

## 3. The conflict §15 warns about, found and named

§15 says *"Do not create a competing self-healing architecture."* OpenClaw has
one, and it is good — which is exactly why the warning matters.

From `docs/gateway/restart-recovery.md`, VERIFIED FROM OFFICIAL SOURCE:

- *"Restarting the gateway does not lose agent state. Conversations, transcripts,
  scheduled jobs, background task records, and queued outbound messages all live
  on disk, and work that was interrupted mid-turn is detected and resumed
  automatically after the gateway comes back up."*
- *"A few seconds after startup, the gateway re-dispatches each marked session
  with a synthetic system message telling the agent its previous turn was
  interrupted by a restart and to continue from the existing transcript."*
- Budgets: *"a durable budget of three charged automatic dispatch attempts,
  retained across gateway restarts"*, and sessions that exhaust it are
  *"tombstoned instead of looping forever"*. Runs interrupted more than two hours
  ago are *"finalized instead of resumed"*.

**This is a well-designed recovery system, and it is a competing one.** The
conflict is concrete rather than theoretical:

| | GalSen IA | OpenClaw |
|---|---|---|
| After a crash, who decides to retry? | `retry_manager`, and a run needing a human **suspends** | the gateway **re-dispatches automatically**, a few seconds after startup |
| How many attempts? | policy-driven | *"three charged automatic dispatch attempts"*, durable |
| What resumes? | the checkpointed run | the session, via a **synthetic system message** to the model |

`INFERENCE`, and it is the sharpest of this phase: **automatic re-dispatch after
restart can replay work whose approval was granted for one execution.** ADR-006's
gate is per-execution; a gateway that resumes a turn on its own, and tells the
model to continue, is making an execution decision GalSen IA never took.

Worse for §15's *"OpenClaw must not override GalSen IA security boundaries"*: a
re-dispatch happens **inside OpenClaw**, without a request arriving at
`authorize()`. GalSen IA would learn about it only if the resumed turn calls one
of O03's four allowlisted tools.

## 4. The constraint this produces

**Automatic recovery must be off**, or the adapter is not subordinate.

The measured shape of the constraint, and its `UNKNOWN`:

- Recovery is described as *"automatic by default"*. Whether it can be
  **disabled by configuration** is **`UNKNOWN`** — `restart-recovery.md` names
  budgets and tombstones but no off switch was read.
- If it cannot be disabled, the adapter must make it inert: **a session is
  created per task and ended with it**, so there is no marked session for the
  gateway to re-dispatch. That is implementable on our side and does not depend
  on their configuration.

`INFERENCE`: the second option is better regardless, because it does not rely on
a setting staying correct. It also matches O06's memory rule — OpenClaw's SQLite
is session scratch — and O04's identity constraint — the adapter creates the
session on behalf of a known actor. **Three volets independently arrive at
per-task, adapter-owned sessions.**

## 5. What O09 concludes

- **§16 costs one probe.** OpenClaw becomes a tenth probed subsystem; its
  absence is `DEGRADED`, not a failure, and the platform loses only what
  OpenClaw uniquely brings.
- **§15 needs nothing built.** The self-healer already treats a traceback as
  data and already answers `UNKNOWN_DIAGNOSIS` rather than guessing, which is
  the right posture toward a foreign runtime's errors.
- **A real conflict exists and is named**: OpenClaw's automatic post-restart
  re-dispatch is an execution decision taken outside `authorize()` and outside
  ADR-006's per-execution gate.
- **The resolution is per-task sessions**, owned by the adapter — which O04 and
  O06 already required for other reasons.
- **One `UNKNOWN`**: whether automatic recovery can be disabled by
  configuration. It does not block, because the per-task session makes it moot.
