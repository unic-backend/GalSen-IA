# L03 — licence and dependency matrix: the gate

Live Context Engine directive, **§38 and §39**. Measured 2026-08-19. npm
licences read from `registry.npmjs.org`; the repository licence read from the
project's own files.

§38's instruction is literal: *"Never assume open-source code means unrestricted
commercial use. If uncertain: UNKNOWN."*

---

## 1. The repository

| | |
|---|---|
| Project | `call-md` **1.0.4** |
| Declared licence | **MIT**, in `package.json` |
| `LICENSE` file | **none** — 404 on `LICENSE`, `.md`, `.txt`, `COPYING`, `license`, on `main` **and** `master` |
| Evidence level | **`DECLARED`, not `AUTHORITATIVE`** |

This is the mirror image of `abdrsan/Higgsfield-Open` in the canvas programme,
whose `LICENSE` said MIT while its manifest said `null`. There the file governed.
**Here there is no file** — only metadata.

A manifest field is a statement by the publisher; a `LICENSE` file is the
instrument that grants the rights. The honest record is therefore *MIT,
declared*, and any adoption of actual code would want the file to exist first.

**It does not become load-bearing**, because L01 concluded nothing is
importable: TypeScript and Electron against a Python platform, and a capture
capability that does not exist on Linux.

---

## 2. Dependencies — 54 packages, zero fetch failures

| Licence | Count |
|---|---|
| MIT | **48** |
| Apache-2.0 | **5** |
| ISC | **1** |

**No copyleft. No dual licence. No unlicensed package.** The cleanest dependency
tree of the five external projects audited across four programmes.

The six non-MIT entries, named:

```
Apache-2.0   class-variance-authority, drizzle-orm, openai, typescript, videodb
ISC          lucide-react
```

### Three limits on that finding

1. **Direct dependencies only.** 54 manifest entries were read; their transitive
   trees were not. Transitive licence status is **`UNKNOWN`** and is reported as
   such rather than as clean.
2. **Registry metadata, not `LICENSE` files** — `DECLARED` evidence.
3. **A JavaScript tree is irrelevant to a Python platform.** None of these 54
   packages can enter GalSen IA. The audit exists to answer §38, not because an
   adoption is pending.

---

## 3. The distinction that actually matters here

**`videodb` the SDK is Apache-2.0. VideoDB the service is a commercial hosted
product, and its terms have not been read.**

That separation is the whole point of §38, and it is the fourth time it has
appeared in this repository's audits:

| Programme | Permissive repository | Non-permissive or unread capability path |
|---|---|---|
| MoneyPrinterTurbo | MIT | `edge-tts` **LGPL-3.0**; Pexels/Pixabay output rights unread |
| Creative Canvas | `higgsfield-ai/skills` MIT | the Markdown only — not the hosted API, models, or output rights |
| Research Orchestration | Agent-Reach MIT | three orchestrated CLIs with **no licence at all** |
| **Live Context** | **`videodb` SDK Apache-2.0** | **the VideoDB service — terms `UNKNOWN`** |

**Licence, service terms and platform terms are three different things**, and
only the first is settled.

---

## 4. What the gate refuses, and why it is not a licence refusal

L00 established that two accepted ADRs already decide this, and **neither is
about licences**:

- **ADR-014** — the platform depends on no external model at runtime.
- **ADR-018** — the derogation is configuration, never a request parameter, and
  three categories are refused **whatever the configuration says**: user
  memories/files/knowledge content, **screen captures**, training-data export.

L01 measured that VideoDB carries capture, transcription **and** LLM inference
inside Call.md. So:

| §26's option | Verdict here |
|---|---|
| **A — VideoDB as an optional provider** | **Conflicts with ADR-014 and ADR-018** for live audio and, unconditionally, for screen captures |
| **B — existing GalSen IA providers** | **Compatible** — `multimodal/whisper_provider.py` is local by design, ADR-014's own reasoning |
| **C — hybrid** | Compatible **only** for the parts ADR-018 leaves eligible: stateless reasoning on text the platform itself produced |

**This is documented, not decided.** §0 and
`.claude/rules/spec-driven-governance.md` say the same thing: a conflict with an
existing architectural rule stops the work and is written down. Amending
ADR-014 or ADR-018 is the owner's decision, and this programme does not make it.

**Nothing about this is a licence problem.** Call.md's licensing is the
cleanest of the four; what stops adoption is architecture, platform support and
sovereignty — three reasons that have nothing to do with copyright.

---

## 5. Commercial restrictions

| Question | Answer |
|---|---|
| May the repository be used commercially? | **Probably yes** — MIT, but `DECLARED` only |
| Does any dependency impose copyleft? | **No** |
| May the VideoDB *SDK* be used commercially? | **Yes** — Apache-2.0 |
| May the VideoDB *service* be used commercially? | **`UNKNOWN`** — terms unread |
| What does a recorded conversation cost? | **`UNKNOWN`** — no pricing was read |
| Who may use the resulting transcript? | **`UNKNOWN`, and it is per-participant**, not per-licence |

The last row is the one that will matter in production and that no dependency
audit can settle. It belongs to L11's consent and retention work.

---

## What the gate lets through

- **Ideas** from Call.md — all of them. An idea is not a copyrightable
  expression.
- **Code** — none. Not for licence reasons: there is no Python to take.
- **Dependencies** — none. A JavaScript tree does not enter a Python platform.
- **VideoDB as a provider** — **not without an ADR amendment**, and the
  amendment is the owner's to make.

L04 designs `LiveContextEngine` inside those constraints.
