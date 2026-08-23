# The final response layer — contract

**Status: IMPLEMENTED.** `src/chat/`, wired into `POST /chat`. Decision
recorded as **ADR-039**.

This document defines what the layer receives, what it returns, what it may
never do, and how it fails. It was written as a contract before any code, and
the sections below are unchanged from that contract except where measurement
corrected them — the corrections are marked where they happened rather than
edited away.

**The flow, as it actually runs:**

```
POST /chat
  → RouterEngine.process_request(workflow_id="question")
      → planner            (intents, axes, agent selection)
      → the agents it selected, or none at all
  → _ancrage_de()          grounding, computed HERE, before any generation
  → _contexte_de_reponse() message · history · axes · evidence · agent notes
  → RedacteurConversation.rediger()
      → construire_invite()
      → ModelManagerImpl.generate_text_with_fallback()   [async bridge]
      → on failure: composer_sans_modele()
  → ChatResponse(answer, grounding, generated, generation_unavailable, …)
```

---

## 1. Why a new component, and the search that justified it

Section 7 of the brief requires searching before creating. Measured 2026-08-23:

| Searched for | Found |
|---|---|
| A conversational responder | **Nothing.** No module turns a context into a sentence |
| Generation call sites | 3 — `src/agent/context.py:860`, `src/api/server.py:1433` (`/model/generate`), `src/tools/agri_advice/tool.py:126` |
| Response utilities | `src/model_engine/response_validator.py`, `response_ranker.py` — they judge a response, they do not compose one |

**A new component is justified.** It is a *stage*, not an architecture —
following ADR-017's precedent: *"The Computer Agent Is Tools and a Gate, Not a
New Architecture."*

## 2. What the ADRs impose on it

| ADR | Constraint on this layer |
|---|---|
| **ADR-014** — sovereignty | *"No request leaves the platform to a third-party model, ever."* The layer calls **`ModelManagerImpl` only**. It opens no socket, holds no API client, knows no provider name. |
| **ADR-022** — one orchestrator | Work goes through `RouterEngine`. The layer is reachable **inside** the orchestration path, never beside it. |
| **ADR-017** — no second framework | No new routing, no new model selection, no new provider abstraction. |
| **ADR-019** — one base, two axes | **The decisive one, and the brief misses it.** |

### ADR-019 changes the brief's framing, and is right

The brief (§9, §10) reads as a switch: general questions go one way, Senegalese
ones go another. ADR-019 refused exactly that design:

> *"A question about millet in Kaolack needs both halves: the agronomy of pearl
> millet, which is global, and the varieties, rainfall and prices of Senegal,
> which are not. Two bases force the retriever to pick one before it knows what
> the answer needs — and the failure is silent, because whichever base it picks
> returns something."*

**So the response layer must never receive "global evidence" *or* "Senegalese
evidence". It receives whatever evidence exists, each piece carrying its own
`scope`, and it composes one answer that says which passage came from where.**

The brief's intent is honoured — Senegal is not forced — but by the axis that
already exists rather than by a branch that would have to be invented.

## 3. Inputs

The layer receives one structured object. Nothing is fetched by the layer
itself: it is a **pure composer**, which is what makes it testable without a
model and without a network.

| Field | Source | Why it is there |
|---|---|---|
| `message` | the user | the question actually asked |
| `history` | `/chat` request, truncated | conversation continuity (§15) |
| `axes` | `planner.axes` | `domain`, `task_type`, `complexity`, `risk`, `freshness`, `language`, `geographic_scope` — **already computed**, never recomputed |
| `evidence` | agent results | each item carries `content`, `source`, `scope`, `verified` |
| `agent_notes` | agent results | refusals and gaps, e.g. `senegal.empty_base` |
| `grounding` | computed before the call | `GROUNDED` / `UNGROUNDED` / `NOT_CHECKED` — **reaches the prompt**, so the model knows when it answers from its own knowledge |

**Not every internal result is passed** (§8). An agent's plan, its task list and
its timing are machinery, not evidence.

## 4. Output

```
answer            : str            — the text shown to the user, never empty
model_used        : str | None     — always None today, see §13
generated         : bool           — True only if a model produced the text
failure_reason    : str | None     — why generation did not happen
elapsed_seconds   : float          — measured, never 0.0 by default
```

`generated` exists so no caller can mistake a composed refusal for a model
answer. **It is the field that keeps this layer honest.**

## 5. The async boundary — decided

`generate_text_with_fallback` is `async`; the orchestrator is synchronous.
**`AgentContext._run_async()` (`src/agent/context.py:1233`) already solves
this**, and already handles the case where a loop is running by moving the
coroutine to a dedicated thread.

**Decision: reuse it. Do not write a second bridge.** Cost if wrong: a blocked
event loop in the platform's hottest route — and the Linux audit already
measured `/health` going from 3.5 ms to 1 149 ms under exactly that condition.

## 6. What the layer may never do

- **Never claim grounding.** Grounding is computed from evidence *before*
  generation. A model producing fluent text changes nothing about whether the
  claim is sourced (§12).
- **Never invent a source, a tool result, or a search that did not happen.**
- **Never present unverified external text as verified.** `verified: False`
  travels into the prompt and must survive into the answer.
- **Never expose `planner`, `researcher`, `senegal`, `verifier`** as machinery
  (§11). The user asked a question, not for a build log.
- **Never gain a permission.** Composing text is not authorisation to execute a
  tool (§19). The layer receives evidence; it calls nothing but the model.
- **Never fabricate on failure.** No model → a stated refusal, not a guess (§14).

## 7. Failure modes, and what each returns

| Situation | `answer` | `generated` | `failure_reason` |
|---|---|---|---|
| A model answers | its text | `True` | `None` |
| No model registered | the composed evidence, or a stated refusal | `False` | `"no model available"` |
| Generation raises | the composed evidence, or a stated refusal | `False` | the real cause, redacted |
| Evidence exists, no model | the evidence, attributed | `False` | `"no model available"` |
| No evidence, no model | *"I have nothing to answer this with"* + what would settle it | `False` | `"no model available"` |

**The last row is the current behaviour**, and it is kept — it is the honest
floor the platform already stands on. What changes is that it stops being the
*only* behaviour.

## 8. What this contract deliberately leaves open

- **Whether a greeting skips the research pipeline** (§9). It is an
  orchestration decision, not a response-layer one, and it belongs to
  chapter 03. Flagged for the owner.
- **Whether `NOT_CHECKED` lets the model answer from its own knowledge** (§12
  says yes). This is a change of posture for a platform that has refused to
  answer without a source. Flagged for the owner.

---

## 9. What the routing already does — measured, not assumed

Chapter 03. The eight examples below are **the brief's own**, run through
`RouterEngine.process_request(workflow_id="question")` on 2026-08-23.

| Message | Agents selected | `geographic_scope` |
|---|---|---|
| Bonjour | `['researcher']` | global |
| Qui était Albert Einstein ? | `['researcher']` | global |
| Explique Linux. | `['researcher']` | global |
| Écris une fonction Python qui trie une liste. | `['researcher']` | global |
| Compare Python et Rust. | `['researcher']` | global |
| Quelles sont les régions du Sénégal ? | `['researcher', 'senegal']` | **country** |
| Donne-moi un conseil sur l'agriculture sénégalaise. | `['researcher', 'senegal']` | **country** |
| Quel est le prix du ciment à Dakar ? | `['researcher', 'senegal']` | **country** |

**Five global out of five, three Senegalese out of three.** Sections 9 and 10 of
the brief ask for exactly this behaviour, and it is already the behaviour.

**Conclusion: the Senegal agent is already a specialization.** Nothing in this
VOLET needs to make it one. That part of the brief is `ALREADY COVERED`, and
saying so is worth more than implementing it twice.

## 10. The two routing gaps that are real

The same measurement exposes what the table above hides, on the `task_type`
axis:

| Message | `task_type` | `research_required` |
|---|---|---|
| Bonjour | `['research']` | **True** |
| Explique Linux. | `['research']` | True |
| Écris une fonction Python… | `['research']` | True |
| Corrige ce bug dans mon code. | `['quality']` | True |

**Gap 1 — a greeting runs a full research pass.** « Bonjour » is classified
`research`, and chapter 01 measured what that costs: **1 095 ms** in the
researcher, searching for evidence about a greeting, finding none, every time.
Section 9 names this: *"Do not unnecessarily launch the full research pipeline
for simple conversation."*

**Gap 2 — asking for code is classified as research.** *« Écris une fonction
Python »* lands on `research`, identical to *« Explique Linux »*. The platform
has a `coder` agent and an entire coding engine, and neither is reached. Only
*« Corrige ce bug »* moves the axis, and only to `quality`.

### The smallest correct fix, and where it belongs

Both gaps live in **one place**: the planner's intent detection. Neither needs a
new router, a new axis or a branch in `/chat`.

- A `conversation` intent, recognised before `research`, whose selection is
  **no agent at all** — the response layer answers from the message and the
  history alone.
- The existing `coding` capability reached when the intent is to *write* code,
  not only to fix it.

**Both are orchestration changes, made inside the planner**, which is what
ADR-022 requires: *"unattended work uses the same orchestrator as a person's
request"*, and a person's request is no different.

### Scope, stated rather than assumed

The plan gave chapter 03 two phases for design and **no implementation slot**.
Rather than silently add phases, the two planner changes are folded into
chapter 05, which already touches the `/chat` path — and they are named here so
the scope audit at the end can check them.

**What is *not* in scope**: making the planner good at intent detection in
general. Two named intents, measured before and after, and nothing more.

---

## 11. What was measured after implementation

| Case | Measured 2026-08-23 |
|---|---|
| *« Bonjour »* | **1 092 ms → 77 ms**, only the planner runs |
| *« Merci ! »* | 2 ms |
| A general question with a model | generated answer, grounding stays `UNGROUNDED` |
| Generations per turn | **1** |
| Models registered on this machine | **0** — the chain is verified with a simulated provider |
| Full suite | **7 148 passed, 9 skipped, 0 failed** |

## 12. The two questions section 8 left open — answered

**A greeting skips the research pipeline.** Not by a branch in `/chat` but by a
`conversation` intent that mobilises no agent, and by restoring the distinction
`selection_appliquee()` had collapsed. The orchestrator is not bypassed; it is
given a plan that names nobody.

**`NOT_CHECKED` lets the model answer from its own knowledge.** The prompt says
so explicitly, and `generated` plus the grounding chip keep the two apart in the
response. This is the change of posture the contract flagged, and ADR-039
records it.

---

*Implemented. See ADR-039 for the decision and its cost.*

---

## 13. What the self-review of this diff found

Section 19 of the follow-up brief asks for a review of one's own changes. It
found three things, and the third is the one worth remembering.

**A dead property.** `constats_non_verifies` was defined and read nowhere.
Removed.

**A field written and never read.** `grounding_status` travelled into the
context and stopped there. A field nobody reads is a promise nobody keeps — so
it now reaches the prompt, which is what §12 wanted anyway: the model is told
when nothing is verified, and instructed to say so rather than to sound sourced.

**A guess wearing the clothes of a measurement.** `_modele_utilise()` returned
the engine's first active model, while its own docstring claimed it returned
`None` rather than a guessed name. `generate_text_with_fallback()` tries
candidates in order and returns a string: *which* model answered is nowhere in
its return value. The first of the list is therefore wrong precisely when the
fallback was used — the only case where the question is interesting.

`model_used` is now always `None`, and the function says why. **A guessed name
is worth less than no name: it reads as a measurement.** What would settle it:
the engine returning the chosen model alongside the text.

Three tests pin all three.
