# D00 — Official source audit (Phase 1)

**Read**: 2026-08-20, from `github.com/deepseek-ai/deepseek-harness` and its
`docs/` sources. Every claim carries the URL it came from.

Phase 1 forbids memory, previous conversations, unofficial articles and
*"benchmark claims without primary sources"*. Nothing below comes from this
session's training data.

Evidence classes: **VERIFIED FROM OFFICIAL SOURCE** · **UNKNOWN** (with the
failure recorded) · **INFERENCE** (labelled).

---

## 0. What could not be read

**`deepseek.com` is blocked by this environment's egress proxy.**

```
WebFetch https://deepseek.com/harness
→ {"error_type":"EGRESS_BLOCKED","domain":"deepseek.com",
   "message":"Access to deepseek.com is blocked by the network egress proxy."}
```

A refusal by **this environment**, not by DeepSeek. The directive names that URL
as official documentation, so its content is `UNKNOWN` unless mirrored in the
repository.

**The workaround exists, and it needed a correction.** The first raw fetch 404'd
because **the default branch is `master`, not `main`** — recorded so a later
reader does not repeat it. With `master`, `raw.githubusercontent.com` serves the
repository's `docs/` tree, which is substantial: **19 documents × 3 languages**
(English, Chinese, and an `.i18n.yaml` per document), plus `cookbook/`,
`cordis-api/`, `cordis-tutorial/`, `postmortem/`, `subsystems/` and `user/`.

---

# D00.1 — Identity, licence, releases, requirements

## Phase 1's items 1, 2, 14–17, 23

| # | Item | Value | Class |
|---|---|---|---|
| 1 | Exact repository | `github.com/deepseek-ai/deepseek-harness`, default branch **`master`** | VERIFIED |
| 2 | Version | `package.json` → **`0.1.0-rc.8`**, name `@deepseek-ai/dsh-root`, `private: true` | VERIFIED |
| 2 | Latest release | **`v0.1.0-rc.8`**, published **2026-08-19 15:37** — *one day before this audit* | VERIFIED |
| 2 | Previous release | `v0.1.0-rc.7`, 2026-08-17 12:01 | VERIFIED |
| 14 | Runtime requirements | `engines`: **`node: ^22.19.0 \|\| >=24.0.0`**; `packageManager: pnpm@11.7.0` | VERIFIED |
| 15 | Node / Python / system | Node as above. A **`python/` directory and a `pytest.ini` exist** at repository root — so it is not TypeScript-only. Python version requirement: **`UNKNOWN`** | VERIFIED / UNKNOWN |
| 16 | GPU requirements | **not stated** in the README | UNKNOWN |
| 17 | Network requirements | **not stated** in the README | UNKNOWN |
| 23 | Licence | **MIT**, and the grant is **filed**: *"MIT License / Copyright (c) 2026 DeepSeek"* | VERIFIED |
| — | Stars | 170.4k | VERIFIED |
| — | Install | `npx @deepseek-ai/dsh web`, or clone + `pnpm install && pnpm run build && pnpm dsh web` | VERIFIED |

## The maturity fact that outranks the star count

**The project is at `0.1.0-rc.8`.** A release candidate for a **0.1.0** — not a
1.0, not a 2026.x calendar version. The most recent release landed **the day
before this audit ran**, and `rc.7` two days before that.

`INFERENCE`, and it is the one to carry into Phase 7: **170.4k stars on a
`0.1.0-rc` project measures attention, not stability.** The directive's own rule
— *never claim "production ready" without evidence* — cuts both ways here, and
the version string is evidence about the project's own self-assessment. A
subsystem whose API is pre-1.0 and shipping release candidates two days apart is
a subsystem whose interface can move under an adapter.

The previous audit found the same shape stated differently: OpenClaw's Fleet was
*"experimental… can change between releases without a deprecation window."* Here
the whole product carries the pre-1.0 marker.

## Licence, and the file that matters for Phase 6

MIT is declared **and** filed — like OpenClaw, unlike Call.md two programmes
ago, which declared MIT in its manifest with no `LICENSE` file anywhere.

**And there is something neither previous subject had**:
**`THIRD_PARTY_NOTICES.md` exists at repository root** (VERIFIED, seen in the
top-level listing). That is the artefact Phase 6 asks for — *"Audit all relevant
third-party dependencies"* — published by the project itself. D08 reads it.

For both previous programmes the dependency licences ended `UNKNOWN` because
`package.json`'s dependency block could not be fetched whole. **This repository
may not have that problem**, and that is worth saying now: it is the first
subject in four programmes that ships its own third-party notice file.

---

# D00.2 — Architecture, plugins, agent loop, tools, MCP

## Phase 1's items 3–7, 11–13

**Everything is a plugin, and the documentation means it literally.**

> *"Every part of the product is a plugin, including the model adapter, the tool
> registry, the session log, and **the agent loop itself**."*

> *"There is no privileged core to patch: you extend dsh by mounting a plugin
> beside the others."*

Both VERIFIED FROM OFFICIAL SOURCE, `docs/architecture.md`.

| # | Item | What the source says |
|---|---|---|
| 3 | Architecture | *"A running `dsh` is a plugin tree composed at boot from ordered layers"* — bundles in profile order, then the profile patch, then the home patch, then a command-line overlay |
| 4 | Plugin system | plugins declare themselves via a **`dsh` field in `package.json`**; bundles reference patch files through `dsh.bundle`; profiles list bundles via `dsh.profile` |
| — | Three foundational bundles | `dsh-base` — *"model adapters, tools, persistence, sandbox and approval policy, settings, credentials, telemetry"*; `dsh-web-app` — the browser interface; `dsh-headless` — *"a one-shot runner without a server"* |
| — | Cordis | *"Cordis is the framework under dsh: plugins contribute services, typed events, and reversible effects to a shared context"* |
| 7 | Agent loop | lives in `core/agent-loop`, owns `ctx.agentLoop`, and is **replaceable** — *"patchable infrastructure, not privileged"* |
| 6 | Tool system | pipeline: `tool/call* → tools/pre-execute → tools/execute → tools/post-execute → tool/result*`, as **durable session events**, with pre- and post-execute as extension points |
| 5 | Model integration | a **model adapter plugin**; which providers, **`UNKNOWN`** — the README does not say and `docs/` was not exhausted in this phase |
| 11 | MCP support | **not stated in the README**; the release notes for `rc.7` mention *"durable image attachments for MCP/ACP"*, so **MCP exists** — depth `UNKNOWN` |
| 12 | Extensibility | maximal by design: no privileged core |
| 13 | APIs | `docs/api-gateway.md` exists and was **not read** in this phase → D00.3 |

## The isolation mechanism, and the phrase to keep

> *"Give one session a different capability set"* by composing an agent preset
> with an **`isolate` realm** for service rows.

VERIFIED FROM OFFICIAL SOURCE. `INFERENCE`: that is a per-session capability
scope — the same **shape** as OpenClaw's four permission modes, and the same
mismatch with GalSen IA's per-call `authorize()`. D07 must test whether `isolate`
goes further than a mode, because "different capability set per session" is
closer to what an adapter needs than a fixed four-rung ladder was.

## `dsh-headless` is the finding of this phase

*"a one-shot runner without a server"* — VERIFIED FROM OFFICIAL SOURCE.

**This is materially different from the previous subject.** OpenClaw was a
long-lived gateway that owned sessions, and every design constraint in that audit
flowed from a daemon holding state and credentials: per-task sessions had to be
imposed, automatic re-dispatch had to be defeated, a container boundary had to
wrap a permanent process.

A **one-shot runner** has none of those properties by construction. It starts,
does one thing, exits.

`INFERENCE`, and it is why this audit must not inherit the previous verdict:
**the shape that made OpenClaw un-adoptable may simply not be present here.**
Whether `dsh-headless` is really that — no daemon, no surviving state, no
credential store of its own — is exactly what D00.3 and D07 have to establish,
and it is now the audit's central question rather than a detail.

---

---

# D00.3 — Sandbox, permissions, persistence, credentials

`docs/subsystems/` holds **at least 33 subsystem documents × 3 languages** — the
listing truncated at 100 entries. Four were read for this phase, chosen because
they carry Phase 1's items 8, 9, 10, 18 and 19.

## Item 9 — the sandbox, and it is a real one

`docs/subsystems/sandbox.md`, VERIFIED FROM OFFICIAL SOURCE.

**Three OS-level mechanisms, not a container option:**

| Platform | Mechanism |
|---|---|
| Linux | **`bwrap` / Landlock** |
| macOS | **Seatbelt** |
| Windows | **ACL restricted-token backend** |

Described as *"sibling implementations"* rather than one unified approach.

**Three modes**: `read-only` — *"permits only required sinks such as
`/dev/null`"*; `workspace-write` — *"permits writes under the workspace root and
the backend's promised temp area"*; `danger-full-access` — which *"bypasses
confinement"*.

**And the sentence that matters most in this phase:**

> *"Silent unconfined passthrough is never legal for a confined policy."*

That is this repository's own rule, in someone else's words: a capability that
cannot be delivered reports its state rather than degrading quietly. The
Windows runner *"reports partial enforcement for its ambient ACL gaps"*, and
older Landlock ABIs likewise report partial enforcement — **they say so rather
than pretending**.

**The named limit**: *"Network and process visibility are outside this
vocabulary."* The sandbox governs **file effects only**.

`INFERENCE`, and it is a reversal of the previous audit's finding: **OpenClaw's
sandbox was off by default and its own document called it "not a perfect security
boundary". This one is kernel-level, per-platform, and declares what it does not
cover.** The two are not comparable, and this audit must not carry the previous
verdict across.

**`UNKNOWN`**: whether the sandbox is on by default. `sandbox.md` does not say,
and `permission-presets.md` says the deployment default is *"not stated"*.

## Item 10 — permissions

`docs/subsystems/permission-presets.md`, VERIFIED FROM OFFICIAL SOURCE.

**Two presets**, each pairing a sandbox mode with an approval policy:

| Preset | Sandbox mode | Approval policy |
|---|---|---|
| `workspace-write` | `workspace-write` | **`ask`** |
| `danger-full-access` | `danger-full-access` | **`never`** |

**Scope**: per **session** — `set(session, name)` writes to a specific session,
and *"the selection event precedes the knob events in the same turn"*, so a
change takes effect immediately within a session.

**Who may change a preset**: **not stated**. `UNKNOWN`, and it is a security
question rather than a documentation gap — D07 owns it.

`INFERENCE`: this is again **per-session** capability scoping, the same
granularity mismatch the OpenClaw audit found against GalSen IA's per-call
`authorize()`. The mismatch is structural to agent harnesses, not specific to
one project. What differs here is that the sandbox mode and the approval policy
are **paired in the preset**, so `danger-full-access` and `never` arrive
together — a coupling that is at least legible.

## Items 8 and 19 — session state and persistence

`docs/subsystems/persistence.md`, VERIFIED FROM OFFICIAL SOURCE.

**Two backends.** JSONL: *"an append-only logical JSONL log per session, stored
as checksummed concatenated Zstandard frames by default or raw lines by
configuration"*, returning *"the absolute transcript path inside its
project/session directory"*. SQLite: *"schema 17"*, with bounded `text-chunks`,
`reasoning-chunks` and `tool-call-chunks` rows, returning `undefined` for a path
because *"sessions share one database"*.

**State survives process exit**, and crash recovery is explicit: *"A backend
that reloads a log crashed mid-turn finds an open `turn/start` with no
`turn/end`"* and closes orphaned turns with synthetic boundaries. Sessions
resume via `ctx.agents.resume({ resumeSessionId })`.

**The question this phase was opened to answer**: does `dsh-headless` — *"a
one-shot runner without a server"* — persist anything?

**`UNKNOWN`.** `persistence.md` *"does not distinguish persistence behavior
between one-shot runs and server deployments"*, read verbatim. So the audit's
central question from D00.2 is **not yet answered**, and this phase records that
rather than resolving it by assumption.

`INFERENCE` worth carrying: an append-only session log with **resume by session
id** is the same capability that made OpenClaw's automatic re-dispatch a
problem — an execution decision taken outside our gate. The difference, if there
is one, is whether `dsh-headless` **opts out**. D07 must establish it.

**Retention and deletion**: **not stated**. `UNKNOWN`.

## Item 18 — credentials

`docs/subsystems/credentials.md`, VERIFIED FROM OFFICIAL SOURCE.

**Storage location, form and encryption: all *"not stated"***. Layer identifiers
exist — `env`, `file`, `project-env`, `user-env` — for the local provider.

**Two rules are stated, and both are good ones**: *"an empty stored value is
absent everywhere"* — a blank is unconfigured, not empty-but-set — and
credentials are resolved *"once per operation"* with consumers that *"must not
cache across operations."*

**Whether credentials reach plugins or tools: not stated.** `UNKNOWN`, and given
*everything is a plugin*, it is the sharpest open question of this phase. D07
owns it.

---

## Phase 1's twenty-five items, tallied

| Verified | `UNKNOWN` | Deferred to a later volet |
|---|---|---|
| 1, 2, 3, 4, 5 (partial), 6, 7, 9, 10, 12, 14, 15 (partial), 19, 23 | 5 (providers), 11 (MCP depth), 13, 15 (Python version), 16, 17, 18 (storage), 20, 21, 22, 24, 25 | 13 → D07 · 20, 21, 22 → D07 · 24 → D08 · 25 → D08 |

**Fourteen verified, eleven `UNKNOWN`**, and the `UNKNOWN`s are named with the
document that would close each. Four of them — observability, failure handling,
recovery, and whether credentials reach plugins — are **security questions**, and
they are handed to D07 rather than answered from a document that does not say.

## The two things D00 establishes for the rest of the audit

1. **This sandbox is not OpenClaw's sandbox.** Kernel-level per platform, three
   declared modes, partial enforcement reported rather than hidden, and a
   published limit — file effects only. The previous programme's blocker was
   *"cannot be sandboxed"*; here that question has to be asked again from
   scratch.

2. **The central question is still open.** `dsh-headless` is documented as a
   one-shot runner; `persistence.md` does not say what a one-shot run persists.
   Everything downstream — whether an adapter needs to impose per-task sessions,
   whether resume can be defeated, whether a credential store exists — turns on
   it, and it is `UNKNOWN` today.

## What remains for later volets

`docs/api-gateway.md`, `docs/agent-lifecycle.md`, `docs/defensive-patterns.md`,
`docs/capability-seams.md`, `docs/subsystems/approval.md`,
`docs/subsystems/shell.md`, `docs/subsystems/skills.md`,
`docs/subsystems/extensions.md`, `docs/subsystems/code-runtime.md`,
`docs/postmortem/`, `BENCHMARK.md`, and `THIRD_PARTY_NOTICES.md`.

**`docs/postmortem/` and `BENCHMARK.md` are worth noting before they are read**:
a project that publishes its postmortems says what went wrong, and a project
that publishes a benchmark file has made claims an audit can check against
Phase 3's rule — *never claim "best coding model" without comparative
evidence*.
