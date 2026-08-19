# O01 — OpenClaw, read from official sources

**Read**: 2026-08-19. **Every line below carries the URL it came from.**
Nothing here comes from this session's training data, and nothing is inherited
from `docs/architecture/agent-foundations-comparison.md` — that document is a
prior reading by this same project, not a source (O00 recorded why).

Evidence classes used throughout, as the directive requires:

- **VERIFIED FROM OFFICIAL SOURCE** — read today at the URL given.
- **UNKNOWN** — could not be verified, with the exact failure recorded.
- **INFERENCE** — a conclusion drawn by this audit, labelled as such.

---

## 0. What could not be read, and why

**`docs.openclaw.ai` is blocked by this environment's egress proxy.**

```
WebFetch https://docs.openclaw.ai/gateway/security
→ {"error_type":"EGRESS_BLOCKED","domain":"docs.openclaw.ai",
   "message":"Access to docs.openclaw.ai is blocked by the network egress proxy."}
```

Measured 2026-08-19. This is a **refusal by this environment**, not by the
project. The documentation source files are reachable through
`raw.githubusercontent.com`, which is what the rest of this audit uses, so the
block reduced convenience rather than coverage — but any claim that could only
have come from the rendered docs site reads `UNKNOWN`.

Two `404`s were also measured and are recorded so a later reader does not repeat
them: `docs/gateway/security.md` and `docs/providers.md` do not exist at those
paths; the real paths are `docs/gateway/` (a directory with a `security`
subdirectory) and `docs/providers/index.md`.

---

## 1. §4 — the distinction the directive makes mandatory

§4 forbids describing OpenClaw as GalSen IA's foundation model. The sources
settle this immediately.

| Layer | What the source says | Class |
|---|---|---|
| **Runtime** | *"A single long-lived **Gateway** owns all messaging surfaces"* and *"Maintains provider connections. Exposes a typed WS API (requests, responses, server-push events)."* — `docs/concepts/architecture.md` | VERIFIED FROM OFFICIAL SOURCE |
| **Model provider** | **60 providers named**, including Anthropic, OpenAI, Google, Moonshot AI, LiteLLM, vLLM, SGLang, Ollama, llama.cpp, LM Studio — `docs/providers/index.md` | VERIFIED FROM OFFICIAL SOURCE |
| **Tool execution** | *"Tool start/update/end events emit on the `tool` stream"*; the turn includes *"tool execution with result handling"* — `docs/concepts/agent-loop.md` | VERIFIED FROM OFFICIAL SOURCE |
| **Skills** | referenced in the turn's *"context assembly (workspace/skills/bootstrap preparation)"* — `docs/concepts/agent-loop.md` | VERIFIED FROM OFFICIAL SOURCE |
| **Gateway** | *"the local control plane for sessions, tools, events, and channel connections"* — repository README | VERIFIED FROM OFFICIAL SOURCE |
| **Memory / session** | *"The Gateway is the single source of truth for sessions, routing, and channel connections"*; *"isolated sessions per agent, workspace, or sender"* — `docs/index.md` | VERIFIED FROM OFFICIAL SOURCE |
| **Security** | see §4 below | mixed |

**OpenClaw is not a model.** It is a self-hosted gateway that runs an agent loop
and calls models belonging to other people. `INFERENCE`, drawn from the table
above: any integration would place it beside GalSen IA's agent runtime, never
beside its model providers.

---

## 2. Identity, version, licence

| | Value | Class |
|---|---|---|
| Repository | `github.com/openclaw/openclaw` | VERIFIED FROM OFFICIAL SOURCE |
| Description | *"Your own personal AI assistant. Any OS. Any Platform. The lobster way. 🦞"* | VERIFIED FROM OFFICIAL SOURCE |
| Stars | **386.8k** | VERIFIED FROM OFFICIAL SOURCE |
| `package.json` version | **`2026.8.1`** | VERIFIED FROM OFFICIAL SOURCE |
| Latest release | **`OpenClaw 2026.8.1-beta.2`**, published **2026-08-15 05:36 UTC** | VERIFIED FROM OFFICIAL SOURCE |
| Two prior releases | `openclaw 2026.7.1-2` and `openclaw 2026.7.1-1`, both 2026-08-04 | VERIFIED FROM OFFICIAL SOURCE |
| Licence, manifest | `"license": "MIT"` | VERIFIED FROM OFFICIAL SOURCE |
| Licence, **file** | `LICENSE` exists: *"MIT License / Copyright (c) 2026 OpenClaw Foundation"* | VERIFIED FROM OFFICIAL SOURCE |
| Steward | OpenClaw Foundation | VERIFIED FROM OFFICIAL SOURCE |
| Dependency list | **`UNKNOWN`** — the fetched `package.json` was truncated before its `dependencies` block | UNKNOWN |
| Implementation language | **`UNKNOWN`** — not stated on the pages read | UNKNOWN |

**The licence gate looks different here than in the last programme, and the
difference is worth naming.** Call.md declared MIT in its manifest with **no
`LICENSE` file on any branch**, so it was filed `MIT DECLARED`. OpenClaw has
**both**: the manifest field *and* the filed grant. That is `MIT` with a real
grant — subject to O05, which still has to read the **dependency** licences,
and those are `UNKNOWN` today.

**The latest release is a `beta`.** Recorded, not judged: O05 and O12 decide
what a beta means for a subordinate subsystem.

---

## 3. Architecture, as the sources describe it

**The Gateway is a single long-lived daemon.** *"One Gateway per host; it is the
only place that opens a WhatsApp session."* It validates inbound frames,
maintains provider connections and emits `agent`, `chat`, `presence`, `health`,
`heartbeat`, `cron` events. Clients send `health`, `status`, `send`, `agent`,
`system-presence` and subscribe to events. Nodes join the same WS server with
`role: node` and a device identity; **pairing is device-based**.
(`docs/concepts/architecture.md`, VERIFIED FROM OFFICIAL SOURCE)

**The execution flow is request/stream/response**: `req:agent` →
`event:agent (streaming)` → `res:agent final {runId, status, summary}`.
(same source, VERIFIED FROM OFFICIAL SOURCE)

**A turn is**: intake and session validation → context assembly (workspace,
skills, bootstrap) → model inference with prompt assembly → tool execution with
result handling → streaming of deltas → persistence, with optional reply shaping
and compaction. (`docs/concepts/agent-loop.md`, VERIFIED FROM OFFICIAL SOURCE)

**There is a hook that can block a tool call**: *"`before_tool_call`:
`{ block: true }` is terminal and stops lower-priority handlers"*, and
`security.installPolicy` carries *"operator-owned install allow/warn/block
decisions."* The same document says the core loop *"does not detail specific
human-in-the-loop mechanisms within the standard turn execution itself."*
(VERIFIED FROM OFFICIAL SOURCE)

**Channels are the surface**: WhatsApp, Telegram, Slack, Discord, Signal,
iMessage, WebChat in the core; Matrix, Nostr, Twitch, Zalo and more as channel
plugins, *"official plugins install on demand."* (`docs/index.md`, VERIFIED FROM
OFFICIAL SOURCE)

---

## 4. Sandboxing — read in full, because §8 turns on it

`docs/gateway/sandboxing.md`, all VERIFIED FROM OFFICIAL SOURCE:

- **Sandboxing is off by default**: *"Sandboxing is off by default and
  controlled by `agents.defaults.sandbox`."*
- **The document states its own limit**: *"This is not a perfect security
  boundary, but it materially limits filesystem and process access when the
  model does something dumb."*
- **What is sandboxed**: tool execution — `exec`, `read`, `write`, `edit`,
  `apply_patch`, `process` — and an optional sandboxed browser.
- **What is not**: the Gateway process itself, and *"tools explicitly allowed
  via `tools.elevated`"*, which run on the host or a configured escape path.
- **Backends**: Docker/Podman, SSH, and OpenShell (managed remote sandboxes).
- **Filesystem**: three workspace levels — `none`, `ro` (read-only at `/agent`),
  `rw` (read-write at `/workspace`). Extra folders via bind mounts, and
  *"Binds bypass the sandbox filesystem: they expose host paths with whatever
  mode you set."* Dangerous bind sources are blocked by default: system paths,
  Docker socket directories, common home-directory credential roots.
- **Network**: Docker default is *"network: 'none' (no egress)"*;
  `network: "host"` and `container:<id>` namespace joins are blocked by default.
- **A named gap**: *"The default-off secret egress proxy is Gateway-loopback
  only… Sandbox/container proxy reachability is not implemented."*
- **A host-posture warning**: `kernel.apparmor_restrict_unprivileged_userns=0`
  is *"a host-wide fallback with security tradeoffs; use it only when that host
  posture is acceptable."*

**This is the most important paragraph of O01**, and it agrees with what this
repository already believed for its own reasons: `src/sandbox/policy.py` opens
with *"a sandbox is a claim until someone has tried to escape it."* OpenClaw's
own documentation says the same thing about itself, in its own words.

---

## 5. Multi-tenancy — §9's question, answered by the source

`docs/gateway/multi-tenant-hosting.md`, all VERIFIED FROM OFFICIAL SOURCE:

**What exists**: per-tenant *cells*. Each tenant gets *"a full Gateway in a
hardened container with its own state, credentials, workspace, channel accounts,
token, and loopback-only host port"*, with dropped Linux capabilities,
`no-new-privileges`, PID/memory/CPU limits, separate persistent mounts,
per-cell networks and loopback-only publishing.

**What does not exist, in the document's own words**:

- *"Session IDs select routing; they do not authorize one tenant against
  another."* — **there is no application-level authorization between tenants.**
- *"Fleet does not provide these surfaces"* — no shared channel accounts, no
  ingress routing.
- *"The Fleet operator and the host are trusted by every tenant. Resistance to a
  compromised host is a non-goal."*
- *"Do not co-locate hostile tenants in one OpenClaw process or OS user."*

**Status**: *"Fleet remains experimental: its commands, flags, and container
profile can change between releases without a deprecation window."*

`INFERENCE`, and O04 will have to test it rather than assume it: multi-tenant
isolation in OpenClaw is **per-container, not per-request**. GalSen IA's model
is the opposite — one process, many subjects, authorisation checked per call
(`src/api/rbac.py`, `src/tool/authorization.py`). Those two shapes do not
compose by default, and §9 exists precisely because assuming they do is the
failure mode.

---

## 6. Model providers — §10's question

**60 providers named** in `docs/providers/index.md` (VERIFIED FROM OFFICIAL
SOURCE). Against §10's explicit list:

| §10 asks about | Present in the list |
|---|---|
| Claude | **yes** — Anthropic |
| Kimi | **yes** — Moonshot AI |
| LiteLLM | **yes** |
| vLLM | **yes** — *"vLLM (local models)"* |
| SGLang | **yes** — *"SGLang (local models)"* |
| Local models | **yes** — llama.cpp, LM Studio, Ollama, inferrs, plus the two above |

**Whether OpenClaw routes between models itself**: `UNKNOWN`. The document has
users *"set the default model"* as `provider/model` and lists *"ClawRouter
(managed multi-provider routing)"* as one provider among sixty, but does not
state whether the gateway routes. Failover is mentioned once, scoped to image
generation: *"Shared `image_generate` tool, provider selection, and failover."*

This matters because §10 says GalSen IA's `ModelRouter` remains authoritative.
Whether that is a conflict or a non-issue cannot be settled from what was read
today, and O06 will have to settle it.

---

## 7. What O01 deliberately did not do

- **Nothing was installed.** §20 forbids it during the audit.
- **No dependency tree was resolved**, so dependency licences are `UNKNOWN` and
  O05 owns them. The last four programmes each found that a repository licence
  says nothing about its dependencies.
- **No security claim was tested.** Everything in §4 above is what the project
  says about itself. `src/sandbox/policy.py` already states the standard this
  repository holds: a sandbox is a claim until someone has tried to escape it —
  and that applies to OpenClaw's claims exactly as it applies to ours.
- **No benchmark was run**, so §17 stays `UNKNOWN` until O10.

---

## 8. What O01 establishes for the volets that follow

1. **It is a gateway with an agent loop, not a model** — §4 satisfied, and the
   adapter's place in the architecture is fixed by it.
2. **MIT with a filed `LICENSE`**, unlike the previous programme's subject —
   but dependency licences are `UNKNOWN`, and O05 is still a gate.
3. **Sandboxing is off by default and the project says it is not a perfect
   boundary** — O03 inherits a specific, quotable starting point rather than an
   impression.
4. **Multi-tenant isolation is per-container, experimental, and explicitly does
   not authorise one tenant against another** — O04's hardest question already
   has the source's own answer, and it is not a comfortable one.
5. **The provider list covers every model family §10 names** — so provider
   compatibility is unlikely to be the blocker; whether OpenClaw insists on
   routing is the open question.
