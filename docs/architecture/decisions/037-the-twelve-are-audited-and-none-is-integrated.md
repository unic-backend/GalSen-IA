# ADR-037 — Twelve open-source projects were audited and none is integrated

**Status**: accepted
**Date**: 2026-08-20
**Directive**: GalSen IA — Open-Source Ecosystem Audit & Integration, §1–§14
**Volets**: E01–E11 (evidence), E12 (this decision)
**Report**: `docs/oss-ecosystem/final-report.md`

## Context

The directive named twelve projects — Transformers, SGLang, llama.cpp,
LangGraph, OpenHands, vLLM, LiteLLM, LlamaIndex, Qdrant, Open WebUI, Unsloth,
whisper.cpp — and asked which belong in GalSen IA. Its closing rule:
*"BUILD THE ORCHESTRATOR, NOT THE CAGE."*

Twenty-two phases were planned; **twenty-two were executed**. §12 forbids
implementation during the audit, and **zero lines of `src/` changed, zero
dependencies were added, and zero tests were added, altered or removed.**

## Decisions

### 1. None of the twelve is integrated

| Verdict | Count | Projects |
|---|---:|---|
| `ALREADY_PRESENT` | 3 | Transformers, vLLM, OpenHands |
| `OPTIONAL` | 2 | SGLang, llama.cpp |
| `DEFER` | 3 | LiteLLM, Qdrant, Unsloth |
| `KEEP_EXISTING` | 2 | LangGraph, whisper.cpp |
| `REJECT` | 2 | LlamaIndex, Open WebUI |
| **`INTEGRATE`** | **0** | — |

Zero is not a defensive posture. It is what §1's own question — *"Is it actually
needed?"* — returns when the repository is read before the candidates are. Every
provider abstraction §6 asks for already exists; each candidate would enter
behind a seam that is already there, and none brings what the seam lacks.

### 2. Three of them are reached today without code

vLLM, SGLang and `llama-server` all speak the OpenAI protocol, which
`openai_compatible_provider.py` already speaks. **vLLM is named in the
platform's own unavailability message, with its port** — someone already decided
it was supported. The gap is that `docs/deployment/` does not say so.

### 3. The four high-overlap candidates share one shape

LiteLLM, LangGraph, LlamaIndex and whisper.cpp each **overlap the mechanism and
miss the constraint**: LiteLLM misses ADR-014's refusal at registration,
LangGraph misses ADR-006's requirement that a *person* decide rather than a
caller resume, LlamaIndex misses scope and the `UNKNOWN` path that keeps law,
administration and languages from falling back to global knowledge.

**The mechanism is the commodity half. The constraint is what this repository
spent its programmes on.**

### 4. If LiteLLM ever enters, it enters `OUTSIDE`

Not above (it would invert ADR-014), not beside (a third retry policy beside
`FailoverModelRouter`, in a repository that already recorded two `retry_manager`
as a defect), not below (that describes a deployment, not a place). Outside: a
proxy someone deploys, reached like any other endpoint, holding **no credential
this platform issued**.

### 5. Two licences are not what their manifests say

| Project | Manifest | File |
|---|---|---|
| **LiteLLM** | `MIT` | MIT **except `enterprise/`**, whose licence returns **404** |
| **Open WebUI** | `Other/Proprietary` | BSD-3 **+ clause 4**: no rebranding above **50 users / 30 days** |

Ten of twelve are clean permissive grants compatible with ADR-036. Both
exceptions were found **only by opening the file** — one where the manifest was
the *more permissive* reading. §8's rule, demonstrated: a manifest is a
declaration, a file is a grant.

## Consequences

**Positive.** Nothing was installed, so nothing was weakened: ADR-014's
sovereign default, `ENVIRONMENT_TRANSMIS`, ADR-006's gate, `security/trust.py`
and ADR-034's four-tool allowlist are all untouched. The architecture was tested
against twelve serious projects and held.

**Negative, stated rather than softened.** **Nine performance rows are
`UNKNOWN`** — no GPU, no reachable model weights (Hugging Face → 403), no
`ffmpeg`. Four candidates are recorded as *not needed* rather than *not better*,
and the difference is real: nobody measured them.

**Neutral.** Four candidates carry named reopening conditions. None is met.

## Findings about GalSen IA produced by this audit

**None is fixed here.** Each is a suggestion, not a task
(`.claude/rules/spec-driven-governance.md`).

1. **`SQLiteVectorStore.search()` is 3 388 × slower than the design ADR-015
   described.** It re-reads every row and calls `json.loads` per row on every
   query; the ADR's premise, *"une matrice en mémoire"*, is not what the code
   does. At 100 000 vectors: **13 132 ms** measured, **3.88 ms** with the matrix
   cached, 153.6 MB resident. **The p95 half of ADR-015's own reversal condition
   is met at 271 vectors** — today's corpus size. A database was about to be
   blamed for a caching bug.
2. **§4F's constraint is unmet.** `POST /coding/task` is gated by
   `tool:execute`, held by `admin`, `operator` **and `user`**;
   `resolve_workspace()` accepts any host directory with no permitted root;
   `allow_network` and `allow_push` come from the request body. **The exposure
   is latent** — all three coding engines are unavailable, so nothing executes.
3. **The training pipeline gates the run, not the data.**
   `train_adapter.py` refuses to start without an ADR-006 approval and hashes
   the dataset for lineage — but the dataset path is chosen by the runner, so
   the approval proves *a run was approved*, never *what the file contained*.

Plus, informational: **`litellm==1.81.10` is installed in this environment,
declared by no requirements file and imported by nothing.** Unowned, not
dangerous, and not installed by this repository.

**Fourth consecutive external audit to find a defect here rather than in its
subject** — after ADR-034's sovereignty blind spot and ADR-035's missing
`LICENSE`.

## What this ADR does not decide

- **Whether any candidate is faster or better.** Nine `UNKNOWN` rows, and no
  number invented to fill them.
- **Whether to fix the three findings.** They are named so someone can decide.
- **Anything about model weights.** Every licence row is `n/a` at the library
  level; the models these tools load carry their own terms, and none was read.
