# D08 — Licence audit (Phase 6), the gate

**Read**: 2026-08-20, from official sources. Phase 6's rule: *"If license
compatibility cannot be verified: MARK UNKNOWN. Do not integrate."*

---

## 1. The repository licence

**MIT, declared and filed.** `LICENSE` reads *"MIT License / Copyright (c) 2026
DeepSeek"*; `package.json` declares `"license": "MIT"` at `0.1.0-rc.8`
(D00.1, VERIFIED FROM OFFICIAL SOURCE).

Obligations: the copyright notice and permission notice in copies and
substantial portions. No copyleft, no commercial restriction, no
source-disclosure requirement.

## 2. Third-party dependencies — audited by the project itself

**This is the first subject in five programmes to publish its own dependency
licence audit.** `THIRD_PARTY_NOTICES.md`, read 2026-08-20:

| Licence | Packages | Note |
|---|---|---|
| MIT | ~100 | dominant |
| Apache-2.0 | ~15 | |
| BSD-3-Clause | 3 | `diff`, `istanbul-lib-report`, `smol-toml` |
| ISC | 2 | `yaml`, `knip` |
| BSD-2-Clause | 1 | `@yarnpkg/cli-dist` |
| **`SEE LICENSE IN`** | **2** | **`@anthropic-ai/claude-agent-sdk`**, platform packages |
| **LGPL-3.0-only** | 1 | `eslint-plugin-sonarjs` |
| **MPL-2.0** | 1 | `lightningcss` |

**~130 packages across vendored, runtime, development, Python and build-time.**

**The two copyleft entries carry the project's own scoping statement**, quoted:
they *"run only as development tooling; their code is not linked into or
distributed with any DeepSeek Harness artifact."*

`INFERENCE`: if that statement is accurate, **LGPL-3.0 and MPL-2.0 do not reach
a distributed artefact** and impose nothing on a downstream user. The statement
is the project's, not a verification — but it is a **specific, checkable** claim
rather than silence, which is more than the previous four subjects offered.

Two further disciplines worth recording, because they are unusual:

- **Patches are documented**: *"pnpm applies local patches"* to
  `node-pty@1.2.0-beta.15`, with *"each patch file the complete record of the
  modification."*
- **Vendored code keeps its grant**: vendored source *"preserves its upstream
  LICENSE file."*

## 3. The one entry that is not settled

**`@anthropic-ai/claude-agent-sdk` is listed as `SEE LICENSE IN`.**

That is not an SPDX open-source identifier. It is a pointer to a licence file
whose terms this audit **has not read**. It also connects to a fact from D00.1:
the `rc.8` release notes announce *"Claude Code and Codex as installable
subagents."*

**`UNKNOWN`**, and Phase 6 says exactly what to do with an unverified licence:
mark it, and do not integrate on the strength of the others.

`INFERENCE`, and this is the practically important part: **whether it matters
depends entirely on the integration shape.** If DSH were used as a coding
adapter configured against GalSen IA's own endpoint (D06's viable
configuration), the Claude subagent path would not be exercised. If it were
installed with its full default plugin set, it would be. **The licence question
is therefore a function of D10's decision, not a precondition of it.**

## 4. The finding this phase owes about GalSen IA itself

**GalSen IA has no `LICENSE` file.**

```bash
ls LICENSE*   # → no such file
```

Measured 2026-08-20, VERIFIED FROM REPOSITORY.

This audit has spent five programmes recording that *a manifest field is a
declaration and a `LICENSE` file is a grant* — and applying it to Call.md
(declared MIT, no file), OpenClaw (both), and now DSH (both). **This repository
has neither.** Absence of a licence file means all rights reserved by default.

That is not a blocker for *this* programme — GalSen IA integrating MIT code is
unaffected by GalSen IA's own licence — but it is a real omission found by
taking Phase 6 seriously, and it belongs in `pending-work` rather than in this
document's conclusions.

## 5. Phase 6's five questions, answered

| Question | Answer |
|---|---|
| Legally compatible with integration? | **YES for the core and ~128 of ~130 dependencies** — MIT, Apache-2.0, BSD, ISC are all compatible with anything this repository does |
| Attribution requirements? | **Yes** — MIT and Apache-2.0 notice clauses; the project's own `THIRD_PARTY_NOTICES.md` is the template for satisfying them |
| Redistribution requirements? | **Notice retention only**; no copyleft in the distributed set *per the project's statement* |
| Notice requirements? | Preserve `LICENSE` and the third-party notices; vendored code keeps its upstream file |
| Plugin licensing implications? | **The open question.** Everything is a plugin, so every added plugin is a separate licence. `@anthropic-ai/claude-agent-sdk` is `SEE LICENSE IN` and **unread** |

## 6. Does the gate close?

**No — and for a better reason than the previous programme's.**

O05 (OpenClaw) could not close because the dependency tree **could not be read
at all**. Here it can be read, has been read, and is ~98 % permissive with the
two copyleft entries scoped to development by an explicit statement.

**What is unsettled is narrow and named**: one dependency whose licence is a
pointer to a file, and a plugin model where each future plugin is its own
licence question.

**Recorded for D09, gate on licences**: `YES` for the core and the audited
dependency set; **`UNKNOWN` for `@anthropic-ai/claude-agent-sdk`**, resolvable
by reading one file; and **structurally per-plugin** for anything installed
later — which is an argument for the narrowest possible integration, the same
conclusion O05 reached by a different route.

## 7. What this phase refused to do

- **Call the set "MIT"** — it is ~100 MIT out of ~130, with seven other
  identifiers and two unread.
- **Dismiss the copyleft entries because the project says they are dev-only.**
  The statement is quoted and attributed; it is not adopted as verified.
- **Treat `SEE LICENSE IN` as probably fine.** It is `UNKNOWN`, and Phase 6 is
  explicit about what that means.
- **Fix GalSen IA's missing `LICENSE`.** Found, recorded, out of scope.
