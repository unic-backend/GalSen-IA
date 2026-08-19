# R09.1 — STEP 12's eighteen cases, mapped before any was written

Research Orchestration directive, **STEP 12**. Mapped on 2026-08-19.

**The mapping came first on purpose.** Many of STEP 12's eighteen cases describe
properties the tests written during R04–R08 already assert. Writing a second
`SSRF protection` test beside an existing one would inflate the count without
adding a line of coverage, and a count that grows without coverage is worse than
no count. The MoneyPrinterTurbo programme's `golden-mapping.md` established this
order; it is followed here.

**Fourteen of eighteen were already covered. Three were written. One is not
covered, and the reason is stated rather than worked around.**

---

## The mapping

| # | STEP 12 case | Covered by | Status |
|---|---|---|---|
| 1 | Provider discovery | `test_research_providers.py::TestSelection` (5 tests) | **covered** |
| 2 | Provider health | `TestSanteMesuree` (7 tests) | **covered** |
| 3 | Provider routing | `test_research_routing.py::TestRoutage` (4 tests) | **covered** |
| **4** | **Agent-Reach fallback** | — | **written (R09.1)** |
| **5** | **Web-Search-MCP fallback** | — | **written (R09.1)** |
| **6** | **Duplicate provider capability** | partial | **written (R09.1)** |
| 7 | Source normalization | `test_research_sources.py::TestNormalisation` (8 tests) | **covered** |
| 8 | Provenance | `TestPontVersAcquisition` + `test_les_dix_champs_de_step9_sont_rendus` | **covered** |
| 9 | `UNKNOWN` behaviour | `TestAucuneSubstitution`, `TestAucuneReponseFabriquee` | **covered** |
| 10 | Malicious retrieved content | `test_research_safety.py::TestContenuRecupere` (9 tests) | **covered** |
| 11 | SSRF protection | `TestAdressesLitterales` + `TestResolution` (12 tests) | **covered** |
| 12 | Authentication isolation | `TestAucunSecret` (4 tests) | **covered** |
| **13** | **Timeout** | — | **not covered — see below** |
| 14 | Provider failure | `TestAucuneSubstitution` (5 tests) | **covered** |
| 15 | Rate limiting | `tests/test_api_rate_limiter.py`, and `tools/web_search`'s token bucket | **covered, elsewhere** |
| 16 | Cache behaviour | `test_research_pipeline.py::TestFraicheur` (8 tests) | **covered** |
| 17 | Source freshness | same | **covered** |
| 18 | Cross-source validation | `test_research_sources.py::TestCorroboration` (5 tests) | **covered** |

---

## What writing the three missing tests found

### Cases 4 and 5 cannot be measured, and the tests say so

Both candidates are `BLOCKED` — measured, not assumed: `agent_reach` misses its
executable and two operator-level requirements, `web_search_mcp` misses its
Python module and three environment variables.

So a fallback *to* either of them cannot be exercised against the real thing.
The tests therefore force availability through a fixture whose docstring states
plainly that **it measures the router, never the provider**, and that neither
project was executed. The alternative — asserting nothing, or asserting a
plausible outcome — would have been worse in opposite directions.

What they do establish, honestly:

- `agent_reach` is the only declared provider for `youtube_transcript`;
- `web_search_mcp` is the only one for `academic_search` and
  `wikipedia_search`, and routing for those returns `ALL_BLOCKED` today with
  exactly one candidate considered;
- when a first provider raises, the chain moves to the next **and keeps the
  first failure visible**.

### Case 6 turned out to be two questions, not one

STEP 3 says not to install two versions of a capability one provider already
serves better. STEP 12 asks for a test of *duplicate provider capability*. Those
are not the same thing, and conflating them would have produced a test asserting
that duplication is forbidden — which is false here.

`web_search` is served by **three** providers, and that is correct: the second
and third are **fallbacks**, not duplicates. The test asserts the plan is
`["existing_galsen_research", "web_search_mcp", "agent_reach"]` in **declaration
order**, and a companion test asserts `ordering == "declaration"` so nobody
reads position one as a quality ranking.

### Case 13 is not covered, and inventing coverage would have been the mistake

**Nothing in this layer executes a request.** The search function is injected
(R07.2), and the timeout belongs to the caller's HTTP client. A test that timed
a fake function would measure the fake function.

Two things are asserted instead, and neither pretends to be a timeout test:

1. The measured state — both candidates `BLOCKED`, so no request can time out
   because no request is made.
2. That **a timeout arrives here as any other exception** does: a search raising
   `TimeoutError` yields `UNKNOWN` with `TimeoutError` preserved in the attempt
   record.

Timeout coverage becomes possible the day a provider actually runs. Until then
it is a **gap**, recorded as one.

---

## What the mapping did not need to add

Rate limiting (case 15) exists at two levels and is tested at both:
`src/api/rate_limiter.py` with `tests/test_api_rate_limiter.py` for inbound, and
`tools/web_search`'s token bucket for outbound. **The research layer adds no
rate limiter**, because STEP 10 says not to bypass the existing one and adding a
third would be the duplication STEP 3 forbids.

---

## Counts

| | |
|---|---|
| Cases named by STEP 12 | **18** |
| Already covered before R09 | **14** |
| Written in R09.1 | **3** |
| Not covered, recorded as a gap | **1** (timeout) |
| Tests in `tests/research/` | **206**, 1 skipped |
| Runnable cases in `src/research/golden.py` (R09.2) | **18** — 14 `VERIFIED`, 3 `BLOCKED`, 1 `NOT_APPLICABLE` |

The skipped one is the multi-provider fallback chain in
`test_research_routing.py`, which cannot run end to end while only one provider
is admitted — it says so rather than asserting something weaker. Note that
`test_research_step12.py` exercises the same path **with availability forced**,
which is why the two coexist: one measures reality, the other measures the
router.


---

## R09.2 — the eighteen cases, runnable

`tests/research/` passes in CI and then disappears: nobody can ask the platform
**what it holds**, only run its suite. `src/creative/golden.py` solved that for
the creative programme with twenty-five runnable scenarios;
`src/research/golden.py` does it for STEP 12's eighteen.

Measured on 2026-08-19: **14 `VERIFIED`, 3 `BLOCKED`, 1 `NOT_APPLICABLE`, 0
failed.**

The three `BLOCKED` are cases 4, 5 and 14 — both candidates and the academic
route — and `BLOCKED` here is **an assertion, not a skipped test**: it states
that the platform reports its incapacity instead of inventing a result. The
`NOT_APPLICABLE` is the timeout, with its reason returned beside it.

A third verdict was added rather than folding the timeout into `BLOCKED`: a
blocked capability gets installed, a case without an object does not.
