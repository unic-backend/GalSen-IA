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

---

*Chapters 02 to 13 pending. No recommendation is made before the feasibility
gates of chapter 11.*
