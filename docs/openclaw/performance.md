# O10 — Performance analysis (§17)

**Measured**: 2026-08-19, on `Linux 6.18.5-fc-v20`, Python `3.11.15`, **4 CPUs**.
A figure without the machine that produced it compares to nothing.

§17's closing rule governs this whole phase: *"If no benchmark can be performed:
UNKNOWN. Never fabricate numbers."*

---

## 1. The comparison §17 asks for cannot be made, and here is why

§17 asks to compare **existing GalSen IA** against **GalSen IA + OpenClaw**.

**The right-hand column is `UNKNOWN` in every row, and not for want of trying.**
§20 forbids installing OpenClaw during the audit — *"DO NOT install OpenClaw
during the first audit"* — so there is nothing to measure. This is a rule of the
directive colliding with a request of the directive, and the resolution is the
one §17 states itself: `UNKNOWN`.

**What this phase does instead** is measure the **left-hand column properly**,
so that a future benchmark has something real to compare against. A baseline
measured today is worth more than a comparison invented today.

---

## 2. GalSen IA baseline, measured

| §17 asks for | Measured | Note |
|---|---|---|
| **Startup time** | `import src.api.server` → **651.8 ms** | one process, cold |
| **Tool latency** | `authorize()` with a shared registry → **0.003 ms** | the production path |
| — same, without a shared registry | **21.5 ms** | see §3 below |
| **Memory usage** | peak RSS after importing the API → **67.6 MB** | `ru_maxrss` |
| **CPU usage** | 4 CPUs available | not a load measurement |
| **GPU usage** | **none** — `torch` is not importable, no GPU | measured in four previous programmes |
| **Task latency** | **`NOT_MEASURED`** | needs a model; `ollama serve` is not running |
| **Concurrency** | **`NOT_MEASURED`** | no load harness exists |
| **Failure rate** | **`NOT_MEASURED`** | requires real traffic over time |
| **Recovery time** | **`NOT_MEASURED`** | requires inducing a failure under load |

**Four of nine measured, five `NOT_MEASURED` with their reason.** None is zero,
and none is estimated.

---

## 3. A real finding, and the discipline to state it correctly

`authorize()` called **without** a registry costs **21.5 ms**, because it calls
`load_capabilities()`, which reads and parses `tools/tools.yaml` on **every
call** — measured at **21.96 ms**, with no caching (`lru_cache` absent from its
source).

**And it is not on the request path.** Both call sites in `src/api/server.py`
pass a pre-loaded registry:

```python
verdict = authorize(request.tool_id, Actor.from_rbac(ctx), tool_engine.capabilities)
```

So the production cost is **0.003 ms**, and reporting "authorisation costs 22 ms"
would be false. What is true is narrower and still worth writing down:

> **`load_capabilities()` is uncached and costs ~22 ms. Today every caller in
> the API passes a shared registry, so the cost is latent. A future caller that
> omits the argument gets a 7 000× slower authorisation and no warning.**

Recorded for `pending-work`, **not fixed here** — it is GalSen IA's own, unrelated
to OpenClaw, and `.claude/rules/spec-driven-governance.md` calls fixing it scope
expansion. It was found because §17 made me measure the thing rather than assume
it.

---

## 4. What OpenClaw declares about its own requirements

`docs/install/index.md`, read 2026-08-19, VERIFIED FROM OFFICIAL SOURCE:

- **Node** `22.22.3+`, `24.15+`, or `25.9+`, with Node 26 recommended.
- **OS**: macOS, Linux, Windows.
- **RAM, CPU, disk, GPU**: *"No minimum RAM, CPU, disk space, or GPU
  requirements are stated in the documentation."*
- **Resource usage or performance specifications**: none provided.

Two consequences.

**A second runtime, not a library.** Node 22+ alongside Python 3.11 means a
second language runtime, its own process, its own memory. `INFERENCE`: the
platform's measured 67.6 MB baseline would gain an OpenClaw gateway of
**`UNKNOWN`** size — and *"unknown"* is the correct word, because the project
states no figure and none was measured here.

**Nobody has published the number.** That is not a criticism; it is a fact that
makes §17's comparison unanswerable from documentation as well as from
measurement. Both routes to the number are closed today.

---

## 5. What would settle it, precisely

For a future phase, and cheap enough to be worth naming exactly:

1. Install OpenClaw in an environment permitted to install (**not this one**).
2. Measure gateway idle RSS and startup time.
3. Measure a round trip: `adapter → gateway → allowlisted tool → back`, against
   the same tool called directly. **That difference is the only number that
   matters** — it is the cost the adapter adds, and everything else is context.
4. Repeat under the per-task session shape O09 requires, since a session created
   and destroyed per task has a startup cost a long-lived session does not.

Point 4 is the one a naive benchmark would miss, and it could be decisive: if
per-task session creation costs seconds, the arrangement that O04, O06 and O09
all independently required becomes expensive in exactly the way the audit did
not anticipate.

---

## 6. What O10 concludes

- **§17's comparison is `UNKNOWN`**, because §20 forbids the installation that
  would make it measurable. Stated as a collision between two of the directive's
  own rules, not as an omission.
- **The baseline is measured**: 651.8 ms startup, 67.6 MB, 0.003 ms per
  authorisation on the production path, no GPU.
- **Five of nine figures are `NOT_MEASURED`** with a named reason each.
- **One latent cost found and recorded**: `load_capabilities()` is uncached at
  ~22 ms, harmless today because every API caller passes a shared registry.
- **One benchmark named for later**, and the measurement that would decide it:
  the cost of a per-task session.
