# Linux kernel architecture — research audit

**Status: IN PROGRESS.** Chapter 01 of 13. Nothing is implemented by this audit,
no kernel source is copied, no dependency is introduced.

Started 2026-08-23. Owner's brief: study the Linux kernel as an example of mature
systems engineering, extract **engineering principles**, and determine which ones
solve a problem GalSen IA actually has.

---

## Source reachability, measured before anything else

A plan that assumes its sources are reachable is not a plan. From this machine,
2026-08-23:

| Source | HTTP |
|---|---:|
| `raw.githubusercontent.com/torvalds/linux/…` | **200** |
| `github.com/torvalds/linux` | 403 |
| `docs.kernel.org` · `www.kernel.org` · `git.kernel.org` | 000 |
| `spdx.org` | 000 |

`docs.kernel.org` is the rendered form of `Documentation/` in the tree, and that
tree answers. Verified file by file: `COPYING` (496 B),
`Documentation/admin-guide/cgroup-v2.rst` (135 502 B),
`Documentation/trace/ftrace.rst` (145 229 B),
`Documentation/fault-injection/fault-injection.rst` (19 325 B),
`Documentation/security/credentials.rst` (20 875 B),
`Documentation/process/license-rules.rst` (18 477 B).

**The audit reads the authoritative source rather than a summary of it.** What
stays out of reach — the canonical SPDX text, anything living only on
`kernel.org` — will be reported `UNKNOWN`, never guessed.

---

# Chapter 01 — What GalSen IA already does

The brief's own warning governs this chapter: *"do not assume a capability is
absent simply because it has a different name."* Everything below was measured
in the repository on 2026-08-23, not recalled.

## 1.1 — Orchestration, agents, scheduling, lifecycle, queues

### What exists

| Thing | Measured |
|---|---|
| Orchestrator | `src/router/`, **16 modules, 3 010 lines** |
| Largest pieces | `router_engine.py` 637 · `workflow_checkpoint.py` 530 · `agent_dispatcher.py` 239 |
| Agents | **17** declared in `agents/registry.yaml`, 16 directories under `agents/` |
| Workflows | **8** in `workflows/workflows.yaml` |
| Application lifecycle | FastAPI `lifespan`, `src/api/server.py:329` |
| Retry | `RetryManager(max_attempts=3, delay_seconds=1.0)` |
| Parallelism primitives | **2 files only**: `src/model_engine/parallel_executor.py` (`ThreadPoolExecutor`, `asyncio.gather`), `src/agent/context.py` |

Beside the engine sit an execution planner, a result aggregator, a decision
trace, a workflow history, an output validator, a workflow validator and a
checkpoint store. This is not a thin dispatcher.

### The three findings that matter

**1. Execution is strictly sequential, and the engine says so itself.**
`src/router/router_engine.py:1-16` states two limits in its own module
docstring rather than leaving them to be discovered:

> *"**Execution is sequential.** Workflows declare `parallel_agents`, and nothing
> runs them concurrently: they are appended to the sequential order. The plan
> reports `parallel_supported: False` so no caller mistakes the declaration for
> a behaviour."*

> *"**The plan does not depend on the request.** The order of agents comes from
> the workflow declaration."*

A declared-but-unimplemented capability that reports itself as unimplemented is
the opposite of the usual failure. It is also the exact place where a scheduling
principle would apply, if one applies at all.

**2. There is no timeout anywhere in the orchestrator.** `grep -n "timeout"
src/router/*.py` returns **nothing** across all 16 modules. An agent that blocks
blocks the request that called it, and nothing above it will cut it short.

This is the first genuine gap of the audit, and it is precisely the class of
problem an operating system exists to solve: in a kernel, no task holds a CPU
because it decided to.

**3. Agents run in-process, by import.** `AgentDispatcher.dispatch()` imports the
agent's module, finds its class and calls it in the same interpreter. There is
no process boundary between the orchestrator and an agent, so an agent cannot be
bounded, killed or accounted for separately. Compare with `src/sandbox/`, which
*does* cross a process boundary — for tool code, not for agents.

**4. There is no queue.** No `asyncio.Queue`, no `queue.Queue`, no broker, no
worker pool for agent work. Requests are served synchronously, one HTTP request
at a time, by the ASGI server. Admission control, backpressure and priority have
nowhere to live because there is no place where work waits.

Whether that is a defect or a correct choice for a single-instance platform
(ADR-009) is chapter 05's question, not this one's.

## 1.2 — Resources, isolation, sandbox, security, permissions

### What exists

**`src/sandbox/` already applies kernel limits.** `SandboxPolicy` declares six
bounds, applied by `setrlimit` in `preexec_fn` — between `fork` and `exec`, so
they are in force before the first instruction of the guest code:

| Bound | Value |
|---|---:|
| `cpu_seconds` | 5 |
| `memory_bytes` | 256 MiB |
| `file_size_bytes` | 10 MiB |
| `processes` | 64 |
| `wall_seconds` | 15 |
| `output_bytes` | 64 KiB |

Plus `RLIMIT_CORE = 0` (no memory dump on disk) and `os.setsid()`, so the whole
process group is killed at the end of every execution rather than only on
timeout.

**And it already names what it does not guarantee — using the kernel's own
vocabulary.** `NON_GARANTI` in `src/sandbox/policy.py:49` reads, in the
repository's own words:

- *filesystem*: a child reads and writes wherever the user can; the working
  directory is tidying, not a boundary;
- *network*: **no network cut without namespaces**;
- *processes*: `RLIMIT_NPROC` bounds **the user**, not this sandbox. A fork bomb
  is capped, but it consumes the platform's own process budget. **A real
  per-execution cap needs cgroups, therefore privileges the platform does not
  have.**

**This is the single most important measurement of chapter 01.** Two of the
three concepts this audit was most likely to recommend — **namespaces** and
**cgroups** — are already identified here by name, with the reason they are
absent. The audit's job on those two is therefore not to discover them, but to
determine whether the stated blocker still holds.

`grep -rln "setrlimit\|RLIMIT\|cgroup\|namespace" src/` matches four files:
`src/sandbox/runner.py`, `src/sandbox/policy.py`, `src/coding_engine/execution.py`,
`src/coding_engine/workspace.py`. In `policy.py` the cgroup and namespace matches
are **prose, not code** — they are the sentences quoted above.

### The rest of the security surface

| Module | What it holds |
|---|---|
| `src/security/isolation.py` | User-data isolation: **no function takes an optional owner** |
| `src/security/trust.py` | External text is data with an origin, never an instruction |
| `src/security/posture.py`, `checkpoints.py`, `redaction.py` | Posture, gates, redaction |
| `src/api/rbac.py` | `Role` and `Permission` enums, **35 constants** |

`isolation.py` records why it exists, and the reason is a principle in itself:

> *"The repository already had a `user_id` on memory items — but as an optional
> filter. […] the default was leakage and isolation was something a caller had
> to remember to ask for. Every such design fails the same way: not through an
> attack, through an omission."*

That is the same argument the kernel makes for capabilities over ambient
authority, arrived at independently and for a different subsystem.

**Windows is refused rather than faked.** `unavailable_reason()` returns a reason
instead of running unbounded code while claiming bounds — the platform reports
incapacity rather than simulating capability.

### Early reading, to be confirmed by chapters 03–08

Two candidates are already visible and neither is a surprise:

- **No timeout in the orchestrator** — a real gap, small and reversible.
- **No boundary around an agent** — real, but expensive, and the sandbox shows
  the platform knows how to cross a process boundary when it decides to.

And one likely `D — ALREADY COVERED` in advance: the platform's habit of
declaring what it does *not* guarantee is the discipline this audit came to
recommend, already practised.

## 1.3 — Self-healing, observability, memory, configuration, degradation

### Self-healing already exists, and it is built as a chain of gates

`src/agent/self_healer.py` states its own design premise:

> *"the dangerous part of automated repair is not writing the patch, it is
> **deciding the patch worked**. So the lifecycle separates the two, and
> everything after `propose_patch` is a gate rather than a step."*

```
diagnose → workspace → propose → validate scope → apply (isolated)
         → tests → security tests → ruff → integrity → merge | rollback
```

Two of its four rules are directly comparable to kernel practice:

- **A traceback is data.** It arrives from a crashing program, and a crashing
  program can be made to say anything. Text inside it is parsed for a file, a
  line and an exception type — never read as an instruction.
- **`UNKNOWN_DIAGNOSIS` is a real answer.** A guess dressed as a diagnosis sends
  a repair at the wrong file, which is worse than stopping.

There is a **rollback path**, and the merge is conditional on every gate. This
is closer to a transactional recovery model than to a retry loop.

### Degradation is probed, with a three-value vocabulary

`src/integration/degradation.py` (382 lines) probes nine subsystems and answers
per subsystem:

| Verdict | Meaning, in the module's own words |
|---|---|
| `AVAILABLE` | it answered, and it has what it needs |
| `DEGRADED` | it answered, and **it says what it is missing** |
| `UNAVAILABLE` | the probe raised; **the exception is carried as the reason** |

And the probing follows the rule it measures: *"a subsystem that fails while
being probed is reported, never [hidden]"*. `src/api/health.py` is 656 lines —
health is not a boolean here.

### Observability: one identifier that survives the boundaries

`src/observability/trail.py` exists because every subsystem already recorded
what it did — audit events, checkpoints, routine journal, workflow history —
and none could answer *"what happened to this one job?"*. A routine turn's
`correlation_id` becomes the workflow's `request_id`, which becomes the
`request_id` of its audit events, and the trail is reassembled by reading the
identifier back out of each store.

That is the same idea as a correlation identifier in kernel tracing, arrived at
for the same reason: per-subsystem logs cannot be joined after the fact unless
something was carried across.

Also present: `src/router/decision_trace.py`, `src/api/metrics.py`, and a
`RotatingFileHandler` bounding the log.

### Configuration

`src/config/environment.py` is the single module. Behaviour is selected by
environment variable — `GALSEN_STORAGE_BACKEND`, `GALSEN_DATA_DIR`,
`GALSEN_API_KEYS`, `GALSEN_CODING_WORKSPACE_ROOTS` — and an unset
`GALSEN_CODING_WORKSPACE_ROOTS` **refuses every execution** rather than meaning
"the whole host".

### Chapter 01 verdict

The platform already has: fault detection, diagnosis with an explicit unknown,
isolated repair, gated validation, rollback, per-subsystem degradation with
reasons, a cross-subsystem trail, health beyond a boolean, and a
refuse-by-default configuration.

**What it does not have, measured:** a timeout on any agent, a boundary around
an agent, a queue, and any notion of one piece of work costing more than
another.

---

# Chapter 02 — Linux architecture, read at the source

All quotations below are from `Documentation/` in `torvalds/linux` at `master`,
fetched 2026-08-23. Nothing is quoted from memory.

## 2.1 — Resource distribution, scheduling, capabilities

### The four resource-distribution models (`admin-guide/cgroup-v2.rst`)

The kernel does not have *a* resource limit. It has four distinct models, and
the distinction is the useful part:

| Model | Kernel's definition (abridged) |
|---|---|
| **Weights** | a parent's resource is split by the ratio of each active child's weight to the sum |
| **Limits** | a child can consume up to a configured amount; **limits can be over-committed** |
| **Protections** | a cgroup is protected up to a configured amount as long as its ancestors are under theirs; hard or best-effort |
| **Allocations** | exclusive amount of a finite resource; **cannot be over-committed** |

The principle worth extracting is not "add limits". It is that **a limit and a
guarantee are different promises**, and over-commitment is allowed for one and
forbidden for the other. A platform that only has limits can starve a
subsystem it never intended to starve.

### Delegation containment

> *"A delegated sub-hierarchy is contained in the sense that processes can't be
> moved into or out of the sub-hierarchy by the delegatee."*

Delegating control over a subtree does not delegate the ability to escape it.
This is the same shape as `GALSEN_CODING_WORKSPACE_ROOTS`: declaring where a
workspace may live is not the same as letting the workspace choose.

### Scheduling — EEVDF (`scheduler/sched-eevdf.rst`)

Linux moved from CFS to EEVDF in 6.6. Its mechanism, in the document's terms: a
virtual runtime per task produces a **lag** — positive means the task is owed
CPU time, negative means it has had more than its share. Only tasks with
lag ≥ 0 are eligible; among those, the earliest virtual deadline runs next.

> *"this allows latency-sensitive tasks with shorter time slices to be
> prioritized, which helps with their responsiveness."*

The extractable principle: **fairness is computed from what a task has already
received**, not from a static priority number. Whether GalSen IA has anything
to schedule is chapter 05's question — it currently has no queue, so it may not.

### Capabilities (`security/credentials.rst`)

A task carries four sets: permitted, inheritable, effective, and a **capability
bounding set**.

> *"They indicate superior capabilities granted piecemeal to a task that an
> ordinary task wouldn't otherwise have."*

Two principles, and the second is the one usually missed:

- **Piecemeal, not all-or-nothing.** Privilege is a set of named powers, not a
  boolean.
- **A bounding set exists** — a ceiling that a task cannot raise, only lower.

GalSen IA already has the first (35 named permissions in `src/api/rbac.py`) and
already has a form of the second (`PERMISSIONS_HORS_PLATEFORME` keeps publishing
and learner reads out of every platform role, admin included). Whether the
ceiling is enforced as consistently as the kernel's is chapter 06's question.

## 2.2 — Modules, VFS, tracing, fault injection, boundaries, synchronisation

### The VFS: one interface, many implementations

> *"The Virtual File System […] provides the filesystem interface to userspace
> programs. It also provides an abstraction within the kernel which allows
> different filesystem implementations to coexist."*
> — `Documentation/filesystems/vfs.rst`

The principle: **a caller names an operation, never an implementation.** Adding
a filesystem costs no change in `open(2)`.

**GalSen IA already has this**, three times over:
`src/model_engine/providers/provider_registry.py`, `src/model_engine/interfaces.py`,
`src/creative/providers.py`. ADR-037 measured it too — *"every provider
abstraction the directive asks for already existed"*. This is `D — ALREADY
COVERED`, and stated here so the final report does not re-propose it.

### Tracing

> *"Ftrace is an internal tracer designed to help out developers and designers of
> systems to find what is going on inside the kernel."* — `Documentation/trace/ftrace.rst`

The kernel's tracing is **built in and always present**, switchable at runtime
rather than compiled for a debugging session. GalSen IA's `decision_trace.py`,
`observability/trail.py` and audit engine are the same posture. Chapter 07
decides whether anything is missing.

### Fault injection — the one concept GalSen IA does not have at all

`Documentation/fault-injection/fault-injection.rst` describes an infrastructure
for making allocations fail **on purpose**: `failslab` (slab allocation),
`fail_page_alloc` (page allocation), and others. What makes it infrastructure
rather than a test is that it is **parameterised at runtime**:

| Knob | What it controls |
|---|---|
| `probability` | likelihood of injection, in percent |
| `interval` | spacing between injections |
| `times` | how many times to fail |
| `space` | bytes to let through before failing |
| `task-filter` | fail **only** processes marked `/proc/<pid>/make-it-fail` |
| `stacktrace-depth` | how deep to match the calling site |
| `verbose` | how loudly to report |

**Measured in GalSen IA: nothing.** `grep -rln "fault_inject\|inject_failure\|chaos"`
over `src/` and `tests/` returns **zero files**.

And yet this repository *already practises fault injection* — by hand, once per
session, under the name **"sabotage the guard before believing it"**. It is in
`docs/memory/session-state.md` as the thing that has served every time. It was
used four times today alone.

The extractable principle is therefore not *"inject faults"* — the habit exists.
It is that **the kernel turned that habit into a facility with knobs**, so it no
longer depends on whoever is careful that day. That is the same argument this
repository already accepted when it turned systematic debugging from an instinct
into `.claude/skills/systematic-debugging`:

> *"an instinct that works when the operator is careful is exactly what fails on
> the day they are not."*

The audit did not expect its strongest candidate to be one the repository had
already argued for, in its own words, about a different subject.

### Synchronisation

`Documentation/locking/locktypes.rst` divides primitives by the context they may
be taken in — sleeping versus non-sleeping — and the rule is about **where** a
lock may be used, not how fast it is.

GalSen IA uses locks in **68 files**. It is single-instance (ADR-009), and its
orchestration is sequential, so the kernel's contention problems mostly do not
arise. Nothing here suggests a change; chapter 08 will say so explicitly.

---

# Chapter 03 — Principle extraction

Eight fields per concept, as the brief requires. Only concepts that map to a
problem GalSen IA actually has are carried forward.

## 3.1 — Isolation and resources

### P1 — Four distribution models, not one limit

| Field | |
|---|---|
| **Linux principle** | cgroup-v2 distributes by weights, limits, protections or allocations. Limits may be over-committed; allocations may not. |
| **Problem it solves** | A single "limit" cannot express a guarantee. Without protections, a subsystem starves that nobody meant to starve. |
| **GalSen IA equivalent problem** | None measured today. There is no contention: no queue, sequential orchestration, one instance. |
| **Current solution** | `SandboxPolicy` — six hard bounds, i.e. the *limits* model only. |
| **Potential improvement** | None until work waits somewhere. |
| **Complexity** | High |
| **Risk** | Inventing a scheduler for a platform that schedules nothing |
| **Reversibility** | N/A |
| **Provisional class** | **E — NOT RELEVANT** (revisit if a queue ever exists) |

### P2 — Delegation containment

| Field | |
|---|---|
| **Linux principle** | *"processes can't be moved into or out of the sub-hierarchy by the delegatee"* |
| **Problem it solves** | Delegating control over a subtree must not delegate the right to leave it. |
| **GalSen IA equivalent problem** | A coding workspace must not be able to choose a workspace outside its declared roots. |
| **Current solution** | `GALSEN_CODING_WORKSPACE_ROOTS` + `confine()`. An unset variable refuses everything rather than meaning "the whole host". |
| **Potential improvement** | None identified. |
| **Complexity** | — |
| **Risk** | — |
| **Reversibility** | — |
| **Provisional class** | **D — ALREADY COVERED** |

### P3 — Capabilities, piecemeal, with a bounding set

| Field | |
|---|---|
| **Linux principle** | Privilege is a set of named powers; a **bounding set** is a ceiling a task may lower and never raise. |
| **Problem it solves** | All-or-nothing privilege forces over-granting. |
| **GalSen IA equivalent problem** | Same, for roles and tools. |
| **Current solution** | 35 named permissions in `src/api/rbac.py`; `PERMISSIONS_HORS_PLATEFORME` is a true ceiling — publishing and learner reads sit outside every platform role, **admin included**. |
| **Potential improvement** | Verify in chapter 06 that the ceiling is enforced everywhere, not only in education. |
| **Complexity** | Low, if a gap is found |
| **Risk** | Low |
| **Reversibility** | High |
| **Provisional class** | **D — ALREADY COVERED**, pending chapter 06 |

### P4 — Namespaces for a real network cut

| Field | |
|---|---|
| **Linux principle** | A namespace changes what a process *can see*, not what it is allowed to ask for. |
| **Problem it solves** | Sandboxed code reaching the network. |
| **GalSen IA equivalent problem** | Named already, by the platform: `NON_GARANTI` says *"no network cut without namespaces"*. |
| **Current solution** | None. The gap is declared rather than hidden. |
| **Potential improvement** | Requires privileges the platform states it does not have — to be re-tested in chapter 06, not assumed. |
| **Complexity** | High |
| **Risk** | A sandbox that *claims* a boundary it does not have is worse than none |
| **Reversibility** | Medium |
| **Provisional class** | **F — BLOCKED**, pending re-measurement |

### P5 — Bounded execution before the first instruction

| Field | |
|---|---|
| **Linux principle** | `setrlimit` is applied by the kernel to the child before `exec`; nothing the code does afterwards lifts it. |
| **Problem it solves** | A limit the guest can raise is not a limit. |
| **GalSen IA equivalent problem** | Same, for tool code. |
| **Current solution** | Exactly this, in `src/sandbox/runner.py`, in `preexec_fn`. |
| **Potential improvement** | **The orchestrator has no equivalent**: no timeout on any agent (chapter 01, finding 2). |
| **Complexity** | Low |
| **Risk** | Cutting a legitimately slow agent |
| **Reversibility** | High — one guard, removable |
| **Provisional class** | **A — USEFUL NOW** (candidate) |

### P6 — Fault injection as a facility, not a habit

| Field | |
|---|---|
| **Linux principle** | Failures are injectable at runtime, with probability, interval, count, task filter and stack depth. |
| **Problem it solves** | Recovery paths are the least exercised code and the most load-bearing. |
| **GalSen IA equivalent problem** | The self-healer, the degradation probes and every `UNAVAILABLE` path are exercised only when something really breaks. |
| **Current solution** | **None as code.** The habit exists — *"sabotage the guard before believing it"* — performed manually, per session. |
| **Potential improvement** | Turn the habit into a facility, as this repository already did for systematic debugging. |
| **Complexity** | Medium |
| **Risk** | A fault-injection switch reachable in production would be a weapon; it must be inert unless explicitly enabled |
| **Reversibility** | High |
| **Provisional class** | **A — USEFUL NOW** (candidate) |

**Two candidates so far, both small and both reversible.** Neither is confirmed
before the feasibility gates of chapter 11.

## 3.2 — Faults, observability, boundaries

### P7 — A taint is permanent, because the damage may not be undoable

| Field | |
|---|---|
| **Linux principle** | *"the kernel will remain tainted even after you undo what caused the taint […] to indicate the kernel remains not trustworthy"*, and it **prints the tainted state** whenever it reports a bug, an oops or a panic. |
| **Problem it solves** | A system that has been in an untrustworthy state cannot become trustworthy again by leaving it: the consequences may already be in the output. Reporting the state at the moment of failure is what lets an investigator find the real cause. |
| **GalSen IA equivalent problem** | An answer produced while a subsystem was `DEGRADED` is **indistinguishable** from one produced while everything was `AVAILABLE`. |
| **Current solution** | `src/integration/degradation.py` reports degradation **at probe time**. `grep -rln "tainted\|degradation_snapshot\|produced_while_degraded" src/` returns **zero files**: no result carries the platform state it was produced under. A workflow response carries `status`, `run_id` and `metadata`, and none of them says *"the knowledge engine was DEGRADED when this was answered"*. |
| **Potential improvement** | Attach the degradation verdict of the subsystems a run actually used to that run's record — and keep it, even after they recover. |
| **Complexity** | Medium — the probe and the trail both exist; this joins them |
| **Risk** | Low. It adds information and removes none. The real risk is the opposite one: it will make some past answers look worse than they did, which is the point |
| **Reversibility** | High — one field, ignorable by any reader that does not want it |
| **Provisional class** | **A — USEFUL NOW** (candidate) |

This is the principle that fits GalSen IA's existing philosophy most exactly.
The platform already refuses to present an ungrounded answer as grounded; it
does not yet refuse to present a **degraded** answer as healthy.

### P8 — Two interface classes, with opposite promises

| Field | |
|---|---|
| **Linux principle** | In-kernel interfaces are deliberately unstable. The kernel-to-userspace interface *"is **very** stable over time, and will not break"*. |
| **Problem it solves** | Freezing internals prevents repair; breaking the external contract breaks every user. The two need opposite rules, stated. |
| **GalSen IA equivalent problem** | Same shape: `src/` modules are refactored freely, while 143 HTTP routes are what callers depend on. |
| **Current solution** | Partly, and by habit rather than statement: `tests/test_published_numbers.py` pins the route count, ADRs govern compatibility, `.claude/rules/spec-driven-governance.md` requires that *"existing APIs remain compatible unless explicitly authorised"*. |
| **Potential improvement** | State the boundary once, as Linux does: which surfaces are contracts and which are internals. Chapter 08 decides whether that is worth an ADR. |
| **Complexity** | Low — a document, not code |
| **Risk** | Very low |
| **Reversibility** | Total |
| **Provisional class** | **B — USEFUL LATER** |

### P9 — Tracing is built in, not compiled in for the occasion

| Field | |
|---|---|
| **Linux principle** | ftrace is present in the running kernel and switched on at runtime. |
| **Problem it solves** | A failure that only appears in production cannot be investigated by a build that is not in production. |
| **GalSen IA equivalent problem** | Same. |
| **Current solution** | `src/router/decision_trace.py`, `src/observability/trail.py`, the audit engine, `src/api/metrics.py`, and one identifier carried across subsystem boundaries. Always on. |
| **Potential improvement** | None identified. |
| **Complexity** | — |
| **Risk** | — |
| **Reversibility** | — |
| **Provisional class** | **D — ALREADY COVERED** |

---

# Chapter 04 — Self-healing, compared

The brief calls this out as particularly important. Nine points, each measured
on both sides.

| | Linux | GalSen IA | Verdict |
|---|---|---|---|
| **Fault detection** | BUG, oops, panic; the state is printed with the fault | Degradation probes; traceback parsed for file, line, exception type — and *"a traceback is data […] never read as an instruction"* | **Covered**, and hardened against a class of attack the kernel does not face |
| **Isolation of the fault** | The faulting task dies; the kernel survives where it can | Repair is applied in an isolated workspace, merged only if every gate passes | **Covered** |
| **Resource exhaustion** | OOM killer; cgroup limits | `setrlimit` for sandboxed tool code. **Nothing for agents** | **Gap** — P5 |
| **Process failure** | Parent reaps; group semantics | Group killed after *every* sandbox execution, not only on timeout | **Covered** |
| **Subsystem failure** | Taint flag, permanent | Probe says `UNAVAILABLE` and carries the exception as the reason — **but nothing marks the results produced meanwhile** | **Gap** — P7 |
| **Restart** | The kernel does not restart itself | Rollback, then merge or refuse | **Covered, differently and deliberately** |
| **Recovery decision** | Left to the operator | *"the dangerous part of automated repair is not writing the patch, it is deciding the patch worked"* — everything after `propose_patch` is a gate | **Covered, and better stated** |
| **Observability of the decision** | dmesg, taint state printed at the fault | `decision_trace.py`, audit events, the trail | **Covered** |
| **Fault injection** | A parameterised facility | **Nothing.** The habit exists; the facility does not | **Gap** — P6 |

### What this chapter concludes

**Six of nine are covered, and two of those are better stated here than in the
kernel** — because GalSen IA faces an adversary the kernel does not: text that
arrives from a failing component and may have been written to be read as an
instruction.

The three gaps are exactly the three candidates already carried: **P5** (a bound
on an agent), **P6** (fault injection as a facility), **P7** (a result remembers
the state it was produced under).

None of the three is an architecture change. All three add a guard or a field to
something that already exists — which is what a research audit should hope to
find, and the opposite of what "adopt the Linux model" would have produced.

# Chapter 05 — Resource management

The brief asks whether GalSen IA needs quotas, priorities, isolation, admission
control, scheduling, backpressure, workload accounting or graceful degradation —
and to say so explicitly when it does not.

**It needs none of them. It needs something else, and the measurement is
unambiguous.**

## P10 — Blocking work must not run where everything else waits

`grep` over `src/api/server.py`: **144 `async def` routes, and zero uses of
`run_in_executor`, `to_thread` or `anyio.to_thread`.** The orchestrator is
called synchronously from inside `async def` handlers (`server.py:1506`,
`:2282`, `:2399`).

In Starlette, an `async def` endpoint runs **on the event loop**. Blocking inside
it stalls the whole process.

Measured on this machine, 2026-08-23, with a live uvicorn on port 8123:

| Request | Time |
|---|---:|
| `/health` alone, three times | **4.2 ms · 3.9 ms · 3.5 ms** |
| `/health` issued 0.25 s into a `/chat` | **1 149 ms** |

**A 274× slowdown**, and the 1.149 s is precisely the remainder of the `/chat`
turn. The health check did not answer slowly — it waited for the chat to finish.

Two consequences, neither hypothetical:

- **The platform cannot report its own health while it is working.** A
  supervisor polling `/health` with a 1 s timeout would declare a working
  platform dead.
- Every concurrent user waits for every other user's slowest agent, with no
  queue, no priority and no way to see it happening.

| Field | |
|---|---|
| **Linux principle** | A task that blocks is descheduled; it does not hold the CPU because it decided to. |
| **Current solution** | None. Blocking orchestration runs on the event loop. |
| **Potential improvement** | Run blocking orchestration off the loop — in Starlette this is one decision per endpoint, not an architecture. |
| **Complexity** | **Low** |
| **Risk** | Low, and testable: the measurement above is the test |
| **Reversibility** | **Total** — it is a call-site change |
| **Provisional class** | **A — USEFUL NOW** (candidate) |

## The brief's list, answered

| Mechanism | Needed? | Why |
|---|---|---|
| Resource quotas | **No** | One instance (ADR-009), no tenants competing for a shared budget |
| Priorities | **No** | Nothing queues, so nothing can be prioritised |
| Isolation | **Partly** — see chapter 06 | Covered for tool code, absent for agents |
| Admission control | **No, not yet** | It would shed load the platform cannot currently even measure. Fix P10 first; re-ask afterwards |
| Scheduling | **No** | Sequential by design, and the engine says so |
| Backpressure | **No** | Requires a queue; there is none |
| Workload accounting | **No** | `elapsed_seconds` per turn already exists where it matters |
| Graceful degradation | **Already covered** | `src/integration/degradation.py`, three verdicts, reasons carried |

**Seven of eight are not needed.** Adding any of them would be building a
scheduler for a platform that schedules nothing — the exact failure this audit
was told to avoid.

---

# Chapter 06 — Agent isolation

## What exists

- **Tool code** crosses a process boundary and runs under six `setrlimit` bounds
  applied before its first instruction (`src/sandbox/`).
- **Agents** do not. They are imported and called in the orchestrator's own
  interpreter (chapter 01, finding 3). An agent cannot be bounded, killed or
  accounted for.
- **Permissions** are capability-shaped: 35 named permissions, and a real
  ceiling in `PERMISSIONS_HORS_PLATEFORME`.
- **Untrusted input** is handled at `src/security/trust.py`: external text is
  data with an origin, never an instruction.

## P11 — A limitation asserted is not a limitation measured

This is the finding of the chapter, and it is about the repository rather than
about Linux.

`src/sandbox/policy.py:57` states, as a fact, that a real per-execution process
cap needs *"cgroups, therefore privileges the platform does not have"*.

**Measured on this machine, 2026-08-23:**

| Probe | Result |
|---|---|
| `/proc/sys/user/max_user_namespaces` | **64262** |
| `unshare -Un true` | **succeeds** — a user + network namespace is creatable |
| cgroup2 mount | **`cgroup2 on /sys/fs/cgroup/unified (rw)`** |
| `cgroup.subtree_control` at that path | **absent** — delegation not usable as-is |
| uid | 0, `CapEff: 000001fffeffffff` |

So on this machine the network cut that `NON_GARANTI` calls impossible is, in
fact, **creatable**. The assertion is not false everywhere — it is
**environment-dependent, and was written as absolute**. This container runs as
root with a near-full capability set; the owner's Windows machine has neither
mechanism, and a production host is a third unknown.

**And the repository already knows how to do this correctly, in another
subsystem.** `src/media/core/capabilities.py` opens with *"What this machine can
actually do to media — asked, never assumed"*, and explains why a boolean is
wrong **in both directions**: this environment's `ffmpeg` is absent from `PATH`
yet present elsewhere, and that copy is built `--disable-everything`. So the
media engine interrogates the binary — `-encoders`, `-decoders`, `-demuxers`,
`-protocols` — and reports capability by capability.

The sandbox asserts where the media engine measures.

| Field | |
|---|---|
| **Linux principle** | Isolation mechanisms are queryable; whether one is available is a property of the running system, not of the program's opinion. |
| **Problem it solves** | A sandbox claiming a boundary it lacks is worse than none — and one *refusing* a boundary it has silently gives up protection it could have had. |
| **GalSen IA equivalent problem** | Exactly this, measured above. |
| **Current solution** | An assertion in a prose tuple. |
| **Potential improvement** | Probe, and report what was found — the pattern `src/media/` already uses. **No new isolation mechanism is proposed here**, only that the platform stop guessing about its own. |
| **Complexity** | Low |
| **Risk** | **Low, and asymmetric**: today the platform under-claims, which is the safe direction. Any use of a discovered namespace is a separate decision, not part of this |
| **Reversibility** | High |
| **Provisional class** | **A — USEFUL NOW** (candidate, documentation-and-probe only) |

## What is explicitly not recommended

- **Do not sandbox agents by moving them to processes.** They are first-party
  code loaded from a declared registry, not untrusted input. The cost is high,
  the benefit is bounded, and P5 (a time bound) addresses the failure that
  actually occurs.
- **Do not add namespaces to the sandbox** on the strength of one measurement on
  one container running as root. P4 stays **F — BLOCKED**; what changes is that
  the *reason* must be measured rather than asserted.
- **Do not weaken anything.** No existing check is relaxed by any candidate in
  this audit.

# Chapter 07 — Observability

The brief asks for **measurable** improvements only. Two hypotheses were tested
and one of them was wrong, which is recorded here rather than quietly dropped.

## What was expected to be missing, and is not

The audit expected no per-agent timing — the natural companion of P5, since a
bound you cannot measure is a bound you cannot choose. **It exists.**
`src/router/router_engine.py:235` declares `agent_durations`, commented in the
repository's own words as *"Durée observée de chaque agent, reprises comprises"*,
measured with `time.perf_counter()` around each dispatch (`:310`, `:316`).

The hypothesis was wrong. The measurement corrected it, which is the only reason
this audit is worth anything.

## What is measurably missing

**1. Per-agent durations are recorded but not returned.** `agent_durations`
reaches `workflow_history` and stops there: `grep -rln agent_durations src/`
matches `router_engine.py` and `workflow_history.py` and nothing else. The
response payload carries `execution_time_seconds` and a `metadata` block with
agent counts — **not the per-agent breakdown**. An operator holding a slow
response cannot see which agent was slow without going to the history store.

**2. A bounded execution reports how long it ran, never what it consumed.**
`SandboxResult` carries `exit_code`, `stdout`, `stderr`, `timed_out`,
`killed_by`, `truncated`, `duration_seconds`, `notes`. There is **no CPU time
and no peak memory**.

### P12 — Account what was consumed, not only how long it took

| Field | |
|---|---|
| **Linux principle** | The kernel accounts resource usage per process and hands it back — user time, system time, peak resident set — independently of whether the process succeeded. |
| **Problem it solves** | *"It worked"* and *"it worked with 2 MB of headroom"* are different facts, and only the second one predicts tomorrow's failure. |
| **GalSen IA equivalent problem** | The sandbox enforces six bounds and reports which one killed a process — but a **successful** run says nothing about how close it came. Limits cannot be tuned from data that is not collected. |
| **Current solution** | `duration_seconds` only. |
| **Potential improvement** | The sandbox already crosses a process boundary and already imports `resource`; the usage of a reaped child is available at the point where the result is already being assembled. |
| **Complexity** | **Low** |
| **Risk** | Very low — additive fields; no behaviour depends on them |
| **Reversibility** | **Total** |
| **Provisional class** | **A — USEFUL NOW** (candidate) |

Surfacing `agent_durations` in the response is smaller still and rides along
with the same reasoning; it is folded into P12 rather than given a number of its
own.

## What is already covered, and stated so it is not re-proposed

| Concern | Where |
|---|---|
| Orchestration traces | `src/router/decision_trace.py` |
| Cross-subsystem trace | `src/observability/trail.py`, one identifier surviving boundaries |
| Failures | Audit engine, `killed_by`, `UNAVAILABLE` carrying its exception |
| Latency | `agent_durations`, `execution_time_seconds`, `elapsed_seconds` |
| Provenance | Corpus registry; every entity and relation carries its own |
| Self-healing decisions | Gate-by-gate, with rollback recorded |

And `trail.py` distinguishes *"no audit event carries this identifier"* from
*"the audit engine is unavailable"* — the `ABSENT` versus `UNKNOWN` discipline,
applied where most systems collapse the two.

---

# Chapter 08 — Architectural boundaries

The brief lists thirteen candidate boundaries and instructs: **do not restructure
unless the audit proves it necessary.**

## Measured

| | |
|---|---:|
| Module directories under `src/` | **43** |
| `src/api/server.py` | **4 689 lines**, 78 imports from `src/` |
| Files importing `src/tool` from outside it | **39** |
| Files importing `src/security` from outside it | **14** |
| `knowledge_engine` · `memory_engine` · `sandbox` · `model_engine` | 8 · 5 · 4 · 4 |
| `router` · `media` | 2 · 2 |

**Eleven of the brief's thirteen boundaries already exist as directories**, and
coupling across them is low — the orchestrator is imported from two files
outside itself, the media engine from two. This is not a codebase whose
subsystems have leaked into each other.

## Verdict: no restructuring is justified

The one large object is `src/api/server.py`. `.claude/rules/coding-standards.md`
says *"Avoid large monolithic files"* and *"Avoid God Objects"*, and 4 689 lines
with 78 imports is both. **But the audit found no defect caused by it**, and a
maintainability preference is not measurable evidence. Splitting it would be
precisely the *"opportunistic refactoring"* that
`.claude/rules/spec-driven-governance.md` forbids.

**Recorded as an observation, generating no task.**

## The one boundary worth stating rather than building

P8, from chapter 03: Linux keeps two interface classes with **opposite**
promises — in-kernel interfaces deliberately unstable, the userspace interface
never broken. GalSen IA has the same split in fact (43 refactorable modules
behind 143 HTTP routes) but holds it by habit: a route-count test, the ADRs, and
one line of governance.

Naming it once would cost a document and no code. **`B — USEFUL LATER`**, and
only if the owner wants it; nothing depends on it today.

# Chapter 09 — Licence findings

**Not legal advice.** What follows is measured fact plus a reading; where the
reading is a legal question, it is marked `UNKNOWN` rather than answered.

## What Linux is, from its own `COPYING`

> `SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note`
>
> *"Being under the terms of the GNU General Public License version 2 only"*

**GPL-2.0 *only***, with an explicit syscall exception. The brief's statement
that Linux is "primarily GPL-2.0" is confirmed at the source.

## The licence of each file this audit actually read

Checked per file, searching the whole file and not only its header:

| File | SPDX tag |
|---|---|
| `filesystems/vfs.rst` | **`GPL-2.0`** |
| `locking/locktypes.rst` | **`GPL-2.0`** |
| `process/license-rules.rst` | **`GPL-2.0`** (rst comment form) |
| `admin-guide/cgroup-v2.rst` | none |
| `security/credentials.rst` | none |
| `scheduler/sched-eevdf.rst` | none |
| `trace/ftrace.rst` | none |
| `fault-injection/fault-injection.rst` | none |
| `admin-guide/tainted-kernels.rst` | none |
| `process/stable-api-nonsense.rst` | none |

Six files carry no tag anywhere. `license-rules.rst` states the tree-wide rule —
*"The Linux Kernel is provided under the terms of the GNU General Public License
version 2"* — so the reasonable reading is that untagged files fall under it.

**`UNKNOWN`:** the canonical SPDX licence texts are unreachable from this
machine (`spdx.org` → `000`, measured), so nothing here rests on the exact
wording of the licence itself.

## GalSen IA is Apache-2.0 (ADR-036)

GPL-2.0-only and Apache-2.0 do not combine into one work. This is exactly why
the brief forbids copying, and the prohibition is the right one.

## Why this audit creates no licence obligation

Two distinct things were done, and they have different answers.

**1. Principles were extracted.** Copyright protects expression, not ideas,
procedures or methods of operation. *"A limit and a guarantee are different
promises"*, *"a taint is permanent"*, *"privilege is a set of named powers with a
ceiling"* — these are ideas. Reading them creates no obligation, and none of
them arrived as code.

**2. Passages were quoted.** Measured, not estimated:

| | |
|---|---:|
| Kernel quotations verified verbatim against the fetched source | **7** |
| Longest single quotation | **132 characters** |
| Total kernel text quoted | **624 characters** |
| Total kernel text read | **421 031 characters** |
| Proportion quoted | **0.148 %** |

Every one is attributed to its file, used for commentary, and none substitutes
for reading the original.

**`UNKNOWN`:** whether that constitutes fair use, fair dealing, or the quotation
right of any particular jurisdiction is a legal question this audit cannot
settle. What it can do is keep the quantity measured and small, and it has.

## Conclusion

No licence concern is created by any recommendation in this audit, because every
recommendation is a principle applied to GalSen IA's own code — **not one line
of kernel source is proposed for inclusion, adaptation or reference.** If any
future phase proposes otherwise, this chapter is void and the question must be
re-asked.

---

# Chapter 10 — Proof that no code was copied

The brief prohibits copying, vendoring and importing. A prohibition is worth
what its verification is worth, so this chapter measures rather than asserts.

| Check | Result |
|---|---|
| Kernel files tracked by git (`.rst`, `.c`, `.h`, `COPYING`) | **none** — `git ls-files` matches nothing |
| Where the 12 fetched kernel files live | `/tmp/…/scratchpad/`, **outside the working tree** |
| File extensions added by this whole branch | `md` 19 · `py` 17 · `html` 2 · `js` 1 · `css` 1 · `bat` 1 |
| Kernel-shaped extensions among them | **zero** |
| Longest kernel quotation | 132 characters |
| Total kernel text in the repository | 624 characters, all attributed |

**No dependency was added.** No `requirements` file was touched by this audit;
no kernel component is vendored, imported, adapted or reimplemented.

**No architecture was changed by this audit.** It has written exactly two
files: this document and `docs/memory/phase-plan.md`.

**And the check that proves it caught the claim being too broad.** Measured
`git diff --name-only 3c8022a^..HEAD`, four files have changed since the VOLET
opened — the two above, plus `src/api/server.py` and `tests/test_api_chat.py`.

Those two are **not** the audit. They are the fix for a CI failure that arrived
mid-VOLET: `/chat` returned `503` whenever the researcher found something,
because the web search succeeds on GitHub runners and cannot on this machine.
The fix and its five tests were committed separately (`bf1853b`) and are
described in that commit, not here.

The first version of this paragraph said *"nothing under `src/`, nothing under
`tests/`"*. That was false, and the verification is what said so — which is the
whole reason a prohibition is worth what its check is worth. Corrected rather
than quietly narrowed.

Re-check this at the end of chapter 13: it is the claim an audit most easily
stops being able to make.

---

*Chapters 11 to 13 pending.*
