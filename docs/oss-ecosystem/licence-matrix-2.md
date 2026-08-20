# E06.2 — Licence matrix, part 2 of 2 (§8)

**Read**: 2026-08-20, each row from the project's own `LICENSE` file on its
official repository, cross-checked against its own published package metadata.
`api.github.com` → **403**, so licence *history* is `UNKNOWN` for all twelve.

---

## Part 2 — knowledge, tooling, training, UI

| | LlamaIndex | Qdrant | OpenHands | Unsloth | whisper.cpp | **Open WebUI** |
|---|---|---|---|---|---|---|
| **Licence** | MIT | Apache-2.0 | MIT | Apache-2.0 | MIT | **BSD-3 + clause 4** |
| **Copyright line read** | *"Copyright (c) Jerry Liu"* | Apache text | *"Copyright © 2025 OpenHands contributors"* | Apache text | *"Copyright (c) 2023-2026 The ggml authors"* | **"All rights reserved"** |
| **Metadata agrees** | yes | yes | yes | yes | yes | **yes — `Other/Proprietary License`** |
| **Commercial use** | permitted | permitted | permitted | permitted | permitted | **conditional** |
| **Redistribution** | notice required | notice required | notice required | notice required | notice required | notice required |
| **Attribution** | copyright notice | §4 NOTICE | copyright notice | §4 NOTICE | copyright notice | copyright notice **+ branding retained** |
| **Modification** | permitted | permitted, must be marked | permitted | permitted, must be marked | permitted | permitted **except the branding** |
| **Patent grant** | no | **yes (§3)** | no | **yes (§3)** | no | no |
| **Weight restrictions** | n/a | n/a | n/a | **n/a to the library — the base models it tunes carry their own terms, unread here** | n/a | n/a |
| **Notable condition** | — | — | — | — | same authors as llama.cpp | **no rebranding above 50 end users / 30 days** |
| **Compatible with ADR-036** | yes | yes | yes | yes | yes | **no, for this platform's purpose** |

---

## The one row that decides itself

**Open WebUI**, clause 4, quoted in E03.4 and repeated because it is the only
term in twelve projects that actually forbids something this platform wants:

> *"licensees are strictly prohibited from altering, removing, obscuring, or
> replacing any 'Open WebUI' branding … except … (i) deployments … where the
> total number of end users … does not exceed **fifty (50)** within any rolling
> thirty (30) day period; (ii) … prior written permission …; or (iii) … a duly
> executed enterprise license."*

GalSen IA is meant to be deployed by ministries, universities and NGOs **under
its own name**. Ship the branding, stay under 50 users, or buy a licence — the
first two contradict the vision directly.

**PyPI classifies it `Other/Proprietary License`.** The manifest and the file
agree. This is the opposite of LiteLLM, where they did not.

---

## The twelve, consolidated

| Licence | Count | Projects |
|---|---:|---|
| **MIT** | 5 | llama.cpp, LiteLLM*, LangGraph, LlamaIndex, OpenHands, whisper.cpp — *six files, five clean* |
| **Apache-2.0** | 5 | Transformers, SGLang, vLLM, Qdrant, Unsloth |
| **MIT + unreadable carve-out** | 1 | **LiteLLM** — `enterprise/LICENSE` → **404** |
| **BSD-3 + branding clause** | 1 | **Open WebUI** |

**Ten of twelve are clean permissive grants**, all compatible with ADR-036's
Apache-2.0. **Five carry a patent grant** — the Apache-2.0 half. **Two are not
plain**, and both were found only by opening the file.

§8's rule, demonstrated rather than asserted: *"Do not state 'open source =
unrestricted'."* Two of twelve, one in each direction — a manifest more
permissive than its file (LiteLLM), and a manifest honestly declaring a
restriction (Open WebUI).

---

## What E06.2 refuses to conclude

- **That a licence blocked any integration.** None did. The architecture
  produced twelve non-integrations before the licences were consolidated
  (E05); the only row where the licence is decisive, Open WebUI, was already
  `REJECT` on duplication grounds.
- **Anything about model weights.** Every row is `n/a` at the library level.
  Unsloth's base models and Whisper's checkpoints carry **their own terms**,
  and none were read — Hugging Face answers **403** here.
- **That licence history is clean.** `api.github.com` is unreachable; whether
  any of these relicensed is `UNKNOWN`.
