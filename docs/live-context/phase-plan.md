# Live Context Engine — phase plan

Programme: **GALSEN-IA — LIVE CONTEXT ENGINE / CALL.MD INTEGRATION DIRECTIVE**
(48 sections, 16 directive phases).
Baseline `4e0814b`, 6 582 tests passing, `ruff check .` clean.

Follows the Research Orchestration programme (18 phases, complete —
`docs/research/final-report.md`, ADR-032) and does **not** restart it. Its
regression status is `PASS`, which is what the mandatory rule requires before
this one may open.

**Cadence: two phases per turn**, as agreed on 2026-08-19.

**Rules in force**: `.claude/rules/post-integration-validation.md` (regression)
and `.claude/rules/spec-driven-governance.md` (scope). The directive restates
both; they already applied.

---

## The sentence this programme has to keep true

§4 and §46: **GalSen IA does not become a meeting application.** Call.md is a
research source and an optional component. `LiveContextEngine` belongs to
GalSen IA, and the goal is a platform able to *see, hear, understand, remember,
reason and act* in continuous contexts — not a clone of a meeting copilot.

---

## The 16 volets, and their phases

```
L00  Repository audit — what GalSen IA already has (PHASE 0, §1)        → 2 phases  ✅
L01  Call.md audited from source (PHASE 1, §2, §3)                      → 2 phases  ✅
L02  Existing real-time capability audit (PHASE 2, §7, §8, §41)         → 1 phase (indivisible)  ✅
L03  Licence and dependency matrix (§38, §39) — the gate                → 1 phase (indivisible)  ✅
L04  LiveContextEngine architecture + ADR-033 (PHASE 3, §5, §6, §42)    → 2 phases  ✅
L05  Smallest validated live-input slice (PHASE 4, §7)                  → 2 phases
L06  ContextFusionEngine (PHASE 5, §13)                                 → 2 phases
L07  Speakers and languages (PHASE 6, §9, §10, §11)                     → 2 phases
L08  Live assistance and nudges (PHASE 7, §19, §20)                     → 2 phases
L09  MCP integration (PHASE 8, §16, §17)                                → 1 phase (indivisible)
L10  Screen context (PHASE 9, §12)                                      → 1 phase (indivisible)
L11  Memory, privacy, consent, retention (PHASE 10, §14, §28)           → 2 phases
L12  CreativeEngine connection (PHASE 11, §23, §24, §37)                → 1 phase (indivisible)
L13  Provider routing and degraded mode (PHASE 12, §31–§34)             → 2 phases
L14  The thirty test scenarios (§35, §36)                               → 2 phases
L15  Performance, hardening, full regression, final report (13–15, §45) → 2 phases
```

**Total: 27 phases.** Counted programmatically, not estimated.
Completed: **8**. Decision → **ADR-033**. Audits → `docs/live-context/audit.md` (L00),
`repo-audit.md` (L01), `realtime-audit.md` (L02), `licence-matrix.md` (L03).

**Several of these volets will shrink**, and the plan says so now rather than
pretending the count is fixed. L03 is a gate: if it closes, L05 through L13 lose
most of their imported content and become design-only. That is the honest shape
of an audit-first programme, not a hedge.

---

## What the probes already established

Four measurements, taken before writing this plan.

### 1. Call.md is a TypeScript desktop application, and its licence is declared but not filed

| Read | Value |
|---|---|
| `package.json` | `call-md` **1.0.4**, `"license": "MIT"` |
| `LICENSE`, `.md`, `.txt`, `COPYING`, `license` | **404 on `main` and `master`, all five** |
| Runtime dependencies | **27** — hono, tRPC, React, Radix, zustand, drizzle-orm, better-sqlite3, `openai`, **`videodb`**, `@modelcontextprotocol/sdk` |
| Dev dependencies | 27 |
| Python | **none** |

**A manifest field is a declaration; a `LICENSE` file is a grant.** This is the
mirror image of `abdrsan/Higgsfield-Open` in the canvas programme, whose file
said MIT and whose manifest said `null`. Here the file is missing entirely, and
L03 has to weigh what that means rather than record "MIT" and move on.

**`videodb` is a runtime dependency**, which confirms §26's warning before the
audit even starts.

### 2. This environment has no live input at all

| Probe | Result |
|---|---|
| `/dev/snd` | **absent** — no audio device |
| `/dev/video*` | **absent** — no camera |
| `DISPLAY` | **empty** — no screen |
| `ffmpeg` on `PATH` | **not found** |

**This is the constraint that shapes the whole programme**, the way *nothing
generates* shaped the Creative Canvas one. §33 forbids claiming "real-time"
without measurement; here there is nothing to capture, so **capture latency,
transcription latency and every other live figure will read `NOT_MEASURED`**,
and L05's slice must report that rather than simulate it.

A design can still be built and tested. A microphone cannot be invented.

### 3. GalSen IA already has more of this than the directive assumes

Found in the first sweep, to be classified properly in L00 and L02:

- `src/multimodal/whisper_provider.py` — a transcription provider **exists**;
- `src/model_engine/stream_handler.py` — streaming **exists**;
- `src/mcp/` — client, server and a deliberate exposure subset **exist**, and
  the client already defends against tool poisoning;
- `src/media/subtitles/`, `src/media/qc/` — cue and timing machinery exists;
- `pyannote-audio` is already a declared candidate in
  `corpus/creative/providers.yaml`, with its state measured.

§41 forbids creating a second transcription engine, agent loop, memory, MCP
orchestration, event bus or summary engine. **L02 exists to find out how many of
those the directive would have had us build twice.**

### 4. The previous programme's gate is directly relevant

`src/research/safety.py` already holds one address guard, and
`src/creative/canvas/privacy.py` already holds `ProviderPrivacyPolicy`. §29 —
*all live inputs are untrusted data* — is `src/security/trust.py`, which exists
and is already used by two programmes.

---

## What this programme must NOT redo

| Directive asks for | Already here | Where |
|---|---|---|
| Provenance | **yes, twice** | `acquisition/`, `creative/jobs.py` |
| Memory | **yes** | `memory_engine/` |
| MCP orchestration | **yes** | `mcp/client.py`, `server.py`, `exposure.py` |
| Agent loop | **yes** | `agent/`, `router/` |
| Transcription provider | **yes** | `multimodal/whisper_provider.py` |
| Provider registries | **yes, four** | creative, media, model_engine, research |
| Trust boundary | **yes** | `security/trust.py` |
| Privacy per provider | **yes** | `creative/canvas/privacy.py` |
| Summarisation | to be verified | L02 |
| Event bus | to be verified | L02 |

**Four provider declarations now exist.** ADR-032 justified the fourth; a fifth
needs an argument at least as strong, and L04 has to make it or reuse one.

---

## The rules this programme is built on

1. **Audit before design, design before code** (§48).
2. **Call.md is not the foundation** (§0). Capabilities are adapted into the
   existing architecture, never copied wholesale.
3. **No second architecture** (§41). Extend or adapt; do not duplicate.
4. **Live inputs are untrusted data** (§29). Speech, transcript, screen content
   and tool results never override a system instruction or a permission.
5. **Nothing is recorded, retained, uploaded, indexed or shared silently**
   (§28).
6. **Never fabricate a transcription or a translation** (§10). An unidentified
   language is `UNKNOWN`.
7. **Original audio is the source artefact** (§11); transcription is an
   interpretation layer and never replaces it.
8. **No "real-time" claim without a measurement** (§33).
9. **VideoDB is not assumed mandatory** (§26) — cost, privacy, availability and
   fallback are evaluated before any dependency.
10. **Full regression after every phase** — the permanent rule.

---

## Reporting

Every phase ends in the shape `.claude/rules/phase-protocol.md` requires, plus
the regression validation. The programme closes with §45's twenty-four points,
including those that will read `UNKNOWN`, `BLOCKED` or `NOT_MEASURED`.
