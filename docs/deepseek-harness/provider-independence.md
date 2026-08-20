# D06 — Provider independence (Phase 4)

**Built**: 2026-08-20. GalSen IA facts VERIFIED FROM REPOSITORY; DSH facts
VERIFIED FROM OFFICIAL SOURCE, `docs/config-catalog.md` read today.

Phase 4's requirement: adding DSH must **not** make GalSen IA dependent on
DeepSeek, the orchestrator must remain provider-independent, and if DeepSeek
becomes unavailable the platform must continue through fallback providers.

---

## 1. The distinction the name hides

**"DeepSeek" appears twice in this programme and means two different things.**

| | What it is | What depending on it would mean |
|---|---|---|
| **DeepSeek the model provider** | a hosted inference API | requests leave the machine; ADR-014 refuses this by default |
| **DeepSeek Harness the runtime** | MIT, self-hosted, TypeScript, runs locally | a code dependency, not a network one |

The previous programme's directive made the same distinction for OpenClaw
(*"do not confuse OpenClaw with a model"*). Here it matters more, because the
runtime and the provider **share a company name**, and conflating them would
produce either a false alarm or a real blind spot.

Phase 4 asks about **both**, and they must be answered separately.

## 2. Does the harness require DeepSeek models? No.

`docs/config-catalog.md`, VERIFIED FROM OFFICIAL SOURCE:

| Adapter plugin | What it serves |
|---|---|
| `@deepseek-ai/dsh-llm-deepseek` | DeepSeek — *"Provider route for created agents"*, with `apiKeyEnv`, `baseURL`, thinking modes, `maxTokens` |
| `@deepseek-ai/dsh-llm-pi-ai` | **OpenAI wire-compatible**, plus *"multiple vendor protocols including Anthropic, Bedrock, and various OpenAI-compatible implementations"*, with `baseURL` endpoint overrides |
| `@deepseek-ai/dsh-llm-replay` | recorded snapshots, for tests |

**DeepSeek is *"supported but not mandated as default"*** — read verbatim. The
model adapter is a plugin like everything else (D00.2), and `dsh-llm-pi-ai`
accepts a `baseURL` override.

`INFERENCE`: **the harness can be pointed at GalSen IA's own OpenAI-compatible
endpoint**, exactly as the OpenClaw audit found for its subject. That means
inference would pass through `ModelRouter`, `routing_policy` and
`config/model_routing.yaml`, and ADR-014's sovereign default would hold.

**This closes a `UNKNOWN` D00.2 left open** — item 5, model integration.

## 3. Does adding the harness create a network dependency on DeepSeek? No, if configured so.

Three configurations, three verdicts:

| Configuration | Verdict |
|---|---|
| DSH with `dsh-llm-deepseek` and a DeepSeek API key | **REJECT** — a hosted provider reached outside `ModelRouter`, defeating ADR-014's default exactly as the OpenClaw audit found |
| DSH with `dsh-llm-pi-ai` pointed at **our** endpoint | **VIABLE** — no DeepSeek network dependency at all |
| DSH with `dsh-llm-replay` | test fixtures only |

**The runtime itself is MIT and self-hosted** (D00.1), so the *code* dependency
is the ordinary kind: a package that can be pinned, vendored or dropped.

`UNKNOWN`, carried from the OpenClaw audit because it recurs identically:
**can the provider configuration be made unwritable by the agent?** DSH's own
tools include `cordis_define`, `cordis_run` and `cordis_undefine` — *"Define
immutable Cordis packages for dynamic plugin registration"*, *"Activate packages
of dynamic plugins"*. An agent that can register plugins at runtime is an agent
that might register a second model adapter. **D07 owns this**, and it is now the
sharpest security question of the programme.

## 4. Does GalSen IA continue if DSH disappears?

**Yes, and the mechanism is already built and already exercised.**

`src/coding_engine/router.py` — VERIFIED FROM REPOSITORY:

> *"Le routeur ne connaît **aucun** des trois moteurs par son nom. Il ne manipule
> que des capacités."*

It routes on `CodingCapability`, scores engines by specialty weight, and — D05
measured this — **already operates with all three engines unavailable**. Adding
a fourth that later becomes unavailable is a case the router handles today,
because it is the case it handles today for the other three.

`src/integration/degradation.py` probes **nine subsystems** and reports
`DEGRADED` — *"it answered, and it says what it is missing. The platform keeps
working; that subsystem does less. This is not a failure and must not be
reported as one."*

`src/model_engine/model_router.py` — `FailoverModelRouter` counts failures per
model, switches after a threshold of three, and resets after 300 seconds.

**Three independent fallback mechanisms**, at three layers: engine choice,
subsystem availability, model failover. None was built for this programme.

## 5. Phase 4's diagram, answered

```
Provider A          → src/model_engine/providers/anthropic_provider.py
Provider B          → google_provider.py
Provider C          → openai_provider.py / openai_compatible_provider.py
DeepSeek            → not registered today; would enter as one more
Future Provider D   → a file beside the others
Future Provider E   → idem
```

`provider_registry.py` and `provider_selector.py` decide; ADR-014 decides which
are registered at all. **The orchestrator does not name a provider anywhere** —
`config/model_routing.yaml` externalised that policy precisely so changing it
does not mean changing code.

**Phase 4's requirement is already satisfied by the existing architecture**, and
would remain satisfied with DSH added *in the viable configuration*. It would be
violated by the rejected one — not because DSH is at fault, but because any
runtime holding its own credentials sits outside `ModelRouter`.

That generalisation was already recorded in ADR-034 for OpenClaw: **any
subordinate runtime with its own credential store is a hole in ADR-014 that the
existing sovereignty test cannot see**, because that test exercises GalSen IA's
model path and a second runtime is not on it.

**Two programmes, two different projects, same hole.** `INFERENCE` for D10: this
is not a DSH problem to be weighed against DSH's merits. It is a **missing test
in this repository**, and it will recur with every future runtime proposal.

## 6. What D06 concludes

1. **The harness does not require DeepSeek models.** *"Supported but not
   mandated as default"*, and `dsh-llm-pi-ai` accepts a `baseURL`. `UNKNOWN`
   item 5 from D00.2 is closed.
2. **One viable configuration exists** — point it at our own endpoint — and one
   rejected one.
3. **Fallback is already built**, at three layers, and the coding router already
   runs with zero engines available.
4. **Phase 4 passes**, conditionally on configuration.
5. **One security question is now the programme's sharpest**: `cordis_define` /
   `cordis_run` let an agent register plugins at runtime. Whether that reaches
   the model adapter is `UNKNOWN` → **D07**.
6. **One finding about GalSen IA itself**, recurring for the second time:
   the sovereignty test does not cover subordinate runtimes. Recorded for
   `pending-work`, not fixed here.
