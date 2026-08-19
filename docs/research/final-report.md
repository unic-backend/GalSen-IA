# Research Orchestration Integration — final report

**Programme**: GALSEN-IA — RESEARCH ORCHESTRATION INTEGRATION DIRECTIVE
(16 steps, two mandatory rules). **12 volets, 18 phases, all completed.**
Plan → `docs/research/phase-plan.md`. Decision → **ADR-032**.

**Date**: 2026-08-19. Every figure below was measured on the day.

---

## The sentence this programme exists to have established

**Only one of the two candidates is a library, and neither can run here.**

`Agent-Reach` 1.5.0 exports exactly one class, whose only methods are `doctor()`
and `doctor_report()`. Its capability lives in an 87 606-byte `cli.py` with 43
`subprocess` call sites, routing fifteen platforms to third-party CLIs — three
of which carry **no licence at all**. Its own README advises a burner account,
because scripted access risks suspension.

Had the adapter been written first — the natural instinct — GalSen IA would have
acquired a dependency on eight unversioned external programs, a desktop Chrome
session it cannot have, and a discipline that is the exact negation of
`acquisition/fetcher.py`, which refuses a disguised user agent **in code**.

---

## Repository state

`main` at `9f80dbc` before the three programmes; this one sits on
`claude/unit-tests-notification-search-file-4z0ok1`. **9 commits, 25 files
changed, 5 360 insertions, 18 deletions** — 21 new files, 4 modified.

## Files created

**Code (8)** — `src/research/`: `__init__.py`, `providers.py`, `routing.py`,
`safety.py`, `sources.py`, `pipeline.py`, `cache.py`, `golden.py`,
`measurements.py`. **2 929 lines.**

**Tests (7)** — `tests/research/`, **219 tests**, 1 skipped.

**Documents (6)** — `docs/research/`: `phase-plan.md`, `audit.md`,
`repo-audit.md`, `licence-matrix.md`, `capability-comparison.md`,
`test-mapping.md`, this report — plus **ADR-032**.

## Files modified

Four: `CLAUDE.md` and `docs/architecture/overview.md` (ADR and test counts),
`docs/changelog/CHANGELOG.md`, `docs/memory/phase-plan.md`.

**No existing source file was touched.** Not one line of `src/` outside the new
package.

## Existing components reused

Nine, called rather than rewritten:

| Reused | For |
|---|---|
| `creative/providers.LicenceRecord` | usage rights and their evidence |
| `creative/canvas/privacy.ProviderPrivacyPolicy` (K07) | where the data goes |
| `security/trust` | retrieved content is data, hostile by default |
| `creative/language/observation` | the `OBSERVED → CANDIDATE → CORROBORATED` ladder |
| `creative/jobs.fingerprint` | content hashing |
| `acquisition/record` | the provenance format and its minimum fields |
| `creative/cache.CreativeCache` | the whole cache mechanism |
| `creative/mvp` | the outcome vocabulary |
| `api/rate_limiter`, `tools/web_search` | rate limiting, at two levels |

## New components

**One package, seven modules.** STEP 4 alone lists eleven pieces of provider
metadata and STEP 5 ten routing criteria; the audits reduced what was genuinely
missing to a provider declaration, a router, an address guard, a source record,
a pipeline, a research cache key, and a runnable case set.

## Providers evaluated

| Repository | Licence | State here | Verdict |
|---|---|---|---|
| `Panniantong/Agent-Reach` 1.5.0 | MIT, © 2025 Agent Eyes | **`BLOCKED`**, 3 conditions | declared `SUBPROCESS`, not adopted |
| `sydasif/web-search-mcp` 0.6.3 | MIT, © 2026 Syed Asif | **`BLOCKED`**, 4 conditions | declared `IN_PROCESS`, not installed |
| `existing_galsen_research` | this repository | **`AVAILABLE`** | the only provider that can run |

## Licence findings

**19 direct Python dependencies**, read from PyPI, zero fetch failures: 10 MIT,
5 Apache-2.0, 2 BSD-3-Clause, 1 BSD-2-Clause, 1 Unlicense, and **1 LGPL**.

**The single copyleft entry is `browser-cookie3`** — the package that reads
session cookies out of a user's browser profile, the most sensitive dependency
in either project. It is an optional extra, so a required install triggers
nothing; its LGPL **version is `UNKNOWN`**, the metadata saying `lgpl` in
lowercase with no number.

**Three of the six programs Agent-Reach orchestrates carry no licence file** —
`public-clis/twitter-cli`, `rdt-cli`, `bilibili-cli`. Their READMEs answer
`200`: they exist and are unlicensed, not unreachable. They are its default
Twitter backend, its Reddit fallback and its preferred Bilibili backend.

Checked rather than assumed: `jina-ai/reader`'s `LICENSE` opens with *"All
rights reserved"* — a copyright header **above** the Apache-2.0 text.

**Four hosted services** (Jina Reader, Exa, Xquik, DuckDuckGo) have **terms, not
licences**, and none was read. Rights over *retrieved content* are per-source
and also `UNKNOWN` — which is why provenance records where each source came
from.

## Tests added

**219**, 1 skipped — 38 providers, 66 routing, 38 safety, 39 sources and
pipeline, 14 STEP 12 gaps, 10 golden, 13 measurements, plus the shared fixtures.

## Total, passed, failed, skipped

```
python -m pytest -q
1 failed, 6569 passed, 12 skipped, 3 deselected in 395.66s   (R09 checkpoint)
```

6 363 → **6 588** across the programme. The single failure is the `v0.1.0` tag,
never pushed; it predates all four programmes and fails identically on `main`.

## Regression status

**PASS**, across six full-suite runs — one per pair of phases.

**One regression was introduced and fixed.** `tests/research/test_providers.py`
shared a basename with `tests/media/test_providers.py`, and this repository has
no `__init__.py` under `tests/`, so pytest requires unique basenames and
**interrupted collection entirely** — no test ran, old or new. The file passed
in isolation, which is exactly why the permanent rule demands the whole suite
rather than the subset near the change. Renamed; `--collect-only` went from
`1 error` to 6 413 collected.

**Two guards caught defects of mine**, and both were right:
`test_published_numbers` refused the ADR count until 32 → **33**, and a test I
wrote caught `generate_queries` deduplicating on the facet instead of on the
constructed query.

## Performance measurements

Measured, and **only what could honestly be measured**:

| Operation | Time |
|---|---|
| `generate_queries` | **0.0006 ms** |
| `cache.lookup` | **0.0036 ms** |
| `check_url` (literal) | **0.0073 ms** |
| `normalize` a source | **0.0161 ms** |
| `as_data` wrap | **0.0227 ms** |
| `route` a web search | **0.164 ms** |
| Full pipeline, no search | **0.163 ms** |

Cache: 50 entries written, **50 hits on written, 0 on absent** — and the report
declares the exercise **synthetic**, because a rate measured on keys you just
wrote says something about the cache and nothing about usage.

Machine: 4 cores, 15.7 GiB, GPU `NOT_MEASURED`.

**Five of STEP 13's eight measurements return `NOT_MEASURED` with their
reason**: search latency, fetch latency, provider failure rate, fallback rate,
network usage. Nothing executes, so a number in those columns would be invented.
**No performance improvement is claimed**: nothing was compared to a before.

## Security status

No new dependency, no new network call, no new secret, no external code
imported. Both repositories were treated as **data** (STEP 10): nothing cloned,
installed or executed.

**The security decision of the programme** is where the address check lives.
Three page-fetch implementations existed and none dominated — `tools/browser`
checks nothing and disguises its agent, `fetch_page` blocks literal private IPs
only, `acquisition/fetcher.py` guards politeness and redirects but only the
loopback. `src/research/safety.py` now holds the check once, blocking internal
ranges **as literals and as resolved names** — closing the hole web-search-mcp
names in its own docstring.

**What it does not claim**: the DNS re-resolution window stays open. Closing it
means connecting to the address already checked, which belongs to the HTTP
client. `safety_report()` says so under `not_guaranteed`.

Retrieved content enters as `EXTERNAL` and the caller cannot choose otherwise —
`as_data()` has no level parameter, and a test asserts it.

## Privacy status

`ProviderPrivacyPolicy` (K07) is reused, not rebuilt. All three providers'
`data_destination` is a third-party host or `UNKNOWN`, so **all three are
`EXTERNAL`** — including the platform's own, because its web search reaches
`duckduckgo.com`. A request carrying personal data is **`REFUSED`** for every
provider today, and the refusal names the gesture that lifts it.

## Known limitations

- **Neither candidate can run here**, and neither is commercially cleared.
- **Nothing executes**, so no latency, failure rate or fallback rate exists.
- **Timeout is untested** (STEP 12 case 13), recorded as a gap rather than
  faked.
- **No API route was added**; the layer is a model, exposing it is a separate
  decision.
- **Twelve capabilities are declared, three are routable** — `web_search`,
  `page_fetch`, `github_read`, all served by the platform's own tools.

## `UNKNOWN` items

- Both repositories' exact commit — the GitHub tree API answers `403` here.
- **Transitive dependency licences** — 19 direct entries read, their trees not.
- `browser-cookie3`'s LGPL version.
- The terms of Jina Reader, Exa, Xquik and DuckDuckGo.
- Rights over retrieved content, per source.
- Every runtime behaviour of both projects: **nothing was executed.**

## Next phase

None in this programme. What is owed, and named rather than forgotten:

1. **Install one provider and measure it.** `web_search_mcp` is `IN_PROCESS`
   and needs one `pip install` plus three optional variables; it would turn five
   `NOT_MEASURED` rows into figures and make the timeout case testable.
2. **Read one service's terms** — Exa or DuckDuckGo — to move
   `commercial_status` off `UNKNOWN` for the only routable capability.
3. **The two-layer field discrepancy** (`min_vram_gb`, `invocation`) recorded in
   ADR-031 remains open; this programme avoided a third by naming its field
   `execution`.
4. **`git push origin v0.1.0`** — the single red test, in four programmes now.

---

## What was refused, and stays refused

No claim that either project provides provenance, a knowledge ladder, a trust
boundary, cross-source comparison, freshness, citations or rate limiting. They
provide **reach**; the judgement stays here.

Nothing was inserted into the knowledge base — `propose_for_knowledge()` returns
a `DRAFT` and ADR-021's human approval gate is not bypassed. No query was
widened. No answer was fabricated: the pipeline's `answer` is `None` and its
status `UNKNOWN`. And no research result becomes a creative instruction — STEP
15 is held by a test, not by a sentence.

**GalSen IA did not become Agent-Reach or Web-Search-MCP.** It gained a provider
declaration, a router that refuses three different ways, one address guard where
there were two halves, and a record of which programs it may not lawfully use.
