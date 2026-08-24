# ADR-040 — A local model declares what it can do, and where that is known from

- **Status**: accepted
- **Date**: 2026-08-24
- **Supersedes**: nothing
- **Related**: ADR-014 (sovereignty — local generation is the only runtime path),
  ADR-030 (provider programme), ADR-039 (the chat writes)

## Context

The platform has had a capability-based model routing layer since VOLET 30:
`config/model_routing.yaml` declares what each task type needs,
`RoutingPolicy` turns a request into requirements, `ProviderSelector` compares
candidates against them, and `CapabilityDetector` asks the provider what a
model can do.

On 2026-08-24 that layer was measured end to end against a realistic local
fleet — a coding model, a reasoning model, a vision model, a small fast model
and a long-context model, all served by Ollama. The result:

| Task requested | Model chosen |
|---|---|
| `code_generation` | `qwen2.5-coder:14b` — first in the list |
| `reasoning` | `qwen2.5-coder:14b` — the same |
| `conversation` | `qwen2.5-coder:14b` — the same |
| `vision` | **none** |
| `summarization` | **none** |
| `document_analysis` | **none** |

The first three lines are not one good choice followed by two mistakes. They
are **the first element of the list, three times.** The selection layer existed,
was wired, and selected nothing.

Five distinct causes, each measured:

1. **`LocalProvider` built one identical descriptor for every model** — no
   vision, no tools, 8192 tokens, and three special features (`local`,
   `no_cost`, `offline`) that belong to no routing vocabulary. Nothing
   distinguished a coding model from a vision model, so nothing could choose
   between them.
2. **`/api/tags` carries no `context_length`.** The provider read
   `details.context_length` from it; that key does not exist, so every model
   was declared 8192 — which made `summarization` (32k) and
   `document_analysis` (100k) unroutable by construction.
3. **An unstated complexity was treated as `medium`**, silently imposing an
   8192-token floor. That floor excluded the only vision model served, for a
   context an image never asks for.
4. **`ProviderSelector._pick_best` returned the first candidate carrying *any*
   expected feature**, and `prefer_cheapest` short-circuited before features
   were considered at all. Local models are all free, so "cheapest" was a
   universal tie broken by list order.
5. **The generation path never called the selector.**
   `generate_text_with_fallback` — the function the chat calls — walked the
   catalogue in provider order and kept the first model that answered. All the
   selection logic lived in `ProviderSelector`, which this path did not call:
   from a chat user's point of view, nowhere.

And one more, at the seam between subsystems: **seven of the planner's eight
intents had no routing rule.** The chat forwards the planner's `task_type` axis
verbatim, so `implementation` — a request to write code — matched nothing, fell
through to `default` (`general_conversation` + `prefer_cheapest`), and was
answered by the smallest model installed.

## Decision

**A local model's capabilities are established from three sources, ranked, and
every capability carries the source that fixed it.**

```
measured  >  declared  >  default
```

- `measured` — observed on the Ollama server's `POST /api/show`. Its response
  carries a `capabilities` array (`vision`, `tools`, `completion`…) and a
  `model_info` object holding an architecture-prefixed key ending in
  `.context_length`. Verified against the official API documentation
  (`ollama/ollama`, `docs/api.md`). This is the only source that observes.
- `declared` — `config/model_routing.yaml`, section `local_models`. An
  operations decision: the operator says which model is installed and what it
  is for. Name patterns, first match wins, so specific patterns precede
  general ones.
- `default` — nothing is known. The context stays what `/api/tags` gave, and no
  strength is announced.

Three consequences follow, and none is a formality:

- **A measurement overrides a declaration; a declaration overrides a default.**
- **A silent measurement erases nothing.** A `/api/show` response that says
  nothing about vision does not clear what the configuration said about it.
  "Not measured" is not "measured false", and `ProfilLocal` carries `None` for
  the first and `False` for the second.
- **An absent capability in a `capabilities` array *is* a measurement.** The
  array is the complete list of what the server recognises, so `vision` missing
  from it means `False`, not `None`. A missing array means `None`.

**An unstated complexity imposes no floor.** `medium` remains the value
*reported*, so callers reading it do not change behaviour; it no longer raises
any minimum context.

**Selection scores, it does not take the first match.** Candidates are ranked by
how many of the task's expected features they carry. Python's stable sort leaves
the incoming cost order as the final tiebreak, so cheapness still decides
between equally capable models. Under `prefer_cheapest`, cost leads and features
break ties — which is what makes a greeting reach the small model rather than
the 14-billion-parameter one.

**The generation path sorts the catalogue before walking it.** `_fallback_candidates`
puts the selected model first and leaves the rest in place. Nothing is pruned:
the fallback keeps exactly the reach it had.

**Planner intents are added to the routing policy, not renamed in the planner.**
Those intents also designate which agents to mobilise; renaming them would break
that correspondence in order to repair this one. One vocabulary, two readers.

## Consequences

Measured after the change, same fleet, same five models:

| Task | Model chosen |
|---|---|
| `conversation`, `translation` | `phi3:mini` |
| `code_generation`, `code_review`, `implementation`, `quality` | `qwen2.5-coder:14b` |
| `reasoning`, `planning`, `analysis`, `security` | `deepseek-r1:14b` |
| `vision` | `llava:13b` |
| `document_analysis`, `summarization`, `research`, `documentation` | `llama3.1:8b` |

Ten task types and eight planner intents now reach five distinct models. The
same table is asserted by `tests/test_local_model_profiles.py`, and removing the
integration makes eight of those tests fail — verified by sabotage, not assumed.

**What this does not do.** It does not make any model better, and it measures no
model's quality. It makes the platform *choose* among the models an operator
installed. Whether `deepseek-r1:14b` reasons better than `qwen2.5:14b` is not
established here and is not claimed anywhere in this change.

**What stays declared rather than measured.** The `context_window` values in
`local_models` are starting points an operator should confirm; no server was
reachable from this environment to measure them. They are marked `declared` in
every descriptor that uses them, and a running `ollama serve` replaces them with
measurements on the next catalogue read. The `features` lists are declarations
by nature — `/api/show` says whether a model sees, never whether it is good at
code.

**The cost if this is wrong.** If a name pattern maps a model to the wrong role,
that model is tried *first* for a task it is bad at — and then the fallback tries
the others, so the failure is a worse answer, not an absent one. The previous
behaviour had the same failure mode permanently and without a way to correct it,
which is why the pattern table lives in configuration and not in code.
