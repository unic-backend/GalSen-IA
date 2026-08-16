# Universal Creative Intelligence — repository audit (PHASE 0)

Directive: **GALSEN-IA — UNIVERSAL CREATIVE INTELLIGENCE, MASTER ARCHITECTURE &
IMPLEMENTATION DIRECTIVE V4**, 81 sections.
This document answers STEPS 1–8 of §79. **No code was written for it.**

*Measured on 2026-08-16 at commit `b7267fc`. Every claim below was checked by
running something or reading the file it names. Where a thing could not be
checked, it says `UNKNOWN` and names what would settle it.*

---

## 1. What was inspected (STEPS 1–6)

| Inspected | Method | Result |
|---|---|---|
| Directory structure | `find`, `ls` | 473 Python modules, 101 421 lines, 35 packages under `src/` |
| Existing architecture | `docs/architecture/overview.md` + the code it names | 14 registered engines, 9 later subsystems |
| Agents | `agents/registry.yaml` | 17 agents |
| Orchestration | `src/router/` | `RouterEngine`, workflows, `workflow_checkpoint.RunStatus` |
| RAG / knowledge | `src/knowledge_engine/` (37 files, 10 706 lines) | Two-axis knowledge base (ADR-019), `SourceTier`, retrieval |
| Memory | `src/memory_engine/` | 4 memory types, layers, cache, ranker, quality |
| Multimodal | `src/multimodal/` | `TranscriptionProvider` interface + registry + Whisper adapter |
| APIs | live FastAPI route table | 131 routes, RBAC + API key on all of them |
| Frontend | `src/web/static/` | Buildless dashboard + Media Studio (ADR-008) |
| Storage / DB | `src/storage/`, ADR-005 | `GALSEN_STORAGE_BACKEND` = `in-memory` \| `sqlite` |
| Queues / jobs | `src/media/queue/jobs.py`, `src/router/workflow_checkpoint.py` | Render queue with priorities, attempts, terminal cancel |
| Connectors / plugins / routines | `src/connectors/`, `src/plugins/`, `src/routines/` | Present, probed by `degradation.py` |
| AuthN / AuthZ | `src/api/rbac.py`, `src/tool/authorization.py` | 10 roles, per-tool ceilings on `DataScope` × `Effect` |
| Security | `src/security/` | trust boundary, isolation, redaction, posture (10 dimensions, 7 named gaps) |
| Self-healing | `src/agent/` (23 files, 6 406 lines) | Harness with isolation, rollback, regression gate |
| Observability | `src/observability/`, `/observability/trail/{id}` | One job followable end to end |
| Tests | pytest collection | 274 files, **5 369 passing**, 8 skipped |
| Deployment / config | `Dockerfile`, `docker-compose.yml`, `src/config/` | Single-instance posture (ADR-009/013) |
| Model integrations | `src/model_engine/providers/` | `ModelProvider` ABC + 6 concrete providers |
| Provider abstractions | `src/media/providers/base.py` | Capability/cost/VRAM matching, no nearest-match |

---

## 2. Architecture map (STEP 7)

```
                      ┌──────────────── src/api/server.py — 131 routes, RBAC ─────────────┐
                      │  /health /memory /model /knowledge /tool /routines /workflow      │
                      │  /media (8) /approval /connectors /plugins /file /email /calendar │
                      └───────────────────────────┬──────────────────────────────────────┘
                                                  │
   ┌──────────────────────────────────────────────┼──────────────────────────────────────┐
   │                                              │                                      │
┌──┴───────────────┐  ┌────────────────┐  ┌───────┴────────┐  ┌──────────────┐  ┌────────┴───────┐
│ router/          │  │ agent/         │  │ tool/ + tools/ │  │ model_engine/│  │ media/         │
│ RouterEngine     │  │ AgentRuntime   │  │ 24 declared    │  │ ModelProvider│  │ 26 modules     │
│ workflows        │  │ self-healing   │  │ capabilities + │  │ 6 providers  │  │ capability     │
│ checkpoints      │  │ guarded editor │  │ ceilings       │  │ selection    │  │ probes, queue  │
└──────────────────┘  └────────────────┘  └────────────────┘  └──────────────┘  └────────────────┘
   │                       │                    │                   │                  │
┌──┴───────────────────────┴────────────────────┴───────────────────┴──────────────────┴────────┐
│ memory_engine/  knowledge_engine/  document_intelligence_engine/  vision_intelligence_engine/  │
│ multimodal/  acquisition/  darra_j/  services/  connectors/  plugins/  routines/  proactive/   │
└────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                             │
        ┌────────────────────────────────────┴────────────────────────────────────┐
        │ security/ (trust, isolation, redaction, posture) · storage/ (ADR-005)    │
        │ audit_engine/ · approval_engine/ (ADR-006) · observability/ · analytics/ │
        └─────────────────────────────────────────────────────────────────────────┘
```

The shape that matters for this directive: **the platform already owns
orchestration, provider abstraction, memory, a trust boundary, a job queue,
provenance discipline and a human approval gate.** What it does not own yet is
the *creative* representation layer — reference entities, world state, entity
memory, directing, continuity and identity verification.

---

## 3. Classification (STEP 8)

Legend: **E** existing and reusable as is · **X** extension required · **N** new
component required · **D** deprecated · **?** unknown.

### 3.1 Components the directive names — orchestration & providers

| Directive component | § | State | Evidence / what exists today |
|---|---|---|---|
| Provider abstraction | 34 | **X** | `src/model_engine/providers/base.py` (`ModelProvider` ABC), `src/multimodal/interfaces.py` (`TranscriptionProvider`), `src/media/providers/base.py` (capability + VRAM + cost matching). Three shapes exist; the directive asks for ~20 provider kinds. **Extend one shape, do not create a fourth.** |
| ProviderRegistry | 35 | **X** | `src/multimodal/registry.py` and `src/tool/capabilities.py` both implement registry-with-declared-capability. States `AVAILABLE/DEGRADED/UNAVAILABLE` already exist in `src/integration/degradation.py`; `EXPERIMENTAL` and `DISABLED` do not. |
| ModelRouter | 36 | **X** | `src/model_engine/model_selector.py` + `capability_detector.py` + `src/media/providers/base.select_provider`. Routing on task/quality/cost/VRAM exists; license, user tier and verification requirements are not routing inputs yet. |
| Job system | 53 | **X** | `src/media/queue/jobs.py` (priorities, bounded attempts, terminal cancel, counted progress, declared reservations) + `src/router/workflow_checkpoint.py` (`RunStatus`, resumability). Missing: `PAUSED`, per-job cost metadata, artifacts. |
| Cache | 54 | **X** | `src/memory_engine/memory_cache.py`, model metadata caching in `src/media/core/capabilities.py`. No artifact cache with explicit invalidation. |
| Provenance | 55 | **X** | `src/acquisition/manifest.py`, `src/media/core/project.Artifact` (origin `AI_GENERATED`/`SOURCED`/`UNKNOWN_ORIGIN`, `sha256`, `produced_by`, `provenance_complete`). Reference provenance is not modelled. |
| GPU / resource orchestration | 52 | **X** | `gpu_compute` probe + `measured_vram_gb()` (returns `None` when unreadable, never a guess). No scheduler, no model load/unload. |
| Security | 56 | **E** | `src/security/trust.py` (7 trust levels, injection patterns, wrap-as-data), `isolation.py`, `redaction.py`, `posture.py`. **Reuse; do not build a second boundary.** |
| Self-healing | 57 | **E** | `src/agent/` harness with isolation, rollback, regression gate. **Reuse as is.** |
| Observability | 59 | **X** | `/observability/trail/{id}`, `src/api/metrics.py`. No provider-health or drift metrics. |
| API surface | 70 | **X** | 131 routes; `/media/*` is the closest precedent. `/creative`, `/references`, `/entities`, `/worlds`, `/shots`, `/verification` do not exist. |

### 3.2 Components the directive names — creative layer

| Directive component | § | State | Evidence |
|---|---|---|---|
| CreativeEngine + CreativeRepresentation | 5 | **N** | Nothing structures intent this way. Closest: `src/media/tools/intent.py` (request → structured plan, unstated fields become questions) and `src/media/story/structures.py` (8 narrative structures). Both are inputs, neither is the representation. |
| ReferenceEntityEngine | 6–11 | **N** | **Nothing exists.** No reference, no identity representation, no multi-image or video reference ingestion. |
| Reference consent / privacy | 12, 58 | **X** | The *mechanisms* exist and are proven: `src/darra_j/access.py` + `privacy.py` (permission **and** declared link), `src/approval_engine/` (ADR-006), `src/acquisition/gate.py` (batch human approval), `PERMISSIONS_HORS_PLATEFORME`. What is missing is a consent model **for reference media**. |
| ReferenceMemory | 13 | **X** | `src/memory_engine/` has layers, versioning discipline and stores; `src/media/core/project.py` has versions that are never deleted. A reference memory should be a layer here, **not a competing store**. |
| EntityEngine | 14 | **N** | Nothing. |
| CharacterMemory | 15 | **N** | Nothing. |
| WorldState | 16 | **N** | Nothing. Closest: `src/media/analysis/scene_model.py` (`Scene` with `origins` MEASURED/AI_DERIVED/ABSENT) — a good precedent for per-field provenance, not a world. |
| WorldMemory | 17 | **N** | Nothing. |
| DirectorEngine | 18 | **N** | Nothing structural. `src/media/story/planner.py` plans scenes by narrative role, not by camera/lens/blocking. |
| ShotPlanner | 19 | **X** | `src/media/story/planner.py` + `src/media/timeline/edit_plan.py` decompose into scenes/segments on **measured** boundaries. Shot-level regeneration does not exist. |
| CrowdEngine / BackgroundMotionEngine | 20 | **N** | Nothing. |
| VoiceSceneEngine | 21 | **N** | Pipeline does not exist. Two of its stages do: transcription (`src/multimodal/`) and word-level timing (`src/media/transcription/words.py`, refuses estimated timings). |
| Original audio preservation | 22 | **X** | The principle is already enforced elsewhere: `Selection` has no time field, cues are never stretched, official fields are returned verbatim. No audio-preservation path exists yet. |
| VoiceConversionProvider | 23 | **N** | Nothing. |
| Speaker diarization | 21 | **N** | Nothing. |
| Lip sync | 42 | **N** | Nothing. |
| AudioEngine | 41 | **X** | `src/media/audio/sound_design.py` (events anchored to real timeline events), `music.py` (rights `CLEARED`/`UNKNOWN`/`RESTRICTED`). No dialogue mixing. |
| VideoEditorEngine | 44 | **X** | `src/media/timeline/`, `qc/`, `adapt/formats.py` cover trimming, subtitles, aspect conversion, verification. Shot replacement does not exist. |
| Social format engine | 45 | **E** | `src/media/adapt/formats.py` — 6 formats, relative placement, refuses centre-crop and measures its cost. |
| StyleEngine | 46 | **X** | `src/media/motion/scene.VisualIdentity` is style-as-data. Not extensible to the listed style families yet. |
| IdentityVerificationEngine | 48 | **N** | Nothing. `src/vision_intelligence_engine/face_detector.py` exists but **reports unavailable here** (no Haar cascade file shipped with headless OpenCV — measured: `is_available() == False`). Note its history: it once returned an empty list always, i.e. "no faces" for a photo of ten people; that was corrected to an explicit unavailability. |
| IdentityDriftDetector | 49 | **N** | Nothing. |
| ContinuityEngine / Checker | 50 | **X** | `src/media/timeline/verify.py` re-transcribes a render and compares mechanically, answering `NOT_VERIFIED` when it cannot. The pattern is right; the scope (identity, clothing, lighting, direction) is absent. |
| Creative quality loop | 51 | **X** | `src/media/qc/checks.py` (three outcomes, `PRODUCTION_SUCCESS` hard to reach) + `src/agent/` repair harness. No plan→generate→verify→regenerate loop. |
| Global language intelligence | 27–31 | **X** | Strong reuse: `corpus/languages/aliases.yaml` (16 concepts, 115 terms, `wo_reviewed: false`), `src/services/senegal/multilingual_aliases.py`, ADR-021 acquisition states, `SourceTier` (`TIER_A_PRIMARY_OFFICIAL` … `TIER_C_SECONDARY`), Darra J's `CLARIFICATION_REQUIRED`. **The observation→validation ladder of §28 is the same shape ADR-021 already implements.** |
| LanguageKnowledgeBase | 30 | **X** | `src/knowledge_engine/` with two axes (scope, subject) and per-item provenance is the natural home. A separate store would duplicate ADR-019. |
| Code-switching | 25 | **N** | Nothing. Aliases are per-term, not per-segment. |
| Multimodal input routing | 47 | **X** | `src/media/tools/catalog.py` declares what each tool consumes/produces and refuses impossible chains. Same mechanism can decide which modality supplies identity vs motion vs style. |

### 3.3 Deprecated / to retire

| Item | State | Note |
|---|---|---|
| `/cloud/*` (6 routes) | **D** | Already marked `deprecated=True` in the API; superseded by `/file/*`. Decision pending in `pending-work.md`. |
| ADR-020 analytics retention | **?** | Status `proposed`, not accepted. |

---

## 4. Discrepancies found (§3 — documented, not silently rewritten)

1. **`docs/architecture/overview.md` was stale** — it announced 236 test files /
   4 480 tests / 22 tools / 22 ADRs against a repository serving 274 / 5 369 /
   24 / 23. Corrected on 2026-08-16 (commit `b7267fc`). The repository's own
   `tests/test_published_numbers.py` exists precisely to catch this and had
   caught the route count twice already.
2. **`face_detector.py` promises more than the environment delivers.** The class
   is named for Haar-cascade detection, the code is real, and `is_available()`
   is `False` here because headless OpenCV no longer ships cascade files. That is
   correct behaviour (it refuses rather than returning "no faces"), but any
   identity-verification design that assumes face detection works **here** would
   be wrong.
3. **Two provider registries and three provider base classes** already exist
   (`model_engine`, `multimodal`, `media`). The directive asks for ~20 more
   provider kinds. Adding a fourth family would be the "duplicate abstraction
   because a new name sounds cleaner" that §2 forbids — this is the single
   biggest design risk of the programme and belongs in ADR-001.

---

## 5. Feasibility measured (STEPS 9–10 probe, §61, §80)

### 5.1 Research and license audit — **PARTIAL**

Measured now, from this container:

| Source | Reachable | Consequence |
|---|---|---|
| `raw.githubusercontent.com` | **200 — yes** | Official `LICENSE` and `README` files **can** be read from authoritative sources |
| `api.github.com` | **scoped** | Only `unic-backend/galsen-ia`; metadata (release, commit, archived) for third-party repos is **not** reachable |
| `github.com` HTML | **403** | Blocked by the proxy |
| `huggingface.co` | **000 — no route** | **Model cards and weight licenses are NOT reachable.** |
| `pypi.org` | **200** | Package metadata reachable |

This is the exact distinction §40 insists on, and the environment enforces it:
**repository licenses are verifiable; model-weight licenses mostly are not.**
Anything not read from an authoritative source stays `UNKNOWN`.

Feasibility probe — real license texts fetched from the official repositories
(**this is not the license matrix**; §39/§40 work belongs to C01):

| Project | Repository LICENSE (fetched) | Weight license |
|---|---|---|
| `Wan-Video/Wan2.2` | Apache-2.0 | `UNKNOWN` — on Hugging Face, unreachable here |
| `Lightricks/LTX-Video` | Apache-2.0 | `UNKNOWN` |
| `Tencent-Hunyuan/HunyuanVideo` | **Tencent Hunyuan Community License Agreement** — not an OSI licence | `UNKNOWN`; the community licence carries use restrictions that must be read in full |
| `QwenLM/Qwen2.5-Omni` | Apache-2.0 | `UNKNOWN` |
| `pyannote/pyannote-audio` | MIT | `UNKNOWN` — pretrained pipelines are gated on Hugging Face |
| `Plachtaa/seed-vc` | **GPL-3.0** | `UNKNOWN` |
| `bytedance/LatentSync` | Apache-2.0 | `UNKNOWN` |
| `fudan-generative-vision/hallo2` | MIT | `UNKNOWN` |

Two findings already worth an ADR: **seed-vc is copyleft (GPL-3.0)**, which is a
different integration question from the permissive ones — vendoring it into this
repository is not the same act as calling it behind an adapter. And
**HunyuanVideo is not under an OSI licence at all**; "open source repository"
does not follow from "weights downloadable", which is §40's whole point.

### 5.2 Execution capability — **BLOCKED for generation**

| Dependency | State here | Measured by |
|---|---|---|
| GPU / CUDA | **absent** | no `/proc/driver/nvidia`, `gpu_compute` probe → `UNAVAILABLE` |
| `torch` | **absent** | `ModuleNotFoundError` |
| `transformers` | **absent** | `ModuleNotFoundError` |
| `ffprobe`, full `ffmpeg` | **absent / crippled** | `media_probe`, `video_decode`, `video_encode` → `DEGRADED` |
| Audio decode / analysis | **absent** | `UNAVAILABLE` |
| Transcription (`whisper`) | **absent** | `UNAVAILABLE` |
| Face cascade | **absent** | `HaarCascadeFaceDetector.is_available() == False` |
| Frame encode, image analysis | **AVAILABLE** | verified by writing a real WebM; OpenCV 5.0, Pillow 12.3 |

**No video, image, speech or voice model can execute in this environment.** That
is not a reason to fake them and not a reason to skip them: it is the reason the
programme is built as **adapters with capability probes**, the same way the media
engine was — and it is why every provider will report its state rather than a
plausible result.

### 5.3 Active stop conditions (§80)

| Condition | State | What would settle it |
|---|---|---|
| Model weight licenses unclear | **UNKNOWN** | Reachability to `huggingface.co`, or the licence text mirrored in the repo |
| Commercial rights unclear | **UNKNOWN** | Same, plus a reading of the Tencent community licence |
| Required hardware infeasible | **BLOCKED** | A GPU host, or a remote provider API + credentials |
| Provider capability unverified | **UNKNOWN** | Cannot be verified without executing a model |
| Identity verification measurable? | **UNKNOWN** | No face detection available here; §48 forbids inventing a metric's scientific meaning |
| Privacy requirements satisfiable | **PARTIAL** | Consent, deletion and audit mechanisms exist; approval and audit are **in memory** unless `GALSEN_STORAGE_BACKEND=sqlite` |

None of these blocks the architectural work. All of them block claims about
generation quality, and the programme must not make any.

---

## 6. What this audit concludes

1. **Reuse dominates.** Of the ~40 components the directive names, 9 exist as is,
   19 need extension, 12 are genuinely new. The new ones are concentrated in one
   place — the creative representation layer (reference, entity, world, director,
   continuity, identity) — which is precisely the layer §74 says belongs to
   GalSen IA.
2. **The riskiest decision is provider abstraction**, because three provider
   families already exist. ADR-001 must decide whether to unify or extend, with
   the migration path written down before any code.
3. **Nothing in this programme can prove generation quality here.** Every
   capability will be declared, probed and reported; the readiness verdict will
   be computed the way `src/media/readiness.py` computes its own.
4. **The language-knowledge ladder of §28 already exists in another form**
   (ADR-021 acquisition states, `SourceTier`, human batch approval). Building a
   second one would be the duplication §2 forbids.

Next: **C01 — ecosystem research, provider comparison and licence matrix**
(§37–§40, §67), then the ADRs and schemas of §68–§69.
