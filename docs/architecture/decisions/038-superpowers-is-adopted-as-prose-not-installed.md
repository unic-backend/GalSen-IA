# ADR-038 — Superpowers is adopted as prose, and not installed

**Status**: accepted
**Date**: 2026-08-22
**Directive**: GalSen IA — Superpowers Compatibility & Integration Audit, §0–§27
**Audit**: `docs/research/superpowers-audit.md` (24 phases)
**Implementation**: 11 phases, candidates C1–C6
**Subject**: `obra/superpowers` at `b36e0829c6d0140e93cfef2ca599b1b07d4a7797`,
release v6.3.0, MIT

## Context

The owner asked whether `obra/superpowers` could improve GalSen IA's internal
engineering methodology — its agents, skills, verification, planning, debugging,
testing, memory and orchestration — under an explicit constraint: GalSen IA is an
independent platform, and no coding-agent framework belongs in its runtime.

The audit ran 24 phases and measured both sides before comparing them.

**What Superpowers is, measured rather than characterised**: 29 322 lines of
markdown against 4 012 lines of code, zero declared dependencies, no lockfile, no
vendored third-party code, and **no import surface at all**. It is a plugin that
distributes an engineering methodology as markdown skills to thirteen
coding-agent CLIs. Not a model, not an inference engine, not a runtime — and not
a library. *Integration was therefore never a technical question, only an
editorial one.*

**What GalSen IA already had**: of 37 subsystems compared, **19 scored `KEEP
GALSEN`** and **`REPLACE EXISTING COMPONENT` scored zero**. There was no gap in
security, permissions, observability, memory, documentation or product testing.

**The finding that decided the ADR is about GalSen IA, not about Superpowers**:
15 rule files, 15 skills and a `CLAUDE.md` existed with **no evidence that any of
them changed an agent's behaviour**. This repository's central discipline is that
a guard is not believed until it has been sabotaged and seen to go red — applied
rigorously to code, and never once to the prose governing the code.

## Decision

**`PARTIAL-GO`. Six concepts are adopted natively. One file is copied. Nothing is
installed.**

| | Candidate | Landed in |
|---|---|---|
| C1 | Behaviour testing for instructions | `.claude/skills/testing-instructions/` |
| C2 | Four-phase debugging procedure | `.claude/skills/systematic-debugging/` |
| C3 | Verification freshness — *in this message* | `.claude/rules/verification.md` |
| C4 | Ruling format — what · why · **cost if wrong** | `.claude/rules/memory.md`, `phase-protocol.md` |
| C5 | How a development branch ends | `.claude/rules/git-workflow.md` |
| C6 | `find_polluter.py` | `scripts/find_polluter.py` |

**The plugin is not installed**, and that is the load-bearing half of the
decision. Installing would import three things GalSen IA has decided against:

1. **A cadence that contradicts a permanent rule.** `subagent-driven-development`
   and `executing-plans` instruct the agent not to pause between tasks and to
   rule rather than ask. `.claude/rules/phase-protocol.md` mandates one phase per
   turn ending in an explicit stop. `spec-driven-governance.md` forbids silently
   overriding an architectural rule, so the conflict is resolved *against* the
   source and recorded rather than absorbed.
2. **An unreviewed, auto-updating instruction stream.** The bootstrap injects a
   skill file into every session wrapped in `<EXTREMELY_IMPORTANT>`, and updates
   are — the README's words — *"often automatic"*. That inverts
   `src/security/trust.py`'s rule that external text is data with an origin and
   never an instruction. The current content is benign; its benignity is not
   verified at the moment it is used.
3. **Nine skills GalSen IA does not need**, paid for in context and governance.

Four further exclusions are named so they cannot drift back in:
`dispatching-parallel-agents` (`execution_planner.py` sets
`parallel_supported: False`; adopting the procedure would document a capability
that does not exist), `brainstorming` (the repository's only telemetry surface),
`using-git-worktrees` (real value, unrealised in a single ephemeral container),
and **the subagent fix loop** — genuinely valuable, but it touches
`workflows.yaml` and agent behaviour and its model cost is `UNKNOWN`, so it
requires its own audit rather than a line in someone else's candidate list.

## Consequences

**Cost: zero dependencies, zero runtime, ~0 bytes added to session start.** Rules
load on demand as the existing 15 already do. Nothing under `src/` changed;
`agents/`, `workflows/` and the test suite are untouched.

**Licence**: MIT throughout, verified from the clone — `LICENSE` and
`plugin.json` agree, `package.json` carries no `license` field. No copyleft,
compatible with ADR-036's Apache-2.0. Five candidates reuse concepts, which carry
no attribution obligation; **C6 is a real copy and carries the MIT notice and its
origin commit in its header.**

**Independence is unaffected**: Superpowers is development-time, nothing under
`src/` would load it, and GalSen IA in production does not contain it.

**One rule was measured for the first time in this repository's history.** C3 was
put through C1: RED without the clause, GREEN with it. Two things came out of it
that no amount of reading would have produced:

- **C3 created a conflict with `work-cadence.md`** — an agent cited *"do not
  re-verify what a previous phase already verified"* to justify a stale claim.
  Closed the same day; `work-cadence.md` now states its boundary.
- **The method has a limit in this environment**: subagents inherit `CLAUDE.md`,
  so a rule-free baseline is not achievable by instruction. The skill records the
  weaker claim it can actually support.

**C6's proof step found a real bug in the port on its first run** — a `TypeError`
in the bisection call. Adopting it without that step would have adopted a broken
tool, which is why the audit made the proof a requirement of the candidate.

**Measured cost of C1**: ~59 000 subagent tokens and 7–11 s per dispatch, ~60 000
per arm. Cheap enough for rules that cost something to obey; not cheap enough for
all 15 without choosing.

**What remains `UNKNOWN`**: the model cost of the excluded subagent loop, the
minimum Node version of two Superpowers files no candidate uses, and the licences
of the externally hosted brand image and the Graphviz binary. None blocks
anything; all are recorded in the audit rather than reasoned away.

## Alternatives rejected

**Install the plugin (`GO`)** — rejected for the three reasons above. Popularity
is not among them: `subagent-driven-development` is genuinely excellent and
carries an instruction this repository has already decided against.

**Do nothing (`NO-GO`)** — rejected because the gaps were not speculative. Three
of the five were hit by hand during the session that found them.

**Defer** — rejected because nothing material was missing. The two open
`UNKNOWN`s concern what a recommendation costs to operate, not whether it is
sound.
