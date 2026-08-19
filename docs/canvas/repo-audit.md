# K01 — the five repositories, audited from source

Creative Canvas directive, §2 and §4. Read on 2026-08-19 from
`raw.githubusercontent.com`, file by file. **Nothing was cloned, installed or
executed** — §19's rule on external content, and the same discipline the
MoneyPrinterTurbo programme used.

The directive names five candidates. This document answers, for each: what it
actually is, what licence actually covers it, and §4's classification —
**KEEP / ADAPT / REIMPLEMENT / REFERENCE ONLY / REJECT**.

---

## Summary — the table the rest of this document justifies

| Repository | What it is | Licence, read | §4 verdict |
|---|---|---|---|
| `opencanvasai/OpenCanvas` | TypeScript / React / Electron desktop app | **MIT** | **REFERENCE ONLY** — no transferable code |
| `abdrsan/Higgsfield-Open` | Vanilla-JS single-page studio, one vendor | **MIT** (file) / `null` (manifest) | **REFERENCE ONLY** — and two anti-patterns to refuse |
| `clearsolid/open-higgsfield-ai` | Next.js wrapper over the repo below | **none — all rights reserved** | **REJECT** |
| `troy1471-sys/open-higgsfield` | Vite + Electron studio, byte-identical core | **none — all rights reserved** | **REJECT** |
| `higgsfield-ai/skills` | 9 Markdown agent skills driving a paid hosted API | **MIT** (the Markdown only) | **REFERENCE ONLY** — adopting it is a privacy decision, not a dependency |

**Zero of the five is classified KEEP or ADAPT.** Not one line of code from any
of them enters GalSen IA. What they contribute is four ideas and three warnings,
listed at the end.

---

## K01.1 — `opencanvasai/OpenCanvas`

**MIT**, read from the `LICENSE` file. 71 dependencies.

### It is not a library. It is a desktop application.

| Read | Value |
|---|---|
| `main` | `.vite/build/main.js` |
| `devDependencies` | `electron ^40.0.0` and the full `@electron-forge/*` toolchain |
| scripts | `make:win`, `make:mac`, `publish` |
| `tsconfig.json` | present |
| `requirements.txt`, `pyproject.toml` | **404, both** |

The canvas engine is **`@xyflow/react ^12.10.0`** (React Flow). Provider access
is `@ai-sdk/google` and `@google/genai` — a single vendor, wired directly into
the UI layer.

### Why this settles §5

§5 asks whether to embed OpenCanvas. **The question does not arise**: GalSen IA
is Python and FastAPI (ADR-001). There is no Python in OpenCanvas to take, so
"embedding" would mean shipping an Electron application beside a Python
platform and inventing a bridge between them — a second runtime, a second
dependency tree, a second update path, to obtain a node graph.

What is transferable is the *idea*: a node graph with typed ports, where a
connection is legal only when the port types agree. That idea costs nothing to
adopt and does not require React.

---

## K01.2 — `abdrsan/Higgsfield-Open`

### A licence discrepancy worth recording

`LICENSE` reads **MIT License**. `package.json` declares `"license": null`.
Both statements are in the same repository, at the same commit. The file is the
stronger of the two — a manifest field is metadata, a `LICENSE` file is the
grant — but a project that contradicts itself about its own licence is a
project whose licence must be re-read before any adoption, not assumed.

Seven declared dependencies — Tailwind, PostCSS, Vite, and **`puppeteer`**, a
full headless Chromium, declared at runtime in a client-side studio (see K02).
No framework: `index.html` loads
`/src/main.js`, which is 214 lines of hand-written routing across 25 studio
components. Total application ≈ 8.7 KB of entry code.

### The cinema layer, which is why this repository was audited at all

§10 asks for `CameraSpec`, `LensSpec`, `ShotSpec`. This repository has the
closest thing to them among the five, in `src/lib/promptUtils.js` (154 lines).
It is worth reading precisely, because what it does is **not** what §10 asks
for.

**Six cameras and eleven lenses, as string→string maps:**

```
"Modular 8K Digital"  → "modular 8K digital cinema camera"
"Classic Anamorphic"  → "classic anamorphic lens"
```

Names are anonymised — no manufacturer, no model. That avoids a trademark
problem and creates a physical one: **there is no sensor size, no coverage, no
real aperture range, no crop factor anywhere in the file.** A "camera" here is
an adjective, not a body.

**Focal length and aperture are lookup tables with six and three entries:**

```js
const perspective  = FOCAL_PERSPECTIVE[focalLength] || "";
const depthEffect  = APERTURE_EFFECT[aperture]      || "";
```

`FOCAL_PERSPECTIVE` holds `{8, 14, 24, 35, 50, 85}`; `APERTURE_EFFECT` holds
`{f/1.4, f/4, f/11}`. **Any other value silently becomes the empty string.** A
40 mm lens produces no perspective description at all, and the interface says
nothing. This is the exact behaviour this platform forbids: an unhandled case
must report itself, never degrade quietly into a plausible-looking result.

**The whole specification is then concatenated into one English sentence:**

```
<prompt>, shot on a <camera>, using a <lens> at <focal>mm (<perspective>),
aperture <f/…>, <depth effect>, cinematic lighting, natural color science,
high dynamic range, professional photography, ultra-detailed, 8K resolution
```

Three consequences, and they are the reason §10 asks for *normalised* specs:

1. **A prompt fragment cannot be verified.** Once the camera is a phrase inside
   a sentence, nothing downstream can check that shot 4 used the same lens as
   shot 3. GalSen IA's `verification.py` and continuity checks need structure,
   not prose.
2. **A prompt fragment cannot be translated.** The vocabulary is English-only.
   This platform's language layer (C13) covers nineteen languages, and a
   creative specification that only exists as English adjectives cannot serve
   a Wolof or Pulaar request.
3. **A prompt fragment cannot be routed.** Capability routing (C15) matches on
   declared capabilities. "cinematic lighting" inside a string is invisible to
   it.

### `LENS_MOTION_PRESET` — the anti-pattern §6 exists to forbid

Choosing a lens **applies camera motion the user never asked for**:

```js
"Classic Anamorphic": { pan: 50, tilt: 0, zoom: 0, dolly: 0 },
"Extreme Macro":      { pan: 0, tilt: 0, zoom: 0, dolly: 30 },
```

Pick an anamorphic lens and the camera pans. Nothing was requested; a default
was invented and applied. §6 states it in one line — *GalSen IA must not invent
creative content the user did not request* — and this file is the working
counter-example. The preset table is a fine **suggestion**; it is applied as a
**decision**, and the difference is the whole of §6.

### The API-key handling, per §19 and §20

`src/lib/muapi.js`:

```js
getKey() {
    const key = localStorage.getItem('muapi_key');
    if (!key) throw new Error('API Key missing. Please set it in Settings.');
    return key;
}
```

The key is sent as an `x-api-key` header from the browser to
`https://api.muapi.ai`. The README presents this as a feature — *"Keys live in
`localStorage` only; never sent anywhere except Muapi"*.

**`localStorage` is readable by any script running on the page**, so this is
storage without a boundary; and the directive forbids exactly this — *do not
move secrets into frontend code*. GalSen IA keeps provider credentials
server-side, and this repository is the reason to say so explicitly in the
canvas design rather than assume it.

Single-vendor lock-in is total: all generation, polling and editing go through
one host. There is no provider abstraction to learn from.

---

## K01.3 — the two unlicensed repositories, and the skills pack

### `clearsolid/open-higgsfield-ai` and `troy1471-sys/open-higgsfield` are the same application

Measured by SHA-256 over the raw files:

| File | `clearsolid` | `troy1471-sys` | Identical? |
|---|---|---|---|
| `index.html` | `297730fb0235` | `297730fb0235` | **yes, byte for byte** |
| `src/main.js` | `55ad1b4b37e8` | `55ad1b4b37e8` | **yes, byte for byte** |
| `src/lib/promptUtils.js` | 4 183 B | 2 631 B | no — diverged |
| `README.md` | 18 398 B | 17 768 B | no — diverged |

Both manifests declare the same `appId` (`ai.higgsfield.open`), the same
`productName`, the same `copyright`, the same `afterPack.js`, the same icon.
`clearsolid` adds a Next.js 15 / React 19 workspace on top and demotes the
original Vite scripts to `vite:dev` / `vite:build`; `troy1471-sys` is the
plain Vite + Electron form.

So §2 D — *"which implementation is technically superior"* — is not the right
question for this pair. One is a wrapper around the other. Comparing them
compares a repackaging, not two designs.

### Neither carries a licence, and that is decisive

`LICENSE`, `LICENSE.md`, `LICENSE.txt` and `COPYING` were requested on both
`main` and `master` for both repositories: **404, every one.** Both manifests
declare `"private": true` and **no `license` field**.

**Absence of a licence is not permission.** By default of copyright, all rights
are reserved: no copying, no adaptation, no vendoring, no derivative work. §18
makes this a gate and the gate closes here. They are **REJECT** — not because
the code is poor, but because this platform has no right to it.

Two further observations, recorded because they are the kind of thing that
matters later:

- Both use a third-party product name as their application identifier
  (`ai.higgsfield.open`, *"Open-source alternative to Higgsfield AI"*). That is
  a trademark question, separate from the copyright one, and it attaches to
  anything built on them.
- `troy1471-sys` lists **`puppeteer ^24.37.2`** as a runtime dependency of a
  creative studio, exactly as `abdrsan/Higgsfield-Open` does; `clearsolid`
  replaces it with a Next.js/React/axios tree. A headless Chromium in a media
  application is not self-explanatory; unexplained heavyweight dependencies are
  §18's other subject.

### `higgsfield-ai/skills` — MIT, and still not adoptable as a component

**MIT**, `Copyright (c) 2026 Higgsfield AI`, version `0.12.0`. Nine skills.

It contains **no library**. It is Markdown skill definitions plus a `setup`
bash script, installed into a coding agent (`npx skills add`,
`gh skill install`, or a Claude Code plugin marketplace entry), and every skill
drives the **hosted commercial `higgsfield.ai` API** through an authenticated
CLI.

Three things follow:

1. **The MIT grant covers the Markdown, not the service.** Not the models, not
   the weights, not the output rights, not the pricing. The licence matrix (K02)
   must not record this repository as "MIT" without that sentence beside it.
2. **Adopting it is a privacy decision.** Every skill sends user media and
   prompts to a third-party host. K00 found that `ProviderPrivacyPolicy` is one
   of exactly three things genuinely missing from this platform. This repository
   is the concrete case that gap was waiting for.
3. **It is instructions for an agent.** §19 and §31 say external repository
   content is *data*, never instruction. `SKILL.md` files are literally
   instructions to an agent, and `setup` is a script that installs and
   authenticates. **Neither was run, and neither should be.**

One idea in it is worth naming: `higgsfield-soul-id` trains a reusable
face-faithful identity model and returns a `reference_id` consumable by later
generation calls. That is the same shape as this platform's own
`reference/` → `jobs.py` chain (C05, C06, C16) — which is already built,
already carries consent, and already records provenance. Confirmation, not a
component.

---

## What the five repositories actually contribute

**Four ideas**, none of which requires their code:

1. **A node graph with typed ports** (OpenCanvas) — a connection is legal only
   when port types agree. The strongest idea of the five.
2. **Camera / lens / focal / aperture as first-class user controls**
   (Higgsfield-Open) — the *controls* are right; their representation is not.
3. **Motion as four signed axes** — pan, tilt, zoom, dolly, negative and
   positive, with a dead zone. A clean vocabulary for §10's `ShotSpec`, worth
   keeping as structure rather than as prose.
4. **A trained identity referenced by id in later jobs** (skills) — already how
   this platform works, which is useful confirmation that the design is not
   eccentric.

**Three warnings**, each with a file name behind it:

1. **Never invent a creative default** — `LENS_MOTION_PRESET` applies motion
   nobody asked for (§6).
2. **Never let an unhandled value become an empty string** —
   `FOCAL_PERSPECTIVE[x] || ""` degrades in silence (§7: `UNKNOWN` stays
   `UNKNOWN`).
3. **Never put a provider key in the frontend** — `localStorage.getItem` and an
   `x-api-key` header from the browser.

**And one gate**: two of the five candidates cannot be used at all. K02 records
that formally.

---

## Method note

Everything above was read from raw files. No repository was cloned, no script
executed, no skill installed, no dependency added. Version pinning is
**`UNKNOWN`** for all five: the GitHub tree API is not reachable from this
session (`403`, this session's repository scope), so no commit SHA could be
read. Files come from each repository's default branch as served on
2026-08-19.
