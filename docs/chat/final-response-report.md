# `/chat` produces a real answer — final report

VOLET *« CHAT — RÉPONSE FINALE RÉELLE »*, owner's brief 2026-08-23.
11 chapters, 19 phases. The twelve points of §24, in order.

---

## 1. Confirmed root cause

The brief's diagnosis was **directionally right and wrong in two specifics**,
and measurement settled all three.

Traced by instrumenting `RouterEngine._dispatch_agent` on real `/chat` calls:

| Message | Agents actually executed |
|---|---|
| *« bonjour »* | `planner` 114 ms · `researcher` **1 095 ms** |
| *« Qui était Albert Einstein ? »* | `planner` 3 ms · `researcher` **1 071 ms** |

**Confirmed:** nothing in the chain wrote. Between the agents' structured
results and `ChatResponse.answer` sat `_texte_de_reponse()`, which *renders
data*. No agent, no workflow, no module turned a context into a sentence.

**Corrected — the general-purpose routing already existed.** The `question`
workflow carries `agent_selection: planner`. Measured on the brief's own eight
examples: five global questions selected `researcher` alone, three Senegalese
ones added `senegal`. §9 and §10 asked for behaviour that was already there.

**Corrected — the planner already called the model**, and failed honestly:
`model_assisted: {status: unavailable, reason: "Aucun modèle enregistré…"}`.

**The symptom the brief did not name**, and the one the owner actually saw:
`_texte_de_reponse()` falls back to the researcher's gaps whenever it found
nothing — which on this machine is *every* question. Hence *« bonjour »* and
*« Qui était Albert Einstein ? »* returning **the identical answer, word for
word**.

## 2. Files changed

16 files, **+2 129 / −127** — measured before this report was itself committed.

| File | Δ | What |
|---|---:|---|
| `src/chat/response.py` | +426 | The layer: context, prompt, responder, honest floor |
| `src/chat/__init__.py` | +25 | Public surface |
| `src/api/server.py` | +105 −2 | Context builder, wiring, two response fields |
| `agents/planner/agent.py` | +48 −2 | `conversation` intent, code-writing keywords |
| `src/agent/context.py` | +29 −13 | Async bridge extracted, behaviour unchanged |
| `src/router/decision_trace.py` | +25 −4 | Three-way distinction restored |
| `tests/test_chat_general_purpose.py` | +567 | The brief's matrix, A to J |
| `tests/test_api_chat.py` | +197 | Context, grounding invariant, failure, memory |
| `tests/test_orchestration_claims.py` | +27 −1 | The changed test, with its reasoning |
| `docs/…` (6 files) | +678 −77 | ADR-039, contract, memory, changelog, CLAUDE.md |

No `requirements` file touched. No unrelated file changed.

## 3. The new `/chat` architecture

```
POST /chat
  → RouterEngine.process_request(workflow_id="question")
      → planner            intents · axes · agent selection
      → the agents it selected — or none at all
  → _ancrage_de()          grounding, computed HERE, before any generation
  → _contexte_de_reponse() message · history · axes · evidence · agent notes
  → RedacteurConversation.rediger()
      → construire_invite()
      → ModelManagerImpl.generate_text_with_fallback()   [sync→async bridge]
      → on failure: composer_sans_modele()
  → ChatResponse(answer, grounding, generated, generation_unavailable, …)
```

`src/chat/` is a **stage, not an architecture** (ADR-017's precedent). It
fetches nothing, calls no tool, opens no connection.

## 4. How `ModelManager` is connected

Through **`ModelManagerImpl`**, injected — the platform's shared instance, the
one `/model/generate` already uses. The layer builds no manager, holds no
client, knows no URL, names no provider. That is ADR-014 (*no request leaves the
platform to a third-party model, ever*) enforced by construction rather than by
discipline.

Two details worth recording:

- `generate_text` and `generate_text_with_fallback` are **`async`**; the
  orchestrator is synchronous. **No second bridge was written**:
  `AgentContext._run_async` never used `self`, so its body became the
  module-level `executer_coroutine()` and the method delegates to it, unchanged
  for its existing caller.
- The layer passes **real** `task_requirements` — `task_type` and `complexity`,
  exactly the keys `ModelSelector` reads, taken from the planner's existing axes.
  `/model/generate` still passes `{}` with a *« à enrichir »* comment.

## 5. How the response context is constructed

`_contexte_de_reponse()` gathers six things and refuses the rest.

Evidence comes from two places and **their difference is the point**: the
researcher's findings carry their own `verified` flag; `senegal` elements come
from the corpus, where nothing enters without a source (ADR-019) and where
`apply_scope_policy` has already ruled — so they enter marked verified, *because
the corpus requires it, not because it is convenient*.

A `senegal` refusal travels **word for word**. Rephrasing a refusal is the first
step to softening it.

What stays out: the plan, the task list, the timings. A model given machinery
writes an execution report instead of an answer — and a test checks the built
prompt, not the context, because the prompt is what the model reads.

## 6. How grounding is preserved

**Grounding is computed before generation and never touched by it.** Three
outcomes, never two.

`ChatResponse.generated` is true only when a model produced the text. Without
that field a refusal composed by the platform would be indistinguishable from
an answer — the exact lie this repository refuses everywhere else.

Verified by sabotage: making generation overwrite grounding fails
`TestLaGenerationNAncreRien`; restoring it passes.

## 7. How Senegal stays a speciality

**It already was**, and the audit says so rather than implementing it twice:
5 global questions out of 5 never reach `senegal`; 3 Senegalese ones do.

What this VOLET added is the other half — the half that gets forgotten. A
speciality that never activates is not a speciality, so `TestCSenegal` asserts
that the Senegalese question **does** mobilise the agent.

And ADR-019 corrected the brief's framing: the layer never receives *global
evidence* or *Senegalese evidence*. It receives what exists, each piece carrying
its `scope`, because *a question about millet in Kaolack needs both halves*.

## 8. Tests actually executed

Every command below was run; none is quoted from an earlier session.

```
pytest tests/test_api_chat.py                        →  28 passed
pytest tests/test_chat_general_purpose.py            →  34 passed
pytest tests/test_orchestration_claims.py            →   9 passed
pytest tests/agent … test_agents_verifier_senegal.py →  195 passed
pytest -k "planner or decision or orchestration or router or workflow or chat or agent"
                                                     →  664 passed
pytest -q                                            → 7148 passed
ruff check src tests scripts agents                  → All checks passed
```

Sabotage runs, each reversed afterwards: the grounding invariant, the leak
classification, the three-way distinction, the response-layer wiring.

## 9. Exact measured results

| | Measured 2026-08-23 |
|---|---|
| Full suite | **7 148 passed, 9 skipped, 3 deselected, 0 failed** in 352 s |
| Baseline before this VOLET | 7 104 passed |
| Tests added / removed / weakened | **44 / 0 / 0** |
| *« Bonjour »* | **1 092 ms → 77 ms**, `agents == ["planner"]` |
| *« Merci ! »* | 2 ms |
| Generations per turn | **1** (prompt 1 441 chars) |
| Models registered on this machine | **0**, after full startup |
| Dependencies added | 0 |
| Secrets introduced | 0 |

## 10. What remains UNKNOWN

Everything that needs a real model. **Zero models are registered here**, so the
whole chain is verified with a simulated provider:

- the quality of real answers;
- real latency with a real model;
- the behaviour of fallback between providers;
- whether the prompt's instructions are actually followed by any given model.

These become measurable the day an operator runs one. Nothing in this report
claims otherwise.

## 11. Potential risks

**A turn is now longer, and the event loop still blocks.** The Linux audit
measured `/health` going from 3.5 ms to 1 149 ms during a `/chat` because
blocking work runs on the event loop — 144 `async` routes, zero offloads.
Adding a generation makes that worse, possibly much worse. **Its recommendation
P10 is three call sites and is now the most urgent thing in the repository.**

**The prompt is an instruction, not a guarantee.** It forbids inventing sources
and demands that unverified evidence be named as such. A model may disobey.
`generated` and the grounding chip are what keep the *platform's* claims honest;
they cannot police the *model's* prose. Measuring that needs a real model.

**Two public fields were added** to `ChatResponse`. Additive, but a contract is
a contract.

**One existing test changed.** It asserted an empty recommendation behaves as
`None` — correct while nothing could produce one. Updated with its reasoning,
and the fallback it guards is still asserted.

## 12. Commits

Branch `claude/galsen-ia-phases-ukwz7p`, restarted from `main` after PR #36
merged.

```
8663999  phase plan
3f5ee51  chapter 01 — root cause confirmed, brief corrected twice
c2417f0  chapter 02 — the contract, and ADR-019 correcting the brief
c9b056c  chapter 03 — routing measured on the brief's own examples
f28d031  chapter 04 — the response layer, wired to the model engine
f580f6c  chapter 05 — /chat produces a real answer
717c1c4  phase 5.3 — a greeting no longer runs a research pass
a99fe5f  chapter 06 — the error message was leaking the model host
4ec6666  chapter 07.1–7.2 — the matrix, cases A to F
58c3f37  chapter 07.3 + 08 — cases G to J, and §18/§19/§20
4a172c5  chapter 10 — ADR-039 and the documentation
```

---

## Scope audit

**Requested and delivered:** a real final answer, through the existing
orchestration, model engine, grounding, memory and security; the brief's test
matrix; general-purpose routing.

**Requested and deliberately not delivered**, both recorded and pinned by tests
that will fail the day either changes:

1. **The coding capability is not reached.** The intent is now `implementation`
   recommending `coder`, but the `question` workflow does not declare `coder`.
   Wiring a chat message to an agent that writes files is an operator decision
   under §19.
2. **A verified researcher finding does not ground a Senegalese question whose
   national base is empty.** The `senegal` agent's verdict wins — defensible,
   since it is the authority on national scope, but it is a choice and it is
   named.

**Not requested, not added.** No new provider abstraction, no second model
selection, no parallel architecture, no metric invented, no dependency.

**Two defects found by re-reading this VOLET's own work**, both fixed:
`/chat` returned `http://localhost:11434` to any caller, and an intent with no
agents raised `IndexError` in the planner.
