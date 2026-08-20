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
D04  GalSen IA overlap matrix — Phase 2's 20 subsystems        → 2 phases  ✅
D05  Coding capability evaluation (Phase 3)                    → 2 phases  ✅
D06  Provider independence (Phase 4)                           → 1 phase (indivisible)  ✅
D07  Security audit (Phase 5)                                  → 1 phase (indivisible)  ✅
D08  Licence audit (Phase 6) — the gate                        → 1 phase (indivisible)  ✅
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

**D04 is done** — `docs/deepseek-harness/overlap-matrix.md`. Nineteen
subsystems: **4 complementary, 1 duplicate, 4 conflicting, 5 unnecessary,
5 `UNKNOWN`**.

**The strongest positive finding in five programmes**: GalSen IA's sandbox and
DSH's fail on *opposite* axes. Ours bounds CPU, memory, processes and the
environment but explicitly **not** filesystem or network, for want of
privileges. Theirs bounds **exactly the filesystem**, at kernel level, and
explicitly not network. Each covers what the other cannot — Phase 2's class A by
definition. Whether `bwrap`/Landlock is permitted **here** is `UNKNOWN`, and D07
must measure it rather than assume either way.

**The question is reframed.** DSH is a *coding-agent harness* — `bash`, `pwsh`,
file ops, `glob`/`grep`, `lsp`, PTYs, `subagent`, `run_code`. It touches none of
creative state, video, reference entities, VoiceScene or world representation.
So the honest question is **not** whether it should orchestrate — the directive
answers no and rows 1, 3 and 19 show why it would collide — but **whether it is
a better coding backend than the three adapters `src/coding_engine/` already
declares**.

**D05 is done** — `docs/deepseek-harness/coding-capability.md`. **`BENCHMARK.md`
publishes no scores** — it is a how-to-run file. The repository therefore
contains **no comparative evidence** about coding quality, which is exactly the
claim Phase 3 says not to accept uncritically.

Measured on our side, reproducibly: **three engines declared, zero available**,
each unavailability naming its repair. Phase 3's thirteen axes × two sides =
**twenty-six cells, twenty-six `NOT_MEASURED`**, with different reasons per
column.

Two real capability differences that are not repackaging: **`lsp`** (no existing
adapter declares a language-server path) and **six persistent-PTY tools**.

And the finding that does not depend on any benchmark: `router.py` *"ne connaît
aucun des trois moteurs par son nom"*, so **adding DSH as a fourth adapter costs
a declaration, not a redesign** — the seam Phase 9 asks for already exists
(ADR-028).

**D06 is done** — `docs/deepseek-harness/provider-independence.md`. **The
harness does not require DeepSeek models**: *"supported but not mandated as
default"*, and `dsh-llm-pi-ai` takes a `baseURL` override, so it can be pointed
at our own OpenAI-compatible endpoint and inference stays inside `ModelRouter`.
That closes D00.2's `UNKNOWN` on item 5.

**Phase 4 passes, conditionally on configuration.** Fallback is already built at
three layers — capability-based coding router (which already runs with zero
engines available), nine-subsystem degradation, and `FailoverModelRouter`.

**The programme's sharpest question is now security**: `cordis_define` /
`cordis_run` let an agent **register plugins at runtime**. Whether that reaches
the model adapter is `UNKNOWN` → D07.

**D07 is done** — `docs/deepseek-harness/security-audit.md`. **The measurement
that decides it**: DSH's Linux confinement is `bwrap`/Landlock, and on this host
`bwrap` is absent, `landlock_create_ruleset` returns `ENOSYS`, `kallsyms` shows
a **weak stub**, and `securityfs` lists no LSM. Kernel `6.18.5-fc-v20` has
Landlock compiled out.

So **D04's best finding survives as architecture and fails as deployment,
here.** Third consecutive programme whose blocker is this environment's
privileges rather than the audited project.

Genuine alignment found: approval **fails closed**, and `never` *"resolves
`'rejected'` deterministically"* — this repository's own rule, reached
independently. Weaker than ours on one point: *"Plugin-wide authorization covers
later versions"*, where `src/plugins/review.py` **disables a plugin the moment it
is edited**.

**D08 is done** — `docs/deepseek-harness/licence-audit.md`. **The dependency
tree was read**, which is new: ~130 packages, ~100 MIT, ~15 Apache-2.0, plus
BSD, ISC — and **two copyleft entries** (LGPL-3.0-only, MPL-2.0) that the project
scopes itself to *"development tooling; their code is not linked into or
distributed with any DeepSeek Harness artifact."* Quoted and attributed, not
adopted as verified.

**The gate does not close, and for a narrower reason than last time**: one
dependency, `@anthropic-ai/claude-agent-sdk`, is listed `SEE LICENSE IN` —
a pointer to a file this audit has not read. `UNKNOWN`, and Phase 6 says what
that means. Whether it matters **depends on D10's shape**: the viable coding
configuration would not exercise that path.

**A finding about this repository**: `ls LICENSE*` → **no such file**. Five
programmes spent on *a manifest is a declaration, a file is a grant*, and
GalSen IA has neither. Recorded for `pending-work`.

**Next: D09** — the eleven feasibility gates (Phase 7), one indivisible
phase.

Nothing is installed, nothing under `src/` is touched, and no existing test is
deleted, disabled, weakened or bypassed.
