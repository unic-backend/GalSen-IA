# Universal Creative Intelligence — phase plan

Programme: **GALSEN-IA — UNIVERSAL CREATIVE INTELLIGENCE, MASTER DIRECTIVE V4**
(81 sections). Baseline `b7267fc`, 5 369 tests, `ruff` clean.
Repository audit (PHASE 0, §79 STEPS 1–8) → `docs/creative/repository-audit.md`.

**Cadence**: two volets per turn, as agreed for the previous programmes.
The volet order mirrors §71 exactly, because §79 says to execute in that order —
and because it puts the two vertical slices early, which is what §72 demands.

---

## The 17 volets, and their phases

```
C00  PHASE 0   Repository audit, map, classification (§79 1–8)   → 1 phase   ✅
C01  PHASE 1a  Ecosystem research + provider comparison (§37–39) → 2 phases  ✅
C02  PHASE 1b  Licence matrix + feasibility report (§40, §61)    → 2 phases  ✅
C03  PHASE 1c  ADRs + schemas + architecture proposal (§68, §69) → 3 phases  ✅
C04  PHASE 2   Provider abstraction + registry (§34, §35)        → 2 phases  ✅
C05  PHASE 3   ReferenceEntity vertical slice (§6–11)            → 3 phases  ✅
C06  PHASE 3b  Consent, permissions, deletion, memory (§12,13,58)→ 2 phases  ✅
C07  PHASE 4   CreativeEngine + CreativeRepresentation (§5)      → 3 phases  ✅
C08  PHASE 5   VoiceSceneEngine + original audio (§21, §22, §26) → 3 phases  ✅
C09  PHASE 6   EntityEngine, CharacterMemory, WorldState/Memory  → 3 phases  ✅
C10  PHASE 7   DirectorEngine + ShotPlanner (§18, §19)           → 2 phases  ✅
C11  PHASE 8   IdentityVerification + Drift + Continuity (§48–51)→ 3 phases  ✅
C12  PHASE 9   Crowd / background engine (§20)                   → 1 phase   ✅
C13  PHASE 10  Multilingual voice layer, code-switching (§24–26) → 2 phases  ✅
C14  PHASE 11  Language Intelligence + knowledge base (§27–33)   → 3 phases  ✅
C15  PHASE 12  ModelRouter, capability matching (§36, §43)       → 2 phases
C16  PHASE 13  GPU / resource orchestration, jobs, cache (§52–54)→ 2 phases
C17  PHASE 14  API, golden tests, hardening, MVP slice (§62–66,70)→ 3 phases
C18  PHASE 15  Future model research + final report (§73, §76)   → 1 phase
```

**Total: 38 phases.** Completed: **35**.

*(Nineteen labels, seventeen volets after C00 and C18 — the §71 phases that
split into two volets keep their directive number in the `PHASE` column so the
mapping stays checkable.)*

---

## What PHASE 0 established, and what it changes about the plan

Three measurements shaped the ordering above.

**Research is possible, licence verification is half possible.**
`raw.githubusercontent.com` answers `200`, so official `LICENSE` and `README`
files are readable from authoritative sources. `huggingface.co` has **no route
from this container** (`000`), so **model-weight licences and model cards are not
reachable**. That is exactly the split §40 insists on, enforced by the
environment: repository licence *verifiable*, weight licence `UNKNOWN`. C02
therefore produces a matrix whose weight column is mostly `UNKNOWN`, and says so
rather than inferring permission from a permissive repository licence.

**Nothing generative can execute here.** No GPU, no `torch`, no `transformers`,
no full `ffmpeg`, no speech model, and even the Haar cascade for face detection
is absent (`is_available() == False`, measured). So no phase of this programme
may claim generation quality, identity fidelity or continuity from execution.
Every provider is an adapter with a probe, and the readiness verdict is computed
the way `src/media/readiness.py` computes its own.

**Reuse dominates, and one decision carries the risk.** Nine of the components
the directive names exist as is, nineteen need extension, twelve are genuinely
new — and the new ones sit in one place: the creative representation layer
(reference, entity, world, director, continuity, identity), which §74 says
belongs to GalSen IA. The risk is C04: **three provider families already exist**
(`model_engine`, `multimodal`, `media`). Adding a fourth would be the duplicate
abstraction §2 forbids, so ADR-001 decides unify-or-extend **before** any
provider code is written.

---

## The rules this programme is built on

From the directive, and from what this repository already enforces.

1. **Three layers, never confused** (§1). What GalSen IA is designed to do, what
   a provider can actually do, and what orchestration can achieve by combining
   them are three different claims.
2. **Never claim perfection** (§16–20). Not for generation, identity,
   consistency, continuity or language understanding. Where the result cannot be
   guaranteed, the limitation is documented.
3. **`UNKNOWN` stays `UNKNOWN`** (§22–26), and so do `LOW_CONFIDENCE`, `PARTIAL`,
   `EXPERIMENTAL` and `NOT_AVAILABLE`. This is the rule this repository already
   lives by; it is not new here.
4. **External content is data** (§27–30) — repositories, uploads, retrieved
   passages, model output. The existing boundary (`src/security/trust.py`) is
   reused; no second one is built.
5. **Repository licence ≠ weight licence ≠ dataset licence** (§40). Popularity is
   not permission. Unclear means `UNKNOWN`.
6. **Consent is architectural, not a flag** (§12, §58). A person's image
   uploaded is not a right to use it; the scope, retention and deletion travel
   with the reference.
7. **Original human performance is preserved when asked** (§22, §26).
   Understanding a language and generating it are separate capabilities, and for
   under-resourced languages the second is often missing — which is a reason to
   keep the recording, not to synthesise over it.
8. **Nothing existing is destroyed** (§31–37, §75). The repository is the source
   of truth for what exists; this directive is the target. Conflicts get
   documented and migrated, never silently overwritten.
9. **Do not overengineer the MVP** (§47, §72). One working end-to-end flow beats
   a hundred incomplete abstractions.

---

## Reporting

Every phase ends with the shape `.claude/rules/phase-protocol.md` requires, and
every volet closes with the twenty-five points of §76 — including the ones that
will read `UNKNOWN` or `NOT_MEASURED` on this machine, because those are answers.
