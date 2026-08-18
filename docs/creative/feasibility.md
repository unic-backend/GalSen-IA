# Feasibility report (C02, directive V4 §61)

*Measured 2026-08-16.* §61 gives ten questions to ask before implementing any
major capability. They are asked here of each one the directive names, and the
answers are the ones this environment actually supports — including the ones
that are `UNKNOWN` and `BLOCKED`, which §61 explicitly requires to be documented
rather than guessed.

The ten gates: **(1)** possible today · **(2)** an appropriate provider exists ·
**(3)** GPU feasible · **(4)** latency acceptable · **(5)** quality acceptable ·
**(6)** measurable · **(7)** failure detectable · **(8)** fallback possible ·
**(9)** removable later · **(10)** licence compatible.

---

## 1. Summary

| Capability | Verdict | The gate that decides it |
|---|---|---|
| Creative representation, WorldState, entity & world memory | **FEASIBLE** | Pure orchestration. No provider, no GPU, no licence question. |
| Reference entity ingestion, consent, deletion | **FEASIBLE** | Data model + permissions; the mechanisms already exist in this repository. |
| Director, shot planner, continuity model | **FEASIBLE** | Structural reasoning, not generation. |
| Job orchestration, provenance, routing, cache | **FEASIBLE** | Extends what already runs. |
| Language knowledge ladder, validation, code-switching metadata | **FEASIBLE** | The ADR-021 observation→validation ladder already exists in another form. |
| Speaker diarization | **BLOCKED** (gate 3, 10) | pyannote needs `torch` and a **gated** licence acceptance; neither is possible here. |
| Speech recognition / word timings | **BLOCKED** (gate 3) | No `whisper`, no `torch`. The interface exists (`src/multimodal/`). |
| Lip sync | **BLOCKED** (gate 3, 6) | Needs GPU **and** face landmarks; no face cascade is even available here. |
| Voice conversion | **BLOCKED** (gate 3, 10) | GPU absent; Seed-VC is GPL-3.0, an unresolved architectural question. |
| Video generation (any) | **BLOCKED** (gate 3, 10) | No GPU. Zero candidates cleared commercially. |
| Identity verification | **UNKNOWN** (gate 6) | See §3 below — this one is not merely blocked. |
| Speech synthesis (VOICE) | **NOT_AVAILABLE** | Nothing in this repository does it; Qwen2.5-Omni is a candidate, unverified. |

**Everything the directive assigns to GalSen IA itself (§74) is feasible now.
Everything that requires a model is blocked on hardware, licences, or both.**
That is a workable split: it means the orchestration layer can be built,
tested and measured while the providers stay adapters that report their state.

---

## 2. The gates, capability by capability

### 2.1 Orchestration layer — FEASIBLE

CreativeEngine, CreativeRepresentation, ReferenceEntity, ReferenceMemory,
EntityEngine, CharacterMemory, WorldState, WorldMemory, DirectorEngine,
ShotPlanner, ContinuityEngine, ModelRouter, ProviderRegistry, jobs, provenance.

| Gate | Answer |
|---|---|
| 1 possible today | **Yes** — data structures and rules, no inference |
| 2 provider | **Not required** |
| 3 GPU | **Not required** |
| 4 latency | Measurable now; the media engine's comparable paths run in 0.3–20 ms |
| 5 quality | Judged by tests, not by a model |
| 6 measurable | **Yes** |
| 7 failure detectable | **Yes** — refusals are explicit, as everywhere in this repository |
| 8 fallback | Not applicable |
| 9 removable | **Yes** |
| 10 licence | No third-party dependency |

### 2.2 Speech understanding (ASR, diarization, word timings) — BLOCKED

| Gate | Answer |
|---|---|
| 1 possible today | Yes, in general |
| 2 provider | pyannote (diarization), Whisper (ASR) — interfaces already exist here |
| 3 **GPU** | **No.** No GPU, no `torch`. `transcription` probe → `UNAVAILABLE` |
| 4–5 latency, quality | `NOT_MEASURED` |
| 6 measurable | Yes, once it runs |
| 7 failure detectable | **Yes, and already enforced**: `words_from_segments()` refuses to interpolate, and an estimated timing is marked `ESTIMATED` and refused by the edit planner |
| 8 fallback | Preserve the original audio and answer `UNKNOWN` — §22 and §33 make this the *correct* behaviour, not a degraded one |
| 9 removable | Yes — provider behind an interface |
| 10 **licence** | pyannote code MIT ✔; **pretrained pipelines are gated** and require accepting conditions with an account. `UNKNOWN` |

### 2.3 Video generation — BLOCKED

| Gate | Answer |
|---|---|
| 1 possible today | Yes, in the ecosystem |
| 2 provider | Four candidates surveyed |
| 3 **GPU** | **No.** 8 GB is the lowest documented floor (LTX distilled); this machine has none |
| 4–5 latency, quality | `NOT_MEASURED`, and unmeasurable here |
| 6 measurable | Yes, on a GPU host |
| 7 failure detectable | Partly — a render either produces a file or does not; whether it matches intent is §51's verification loop |
| 8 fallback | **Yes, and it is not a lesser answer**: report `NOT_CONFIGURED` with the missing capability named |
| 9 removable | Yes — this is the entire point of the adapter design |
| 10 **licence** | **Zero candidates cleared.** One `RESTRICTED` (territorial exclusion), one `PARTIAL` (OpenRail-M weights), seven `UNKNOWN` |

### 2.4 Voice conversion — BLOCKED, and optional

§23 makes it optional and §22 makes preserving the original recording the
default path. Seed-VC is **GPL-3.0**: calling it out-of-process is not the same
act as vendoring it. Gate 10 is unresolved and gate 3 is a hard no.
**The cheapest resolution is not to need it** — which is what §22 already says.

### 2.5 Speech synthesis — NOT_AVAILABLE

The media engine's readiness report already states this: `VOICE` is `ABSENT`,
not blocked. Nothing here turns text into voice, and no installation changes
that — a module has to be written or a provider adopted. Qwen2.5-Omni produces
streaming speech per its README and is a candidate; its weight licence is
`UNKNOWN`.

§26 is the reason this matters more than it looks: for the languages §24 names,
**understanding and generation are separate capabilities and the second is often
missing**. Preserving the user's own recording is not a workaround there. It is
the better answer.

---

## 3. Identity verification — `UNKNOWN`, and honestly so

This one deserves its own section because gate 6 fails in an unusual way.

§48 requires evidence-based verification and forbids inventing scientific
meaning for a score. Measured here: **no face detection is available at all** —
`HaarCascadeFaceDetector.is_available()` is `False`, because headless OpenCV no
longer ships cascade files. So facial similarity cannot be computed, and neither
can anything derived from it.

That leaves a choice the directive already anticipated, and only one side of it
is acceptable:

- Produce a number anyway from colour histograms or embedding distance and call
  it an *identity score*. It would look scientific, it would be comparable
  across shots, and it would mean nothing. This repository has shipped exactly
  that kind of number before — the RAG relevance scores — and paid for it.
- Report the dimension as `NOT_MEASURABLE` with the capability that would enable
  it, and let the verification loop treat "cannot check" as distinct from
  "checked and fine". Three outcomes, not two — the same rule the media QC layer
  already holds.

**The second.** Identity verification will be architected, its dimensions
declared, and each one will report `MEASURED` or `NOT_MEASURABLE` with a named
reason. No composite "identity score" will be invented.

---

## 4. Stop conditions currently active (§80)

| Condition | State | What settles it |
|---|---|---|
| Model licences unclear | **UNKNOWN** ×8 | `huggingface.co` reachable, or texts mirrored |
| Commercial rights unclear | **UNKNOWN** ×7 | Same |
| Hardware infeasible | **BLOCKED** | A GPU host, or a remote provider with credentials |
| Provider capability unverified | **UNKNOWN** | Cannot be verified without executing a model |
| Identity verification measurable | **UNKNOWN** | A face/landmark capability, plus a documented metric |
| Privacy requirements satisfiable | **PARTIAL** | Consent, deletion and audit mechanisms exist; approval and audit persist only with `GALSEN_STORAGE_BACKEND=sqlite` |

None of these blocks the orchestration work. All of them block claims about
generation, identity and quality — and the programme will make none.

---

## 5. What this report authorises

**Proceed with:** the orchestration layer (§74's list), provider *interfaces*
with capability probes, reference and consent architecture, language knowledge,
routing, jobs, provenance, verification structure.

**Do not proceed with:** vendoring any model, adopting Seed-VC before its
copyleft question is decided, any claim about identity fidelity, continuity or
generation quality, and any commercial-use assumption for any candidate.

**Next**: C03 — ADRs and schemas. ADR-001 first, because three provider families
already exist in this repository and adding a fourth would be the duplicate
abstraction §2 forbids.
