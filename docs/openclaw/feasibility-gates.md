# O12 — The twelve feasibility gates (§19), and the decision

**Built**: 2026-08-19, from the eleven volets that precede it. Every answer
cites the volet that measured it. No new evidence is introduced here — a gate
answered from something the audit did not establish would be a guess wearing a
verdict's clothes.

§19's rule: *"If any critical answer is NO: DOCUMENT THE BLOCKER. Do not force
integration."*

---

## The twelve gates

| # | Gate | Answer | Why | From |
|---|---|---|---|---|
| 1 | Does OpenClaw provide functionality GalSen IA actually lacks? | **YES, one** | thirteen of §5's fourteen capabilities already exist here; the exception is **bidirectional conversational channels** | O02 |
| 2 | Is the functionality measurable? | **PARTIAL** | the capability is; every performance figure is `UNKNOWN` because §20 forbids the install that would measure it | O10 |
| 3 | Compatible with the current orchestrator? | **YES, conditionally** | the adapter design holds **12 of §6's 15** controls with existing mechanisms | O11 |
| 4 | Can it remain subordinate? | **YES, conditionally** | subordination is achievable by design; it depends on one open `UNKNOWN` — can OpenClaw be pinned to a single adapter-owned provider? | O06, O11 |
| 5 | **Can it be sandboxed?** | **NO** | its own sandbox is **off by default**, the Gateway process is **not sandboxed at all**, and `tools.elevated` runs on the host. The layer §8 requires needs namespaces and cgroups `src/sandbox/policy.py` records the platform as **not having** | O03, O11 |
| 6 | **Can it support multi-user isolation?** | **NO** | shared: *"Session IDs select routing; they do not authorize one tenant against another."* Per-container: blocked on the same missing privileges, on a Fleet the project calls **experimental** | O04 |
| 7 | Can permissions be centrally controlled? | **YES** | four-tool allowlist narrows the request; `authorize()` decides every call | O03 |
| 8 | Can failures be isolated? | **YES** | one probe in `degradation.py`; absence is `DEGRADED`, not failure | O09 |
| 9 | Can it be removed later? | **YES** | feature-flagged, one probe entry, no core change | O11 |
| 10 | **Does it justify the additional complexity?** | **NO** | it would import a gateway, an agent loop, a permission model, a recovery system and a skill ecosystem **to obtain a messaging surface** — and `src/connectors/` already has the contract for that | O02, O11 |
| 11 | Are licences compatible? | **YES for the core; `UNKNOWN` below it** | MIT declared **and filed**; dependency licences unread; the skill ecosystem has **no single licence to know** | O05 |
| 12 | Unacceptable security risks? | **YES, as deployable here** | gates 5 and 6 together: an unsandboxed process holding credentials, with no authorisation between tenants | O03, O04 |

**Three `NO` on gates 5, 6 and 10; one unacceptable risk on gate 12.**

---

## The decision

**DO NOT INTEGRATE OpenClaw.** No adapter is built, no dependency is added, no
line of `src/` changes.

§19 asks for the blocker to be documented rather than argued around, so here it
is in one paragraph:

> **OpenClaw cannot be sandboxed to the standard §8 requires, on a platform that
> lacks the container privileges to build the boundary; it cannot isolate
> multiple users, by its own documentation; and the one capability it uniquely
> offers — conversational channels — is reachable through a contract this
> repository already enforces, without importing a second runtime.**

**This is a decision about a deployment, not a judgement about a project.**
OpenClaw is candid where it matters — it says its sandbox *"is not a perfect
security boundary"*, it says session IDs do not authorise between tenants, it
marks Fleet experimental. That candour is what made this audit possible, and
most of the `NO`s above come from **its own documentation**, quoted.

## What would change the answer

Written as conditions rather than as hope, because a rejection whose reversal
conditions are vague is a rejection nobody can revisit:

1. **A container runtime the platform may drive**, or a separate host. Gates 5
   and 12 turn on this alone.
2. **Fleet leaving experimental status**, plus application-level authorisation
   between tenants — or a decision that GalSen IA is single-user, which makes
   gate 6 not apply rather than pass.
3. **`pnpm licenses list`** in an environment allowed to install, closing gate
   11's `UNKNOWN`.
4. **Confirmation that OpenClaw can be pinned to one adapter-owned provider**,
   closing gate 4's condition.
5. **A measured per-task session cost**, since three volets independently
   require per-task sessions and nobody knows what they cost.

Gate 10 would still need answering after all five, and it is the one the others
do not reach: **thirteen of fourteen capabilities already exist here.**

## What is recommended instead

**Cost a WhatsApp connector under `src/connectors/`** — not build it; cost it.
It delivers the only thing this audit found missing, and it fits a contract that
already makes subject binding mandatory and checked at registration.

That is a **proposal for a separate programme**, not a task this one creates.
`.claude/rules/spec-driven-governance.md` is explicit that an audit does not get
to authorise its own follow-on work.

---

## What this programme produced

| | |
|---|---|
| Volets | 13 |
| Phases | 19 |
| Documents | 13 under `docs/openclaw/` |
| ADR | ADR-034 |
| Lines of `src/` changed | **0** |
| Dependencies added | **0** |
| Tests added or changed | **0** |
| Full regressions run | one per phase, all `PASS` |

**Ten deliverables of §20, all present**: repository audit (O00), OpenClaw
capability audit (O01), duplication matrix (O02), security analysis (O03),
multi-user isolation analysis (O04), licence audit (O05), performance analysis
(O10), compatibility analysis (O06), architecture proposal (O11), feasibility
decision (this document).

**§21 is not entered.** It is conditional on approval, and the answer is no.

---

## Findings about GalSen IA itself, produced by the audit

Recorded rather than fixed — each belongs to `pending-work`, and none is
OpenClaw's business:

1. **`ApprovalRequest` carries `agent_id`, no subject** — an approval is
   attributed to the agent that asked, not the person it was asked for (O04).
2. **Key revocation state lives in process memory**, which is why a second
   instance is forbidden on the same data directory (O04).
3. **`load_capabilities()` is uncached at ~22 ms** — latent, because every API
   caller passes a shared registry, and a future caller that omits it gets a
   7 000× slower authorisation (O10).
4. **Two job vocabularies and two retry managers**, recorded in O00 and left
   unjudged.
5. **`OPTIONAL SUGGESTION — NOT IMPLEMENTED`**: installation-keyed pseudonyms
   for exported identifiers, an idea taken from OpenClaw's audit ledger (O08).

An audit that finds five things about its own repository has been worth running
even when its answer is no.
