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

---

*Chapters 02.2 to 13 pending. No recommendation is made before the feasibility
gates of chapter 11.*
