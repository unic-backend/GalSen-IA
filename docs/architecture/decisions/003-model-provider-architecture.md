# ADR-003: Model provider architecture

## Status
Accepted

## Date
2026-07-29

## Context
The Model Engine had sixteen components (selection, routing, cost and token
tracking, health monitoring, rate limiting) but no way to reach an actual model.
`generate_text()` returned a hardcoded string and the real provider call sat in
comments. Every agent that asked for text got the same fabricated sentence.

Three questions had to be answered before any model could be called:

1. How does the engine talk to OpenAI, Anthropic, Google or a local server
   without the rest of the engine knowing which one it is?
2. Where does the list of models and their capabilities come from?
3. What happens when no provider is configured — which is the project's state
   today, and will remain so until credential handling is decided?

## Decision

### A single provider contract
Every provider implements `ModelProvider` (`src/model_engine/providers/base.py`):
a declared catalogue (`list_models`), an availability check
(`check_availability`), and generation (`generate`). Nothing above that file
refers to a specific vendor.

Adding a provider means writing one class and registering it. The engine,
the selector and the agents are unchanged.

### Two registries, deliberately separate
- **`ProviderRegistry`** — which providers exist and which can answer now.
- **`ModelRegistry`** — the catalogue: every known model with its context
  window, capabilities and price, whatever its provider.

They are kept apart because the catalogue must stay readable when no provider is
configured. That is what lets the platform say "this task would need a model with
a 200k context window, and here is why none is available" instead of failing
blankly.

The existing `ModelStore` is a third, different thing: models registered at
runtime for use. It is untouched.

### Capabilities come from the provider
`CapabilityDetector` asks the provider that serves the model, because the
provider is the authority on its own catalogue. When the provider is unknown it
falls back to `StaticCapabilityDiscoverer`, the pre-existing table. That fallback
is what keeps hand-registered models — including those in the existing tests —
working unchanged.

### Unavailability is a status, not an exception
When nothing can serve a request:
- `generate()` returns a `GenerationResponse` with `status = UNAVAILABLE`, an
  empty `text`, a machine-readable `reason` and an actionable `detail`.
- `generate_text()`, which is typed `-> str`, raises `ProviderUnavailableError`.
  A caller expecting text must not receive a substitute for it.

Empty text with a status is the honest answer. A plausible sentence nobody
generated is worse than no answer, because it cannot be detected downstream.

### Credentials are explicitly out of scope
Hosted providers declare which environment variable will carry their key and
report `NO_CREDENTIALS` until then. Where keys come from, how they are supplied
in each deployment and how they are kept out of the repository is a separate
decision that needs its own ADR.

The local provider (Ollama) needs no credentials and is fully implemented: if a
server is running, generation works today.

## Consequences

### Good
- Providers are interchangeable; the engine has no vendor-specific code.
- The platform can explain precisely why it cannot answer, per provider.
- Selection favours the cheapest capable model, which matters for a platform
  built for contexts where per-token spend is a real constraint.
- A local model gives a zero-cost, offline path — relevant where bandwidth is
  expensive or unreliable.
- The sixteen existing components were reused as-is, not rewritten.

### Costs
- Two registries plus the store is three model-related concepts. The separation
  is justified but has to be documented, or it will be collapsed by mistake.
- Catalogue figures (context windows, prices) are declared in code and will
  drift as vendors change them. They need periodic review.
- Nothing generates text yet unless Ollama is running locally.

### Follow-up
An ADR on credential handling is now the blocking item for text generation.
It must cover: source of keys (environment only), per-deployment supply,
rotation, and what the engine does when a key is present but rejected.
