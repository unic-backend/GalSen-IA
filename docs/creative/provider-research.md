# Provider research, comparison and licence matrix (C01–C02)

Directive V4 §37–§40 and §67. *Researched on 2026-08-16 at execution time, not
recalled.* The machine-readable record is `corpus/creative/providers.yaml`; it
is validated at load time by `src/creative/research.py`, and the rules it
enforces are pinned by `tests/creative/test_provider_research.py`.

**This document selects nothing.** Selection is C04's decision and belongs in an
ADR. What follows is evidence, and — just as important — the record of what
could not be evidenced.

---

## 1. What could actually be researched, and what could not

§67 says to prefer official repositories, documentation, model cards, licences
and release notes, and not to rely on secondary articles. Measured from this
container:

| Source | Result | Consequence |
|---|---|---|
| `raw.githubusercontent.com` | **200** | Official `LICENSE` and `README` files **were read directly**. Eight of nine repository licences are authoritative. |
| `huggingface.co` | **000, no route** | **Model cards and weight licences could not be read at all.** Eight of nine weight licences are `UNKNOWN`. |
| `github.com` (HTML) | 403 | Release notes, tags and issues unreachable |
| `api.github.com` | scoped | Version, last commit and archived status unreachable for third parties |
| `pypi.org` | 200 | Package metadata reachable |

The environment therefore enforces the exact distinction §40 asks for. A
repository licence is verifiable here; a weight licence usually is not. Every
place this document says `UNKNOWN`, it means *not read from an authoritative
source* — not "probably fine".

---

## 2. Comparison (§39)

Nine candidates. `NOT_MEASURED` appears wherever a number would have to come
from a README rather than from a run, because no model can execute on this
machine (no GPU, no `torch`, no `transformers`).

| Task | Candidate | Repo licence | Weight licence | Commercial | VRAM floor | Audio | Reference | Quality / latency |
|---|---|---|---|---|---|---|---|---|
| T2V, I2V, S2V, animate | **Wan 2.2** | Apache-2.0 ✔ | `UNKNOWN` | `UNKNOWN` | 24 GB (5B) · 80 GB (A14B) ✔ | **yes — S2V-14B is audio-driven** | **yes — Animate-14B** | `NOT_MEASURED` |
| T2V, I2V, editing | Wan 2.7 | `UNKNOWN` | `UNKNOWN` (secondary: not on HF, not Apache) | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_MEASURED` |
| T2V, I2V | HunyuanVideo | **Tencent Community Licence** ✔ | `UNKNOWN` | **RESTRICTED** ✔ | 45–80 GB ✔ | `UNKNOWN` | `UNKNOWN` | `NOT_MEASURED` |
| T2V, I2V | LTX-Video | Apache-2.0 ✔ | **OpenRail-M** ✔ | **PARTIAL** | 8 GB ✔ | `UNKNOWN` | `UNKNOWN` | `NOT_MEASURED` |
| Multimodal understanding + speech | Qwen2.5-Omni | Apache-2.0 ✔ | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | **yes — Thinker/Talker, streaming speech** | n/a | `NOT_MEASURED` |
| Speaker diarization | pyannote.audio | MIT ✔ | **gated** ✔ | `UNKNOWN` | `UNKNOWN` | yes | n/a | `NOT_MEASURED` |
| Voice conversion | Seed-VC | **GPL-3.0** ✔ | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | yes — zero-shot from 1–30 s | yes (voice) | `NOT_MEASURED` |
| Lip sync | LatentSync | Apache-2.0 ✔ | `UNKNOWN` | `UNKNOWN` | 20–55 GB (**training**) ✔ | yes | needs face landmarks | `NOT_MEASURED` |
| Portrait animation, lip sync | Hallo2 | MIT ✔ | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | yes | single portrait | `NOT_MEASURED` |

✔ = read from an authoritative source.

### Four findings that change the architecture

**1. Audio-driven video generation already exists in the ecosystem.**
Wan 2.2 ships **S2V-14B**, an audio-driven speech-to-video model, and
**Animate-14B**, described as character animation and replacement with movement
and expression replication. Both bear directly on §8 (real-person reference) and
§22 (original audio preserved, lip-synced). This is why §43 is right to keep two
pipelines: *video + separate lip sync* and *native audio-video* are genuinely
different architectures, and the router must be able to choose — not the code.

**2. "Newer" is not "more usable".** Secondary sources describe Wan 2.7 as
**not** published on Hugging Face and **not** Apache-2.0, with weights surfacing
elsewhere under unclear terms. Unverified, and recorded as `UNKNOWN` — but
enough to refuse the reflex of routing to the newest version. §36's rule against
hard-coding `video → model X` covers versions too.

**3. Two licences in one project is the normal case, not the exception.**
LTX-Video: repository Apache-2.0, **weights OpenRail-M**, stated in its own
README. That is the whole of §40 in a single project. And HunyuanVideo's licence
— read from the text, not from a summary — **does not apply in the European
Union** and carries a 100-million-MAU threshold. Neither restriction is visible
from the word "open".

**4. One candidate is copyleft.** Seed-VC is **GPL-3.0**. Calling it as an
isolated process is not the same act as vendoring it, and the difference has
legal consequences for everything that links against it. That belongs in an ADR,
not in a dependency list. §23 already makes voice conversion *optional*, and §22
makes preserving the original recording the default — so the cheapest resolution
may be not to need it.

### Alternatives searched (§37)

Searching for newer options returned LTX-2.x and Wan 2.7 as the current
generation, both with **less permissive terms than the versions they replace**
on the available (secondary) evidence. No newer permissively-licensed video
model was identified that supersedes Wan 2.2 or LTX-Video on licence grounds.

For the languages §24 names, the relevant find is a **dataset, not a model**:
WAXAL, reported as covering 27 Sub-Saharan African languages with roughly
1 846 h transcribed for ASR and 565 h for TTS. Recorded as a lead with its
licence `UNKNOWN` — §41 makes dataset licensing its own question, and it was not
read.

---

## 3. Licence matrix (§40)

Computed by `license_matrix()`, so it cannot drift from the record:

| | Verified authoritatively | `UNKNOWN` |
|---|---|---|
| Repository licence | **8 / 9** | 1 (Wan 2.7 — no reachable repository) |
| Weight licence | 1 / 9 | **8** |
| Dataset licence | 0 / 9 | **9** |
| Commercial status | 2 (1 `RESTRICTED`, 1 `PARTIAL`) | **7** |

**Zero candidates are cleared for commercial use.** Not one. The loader refuses
to record `ALLOWED` unless *both* the repository and weight licences were read
from authoritative sources, and that has not happened for any candidate. This is
not pessimism; it is the state of the evidence, and shipping against anything
softer would be the fabrication this repository exists to refuse.

---

## 4. What would change these answers

| Blocked question | What settles it |
|---|---|
| 8 unknown weight licences | Network access to `huggingface.co`, or the licence texts mirrored somewhere reachable |
| 9 unknown dataset licences | Publication by the projects; most do not publish training-data terms at all |
| pyannote pipelines | Accepting the gated user conditions with an account and a token — a human act, not an automated one |
| LTX-2 / 2.x terms | The community licence text from an authoritative source |
| Every quality and latency figure | A GPU host, and a benchmark that actually runs |

Until then: `UNKNOWN` stays `UNKNOWN` (§22), and no provider is selected.

**Next**: C03 — ADRs and schemas (§68, §69), starting with ADR-001, which must
decide whether the three provider families already in this repository are
unified or extended **before** any provider code is written.
