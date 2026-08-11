# ADR-014: Model Sovereignty — GalSen IA Depends on No External Model at Runtime

## Status
Accepted

## Date
2026-08-11

## Context

The project's direction, stated by its owner: GalSen IA is not a client of other AI
platforms. It must run entirely on infrastructure the project controls, with its own
models — the **SamP** and **ToP** families — and its own reasoning. Depending on Claude,
GPT or DeepSeek APIs would make the platform a tenant of companies that can change their
prices, their terms, their availability, or their willingness to serve this region, on
any morning, without notice.

This is not only a philosophical position. For a platform serving Senegal and Africa it
is an operational one: latency to distant regions, payment in foreign currency, key
revocation by a third party, and data leaving the continent are all real costs of
depending on someone else's endpoint.

What the code does today, measured:

- `provider_registry.py` registers **five** providers by default: OpenAI, Anthropic,
  Google, Local (Ollama) and OpenAI-compatible.
- The three hosted ones carry hardcoded URLs — `api.openai.com`, `api.anthropic.com`,
  `generativelanguage.googleapis.com`.
- They stay inert without a key. **Inert is not the same as absent**, and "nobody set a
  key" is a state, not a guarantee.

## Decision

**Sovereignty is a property the platform enforces, not a habit it hopes for.**

### 1. Two axes, kept apart

They are routinely confused, and confusing them makes one of them look impossible.

| Axis | Meaning | State |
|---|---|---|
| **Runtime sovereignty** | No request leaves the platform to a third-party model, ever | **Reachable now**, and enforced by this ADR |
| **Weight lineage** | Where the model's parameters come from | Staged — see below |

Runtime sovereignty is the one that carries the operational risk, and it is achieved the
day the platform serves its own model. It is decided here.

### 2. Sovereign mode is the default

`GALSEN_SOVEREIGN_MODE` defaults to **true**. In that mode:

- The hosted providers are **not registered at all** — not registered-and-idle. A
  provider that is not in the registry cannot be selected by any path, accidental key or not.
- Only `LocalProvider` (Ollama) and `OpenAICompatibleProvider` are available. The second
  is not a dependency on OpenAI: it is a *protocol* that vLLM, llama.cpp, LM Studio and
  the project's own server all speak. The name is theirs; the wire format is public.
- `/health` states the mode, so an operator can see it rather than assume it.

Setting it to `false` is a deliberate, logged decision — useful for comparing an own model
against a reference during evaluation, and for nothing else.

The test that matters is not "is the flag read". It is: **with sovereign mode on and every
hosted key set, no external endpoint is reachable from the model path.** That is the
assertion, and it belongs in the suite.

### 3. Weight lineage is staged, and the stages are named

Building the SamP and ToP families does not start with pretraining from scratch, and
saying so plainly is more useful than encouragement.

| Stage | What it produces | Cost order |
|---|---|---|
| **S1 — Adaptation** | SamP/ToP as adapters over an open-weight base (VOLET 33) | Hours on one GPU, tens of euros |
| **S2 — Merge and own** | A single merged, quantised model served by the project, evaluated on its own benchmark | Same, plus storage |
| **S3 — Continued pretraining** | Wolof and regional-language capability the base never had, from the corpus of VOLET 28 | Thousands of GPU-hours |
| **S4 — Pretraining from scratch** | A model owing nothing to anyone's weights | Millions of GPU-hours, a corpus in the hundreds of billions of tokens |

**S1 and S2 give full runtime sovereignty.** The platform depends on no one's servers,
no one's keys and no one's uptime. S3 is where the models become genuinely *this
project's*, because they will know things no base model knows. S4 is a legitimate
long-term ambition and is not on any roadmap here — putting it on one would be a promise
against the evidence.

### 4. The base model licence is a decision, not a detail

Naming an adapted model **SamP** or **ToP** is only clean under a permissive licence.

- **Apache-2.0 bases** (Qwen 2.5, Mistral 7B v0.3) allow renaming, redistribution and
  commercial use with attribution in the notices. **This is the recommended lineage.**
- **Llama** ships a community licence with naming and attribution requirements —
  derivatives must carry "Llama" in the name and display "Built with Llama". That
  contradicts the SamP/ToP identity, so it is declined for that reason alone.
- **Gemma** has its own terms with use restrictions.

The licence of every base used, and the file where it is recorded, is part of the run
manifest defined in `docs/architecture/training-infrastructure.md`.

## Consequences

Positive:

- No key to buy, no quota from a third party, no price change to absorb.
- No user prompt leaves the machine. That is a data-protection property, not just a cost one.
- Offline and low-connectivity deployment stays possible — which matters here.
- The platform can be shown to be sovereign, not merely described as such.

Negative, and accepted:

- **The operator must run a model.** Ollama or a compatible server is now a hard
  requirement, not one option among several. Exit criterion C1 has exactly one path.
- Quality on general reasoning will trail the largest hosted models for some time. The
  answer is not to borrow theirs: it is specialisation — a 7B model that knows Senegalese
  agriculture beats a 400B model that does not.
- Hardware becomes the project's problem. A 7–8B quantised model needs ~6–8 GB of RAM to
  serve; that bound belongs in the deployment documentation.

## Alternatives considered

- **Hosted first, sovereign later.** The common path, and the one that never completes:
  every feature built against a hosted API acquires assumptions about its latency, its
  context window and its behaviour, and removing it later is a rewrite.
- **Hybrid with fallback to a hosted provider.** Attractive, and it quietly reintroduces
  the dependency at exactly the worst moment — under load, or when the local model fails.
  A fallback that is only used in incidents is a dependency you discover during incidents.
- **Keep the hosted providers registered but keyless.** What the code does today. It
  relies on absence of configuration, which is not a guarantee.

*Ollama (MIT), llama.cpp (MIT), vLLM (Apache-2.0) are serving paths, not dependencies of
the platform's logic: the OpenAI-compatible wire format lets any of them be replaced.*
