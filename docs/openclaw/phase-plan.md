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
O00  Repository audit — the 27 subsystems of §2                  → 2 phases  ✅
O01  OpenClaw research from official sources (§3, §4)            → 2 phases  ✅
O02  Duplication matrix (§5)                                     → 1 phase (indivisible)  ✅
O03  Tool permission model and sandbox (§7, §8)                  → 2 phases  ✅
O04  Multi-user isolation (§9)                                   → 1 phase (indivisible)  ✅
O05  Licence audit (§18) — the gate                              → 1 phase (indivisible)  ✅
O06  Model providers and memory (§10, §11)                       → 2 phases  ✅
O07  Skills and plugins, untrusted until audited (§12)           → 1 phase (indivisible)  ✅
O08  Provenance and observability (§13, §14)                     → 1 phase (indivisible)  ✅
O09  Self-healing and failure isolation (§15, §16)               → 1 phase (indivisible)  ✅
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

**O00 is done** — `docs/openclaw/repo-audit.md`. 27 subsystems classified
against the real repository, 22 `EXISTING`, 4 `PARTIAL`, 0 `MISSING`, 0
`UNKNOWN`, with the path proving each verdict and three candidate duplications
recorded for O02.

**The finding that changes the programme**: this repository already contains an
OpenClaw analysis (`docs/architecture/agent-foundations-comparison.md`, dated
2026-08-12) and **ADR-017 was partly decided on it**. That is not a shortcut —
a claim inside this repository is not an official source, and §3 says do not
rely on old information. O01 verifies from official sources or records
`UNKNOWN`.

**O01 is done** — `docs/openclaw/openclaw-audit.md`. Read 2026-08-19 from
`github.com/openclaw/openclaw` and its `docs/` sources; `docs.openclaw.ai` is
`EGRESS_BLOCKED` by this environment and the refusal is recorded verbatim.

Established: it is a **gateway running an agent loop, not a model** (§4
satisfied); **MIT with a filed `LICENSE`**, dependency licences `UNKNOWN`;
**sandboxing is off by default** and the project states it is *"not a perfect
security boundary"*; multi-tenant isolation is **per-container, experimental**,
and *"session IDs … do not authorize one tenant against another"*; and the
provider list covers every model family §10 names.

**O02 is done** — `docs/openclaw/duplication-matrix.md`. Of §5's fourteen
capabilities: **eight `KEEP_EXISTING`, three `DEFER`, two `UNKNOWN`, zero
`INTEGRATE`**.

The finding: **thirteen of the fourteen already exist here**, and the one real
asymmetry is a category §5 never lists — **bidirectional conversational
channels**. GalSen IA has three one-way operator-facing notification channels;
OpenClaw has WhatsApp, Telegram, Slack, Discord, Signal, iMessage and WebChat.
The honest reason to want it is **reach, not orchestration**, and O11 must weigh
that against a channel connector under the existing orchestrator.

**O03 is done** — `docs/openclaw/permissions-and-sandbox.md`. The allowlist is
**four tools out of twenty-four**, derived from `tools/tools.yaml` rather than
invented, and narrower than the MCP one for a stated reason.

§8's answer: **OpenClaw's sandboxing is not sufficient**, on its own evidence —
off by default, the Gateway itself unsandboxed, `tools.elevated` on the host.
The additional layer §8 demands is a container boundary around the whole
process, and **the platform lacks the privileges to create it** — already
recorded in `src/sandbox/policy.py`'s own `NON_GARANTI`. Named as a blocker for
O12 gate 5, not papered over.

**O04 is done** — `docs/openclaw/multi-user-isolation.md`. §9's fork has
**both branches blocked**. One shared OpenClaw fails on the source's own
sentence — *"Session IDs select routing; they do not authorize one tenant
against another"* — and one container per user needs privileges O03 already
measured as absent, on a Fleet the project calls experimental.

The two shapes do not compose: GalSen IA isolates **per call**, OpenClaw
isolates **per deployment**.

**O05 is done** — `docs/openclaw/licence-matrix.md`. **The gate does not
close.** MIT is both declared *and* filed — unlike the previous programme's
subject, which had the field and no file.

But the ecosystem does not share one licence, measured rather than assumed: two
workspace packages carry **no `license` field**, `skills/` holds **51 wrappers
around other people's software** with no `LICENSE` at that level, and ClawHub
states **no licensing policy** for published skills. Dependency licences are
`UNKNOWN` — `package.json`'s dependencies block could not be fetched, twice, and
`pnpm-lock.yaml` cannot be read whole here.

`UNKNOWN` is a condition, not a refusal: one `pnpm licenses list` settles it, in
an environment allowed to install.

**O06 is done** — `docs/openclaw/providers-and-memory.md`. Provider **coverage**
is not the obstacle: every family §10 names is among OpenClaw's sixty. Provider
**configuration** is. ADR-014 defaults `GALSEN_SOVEREIGN_MODE` to true and does
not register hosted providers *at all*; an OpenClaw holding its own keys reaches
them, and the existing sovereignty test would still pass while the guarantee was
false. One viable shape: OpenClaw configured against GalSen IA's own
OpenAI-compatible endpoint, so `ModelRouter` stays authoritative.

Memory: **controlled combination** — OpenClaw's SQLite is session scratch,
`memory_engine` is the source of truth, and nothing crosses except through the
permission-and-declared-link gate already written.

**O07 is done** — `docs/openclaw/skills-and-plugins.md`. **§12 describes
`src/plugins/`**, which already declares effects and scopes, installs
**disabled**, runs a static manifest-versus-imports check, and **disables a
plugin the moment it is edited**. OpenClaw's plugin document states no
permissions model and leaves capability boundaries unstated; `installPolicy` is
a sound hook, not a policy.

Applying §12's nine-item checklist to the 51 in-repo skills gives **seven
`UNKNOWN`** — not for lack of effort, but because the answer is per-skill and
each wraps someone else's program.

**Decision: expose no OpenClaw skill or plugin. `REJECT` for that surface**,
while the rest of the programme stays open.

**O08 is done** — `docs/openclaw/provenance-and-observability.md`. §13 is
satisfiable **by writing nothing new**: our `AuditEvent` records the execution,
OpenClaw's ledger records its own lifecycle, the `request_id` crosses the
boundary — it already survives boundaries by design — and the two are never
merged. Their ledger is deliberately `metadata_only` and stores **no input, no
output, no raw error**, which is precisely what §13 wants recorded; that
asymmetry is what makes the two complementary rather than conflicting.

§14 needs no new component. One dependency worth noting: `model_id` is only
recordable under O06's viable arrangement, so §10 and §13 exclude the same
option from different directions.

**O09 is done** — `docs/openclaw/self-healing-and-failure-isolation.md`. §16
**costs one probe**: `src/integration/degradation.py` already reports a
subsystem as `DEGRADED` rather than failed, and already refuses to be taken down
by the thing it observes. §15 needs nothing built — the self-healer treats a
traceback as data and answers `UNKNOWN_DIAGNOSIS` rather than guessing.

**A real conflict is named**: OpenClaw re-dispatches interrupted sessions
automatically a few seconds after restart, with a synthetic system message
telling the model to continue. That is an execution decision taken outside
`authorize()` and outside ADR-006's per-execution gate. Resolution: **per-task
sessions owned by the adapter** — which O04 and O06 already required for
different reasons.

**Next: O10** — performance analysis (§17), one indivisible phase.
