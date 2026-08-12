# Open-Source Agent Foundations — Coding and Multi-Agent

VOLET 34, phase 2.1. Researched on the web on 2026-08-12; every claim carries its
source. Computer-use, desktop automation and MCP are phase 2.2 and are not
covered here.

The brief asks to *"analyze them, improve them, combine them, or replace them if
necessary"*. That is the right framing, and it needs one prior question answered
first, because it changes every recommendation below.

---

## 0. The question that decides everything: harness or library?

These projects are not comparable as a single list. They fall into two kinds:

- **Harnesses** — a complete running agent with its own loop, runtime and UI:
  OpenHands, Open Interpreter, OpenClaw. You *use* them.
- **Orchestration libraries** — a way to wire agents together: LangGraph,
  CrewAI, AutoGen. You *build* with them.

GalSen IA is already an orchestration layer. It has a router, an execution
planner, a workflow registry with validation, ten agents with bounded
delegation, a persistent audit trail, an approval gate, RBAC and per-subject
ownership (phase 1.1). **Adding a second orchestration library would be the
duplication this repository spent 951 lines removing last week** (ADR-016: one
design implemented twice, kept apart by two names).

So the honest conclusion is set before the comparison: **none of these six is a
dependency to adopt wholesale.** What is worth taking is patterns, and in one
case, a runtime.

---

## 1. OpenHands — the reference for the software-engineering part

**What it is.** A sandboxed runtime plus a small set of agent processes
(CodeAct, Browser, Planner) sharing a workspace. The agent is modelled as a pure
function from event history to next event, run in a loop. Its action vocabulary
is small and explicit: `CmdRunAction`, `IPythonRunCellAction`, `FileEditAction`,
`AgentFinishAction`. An `AgentController` supervises the loop and enforces
operational constraints — conversation iterations and **budget**.

**Numbers.** 77.6 % on SWE-Bench Verified with Claude 3.5 Sonnet Thinking on the
V0 harness; 72.8 % SWE-Bench Verified and 67.9 % GAIA with Claude Sonnet 4.5 on
the V1 SDK. Most agentic-coding research in 2025–2026 uses OpenHands as its
substrate — which matters more than the score: it is the thing other people
build on.

**What to take.**

1. **The controller that bounds the loop.** This is the finding of this phase,
   and it is not a compliment to OpenHands so much as a warning about our own
   plan — see §6.
2. **A sandboxed runtime by default**, not as an option. It runs as a Docker
   container locally or on a hosted runtime; the same code runs in-process or
   against a remote container farm depending on config. Chapter 08 should copy
   that shape: one interface, two implementations, sandbox as the default and
   not the upgrade.
3. **A small, closed action vocabulary.** GalSen IA's agents return a dictionary
   validated against a contract (`output_validation`, added this week). Naming
   the *actions* as explicitly as the *results* is the missing half.

**What not to take.** The whole platform. It is a coding agent product with its
own UI, conversation model and hosted runtime. Bolting it under GalSen IA would
put a second brain inside the platform, and the sovereignty question (ADR-014)
would be answered by its config file rather than by us.

## 2. Open Interpreter — the anti-pattern, and it is documented as such

**What it is.** A natural-language interface to a computer: an LLM writes code
and runs it locally. It has pivoted toward a desktop agent application with
integrated Word, Excel and PDF editors.

**Why it is the anti-pattern.** Generated code executes in the local
environment, where it can touch files and system settings — its own
documentation states the risk of data loss. It asks before each code block by
default, and offers a "safe mode" that scans code and packages. The published
reasons people leave it are precise: *security without strong sandboxes*,
*breaking changes*, and *no built-in memory or scheduled persistence*.

**What to take.** The confirmation that our order of work is right. GalSen IA
answers all three of those complaints already — the guarded editor gates every
write, memory is persistent, and the approval queue survives a restart. The one
idea worth borrowing is **package scanning before execution**, which belongs in
chapter 08 next to the sandbox.

## 3. OpenClaw — the most-starred, and the most-escaped

**What it is.** A self-hosted agent gateway: a long-running system managing
communication, session continuity, access control and agent execution across
WhatsApp, Telegram, Slack, Discord, Signal, iMessage and web chat. Reported at
**280 000+ GitHub stars**, overtaking React. Architecturally a *kernel-plugin*
design: a minimal Trusted Computing Base for memory, planning and execution
orchestration, plus a third-party plugin ecosystem. It distinguishes trusted from
constrained sessions, allowlists across several scopes, and runs tool executions
in hardened Docker sandboxes.

**And this is why it matters more than its star count.** In 2026 there is a
*literature* on breaking it: a published sandbox-bypass write-up from Snyk Labs,
data exfiltration from a vendor sandbox, and at least three arXiv papers on
threats, mitigation and governance of exactly this system.

**The lesson, and it is the most useful thing in this whole comparison: a
sandbox is a claim until someone has tried to escape it.** GalSen IA's chapter 08
must therefore ship with an escape test, not only with a sandbox. The Docker tool
here is disabled precisely because the obvious implementation — mounting the host
socket — hands out host root; that instinct is validated by what happened to a
project with 280 000 stars and a hardened design.

**What to take.** The trusted/constrained session distinction maps directly onto
something GalSen IA lacks: a *task* today inherits the caller's permissions
whole. And the minimal-TCB idea is worth stating explicitly for our own kernel.

## 4. LangGraph — the strongest library, and the one we must not add

**What it is.** Graph-based state machines with explicit control flow. Built-in
checkpointing with time travel. It passed CrewAI in stars in early 2026, driven
by enterprise adoption, because its architecture maps onto production
requirements: audit trails and rollback points.

**Why not adopt it.** Those two requirements — audit trail, rollback point — are
the ones GalSen IA already implements natively: a persistent audit event per
agent, per tool call and per request, retrievable by `request_id`; an approval
gate that suspends rather than fails; a workflow history. Adopting LangGraph
would mean either running two orchestrators or rewriting the platform's core
around a dependency, and ADR-014's sovereignty posture is not helped by putting
the control flow of a Senegalese platform inside a US vendor's framework.

**What to take.** **Checkpointing with time travel** is the one idea here that
GalSen IA genuinely does not have. Our audit trail records what happened; it
cannot resume a request from step 4. For long file-organisation or refactoring
runs — exactly what the brief asks for — being able to replay from a checkpoint
is the difference between an interrupted job and a lost one. That belongs in
chapter 13, and it is buildable on the audit trail we already persist.

## 5. CrewAI and AutoGen — both to be avoided as foundations, for different reasons

**AutoGen** popularised agents collaborating through structured conversation.
**Microsoft has moved it to maintenance mode** in favour of the broader Microsoft
Agent Framework. Building a long-term platform on a framework whose owner has
stopped developing it is a decision that ages badly by construction.

**CrewAI** models agents as a team with defined roles and is fast to build with.
Its own advocates place it as *"useful for internal prototypes where you want to
validate a multi-agent design before committing to a LangGraph
implementation"*, and note that **debugging stuck agents is painful and
observability is an afterthought**. GalSen IA's ten agents already exist with a
decision trace and per-agent durations; adopting CrewAI would trade an
observable system for a faster-to-write one.

**What to take from AutoGen.** One idea, and it is real: agents that *converse*
can correct each other. GalSen IA's agents share state through a blackboard and
never address one another. That is a deliberate simplification, and chapter 11
should decide whether it stays one.

---

## 6. The finding of this phase: our loop does not exist, and that is both a strength and a trap

OpenHands needs an `AgentController` enforcing iteration and budget limits
because its agent **loops until it emits `AgentFinishAction`**. GalSen IA's
router does not loop: it walks a declared pipeline once, in order, and stops.
Measured in the code — there is no `max_iterations` and no request budget
anywhere in `src/router/` or `src/agent/`, and none is needed today.

Two consequences, and the second is why this matters now:

1. **Today's safety is structural.** A declared pipeline cannot spin. That is a
   better guarantee than a cap, and it is free.
2. **The brief asks for "self-reflection and improvement loops".** The moment
   that lands, the structural guarantee is gone and a runaway loop becomes
   possible — one that can call tools, write files and spend money. **The
   controller with an iteration cap and a budget must ship in the same phase as
   the loop, never in the phase after.** Written here so that a later phase
   cannot quietly forget it.

`max_cost` already filters model selection per call, and delegation is bounded at
depth 3. Neither bounds a *request*.

---

## 7. Summary

| | Autonomy | Computer control | Coding | Memory | Multi-agent | Security | Local | Verdict for GalSen IA |
|---|---|---|---|---|---|---|---|---|
| **OpenHands** | loop + controller | sandboxed shell, browser | 72–78 % SWE-bench | workspace-scoped | 3 processes, shared workspace | sandbox by default | yes | **Patterns**: bounded controller, sandbox-as-default, closed action vocabulary |
| **Open Interpreter** | REPL, asks per block | local execution, broad | good on cheap models | **none built in** | no | **weak — its known flaw** | yes | **Anti-pattern**, plus one idea: scan packages before running |
| **OpenClaw** | long-running gateway | plugins, messaging channels | via plugins | session continuity | plugin ecosystem | TCB + allowlists + Docker, **documented escapes** | yes | **Pattern**: trusted vs constrained sessions. **Lesson**: test the escape |
| **LangGraph** | explicit state machine | none | none | **checkpoints + time travel** | graph | library-level | yes | **Do not adopt.** Take checkpointing |
| **CrewAI** | role pipeline | none | none | task outputs passed along | teams | library-level | yes | **Avoid** — observability is an afterthought |
| **AutoGen** | conversation loop | none | strong at generation | in-memory by default | conversation | library-level | yes | **Avoid** — maintenance mode. Take: agents that answer each other |

The 2026 consensus on what separates a production framework from a toy —
multi-model support, security as a first-class concern, stateful execution across
sessions, and observability — is worth quoting because **GalSen IA already has
all four**. That is the honest headline of this phase: the platform is not
behind these projects on the axes that are hard. It is behind on *hands*, which
is phase 2.2.

---

## Sources

- [OpenHands (GitHub)](https://github.com/OpenHands/openhands) ·
  [SWE-bench figures](https://tensorfeed.ai/harnesses/openhands) ·
  [architecture and finance-automation analysis](https://beancount.io/bean-labs/research-logs/2026/06/30/openhands-open-platform-ai-software-developers-generalist-agents) ·
  [self-hosting on Ollama or any provider](https://dev.to/lynkr/run-openhands-on-any-model-you-want-1mnd)
- [Open Interpreter safety documentation](https://docs.openinterpreter.com/safety/introduction) ·
  [2026 review](https://www.tooljunction.io/ai-tools/open-interpreter) ·
  [why users leave it](https://moclaw.ai/blog/open-interpreter-alternative-2026)
- [OpenClaw security architecture](https://nebius.com/blog/posts/openclaw-security) ·
  [sandbox bypass, Snyk Labs](https://labs.snyk.io/resources/bypass-openclaw-security-sandbox/) ·
  [sandbox data exfiltration](https://www.lasso.security/blog/sandboxed-ai-agents-attack-surface) ·
  [threat analysis and mitigation (arXiv)](https://arxiv.org/pdf/2603.11619) ·
  [security, privacy and ethical risks (arXiv)](https://arxiv.org/pdf/2605.23330)
- [LangGraph vs CrewAI vs AutoGen, 2026](https://dev.to/agdex_ai/crewai-vs-autogen-vs-langgraph-which-multi-agent-framework-in-2026-51m6) ·
  [benchmark comparison](https://tensoria.fr/en/blog/multi-agent-orchestration-comparison) ·
  [DataCamp comparison](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen)
- [2026 framework landscape](https://blog.jetbrains.com/pycharm/2026/06/top-agentic-frameworks-for-building-applications-2026/) ·
  [open-source agent frameworks](https://www.firecrawl.dev/blog/best-open-source-agent-frameworks)
