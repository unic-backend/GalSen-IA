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

## What D00 leaves for D00.3

Items **8, 9, 10, 18, 19, 20, 21, 22, 24, 25** — session/state management,
sandbox and execution model, permissions, security boundaries, persistence,
observability, failure handling, recovery, third-party dependencies, and
compatibility-breaking changes.

The documents that hold them exist and are named:
`docs/persistence-catalog.md`, `docs/tool-execution-pipeline.md`,
`docs/agent-lifecycle.md`, `docs/api-gateway.md`, `docs/defensive-patterns.md`,
`docs/capability-seams.md`, `docs/subsystems/`, `docs/postmortem/`, and
`THIRD_PARTY_NOTICES.md`.

**`docs/postmortem/` is worth noting before it is read**: a project that
publishes postmortems is a project that says what went wrong, and that is the
kind of source an audit can use.
