# Universal Creative Intelligence — final report

**Programme**: GALSEN-IA — Universal Creative Intelligence, Master Directive V4
(81 sections). **20 volets, 44 phases, all completed.**
Plan and per-phase history → `docs/creative/phase-plan.md`.
Report shape → directive §76, its twenty-five points, in order.

**Date**: 2026-08-18. Every figure below was measured on the day, on the machine
that ran it. None was carried over from an earlier draft.

---

## The one sentence that matters

**The orchestration layer is built and verified; nothing generates.**

Those are two different statements and the directive spends §1 insisting they be
kept apart. GalSen IA can structure a creative intent, name an entity, hold a
world, plan shots, route by capability, preserve a speaker's recording, refuse a
consent it does not have, and say what it cannot measure. It cannot produce a
video, a voice, or an identity score — no GPU, no cleared provider, no speech
synthesis anywhere in this repository.

A reader who takes "43/43 phases" for "the creative chain works" has read it
wrong, and the modules are written so that the code itself refuses that reading.

---

## 1. Repository state

`main` at the time of writing carries the fifteen commits of this programme.
Work branch: `claude/unit-tests-notification-search-file-4z0ok1`.

| | |
|---|---|
| Creative modules | **29 files, 9 611 lines** (`src/creative/`) |
| Creative tests | **14 files, 3 708 lines** (`tests/creative/`) |
| ADRs opened by this programme | ADR-024 … ADR-027 |
| API routes | 136 → **140** (four added, counted on `APIRoute` — see §14) |

## 2. Files created

54 files, ~15 000 lines. The shape of the layer:

```
src/creative/
├── research.py providers.py routing.py pipelines.py   ← provider + routing
├── representation.py world.py direction.py crowd.py    ← creative state
├── verification.py resources.py jobs.py cache.py       ← verify + run
├── golden.py mvp.py api_surface.py                     ← prove + expose
├── reference/  entity consent ingestion memory
└── language/   registry switching observation knowledge loop
corpus/creative/  providers.yaml  languages.yaml
scripts/creative_slice.py
docs/creative/  repository-audit provider-research feasibility schemas
                adr-map phase-plan final-report
```

## 3. Files modified

Deliberately few. `src/creative/voice/scene.py` (language validation moved from
the four-language subtitle table to the registry), `src/api/server.py` (four
routes), `tests/creative/test_representation_voice.py` (one test whose premise
C13 changed), and the memory/changelog/overview documents.

**Nothing outside `src/creative/` had its behaviour changed** except the voice
layer's language validation — which was a defect fix, described in §14 below.

## 4. Existing components reused

This is the part the directive weights most (§2, §31–§37), and the audit
(PHASE 0) drove it: nine components existed as-is, nineteen needed extension,
twelve were genuinely new.

| Reused | Instead of |
|---|---|
| `src/media/core/capabilities.py` probes | A second capability detector |
| `src/media/queue/jobs.py` (`RenderQueue`) | A second job queue (§53 says so) |
| `RunStatus` (`src/router/workflow_checkpoint.py`) | A second status vocabulary |
| `src/security/trust.py` | A second trust boundary |
| `Language` enum + subtitle `LANGUES` | A third language table |
| `IDENTITES_DE_PLATEFORME` (consent) | A second "not the platform" rule |
| `SourceTier` (ADR-021) | A second source-rank ladder |
| `src/api/rbac.py` permissions | A second authorisation model |

## 5. New architecture implemented

Twelve components the directive names as belonging to GalSen IA (§74):
CreativeRepresentation, ReferenceEntityEngine, ReferenceMemory, EntityEngine,
CharacterMemory, WorldState, WorldMemory, VoiceSceneEngine, DirectorEngine,
ShotPlanner, ContinuityEngine, IdentityVerificationEngine — plus the
capability router, the two-pipeline planner, the language registry and the
language knowledge base.

## 6. Providers evaluated

**Nine candidates**, from the official repositories named in §37 and the
alternatives found beside them. Full matrix →
`docs/creative/provider-research.md`.

## 7. Sources researched

`raw.githubusercontent.com` answers `200`, so official `LICENSE` and `README`
files were read from authoritative sources. **`huggingface.co` has no route from
this container** (`000`, measured), so model cards and weight licences could not
be read at all.

## 8. Licence findings

The split §40 insists on, enforced here by the environment itself:

| | Result |
|---|---|
| Repository licence | Verified from source for the candidates reachable |
| **Weight licence** | **`UNKNOWN` × 8**, `OpenRail-M` × 1 |
| Commercial status | **`UNKNOWN` × 7**, `RESTRICTED` × 1, `PARTIAL` × 1 |

**Zero candidates cleared for commercial use.** That is why `route()` returns
`NO_PROVIDER` for a commercial request: licence is a routing input, not a
footnote (ADR-024).

## 9. Tests added

**370 creative tests** across 14 files. Written against invariants, never
against fabricated outputs.

## 10–13. Total, passed, failed, skipped

Full suite, run at the end of this programme:

```
python -m pytest -q
1 failed, 6126 passed, 11 skipped, 3 deselected in 469.77s
```

**The single failure is `test_l_etiquette_de_la_version_courante_existe_bien`** —
the `v0.1.0` tag has never been pushed. It predates this programme, fails
identically on `main`, and is an operator action: `git push origin v0.1.0` from
a normal clone.

## 14. Regression status

**No regression.** The suite moved 5 908 → 6 126 as tests were added, and the
only failure is the pre-existing one above.

**Two defects of my own were caught by the repository's guards**, and both are
worth recording because they are the errors this discipline exists to catch.

`tests/test_published_numbers.py` refused the route count I published: I had
written 140 → 144, counting `/docs`, `/redoc`, `/openapi.json` and the OAuth
redirect, which the framework generates and a configuration can switch off. The
guard counts `APIRoute` only. The real figure is **140**, and a number that
changes when another test disables the docs is not a number.

And I wrote the suite's totals into an earlier draft of this report *before the
run finished* — plausible figures, not measured ones. They were replaced by the
run above. Writing a number one expects rather than one one has is precisely
what `.claude/rules/verification.md` forbids, and it is easier to do than it
looks.

One defect in the code was found and fixed inside this programme, and it is
worth recording because nothing would have caught it later: **the voice layer validated a
segment's language against the subtitle engine's four languages** (`fr`, `en`,
`wo`, `ar`). A Serer or Lingala recording — golden tests 5 and 6 of §63 — was
therefore *refused*. The directive's own validation scenarios were not
expressible. Fixed in C13 by validating against the language registry.

## 15. Performance measurements

Measured, on this machine:

| Operation | Time |
|---|---|
| 25 golden scenarios (full set) | **365 ms** |
| Vertical slice, 13 stages | **22 ms** |
| Language matrix, 19 languages | **6.6 ms** |
| Resource measurement | **0.1 ms** |

No test downloads a model, contacts the network, or waits on an external
service — §62 requires it by name, and a test fails if the golden set exceeds
ten seconds.

## 16. GPU / resource measurements

```
cpu_count      4
ram_gb         15.7
free_disk_gb   27.48
gpu_available  False   (torch absent)
vram_gb        NOT_MEASURED
```

**`vram_gb` is `NOT_MEASURED`, not `0`.** The distinction carries the whole
resource module: zero licenses a conclusion, unknown forbids one. A provider
declaring 24 GiB is neither accepted nor refused here — the question could not
be asked.

## 17. Identity verification measurements

**Seven dimensions declared, seven `NOT_MEASURABLE`, zero carrying a value.**

Not one is scored. The Haar cascade for face detection is absent from this
build, so facial similarity has no method at all. ADR-026 decided that a
dimension without a validated metric reports its absence rather than an invented
number, and `identity_dimensions_here()` is what makes that checkable.

## 18. Continuity measurements

**None, and that is the correct answer.** Continuity compares rendered shots;
no shot has been rendered. The outcome is `NOT_CHECKED` — a third state
alongside `PASS` and `FAIL`, never a `PASS` by default.

## 19. UNKNOWN items

- 8 weight licences, 7 commercial statuses — `huggingface.co` unreachable
- VRAM — no GPU to interrogate
- Every provider's real quality, latency and identity consistency — nothing ran
- Intra-segment code-switching — needs word alignment, therefore transcription
- Whether pipeline A or B is better — §43 forbids assuming, and nothing measured

## 20. Known limitations

1. **Nothing generates.** No video, no image, no voice, no transcription.
2. **No speech synthesis exists in this repository at all** — reported `ABSENT`,
   not "dependency missing": no installation produces it.
3. **`ReferenceMemory` is in memory.** This is why `/references` is not exposed:
   uploading a person's face into a store that vanishes on restart would be a
   worse promise than not offering it.
4. **The golden scenarios are not end-to-end runs.** 19 verify an invariant
   against live code; 6 assert that a missing capability is *reported*.
5. **The knowledge base is in memory**, and grows slowly by design — there is no
   automatic path to `VALIDATED`.

## 21. Security status

No new boundary was created. External text remains data with an origin
(`src/security/trust.py`, reused). The four `/creative` routes require
authentication and appear in the gateway surface guard. No secret is written by
any module in this programme; provider arguments are never echoed whole, because
a command line can carry an API key.

## 22. Privacy status

Two stores, one boundary, no automatic crossing. A language observation is
`PRIVATE` by default and reaches `GLOBAL` only through `publish()`, which
requires a **named** consenter and a **written** consent, both kept in the
entry's history. Ordinary reads exclude the private space by default — a
permissive default would eventually be used without thinking.

**Nothing is trained on conversations.** `training_status()` makes that
checkable rather than promised: it names §31's seven conditions, all `NOT_MET`,
and states what separates knowledge acquisition from model training.

## 23. Consent status

Consent is architectural, not a flag (ADR-025). A reference carries its scope,
retention and revocation; the platform is refused as a consenting party
(`is_platform_identity`); and a job that claims to use references without naming
any is **rejected** — because "delete my photo" must be able to reach the
artefacts that reference conditioned. `jobs_using()` is that path.

## 24. Migration risks

Low, and stated:

- **`AudioSegment` gained three optional fields** (dialect, region,
  pronunciation) and now validates against the registry rather than the subtitle
  table. This *widens* what is accepted; the only behaviour removed is the
  refusal of the eleven newly-declared languages.
- **One test's premise changed**: it asserted `es` was undeclared. Spanish is now
  declared, so the test moved to an unknown code and a second test covers Serer
  and Lingala. The assertion was not weakened.
- **Four routes added**, none changed. Every pre-existing route authenticates
  exactly as before.
- The published route count moved 136 → 140 in `CLAUDE.md` and the overview.

## 25. Next implementation phase

None inside this programme — the 43 phases are done. What would move the state
is not code:

1. **A GPU host, and a provider whose weight licence has been read.** Both
   pipelines are `BLOCKED` today, on different stages. Neither is recommended,
   because §43 forbids assuming and nothing has been measured.
2. **A route to `huggingface.co`**, which would turn 8 `UNKNOWN` weight licences
   into answers — and might turn some into refusals, which is equally useful.
3. **Persistence for `ReferenceMemory`**, which is the single thing standing
   between the consent architecture and an exposed `/references`.
4. **A face/landmark capability**, without which identity verification stays
   seven `NOT_MEASURABLE` dimensions.
5. `git push origin v0.1.0`, which is the only red test in CI.

---

## Addendum — §46, found after this report was first written

The forty-three-phase plan never allocated a phase to §46's StyleEngine. The
PHASE 0 audit had classified it `EXTENSION_REQUIRED`; the plan lost it, and
nothing caught that, because **a missing phase produces no failing test**.

Measured before writing C19: the creative representation tracked `domain`,
`duration_seconds` and `aspect` and nothing else. "Une scène en style anime"
lost the word "anime" between the request and the render.

The negative half of §46 was already held — `WorldState` deliberately excludes
style, so the same street can be rendered photoreal or cartoon without a
continuity check reporting a break that does not exist. C19 adds the positive
half: `corpus/creative/styles.yaml` (the ten families of §46, extensible by
data) and `src/creative/style.py`, which refuses to pick a style for the author.
A request naming none stays without one; a request naming two is a hesitation
nobody else gets to resolve.

`world_is_style_free()` checks the separation rather than trusting it: the rule
is easy to honour while you are thinking about it, and the next module to add
"just one field" to the world will not be.

## §73 — future proprietary models

The directive is explicit: **do not train first**. Build, integrate, measure,
identify gaps, collect consented data, validate, *then* consider training.

This programme is the "build and measure" step, and what it measured says
something useful about the gaps: the scarcity is not models, it is **licences
that can be read** and **data that can be consented to**. Seven of nine
candidates have an unknown commercial status; the Wolof alias table carries
`wo_reviewed: false`; no Senegalese curriculum was ever integrated because none
was available.

So the honest reading is that a proprietary model is not the next problem. A
corpus with provenance is. The language knowledge base built in C14 is the shape
that corpus would take — observation, corroboration, a named human, an external
authority — and it deliberately grows slowly, because the alternative is
encoding the errors of the loudest users into a language's record.

Any future training remains a separate, explicit, consent-aware,
licence-reviewed, dataset-controlled, reproducible, isolated and auditable
pipeline, with its own ADR. It is not a side effect of this loop, and
`training_status()` is there so that claim can be checked rather than believed.
