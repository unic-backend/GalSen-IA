# Creative Canvas & Cinema Orchestration — phase plan

Programme: **GALSEN-IA — CREATIVE CANVAS & CINEMA ORCHESTRATION EXTENSION**
(28 sections, 21 execution steps).
Baseline `9f80dbc` (PR #28 merged), 6 233 tests passing, `ruff` clean.

Follows the MoneyPrinterTurbo programme (15 phases, complete —
`docs/providers/phase-plan.md`) and does **not** restart it.

**Cadence: two phases per turn**, as agreed on 2026-08-19.

**New permanent rule in force**: `.claude/rules/post-integration-validation.md`,
established by the project owner in §24 of this directive. Every phase from here
ends with a full regression validation, not with a compilation.

---

## The sentence this programme has to keep true

§28: **GalSen IA is not a Higgsfield clone and not an OpenCanvas clone.** They
are references and optional component sources. The orchestrator owns creative
intent, references, world state, continuity, shot planning, routing,
verification, provenance, privacy, consent and safety.

Everything below is ordered so the canvas is designed **after** the audits that
say which ideas are worth taking — because copying a node graph first is exactly
how an orchestrator becomes a cage.

---

## The 9 volets, and their phases

```
K00  Audit — GalSen IA's creative/video, security, memory, provenance  → 2 phases  ✅
K01  Audit — the five repositories, one at a time (§2, §4)             → 3 phases  ✅
K02  Licence and dependency matrix (§18) — the gate                    → 1 phase (indivisible)
K03  Obsolete assumptions + Creative Canvas architecture (§5, §7)      → 2 phases
K04  Provider comparison, ADR-031, feasibility report (§11, §25)       → 2 phases
K05  CreativeIntent — required / optional / forbidden (§6, §7)         → 2 phases
K06  Cinema layer — CameraSpec, LensSpec, ShotSpec normalised (§10)    → 2 phases
K07  Smallest validated vertical slice (§22)                           → 2 phases
K08  Full regression, measurements, final report (§24, §26)            → 1 phase (indivisible)
```

**Total: 17 phases.** Completed: **5**.
Audits → `docs/canvas/audit.md` (K00), `docs/canvas/repo-audit.md` (K01).

---

## What the probes already established, and how it shapes the plan

Two measurements, taken before writing this plan.

**All five repositories are reachable.** `raw.githubusercontent.com` answers
`200` for every README. So §2's audit can be done against source, like the
MoneyPrinterTurbo one — not against summaries.

**Two of the five have no licence file at all.** This contradicts the directive,
which states MIT for both:

| Repository | `LICENSE` at `main` | Other paths tried |
|---|---|---|
| `opencanvasai/OpenCanvas` | **MIT License** | — |
| `abdrsan/Higgsfield-Open` | **MIT License** | — |
| `higgsfield-ai/skills` | **MIT License** | — |
| `clearsolid/open-higgsfield-ai` | **404** | `LICENSE.md`, `.txt`, `COPYING`, on `main` **and** `master` — all 404 |
| `troy1471-sys/open-higgsfield` | **404** | same, all 404 |

**Absence of a licence is not MIT. It is all rights reserved**, by default of
copyright. Two of the five candidates may therefore be legally unusable as
source of anything — not as a dependency, not as a vendored file, not as copied
code.

Both also serve an identical README first line — *"# Open Higgsfield AI —
Open-Source Alternative"* — which suggests one is a fork or copy of the other.
Establishing that relationship is part of K01, because "which implementation is
technically superior" (§2 D) is a different question when one is a copy.

**K01 settled that relationship**: `index.html` and `src/main.js` are
byte-identical (SHA-256) between the two unlicensed repositories — one is a
repackaging of the other, not a competing design. Full findings, including a
licence discrepancy inside `abdrsan/Higgsfield-Open` itself, →
`docs/canvas/repo-audit.md`.

**So K02 is not a formality placed after the fun part.** It is a gate: two
candidates could be disqualified before a single idea is extracted from them,
and extracting first would mean reading code this platform may not lawfully
learn from in a shipped product.

---

## What this programme must NOT redo

§13 and §3 forbid rebuilding what exists. Measured in the two previous
programmes:

| Directive section | Already built | Where |
|---|---|---|
| §8 Reference entities, consent, provenance | C05, C06, C16 | `src/creative/reference/`, `jobs.py` |
| §9 World state | C09 | `src/creative/world.py` |
| §11 Provider abstraction, registry | C04, M05 | `src/creative/providers.py` |
| §12 Capability routing | C15 | `src/creative/routing.py` |
| §14 Continuity, §15 verification | C11 | `src/creative/verification.py` |
| §17 Fallback (refusal to substitute) | C15, M07 | `routing.py` |
| §10 partial — style separated from world | C19 | `src/creative/style.py` |
| §13 existing video generation | — | `src/media/providers/` (wangp, moneyprinterturbo) |

**K00's job is to verify these against the code, not to write them again**, and
to record precisely what each does *not* do. The three provider abstractions
found in M00.2 are the trap to avoid repeating: §11 lists fifteen registry-ish
types, and this platform already has three registries.

---

## The rules this programme is built on

1. **Audit before design, design before code** (§27's twenty-one steps).
2. **No licence, no adoption** (§18). Absence is not permission.
3. **The orchestrator owns the intelligence** (§28); providers stay replaceable.
4. **Never invent creative content the user did not request** (§6). Required,
   optional and forbidden elements stay three separate things.
5. **`UNKNOWN` is never converted into an assumption** (§7).
6. **No duplicate registry, memory or provenance system** (§3).
7. **Measure after implementing, never before** (§21). No fabricated benchmark.
8. **Full regression after every phase** — the new permanent rule.

---

## Reporting

Every phase ends in the shape `.claude/rules/phase-protocol.md` requires, plus
the regression validation the new rule demands. The programme closes with §26's
twenty-four points, including those that will read `UNKNOWN` or `BLOCKED`.
