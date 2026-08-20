# GalSen IA — Current Objectives

*Mesuré le 2026-08-20, contre `docs/roadmap/roadmap.md` et les données sur disque.*

## Active Phase
**Core Platform** (Phase 2 of VOLET_04 ch. 02). Four of the six exit criteria are
met — **C2, C3, C5, C6**. The two that remain, **C1** and **C4**, are an
operator's move and not a build. Where each item stands →
`docs/roadmap/roadmap.md`.

## Current Objectives

1. **Keep the suite green.** C6, and it is held: **6 955 pass, 15 skipped, 1
   failed** in CI. The single failure is the `v0.1.0` tag, which has never been
   pushed and fails identically on `main`.
2. **Make generation answer** (C1). The platform's only real feature returns
   `503` until a provider is configured. The proof already exists —
   `tests/test_generation_end_to_end.py` skips while nothing answers and runs
   the moment something does. Free path: `ollama serve` with a context of at
   least 8 192.
3. **Reach the platform over a network** (C4). Caddy terminates TLS and the
   compose file is written; what is missing is a host and a domain.
4. **Put the corpus that matters into the knowledge base.** It is **no longer
   empty**: 212 sector objects across 4 domains, 14 regions and 45 departments,
   all with provenance, and **10 domains carrying the reason they hold nothing**
   rather than a fabricated filling. What is missing is agriculture, health and
   education — and this environment's proxy refuses the nine Senegalese
   institutional domains (`CONNECT → 403`), so it depends on documents reachable
   from somewhere else.
5. **Give this repository a `LICENSE` file.** Both external audits found it
   missing. A `pyproject` field is a declaration; a file is a grant. **Which
   licence is the owner's decision**, so this objective is a question, not a task.

**Retired on 2026-08-20** — *« Decide whether the platform has users »*: decided
by **ADR-029** (option C) on 2026-08-18. It stayed listed as open for two days.

The full ranked queue is in `pending-work.md`; nothing there should start ahead
of these without a stated reason.

## What tells us this phase is over
The six exit criteria in `docs/roadmap/roadmap.md`, written to be checked by
someone other than their author — a command, a route or a test. **C1 and C4 are
the whole remainder**, and neither is engineering.
