# DeepSeek Harness — compatibility audit, phase plan

Programme: **DEEPSEEK HARNESS — GALSEN-IA COMPATIBILITY AUDIT** (10 phases +
final report). Baseline `c7cb1b6`, 6 958 tests passing, `ruff check .` clean.

Follows the OpenClaw audit (19 phases, complete — `docs/openclaw/feasibility-gates.md`,
ADR-034) and does **not** reopen it. Its regression status is `PASS`.

**Cadence: two phases per turn**, as agreed on 2026-08-19.

---

## Two probes taken before writing this plan

The directive names a repository and a documentation site. Both were checked
**before** planning ten phases on top of them, because four previous programmes
were each reshaped by a primary source not being what the directive assumed.

**1. The repository exists.** `github.com/deepseek-ai/deepseek-harness`, read
2026-08-20:

| Read | Value |
|---|---|
| Description | *"DeepSeek Harness (`dsh`) is an open-source agent harness developed by DeepSeek AI"*, with *"an architecture where everything is a plugin"* |
| Licence | **MIT** |
| Stars | 170.4k |
| Language | TypeScript |
| Latest release | **not shown** on the page read → `UNKNOWN` until D01 |

**2. The official documentation site is unreachable from here.**

```
WebFetch https://deepseek.com/harness
→ {"error_type":"EGRESS_BLOCKED","domain":"deepseek.com",
   "message":"Access to deepseek.com is blocked by the network egress proxy."}
```

This is a refusal by **this environment**, not by DeepSeek. The OpenClaw audit
hit the same wall on `docs.openclaw.ai` and worked around it through
`raw.githubusercontent.com`, which carries the same documentation as source
files. **D01 must establish whether that workaround exists here too**, and where
it does not, Phase 1's twenty-five items read `UNKNOWN` with the refusal quoted.

---

## What this plan does not say

**It does not say what DeepSeek Harness is**, beyond the two lines quoted above
from the repository page itself. Phase 1 forbids memory, previous conversations,
unofficial articles and *"benchmark claims without primary sources"*. This
session's training data is not a source.

**It does not assume the answer is no.** The OpenClaw audit ended in `DO NOT
INTEGRATE`, and repeating that verdict by habit would be as unmeasured as
repeating a yes. The two projects differ on at least one axis already visible:
DSH describes itself as *an agent harness* where *everything is a plugin*,
against OpenClaw's *messaging gateway*. Whether that difference matters is what
the audit is for.

**It does not plan implementation.** Phase 9 is conditional on Phase 8 choosing
B, C or D, and Phase 8 is conditional on the gates. If the decision is A, this
programme ends at its final report.

---

## The 11 volets, and their phases

```
D00  Official source audit — Phase 1's 25 items                → 3 phases
D01  ├─ D00.1 identity, licence, releases, requirements
D02  ├─ D00.2 architecture, plugins, agent loop, tools, MCP
D03  └─ D00.3 sandbox, permissions, persistence, observability, recovery
D04  GalSen IA overlap matrix — Phase 2's 20 subsystems        → 2 phases
D05  Coding capability evaluation (Phase 3)                    → 2 phases
D06  Provider independence (Phase 4)                           → 1 phase (indivisible)
D07  Security audit (Phase 5)                                  → 1 phase (indivisible)
D08  Licence audit (Phase 6) — the gate                        → 1 phase (indivisible)
D09  Feasibility gates (Phase 7)                               → 1 phase (indivisible)
D10  Architecture decision + ADR (Phase 8)                     → 1 phase (indivisible)
D11  Test plan (Phase 10) + final report                       → 2 phases
```

**Total: 14 phases.** Phase 1 gets three because it carries twenty-five items;
splitting it two ways would put sandbox and licensing in the same phase as
architecture, and the OpenClaw audit showed those are the ones that decide.

Phase 9 — the adapter boundary — is **not planned here**. It is conditional on
D10, exactly as §21 was in the previous programme.

---

## The one Phase 3 cannot promise, said now

Phase 3 asks for **reproducible tests** of repository understanding, multi-file
changes, debugging, test generation and repair, autonomous loops, recovery and
regression rate — compared against GalSen IA's existing coding providers.

**Two obstacles are already measured**, and naming them now is better than
discovering them in D05:

1. **Nothing may be installed** — the directive says *"DO NOT INSTALL YET"*.
   A harness that is not installed runs no coding task.
2. **`ollama serve` is not running**, and ADR-014 defaults sovereign mode to
   true, so GalSen IA's own coding path produces no generation here either.
   `src/coding_engine/` exists and its providers are unreachable.

`INFERENCE`: D05 will most likely produce a **comparison of declared
capabilities against measured absence on both sides**, not a benchmark. That is
still worth doing — it establishes what each side claims and what would settle
it — but it must be labelled for what it is. Phase 7's gate 8 (*is capability
measurable?*) is where that lands.

---

## Where this programme starts

**D00.1 and D00.2 are done** — `docs/deepseek-harness/source-audit.md`.

Established: **`0.1.0-rc.8`**, released **2026-08-19**, one day before this
audit; **MIT filed**; Node `^22.19.0 || >=24.0.0`; a `python/` directory and a
`pytest.ini` at root, so not TypeScript-only; **`THIRD_PARTY_NOTICES.md` shipped
by the project** — the first subject in four programmes to publish one.

*Everything is a plugin* is literal: *"including the model adapter, the tool
registry, the session log, and the agent loop itself"*, with *"no privileged
core to patch"*.

**The finding that reframes the audit**: `dsh-headless` is *"a one-shot runner
without a server"*. Every constraint that made OpenClaw un-adoptable flowed from
a daemon holding state and credentials. A one-shot runner has none of those
properties by construction — **whether that is really so is now the audit's
central question**, and D00.3 and D07 must establish it rather than inherit the
previous verdict.

Correction recorded: the default branch is **`master`**, not `main`; the first
raw fetch 404'd on that.

**D00.3 is done** — the source audit now covers Phase 1 end to end:
**fourteen items verified, eleven `UNKNOWN`**, each `UNKNOWN` named with the
document that would close it.

**The sandbox is not OpenClaw's sandbox**: kernel-level per platform — `bwrap`/
Landlock, Seatbelt, ACL restricted-token — three declared modes, partial
enforcement **reported rather than hidden**, and a published limit (file effects
only; *"Network and process visibility are outside this vocabulary"*). Its own
rule reads like ours: *"Silent unconfined passthrough is never legal for a
confined policy."*

**The central question is still open.** `dsh-headless` is documented as a
one-shot runner, and `persistence.md` *"does not distinguish persistence
behavior between one-shot runs and server deployments"*. Everything downstream
turns on it. Handed to D07, not resolved by assumption.

**Next: D04.1 and D04.2** — the overlap matrix against Phase 2's twenty
subsystems.

Nothing is installed, nothing under `src/` is touched, and no existing test is
deleted, disabled, weakened or bypassed.
