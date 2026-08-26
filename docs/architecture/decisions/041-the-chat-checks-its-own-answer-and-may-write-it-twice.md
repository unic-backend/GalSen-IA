# ADR-041 — The chat checks its own answer, and may write it twice

- **Status**: accepted
- **Date**: 2026-08-24
- **Related**: ADR-039 (the chat writes), ADR-040 (the router selects),
  `agents/verifier/agent.py` (factual verification, VOLET 36)

## Context

ADR-039 gave the chat a writing stage. It generates **once** and returns the
result. Nothing reads what came back.

That is not a hypothetical gap. A model that writes *« le total est 2 + 2 = 5 »*,
or asserts *« il est prouvé que… »* about something the platform never verified,
or states a claim that one of the platform's own gathered findings contradicts,
is served as-is. The platform already refuses, everywhere else, to present the
unverified as established — and its own writing stage had no such check.

A verifier exists (`agents/verifier/agent.py`) and is deliberately narrow: it
carries a verdict on retrieved claims and **never rewrites**. It is dispatched
as an agent, and it triggers nothing. Nothing in the repository closes the loop
between "this answer has a defect" and "write it again".

## Decision

**A generated answer is criticised before it is served, and may be regenerated
once.** Two modules, and the boundary between them is the design:

- `src/reasoning/critics.py` **observes**. It corrects nothing and calls no model.
- `src/reasoning/deliberation.py` **decides what to do with an observation**, and
  when to stop.

Separating the measure from what is done with it is the rule
`agents/verifier/agent.py` already set for factual verification. It holds here
for the same reason: a component that measures and corrects at once no longer
lets you tell which half was wrong.

### No critic asks a model whether it was right

The verifier's own words: doing so *« would measure the model's confidence in
itself, which is exactly what a verification layer exists to escape »*. Every
check is therefore deterministic — decided on the text and the gathered
findings, with no second call:

| Check | Catches | Severity |
|---|---|---|
| `empty_answer` | the model produced nothing | blocking |
| `arithmetic_error` | `a op b = c` that is false, in `Decimal` | blocking |
| `contradicted_by_evidence` | a claim a gathered finding contradicts | blocking |
| `unsupported_certainty` | certainty markers while grounding is not `GROUNDED` | blocking |
| `internals_exposed` | the answer names the planner, the researcher, a workflow | advisory |

`contradicted_by_evidence` reuses `evaluate_answer()` from
`src/knowledge_engine/factual_evaluation.py` rather than writing a second
claim-splitter — two of them would eventually stop agreeing.

Only `DISPUTED` is blocking. `UNSUPPORTED` — "no passage mentions this" — is
ordinary as soon as an answer goes beyond the findings, which it is allowed to do.

### Three stops, and the report says which one fired

`verified` (nothing left to fix), `iteration_budget_exhausted`,
`deadline_exceeded`, plus `generation_failed` when a retry cannot reach a model.
A caller reading "budget exhausted" must not act like one reading "verified".

The deadline is checked **before** a retry, never mid-generation: interrupting a
model in flight returns truncated text, which is worse than late.

### When the budget runs out, the answer is served *with* its findings

`ReponseFinale.deliberation` carries every attempt, its findings, and the stop
reason. A loop that silently serves an answer it knows is doubtful is worth less
than no loop at all — it adds a guarantee that does not exist.

### One retry by default, and the operator sets it

`GALSEN_CHAT_MAX_RETRIES`, default `1`. That is the retry that fixes a bad sum
or removes an unearned certainty; further ones cost the same and return much
less. **`0` does not disable the criticism** — findings are still reported, only
the retry stops.

### The retry says what was wrong, never re-sends the text

Handing a model its own text invites it to rephrase rather than redo, and that
is how an error survives its own correction.

## Consequences

Measured on this machine, `python -m src.reasoning.benchmark`, 22 hand-written
cases:

```
détection       : 66.7 % (8/12)
fausses alertes : 0.0 % (0/10)
```

**The false-alarm rate is the important half**, and the one usually left
unmeasured. A critic that flags everything reaches 100 % detection and makes the
loop unusable — every answer would cost a retry.

**66.7 % is deliberate.** The first version of that benchmark scored 8/8, which
said nothing: the cases and the checks came from the same hand. Four cases that
the checks genuinely miss were added — a sum written in words, a calculation with
no equals sign, a percentage, a rephrased contradiction — each carrying the
reason it fails. A benchmark whose score can only rise is a decoration.

**What this does not claim.** These checks do not catch "hallucinations". They
catch specific shapes. A plausible, uncontradicted fabrication passes, and saying
so is better than implying a net that is not there.

**One earlier constraint is superseded.** `test_un_tour_ne_declenche_qu_une_generation`
encoded *"one turn, one generation"* from the chat brief — a rule aimed at not
having every agent write the answer and then rewriting it. A verified retry is
not that, and this ADR's brief asks explicitly for a loop that can trigger
another attempt. The test still passes: a single retry only happens when a
blocking finding exists.

**A defect found while building this, worth recording.** The first
`empty_answer` check required three words, so it flagged *« 42 »*, *« Oui. »* and
*« Non, à Dakar. »* — complete answers to questions that need no more. A verifier
that penalises concision costs a model call and improves nothing. *Empty* means
empty.

**The cost if this is wrong.** A false alarm costs one extra generation and
serves a rewritten answer that was already fine. It is bounded by the retry
budget and measured at 0 % over ten clean cases — a small sample, and stated as
such.
