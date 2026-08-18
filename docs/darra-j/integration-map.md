# Darra J — integration map (VOLET 1)

What already exists in GalSen IA, what Darra J reuses, and the short list of
things that genuinely do not exist yet. Measured on `1a586bc` — every row below
was read in the repository, not assumed.

The directive's rule XLIX is the reason this document exists: *do not assume the
architecture described above does not already partially exist.* Most of it does.

## Reused as-is — no new implementation

| Darra J requirement | What already carries it | Why it is not rebuilt |
|---|---|---|
| VIII — source authority tiers | `SourceTier` (`source_registry.py`): `A_PRIMARY_OFFICIAL`, `A_ACADEMIC`, `B_INTERNATIONAL`, `C_SECONDARY`, `D_DISCOVERY_ONLY`, plus `RANGS_ACQUERABLES` | The distinction the directive asks for — *what may this source be used for*, not *who published it* — is exactly what `SourceTier` already encodes. Darra J adds a mapping, not a second hierarchy. |
| X, XI — ingestion states and human validation | `AcquisitionStatus`: `DISCOVERED → PARSED → VERIFIED → INGESTED`, with `QUARANTINED` and `REJECTED`, and **`VERIFIED` reachable only by a human decision** (ADR-021) | The directive's `INGESTED/PARSED/VALIDATION_REQUIRED/VALIDATED/PUBLISHED/SUPERSEDED/REJECTED` is the same machine with education-specific names. Darra J maps its publication states onto it and adds only what curriculum needs: `PUBLISHED` and `SUPERSEDED`. |
| XI — human-in-the-loop authority | `src/approval_engine/` (ADR-006) + the batch approval of `src/acquisition/gate.py` | A second approval gate would be a second thing to bypass. |
| XX, XXI — access control | `src/api/rbac.py` (`Role`, `Permission`, server-side `require_permission`) and `src/security/isolation.py` (`Owner`, `Audience`, `may_read`, `may_store`) | Student-to-student isolation is the same question the platform already answers for user memory. Darra J adds education roles and permissions to the existing enums. |
| XXII — canonical vs AI memory | `src/memory_engine/layers.py` — a layer **is** a lifetime | Darra J adds one layer above them all: canonical institutional memory, which no conversation may write. |
| XXIII, XXIV — factuality | `src/knowledge_engine/scope.py` (scope × subject), `routing.py` (which layer answered, and why), `domains.py` (five states of an empty domain) | `UNKNOWN` is already a first-class answer here, and the routing already refuses to let a global source answer a national question. |
| IX — provenance | `src/knowledge_engine/entities.py` (entities *and* relations carry provenance), `src/acquisition/manifest.py` (`content_hash`) | Nothing enters this repository without a source; that rule is older than Darra J. |
| XXVII, XXVIII — multilingual | `corpus/languages/aliases.yaml` (16 concepts, 115 terms), `src/wolof/`, `src/services/wolof/` (2105 sentences, CLAD orthography) | Wolof capability is **measured** here, not claimed — which is precisely what XXVIII demands. |
| XXXII — evaluation | `factual_evaluation.py` (`benchmark_coverage`, four states), `docs/evaluation/*.jsonl` (0 verified entries, and it says so) | The barème already refuses entries written from memory. Darra J's curriculum benchmark inherits that refusal. |
| XXXIV — storage | ADR-005: `GALSEN_STORAGE_BACKEND` (`in-memory` / `sqlite`), `GALSEN_DATA_DIR` | Canonical curriculum selects its store the same way every other engine does. |
| XXXVI — model independence | `src/model_engine/` (ADR-014, ADR-018: interchangeable providers) | The LLM is already a replaceable component, not the database. |
| XXXVII — auditability | `src/audit_engine/`, `src/api/tracing.py`, `/observability/trail/{id}` | One job already carries one identifier across subsystems (VOLET 66). |
| XXXVIII — no accidental deletion | Self-healing harness: immutability policy, isolated worktrees, rollback (`docs/agent/README.md`) | Historical curriculum versions become protected paths; the harness already refuses to touch what it is told not to. |
| XLI — routines, plugins, connectors, agents | VOLETs 47–67 | A curriculum import can be a routine; nothing new is needed to schedule it. |

## Genuinely new — what Darra J must build

| # | Component | Why nothing existing covers it |
|---|---|---|
| 1 | **Canonical curriculum objects** (`Curriculum`, `Grade`, `Subject`, `Period`, `CurriculumUnit`) | The knowledge engine stores *fragments with provenance*. A curriculum unit is a **record with identity**: same year + grade + subject + week must resolve to the same object, byte for byte. That is a different data shape, not a different quality of the same one. |
| 2 | **Deterministic resolution** (V, XXVI) | Existing retrieval is lexical/semantic. A curriculum question must resolve *dimensions* first — year, grade, subject, week, version — and answer `AMBIGUOUS` rather than pick. |
| 3 | **Curriculum version register** (VII) | Versions here are institutional and must remain separately addressable forever. Nothing in the repository versions knowledge by publishing authority and effective date. |
| 4 | **Cross-user consistency** (VI) | Four differently-worded questions from four roles must resolve to one object. This is a property to **test**, and the test is the deliverable. |
| 5 | **Conflict records** (XXV) | The world knowledge reports disagreements side by side and never reconciles them; curriculum needs the same idea with a *resolution workflow* attached. |
| 6 | **Education roles** (XXI) | `student`, `parent`, `teacher`, `school_admin`, `education_authority`, `researcher` do not exist in `Role`. |
| 7 | **Mastery model** (XXX) | Per-competency, with *insufficient evidence* as a first-class state. |
| 8 | **Educational graph** (XXIX) | Grade → subject → unit → objective → prerequisite → exercise → mastery. |

## The rule that shapes every one of them

The repository already refuses to write knowledge from memory. Darra J narrows
that further: **the canonical curriculum is empty, and it stays empty until an
authorized dataset is imported.** Fixtures used by tests are marked
`NON_OFFICIAL_TEST_DATA` and the engine refuses to publish them as official.

Expected state at the end of this programme, and it is the honest one:

> **ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING.**
