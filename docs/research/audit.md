# R00 — what GalSen IA already owns for research

Research Orchestration directive, **STEP 1**. Measured on 2026-08-19 at
`4f899f8`, by reading the code — not by recalling it.

STEP 1's instruction is *"do not rebuild existing functionality
unnecessarily"*, and its classification is
**EXISTING / EXTENSION_REQUIRED / NEW_COMPONENT_REQUIRED / DEPRECATED /
UNKNOWN**. Every row below carries one, and the path that justifies it.

---

## A naming collision, first, because it will cause a mistake otherwise

`tests/test_agent_reach.py` **already exists in this repository** and has
nothing to do with `Panniantong/Agent-Reach`. It asks whether a capability
added to `src/` actually *reaches* an agent through `AgentContext` — the silent
failure mode where a feature works for everyone except the agents the platform
is made of.

Anyone grepping for "agent reach" during this programme will find it. It is not
a prior integration, and it must not be edited as if it were.

---

## R00.1 — search, retrieval, knowledge, agents, MCP, connectors

### The scale of what is here

| Area | Size |
|---|---|
| `src/knowledge_engine/` | **37 modules** |
| `src/tools/` | **23 tools** |
| `src/services/search/` | 7 modules, **4 search providers** |
| `src/acquisition/` | gated collection path, ADR-021 |
| `src/mcp/` | client, server, exposure |
| `src/connectors/` | contract, registry, lifecycle, safety, OAuth, SDK |
| Tests already covering this ground | **42 files** (16 knowledge, 9 acquisition, 17 search/browser/MCP/connector) |

### Classification

| STEP 1 asks about | Status | Where, and what it actually does |
|---|---|---|
| **Existing web search** | **EXISTING** | `src/tools/web_search/tool.py` — DuckDuckGo HTML scraping, one provider, with a token-bucket `RateLimiter` and a `TTLCache` (300 s). |
| **RAG / retrieval** | **EXISTING** | `knowledge_engine/knowledge_retriever.py`, `scoped_retrieval.py`, `knowledge_ranker.py`, `knowledge_indexer.py`. |
| **Knowledge base** | **EXISTING** | 37 modules, two axes (scope × subject), ADR-019. |
| **Research agents** | **EXISTING** | `agents/researcher/agent.py` — gathers from three sources **in order of trust**: knowledge base (verified), shared memory, then web (*"unverified, so always reported with its source"*). |
| **MCP integrations** | **EXISTING** | `src/mcp/` — server, `exposure.py` (a deliberate subset of 21 tools, not all), and `client.py` which **refuses to connect to anything** and implements tool-poisoning defence first. |
| **Connectors** | **EXISTING** | `src/connectors/` — contract, registry, lifecycle, `safety.py`, OAuth flow. |
| **Browser tools** | **EXISTING**, and see the gap below | `src/tools/browser/tool.py` — `urlopen`, no host validation. |
| **Citations** | **EXISTING** | `knowledge_engine/citations.py`. |
| **Freshness** | **EXISTING** | `knowledge_engine/freshness.py`, `perishable.py`, `knowledge_lifecycle.py`, `knowledge_revalidation` tests. |
| **Cross-source comparison** | **EXISTING** | `knowledge_engine/contradictions.py`. |
| **Source registry / discovery** | **EXISTING** | `knowledge_engine/source_registry.py`, `source_discovery.py`, `acquisition/discovery.py`. |
| **`ResearchProvider` abstraction** | **NEW_COMPONENT_REQUIRED** | Nothing declares a *research* provider. `services/search/providers.py` has four providers, but they are **internal sources** — knowledge, memory, document, world — not external research services. |
| **`ResearchRouter`** | **NEW_COMPONENT_REQUIRED** | `SearchManagerImpl` merges and ranks across internal providers; it does not route on freshness, reliability, health, cost or permissions. |
| **GitHub research** | **EXTENSION_REQUIRED** | `src/tools/github/tool.py` exists — read-only, token from the environment at call time, anonymous when absent. No search-by-topic, no issue search surfaced as a research capability. |
| **Reddit / X / YouTube** | **UNKNOWN** | Nothing found. To be established in R01 against the two candidates rather than assumed absent. |
| **Academic search** | **UNKNOWN** | Nothing found under that name. |

### The most important finding of R00.1

**The four "search providers" this platform has are not what the directive
means by a provider.** `KnowledgeSearchProvider`, `MemorySearchProvider`,
`DocumentSearchProvider` and `WorldSearchProvider` all search **inside** the
platform. Exactly one component reaches the open web as a search engine
(`tools/web_search`), and it scrapes one HTML endpoint.

So `ResearchProvider` and `ResearchRouter` are genuinely new — which is a
different answer from the previous two programmes, where almost everything
requested already existed. **It is also the one place where the temptation to
build fifteen classes returns**, and §11's lesson applies: the useful abstraction
is small.

### The existing web search, judged honestly

One provider, DuckDuckGo, reached by **parsing HTML**. That has three
consequences worth writing down before anything is built on it:

1. It breaks when the page markup changes, and the failure looks like "no
   results" rather than an error.
2. It carries no API contract, no rate-limit agreement and no terms acceptance.
3. `_parse_duckduckgo_html` already has a **fallback parser** in it, which is
   the fingerprint of markup that has already changed once.

This is `EXTENSION_REQUIRED`, not `DEPRECATED`: it works, it is the only web
reach the platform has, and STEP 3 says not to install a second version of a
capability an existing provider already serves better. Whether either candidate
serves it better is R03's question, not this one's.

---

## R00.2 — provenance, cache, security, permissions, observability, tests

| STEP 1 asks about | Status | Where |
|---|---|---|
| **Provenance** | **EXISTING, twice** | `src/acquisition/` (where a *fact* came from, ADR-021, ten quality checks) and `creative/jobs.py` (where an *artefact* came from). STEP 9 forbids a competing third. |
| **Knowledge status ladder** | **EXISTING** | `OBSERVED → CANDIDATE → CORROBORATED` (C14), and `promote_by_frequency` **never returns `VALIDATED`, whatever the count**. STEP 8's ladder is already this platform's rule. |
| **Source trust** | **EXISTING** | `src/security/trust.py` — seven levels, `wrap()`, `inspect()`, `is_data()`. External content is `EXTERNAL`, *hostile by default*. |
| **MCP tool-poisoning defence** | **EXISTING** | `src/mcp/client.py` — the threat is named and defended before any connection exists. |
| **Caching** | **EXISTING, six implementations** | `knowledge_cache.py`, `memory_cache.py`, `lru_document_cache.py`, `creative/cache.py`, `tools/web_search`'s `TTLCache`, plus interfaces. STEP 11 says reuse. |
| **Authentication** | **EXISTING** | API key or JWT (ADR-029), `src/auth/`, `tests/test_api_auth.py`, `test_auth_jwt.py`, `test_auth_hybrid.py`. |
| **Authorization** | **EXISTING** | RBAC, `src/api/rbac.py`, with `PERMISSIONS_HORS_PLATEFORME` already keeping some permissions out of every platform role. |
| **Rate limiting** | **EXISTING, at two levels** | `src/api/rate_limiter.py` (inbound) and `tools/web_search`'s token bucket (outbound). |
| **Logging** | **EXISTING** | `src/audit_engine/` — and K00 measured its gap: the trail is in memory, so a restart erases it unless `GALSEN_STORAGE_BACKEND=sqlite`. |
| **Observability** | **EXISTING** | `src/observability/trail.py`, one job followable end to end via `/observability/trail/{id}`. |
| **Provider privacy policy** | **EXISTING, new** | `creative/canvas/privacy.py` (K07) — `data_destination`, and `UNKNOWN` failing safe to `EXTERNAL`. Reusable here verbatim. |
| **SSRF protection** | **PARTIAL — see below** | `acquisition/fetcher.py` only. |

### The real gap: SSRF protection exists in exactly one module

`src/acquisition/fetcher.py` is disciplined, and says so in its own docstring —
it refuses a disguised user agent **in code**, fetches `robots.txt` first,
refuses cross-domain redirects, refuses undeclared content types, and refuses
plain HTTP except on the loopback, *"bounded by the address, not by a flag a
caller could pass"*.

**`src/tools/browser/tool.py` and `src/tools/web_search/tool.py` have none of
it.** Both call `urlopen` directly. Neither checks the scheme, the resolved
address, private ranges, the loopback, or link-local metadata addresses. The
fetcher's own docstring already says the browser tool *"follows redirects
anywhere, which crosses the same-domain boundary without any line explicitly
crossing it"*.

**Status: `EXTENSION_REQUIRED`, and it is a precondition of this programme, not
a nice-to-have.** STEP 10 says *"do not bypass existing SSRF protection"* — the
honest reading of that sentence here is that the protection exists in one place
and the modules a research layer would naturally call are the two that lack it.
A `ResearchProvider` that fetches a URL through `BrowserTool` would inherit the
gap, so R06 has to decide whether the fetcher's discipline is lifted into a
shared guard or the research layer is confined to the fetcher.

**Nothing is fixed in this phase.** R00 audits; R06 decides.

---

## What R00 concludes

**Most of STEP 1's list already exists**, as in both previous programmes — but
the shape of what is missing is different this time:

1. **`ResearchProvider` and `ResearchRouter` are genuinely new.** Every provider
   abstraction here selects *models* or *internal sources*; none selects an
   external research service.
2. **One SSRF guard exists, in the one module a research layer would not
   naturally use.** That is the security question of this programme.
3. **Everything else — provenance, status ladder, trust boundary, cache,
   citations, freshness, contradictions, auth, RBAC, rate limiting,
   observability — exists and must be reused.** Writing a second of any of them
   would repeat the mistake §3 of the previous directive named, and STEP 9
   forbids explicitly for provenance.

**Total tests standing on this ground today: 42 files**, inside a suite of
**6 363 passing**. None may be deleted (STEP 12).
