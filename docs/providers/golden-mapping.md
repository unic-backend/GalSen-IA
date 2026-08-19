# M08.1 — §38's golden tests, mapped before any was written

Directive V4 update, §38. Mapped on 2026-08-19.

**The mapping came first on purpose.** Many of §38's twenty-two tests describe
properties the previous programme already runs — `src/creative/golden.py` executes
twenty-five scenarios against live code. Writing a second `REF-05` beside an
existing provenance scenario would have inflated the count without adding one
line of coverage, and a count that grows without coverage is worse than no count.

**Nineteen of twenty-two were already covered. Three were written** (M08.2), and
writing them found a real defect.

---

## MoneyPrinterTurbo tests

| § | Test | Covered by | Status |
|---|---|---|---|
| MPT-01 | Provider discovery | `test_routing_mpt.py::test_le_fournisseur_est_declare` | **covered** |
| MPT-02 | Capability declaration | `test_moneyprinterturbo.py::TestDeclaration` (5 tests) | **covered** |
| MPT-03 | Provider health | `test_moneyprinterturbo.py::TestSante` (6 tests) | **covered** |
| MPT-04 | Routing when appropriate | `test_routing_mpt.py::test_l_assemblage_non_commercial_est_servi` | **covered** |
| MPT-05 | Existing provider still works | `test_moneyprinterturbo.py::test_wangp_reste_intact` | **covered** |
| **MPT-06** | **Failure → fallback** | — | **written (M08.2)** |
| **MPT-07** | **9:16 workflow** | — | **written (M08.2)** |
| **MPT-08** | **16:9 workflow** | — | **written (M08.2)** |
| MPT-09 | Existing video workflow regression | `test_wangp_reste_intact` + `tests/media/` readiness suite | **covered** |

## Reference tests

| § | Test | Covered by | Status |
|---|---|---|---|
| REF-01 | Single image reference | golden scenario 8 | covered |
| REF-02 | Multiple image references | golden scenario 8 | covered |
| REF-03 | Video reference | golden scenario 9 (`BLOCKED`, reported) | covered |
| REF-04 | Multiple entity references | golden scenario 10 | covered |
| REF-05 | Reference provenance | golden scenario 25 | covered |
| REF-06 | Reference deletion | golden scenario 24 | covered |
| REF-07 | Consent restriction | golden scenario 23 | covered |

## Identity tests

| § | Test | Covered by | Status |
|---|---|---|---|
| ID-01 | Identity verification | golden scenario 14 | covered |
| ID-02 | Identity drift detection | golden scenario 15 (`BLOCKED`, no measure) | covered |
| ID-03 | Shot-level regeneration | golden scenario 16 | covered |

## Audio tests

| § | Test | Covered by | Status |
|---|---|---|---|
| AUDIO-01 | Original audio preservation | golden scenarios 4, 5, 6 | covered |
| AUDIO-02 | Multi-speaker reference mapping | golden scenario 3 + `test_mvp.py` | covered |
| AUDIO-03 | Unknown language, no fabrication | golden scenario 20 | covered |

---

## What writing the three missing tests found

**MPT-07 exposed a real defect in my own declaration.** The adapter declared
`max_width=1920, max_height=1080`, and `base.py:199` compares the bounds **axis
by axis**. A 1080×1920 portrait request was therefore refused on its height —
and 9:16 is MoneyPrinterTurbo's *primary* use case.

The fix declares 1920 on both axes, with the imprecision named in the code: a
1920×1920 square now passes although it was never verified. Between wrongly
refusing the central use case and letting an unverified case through — which
would fail visibly at the provider — the second is repaired in minutes and the
first is hunted for hours.

**MPT-06 is written honestly rather than favourably.** §29 asks that a failure
route to another compatible provider. No other provider serves `stock_assembly`,
so a failure yields `NO_PROVIDER`. The test asserts the **refusal to
substitute** — and a second test asserts that exactly one provider serves the
task, so that the day a second appears, this is where it is noticed and the
fallback becomes testable for real.

---

## One discrepancy worth recording (§35)

`None` means opposite things in two layers that talk to each other:

| Layer | `min_vram_gb = None` means |
|---|---|
| `src/media/providers/base.py` (docstring) | **no GPU required** |
| `src/creative/routing.py` | **nothing was declared** → `UNKNOWN` |

Both are defensible inside their own module, and neither is wrong. But two
adjacent layers giving one value opposite meanings is a trap, and it is the
reason MoneyPrinterTurbo is declared `min_vram_gb=None` in the media capability
and `vram_gb_min: 0` in the creative corpus — the same fact, expressed the way
each layer reads it.

**Not resolved here**, because resolving it means changing one of the two
meanings and re-checking every provider that relies on it. Recorded so that the
next person to touch either does not discover it the hard way.
