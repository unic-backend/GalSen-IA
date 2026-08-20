# L01 — Call.md, audited from source

Live Context Engine directive, **§2 and §3**. Read on 2026-08-19 from
`raw.githubusercontent.com`. **Nothing was cloned, installed or executed.**

§2 says not to assume the repository matches the directive's description, and to
verify the current state at execution time. That is what follows — and two of
the directive's assumptions do not survive it.

**Evidence level is marked on every claim**: `SOURCE` when read from a `.ts` or
`.json` file, `README` when read from the project's own description. A README is
a declaration, not an implementation.

---

## The two findings that decide this programme

### 1. Call.md does not record on Linux

`README` — the platform table, in the project's own words:

| Platform | Status |
|---|---|
| macOS 12+ | Supported |
| Windows x64 | build from source; recording supported, no published installer |
| **Windows ARM64** | **recording not supported** |
| **Linux** | **recording not supported** — *"the app will reject recording before launch because no capture binary is available"* |

The VideoDB capture SDK ships binaries for `darwin-arm64`, `darwin-x64` and
`win32-x64` only.

**GalSen IA runs on Linux.** So Call.md's central capability — capture — does
not exist on this platform, independently of the fact that this particular
container has no microphone. Two separate reasons, both measured, pointing the
same way.

### 2. VideoDB is not an optional provider inside Call.md — it is the spine

Four statements, all `README`, all from the project itself:

- *"Dual-Channel Transcription … **powered by VideoDB**"*;
- *"Captures dual-channel audio … and **sends to VideoDB** for real-time
  transcription via WebSocket"*;
- *"**VideoDB Integration** — Transcription and AI features **require internet
  connectivity**"*;
- **OpenAI SDK 6.19.0** is used *"for LLM calls via **VideoDB's
  OpenAI-compatible API**"*.

And `SOURCE`: `videodb` is a runtime dependency in `package.json`, alongside
`openai`.

**So §26's "evaluate whether VideoDB is optional" has an answer for Call.md
itself: it is not.** Capture, transcription and inference all route through one
hosted commercial service.

**L00 already established what that means here.** ADR-014 says the platform
depends on no external model at runtime; ADR-018 refuses screen captures
unconditionally and refuses any request carrying user content. Live audio is a
user's voice. **The conflict is recorded, not resolved** — amending an ADR is
the owner's decision.

Note the vocabulary carefully: Call.md's *"Local-First"* means **settings,
history, transcripts and metadata are stored locally**. It does **not** mean the
audio is processed locally. Local storage and local processing are two claims,
and only the first is made.

---

## §2 — the inspection list

| Asked for | Found | Evidence |
|---|---|---|
| Version | **`call-md` 1.0.4** | `SOURCE` (`package.json`) |
| **Licence** | **`"license": "MIT"` declared; NO `LICENSE` file** — 404 on five filenames × two branches | `SOURCE` |
| Language / stack | Electron 42, TypeScript 5.8, React 19, Tailwind + shadcn/ui, tRPC 11, Hono, Drizzle + SQLite, Zustand, Vite. **No Python** | `SOURCE` + `README` |
| Dependencies | **27 runtime, 27 dev** | `SOURCE` |
| Architecture | Electron three-process: `main/`, `preload/`, `renderer/`, plus `shared/` | `README` |
| **Copilot services** | 6 — `context-manager`, `conversation-metrics`, `nudge-engine`, `sales-copilot` (*core orchestrator*), `summary-generator`, `transcript-buffer` | `README`, and three confirmed reachable at `SOURCE` |
| **MCP services** | 5 — `connection-orchestrator`, `intent-detector`, `mcp-agent`, `tool-aggregator`, `result-handler` | `README` |
| Other services | `live-assist`, `mcp-inference`, `llm`, `videodb` | `README` |
| Database | Drizzle + SQLite, local file `call-md.db` | `README` |
| IPC | preload bridge — `window.electronAPI.mcp.*`, `mcpOn.*` | `README` |
| API | Hono + tRPC, **bound to `127.0.0.1` only**, token required on every procedure except registration | `README` |
| Permissions | microphone + screen recording, granted at OS level before recording | `README` |
| Configuration | `~/Library/Application Support/call-md/` — `config.json`, `data/call-md.db`, `google_tokens.enc`, `logs/` | `README` |
| **Current commit** | **`UNKNOWN`** — the GitHub tree API answers `403` from this session | measured |
| Limitations | 2-hour recording cap; no Linux/ARM recording; internet required for transcription and AI | `README` |

---

## §3 — the capability list, verified one by one

`SUPPORTED` means the project states it and nothing contradicts it;
`SUPPORTED (SOURCE)` means it was read in code; `PLATFORM-LIMITED` means it
exists but not on Linux.

| Capability | Verdict |
|---|---|
| Real-time meeting recording | **PLATFORM-LIMITED** — not on Linux |
| Microphone capture | **PLATFORM-LIMITED** |
| System audio capture | **PLATFORM-LIMITED** |
| Screen capture | **PLATFORM-LIMITED** |
| Dual-channel transcription (you vs them) | SUPPORTED — via VideoDB |
| Live transcription | SUPPORTED — WebSocket to VideoDB |
| Transcription language selection | SUPPORTED — Settings, or Automatic |
| Conversation context | SUPPORTED — `context-manager.service.ts` |
| Live AI assistance | SUPPORTED — `live-assist.service.ts` |
| **Conversation metrics** | **SUPPORTED (SOURCE)** — `conversation-metrics.service.ts`, 11 710 bytes |
| Talk ratio, speaking pace (WPM) | SUPPORTED |
| Question detection | **SUPPORTED (SOURCE)** — `checkQuestions()` |
| Monologue detection | SUPPORTED |
| **Coaching nudges** | **SUPPORTED (SOURCE)** — see below |
| MCP integration | SUPPORTED — 5 services |
| Automatic tool triggering | SUPPORTED — `intent-detector` + `mcp-agent` |
| MCP result presentation | SUPPORTED — results panel |
| Bookmarks | SUPPORTED |
| Meeting preparation, checklists | SUPPORTED — AI-generated wizard |
| Summaries | SUPPORTED — three parallel extractions |
| Key points, action items | SUPPORTED |
| Transcript export | SUPPORTED — markdown |
| Workflow webhooks | SUPPORTED — n8n, Zapier, CRMs |
| Meeting history | SUPPORTED |
| Local storage | SUPPORTED — SQLite; **storage only, not processing** |
| Google Calendar | SUPPORTED — OAuth, tokens via Electron `safeStorage` |

### The nudge engine, read rather than believed

`SOURCE`, `nudge-engine.service.ts` (6 897 bytes):

- **`DEFAULT_COOLDOWN = 120000`** — a two-minute floor between nudges;
- five nudge types, three severities (`low` / `medium` / `high`);
- four checks: `checkTalkRatio`, `checkQuestions`, `checkPace`, `checkNextSteps`;
- `lastNudgeTime` and a `nudgeHistory` kept in the service.

**This is `src/proactive/` with a timer instead of an evidence fingerprint.**
L00 already recorded that GalSen IA's proactive layer suppresses repetition by
hashing the *evidence*, so a suggestion returns only when the situation actually
changed — which is strictly more precise than a cooldown. §41 forbids building
the second one, and the comparison says which is worth keeping.

---

## §29 and §16 — what Call.md does better than this repository, on one axis

`README`, its webhook section:

> *"Delivery is **pinned to the addresses approved by that DNS lookup**,
> preventing **DNS rebinding** between validation and connection."*

`src/research/safety.py` (R06) blocks internal ranges as literals *and* as
resolved names, and its own `not_guaranteed` section states plainly that **it
does not close the re-resolution window**, because closing it means connecting
to the address already checked — which belongs to the HTTP client.

**Call.md closes it. This repository does not.** That is a real, citable idea,
and it belongs to the research layer rather than to this programme.

**OPTIONAL SUGGESTION — NOT IMPLEMENTED**: pin outbound connections to the
addresses `check_url` approved. It generates no task here, and it would be
scope expansion under `.claude/rules/spec-driven-governance.md`.

Its other security controls, recorded because they raise the bar for §28 and
§29: tRPC bound to loopback; app directory `0700`, files `0600`; MCP server
environment variables and headers under AES-256-GCM with a keychain-wrapped key;
**credential writes fail closed** when Linux offers only the insecure
`basic_text` backend; `contextIsolation` on, Node integration off, Chromium
sandbox enabled; credential-shaped fields redacted from logs.

---

## §38 — the licence question, stated precisely

`package.json` declares `"license": "MIT"`. **No `LICENSE` file exists** on
`main` or `master`, under `LICENSE`, `LICENSE.md`, `LICENSE.txt`, `COPYING` or
`license`.

This is the **mirror image** of `abdrsan/Higgsfield-Open` in the canvas
programme, whose `LICENSE` said MIT and whose manifest said `null`. There, the
file governed. Here there is no file — only a declaration in metadata.

**A manifest field is weaker evidence than a licence file**, and the honest
record is: *MIT, `DECLARED`, not `AUTHORITATIVE`*. L03 weighs what that permits;
it is not this phase's decision.

**And the licence of the repository is not the licence of the capability.** The
capability requires **VideoDB**, a commercial hosted service with terms nobody
here has read — the same shape as MoneyPrinterTurbo's MIT repository with an
LGPL TTS path, and as `higgsfield-ai/skills`' MIT Markdown driving a paid API.

---

## What L01 concludes

1. **Nothing is importable.** TypeScript and Electron against a Python platform,
   for the fifth candidate repository in four programmes.
2. **Its capture capability does not exist on Linux**, by its own statement.
3. **Its intelligence is inseparable from VideoDB**, which L00 established runs
   into two accepted ADRs.
4. **Its ideas are worth taking**: dual-channel separation (you vs them) as a
   first-class concept, the transcript buffer, the split between live metrics
   and post-session extraction, and MCP intent detection separated from tool
   execution.
5. **One of its implementations beats ours** on DNS rebinding, and that is
   recorded as an optional suggestion rather than quietly implemented.

L02 audits what GalSen IA already has against this list; L03 is the licence and
dependency gate.
