# ADR-017: The Computer Agent Is Tools and a Gate, Not a New Architecture

## Status
Accepted

## Date
2026-08-12

## Context

The brief of 2026-08-12 asks for an agent that operates a real computer: sees the
screen, drives applications, navigates drives, organises files, understands and
improves codebases, runs commands, and proposes improvements unprompted.

Two measured phases precede this decision.

**Phase 1.1** — what this repository already does, measured by running it. Four
of the brief's fourteen capabilities are present, four partial, six absent. The
four present ones are permissions, the approval gate, the audit trail and
per-subject ownership: the hardest to retrofit, and the reason the missing six
can be built without producing a tool that erases a drive on a bad inference.

**Phases 2.1 and 2.2** — what the open-source field offers, web-sourced. The
finding that shapes everything below: **the six frameworks split into harnesses
you use and libraries you build with**, and GalSen IA is already a library-shaped
orchestrator — router, execution planner, workflow registry with validation, ten
agents with bounded delegation, persistent audit, approval gate, RBAC.

The temptation the brief invites — *"replace them if necessary"* — is to adopt
one of them as the foundation. That is the decision this ADR refuses, and the
reason is not sentiment about existing code.

## Decision

### 1. GalSen IA stays the orchestrator. No second framework is adopted.

LangGraph's two selling points for production are audit trails and rollback
points. This repository implements both natively: an audit event per agent, per
tool call and per request, retrievable by `request_id`, and an approval gate that
suspends rather than fails. Adopting it would mean running two orchestrators or
rewriting the core around a dependency — the duplication ADR-016 cost 951 lines
to remove, taken on deliberately this time.

AutoGen is in maintenance mode. CrewAI's own advocates place it before a
LangGraph implementation, and its observability is an afterthought. Neither is a
foundation for a platform meant to last.

**What is adopted instead is patterns**, each named with its origin:

| From | Pattern |
|---|---|
| OpenHands | a controller that bounds the agent loop; sandbox as the default, not the option; a small closed action vocabulary |
| LangGraph | checkpointing, so a long run resumes instead of restarting |
| OpenClaw | trusted vs constrained sessions; a minimal trusted computing base |
| Open Interpreter | scan packages before executing them |
| AutoGen | agents that can address each other, not only share a blackboard |

### 2. What is missing is **hands**, and hands are tools

This is the decision the whole VOLET turns on. The absent capabilities — sight,
GUI control, a real browser, a sandbox, MCP, a repository map — are **not an
agent architecture**. They are tools, in the sense this platform already has
nineteen of: declared in `tools.yaml`, loaded by the registry, callable by any
agent, audited per call.

So no new runtime, no new agent loop, no parallel execution path. `ScreenTool`,
`GUITool`, a Playwright-backed `BrowserTool`, `SandboxTool`, `RepoMapTool` join
the catalogue and inherit, for free, everything the catalogue already enforces.

An architecture that has to be extended to gain a capability is the wrong
architecture. This one does not.

### 3. Perception is accessibility-first; pixels are a declared fallback

A screenshot agent sends an image of the user's screen to a model. ADR-014 exists
to refuse exactly that. Measurement agrees independently — under 100 ms and
nothing leaving the machine, against 2–5 seconds per step — but the sovereignty
argument decides it alone.

### 4. An action must be able to name its target

The approval gate must be able to say *what* will be clicked. `click at
(412, 380)` is a mystery to approve, and an approval a human cannot evaluate is a
rubber stamp with a log entry.

Therefore: **every GUI action carries element identity** — role, label, bounds —
or it is refused. This rules out pixel-coordinate automation as a base, and it is
a requirement no benchmark in the field produces. It comes from our own gate.

### 5. No new execution power ships without its escape test

OpenClaw has 280 000 stars, a minimal-TCB design, allowlists and hardened Docker
sandboxes — and a published literature on escaping it. The lesson is not that
sandboxes are useless; it is that **a sandbox is a claim until someone has tried
to escape it**.

The Docker tool here is disabled because the obvious implementation hands out
host root. Its replacement (chapter 08) ships with tests that attempt escape, and
it ships **before** the executable allowlist is widened. Today six executables and
one confined root are the only thing between an agent and the host.

### 6. MCP: server before client

Tool poisoning — malicious instructions in tool *metadata* — is documented as the
most prevalent and impactful client-side MCP vulnerability. Becoming a client
loads other people's tool descriptions into our prompt. Becoming a server keeps
the risk ours to authenticate, authorise and audit, and puts a Senegalese
platform in the position of being called rather than calling.

The client comes second, pinned and narrow: no dynamic discovery, tool metadata
treated as untrusted input.

### 7. If a reflection loop is added, its bound ships in the same phase

The router does not loop; it walks a declared pipeline once. Runaway is
structurally impossible today, which is a better guarantee than a cap and costs
nothing. The brief asks for self-reflection loops. **The day one lands, the
guarantee is gone** — and the iteration cap and request budget must land with it,
not in the phase after. A test fails if a loop appears in the router.

### 8. Every capability degrades to a stated refusal

No provider answers today (criterion C1). Everything in this VOLET reports its
unavailability rather than returning a plausible answer — the rule the platform
already applies everywhere, and the reason its capabilities can be trusted when
they do answer.

## What this ADR does **not** decide

**The sovereignty question.** The brief asks for cloud/local switching; ADR-014
refuses third-party providers by default. Changing that is the owner's decision,
it is chapter 04, and nothing here presumes its outcome. Point 3 above holds
under every option: even with cloud models allowed, sending a continuous stream
of screen images to a third party is a different decision from sending text, and
would need its own.

## Consequences

- Five new tools, no new runtime. Each inherits the gate, the audit trail, RBAC
  and ownership by being a tool.
- Chapter order is fixed by point 5: sandbox before wider execution.
- Chapter 09 delivers a server before a client.
- Checkpointing is added to the audit trail rather than adopted with a framework.
- The platform gains no dependency on any of the six projects compared. It gains
  Playwright (declared, weighed) and one accessibility library per platform.

### Accepted cost

Patterns copied from OpenHands are copied, not imported: we maintain them. That
is the price of not putting a second brain inside the platform, and it is the
same price ADR-003 accepted for model providers.

## References

- `docs/architecture/personal-agent-assessment.md` — phase 1.1, measured
- `docs/architecture/agent-foundations-comparison.md` — phase 2.1, sourced
- `docs/architecture/computer-use-comparison.md` — phase 2.2, sourced
- ADR-003 (providers), ADR-006 (approval gate), ADR-010 (identity),
  ADR-014 (sovereignty), ADR-016 (one design, not two)
- `docs/roadmap/VOLET_34.md` — the chapter plan this decision serves
