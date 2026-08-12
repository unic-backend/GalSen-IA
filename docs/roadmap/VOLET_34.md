# VOLET 34 — Personal Computer Agent

Source: brief received 2026-08-12, *"lead AI architect and autonomous systems
engineer… build a next-generation personal AI agent"*.

This file is the VOLET the phase plan counts from. It records **what the brief
asks**, **what the repository already does**, and **what has to be decided
before any code is written**.

---

## 1. What the brief asks

An agent that operates a real computer like a human assistant: sees the screen,
drives GUI applications, navigates local storage across drives, organises files,
understands and improves codebases, runs commands, manages workflows, and
proposes improvements on its own. Plus a comparative study of the strongest
open-source foundations, a security model, hardware requirements, and upgrade
paths.

## 2. What already exists — measured, not remembered

A large part of this brief is built. Rebuilding it would be the waste the
project's own rules forbid.

| Brief asks | State in this repository |
|---|---|
| Central brain, model switching | `src/model_engine/` — provider registry, selection, ranking (ADR-003) |
| Memory system | `src/memory_engine/` + SQLite (ADR-005) + semantic retrieval (ADR-015) |
| Planning | `PlannerAgent`, `ExecutionPlanner`, decision trace |
| Multi-agent | 10 agents, shared `AgentContext`, bounded delegation (VOLET 29) |
| Tool usage | **19 tools enabled**: filesystem, terminal, git, github, database, browser, memory, rag, embeddings, ocr, pdf, web_search… |
| File management | `src/services/file/` — four backends, ownership per subject (ADR-016) |
| Code writing under control | `src/agent/guarded_editor.py` — every write goes through the approval gate (VOLET 31) |
| Approval checkpoints | ADR-006, persistent since 2026-08-12 |
| Activity log | `src/audit_engine/` — persistent, filterable, `/trace/{request_id}` |
| Permission system | RBAC per key, subject ownership (ADR-010) |
| Learning from use | `src/training/` — consented capture, scrubbing, DPO pairs, lineage (VOLET 33) |

**Filesystem and terminal are already the "controlled action" layer**, and they
are deliberately narrow: the filesystem tool is confined to one root (writing off
by default, no `..`, no symlink escape), and the terminal runs **no shell**, only
allow-listed executables, with a timeout.

## 3. What is genuinely missing

1. **Sight.** Nothing captures or interprets a screen. The vision engine reads
   image files; it does not see a desktop.
2. **GUI control.** No pointer, no keyboard, no window awareness.
3. **A real browser.** `BrowserTool` is `urllib` plus regular expressions — no
   JavaScript, no clicking. Any modern page is out of reach.
4. **An execution sandbox.** `DockerTool` is **disabled on purpose**: from inside
   the production container it would require the host Docker socket, which is
   root on the host. An agent that writes code needs somewhere to run it that is
   not the host.
5. **MCP.** No client, no server. The brief's "MCP-based architectures" has no
   counterpart here.
6. **Whole-repository understanding.** The coder agent edits files; nothing
   builds a map of a large codebase.
7. **Working-style learning and proactive discovery.** Feedback is captured;
   nothing yet turns it into preferences or unprompted suggestions.

## 4. Two facts that decide the shape of this VOLET

### 4.1 The model layer still answers 503 — criterion C1 is open

`tests/test_generation_end_to_end.py` skips because no provider answers. An
autonomous computer agent on a platform whose brain is unreachable is a plan
without an engine. **This depends on the operator**, not on code: `ollama serve`
with a context window of at least 8192.

Consequence for the plan: every phase below is written so it is verifiable
**without** a model answering, or it is explicitly marked as blocked by C1.

### 4.2 The brief contradicts ADR-014, and an ADR is changed before code

The brief asks for the *"ability to switch between cloud and local models"*.
ADR-014 (model sovereignty) refuses third-party providers by default —
`GALSEN_SOVEREIGN_MODE` is `true`, and OpenAI, Anthropic, Google and the
compatible-URL-pointing-at-a-third-party-host case are all refused at
registration.

The project's hard rule is *"NEVER invent architecture that contradicts existing
ADRs"*. So this is **not** mine to decide. Three options exist and the choice
belongs to the owner:

- **A. Keep sovereignty.** Cloud models stay refused. The agent runs on SamP/ToP
  and any self-hosted OpenAI-compatible endpoint. Slower to reach quality, and
  it is the position the project was founded on.
- **B. Amend ADR-014 with a declared escape hatch.** Sovereign by default; a
  named, logged, per-task opt-out for cloud models, refused for anything
  touching user data. Keeps the principle, admits a measured exception.
- **C. Drop sovereignty.** Cloud and local are peers.

Nothing in chapters 05 onward depends on which is chosen — but chapter 04 does,
and the honest place to ask is before the code, not after.

---

## 5. Chapters

| # | Chapter | Phases |
|---|---|---|
| 01 | Assessment: this repository against the brief, capability by capability | 1 |
| 02 | Comparative study of open-source foundations, **web-sourced** | 2 |
| 03 | ADR-017 — the architecture decision that follows from 01 and 02 | 1 |
| 04 | ADR-014 revisited — sovereignty vs cloud switching (**needs your decision**) | 1 (indivisible) |
| 05 | Sight: screen capture as a tool, with its refusals | 2 |
| 06 | GUI control: pointer and keyboard, under the approval gate | 2 |
| 07 | Real local storage: multiple drives, declared roots, reversible operations | 2 |
| 08 | Execution sandbox: where agent-written code may run | 2 |
| 09 | MCP: client first, then server | 2 |
| 10 | Whole-repository understanding: the map a coding agent needs | 2 |
| 11 | The missing agents: file organiser, project manager, opportunity analyst | 2 |
| 12 | Working style and continuous improvement | 2 |
| 13 | Security model: permissions, backups, checkpoints, activity | 2 |
| 14 | Hardware, software stack, upgrade paths | 1 |

**Total: 14 chapters → 24 phases.**

---

## 6. What this VOLET refuses to do

- **No comparison written from memory.** Chapter 02 is web-sourced with links.
  A table of scores invented from training data would be the exact failure mode
  `.claude/rules/verification.md` names: a plausible answer where a status was
  due.
- **No unattended GUI control.** Chapters 05–07 land behind the approval gate
  from the first line. An agent that can click and delete needs the gate before
  it needs the capability, not after.
- **No agent that runs code on the host.** Chapter 08 comes before chapter 10
  for that reason.
