# GalSen IA — Priorities

The full ranked backlog lives in `pending-work.md` (P0–P3, with the criterion that
decided each item). This file holds only what is **active** — what someone would pick up
now.

*Ranking revised 2026-08-20: the top of this list had not moved since the day four exit
criteria were still open and ADR-029 was still a question. Both had changed.*

## Active ranking

1. **Keep the suite green.** No module is done while its tests fail. C6, and it is the
   gate every other item passes through.
2. **Configure a model provider** (P0, criterion C1). The platform's only real feature
   answers `503`; the test that proves it works already exists and skips until something
   answers. `ollama serve` with a context of at least 8 192 costs nothing.
3. **Deploy it somewhere reachable** (P0, criterion C4). TLS termination and the compose
   file are written and unverified against a real host.
4. **Feed the knowledge base the corpus that matters.** It is no longer empty — 212
   sector objects, 14 regions, 45 departments, all sourced — but agriculture, health and
   education hold nothing, and **ten domains carry the reason instead of a filling**.
   Blocked here by the proxy, not by code.
5. **Give this repository a `LICENSE` file.** The last of the two holes both external
   audits found, and the only one that is not a task: **which licence is the owner's
   decision.**

**Retired on 2026-08-20** — *« Decide whether the platform has users »*, decided by
ADR-029 on 2026-08-18. And *« the sovereignty test does not cover subordinate runtimes »*,
closed the same day by `tests/test_sovereignty_subordinate_runtimes.py`.

Everything else is queued in `pending-work.md` and should not be started ahead of these
without saying why.

## How to use this file
- Check it before starting new work.
- Keep it to what is active; the queue belongs in `pending-work.md`.
- When the ranking changes, say what changed it — a ranking without a reason gets
  re-argued at every review.
