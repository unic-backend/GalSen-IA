# K00 — what GalSen IA already owns

Creative Canvas directive, §27 STEP 1–4 (K00.1: creative/video and the registry
inventory; K00.2: security, self-healing, memory, provenance).
Measured on 2026-08-19 at `a63a7c2`.

**§3 and §13 forbid rebuilding what exists.** This audit's job is to say what is
already here and — more usefully — **what each thing does not do**, so the
canvas is designed against reality rather than against a wish.

---

## K00.1 — the creative and video layer

### §11 lists fifteen registry-like types. Three registries already exist.

M00.2 established that; §11 is where it becomes dangerous, because a list of
fifteen names invites fifteen new classes.

| §11 asks for | Already exists | Where |
|---|---|---|
| `ProviderRegistry` | **yes, twice** | `creative/providers.py`, `model_engine/providers/provider_registry.py` |
| `ModelRegistry` | **yes** | `model_engine/model_registry.py` |
| `GenerationRequest` | **yes** | `media/providers/base.py` |
| `ProviderCapability` / `ModelCapabilityProfile` | **yes** | `media/providers/base.py` |
| `ProviderLicense` | **yes**, as `LicenceRecord` | `creative/providers.py` |
| `ProviderCost` | **yes**, as a field | `CreativeProvider.cost_per_second` |
| `ProviderLatency` | **yes**, as a field | `CreativeProvider.typical_latency_s` |
| `ProviderAvailability` / `ProviderHealth` | **yes**, as a probe | `availability()`, each adapter's `health()` |
| `GenerationResult` / `GenerationError` | **partial** | adapters raise named exceptions; no shared result type |
| `ProviderQuality` | **absent, deliberately** | ADR-026: no measure exists, so no score is produced |
| `ProviderPrivacyPolicy` | **absent** | genuinely missing — see below |

`CreativeProvider` already carries fifteen fields: `provider_id`, `version`,
`tasks`, `input_modalities`, `output_modalities`, `requires`, `min_vram_gb`,
`licence`, `invocation`, `runs_locally`, `deterministic`, `cost_per_second`,
`typical_latency_s`, `capability_status`, `limitations`. `LicenceRecord` carries
six: `repository`, `weights`, `dataset`, `commercial`, `verified_from`,
`restrictions`.

**So §11 is mostly satisfied by fields on two existing types.** The honest gaps
are two:

- **`ProviderPrivacyPolicy`** — nothing records where a provider sends data,
  whether it retains it, or whether local execution is possible. §20 asks for
  exactly this, and it does not exist. **This is a real gap.**
- **`GenerationResult`** — each adapter refuses in its own way. A shared result
  type would matter the day two providers actually run. Today none does.

### Video generation, per §13

Unchanged since M01, and re-verified: 17 media stages, **10 READY, 6 BLOCKED,
1 ABSENT**; four of the six blocks are one missing `ffmpeg`. Two provider
adapters, both refusing: `wangp.py` (needs a GPU and an uninspected licence) and
`moneyprinterturbo.py` (needs `ffmpeg`, a service, a stock-library key).

**Nothing in this platform can generate an image or a video today.** Any canvas
node that claims otherwise would be claiming something no measurement supports.

### What is already built, and must not be rewritten

`reference/` (entity, ingestion, memory, consent), `world.py`, `direction.py`
(shot planning), `verification.py` (identity, drift, continuity), `routing.py`
(capability matching, refusal to substitute), `style.py` (§10's style, kept out
of the world), `jobs.py` (provenance, reference→artefact link).

---

## K00.2 — security, self-healing, memory, provenance

This ground was **not** audited by the MoneyPrinterTurbo programme. It is new
here.

### Security: measured, and it refuses to give itself a grade

`src/security/posture.py` returns `score: None`, with a reason worth quoting
because it is the discipline this whole platform runs on:

> *"Aucune note globale : une note ferait disparaître la faille qui compte
> derrière la moyenne de celles qui ne comptent pas."*

**Seven gaps, measured, not remembered:**

| Area | Gap |
|---|---|
| execution / filesystem | a child reads and writes wherever the user can |
| execution / network | no network cut without namespaces |
| execution / processes | `RLIMIT_NPROC` bounds the *user*, not this sandbox |
| identity | identities are not verified — a key proves an attribution |
| approval | the gate is in memory: a restart loses pending decisions |
| audit | the trail is in memory: a restart erases activity history |
| recovery | in-memory store: nothing to back up, nothing survives |

**Three of these seven matter directly to this programme.** A canvas that
uploads a person's photograph inherits the filesystem gap; a node that calls an
external provider inherits the network gap; and any consent decision inherits
the in-memory approval gate. They are not blockers for a design phase — they are
constraints the design must not pretend away.

### The trust boundary — reuse it, do not rebuild it

`src/security/trust.py` declares seven levels: `SYSTEM`, `DEVELOPER`, `USER`,
`TOOL`, `RETRIEVED`, `DOCUMENT`, `EXTERNAL`, with `wrap()` and `inspect()`.

**§19 asks about prompt injection and malicious media.** The mechanism exists.
What is missing is not a boundary — it is that **no canvas node type has a
declared trust level yet**. That is a K03 design question, not a new module.

### Self-healing — richer than expected, and constrained

`src/agent/self_healer.py` exposes `diagnose`, `propose_patch`,
`create_patch_context`, `apply_patch`, `run_validation`, `rollback`, `resolve`,
`limits`.

**`rollback` and `run_validation` existing is what makes §24's new permanent rule
implementable** rather than aspirational. The plumbing to validate and undo is
already here.

### Memory and provenance

`src/memory_engine/` — interfaces, layers, cache, indexer.
Provenance lives in two places for two purposes: `src/acquisition/` (knowledge
provenance, ADR-021, ten quality checks) and `src/creative/jobs.py` (artefact
provenance, §33 of the previous directive — inputs, references, provider, model,
seed, SHA-256).

**§8 says do not duplicate the provenance system. There are already two**, and
they are legitimately different: one records where a *fact* came from, the other
where an *artefact* came from. A canvas node produces artefacts, so it uses the
second. Writing a third would be the mistake.

---

## What K00 concludes

**Three things are genuinely missing**, and they are small:

1. **`ProviderPrivacyPolicy`** — §20's question has no home. Where does user
   media go, is it retained, is local execution possible.
2. **A trust level per canvas node type** — the boundary exists, the mapping
   does not.
3. **A shared `GenerationResult`** — moot until two providers run.

**Everything else §5 through §17 asks for already exists in some form.** The
canvas is therefore a *composition* problem, not a construction problem — which
is the opposite of what a node-graph reference implementation would suggest, and
the reason §5 says "do not simply embed OpenCanvas".

**One thing the design must not pretend away**: nothing here generates. A canvas
whose Image and Video nodes cannot run is honest only if it says so, the way
`readiness()` does for the media engine.
