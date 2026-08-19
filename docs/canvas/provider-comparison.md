# K04.1 — provider comparison for the canvas

Creative Canvas directive, §11 and §25. Measured 2026-08-19 against the live
registry, not recalled.

**Most of §11's comparison already exists.** `docs/creative/provider-research.md`
compares ten candidates across capability, licence, VRAM, reference support,
identity, camera control and integration cost; `docs/creative/feasibility.md`
answers ten feasibility gates per capability; `docs/providers/licence-matrix.md`
audits a dependency tree. Rewriting any of that would inflate the page count
without adding a measurement — the mistake `docs/providers/golden-mapping.md`
avoided by mapping before writing.

So this document does two things only: it **maps** what already answers §11, and
it reports the **one comparison axis the canvas introduces** — which turned up a
defect.

---

## 1. What already answers §11, and where

| §11 asks | Answered in | Status |
|---|---|---|
| Capability per provider | `docs/creative/provider-research.md`, `corpus/creative/providers.yaml` | covered, 10 candidates |
| Licence per provider (repo / weights / dataset) | same, + `docs/providers/licence-matrix.md` | covered |
| Cost, latency | `CreativeProvider.cost_per_second`, `.typical_latency_s` | fields exist; **no value measured** |
| Availability / health | `availability()`, each adapter's `health()` | covered, probed live |
| Quality | **deliberately absent** | ADR-026: no measure exists, so no score is produced |
| VRAM / resource | `min_vram_gb` + `measured_vram_gb()` | covered |
| Routing fitness | `src/creative/routing.py` | covered, C15 |
| **Privacy** | **nowhere** | **the gap — see §3 below** |

**Zero of the ten candidates is commercially cleared**, eight carry
`commercial_status: UNKNOWN`, and eight weight licences are `UNKNOWN` because
`huggingface.co` has no route from this container. None of that changed in this
programme, which is the correct outcome for an audit: a comparison that grew a
cleared row would mean something was adopted without evidence.

---

## 2. The measured state, per provider

Read from the registry at execution time:

| Provider | Invocation (computed) | VRAM min | Commercial |
|---|---|---|---|
| `wan2.2` | `IN_PROCESS` | 24 GB | `UNKNOWN` |
| `wan2.7` | `IN_PROCESS` | `None` | `UNKNOWN` |
| `hunyuanvideo` | `IN_PROCESS` | 45 GB | **`RESTRICTED`** |
| `ltx-video` | `IN_PROCESS` | 8 GB | `PARTIAL` |
| `qwen2.5-omni` | `IN_PROCESS` | `None` | `UNKNOWN` |
| `pyannote-audio` | `IN_PROCESS` | `None` | `UNKNOWN` |
| `seed-vc` | **`OUT_OF_PROCESS`** | `None` | `UNKNOWN` |
| `latentsync` | `IN_PROCESS` | 20 GB | `UNKNOWN` |
| `hallo2` | `IN_PROCESS` | `None` | `UNKNOWN` |
| `moneyprinterturbo` | `IN_PROCESS` | 0 GB | `UNKNOWN` |

`runs_locally` is `False` for all ten — none is installed on this machine, and
the field records what was verified, not what is possible.

---

## 3. The axis the canvas adds — and the defect it exposed

K03.2 proposed a rule: **a generation node's output trust level is decided by
the provider's invocation mode.** `API` → `EXTERNAL` (hostile by default),
in-process → `TOOL`.

Checking that rule against the registry is what K04.1 is for, and the rule does
not survive the check.

### `invocation` is derived from the licence, not from how the provider is called

`src/creative/providers.py:580` — `adapt_declared()`:

```python
invocation=(HORS_PROCESSUS
            if "GPL" in str(entree.get("repository_license", ""))
            else DANS_LE_PROCESSUS),
```

The corpus declares **no** `invocation` field. The value is computed from one
question: *is the repository licence copyleft?* If yes, call it out of process,
so linking never happens.

**That derivation is right for the question it answers.** Calling a GPL tool
out-of-process instead of importing it is a deliberate, correct legal decision,
and `seed-vc` is `OUT_OF_PROCESS` for exactly that reason.

**It is wrong for the question K03.2 asked it.** Two layers now disagree about
the same provider:

| Layer | MoneyPrinterTurbo's invocation | Why |
|---|---|---|
| `src/media/providers/moneyprinterturbo.py:228` | **`API`** | it is called by HTTP and never imported (ADR-030) |
| `src/creative/providers.py` (`adapt_declared`) | **`IN_PROCESS`** | its licence is MIT, so the copyleft branch is not taken |

### Why this matters beyond tidiness

Under K03.2's rule as written, a provider reached **over HTTP at a third-party
host** would be classified `IN_PROCESS`, and its output would carry `TOOL` — the
trust level for *this platform's own components*. Content from an external host
would be treated as platform output, and `trust.py`'s whole point is that
external content is data, hostile by default.

The defect is in the rule, not in `adapt_declared`. A licence-derived field was
about to be load-bearing for a security decision it was never designed to carry.

### The correction

**Trust level derives from `ProviderPrivacyPolicy.data_destination`, not from
`invocation`:**

| `data_destination` | Output trust level |
|---|---|
| `LOCAL_ONLY` | `TOOL` |
| `THIRD_PARTY_HOST` | `EXTERNAL` |
| `UNKNOWN` | **`EXTERNAL`** — unknown is not permission |

This is the same field the privacy gate already uses, it answers the question
directly instead of by proxy, and its `UNKNOWN` fails safe. `docs/canvas/architecture.md`
is amended accordingly.

### Where every provider stands on that axis today

`ProviderPrivacyPolicy` does not exist yet, so the honest answer for all ten is
**`data_destination: UNKNOWN`** — and under the corrected rule every generation
node would therefore be `EXTERNAL` until someone reads and records the answer.

That is uncomfortable and it is correct. It is also cheap to fix: for a provider
that runs entirely on this machine, `LOCAL_ONLY` is established by installing
it and observing that it opens no socket — a measurement, not a reading.

---

## 4. A second discrepancy, recorded not resolved

This is the second time two layers have given one field opposite readings. The
first was `min_vram_gb = None` (`docs/providers/golden-mapping.md`): *no GPU
required* in the media layer, *nothing was declared* in the creative layer.

Both discrepancies have the same shape — a field that is honest inside its own
module and misleading across the boundary — and both are recorded rather than
patched, because resolving either means changing a meaning every caller relies
on. **Two occurrences is a pattern**, and the pattern belongs in ADR-031 (K04.2)
rather than in a silent fix here.

---

## 5. What this comparison does not claim

- **No ranking.** Nine of ten providers cannot be ordered on cost, latency or
  quality: no value was measured, and ADR-026 already forbids a quality score
  invented to fill the column.
- **No recommendation.** §25 asks for a comparison; choosing is an ADR's job.
- **No runtime figure.** Nothing was executed. Every provider in this table
  refuses today, and the one that would be selected (`stock_assembly`,
  non-commercial) refuses for three named reasons.
