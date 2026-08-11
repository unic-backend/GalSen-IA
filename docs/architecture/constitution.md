# The constitution, measured

What VOLET_01 requires of every component, and whether the code enforces it. Measured
against the repository on 2026-08-11.

This is the only VOLET that never had a phase plan, and the last one of the series. It is
also the one the rest of the work was, without saying so, an audit of: twenty-two VOLETs
spent finding capabilities that reported success without doing the work — which is
chapter 02's first honesty rule, broken.

---

## Chapter 03 — "AI assists. Humans decide."

The chapter's final rule: *no feature may be implemented if it removes meaningful human
control over important decisions.*

The mechanism exists. `BaseAgent.approval_required` suspends an action in
`requires_approval` and submits it to the approval engine (ADR-006); if the gate is
unavailable the action **fails** rather than proceeding, which is the right way round.

**No agent sets it.** Measured across the nine shipped agents: `approval_required = False`
everywhere.

And that is currently correct, which is the part worth stating carefully. The nine agents
read, analyse and report. Every tool call they make is read-only:

```
filesystem.read, filesystem.search, filesystem.list, filesystem.stat,
filesystem.exists, git.summary
```

Nothing writes, deploys, or sends. The `deployment` agent evaluates readiness; it does not
deploy. So the gate is not idle because it was forgotten — it is idle because nothing yet
needs it.

**What was missing is what keeps it that way.** `approval_required` defaults to `False`, so
the first agent that calls a mutating tool gets no gate, and nothing says so.
`tests/test_constitution_human_control.py` makes the chapter's final rule executable: it
scans every agent's tool calls, and fails if a mutating operation appears on an agent that
has not declared the gate. Verified to fail on a deliberately faulty agent.

A second test locks the measurement itself, so the rule cannot pass green for the wrong
reason — if the agents stopped calling tools altogether, the first test would be vacuously
satisfied.

Reading is deliberately exempt. Requiring human approval to read a file would get the gate
switched off within a day, and a control that gets switched off protects nothing.

## Chapter 02 and 04 — honesty, and "prefer saying I don't know"

> Never fabricate facts. Never claim certainty without evidence. Admit limitations clearly.
> When reliable evidence is unavailable, GalSen IA must prefer saying "I don't know".

This is the standard the whole series was measured against, and the repository failed it
repeatedly before this session. The record, from `completed-work.md`:

- "sent" named e-mails nobody received
- a search that answered "no results" with no source wired
- an empty workflow reporting `success`
- an agent counting 72 test suites it never ran
- four tests pinning fabricated values, including a calendar tool inventing meetings
- an alert raised by an agent invisible on the route the user reads

Each was fixed the same way: the capability now reports its real state — a 503, a `failed`
status, a `NotImplementedError`, or an `unavailable` block naming what cannot be computed
and why. That last pattern is the constitutional "I don't know", made structural: it exists
now in `/analytics`, `/search/status`, `/security/threats`, `/metrics`,
`quality_report()` and `delivery_report()`.

The rule that keeps it is `.claude/rules/verification.md` — *an unfinished capability
reports a status; it never returns a plausible answer* — and it is enforced by tests, not
by intention.

## Chapter 07 — quality standards

Measurable, and measured: 2 022 tests pass, 7 skipped. Performance targets exist
(`docs/standards/performance.md`) and `scripts/release_check.py` checks them. Every route
requires authentication except four named exceptions, and a test enumerates them.

## What the constitution asks and the platform still does not do

- **Confidence levels** (ch. 03, auditability): the approval gate carries
  `approval_confidence`, but nothing else records a confidence with a recommendation —
  because nothing else makes recommendations. It becomes real the day C1 is met.
- **Source hierarchy** (ch. 04): the knowledge engine has domains, sensitivity and
  traceable sources, but the four-level priority the chapter defines is not modelled, and
  the base is empty, so nothing exercises it.
- **Human verification for critical decisions** (ch. 03): no medical, legal or financial
  path exists to gate. Building the gate before the path would be the same fabrication in
  the other direction.

None of these got a placeholder. They are named here so the next person does not have to
re-derive that they are missing.
