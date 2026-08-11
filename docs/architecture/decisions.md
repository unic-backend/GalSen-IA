# Decision Engine

What VOLET_22 asks for, and what the platform actually decides. Measured against the
repository on 2026-08-11.

---

## There is no decision engine, and none was built

The manual describes an eleven-component engine — Decision Core, Rule Engine, Inference
Engine, Risk Assessment Engine, Decision Repository, Decision Analytics — over a
fourteen-stage lifecycle, with metrics for decision accuracy, risk prediction accuracy and
an explainability score.

None of it exists. Nothing in this VOLET was built to make it look like it does. An engine
of that shape is a project, not a phase, and standing one up empty would produce exactly
what `.claude/rules/verification.md` forbids: a capability that reports plausible answers
without doing the work.

What plays the named roles today:

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| Human-in-the-Loop support | `ApprovalManagerImpl`, ADR-006 | present — the one decision path with a real gate |
| Rule Engine | `WorkflowValidator` + the declared pipeline | partial — rules about workflows, not about requests |
| Context / Memory / Knowledge connectors | `AgentContext` (`search_knowledge`, `recall`) | present |
| Decision Recording | **added by this VOLET** — see below | partial |
| Decision Core, Inference, Risk Assessment, Decision Repository, Decision Analytics | — | **absent** |

The AI-reasoning stages (4, 5, 6) also depend on exit criterion **C1**, which is not met:
no model provider is configured, so "AI Decision Reasoning" has nothing to reason with.

## The finding: the one decision the platform takes is thrown away

`PlannerAgent` detects intents in a request and derives the agents it needs. That is a
decision, made from rules, on real input. Measured on `surveille les logs de production`:

```
agents recommandés par le planificateur : researcher, deployment, monitor
agents réellement exécutés              : 9 — le pipeline déclaré, en entier
```

The router executes `workflows.yaml` as written. The recommendation is computed, returned
inside the planner's result, and consumed by nothing. Six agents run that the platform's
own analysis said were not needed — including `tester`, which VOLET 19 measured at 96 % of
request time.

This was already half-known: the VOLET 06 section of `orchestration.md` records that
"intent detection exists in `PlannerAgent` and is not used". What this VOLET adds is the
consequence, in the manual's own terms — chapter 03 makes decision recording stage 10 and
lists explainability assessment among its quality controls. A decision taken and lost is
neither recorded nor explainable: nobody can say it happened, still less why it changed
nothing.

### What it does now

`src/router/decision_trace.py` compares the recommendation with the execution and puts the
result in the response metadata:

```json
"decision": {
  "recommended_agents": ["researcher", "deployment", "monitor"],
  "executed_not_recommended": ["coder", "documentation", "planner",
                               "reviewer", "security", "tester"],
  "recommended_not_executed": [],
  "applied": false,
  "detail": "Le pipeline est déclaré dans workflows.yaml et exécuté tel quel ; la
             recommandation du planificateur est enregistrée, jamais suivie."
}
```

Three deliberate details:

- **`applied: false` is explicit, not inferable.** Without it a reader would assume the
  decision steers the execution, which is precisely what it does not do.
- **"the planner did not run" and "the planner recommended nothing" stay distinct.**
  `recommended_agents: null` versus `[]` — merging them would turn an absence into a
  choice.
- **Both directions are reported.** Agents run without being recommended are the cost the
  decision would have avoided; agents recommended and not run are the symmetric gap.

### What was deliberately not done

Making the router follow the recommendation would change what every request executes. That
is a design decision about the pipeline — the same one already ranked **P1** in
`docs/memory/pending-work.md` after VOLET 19 measured `tester` — and this measurement
sharpens it: the platform already computes which agents a request needs, so the option
"scope the pipeline to the request" is not new work, it is wiring a decision that is
already being made.

A measurement phase records that. It does not take it.

## Chapters 04 to 10

Management, security, compliance, monitoring, quality and governance describe an engine
that does not exist, so most of their content has nothing to measure against. What is real
and already documented elsewhere: approval requests are audited and gated (ADR-006),
every route is RBAC-controlled, and the audit engine records who decided what.

The lifecycle metrics — decision accuracy, risk prediction accuracy, explainability score,
decision consistency — are not reported. Accuracy needs a ground truth nobody has written,
and an explainability score computed on a rules table would be a number without a
question behind it.
