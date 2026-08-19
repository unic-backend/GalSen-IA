# R02 — licence and dependency matrix, audited separately

Research Orchestration directive, **STEP 2**, whose instruction is literal:

> *Do not assume that "MIT" automatically applies to every transitive dependency
> or external service. **Audit dependencies separately.***

Measured on 2026-08-19. Python licences read from **PyPI package metadata**
(`license_expression`, `license`, or the `License ::` classifier); repository
licences read from each project's own `LICENSE` file.

This is a gate, and it does not close where the previous programme's did.

---

## 1. The two repositories

| Repository | Licence | Read from |
|---|---|---|
| `Panniantong/Agent-Reach` **1.5.0** | **MIT** | `LICENSE`, © 2025 Agent Eyes; `pyproject.toml` agrees (`license = {text = "MIT"}`) |
| `sydasif/web-search-mcp` **0.6.3** | **MIT** | `LICENSE`, © 2026 Syed Asif; README §License agrees |

**Both are consistent with themselves** — unlike `abdrsan/Higgsfield-Open` in
the canvas programme, whose `LICENSE` said MIT and whose manifest said `null`.

---

## 2. Python dependencies

Nineteen distinct packages across both projects. **Zero fetch failures.**

### Agent-Reach — required

| Package | Version | Licence | Class |
|---|---|---|---|
| `requests` | 2.34.2 | Apache-2.0 | permissive |
| `feedparser` | 6.0.14 | BSD-2-Clause | permissive |
| `python-dotenv` | 1.2.3 | BSD-3-Clause | permissive |
| `loguru` | 0.7.3 | MIT | permissive |
| `pyyaml` | 6.0.3 | MIT | permissive |
| `rich` | 15.0.0 | MIT | permissive |
| `yt-dlp` | 2026.7.4 | **Unlicense** | public-domain dedication |

### Agent-Reach — optional extras

| Package | Version | Licence | Class |
|---|---|---|---|
| `playwright` | 1.62.0 | Apache-2.0 | permissive |
| `mcp` | 2.0.0 | MIT | permissive |
| **`browser-cookie3`** | 0.20.1 | **LGPL** | **copyleft** |

### web-search-mcp — required

| Package | Version | Licence | Class |
|---|---|---|---|
| `arxiv` | 4.0.1 | MIT | permissive |
| `ddgs` | 9.15.0 | MIT | permissive |
| `exa-py` | 2.18.1 | MIT | permissive |
| `fastmcp` | 3.4.7 | Apache-2.0 | permissive |
| `httpx` | 0.28.1 | BSD-3-Clause | permissive |
| `pydantic` | 2.13.4 | MIT | permissive |
| `pydantic-settings` | 2.15.0 | MIT | permissive |
| `tenacity` | 9.1.4 | Apache-2.0 | permissive |
| `trafilatura` | 2.2.0 | Apache-2.0 | permissive |

### What that produces

| Licence | Count |
|---|---|
| MIT | 10 |
| Apache-2.0 | 5 |
| BSD-3-Clause | 2 |
| BSD-2-Clause | 1 |
| Unlicense | 1 |
| **LGPL** | **1** |

**One copyleft entry, and it is the cookie reader.** `browser-cookie3` is the
package that reads session cookies out of a user's local browser profile — the
single most sensitive dependency in either project — and it is the single
copyleft one.

It is an **optional extra**, so a required-set installation of Agent-Reach
triggers no copyleft obligation. But this is the same shape as the
MoneyPrinterTurbo finding recorded in `docs/providers/licence-matrix.md`: a
permissive repository whose most load-bearing capability path is copyleft. **The
repository's licence is not its capability's licence**, and the answer differs
depending on which extra is installed.

### Three limits on the finding above

1. **Direct dependencies only.** Nineteen manifest entries were read; their
   transitive trees were not. Transitive licence status is **`UNKNOWN`**, and it
   stays `UNKNOWN` rather than being reported clean.
2. **Registry metadata, not `LICENSE` files.** This is `DECLARED` evidence, not
   `AUTHORITATIVE`.
3. **`browser-cookie3` declares `lgpl` in lowercase, with no version.** LGPL-2.1
   and LGPL-3.0 differ in ways that matter, and **which one applies is
   `UNKNOWN`** from the metadata alone.

---

## 3. The dependency surface the manifests do not declare

**This is where the two projects diverge, and it is the finding of R02.**

`web-search-mcp` declares its dependencies in `pyproject.toml`. `Agent-Reach`
declares seven Python packages and then, at runtime, **routes to third-party
programs that appear in no manifest at all** — installed via `npm install -g`,
`pip install`, or a hosted endpoint (R01: 43 `subprocess` call sites).

Audited by fetching each project's own licence file:

| Orchestrated by Agent-Reach | Licence | Read from |
|---|---|---|
| **Jina Reader** (`jina-ai/reader`) — web page reading | **Apache-2.0** | `LICENSE` — the file opens with *"Copyright 2020-2024 Jina AI Limited. All rights reserved."*, which is a copyright header **above** the Apache-2.0 text, not a reservation |
| **OpenCLI** (`jackwener/opencli`) — Reddit, Facebook, Instagram, Xiaohongshu | **Apache-2.0** | `LICENSE` |
| **xiaohongshu-mcp** (`xpzouying/xiaohongshu-mcp`) | **Apache-2.0** | `LICENSE` |
| **twitter-cli** (`public-clis/twitter-cli`) | **none found** | 404 on `LICENSE`, `.md`, `.txt`, `COPYING`, on `main` **and** `master` |
| **rdt-cli** (`public-clis/rdt-cli`) | **none found** | same |
| **bilibili-cli** (`public-clis/bilibili-cli`) | **none found** | same |

The three `public-clis/*` repositories **exist** — their `README.md` answers
`200` on both branches — they simply carry no licence file. That is the
distinction the canvas programme's audit had to make too, and it is the
difference between "unreachable" and "unlicensed".

**Absence of a grant reserves every right.** Agent-Reach's *default* backend for
Twitter, its *fallback* for Reddit, and its *preferred* backend for Bilibili are
three programs nobody has licensed.

### Why this matters even though nothing would be vendored

GalSen IA would not redistribute these programs; it would tell an operator to
install them, or shell out to them. Running an unlicensed program is a weaker
exposure than shipping one — but the platform would be **routing a user's
research through software with no usage grant**, and recommending its
installation in documentation. That is a decision for an ADR, not an assumption.

### The positive contrast, recorded because it is unusual

`web-search-mcp` **vendors** a Node CLI at
`web_search_mcp/vendor/bird-search/`, and does it correctly:

```json
"license": "MIT",
"attribution": "Based on @steipete/bird v0.8.0 by Peter Steinberger (MIT License)"
```

with the upstream `LICENSE` file kept beside it (MIT, © 2025 Peter Steinberger).
Vendoring *is* redistribution, so this is the case where the licence matters
most — and it is the one handled best of everything audited in this programme.

---

## 4. External services — terms, not licences

Four hosted services are involved, and **a service has terms of use, not an
open-source licence**. None was read; each is `UNKNOWN` until it is.

| Service | Used by | Status |
|---|---|---|
| **Jina Reader** (`r.jina.ai`) | Agent-Reach (web reading), web-search-mcp (LinkedIn) | Repository Apache-2.0; **hosted-endpoint terms `UNKNOWN`** |
| **Exa** (`exa.ai`) | web-search-mcp — search **and the `fetch_page` fallback** | Commercial, `EXA_API_KEY`; **terms `UNKNOWN`** |
| **Xquik** (`xquik.ai`) | web-search-mcp `search_x` | Commercial, `XQUIK_API_KEY`; **terms `UNKNOWN`** |
| **DuckDuckGo** | both, via `ddgs` or HTML | **Terms `UNKNOWN`** — and this repository already queries it through `tools/web_search` |

**The platform terms of the searched sites are a separate question again**, and
R01 already found Agent-Reach's own README answering it: scripted access to
Twitter, Xiaohongshu and the rest *"risks detection and account suspension"*,
with the advice to use a burner account.

**Licence, service terms, and platform terms are three different things.** The
same three-way distinction the platform already applies to models — repository
licence ≠ weight licence ≠ dataset licence ≠ output rights.

---

## 5. Commercial restrictions

| Question | Answer |
|---|---|
| May either repository be used commercially? | **Yes** — MIT, both. |
| May the required dependency sets be used commercially? | **Yes** — all permissive. |
| Does any required dependency impose copyleft? | **No.** |
| Does any *optional* dependency impose copyleft? | **Yes — `browser-cookie3`, LGPL, version `UNKNOWN`.** |
| May the orchestrated CLIs be used at all? | **`UNKNOWN` for three of six** — no grant exists. |
| May the hosted services be used commercially? | **`UNKNOWN`** — no terms read. |
| May the *retrieved content* be used? | **`UNKNOWN`, and it is per-source.** A Reddit thread, an arXiv abstract and a Wikipedia article carry three different answers, none of which any licence above governs. |

**The last row is the one that will matter most in production**, and it is the
one no dependency audit can settle. It belongs to R07's provenance work: a
retrieved source has to carry where it came from, so the rights question can be
asked later about the right thing.

---

## What the gate lets through

- **Both repositories**: licences clean and self-consistent.
- **Both required dependency sets**: permissive, no obligation triggered.
- **`browser-cookie3`**: only with a deliberate decision, recorded, and with the
  LGPL version established first.
- **Three of the six orchestrated CLIs**: **not** without a grant.
- **The hosted services**: not without reading their terms.

R03 compares capabilities and decides what, if anything, is worth adopting.
