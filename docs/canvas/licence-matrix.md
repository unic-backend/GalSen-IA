# K02 — licence and dependency matrix: the gate

Creative Canvas directive, §18. Read on 2026-08-19 from each repository's
`LICENSE` file and manifest, and from the **npm registry's own metadata** for
every declared dependency. Every figure below was fetched, not recalled.

This is a **gate, not a summary**. Its purpose is to state, before any design
decision is taken, which of the five candidates GalSen IA has the right to use
and which it does not.

The MoneyPrinterTurbo programme's equivalent — a different repository, a Python
dependency tree — is `docs/providers/licence-matrix.md`. This document does not
restate it.

---

## The verdict

| Repository | Licence, as read | Evidence | May GalSen IA copy, adapt or vendor it? |
|---|---|---|---|
| `opencanvasai/OpenCanvas` | **MIT** | `LICENSE` + `package.json` agree | **Yes** — but there is nothing to take (Electron/TypeScript, no Python) |
| `abdrsan/Higgsfield-Open` | **MIT** (file) vs **`null`** (manifest) | the two disagree | **Yes on the file's authority** — re-read required before any adoption |
| `higgsfield-ai/skills` | **MIT**, © 2026 Higgsfield AI | `LICENSE`, `VERSION` = 0.12.0 | **The Markdown only.** Not the models, not the service, not the outputs |
| `clearsolid/open-higgsfield-ai` | **none** | 404 on 4 filenames × 2 branches; `package.json` has no `license` field | **No — all rights reserved** |
| `troy1471-sys/open-higgsfield` | **none** | same | **No — all rights reserved** |

**Two of five are disqualified before design begins.** That is the gate doing
its job: it closes on a right that does not exist, not on a technical opinion.

### Why "no licence" is a refusal and not a gap to fill later

A public repository is not a public-domain repository. Absent an explicit grant,
copyright reserves every right to the author: no copying, no adaptation, no
vendoring, no derivative work — including work derived from *reading* the code
and reproducing its structure. The two rejected repositories additionally
declare `"private": true` in their manifests, which is the opposite of an
invitation.

This is the same rule the platform already applies to model weights
(`corpus/creative/providers.yaml`): eight of ten candidates carry
`weight_license: UNKNOWN`, and none of them is treated as permitted in the
meantime.

### The discrepancy inside `abdrsan/Higgsfield-Open`

`LICENSE` reads *MIT License*. `package.json` declares `"license": null`. The
file is the stronger instrument — a manifest field is metadata, a `LICENSE` file
is the grant — so the repository is recorded as MIT. But a project that
contradicts itself about its own licence is one whose licence must be re-read at
the exact commit being used, and **K01 classified it REFERENCE ONLY anyway**, so
the question never becomes load-bearing here.

### What MIT does *not* grant in `higgsfield-ai/skills`

Four distinct things are involved, and only the first is licensed:

| Thing | Covered by the MIT grant? |
|---|---|
| The 9 `SKILL.md` files and the `setup` script | **yes** |
| The `higgsfield.ai` hosted API they call | no — a commercial service, under its own terms |
| The models behind it (Veo, Kling, Flux, GPT Image, Seedance, …) | no — third-party weights, each with its own licence |
| Rights over the generated output | **`UNKNOWN`** — never read |

Recording this row as "MIT" without those three lines is precisely the confusion
§30 of the previous directive exists to prevent, and the same confusion the
MoneyPrinterTurbo audit found (permissive repository, copyleft capability).

---

## The dependency matrix

**120 distinct direct dependencies** across the two adoptable manifests
(OpenCanvas: 71 runtime + 45 dev; Higgsfield-Open: 3 runtime + 4 dev). Each
package's `license` field was fetched from `registry.npmjs.org/<pkg>/latest`.
**Zero fetch failures** — all 120 resolved.

| Licence | Count | Class |
|---|---|---|
| MIT | **106** | permissive |
| Apache-2.0 | **9** | permissive, patent grant |
| OFL-1.1 | 2 | fonts — permissive, reserved-name clause |
| ISC | 1 | permissive |
| BSD-2-Clause | 1 | permissive |
| `(MIT OR GPL-3.0-or-later)` | **1** | dual — permissive *if elected* |

The 14 non-MIT entries, named:

```
(MIT OR GPL-3.0-or-later)  jszip
Apache-2.0                 @ai-sdk/google, @google/genai, ai, puppeteer,
                           typescript, @playwright/test, @eslint/compat,
                           class-variance-authority, electron-squirrel-startup
BSD-2-Clause               dotenv
ISC                        lucide-react
OFL-1.1                    @fontsource-variable/geist, …-geist-mono
```

**No copyleft obligation is triggered.** `jszip` is the only GPL-adjacent entry
and it is dual-licensed, so MIT may be elected. Nothing in either tree is
GPL-only, LGPL or AGPL.

### Three honest limits on that finding

1. **Direct dependencies only.** 120 manifest entries were read; their
   transitive trees were not. Real npm trees run to thousands of packages, and
   a copyleft entry three levels down would not appear above. Transitive licence
   status is **`UNKNOWN`**, and it stays `UNKNOWN` rather than being reported as
   clean.
2. **Registry metadata, not `LICENSE` files.** The `license` field is what the
   publisher declared; it is not the text that ships. It is the same class of
   evidence the corpus records as `DECLARED` rather than `AUTHORITATIVE`.
3. **`null` was read as `NONE`, and none occurred** — every one of the 120
   declared something.

### The finding that matters despite all of the above

**None of these 120 packages can enter GalSen IA anyway.** They are npm
packages; this platform is Python and FastAPI (ADR-001). K01 classified every
candidate REFERENCE ONLY or REJECT, so **the number of dependencies this
programme adds is zero**, and the matrix's real value is the record that the
question was asked before the design, not after it.

### One dependency worth naming out loud

`puppeteer ^24.37.2` — a full headless Chromium — is declared a **runtime**
dependency by `abdrsan/Higgsfield-Open` and by `troy1471-sys/open-higgsfield`
(not by `clearsolid`, whose runtime tree is Next.js/React/axios instead).

A browser-automation engine inside a client-side creative studio is not
self-explanatory. It is Apache-2.0, so it raises no licence question; it raises
a **weight and surface** question, which is §18's other subject. It is recorded
here because "the licences are fine" and "the dependency is warranted" are two
different findings, and only the first was established.

---

## GalSen IA's own licence position, unchanged by this programme

For completeness, the platform's existing record — read from
`corpus/creative/providers.yaml`, not restated from memory:

| | Count |
|---|---|
| Candidates recorded | 10 |
| Repository licence known | 9 (one `UNKNOWN`) |
| Weight licence known | **1** (`ltx-video`, OpenRail-M) + 1 `NOT_APPLICABLE` |
| Commercially cleared | **0** |
| `commercial_status: UNKNOWN` | 8 |

One repository licence is copyleft (`seed-vc`, GPL-3.0) and one is a
vendor-specific community licence with an explicit commercial restriction
(`hunyuanvideo`, `RESTRICTED`). Eight weight licences are `UNKNOWN` because
`huggingface.co` has no route from this container — measured, not assumed.

**This programme changes none of it**, which is the correct outcome for an audit
phase: a matrix that grew a row would mean something was adopted.

---

## What the gate lets through

- **Ideas** from all five, including the two rejected ones — an idea is not a
  copyrightable expression, and "two repositories ship the same app" is a fact
  about the world.
- **Code** from none of them.
- **Dependencies** from none of them.

K03 may therefore begin: the architecture it designs owes nothing to any of
these repositories except the four ideas and three warnings K01 named.
