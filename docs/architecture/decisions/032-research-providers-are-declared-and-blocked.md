# ADR-032 — Research providers are declared, measured, and blocked until an operator says otherwise

**Status**: accepted
**Date**: 2026-08-19
**Directive**: Research Orchestration Integration, STEP 1–5, STEP 10, STEP 14, and the two mandatory rules
**Volets**: R00–R03 (evidence), R04 (this decision), R05–R11 (implementation)

## Context

The directive asks for the research capabilities of `Panniantong/Agent-Reach`
and `sydasif/web-search-mcp` to be integrated as **providers**, and forbids
GalSen IA becoming either of them. Four audit volets produced the evidence.

**Only one of the two is a library** (R01). `web-search-mcp` 0.6.3 is a typed,
importable package behind a FastMCP server. `Agent-Reach` 1.5.0 exports one
class whose only methods are `doctor()` and `doctor_report()`; its capability
lives in `agent_reach/cli.py` — 87 606 bytes, 41 functions, **43 `subprocess`
call sites** — routing fifteen platforms to third-party CLIs.

**Both repositories are MIT and self-consistent** (R02). Nineteen direct Python
dependencies are permissive except one: `browser-cookie3`, **LGPL**, which is
the package that reads session cookies out of a user's browser profile. It is an
optional extra.

**Three of the six programs Agent-Reach orchestrates carry no licence at all**
(R02): `public-clis/twitter-cli`, `rdt-cli` and `bilibili-cli`. Their READMEs
answer `200`, so they exist and are unlicensed rather than unreachable. They are
its default Twitter backend, its Reddit fallback and its preferred Bilibili
backend.

**This platform's own web reach is one HTML scraper** (R00). Four things called
search providers all search *inside* the platform; `tools/web_search` parses
DuckDuckGo HTML and already carries a fallback parser, which is the fingerprint
of markup that changed once.

**Everything an orchestrator owns already exists here** (R00): provenance twice,
the `OBSERVED → CANDIDATE → CORROBORATED` ladder, the trust boundary, six
caches, citations, freshness, contradictions, auth, RBAC, rate limiting at two
levels, observability, and `ProviderPrivacyPolicy` from K07.

## Decisions

### 1. A fourth provider declaration exists, and here is why

`src/research/providers.py` declares `ResearchProvider`. That makes four
declaration types in this repository, after `creative/providers.py`,
`model_engine/providers/` and `media/providers/base.py` — and the previous
programme's whole lesson was not to add one lightly.

**A research provider does not produce anything; it reports.** Its capabilities
— search, fetch a page, read a Reddit thread — are not creative tasks, and
declaring them in the creative vocabulary would be the category error ADR-030
avoided by refusing to declare `text_to_video` for a tool that assembles stock
footage.

**Rejected**: extending `CreativeProvider` with research tasks. It would put
`academic_search` beside `text_to_video` in one vocabulary, and the first router
to iterate that vocabulary would have to know which half it was looking at.

### 2. It reuses three existing types rather than copying them

| Reused | From | For |
|---|---|---|
| `LicenceRecord` | `creative/providers.py` | usage rights and their evidence |
| `ProviderPrivacyPolicy` | `creative/canvas/privacy.py` (K07) | where the data goes |
| `TrustLevel` | `security/trust.py` | retrieved content is data |

**Rejected**: a research-specific licence record, a research-specific privacy
policy, a fourth provenance system. STEP 9 forbids the last one explicitly;
the first two would be duplication of exactly the kind §3 of the previous
directive named.

### 3. The field is called `execution`, not `invocation`

Values: `IN_PROCESS`, `SUBPROCESS`, `HOSTED_SERVICE`.

ADR-031 recorded that `invocation` already reads two opposite ways in this
repository — *how the provider is called* in the media layer, *is the repository
licence copyleft* in the creative layer, because `adapt_declared()` computes it
from the licence. **A third meaning on the same word would be worse than the two
existing ones.**

Agent-Reach is `SUBPROCESS`. That is not a packaging preference: it is what R01
measured the repository to be.

### 4. Health is measured against the environment, and a blocked state names its repair

`health()` calls `importlib.util.find_spec`, `shutil.which` and `os.environ` —
it interrogates, it does not remember. Each missing condition carries the
gesture that fixes it, the way `moneyprinterturbo.health()` names its three.

Measured today:

| Provider | State | Missing |
|---|---|---|
| `existing_galsen_research` | **`AVAILABLE`** | — |
| `web_search_mcp` | **`BLOCKED`** | 4 conditions |
| `agent_reach` | **`BLOCKED`** | 3 conditions |

**Nothing is installed by this programme**, and no dependency was added. Whether
either candidate is ever enabled is an operator's decision.

### 5. No secret ever enters a declaration

`authentication` holds **names of environment variables**, never values. A
string containing `=`, or longer than 64 characters, is refused at construction.
Tests assert that neither `as_dict()` nor `health()` can leak a value that is
present in the environment.

### 6. No ranking, and no commercial clearance

`providers_serving()` returns providers in declaration order. `typical_latency_ms`
is `None` for all three, meaning **never measured** — never "fast". Ordering on
an absent number is what `routing.py` already refuses.

`LicenceRecord.commercial` is `UNKNOWN` for both candidates, so **neither is
commercially cleared**. For Agent-Reach the reason is recorded in the record
itself: three of the programs it orchestrates have no licence.

### 7. Retrieved content is data, and trust comes from the destination

`trust_level` derives from `ProviderPrivacyPolicy.data_destination`, and an
absent policy is `UNKNOWN`, which falls safe to `EXTERNAL`. **All three declared
providers are `EXTERNAL` today** — including the platform's own, because its web
search reaches `duckduckgo.com`.

That is STEP 6 expressed as a field rather than as a policy sentence: a web page,
a README, an issue, a search result cannot override system instructions.

## Consequences

**Positive.** The declaration costs one module. Nothing is installed, no
dependency is added, and the audits' findings live where a router can act on
them rather than in a document nobody reads at runtime. The platform's own
research capability is declared in the same format as the candidates, so routing
never has two ways of talking about a provider.

**Negative, stated rather than softened.** Both candidates are `BLOCKED` and
neither is commercially cleared, so this layer changes nothing a user can see
today. `agent_reach` is declared `SUBPROCESS` although no adapter shells out to
it yet — the declaration is ahead of the execution, deliberately, because R03
concluded most of its unique reach is unreachable from a server anyway.

**Neutral.** `web-search-mcp`'s SSRF guard is better than `tools/browser`'s
(which has none) and weaker than `acquisition/fetcher.py`'s. This ADR does not
resolve that; **R06 does**, and copying `fetch_page` before then would leave the
platform with two half-guards.

## What this ADR does not decide

- **Where the SSRF check lives** (R06). The three implementations differ on five
  axes and none dominates.
- **Whether `tools/web_search` is replaced.** It is not: R03 classified `ddgs`
  as a superior implementation *and* recorded that a working capability is not
  removed to land an integration. It becomes the fallback (R05).
- **Whether `browser-cookie3` is ever used.** Not planned; if it ever is, its
  LGPL version must be established first, because the metadata says `lgpl` in
  lowercase with no number.
- **The rights over retrieved content.** Per-source, unread, and the reason
  provenance (R07) has to record where each source came from.
