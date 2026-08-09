# GalSen IA — Priorities

The full ranked backlog lives in `pending-work.md` (P0–P3, with the criterion that decided
each item). This file holds only what is **active** — what someone would pick up now.

## Active ranking

1. **Keep the suite green.** No module is done while its tests fail. This is exit
   criterion C6 and the only one currently met.
2. **Decide whether the platform has users** (P0). An ADR before any code — it gates
   Phase 2's workspace, Phase 3's collaboration and every adoption metric.
3. **Make generation provable end to end** (P0). The platform's only real feature answers
   503; the task is the test that proves it works when a key is present.
4. Finish VOLET 04 — the roadmap phases still open in `phase-plan.md`.

Everything else is queued in `pending-work.md` and should not be started ahead of these
without saying why.

## How to use this file
- Check it before starting new work.
- Keep it to what is active; the queue belongs in `pending-work.md`.
- When the ranking changes, say what changed it — a ranking without a reason gets
  re-argued at every review.
