# ADR-039: The chat writes, and grounding stays separate from writing

## Status

**Accepted** — 2026-08-23. Implemented in `src/chat/`, `src/api/server.py`,
`agents/planner/agent.py`, `src/router/decision_trace.py`.

## Date

2026-08-23

## Context

Measured on 2026-08-23, before any change: `POST /chat` returned the identical
text, word for word, for *« bonjour »* and *« Qui était Albert Einstein ? »* —
the researcher's three gaps.

The cause was narrower than it looked. Tracing `RouterEngine._dispatch_agent`
on real calls showed only two agents ever ran, `planner` and `researcher`, and
that **nothing in the chain writes**. Between the agents' structured results
and `ChatResponse.answer` sat one function that *renders data*. No agent, no
workflow, no module turned a context into a sentence.

Two things the diagnosis got wrong, and both were corrected by measurement
rather than assumed:

- **The general-purpose routing already existed.** The `question` workflow
  carries `agent_selection: planner`; five global questions selected the
  researcher alone, three Senegalese ones added `senegal`. Senegal was already
  a speciality.
- **The planner already called the model**, and failed honestly:
  `model_assisted: {status: unavailable, reason: "Aucun modèle enregistré…"}`.

## The decision

### 1. A response layer is a stage, not an architecture

`src/chat/` receives an assembled context and returns text. It fetches nothing,
calls no tool, opens no connection. It follows ADR-017's precedent — *the
computer agent is tools and a gate, not a new architecture* — and ADR-014's
constraint: it calls `ModelManagerImpl` and nothing else, so it holds no client,
knows no URL and names no provider.

Being a pure composer is what makes it testable on a machine with **zero models
registered**, which is this one. A component that cannot be exercised here is a
component that cannot be exercised at all.

### 2. Writing never grounds

Grounding is computed from the agents' evidence **before** generation and is
never touched by it. A fluent model does not make an answer sourced.

`ChatResponse` gains `generated`, true only when a model produced the text.
Without that field a refusal composed by the platform would be
indistinguishable from an answer — the exact lie this repository refuses
everywhere else.

### 3. Evidence keeps its origin all the way into the prompt

Each item enters marked `VERIFIED` or `UNVERIFIED` with its `scope`, never
melted into a paragraph that would read as the platform's own words. This
follows **ADR-019**, which refused a global base and a Senegalese one because
*a question about millet in Kaolack needs both halves*. The layer therefore
never receives "global evidence" or "Senegalese evidence": it receives what
exists, each piece carrying its scope.

`senegal` elements enter verified because the corpus requires a source, not
because it is convenient. The researcher's findings carry their own flag.

### 4. Machinery stays out of the prompt

No plan, no task list, no timings. A model given machinery writes an execution
report instead of an answer.

### 5. A deliberately empty plan is a plan

`recommended_agents()` already distinguished *"the planner did not run"* from
*"it mobilised nobody"* — its docstring says **deciding to mobilise nobody is a
decision, not deciding is not one** — and `selection_appliquee()` collapsed the
distinction one function later with an or-None expression.

The distinction is restored, not invented. Three cases now: `None` keeps the
declared pipeline, a recommendation naming only undeclared agents keeps it, and
an empty list runs nobody.

This is what lets a `conversation` intent exist. Measured: *« bonjour »* went
from **1 092 ms to 77 ms**, with only the planner running.

### 6. A failure is classified, not quoted

The route returns a short enumerated reason. It does not return the provider's
prose, which was measured carrying `http://localhost:11434` — a host and a port
handed to any API caller. The whole cause is kept in `failure_detail`, logged,
never returned; `/health` is where an operator reads provider state.

## Consequences

**What this buys.** The platform can hold a conversation. A general question
gets a general answer; a Senegalese question activates the speciality; a
greeting costs 77 ms instead of a research pass that could never succeed.

**What it costs.**

- A turn now includes a model generation, so it is longer. The Linux audit
  measured `/health` going from 3.5 ms to 1 149 ms during a `/chat` because
  blocking work runs on the event loop. **Adding generation makes that worse**,
  and its recommendation P10 — three call sites — is markedly more urgent than
  before.
- `ChatResponse` gains two fields. Additive, but public.
- One existing test changed: it asserted an empty recommendation behaves as
  `None`. That was right while nothing could produce an empty recommendation;
  the `conversation` intent created the missing case. Updated with its
  reasoning, and the deliberate fallback it guards is still asserted.

**What is deliberately not done.**

- **The coding capability is not reached.** The intent is now
  `implementation` recommending `coder`, but the `question` workflow does not
  declare `coder`, so the recommendation is unusable. Wiring a chat message to
  an agent that writes files is an operator decision under §19 of the brief,
  not a detail. A test pins the current state and will fail the day it changes.
- **A verified researcher finding does not ground a Senegalese question whose
  national base is empty.** The `senegal` agent's verdict wins, which is
  defensible — it is the authority on national scope. Recorded and pinned by a
  test; changing it needs a decision.

## What stays UNKNOWN

Everything that needs a model to answer. This machine registers **zero models**,
measured after full application startup, so the whole chain is verified with a
simulated provider and these remain unmeasured:

- the quality of real answers;
- real latency with a real model;
- the behaviour of fallback between providers.

They become measurable the day an operator runs a model. Nothing in this ADR
claims otherwise.
