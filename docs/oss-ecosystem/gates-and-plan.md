# E10 — Feasibility gates (§7) · E11 — Integration plan and order (§11, §12)

**Written**: 2026-08-20. §7's rule: *"If evidence is insufficient: MARK UNKNOWN.
Do not guess."*

---

# E10 — The fourteen questions

Applied to the six candidates that are not already present. The six others —
Transformers, vLLM, OpenHands (present), LlamaIndex, Open WebUI (rejected),
LangGraph (kept existing) — are settled and are not re-gated.

| # | Question | SGLang | llama.cpp | LiteLLM | Qdrant | Unsloth | whisper.cpp |
|---|---|---|---|---|---|---|---|
| 1 | Solves a real existing problem? | no | no | **no** | **no** — E04.2 | no | no |
| 2 | Capability missing? | no | no | no | no | no | no |
| 3 | Existing implementation weaker? | `UNKNOWN` | `UNKNOWN` | **no** | **no, as designed** | `UNKNOWN` | `UNKNOWN` |
| 4 | Improvement measurable? | **not here** | **not here** | n/a | **yes — and measured** | **not here** | **not here** |
| 5 | Integration feasible? | yes — env var | yes — env var | yes | yes | on a GPU host | yes |
| 6 | Licence compatible? | yes | yes | **`UNKNOWN`** — 404 | yes | yes | yes |
| 7 | Increases security risk? | no (server) | no | **yes** — ships `openai` | moderate — 2nd datastore | supply chain | no |
| 8 | Increases privacy risk? | **no — improves** | **no — improves** | yes | moderate | **yes** — §4G | no |
| 9 | Maintenance burden? | zero if deployed | low | 13 deps + carve-out | **process + backup path** | high | low |
| 10 | Removable later? | yes | yes | yes | **hard — data migrates** | yes | yes |
| 11 | Fallback exists? | **yes** — `FailoverModelRouter` | yes | yes | **no second store** | n/a | yes |
| 12 | Failure detectable? | yes | yes | yes | yes | n/a | yes — `TranscriptionUnavailable` |
| 13 | Quality measurable? | **`UNKNOWN`** | **`UNKNOWN`** | n/a | yes | **`UNKNOWN`** | **`UNKNOWN`** |
| 14 | Performance measurable? | **no — no GPU** | not here | n/a | yes | **no — no GPU** | **no — no `ffmpeg`** |

**Question 1 answers `no` for all six.** That is the gate that matters, and it
is not a close call: E05 found no capability missing from the platform.

**Question 3 is `UNKNOWN` four times** — and it stays `UNKNOWN` rather than
becoming `no`, because *"we could not measure it"* is not *"it is not better"*.
That distinction is the whole method.

**Only Qdrant scores `yes` on question 4**, because it is the only candidate
whose alternative was actually measured — and the measurement went **against**
it: the cheaper in-process fix is 3 388 × faster than the code as written.

---

# E11 — Integration plan and order

## Nothing is authorised

**Zero of twelve is recommended for integration.** §12 forbids implementation
during the audit, and this chapter does not request it afterwards either. There
is no vertical slice to schedule, because there is no integration to slice.

What follows is the honest content of an integration chapter with no
integration: **the order things would happen in, if anyone ever asked.**

## If anything were ever authorised — the order, and why

**Step 0, and it is not on the candidate list.** Fix
`SQLiteVectorStore.search()`: build the matrix once, invalidate on write. It is
in-process, it needs no dependency, and it is worth **3 388 ×** at 100 000
vectors. **Any integration decided before this is decided against a defect
rather than against the architecture.** *(A suggestion, not a task —
`.claude/rules/spec-driven-governance.md`.)*

**Step 1 — the documentation gap.** State in `docs/deployment/` what the
unavailability message already states: any OpenAI-compatible server serves this
platform; vLLM, SGLang and `llama-server` are three of them. **Zero code, and it
closes three candidates at once.**

**Step 2 — whisper.cpp, only if a host can compare it.** A second
`TranscriptionProvider` beside `faster-whisper`, registered through
`src/multimodal/registry.py`. **Never instead** — the registry holds one active
transcriber, chosen at runtime. Precondition: a machine that can run both, on
the same audio, **with Wolof in the sample**.

**Step 3 — Unsloth, on the day the occasion exists.** Two imports in
`scripts/training/train_adapter.py`. The ADR-006 gate and the lineage registry
keep working unchanged. Preconditions, all three: a GPU host, an authorised
dataset with recorded provenance, and a family to train.

**Step 4 — Qdrant, only if step 0 proves insufficient.** Reopened by payload-
filtered search over millions of vectors, or a working set that no longer fits
in RAM. **153.6 MB at 100 000 says that point is far away.**

**Never — LiteLLM inside the process, LangGraph as an orchestrator, LlamaIndex
as the retrieval layer, Open WebUI as the interface.** Each for a reason
recorded in its own chapter, not for a preference.

## Regression protection, if that day comes

§13's rule, restated for whoever executes it: run `python -m pytest -q` before
and after, compare the counts, and **delete no test, disable no test, weaken no
assertion**. The baseline to compare against is
**`1 failed, 6967 passed, 12 skipped, 3 deselected`**, whose single failure is
the `v0.1.0` tag and **is not a regression**.

---

## What E10 and E11 refuse to conclude

- **That the six gated candidates failed.** They were not needed. That is a
  different verdict, and conflating them would misrepresent four `UNKNOWN`s as
  four negatives.
- **That step 0 is authorised.** It is the most valuable thing this audit found
  and it is **still not this programme's to implement**.
- **That the order above is a plan.** It is a conditional ordering. No condition
  is currently met.
