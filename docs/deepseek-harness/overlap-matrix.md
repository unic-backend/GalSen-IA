# D04 — GalSen IA overlap matrix (Phase 2)

**Built**: 2026-08-20. GalSen IA facts VERIFIED FROM REPOSITORY with paths;
DeepSeek Harness facts VERIFIED FROM OFFICIAL SOURCE (D00), or `UNKNOWN` where
D00 left them so.

Phase 2's classes: **A** complementary · **B** duplicate · **C** conflicting ·
**D** potentially replaceable · **E** unnecessary · **F** `UNKNOWN`.

*"Do NOT modify existing architecture during this audit"* — nothing under `src/`
was touched.

---

# D04.1 — Orchestration, providers, tools, execution, security

| # | Subsystem | GalSen IA | DeepSeek Harness | Class |
|---|---|---|---|---|
| 1 | **Agent orchestration** | `src/router/` — 16 modules; **exactly two orchestration paths**, both on the same engine; 17 agents | agent loop in `core/agent-loop`, **replaceable**, *"patchable infrastructure, not privileged"*; `subagent`, `workflow`, `spawn_teammate`, `team_task_*` (experimental) | **C — conflicting** |
| 2 | **Provider abstraction** | `src/model_engine/providers/` + `ModelRouter` + `config/model_routing.yaml`; ADR-014 sovereign default **does not register** hosted providers | model adapter is a plugin; **which providers: `UNKNOWN`** (D00) | **F** |
| 3 | **Tool routing** | `src/tool/` — 24 declared tools, effects × data scope × approval, `authorize()` **per call** | ~50 tools in `docs/tool-catalog.md`; registered from `packages/*/tool-*`; permissions **per session** | **C — conflicting** |
| 4 | **Memory** | `src/memory_engine/` — 11 modules, `user_id` filtered in SQL | `compaction`, `session` subsystems; a memory architecture distinct from session state: **`UNKNOWN`** | **F** |
| 5 | **Knowledge** | `src/knowledge_engine/`, `corpus/`, Wolof 2 105 sentences, 14 regions / 45 departments, provenance on every item | **nothing comparable found** | **A — complementary** (it does not touch this) |
| 6 | **MCP** | `src/mcp/` — server, client with pinning, exposure whitelist | exists — rc.7 notes *"durable image attachments for MCP/ACP"*; raw-JSON-Schema MCP tools share the catalog. **Depth `UNKNOWN`** | **F** |
| 7 | **Execution** | `AgentRuntime.execute_task`; `src/tool/tool_executor.py` | tool pipeline `tool/call* → pre-execute → execute → post-execute → tool/result*`, as **durable session events** | **B — duplicate** |
| 8 | **Sandboxing** | `src/sandbox/policy.py` — RLIMIT-based; **filesystem and network explicitly not bounded** (`NON_GARANTI`), because namespaces need privileges the platform lacks | **kernel-level**: `bwrap`/Landlock, Seatbelt, ACL restricted-token; three modes; **file effects only** — *"Network and process visibility are outside this vocabulary"* | **A — complementary**, and see below |
| 9 | **Self-healing** | `src/agent/self_healer.py` — diagnose → propose → validate → apply → tests → security tests → ruff → integrity → merge \| rollback | crash recovery on session logs (open `turn/start` closed with synthetic boundaries); a **repair** loop: **`UNKNOWN`** | **F** |
| 10 | **Security** | `src/security/` — trust boundary, redaction (names not values), isolation, posture | sandbox + approval presets; credentials *"resolved once per operation"*; **whether credentials reach plugins: `UNKNOWN`** | **F**, pending D07 |

## The sandbox row is the finding of D04.1

**GalSen IA's sandbox and DSH's sandbox fail on opposite axes.**

`src/sandbox/policy.py` bounds CPU, memory, file size, processes, wall time,
output and **environment** — a child sees *no secret* of the parent. What it
explicitly does **not** bound: *"filesystem: un fils lit et écrit là où
l'utilisateur le peut"* and *"network: aucune coupure réseau sans espaces de
noms"*, because those need privileges the platform does not have.

DSH's sandbox bounds **exactly the filesystem**, at kernel level, on three
platforms — and explicitly does **not** cover network or process visibility.

`INFERENCE`, and it is the strongest positive finding of this audit so far:
**each covers what the other cannot.** That is the definition of Phase 2's class
A. It is also the first time in five programmes that an external project's
strength lands precisely on a gap this repository has documented and been unable
to close.

**It does not follow that the two can be combined.** DSH's file confinement is
delivered by `bwrap`/Landlock, and whether *this* environment permits those
syscalls is **`UNKNOWN`** — the same privilege question that blocked the
OpenClaw container boundary may block this too. D07 must measure it, not assume
it either way.

## Why rows 1, 3 and 7 read `conflicting` rather than `duplicate`

Row 7 is a plain duplicate: both execute tools through a pipeline.

Rows 1 and 3 are **conflicting**, and the reason is the same one the OpenClaw
audit found, stated more sharply here because DSH goes further:

- **The agent loop is replaceable and there is *"no privileged core to patch"*.**
  That is an architectural virtue for DSH and a direct collision with GalSen IA,
  whose whole point is that **there is a privileged core** — one orchestrator,
  two paths, the same checkpoints and audit events on both. The directive's own
  non-negotiable rule says GalSen IA remains the strategic orchestration layer.
- **Permissions are per session; ours are per call.** A preset chosen at session
  start cannot express *"this actor, this tool, these arguments, and that one
  needs a human"*.

`C` is not a verdict of *bad*. It means the two cannot both be authoritative,
and Phase 8 has to choose which — which the directive has already done.

---

# D04.2 — Memory, creative, media, identity, workflows

| # | Subsystem | GalSen IA | DeepSeek Harness | Class |
|---|---|---|---|---|
| 11 | **Provenance** | `src/audit_engine/` — `AuditEvent`, nine fields; `src/acquisition/` — nothing enters without a source | `session_event_trace`, `session_trace`, `session-telemetry`; an append-only session log | **A — complementary** |
| 12 | **Identity** | ADR-010 — a key belongs to a subject; `RBACContext.subject`; six education roles; `PERMISSIONS_HORS_PLATEFORME` | **nothing comparable found**; permissions attach to a session, not a person | **A**, and a gap on their side |
| 13 | **Creative state** | `src/creative/` — intent with four statuses, canvas graph, `NOT_REQUESTED` not declarable | **nothing comparable** | **E — unnecessary** (out of its scope) |
| 14 | **Video generation** | `src/media/` — 26 modules, 17-stage chain, readiness computed | **nothing comparable** | **E** |
| 15 | **Multimodal orchestration** | `src/multimodal/`, `src/live_context/` — 16 modules, observations with status | `read_image`, *"native image requests"* in rc.8; multimodal **orchestration**: **`UNKNOWN`** | **F** |
| 16 | **Reference entities** | `src/creative/reference/` — entity, consent scope, memory | **nothing comparable** | **E** |
| 17 | **VoiceScene** | `src/creative/voice/scene.py` — original audio is the source artefact, language per segment | **nothing comparable** | **E** |
| 18 | **World representation** | `src/creative/world.py` — `CharacterMemory`, `WorldMemory`, deliberately separate | **nothing comparable** | **E** |
| 19 | **Autonomous workflows** | `src/routines/` — scheduler, journal, safety; an approval is never granted by absence | `ralph` (*"fresh-agent loops toward immutable objectives"*), `create_goal`, `schedule_create`, `workflow`, `job_*` | **C — conflicting** |

## The shape of the overlap, and it is the opposite of the last one

Nineteen subsystems: **2 `A` in D04.1 plus 2 in D04.2 = 4 complementary**,
**1 duplicate**, **4 conflicting**, **5 unnecessary**, **5 `UNKNOWN`**.

**The five `E`s are the point.** Creative state, video generation, reference
entities, VoiceScene, world representation — DSH touches none of them, and
nothing in its documentation suggests it intends to. That is not a criticism:
it is a **coding-agent harness**, and its tool catalogue says so plainly —
`bash`, `pwsh`, `read`/`write`/`edit`, `glob`/`grep`, `lsp`, persistent PTYs,
`subagent`, `workflow`, `session_*` tracing, `run_code`.

**Compare the previous audit.** OpenClaw overlapped orchestration heavily and
uniquely offered *channels* — a capability GalSen IA lacked entirely. DSH
overlaps orchestration heavily and uniquely offers **depth on the coding side**,
where GalSen IA has `src/coding_engine/` with three declared adapters
(`aider`, `openhands`, `swe_agent`) and a router that *"ne connaît aucun des
trois moteurs par son nom"*.

`INFERENCE`: the honest question for this programme is **not** "should DSH
orchestrate?" — the directive already answers no, and rows 1, 3 and 19 show why
it would collide. It is **"is DSH a better coding backend than the three
adapters already declared?"** That is Phase 3's question, it is answerable in
principle, and D05 must confront the fact that **none of the four can run
here**.

## What D04 hands forward

1. **Four complementary rows**, and one of them — the sandbox — lands exactly on
   a gap `src/sandbox/policy.py` documents as unclosable with current privileges.
   Whether `bwrap`/Landlock is permitted **here** is `UNKNOWN` → D07.
2. **Four conflicting rows**, all on orchestration and permission granularity.
   The directive's non-negotiable rule already resolves them; the matrix records
   *why* rather than re-litigating.
3. **Five `UNKNOWN` rows**, each named with what would close it: providers (D00.2
   left it), memory architecture, MCP depth, a repair loop, multimodal
   orchestration.
4. **The real question, reframed**: not orchestration, but **coding backend** —
   handed to D05 with its obstacle already stated.
