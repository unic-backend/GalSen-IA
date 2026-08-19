# R01 — Agent-Reach and web-search-mcp, audited from source

Research Orchestration directive, **STEP 2**. Read on 2026-08-19 from
`raw.githubusercontent.com`, file by file. **Nothing was cloned, installed or
executed** — STEP 10's rule, and the same discipline the two previous programmes
used.

The dependency licences are audited separately in R02, as STEP 2 requires.

---

## The one-line answer

**They are not the same kind of thing, and only one of them is a library.**

| | `Panniantong/Agent-Reach` | `sydasif/web-search-mcp` |
|---|---|---|
| Version | **1.5.0** | **0.6.3** |
| Licence | MIT, © 2025 Agent Eyes | MIT, © 2026 Syed Asif |
| Python | ≥ 3.10 | ≥ 3.11 |
| What it is | **a CLI that orchestrates other people's CLIs** | **a FastMCP server with an importable package** |
| Public API | `AgentReach.doctor()` and `.doctor_report()` — **that is all** | 10 MCP tools over typed modules |
| Where the capability lives | `agent_reach/cli.py`, **87 606 bytes, 41 functions** | `web_search_mcp/{search,social,tools}/` |
| Integration mode | out-of-process, shelling out | importable, or MCP |

---

## R01.1 — `Panniantong/Agent-Reach` v1.5.0

### Capabilities — 15 platforms, most of them behind a login

Read from the README's own table, not summarised from the description:

| Zero-config | Unlocked by configuration |
|---|---|
| Web page reading, YouTube transcripts + search, RSS/Atom, V2EX, GitHub (public repos + search), Twitter (single tweet), Bilibili (search + details) | Web-wide semantic search (MCP), Twitter search/timeline, Bilibili subtitles, **Reddit** (no anonymous path at all), **Facebook**, **Instagram**, **Xiaohongshu**, LinkedIn details, Xueqiu, Xiaoyuzhou podcast transcription |

**Six channels work without configuration. Five platforms require a logged-in
browser session**: Reddit, Facebook, Instagram, Xiaohongshu, Twitter.

### The architecture, which decides everything else

`agent_reach/__init__.py` exports exactly one class. `agent_reach/core.py` is
**1 277 bytes**, and `AgentReach` has **two methods: `doctor()` and
`doctor_report()`**. There is no importable `search()`, no `fetch()`, no
`search_platform()`.

Everything else lives in `cli.py` — 87 KB, 41 functions, **43 uses of
`subprocess`**. Each platform routes to a preferred and a fallback **external
CLI**:

```
web       → Jina Reader (hosted service, r.jina.ai)
twitter   → twitter-cli ▸ OpenCLI
reddit    → OpenCLI ▸ rdt-cli        (no anonymous path)
facebook  → OpenCLI
instagram → OpenCLI
bilibili  → bili-cli ▸ OpenCLI
xhs       → OpenCLI ▸ xiaohongshu-mcp ▸ xhs-cli
```

**So "integrating Agent-Reach" is not integrating one MIT Python package.** It
is adopting a router over roughly eight third-party programs — several installed
through `npm install -g` — each with its own licence, maintenance and terms
position. R02 audits those separately; R03 decides whether any of it is worth it.

### Runtime requirements

`requests`, `feedparser`, `python-dotenv`, `loguru`, `pyyaml`, `rich`,
**`yt-dlp[default]`**. Optional extras: `playwright`, **`browser-cookie3`**,
`mcp[cli]`. Plus, outside Python: **Node.js and `npm install -g`** for OpenCLI
and `mcporter`, and a **desktop Chrome session** for five platforms.

### Failure modes and maintenance — the project says it itself

Two sentences from its own README are worth quoting because they are the
honest, load-bearing ones:

> *"2026年3月一批单平台 CLI 集体停更，我们换了路由"* — in March 2026 a batch of
> single-platform CLIs went unmaintained together, and the routing was changed.

> *"通过脚本/API 调用**存在被平台检测并封号的风险**。请务必使用**专用小号**"* —
> scripted access risks account suspension; **use a burner account, never your
> main one.**

**The second one is a finding, not a caveat.** A project that advises a
throwaway account is telling you its capability works against the platform's
terms in practice. Its value proposition says the same thing in the positive:
Twitter's API costs money → scrape it; Reddit returns 403 → route around it;
Xiaohongshu requires a login → open it anyway; Bilibili blocks yt-dlp with 412 →
use a different client.

**This collides directly with what this repository already decided.**
`src/acquisition/fetcher.py` refuses a user agent that disguises itself **in
code**, fetches `robots.txt` before the page, and refuses cross-domain
redirects — because *"a site cannot apply a rule to an agent that is in
disguise"*. Agent-Reach's core value is the negation of that discipline. That is
not a reason to refuse it outright; it is a reason the decision belongs in an
ADR rather than in an import.

### Authentication and credential handling

Cookies and tokens live in `~/.agent-reach/config.yaml`, mode 600, local only —
stated clearly, and the README says the code is auditable. It also states it does
**not** perform the Xiaohongshu login itself and does **not** read Xiaohongshu
browser cookies; OpenCLI reuses a Chrome session the user already controls.

**That is a careful design, and it is still a large surface for this platform**:
integrating it means GalSen IA is adjacent to a store of third-party session
cookies for a user's social accounts. `creative/canvas/privacy.py` is exactly the
place that has to record it.

### Security implications

- `browser-cookie3` (optional extra) reads cookies out of the user's local
  browser profile.
- `npm install -g` of third-party CLIs is code execution from another ecosystem.
- Web reading goes through **Jina Reader**, a hosted third party: page content
  and the URL leave the machine. `data_destination = THIRD_PARTY_HOST`.
- 43 `subprocess` call sites.

---

## R01.2 — `sydasif/web-search-mcp` v0.6.3

### Capabilities — 10 tools, typed, importable

| Tool | What it does | Auth |
|---|---|---|
| `search_web` | DuckDuckGo via **`ddgs`**, or Exa; domain scoping, date filter, news mode, region | none / `EXA_API_KEY` |
| `fetch_page` | Extraction via **trafilatura**, several output formats, **SSRF check** | none |
| `search_reddit` | Keyless, RSS + Shreddit enrichment | **none** |
| `search_hackernews` | Algolia HN API | none |
| `search_github` | Issues and PRs | `gh` CLI or `GITHUB_TOKEN` |
| `get_github_issue` | Full thread, sorted by reactions | same |
| `search_x` | Xquik API **or vendored Bird CLI** | session cookies or `XQUIK_API_KEY` |
| `search_linkedin` | DuckDuckGo + Jina Reader | none |
| `search_arxiv` | Lucene field prefixes (`au:`, `ti:`, `cat:`, `abs:`) | none |
| `search_wikipedia` | MediaWiki API | none |

**Academic search exists here and nowhere else** — R00 recorded `arxiv` as
`UNKNOWN` for this platform, and this is the answer.

**Reddit is keyless here and impossible without a login in Agent-Reach.** That
is the sharpest capability difference between the two, and R03's material.

### Its SSRF guard, read rather than believed

`fetch_page` advertises *"SSRF protection (blocks private/internal IPs)"*, and
it is real: `web_search_mcp/_http/client.py::validate_url` refuses non-`http(s)`
schemes and blocks loopback, private, link-local and reserved ranges, including
IPv4-mapped IPv6.

**And its own docstring names the hole:**

> *"Domain names are resolved by the server/OS, not here."*

So it blocks **literal IP addresses only**. A hostname that resolves to
`127.0.0.1` passes the check. That is the classic DNS-rebinding gap, and the
module is honest about it rather than hiding it.

**Judged against this repository**: better than `tools/browser/tool.py`, which
has no check at all; weaker than `acquisition/fetcher.py`, which additionally
refuses disguised agents, cross-domain redirects, undeclared content types and
plain HTTP off the loopback.

### What its own linter configuration admits

`pyproject.toml` globally ignores `S603`, `S607`, `S310`, `S314`, with per-file
ignores on top:

```
"web_search_mcp/social/reddit/client.py" = ["S310"]
"web_search_mcp/social/reddit/parsers.py" = ["S314"]
"web_search_mcp/social/x.py"              = ["S310", "S603"]
"web_search_mcp/social/github.py"         = ["S310", "S603", "S607"]
```

`S310` is *"audit URL open for permitted schemes"* — the SSRF rule. `S603` and
`S607` are subprocess and partial-path execution. `S314` is unsafe XML parsing.

**Read plainly**: the SSRF discipline that `fetch_page` implements is silenced
in the social modules, three of which open URLs directly, and Reddit's parser
has XML parsing exempted. This is not deception — the ignores are explicit and
per-file — but it means **`fetch_page`'s guard cannot be assumed to cover
`search_reddit`, `search_x` or `search_github`**, and any adoption has to treat
those paths separately.

### Runtime requirements

`arxiv`, `ddgs`, `exa-py`, `fastmcp`, `httpx`, `pydantic`, `pydantic-settings`,
`tenacity`, `trafilatura`. Optional outside Python: **`gh` CLI**, and
**Node.js 22+** for the vendored Bird CLI (unless `XQUIK_API_KEY` is set). The
package ships `vendor/**/*` as package data.

### Authentication

`EXA_API_KEY` (Exa, commercial), `GITHUB_TOKEN` (optional, rate limits),
`AUTH_TOKEN` + `CT0` (**x.com session cookies**), `XQUIK_API_KEY` (commercial
alternative). Environment variables throughout — no cookie store of its own.

### Failure modes

`ddgs` is a maintained library rather than HTML scraping, so `search_web` fails
as an exception rather than as an empty result — unlike this repository's
`tools/web_search`. `fetch_page` falls back from httpx to **Exa**, which means a
failed direct fetch silently becomes a **third-party server-side render**: the
URL and its content go to `exa.ai`. That fallback is a privacy transition, not
just a reliability one, and it happens without the caller asking.

---

## What R01 establishes, before any comparison

1. **Only one of the two is importable Python.** Agent-Reach's public API is a
   health check; its capability is a CLI. Any use of it is `OUT_OF_PROCESS`.
2. **Both reach further than this platform can today**, and both do it partly
   through third-party hosted services (Jina Reader, Exa) and third-party
   programs (OpenCLI, `gh`, Bird CLI).
3. **Reddit, academic search and Wikipedia are real capability gains**;
   `search_web` and page fetching **overlap** with what already exists here.
4. **Both carry a session-cookie surface for social platforms**, and one of them
   recommends a burner account.
5. **Neither's security posture can be adopted wholesale**: one negates this
   repository's fetch discipline by design, the other silences the SSRF rule in
   the modules that need it most.

R02 audits the dependencies. R03 classifies each capability
`UNIQUE_CAPABILITY` / `OVERLAPPING_CAPABILITY` / `SUPERIOR_IMPLEMENTATION` /
`FALLBACK_CAPABILITY` / `UNNECESSARY_DUPLICATION`.

## Method note

Read from raw files at each repository's default branch. **Version pinning is
`UNKNOWN`**: the GitHub tree API is not reachable from this session (`403`), so
no commit SHA was read — only the declared versions, `1.5.0` and `0.6.3`.
Nothing was executed, so **every runtime behaviour above is a reading, not a
measurement**.
