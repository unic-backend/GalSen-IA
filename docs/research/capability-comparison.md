# R03 — capability comparison

Research Orchestration directive, **STEP 3**. Written 2026-08-19, after the
three audits, and deliberately not before.

STEP 3's classification: **UNIQUE_CAPABILITY / OVERLAPPING_CAPABILITY /
SUPERIOR_IMPLEMENTATION / FALLBACK_CAPABILITY / UNNECESSARY_DUPLICATION**, and
its rule: *"Do not install both versions of the same capability if one existing
GalSen IA provider is already better."*

**Three systems are being compared, not two.** GalSen IA is one of the
candidates for every row, and R00 measured what it actually has.

---

## The comparison

| Capability | GalSen IA today | Agent-Reach | web-search-mcp | Verdict |
|---|---|---|---|---|
| **General web search** | `tools/web_search` — scrapes DuckDuckGo **HTML**, one provider, rate-limited, 300 s TTL cache | via MCP, "free, no key" | `ddgs` (maintained library) + Exa fallback, domain scoping, date filter, news mode, region | **SUPERIOR_IMPLEMENTATION → web-search-mcp** |
| **Page fetch / extraction** | `tools/browser` — `urlopen`, crude HTML stripping, **no SSRF check**; `acquisition/fetcher.py` — disciplined but purpose-bound | Jina Reader (hosted third party) | `trafilatura` + literal-IP SSRF check, several output formats | **OVERLAPPING**, and see the split verdict below |
| **Reddit** | none | login required, **no anonymous path** | **keyless**, RSS + Shreddit | **UNIQUE_CAPABILITY → web-search-mcp** |
| **Academic (arXiv)** | none | none | `search_arxiv`, Lucene field prefixes | **UNIQUE_CAPABILITY → web-search-mcp** |
| **Wikipedia** | none | none | MediaWiki API | **UNIQUE_CAPABILITY → web-search-mcp** |
| **Hacker News** | none | none | Algolia HN API | **UNIQUE_CAPABILITY → web-search-mcp** |
| **GitHub** | `tools/github` — read repos, issues, PRs; token from env at call time; anonymous fallback | public repos + search, login for private | issue/PR **search**, full threads sorted by reactions | **OVERLAPPING → extend what exists** |
| **YouTube transcripts** | none | `yt-dlp`, zero config | none | **UNIQUE_CAPABILITY → Agent-Reach** |
| **RSS / Atom** | none | `feedparser`, zero config | none | **UNIQUE_CAPABILITY → Agent-Reach** |
| **X / Twitter** | none | session cookies | Xquik API or vendored Bird CLI (cookies) | **OVERLAPPING** — both need credentials |
| **LinkedIn** | none | Jina Reader + login for details | DuckDuckGo + Jina Reader, keyless | **OVERLAPPING** |
| **Facebook, Instagram, Xiaohongshu, Bilibili, V2EX, Xueqiu, podcasts** | none | via OpenCLI / bili-cli, desktop Chrome session | none | **UNIQUE_CAPABILITY → Agent-Reach**, and see the caveat |
| **Provenance, trust, status ladder, cache, citations, freshness, contradictions** | **all present** (R00) | none | none | **UNNECESSARY_DUPLICATION if adopted** |

---

## The four conclusions that follow

### 1. `search_web` and page fetching are where this platform is weakest, and the overlap is real

R00 found exactly one component reaching the open web as a search engine, and it
**parses DuckDuckGo HTML** — with a fallback parser already in it, which is the
fingerprint of markup that has changed once before. `ddgs` is a maintained
library doing the same job against the same engine.

STEP 3 says not to install a second version of a capability an existing provider
serves better. **Here the existing provider does not serve it better**, and the
honest classification is `SUPERIOR_IMPLEMENTATION` for the candidate.

That does **not** mean deleting `tools/web_search`. Every provider is additive
and replaceable (the mandatory rule), and a tool that works today is not removed
because a better one exists on paper. It means the router should prefer the
better one **when it is available**, and fall back to the existing one — which
is `FALLBACK_CAPABILITY`, and the first genuine use of R05's fallback path.

### 2. Page fetching splits, and the split is the security decision

Three implementations, three different disciplines:

| | Scheme check | Private-IP block | robots.txt | Disguised agent refused | Cross-domain redirect refused |
|---|---|---|---|---|---|
| `tools/browser` | no | no | no | **no — it disguises itself** | no |
| `web-search-mcp` `fetch_page` | **yes** | **literal IPs only** | no | no | no |
| `acquisition/fetcher.py` | **yes** | loopback rule only | **yes** | **yes** | **yes** |

**No single one of them is best**, and that is the useful finding. The candidate
brings the private-IP block this repository has nowhere; `acquisition/fetcher.py`
brings the politeness discipline the candidate has nowhere; and the candidate's
own docstring admits its guard covers **literal IP addresses only**, because
hostnames are resolved by the OS.

Verdict: **OVERLAPPING_CAPABILITY, and neither is adopted as-is.** R06 decides
whether the address check is lifted into a shared guard that both
`acquisition/fetcher.py` and any research provider pass through. Copying
`fetch_page` wholesale would import a guard weaker than the one already here in
one dimension and stronger in another — which is how a platform ends up with two
half-guards.

### 3. Agent-Reach's unique capabilities are real, and most are unreachable here

YouTube transcripts and RSS are genuine gains at zero configuration. Everything
else it uniquely offers — Reddit, Facebook, Instagram, Xiaohongshu, Bilibili —
needs, per R01:

- a **desktop Chrome session** the platform does not have;
- **third-party CLIs installed with `npm install -g`**, three of which carry
  **no licence at all** (R02);
- a **burner account**, on its own author's advice, because scripted access
  risks suspension.

**So the classification is `UNIQUE_CAPABILITY` and the practical answer is
`BLOCKED`**, for reasons that have nothing to do with code quality. A server-side
platform cannot reuse a desktop browser session, and this repository already
decided — in `acquisition/fetcher.py`, in code rather than in a policy document
— that it does not disguise its agent to get past a refusal.

**Reddit is the sharpest illustration in the whole comparison.** Agent-Reach
reaches it only with a logged-in session; web-search-mcp reaches it **keyless**,
through RSS. Same capability, opposite feasibility here.

### 4. Everything the orchestrator owns is already built, and adopting either project's version would be duplication

Neither candidate carries provenance, a knowledge-status ladder, a trust
boundary, cross-source comparison, freshness, citations, caching, RBAC or rate
limiting at the platform level. **GalSen IA has all of them** (R00).

That is not a deficiency in the candidates — they are *research reach*, and the
directive says to treat them as providers. It is the reason the integration is
small: **what they add is reach; what the platform keeps is judgement.**

---

## What this means for R04 and R05

**Recommended shape, to be decided in ADR-032:**

| Provider | Mode | Why |
|---|---|---|
| `existing_galsen_research` | in-process | `tools/web_search`, `tools/browser`, `tools/github`, `acquisition/fetcher` — works today, no new dependency |
| `web_search_mcp` | out-of-process (MCP) or importable | The only candidate that is a library; brings Reddit, arXiv, Wikipedia, HN, and a better `search_web` |
| `agent_reach` | out-of-process (CLI) only | No importable API exists — its public class has two methods, both health checks |

**Nothing is installed by this programme.** R04 declares the abstraction, R05
the routing; whether either provider is ever enabled is an operator's decision,
and `check_health()` must report `BLOCKED` with its reason until then — the same
way `moneyprinterturbo.health()` names its three missing conditions.

### The three verdicts recorded as refusals

- **`tools/web_search` is not deleted**, even though `ddgs` is better. Removing a
  working capability to land an integration is what the mandatory rule forbids.
- **`fetch_page` is not copied**, even though it has the SSRF check this
  repository lacks. R06 decides where that check lives.
- **Agent-Reach's social platforms are not pursued**, even though they are
  unique. A desktop Chrome session, three unlicensed CLIs and a burner account
  are not an integration path for a server-side platform.

## What stays `UNKNOWN`

- Whether `ddgs` is actually more reliable than the HTML scraper **here** —
  nothing was executed, and R10 measures rather than assumes.
- Whether Exa, Xquik or Jina Reader may be used at all — terms unread (R02).
- Whether the LGPL version of `browser-cookie3` matters — the extra is not
  planned, so the question stays open rather than answered.
- Every latency, failure-rate and cache-hit figure. **No performance claim is
  made in this document**, because none has been measured.
