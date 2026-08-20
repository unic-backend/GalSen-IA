# Open-Source Ecosystem Audit — final report

**Programme**: GalSen IA — Open-Source Ecosystem Audit & Integration
**Executed**: 12 chapters, **22 phases**, cadence two phases per turn
**Decision**: [ADR-037](../architecture/decisions/037-the-twelve-are-audited-and-none-is-integrated.md)
**Measured**: 2026-08-20, `Linux 6.18.5-fc-v20`, Python 3.11.15, 4 CPUs, no GPU

§14 asks for exactly twenty-two items. They are answered in order.

---

### 1. Repository state

Branch `claude/unit-tests-notification-search-file-4z0ok1`, clean, all work
pushed. `main` at `f08a4ff` (PR #32). **`git diff origin/main -- src/ tests/` is
empty** at every phase boundary of this programme.

### 2. Existing architecture state

Every provider abstraction §6 asks for already exists: `LLMProvider` /
`InferenceProvider` (`src/model_engine/providers/`, ADR-014),
`EmbeddingProvider` (`src/embeddings/`), `VectorStoreProvider`
(`SQLiteVectorStore`), `VoiceProvider` (`src/multimodal/`, a
`TranscriptionProvider` ABC plus registry), vision/video/image (`src/media/`),
`ResearchProvider` (`src/research/`, ADR-032), coding engines
(`src/coding_engine/`, ADR-028's capability router).

### 3. Projects already present

**Three.** Transformers (`requirements-training.txt`, imported inside a function
body at `train_adapter.py:115`), **vLLM** (named in the platform's own
unavailability message *with its port*), **OpenHands** (one of three declared
`CodingEngineAdapter`s).

### 4. Projects partially present

**Two.** llama.cpp — **one layer down and unnamed**, since `local_provider.py`
targets Ollama and Ollama is built on it. Unsloth's shape — `train_adapter.py`
already imports `AutoModelForCausalLM`, `AutoTokenizer`, `BitsAndBytesConfig`,
which is the quantized fine-tuning form.

### 5. Projects missing

**Seven**: SGLang, LiteLLM*, LangGraph, LlamaIndex, Qdrant, Open WebUI,
whisper.cpp. *\*LiteLLM is **installed in this environment**, declared by no
requirements file and imported by nothing — see item 10.*

### 6. Existing components reused

None consumed; **fourteen measured and cited**: `model_engine/` (33 modules,
`ModelRouter`, `FailoverModelRouter` at threshold 3 / reset 300 s,
`routing_policy.py` reading `config/model_routing.yaml`), `ProviderRegistry`,
`knowledge_engine/` (37 modules), `embeddings/vector_store.py`, `multimodal/`,
`coding_engine/` + its three adapters, `sandbox/policy.py`,
`tool/authorization.py`, `security/trust.py`, `security/redaction.py`,
`plugins/review.py`, `api/rbac.py`, `scripts/training/`, `audit_engine/`.

### 7. Duplication matrix

**2 `NO OVERLAP`, 4 `PARTIAL`, 4 `HIGH`, 2 `DIRECT DUPLICATE`.** Full matrix →
`duplication-matrix.md`.

§5 says a direct duplicate must not be installed. It fires correctly on Open
WebUI and **incorrectly on OpenHands**, which duplicates a seam this repository
built *for it*. A rule that fires on the wrong side of a seam is the rule
mis-read — recorded so a later reading does not delete an adapter.

### 8. Provider comparison

| | GalSen IA | The candidates |
|---|---|---|
| Provider abstraction | `providers/` + `ModelRouter` + externalised policy | LiteLLM offers the same, for platforms that lack it |
| Sovereign default | **hosted providers not registered at all** (ADR-014) | none — configuration decides |
| Fallback | `FailoverModelRouter`, 3 / 300 s | LiteLLM has its own — a **second** policy |
| Inference backends | any OpenAI-compatible server | vLLM, SGLang, `llama-server` — all three fit |

### 9. Licence matrix

**Ten of twelve are clean permissive grants** (5 MIT, 5 Apache-2.0), all
compatible with ADR-036. **Five carry a patent grant.** Two are not plain:
**LiteLLM** (MIT except `enterprise/`, whose licence returns **404** — while
PyPI declares plain MIT, the *more permissive* reading) and **Open WebUI**
(BSD-3 + clause 4, no rebranding above **50 users / 30 days**; PyPI agrees,
`Other/Proprietary License`).

### 10. Security findings

Three about **this** repository, none fixed:

- **S1** — `Role.USER` reaches `POST /coding/task`; `resolve_workspace()`
  accepts any host directory with **no permitted root**; `allow_network` and
  `allow_push` come from the body; `GALSEN_CODING_REQUIRE_CONTAINER` is off by
  default. **Latent**: all three engines are unavailable.
- **S2** — the training pipeline gates the run (ADR-006) but not the dataset's
  contents. **Latent**: nothing trains.
- **S3** — `litellm==1.81.10` installed, undeclared, unimported. Informational.

Nothing was weakened: ADR-014, `ENVIRONMENT_TRANSMIS` (six variables), ADR-006,
`security/trust.py` and ADR-034's four-tool allowlist are untouched.

### 11. Privacy findings

The candidates that improve privacy are the local ones — SGLang, llama.cpp,
whisper.cpp, all local inference, ADR-014's direction. The one that worsens it
is **LiteLLM**, whose 13 unconditional dependencies include
**`openai>=2.20.0`**, putting a hosted-vendor client in the environment whether
or not a key exists. §4G's rule about private training data is **S2**.

### 12. Performance measurements

| Vectors | Current `search()` | Cached matrix | Factor |
|---:|---:|---:|---:|
| 271 *(today)* | 70.42 ms · p95 **94.93 ms** | — | — |
| 10 000 | 1 232 ms | **0.37 ms** | 3 360 × |
| 100 000 | 13 132 ms | **3.88 ms** | **3 388 ×** |

Matrix RAM at 100 000: **153.6 MB**. *(E01 measured 1 943 / 27 944 ms on the
same path; two runs on a shared 4-CPU host vary by about two, stated rather than
averaged.)* Suite: `1 failed, 6967 passed, 12 skipped` — **fourteen identical
runs**.

### 13. GPU / resource measurements

**No GPU** (`ls /dev/nvidia*` → none) · 4 CPUs · ~15 GB RAM free · 28 GB disk ·
**`ffmpeg` → `command not found`** · Hugging Face **403** · `api.github.com`
**403** · `raw.githubusercontent.com` **200** · `pypi.org` **200**.

### 14. Integration recommendations

**None.** Zero of twelve.

### 15. Rejected integrations

**LlamaIndex** — a generic retriever returns the best available match; applied
to an empty domain that is exactly the wrong answer, and it is the answer this
architecture refuses. **Open WebUI** — licence *and* duplication of UI, auth and
accounts.

### 16. Deferred integrations

**LiteLLM** (placement `OUTSIDE`; licence `UNKNOWN`), **Qdrant** (reopened by
filtered search over millions of vectors, or a working set exceeding RAM),
**Unsloth** (a GPU host, an authorised dataset, a family to train — all three).

### 17. UNKNOWN items

1. vLLM / SGLang throughput and latency — no GPU.
2. llama.cpp and Transformers inference speed — no reachable model.
3. `faster-whisper` vs whisper.cpp — neither installed, no `ffmpeg`.
4. Unsloth VRAM saving — no GPU.
5. Qdrant / LangGraph / LlamaIndex overhead — not installed.
6. LiteLLM's `enterprise/` terms — **404**.
7. Licence history for all twelve — `api.github.com` **403**.
8. Model-weight terms for every candidate that loads weights.

### 18. Known limitations

- **Four candidates are recorded *not needed*, not *not better*.** Nobody
  measured them, and the report does not pretend otherwise.
- **One measurement carries the programme.** The vector-search figure is a
  benchmark on a 4-CPU host with stated variance, not a service level.
- **Dependency counts are declarations**, read from metadata — no candidate's
  code was audited.

### 19. Regression status

**PASS.** A full regression ran after **every phase** — fourteen runs, all with
the same single failure: `test_l_etiquette_de_la_version_courante_existe_bien`.
The `v0.1.0` tag has never been pushed, so it fails identically on `main` and in
CI. **Not caused by this programme.**

### 20. Proposed target architecture

**The current one.** Inference through `GALSEN_OPENAI_COMPATIBLE_URL`; routing
in `src/model_engine/`; knowledge in `src/knowledge_engine/` + `src/embeddings/`
**with the caching defect fixed**; voice in `src/multimodal/`; the one
orchestrator; training in `scripts/training/`; the platform's own UI.

**One gap named**: `docs/deployment/` does not say what the unavailability
message says — that any OpenAI-compatible server serves this platform.

### 21. Implementation order

Conditional, and **no condition is met**: (0) fix the vector-search cache —
in-process, no dependency, 3 388 ×; (1) close the documentation gap, which
settles three candidates at once; (2) whisper.cpp *beside* `faster-whisper`,
only on a host that can compare them **with Wolof in the sample**; (3) Unsloth
when the occasion exists; (4) Qdrant only if (0) proves insufficient.

### 22. Next implementation phase

**There is none, and none is requested.** §12's order is audit, then stop. The
most valuable thing found is **step 0**, and it is a finding about this
repository rather than an integration — a suggestion, not a task.

---

## Two claims this report does not make

**Not "production ready".** No claim of readiness appears; nine performance rows
are `UNKNOWN`.

**Not "these projects are inferior".** Twelve serious projects were read
carefully and none was needed *here*. That is a statement about this
repository's coverage, not about their quality.

## What the audit found about GalSen IA

1. **`SQLiteVectorStore.search()` — 3 388 × slower than ADR-015's own design.**
2. **§4F's constraint unmet** — an ordinary `user` reaches the coding engine.
3. **Training gates the run, not the data.**
4. `litellm` installed, unowned.

**Fourth consecutive external audit to find a defect here rather than in its
subject.** ADR-034 found the sovereignty blind spot, ADR-035 the missing
`LICENSE`, ADR-036 fixed the licence — and this one found that a database was
about to be blamed for a caching bug.
