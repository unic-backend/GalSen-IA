# D10 — Architecture decision (Phase 8)

**Decided**: 2026-08-20. Decision recorded as **ADR-035**.

Phase 8: *"Choose exactly one."* This document says which, and why the other
four were not chosen — because a decision that only argues for its own option
has not been made, it has been announced.

---

## The choice

# **OPTION C — integrate as a specialized coding-agent backend.**

**And implementation is not authorized by this decision.** The directive's
header says *"DO NOT INTEGRATE IT YET"*; its closing rule says
*AUDIT → MEASURE → DECIDE → THEN IMPLEMENT ONLY IF JUSTIFIED*. This is the
**decide** step.

---

## Why not the other four

**Option A — do not integrate.** Rejected because **no gate fails outright**
(D09). Three of Phase 7's eleven are `UNKNOWN`, and **one permitted installation
closes all three**. Choosing A would convert *"we have not measured this"* into
*"this does not work"*, which is the substitution this whole audit method exists
to prevent. It would also repeat ADR-034's verdict by habit — the phase plan
warned against exactly that before the first source was read.

**Option B — generic isolated adapter.** Rejected as **less precise than the
evidence**. B would be right if the seam had to be invented. It does not:
`src/coding_engine/` routes on `CodingCapability` and *"ne connaît aucun des
trois moteurs par son nom"* (ADR-028). Saying "isolated adapter" where the
correct answer is "fourth entry in an existing capability router" would lose the
one fact that makes the experiment cheap.

**Option D — selected components only.** Rejected as **ill-defined against this
subject**. D presupposes a system with separable parts. DSH states the opposite:
*"Every part of the product is a plugin, including the model adapter, the tool
registry, the session log, and the agent loop itself"*, with *"no privileged
core to patch"*. There is no component to select — there is a plugin tree, and
taking one plugin means taking Cordis and the boot layering with it.

**Option E — replace an existing subsystem.** Rejected, and the directive
anticipated why: *"Do NOT choose E simply because DeepSeek Harness is popular."*
E demands *"exceptionally strong evidence"*. The evidence available is
**170.4k stars on a `0.1.0-rc`** and a `BENCHMARK.md` that publishes **no
scores**. That is not weak evidence for E; it is **no evidence for E**.

D04 also measured four **conflicting** rows — agent orchestration, tool routing,
autonomous workflows, and the permission granularity underneath them. E would
resolve those conflicts by surrendering the thing the directive names
non-negotiable.

---

## Why C, stated as three facts rather than a preference

**1. The subject is a coding harness, and its own catalogue says so.**
`bash`, `pwsh`, `read`/`write`/`edit`, `glob`/`grep`, **`lsp`**, six persistent
PTY tools, `subagent`, `run_code`. D04 classified five GalSen IA subsystems as
`unnecessary` — creative state, video generation, reference entities,
VoiceScene, world representation — because DSH touches none of them and nothing
suggests it intends to.

**2. The seam exists, is specific, and is already exercised.** Three adapters
are declared and **all three are unavailable**, each naming its own repair
(D05, measured). A fourth that is absent changes nothing that works today; a
fourth that works enters through a router that names no engine.

**3. Everything structural passes, and it passes on work already done.**
Complexity, failure detection, fallback and removability (D09) — ADR-028's
capability router, `degradation.py`'s nine probes, the `check_availability`
pattern. None of it was built for this programme.

---

## What C does not mean

- **Not that DSH is better.** Gate 7 is `UNKNOWN`. `lsp` and persistent PTYs are
  **declared capability differences**, not measured quality.
- **Not that it can be deployed here.** D07 measured that its Linux confinement
  cannot run on this host — `bwrap` absent, Landlock `ENOSYS`, weak stub,
  no LSM. That is a **host** constraint; on a host with Landlock compiled in it
  would hold.
- **Not that its plugins come along.** ADR-034's four-tool allowlist transfers
  unchanged, and nothing from DSH's plugin ecosystem is exposed.
- **Not that it may hold provider credentials.** One configuration is viable —
  pointed at our own OpenAI-compatible endpoint — and one is rejected.

---

## The three conditions, and they are cheap

| # | Condition | Closes |
|---|---|---|
| 1 | Install one existing engine and one DSH variant in an environment permitted to install; run the same task set through both on this repository | Phase 7 gates **6, 7, 8** — latency, quality, measurability |
| 2 | Read `@anthropic-ai/claude-agent-sdk`'s licence file | D08's single `UNKNOWN` |
| 3 | Determine what `dsh-headless` persists | The question open since D00.2, unclosed after three phases |

**Condition 1 is the one that matters.** It is also the one this environment
cannot perform, and the directive forbids anyway during the audit.

---

## What this programme produced

| | |
|---|---|
| Volets | 11 |
| Phases | **12 of 14** (D11 remains) |
| Documents | 9 under `docs/deepseek-harness/` |
| ADR | **ADR-035** |
| Lines of `src/` changed | **0** |
| Dependencies added | **0** |
| Tests added, changed, deleted or disabled | **0** |
| Full regressions | one per phase, all `PASS` |

**Phase 9 — the adapter boundary — is now valid to design**, since C was chosen.
It is **not** planned by this document and is **not** authorized: it depends on
condition 1, and the directive's order is audit, measure, decide, then implement
only if justified.

---

## The comparison with ADR-034, since both were audited the same way

| | OpenClaw | DeepSeek Harness |
|---|---|---|
| What it uniquely offers | conversational channels | `lsp`, persistent PTYs, a wider declared coding surface |
| Gates failing outright | **3 of 12** | **0 of 11** |
| Sandbox | off by default, *"not a perfect security boundary"* | kernel-level — **unavailable on this host** |
| Multi-user isolation | *"session IDs… do not authorize one tenant against another"* | not evaluated: a coding backend has no tenants |
| Dependency licences | `UNKNOWN` — unreadable | **read**, ~98 % permissive, one pointer unread |
| Decision | **do not integrate** | **fourth coding backend, not yet** |

**The method was identical and the answers differ**, which is the only evidence
that the method is doing work rather than producing a house verdict.
