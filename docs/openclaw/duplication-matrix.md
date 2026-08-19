# O02 — Duplication matrix (§5)

**Built**: 2026-08-19, from `repo-audit.md` (O00, VERIFIED FROM REPOSITORY) and
`openclaw-audit.md` (O01, VERIFIED FROM OFFICIAL SOURCE), plus two documents
read for this phase and cited inline.

§5's rule is the one this matrix exists to obey: **never integrate something
merely because it is popular.** 386.8k stars is not a row in this table.

Decisions available: `KEEP_EXISTING` · `OPENCLAW_COMPLEMENT` · `INTEGRATE` ·
`OPTIONAL` · `DEFER` · `REJECT` · `UNKNOWN`.

---

## The matrix

| Capability | GalSen IA existing | OpenClaw | Overlap | Advantage | Decision |
|---|---|---|---|---|---|
| **Planning** | `src/router/execution_planner.py`, `decision_trace.py`, workflow validation before run | Turn includes *"context assembly"* and *"prompt assembly"*; no planner named | `UNKNOWN` | — | `KEEP_EXISTING` |
| **Tool calling** | `src/tool/` — engine, loader, executor, `capabilities.py` (effects, data scope, pre-approvals), `authorization.py` (role × effect ceiling) | Executes tool calls itself; *"Tool start/update/end events emit on the `tool` stream"* | **high** | GalSen IA: authorisation is **per call**, with `REQUIRES_APPROVAL` as a third answer | `KEEP_EXISTING` |
| **Task execution** | `AgentRuntime.execute_task`; **exactly two orchestration paths**, both on the same engine | `req:agent` → `event:agent` streaming → `res:agent final {runId, status, summary}` | **high** | GalSen IA: one engine, checkpoints, execution history, audit event on both paths | `KEEP_EXISTING` |
| **Sessions** | `src/auth/session_manager.py` (identity), `src/agent/context.py` (execution) | *"The Gateway is the single source of truth for sessions"*; *"isolated sessions per agent, workspace, or sender"* | **high** | OpenClaw: session isolation **per sender** is finer-grained than anything here | `DEFER` — the idea, not the code (see below) |
| **Memory** | `src/memory_engine/` — 11 modules, manager/store/retriever/indexer/cache/ranker/summarizer/quality/layers | Turn ends in *"persistence"*, with *"compaction"*; no memory architecture read | `UNKNOWN` | — | `KEEP_EXISTING` |
| **Skills** | **`PARTIAL`** — `src/media/skills/registry.py` only, media-scoped; promotion needs a named validator | Skills present in *"context assembly (workspace/skills/bootstrap preparation)"*; ClawHub is a distribution surface | **low** | OpenClaw: a platform-wide skill surface exists; GalSen IA has none | `DEFER` — O07 audits skills as untrusted first |
| **Plugin system** | `src/plugins/` — `contract`, `manifest`, `registry`, `execution`, `review` | Channel plugins (Matrix, Nostr, Twitch, Zalo); *"official plugins install on demand"* | **medium** | GalSen IA: a `review.py` step exists before execution | `KEEP_EXISTING` |
| **Long-running tasks** | `src/routines/scheduler.py`, `workflow_checkpoint.py`, `src/media/queue/jobs.py` | *"A single long-lived Gateway"*; `cron` events | **medium** | GalSen IA: checkpoints survive a suspension for human approval | `KEEP_EXISTING` |
| **Error recovery** | `src/agent/self_healer.py`, two `retry_manager.py` (router and model layers) | `docs/gateway/restart-recovery.md` exists; **not read** | `UNKNOWN` | — | `UNKNOWN` — O09 |
| **Delegation** | `src/router/agent_dispatcher.py`, **17 agents** in `agents/registry.yaml` | `docs/concepts/multi-agent`; *"isolated sessions per agent"* | **medium** | `UNKNOWN` | `DEFER` — O06 |
| **Agent loops** | `AgentRuntime` | `docs/concepts/agent-loop.md`, read: intake → context → inference → tools → stream → persist | **high** | neither demonstrated over the other | `KEEP_EXISTING` |
| **Human approval** | `src/approval_engine/` + `Decision.REQUIRES_APPROVAL` + ADR-006 gate; *an approval is never granted by the absence of someone to refuse it* | Four session **permission modes** (below); `before_tool_call` hook where *"`{ block: true }` is terminal"*; core loop *"does not detail specific human-in-the-loop mechanisms"* | **medium** | GalSen IA: approval is a **state a run can suspend into**, not a mode set beforehand | `KEEP_EXISTING` |
| **Sandboxing** | `src/sandbox/policy.py` + `runner.py`, **shipped with escape tests** (ADR-017 §5) | Off by default; *"This is not a perfect security boundary"*; Gateway itself unsandboxed; `tools.elevated` runs on host | **high** | GalSen IA: on by design and tested by attempting escape | `KEEP_EXISTING` |
| **Observability** | `src/observability/trail.py` (a job followable end to end), `src/api/metrics.py`, `tracing.py`, `src/audit_engine/` | `opentelemetry.md`, `prometheus.md`, `logging.md`, `audit.md` exist in `docs/gateway/`; **contents not read** | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` — O08 |

**Eight `KEEP_EXISTING`, three `DEFER`, two `UNKNOWN`, zero `INTEGRATE`.**

---

## Permission granularity — the comparison that matters most

Read for this phase from `docs/gateway/permission-modes.md`
(VERIFIED FROM OFFICIAL SOURCE, 2026-08-19):

| Mode | Filesystem | Escalation review |
|---|---|---|
| `read-only` | reads under `sessionRoot`, mutation tools omitted | none; exec denied |
| `guarded` | reads and writes under `sessionRoot` | *"A human after the allowlist fast path"* |
| `workspace` | reads and writes under `sessionRoot` | *"LLM review, with human fallback"* |
| `full` | *"Unrestricted filesystem access"* | none |

*"A new managed worktree session defaults to `workspace` when no mode is
specified."* — so the default has **an LLM reviewing escalations, with a human
as fallback**. *"`full` requires `operator.admin`. The other modes require
`operator.write`."*

**The two systems are not the same shape.** OpenClaw scopes permission to a
**session**, chosen when the session starts. GalSen IA scopes it to a **call**:
`authorize(tool_id, actor)` answers per invocation, with role ceilings, effect
ceilings, a data-scope ceiling, and `REQUIRES_APPROVAL` as a distinct third
answer that is neither yes nor no.

`INFERENCE`: a session-scoped mode cannot express *"this actor may call this
tool with these arguments, and that one needs a human"*. Placing OpenClaw
**under** GalSen IA's authorisation — which §6 requires anyway — is therefore
not a courtesy, it is the only arrangement in which GalSen IA's permission model
survives contact.

**A correction this phase owes the repository.** Our own
`docs/architecture/agent-foundations-comparison.md` (2026-08-12) attributes to
OpenClaw a *"trusted vs constrained sessions"* distinction. Today's
`permission-modes.md` **does not use those terms**; it defines a four-mode
scale. The older phrasing is recorded as **UNVERIFIED** rather than repeated —
which is exactly why O00 refused to inherit that document.

---

## What OpenClaw would actually add — and it is not on §5's list

§5 lists fourteen capabilities. **Thirteen of them, GalSen IA already has**, and
the matrix says `KEEP_EXISTING` or `UNKNOWN` for every one. The genuine
difference is a category the directive never asks about:

**Bidirectional conversational channels.** WhatsApp, Telegram, Slack, Discord,
Signal, iMessage and WebChat in the core, plus Matrix, Nostr, Twitch and Zalo as
plugins (VERIFIED FROM OFFICIAL SOURCE). GalSen IA has
`config/notifications/channels.yaml` with exactly three: `in_app`, `email`,
`webhook` — **all one-way, all operator-facing**. There is no path by which a
person messages GalSen IA from WhatsApp and gets an answer.

`INFERENCE`, and it is this phase's main conclusion: **the honest reason to want
OpenClaw here is reach, not orchestration.** For a platform whose stated purpose
is serving Senegal — where WhatsApp is how people actually talk — that is not a
small thing. But it is a *channel* question, and answering it by adopting an
agent runtime would import a gateway, an agent loop, a permission model and a
sandbox in order to obtain a messaging surface.

The matrix does not decide this. It records it, and O11 has to weigh it against
the alternative nobody has costed yet: a channel connector under the existing
orchestrator, in the shape `src/connectors/` already has.

---

## Three duplications O00 recorded, now judged

1. **Two job vocabularies** (`RenderJob`, `CreativeJob`) — internal to GalSen
   IA, **unrelated to OpenClaw**. Not this programme's business; recorded in
   `pending-work` terms, not fixed here.
2. **Two retry managers** — same, and still not read. Unchanged.
3. **Skills scoped to one engine** — this one **is** relevant: it is the single
   row where GalSen IA is `PARTIAL` and OpenClaw is not. `DEFER` to O07, which
   §12 requires to treat every skill as untrusted until audited.

---

## What this matrix does not claim

- That OpenClaw is worse. Eight `KEEP_EXISTING` verdicts say GalSen IA already
  has the capability **and** that its version carries guarantees this repository
  has already committed to — not that the other implementation is inferior.
- That the `UNKNOWN` rows will stay unknown. Error recovery and observability
  have documents that exist and were not read; O08 and O09 own them.
- That the channel finding is a recommendation. It is a measured asymmetry,
  handed to O11.
