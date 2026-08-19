# GalSen IA — Spec-driven development governance

Established by the project owner on 2026-08-19. **Permanent.**

This rule sits above the assistant's judgement about *what to build*. The other
rules govern how work is done; this one governs **what work is allowed to
exist**.

---

# The primary rule

**The user's explicit request is the functional authority.** The pipeline is:

```
REQUEST → UNDERSTAND → CLARIFY IF NEEDED → SPECIFY → PLAN → TASKS
        → IMPLEMENT → VERIFY → REPORT
```

and never:

```
REQUEST → SPECULATE → INVENT EXTRA PRODUCT → IMPLEMENT WHAT NOBODY ASKED FOR
```

**A possible improvement is not a requirement.** The two words that must never
merge are *useful* and *requested*.

---

# What may never be added on the assistant's own initiative

Features, models, agents, APIs, databases, services, user workflows, UI systems,
providers, business logic, dependencies, architectural layers.

Two exceptions, and only two:

- **A.** it was explicitly requested;
- **B.** it is strictly necessary for the requested feature to function.

Anything else that looks worthwhile is recorded as:

```
OPTIONAL SUGGESTION — NOT IMPLEMENTED
```

**An optional suggestion never quietly becomes a task.** Only *required* missing
work may turn into an implementation task; `OPTIONAL`, `UNKNOWN` and `BLOCKED`
stay outside the current scope.

---

# Understand before building

Answer these before writing anything:

- What is requested, and why?
- Which existing component should handle it?
- What can be reused?
- What is strictly necessary?
- What is explicitly out of scope?

**When a request is ambiguous and the ambiguity materially changes the
implementation, ask.** Do not pick one of several materially different readings
and proceed as though it were the only one.

---

# Four conversions that are forbidden

| Never turn | into |
|---|---|
| `OPTIONAL` | `REQUIRED` |
| `UNKNOWN` | a fact |
| `POSSIBLE` | implemented |
| `DESIRABLE` | requested |

`UNKNOWN` stays `UNKNOWN`. Capabilities, benchmarks, compatibility, performance,
licences, provider support, model quality and test results are never invented —
this repository already enforces that everywhere else, and this rule states it
as policy rather than as habit.

---

# Every specification carries its own boundary

Three sections, always:

- **IN SCOPE** — exactly what will be implemented.
- **OUT OF SCOPE** — what will not.
- **OPTIONAL FUTURE IDEAS** — informational only, generating no task.

---

# Existing architecture has priority

Work happens **inside** GalSen IA's architecture, never beside it. These stay
authoritative: provider abstraction, orchestration, provenance, security,
privacy, consent, verification, memory, `WorldState`, reference entities,
creative representation, model routing, the provider registries, self-healing,
testing.

**Prefer reuse over rebuild.** A working component is not replaced because
another approach looks cleaner.

**If a proposed change conflicts with an existing architectural rule: stop,
document the conflict, and do not silently override it.**

---

# No helpful unrequested changes

No opportunistic refactoring, unrelated cleanup, architecture rewrites,
dependency migrations, UI redesigns, naming migrations or database migrations —
unless the requested feature requires them.

**An unrelated problem found along the way is reported, not silently fixed**,
unless it blocks the requested work or the user authorises the fix.

---

# Task discipline

Every task maps to a requirement, a technical necessity, or a required
verification step. **A task that cannot be justified is removed.** Tasks are
never created to make a project look more complete.

---

# When implementation hits a technical problem

Do **not** redefine the feature quietly. Instead:

1. document the problem;
2. identify the possible solutions;
3. determine whether any of them changes scope;
4. if scope changes materially, **stop**;
5. ask for authorisation or clarification.

---

# Research does not authorise implementation

Research is allowed whenever it is needed. It ends at:

```
RESEARCH → EVALUATE → DOCUMENT → COMPARE → RECOMMEND
```

not at `INSTALL → INTEGRATE → MODIFY ARCHITECTURE`, unless explicitly authorised
or strictly required by the approved feature.

---

# Security is never overridden

No specification, plan, task or model output may authorise breaking security
policies, authentication, authorisation, secrets management, sandboxing,
provenance, privacy, consent, or any immutable safety boundary.

---

# The scope audit, at the end of every phase

Compare **request vs spec vs plan vs tasks vs implementation**, and look for:

- missing requirements;
- **extra implementation**;
- contradictory behaviour;
- undocumented changes;
- accidental scope expansion.

The target is `IMPLEMENTATION ≈ APPROVED SPECIFICATION`, never
`IMPLEMENTATION > SPECIFICATION`.

---

# Verification, and the report

`.claude/rules/post-integration-validation.md` defines the regression pass and
stays in force unchanged. This rule adds the **scope** half of the same gate.

After any feature, phase or integration, verify that:

1. the requested feature works;
2. existing functionality still works;
3. no test was removed or weakened;
4. no unrelated functionality was modified;
5. **no unauthorised feature was added**;
6. no security boundary was weakened;
7. no credential or secret was introduced;
8. no unnecessary dependency was introduced;
9. existing APIs remain compatible unless explicitly authorised;
10. documentation matches the actual implementation.

The final report names, in order: requested objective · scope implemented ·
files created · files modified · components reused · new components · tests run,
passed, failed, skipped · regression status · security status · dependency
changes · **scope audit** · unimplemented requirements · `UNKNOWN` items · known
limitations · **optional suggestions not implemented** · next authorised step.

**Never say "complete", "stable" or "production ready" without the verification
that supports it.**

---

# In one line

Think widely. Understand deeply. Plan precisely. **Implement only what is
authorised.** Verify everything. Do not invent, do not expand scope, and do not
turn suggestions into requirements.
