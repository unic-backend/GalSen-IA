# Creative schemas (C03, directive V4 §69 items 6–15)

The data structures the orchestration layer owns, written before they are
implemented so that C05 onward has something to build against rather than
invent. Every schema here follows one rule the rest of this repository already
holds:

> **A field is measured, declared, or absent — and absence carries its reason.**
> There is no default value that stands in for a fact nobody established.

Field status vocabulary, used wherever a provider or a capability is involved
(§9): `SUPPORTED` · `PARTIAL` · `UNKNOWN` · `UNSUPPORTED`.
Evidence vocabulary, used wherever a value could have come from a model:
`MEASURED` · `DECLARED` · `AI_DERIVED` · `ABSENT`.

---

## 1. `CreativeRepresentation` (§5)

Structured intent. **Not a prompt** — §5 says the engine must not rely only on
natural language, and a prompt cannot express which of its parts were stated by
the user and which were inferred.

```
CreativeRepresentation
├── representation_id
├── intent                  # what the user asked for, kept verbatim
├── intent_source           # USER_TEXT | USER_SPEECH | DOCUMENT | MIXED
├── domain                  # a declared narrative structure, or UNSPECIFIED
├── duration_seconds        # None when not stated — never a default
├── aspect                  # UNSPECIFIED until stated
├── languages[]             # per language: understood?, speakable?
├── entities[]              # -> EntityRef
├── environments[]          # -> WorldRef
├── shots[]                 # -> Shot
├── audio_plan              # -> AudioPlan
├── style                   # -> StyleRef, separate from WorldState (§46)
├── continuity_constraints[]
├── references[]            # -> ReferenceEntity ids, with consent checked
├── clarifications[]        # open questions; a plan with any is not executable
└── provenance              # who/what produced each field
```

**Invariant.** A field the user did not state is `UNSPECIFIED` and produces a
clarification. `src/media/tools/intent.py` already implements exactly this for
media requests and is the starting point, not a second implementation.

---

## 2. `ReferenceEntity` (§9, ADR-025)

```
ReferenceEntity
├── reference_id
├── entity_type             # human | animal | vehicle | product | object |
│                           # robot | creature | 2d | 3d | environment | other
├── identity                # -> IdentityRepresentation
├── visual_identity         # appearance, geometry, proportions, features
│   └── per field: value, evidence, confidence, observed_from[]
├── motion_characteristics  # from video references only
├── voice_reference         # -> VoiceReference
├── language_reference      # languages observed in the reference media
├── style_reference
├── source_media[]          # -> SourceMedium (path, hash, kind, uploaded_by)
├── provenance              # who supplied it, when, from where
├── consent                 # -> ConsentScope   (required; absent = unusable)
├── permissions             # -> Permissions
├── retention_policy        # duration | until_revoked | single_use
├── verification_metadata   # -> per-dimension status, see §4 below
├── status                  # ACTIVE | REVOKED | EXPIRED
└── versions[]              # append-only; a replaced version is SUPERSEDED
```

**Invariants.**
- No `ConsentScope` → the reference **cannot be used**. Absence of a scope is
  absence of permission, not permission by default.
- `visual_identity` fields are per-field: front view `MEASURED` from three
  images, rear view `ABSENT`. A single embedding could not say that, which is
  why §9 forbids reducing a reference to one.
- `status: REVOKED` is terminal for *use* and permanent for the *record*.
- Every version is kept. There is no delete method — the discipline
  `src/media/core/project.py` already holds.

### 2.1 `ConsentScope`

```
ConsentScope
├── granted_by              # a named person, never the platform
├── granted_on
├── subject                 # who the reference depicts
├── permitted_uses[]        # e.g. project:<id>, commercial, internal_test
├── permitted_scope         # PROJECT | ACCOUNT | ORGANISATION
├── expires_on              # None = until revoked, never "forever"
├── may_share               # default false
└── evidence                # how consent was captured
```

**Invariant.** `permitted_uses` is a whitelist. A use not listed is refused, and
the refusal names the missing permission — the shape `src/tool/authorization.py`
already uses for tool ceilings.

### 2.2 `SourceMedium`

```
SourceMedium: medium_id, kind (image|video|audio), path, sha256,
              uploaded_by, uploaded_on, analysed (bool), analysis_status
```

Hash is mandatory: without it, "delete the media I uploaded" cannot be answered
across copies.

---

## 3. `WorldState` and `WorldMemory` (§16, §17)

```
WorldState                              WorldMemory
├── world_id                            ├── memory_id
├── environment                         ├── architecture / geometry / layout
├── entities[]      -> EntityState      ├── recurring_objects[]
├── objects[]                           ├── recurring_entities[]
├── crowd           -> CrowdSpec        ├── lighting / atmosphere
├── lighting / weather / time           ├── environmental_references[]
├── audio_state                         └── style
├── camera          -> CameraState
├── spatial_relations[]
├── temporal_state
├── references[]
└── continuity_constraints[]
```

**Invariants.**
- `WorldState` is the canonical source of truth for continuity; every shot names
  the world it belongs to.
- `WorldMemory` is **independent** of `CharacterMemory` (§17). A recurring shop
  and a recurring shopkeeper are separate facts and must be replaceable
  separately.
- Style is **not** part of `WorldState` (§46): the same world can be rendered
  photorealistic or animated.

---

## 4. `Shot`, `EntityState`, `CharacterMemory` (§14, §15, §19)

```
Shot                                    EntityState
├── shot_id, index                      ├── entity_id, reference_id?
├── world_id                            ├── entity_type
├── entities[]      -> EntityState      ├── position / orientation
├── director        -> DirectorSpec     ├── action / gaze / emotion
├── duration_target / duration_measured ├── clothing / props
├── audio_segment_ids[]                 └── fidelity  # HERO | SUPPORTING |
├── continuity_constraints[]                          # BACKGROUND | CROWD
├── generation_status
└── verification    -> ShotVerification
```

**Invariants.**
- `duration_target` and `duration_measured` are separate fields. The media
  engine learned this: a target written into a measured field becomes a
  measurement nobody took.
- `fidelity` drives resource allocation (§20): a background pedestrian does not
  get hero-level verification or hero-level compute.
- `CharacterMemory` holds appearance, proportions, clothing, colours,
  personality, voice, language, accent, relationships and references — and it
  **promises no consistency**. It supplies conditioning; verification says what
  actually happened.

---

## 5. Verification (§48, ADR-026)

```
ShotVerification
├── shot_id
├── dimensions[]
│   └── DimensionResult
│       ├── dimension        # facial_similarity | appearance | proportions |
│       │                    # clothing | distinctive_features | colour | motion
│       ├── outcome          # MEASURED | NOT_MEASURABLE | FAILED
│       ├── value            # only when MEASURED
│       ├── method           # REQUIRED when MEASURED: what was compared, how
│       ├── scale            # what the number means
│       ├── missing_capability   # REQUIRED when NOT_MEASURABLE
│       └── confidence
├── verdict                  # VERIFIED | INCOMPLETE | FAILED
└── affected_shots[]
```

**Invariants.**
- **No composite score.** There is no field for one, deliberately.
- `MEASURED` without `method` is refused at construction. A number whose
  derivation is unrecorded is exactly the fabrication §48 forbids.
- `verdict: VERIFIED` requires every applicable dimension `MEASURED`. Any
  `NOT_MEASURABLE` → `INCOMPLETE`, never "passed with reservations".
- On this machine every visual dimension will be `NOT_MEASURABLE` and every
  verdict `INCOMPLETE`. That is the correct output, and it will look empty.

---

## 6. Language (§25, §28, §30, ADR-027)

```
AudioSegment                            LanguageObservation
├── segment_id                          ├── observation_id
├── start / end        # MEASURED       ├── language / dialect / region
├── speaker_id         # diarization    ├── expression / meaning / context
├── language           # per SEGMENT    ├── examples[]
├── language_confidence                 ├── pronunciation
├── transcript?        # None if none   ├── status  # OBSERVED | CANDIDATE |
├── transcript_source  # MEASURED|ABSENT│           # CORROBORATED | VALIDATED |
├── prosody / emotion                   │           # OFFICIAL | UNKNOWN
└── original_audio_path # always kept   ├── observed_count
                                        ├── validated_by   # a named human
                                        ├── privacy  # PRIVATE | GLOBAL
                                        └── provenance / history[]
```

**Invariants.**
- Language belongs to a **segment**, never a file (§25). One recording holds
  several.
- `original_audio_path` is never dropped. §22's default depends on it existing.
- **`observed_count` can raise status to `CORROBORATED` and no further.**
  `VALIDATED` needs a named human; `OFFICIAL` needs an authority that is not the
  platform. Frequency is not truth.
- `PRIVATE` observations never migrate to `GLOBAL` without recorded consent
  (§58).

---

## 7. Provider and job (§34, §53, ADR-024)

```
CreativeProvider                        CreativeJob
├── provider_id / version               ├── job_id / user
├── tasks[]          # declared         ├── inputs / references[]
├── input_modalities / output_modalities├── provider_id / model / version
├── capability_status  # per field      ├── status  # reuses RunStatus
├── availability       # PROBED         ├── progress  # done/total, None if
├── resource_requirements                │             # total unknown
├── licence  -> LicenceRecord           ├── logs / artifacts[] / errors[]
├── invocation  # IN_PROCESS |          ├── provenance
│               # OUT_OF_PROCESS | API  ├── resource_usage
├── cost_metadata                       └── cost_metadata
└── limitations[]
```

**Invariants.**
- `licence` and `invocation` are **routing inputs**, not documentation
  (ADR-024). A provider whose commercial status is `UNKNOWN` is not selectable
  for a commercial job; a copyleft provider declares `OUT_OF_PROCESS`.
- `capability_status` is what the provider *claims*; `availability` is what a
  probe *measured*. Both, always.
- `CreativeJob.status` reuses `RunStatus` from
  `src/router/workflow_checkpoint.py`. No second vocabulary.
- `progress` is `done / total` of a counted unit and `None` when the total is
  unknown — never `0`.

---

## 8. Provenance (§55)

Every generated artefact records: inputs, references used, provider, model,
version, parameters, seed where applicable, transformations, post-processing,
timestamp, SHA-256.

**Invariant.** An artefact must name the references that conditioned it.
Without that link, ADR-025's revocation cannot propagate, and "delete my
reference" becomes a promise nobody can keep.

---

## What is deliberately not here

- **No schema for a "creative quality score".** Quality is per-dimension and
  per-check, for the same reason identity is (ADR-026).
- **No schema for training data.** §73 keeps training a separate, controlled
  pipeline; giving it a schema here would imply it is planned work.
- **No GPU scheduler schema.** ADR-032 is reserved and undecidable until a GPU
  host exists; inventing its fields now would be speculative design (§72).
