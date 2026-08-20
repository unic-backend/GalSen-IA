# D09 — Feasibility gates (Phase 7)

**Built**: 2026-08-20. Each gate cites the volet that measured it. Where a gate
needed a measurement nobody had taken, this phase took it — commands given.

Phase 7's rule: *"If any critical gate fails: DOCUMENT THE BLOCKER. Do not fake
implementation."*

---

## Measurements taken for this phase

```bash
node --version   # → v22.22.2
pnpm --version   # → 10.33.0
nproc            # → 4
free -m          # → 16 075 MB total, 15 090 MB available
df -h /          # → 28 G available
ls /dev/nvidia*  # → none
```

**DSH's `engines` field requires `node: ^22.19.0 || >=24.0.0`.**
`v22.22.2` satisfies `^22.19.0`. **The runtime requirement is met on this host**,
and `pnpm` — its declared package manager — is present at 10.33.0 against a
declared `pnpm@11.7.0`, a minor-version gap recorded rather than dismissed.

**The asymmetry this produces is the finding of D09**: the harness *could run*
here, and its *confinement could not* (D07). Being able to execute something you
cannot confine is the least comfortable of the four possible combinations.

---

## The eleven gates

| # | Gate | Answer | Why | From |
|---|---|---|---|---|
| 1 | Does it improve GalSen IA? | **YES, narrowly and unmeasured** | `lsp` and six persistent-PTY tools have no equivalent here; the declared coding surface is wider than any single existing adapter. **No quality claim is supported** | D05 |
| 2 | Does it duplicate existing capabilities? | **YES as an orchestrator, NO as a coding adapter** | 4 conflicting + 1 duplicate rows on orchestration; but the three declared coding engines are **all unavailable**, so a fourth duplicates nothing that runs | D04, D05 |
| 3 | Unacceptable complexity? | **NO** | `router.py` *"ne connaît aucun des trois moteurs par son nom"* — a fourth adapter is a declaration, not a redesign (ADR-028) | D05 |
| 4 | **Is the required CPU feasible?** | **YES** | Node `v22.22.2` satisfies `^22.19.0`; 4 CPUs, 15 GB free, 28 GB disk | **measured here** |
| 5 | **Is the required GPU feasible?** | **YES** | DSH states **no GPU requirement**; none is present, and none is needed | D00.1, measured here |
| 6 | Is latency acceptable? | **`UNKNOWN`** | nothing installed, nothing run — *"never fabricate numbers"* | D05 |
| 7 | Is quality acceptable? | **`UNKNOWN`** | `BENCHMARK.md` publishes **NO SCORES**; the repository contains no comparative evidence | D05 |
| 8 | Is capability measurable? | **YES in principle, NO here** | a benchmark **harness** ships; running it needs an install the directive forbids | D05 |
| 9 | Can failure be detected? | **YES** | `check_availability()` already returns a reason and a repair per engine; `degradation.py` probes nine subsystems | D06 |
| 10 | Can GalSen IA fall back? | **YES** | three independent layers, and the coding router **already runs with zero engines available** | D06 |
| 11 | Can the integration be removed later? | **YES** | remove the adapter declaration; nothing in the orchestrator names it | D05, D06 |

**Seven `YES`, one `NO` (which is the good direction for gate 3), three
`UNKNOWN`, and one split answer.**

---

## The blockers, documented as Phase 7 requires

**Blocker 1 — the sandbox cannot run on this host.**
`bwrap` absent, `landlock_create_ruleset` → `ENOSYS`, weak stub in `kallsyms`,
no LSM in `securityfs` (D07, measured three ways). DSH's file confinement is its
strongest security property and **it is unavailable here**. Its own rule means
it would refuse to confine rather than pretend to.

This does not appear in the eleven gates — Phase 7 does not ask about
sandboxing — which is why it is written here rather than left implicit in a
table.

**Blocker 2 — quality is unmeasured, by anyone whose evidence this audit could
read.** Gate 7 is `UNKNOWN`, and it is the gate the whole *"is it a better
coding agent"* question rests on. The project publishes a harness, not results.

**Blocker 3 — one licence is a pointer, not an identifier.**
`@anthropic-ai/claude-agent-sdk` is `SEE LICENSE IN`, unread (D08). Phase 6 says
mark it and do not integrate on the strength of the others.

**Not a blocker, recorded**: `pnpm 10.33.0` present against `pnpm@11.7.0`
declared.

---

## What the gates say together

**No gate fails outright.** That is a materially different picture from the
previous programme, where three of twelve answered `NO` and one named an
unacceptable risk.

Here the pattern is: **everything structural passes, everything empirical is
`UNKNOWN`.** Gates 3, 9, 10 and 11 — complexity, failure detection, fallback,
removability — all pass **because of work this repository already did**
(ADR-028's capability router, `degradation.py`, the `check_availability`
pattern). Gates 6, 7 and 8 are `UNKNOWN` **because the directive forbids the
install that would settle them**.

`INFERENCE` for D10: this is not a decision between *integrate* and *do not
integrate*. It is a decision about **what to do with three `UNKNOWN`s that one
permitted installation would close**, against **one blocker that no
installation would close on this host**.

Those are different kinds of unknown, and D10 must not average them.

---

## What D09 refuses to conclude

- **That gate 1 justifies anything.** *"Improves, narrowly and unmeasured"* is
  not evidence of improvement; it is evidence of a wider declared surface.
- **That the passing gates recommend integration.** Seven `YES` on structure
  say the experiment is *cheap and reversible*, not that it is *warranted*.
- **That gate 7 can be answered from stars.** 170.4k stars on a `0.1.0-rc`
  measures attention, and the directive forbids the claim that would follow.
