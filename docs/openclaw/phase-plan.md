# OpenClaw Compatibility & Safe Integration — phase plan

Programme: **GALSEN-IA — OPENCLAW COMPATIBILITY & SAFE INTEGRATION DIRECTIVE**
(21 sections). Baseline `b1cb80f`, 6 958 tests passing, `ruff check .` clean.

Follows the Live Context programme (27 phases, complete —
`docs/live-context/final-report.md`, ADR-033) and does **not** reopen it. Its
regression status is `PASS`, which is what the mandatory rule requires before
this one may open.

**Cadence: two phases per turn**, as agreed on 2026-08-19.

**Rules in force**: `.claude/rules/post-integration-validation.md` (regression),
`.claude/rules/spec-driven-governance.md` (scope), and this directive's own §20.

---

## What this plan does not say

**It does not say what OpenClaw is.** §3 requires research from official sources
*at execution time* and §4 forbids confusing an agent runtime with a model. This
session's training data is not a source. Every statement about OpenClaw —
architecture, version, licence, sandbox, provider support — will carry the date
it was read and the URL it came from, or it will read `UNKNOWN`.

Writing "OpenClaw is X" in this plan would fix the conclusion before the audit,
which is exactly what the four previous programmes' audits each overturned.

---

## What §20 makes this programme

§20 lists ten deliverables and ends with **THEN STOP**. This is an *audit
programme with a decision at the end*, not an integration. §21 — the adapter —
is conditional on that decision and is **not planned here**: it will be planned
separately if, and only if, the audit says yes and the owner confirms.

Three things are therefore forbidden for the whole plan below:

- installing OpenClaw,
- modifying the orchestrator, the agents, the memory or the provider routing,
- writing any adapter code.

---

## The 13 volets, and their phases

```
O00  Repository audit — the 27 subsystems of §2                  → 2 phases
O01  OpenClaw research from official sources (§3, §4)            → 2 phases
O02  Duplication matrix (§5)                                     → 1 phase (indivisible)
O03  Tool permission model and sandbox (§7, §8)                  → 2 phases
O04  Multi-user isolation (§9)                                   → 1 phase (indivisible)
O05  Licence audit (§18) — the gate                              → 1 phase (indivisible)
O06  Model providers and memory (§10, §11)                       → 2 phases
O07  Skills and plugins, untrusted until audited (§12)           → 1 phase (indivisible)
O08  Provenance and observability (§13, §14)                     → 1 phase (indivisible)
O09  Self-healing and failure isolation (§15, §16)               → 1 phase (indivisible)
O10  Performance analysis (§17)                                  → 1 phase (indivisible)
O11  Adapter architecture proposal (§6)                          → 2 phases
O12  The twelve feasibility gates, decision and ADR (§19)        → 2 phases
```

**Total: 19 phases.** Counted from the directive's 21 sections; §1 states the
objective and §20 states the method, so neither produces a volet of its own.

**Several of these volets may collapse into a single line**, and the plan says so
now rather than pretending the count is fixed. O05 is a gate: an incompatible or
unfilable licence ends the programme at O05 and turns O06 through O12 into one
recorded blocker. That is the honest shape of an audit-first programme.

---

## The risk this plan names before starting

**The network.** Four previous programmes measured that this environment's proxy
answers `CONNECT → 403` for a long list of domains. §3 requires reading official
OpenClaw sources at execution time. If they cannot be reached, O01 records
`UNKNOWN` **with the exact refusal measured**, and the feasibility gates of §19
are answered on what could actually be read — never on recollection.

An unreachable source is a measured fact, not a reason to fill the gap from
memory.

---

## Where this programme starts

**O00.1 — the first half of §2's subsystem list**, classified
`EXISTING` / `PARTIAL` / `MISSING` / `DUPLICATE` / `UNKNOWN` against the real
repository, with the path that proves each verdict. No file is modified.

Nothing is read about OpenClaw until O01: knowing what this repository already
has is what makes the duplication matrix of §5 mean anything.
