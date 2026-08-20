# ADR-034 — OpenClaw is audited and not integrated; the gap it exposes is a channel, not a runtime

**Status**: accepted
**Date**: 2026-08-20
**Directive**: OpenClaw Compatibility & Safe Integration, §2–§21
**Volets**: O00–O11 (evidence), O12 (this decision)
**Report**: `docs/openclaw/feasibility-gates.md`

## Context

The directive asked whether OpenClaw could be integrated as a **subordinate**
agent runtime — explicitly not as GalSen IA's orchestrator — behind a controlled
adapter. Twelve volets of audit answered it, and §20's instruction to produce
ten deliverables **and then stop** shaped the programme: nothing was installed,
no `src/` file was changed.

**The repository already contained an OpenClaw analysis** dated 2026-08-12, and
ADR-017 cites it. That was treated as a prior reading by this project rather
than as a source: §3 requires official sources read at execution time, and the
older text turned out to attribute to OpenClaw a *"trusted vs constrained
sessions"* distinction that today's `permission-modes.md` does not use.

Everything below is measured, and most of the refusals are quoted from
OpenClaw's own documentation.

## Decisions

### 1. Do not integrate

No adapter, no dependency, no change to `src/`. Three of §19's twelve gates
answer `NO`, and one names an unacceptable risk.

### 2. It cannot be sandboxed to our standard, and the reason is ours

OpenClaw's sandboxing is **off by default**; the Gateway process — the part
holding credentials and channel accounts — **is not sandboxed at all**; and
`tools.elevated` runs on the host by design. Its own document says *"This is not
a perfect security boundary."*

§8 therefore requires an additional isolation layer, and that layer is a
container boundary around the whole process. **`src/sandbox/policy.py` already
records that the platform lacks the namespaces and cgroups to build one**, which
is also why the `docker` tool is declared and disabled (ADR-017). The blocker
predates this programme.

### 3. It cannot isolate multiple users, by its own documentation

*"Session IDs select routing; they do not authorize one tenant against
another."* A shared instance therefore fails §9 on all seven asset classes it
lists. The per-tenant alternative is blocked on the same missing privileges, on
a Fleet the project marks **experimental**, changeable *"without a deprecation
window"*.

**The two systems isolate at different layers**: GalSen IA per call, OpenClaw
per deployment. They do not compose.

### 4. The complexity is not justified, because thirteen of fourteen already exist

§5's duplication matrix returned **eight `KEEP_EXISTING`, three `DEFER`, two
`UNKNOWN`, zero `INTEGRATE`**. The `NudgeEngine` of §20 is `src/proactive/`;
§12's untrusted-plugin discipline is `src/plugins/`, which additionally
**disables a plugin the moment it is edited**; §16's failure isolation is
`src/integration/degradation.py`, which already reports `DEGRADED` rather than
failed.

### 5. The real gap is a channel, and it has a cheaper route

The one thing OpenClaw uniquely offers is **bidirectional conversational
channels**. GalSen IA has three notification channels, all one-way and
operator-facing; nobody can message this platform from WhatsApp and get an
answer.

`src/connectors/` already enforces the two questions a channel raises — *what
class of data does this reach* and *on whose behalf* — mandatory and checked at
registration. **Costing a WhatsApp connector is recommended as a separate
programme.** This ADR does not authorise it.

### 6. Sovereignty would have been bypassed, and silently

ADR-014 defaults `GALSEN_SOVEREIGN_MODE` to true and does **not register** hosted
providers in that mode. An OpenClaw instance holds its own credentials, so one
configured with a hosted key would reach that provider — and **the existing
sovereignty test would keep passing**, because it exercises GalSen IA's model
path and OpenClaw is not on it.

Recorded because it generalises: **any subordinate runtime with its own
credential store is a hole in ADR-014 that our current tests cannot see.**

## Consequences

**Positive.** Nothing was added, so nothing must be maintained, removed or
migrated later. The audit produced five findings about GalSen IA itself
(`feasibility-gates.md`, final section), and a reusable question for any future
runtime proposal: *does it bring a capability we lack, or a wrapper around
capabilities we have?*

**Negative, stated rather than softened.** The channel gap **remains open**, and
this decision does not close it — it declines one route and names another. A
platform whose purpose is serving Senegal still cannot be reached on WhatsApp.

**Neutral.** OpenClaw's ideas are taken where they are better: installation-keyed
pseudonyms for exported identifiers are recorded as `OPTIONAL SUGGESTION — NOT
IMPLEMENTED`, and its metadata-only audit ledger is a sound design that this
repository does not need, because ours must record input and output for
executions it is accountable for.

## What would reopen this

1. A container runtime the platform may drive, or a separate host.
2. Fleet leaving experimental status **with** authorisation between tenants — or
   an owner decision that GalSen IA is single-user, which makes §9 not apply
   rather than pass.
3. `pnpm licenses list` in an environment allowed to install, closing the
   dependency `UNKNOWN`.
4. Confirmation that OpenClaw can be pinned to one adapter-owned provider.
5. A measured per-task session cost.

Even with all five closed, gate 10 stands on its own: thirteen of fourteen
capabilities already exist here.

## What this ADR does not decide

- **Whether to build a WhatsApp connector.** Recommended for costing; not
  authorised.
- **The five GalSen IA findings** the audit produced. They belong to
  `pending-work`.
- **Anything about other agent runtimes.** This decision is about OpenClaw,
  measured on 2026-08-19, at version `2026.8.1` / release `2026.8.1-beta.2`.
