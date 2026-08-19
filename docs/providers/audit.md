# M00 — Report versus repository, and the provider abstractions

Directive V4 update, §35 and §36 STEP 1–3 (phase M00.1), STEP 7–8 (phase M00.2).
Measured on 2026-08-19 at `e6c5fc4`. Nothing here is remembered; every figure was
produced by running something.

**§35's instruction is followed literally: where the report and the code
disagree, the discrepancy is reported and neither is silently preferred.**

---

## M00.1 — `docs/PROJECT-REPORT.md` against the repository

The report states its own provenance: *measured on 2026-08-16 at commit
`6d0e9a1`*. That commit is **29 commits behind** the current head. So the
report is not wrong in the sense of having lied — it is a photograph, and the
subject moved.

### Numeric discrepancies

| Claim | Report (2026-08-16) | Measured (2026-08-19) | Nature |
|---|---|---|---|
| API routes | 131 | **142** | Stale. +11 across three programmes |
| Tests | 5 369 | **6 191** (CI, `e170a03`) | Stale. +822 |
| ADRs | 27 | **30** | Stale. ADR-028, 029 added; 024–027 already counted |
| Registered engines | 14 | **15** | Stale. `coding` added by ADR-028 |
| Agents | 17 | **17** | **Agrees** |

None of these is a contradiction between the report and the code. All five are
the same kind of drift, and the honest resolution is *not* to edit the report to
match: a report carries its measurement date, and rewriting its numbers in place
would destroy the only thing that makes it checkable.

**Recommendation, not applied here:** the report should be re-measured as a whole
at the end of this programme (§42), rather than patched field by field now.
Patching would produce a document that is half 16 August and half 19 August,
with no way for a reader to tell which half.

### Substantive claims, verified

| Report says | Verified today | Verdict |
|---|---|---|
| "WanGP was not vendored: licence not inspected, no GPU. `generate()` always raises" | `src/media/providers/wangp.py:142` — `generate()` documented as *"Refuse, en disant exactement ce qui manque"*; the module states the licence could not be inspected because the proxy refuses it | **Still true** |
| "Video generation blocked on a GPU **and** WanGP's licence inspected" | `third_party/` holds `aider`, `opengap`, `openhands`, `swe_agent` — **no WanGP** | **Still true** |
| "Speech synthesis: nothing — it has to be written" | `src/media/readiness.py` reports `VOICE` as `ABSENT` | **Still true** |
| "`v0.1.0` tag: the single red test in CI" | CI on `e170a03`: 1 failed, 6 191 passed, the tag | **Still true** |

**No contradiction was found between the report's substantive claims and the
code.** The gap is entirely in counts, and entirely explained by three days of
work the report predates.

### One discrepancy worth naming separately

The report's §6 describes the media engine as the platform's video capability.
Since 2026-08-16, `src/creative/` added a second, higher layer that also speaks
of providers, tasks and routing. **A reader of the report alone would not know
that layer exists**, and would look for video routing in `src/media/`.

That is not an error in either document — it is what happens when a report is
not re-measured after a programme lands. It is recorded here because §35 asks
for exactly this, and because the next section shows why it matters.

---

## M00.2 — the provider abstractions: there are three, not two

The phase plan said two. **Measured, there are three**, and finding the third
before writing an adapter is the entire point of auditing first.

| Layer | Path | Lines | What it is for | Registry class |
|---|---|---|---|---|
| **Model providers** | `src/model_engine/providers/` | 382 (registry) | LLM/model providers, sovereign mode, third-party host checks | `ProviderRegistry` |
| **Media providers** | `src/media/providers/base.py` + `wangp.py` | 343 + 203 | Media generation: `ProviderCapability`, `GenerationRequest`, the `TACHES` vocabulary | *none* — no registry class |
| **Creative providers** | `src/creative/providers.py` | 608 | Licence as a routing input, invocation mode, declaration vs measured availability | `ProviderRegistry` |

### The relationship is already decided, and written down

`src/creative/providers.py` opens by stating it **extends rather than replaces**
`src/media/providers/base.py`, and ADR-024 records why: *"tasks are declared
data, not subclasses"*, because twenty abstract classes differing only by method
name is a taxonomy, not a design — and each one becomes a place where the
registry and the router can disagree.

So the layering is not an open question:

```
src/media/providers/base.py      ← the generation contract (capability, request)
        ↑ extends
src/creative/providers.py        ← + licence, invocation mode, probed availability
        ↑ consumes
src/creative/routing.py          ← capability matching, refuses to rank on absent numbers
src/creative/pipelines.py        ← the two architectures of the previous directive
```

`src/model_engine/providers/` is **a different concern entirely** — it selects
language models, not media generators. It shares the word "provider" and nothing
else. Adding a video generator there would be the worst of the three options.

### What this means for M05, stated as a finding and not a decision

The evidence points one way, and M05 will have to either follow it or say why
not:

- `MoneyPrinterTurboProvider` belongs in the **creative** registry, because that
  is the only one that reads a licence before selecting — and §30 makes MPT's
  licence and its dependency tree the central question of this programme.
- It should declare its capability in the **media** vocabulary (`TACHES`,
  `ProviderCapability`), because that is the contract the creative layer extends
  rather than duplicates.
- It must not touch `src/model_engine/providers/`.

**This is not yet the decision.** M03 (licence) and M02 (what MPT actually is)
can still change it — in particular, if MPT turns out to be a *service* called
over HTTP rather than a library, its invocation mode is `API`, and that changes
what "adding a provider" even means here. M05 decides, with an ADR.

### Callers, so that nothing is broken by accident (§1, §21)

| Abstraction | Who depends on it |
|---|---|
| Model providers | `model_manager.py`, `model_registry.py`, `capability_detector.py` |
| Media providers | `src/media/readiness.py` (two stages), `src/media/tools/catalog.py` (two tools) |
| Creative providers | `routing.py`, `pipelines.py`, `api_surface.py`, `golden.py`, `mvp.py` |

`src/media/readiness.py` names `providers/base.py` and `providers/wangp.py` as
the modules behind the `VISUAL_GENERATION` and `VIDEO_GENERATION` stages. **Any
change to those files moves a readiness verdict**, which is the platform's
public statement about what it can do. That is the tripwire to respect when M06
writes the adapter.

---

## What M00 did not do

It did not resolve the report/repository drift, did not choose a registry, and
did not touch a line of provider code. §36 puts nineteen steps before the first
implementation, and this is the first two of them.
