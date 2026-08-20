# E06.1 — Licence matrix, part 1 of 2 (§8)

**Read**: 2026-08-20. Every row below comes from the project's **own `LICENSE`
file**, fetched from its official repository, cross-checked against its **own
published package metadata**. Nothing is recalled from memory.

`api.github.com` answers **403** through this environment's proxy, so licence
*history* — when a licence changed, whether a relicensing is pending — is
**`UNKNOWN` for all twelve** and is not guessed.

§8's rule, quoted: *"Do not state 'open source = unrestricted'."*

---

## Part 1 — the six inference and routing candidates

| | Transformers | SGLang | llama.cpp | vLLM | LiteLLM | LangGraph |
|---|---|---|---|---|---|---|
| **Licence name** | Apache-2.0 | Apache-2.0 | **MIT** | Apache-2.0 | **MIT + carve-out** | **MIT** |
| **Version read** | PyPI `5.15.1` | PyPI `0.5.17` | bindings `0.3.35` | PyPI `0.27.1` | PyPI `1.97.0` *(installed here: 1.81.10)* | file read on `main` |
| **File verified** | yes | yes | yes | yes | **yes — and it is not plain MIT** | yes |
| **Metadata agrees** | `Apache 2.0 License` | `Apache Software License` | `MIT` | `Apache-2.0` | **`MIT` — disagrees with the file** | — |
| **Commercial use** | permitted | permitted | permitted | permitted | permitted *outside* `enterprise/` | permitted |
| **Redistribution** | permitted, notice required | same | permitted, notice required | same | permitted, notice required | permitted, notice required |
| **Attribution** | §4 NOTICE | §4 NOTICE | copyright + permission notice | §4 NOTICE | copyright + permission notice | copyright + permission notice |
| **Modification** | permitted, must be marked (§4b) | same | permitted | same | permitted | permitted |
| **Patent grant** | **yes (§3)** | **yes (§3)** | **no** | **yes (§3)** | **no** | **no** |
| **Model-weight restrictions** | **n/a to the library** — weights carry their own terms | n/a | n/a | n/a | n/a | n/a |
| **Notable extra condition** | copyright header *"All rights reserved"* above the Apache text — a copyright line, not a restriction | — | — | — | **`enterprise/` excluded, and `enterprise/LICENSE` returns 404** | — |
| **Compatibility with ADR-036 (Apache-2.0)** | identical | identical | **compatible** (MIT → Apache-2.0) | identical | compatible **for the MIT portion**; the excluded portion is **`UNKNOWN`** | compatible |

---

## The one row that is not clean, stated precisely

**LiteLLM.** Its `LICENSE` opens:

> *"Portions of this software are licensed as follows: All content that resides
> under the `enterprise/` directory of this repository, **if that directory
> exists**, is licensed under the license defined in `enterprise/LICENSE`.
> Content outside of the above mentioned directories or restrictions above is
> available under the MIT license."*

`https://raw.githubusercontent.com/BerriAI/litellm/main/enterprise/LICENSE` →
**`404: Not Found`** (fetched 2026-08-20).

Three readings are possible and **this audit does not choose between them**:

1. The directory no longer exists, and the clause is self-cancelling — the file
   says *"if that directory exists"*.
2. The directory exists on another branch or in another distribution, with terms
   nobody here has read.
3. The clause is stale text.

**PyPI declares the package simply `MIT`.** That is the project's own metadata
disagreeing with the project's own file — in the *permissive* direction.
§8's rule is that a manifest is a declaration and a file is a grant, so the
**file wins**, and the file points at something unreadable.

**Recorded as `UNKNOWN`, with the exact failure**, per the directive. It is one
of the two reasons LiteLLM is `DEFER` rather than anything else — the other
being that it is `OUTSIDE` architecturally (E04.1).

---

## What part 1 establishes

- **Five of six are clean permissive grants**, filed, and compatible with
  ADR-036's Apache-2.0.
- **Three carry a patent grant** (the three Apache-2.0 projects); three do not
  (the MIT ones). That is not a defect — it is the difference ADR-036 chose
  Apache-2.0 *for*, applied to incoming code rather than outgoing.
- **One is not what its manifest says.**

**Nothing here forbids anything.** No licence in part 1 blocks an integration
that the architecture wanted — and the architecture wanted none of them, which
is the finding of E05 rather than of this chapter.

---

## What E06.1 refuses to conclude

- **That LiteLLM's carve-out is a trap.** A 404 is an `UNKNOWN`, recorded with
  its URL and its date, not an accusation.
- **That an Apache-2.0 dependency makes this platform safer.** A patent grant
  from a dependency protects use *of that dependency*, nothing more.
- **Anything about model weights.** Every row's weight restrictions are `n/a` at
  the library level, and the models these tools load carry **their own terms**,
  which are outside this matrix and were not read.
