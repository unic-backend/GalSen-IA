# ADR-036 — GalSen IA is licensed under Apache-2.0

**Status**: accepted
**Date**: 2026-08-20
**Decided by**: the project owner, who delegated the choice after the options
were laid out
**Files**: `LICENSE`, `NOTICE`

## Context

**This repository had no licence file at all.** `ls LICENSE*` returned nothing
on 2026-08-20, and no `[project]` table in `pyproject.toml` declared one either.

That was found twice, independently, by two external audits — ADR-034 (OpenClaw)
and ADR-035 (DeepSeek Harness) — each of which had just spent its licence phase
refusing to accept another project's manifest as proof, on the grounds that
**a manifest is a declaration and a file is a grant**. Five programmes applied
that standard outward. GalSen IA met neither half of it itself.

Without a licence file, default copyright applies: **nobody may legally reuse,
modify or redistribute this work**, whatever the repository's visibility
suggests. For a platform whose stated purpose is to be adopted in Senegal, then
across Africa, then more widely, that is the opposite of the intent.

## What was measured before choosing

The **19 runtime dependencies** declared in `requirements.txt` were read on
2026-08-20 — twelve from the installed distributions in this environment, seven
from the packages' own published metadata, since they are not installed here:

| Licence | Count |
|---|---|
| MIT (incl. MIT-CMU) | 8 |
| BSD-3-Clause | 4 |
| Apache-2.0 (incl. `Apache-2.0 OR BSD-3-Clause`) | 6 |
| Mixed permissive (`BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`) | 1 |

**Zero copyleft.** Nothing in the runtime tree forces a stronger licence, and
nothing in it conflicts with a permissive one.

Optional, audio, embeddings, training and development requirements were **not**
read for this decision and are recorded as such. `edge-tts` is LGPL-3.0 and was
already handled by ADR-030 — **invoked by API, never imported** — which keeps it
outside this question.

## Decision

**Apache License, Version 2.0.** The canonical text was fetched from
`https://www.apache.org/licenses/LICENSE-2.0.txt` rather than reproduced from
memory, and the appendix's copyright line filled in. A `NOTICE` file accompanies
it, as §4 of the licence provides for.

### Why Apache-2.0 rather than MIT

**The patent grant is the reason.** MIT is silent on patents: a contributor may
grant copyright permission and still hold a patent reading on what they
contributed. An AI platform is precisely where that exposure lives — routing,
retrieval, orchestration and agent methods are all patented territory.
Apache-2.0 §3 grants a patent licence explicitly and terminates it for anyone
who initiates patent litigation over the work.

Two secondary reasons, both matching how this repository already works:

- **§5 defines what a contribution is** and under what terms it arrives. A
  project expecting outside contributors should not leave that to convention.
- **§4 gives attribution a defined home** in `NOTICE`. This repository refuses
  to accept a claim without its source everywhere else; a licence that formalises
  attribution is the same discipline in legal form.

### Why not AGPL-3.0

It would protect against a cloud provider re-hosting the platform without
returning anything. But GalSen IA **ships a Docker image and a public API meant
to be deployed by other people** — ministries, universities, NGOs, companies.
AGPL puts obligations on exactly the deployment the vision is trying to
encourage, and institutional legal departments that approve Apache-2.0 as a
matter of course will not approve AGPL as a matter of course.

**Copyleft would defend this project against a risk it does not yet face, at the
cost of the adoption it exists for.**

### Why not a dual licence or a non-commercial clause

A non-commercial restriction is not open source, disqualifies the work from most
public procurement and from Linux distributions, and would sit badly beside a
dependency tree that granted this project permissive terms unconditionally.
Dual licensing needs a legal entity and an owner willing to administer it;
neither exists here today. **Neither is refused on principle — both are refused
as unsupported by anything this repository currently has.**

## Consequences

**Positive.** The work becomes legally reusable, which it was not. The standard
this repository applies to every external project it audits now applies to
itself. Contributions arrive under defined terms.

**Negative, stated rather than softened.** Apache-2.0 is **irrevocable for the
versions published under it**. Anyone may build a commercial product on this
work and return nothing. That is the accepted cost of the adoption goal, and it
cannot be undone retroactively by relicensing later.

**Neutral.** Relicensing *future* versions stays possible while the copyright is
held in one place. It stops being simple the moment outside contributions
accumulate.

## What this ADR does not decide

- **Who the copyright holder is, in law.** `LICENSE` and `NOTICE` name
  **"GalSen IA"**. If the owner wants a personal legal name or a registered
  entity there instead, both files are one edit — and that edit is theirs, not
  the platform's.
- **The licence of the optional dependency sets.** Audio, embeddings, training
  and development requirements were not read here.
- **Anything about model weights, corpora or acquired data.** Those carry their
  own terms — `corpus/sources/senegal.yaml` and the acquisition manifests hold
  them, and a code licence does not reach them.
