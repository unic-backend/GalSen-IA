# Creative Canvas & Cinema Orchestration — final report

**Programme**: GALSEN-IA — CREATIVE CANVAS & CINEMA ORCHESTRATION EXTENSION
(28 sections, 21 execution steps). **9 volets, 17 phases, all completed.**
Plan → `docs/canvas/phase-plan.md`. Decision → **ADR-031**.

**Date**: 2026-08-19. Every figure below was measured on the day.

---

## The sentence this programme exists to have established

**There was nothing to import.**

The directive frames five repositories as component sources, and the natural
instinct — the one that produces a Higgsfield clone — is to open the best-looking
one and start copying. Four audit volets established, before a line was written,
that four of the five are JavaScript or Electron applications against a Python
platform, that two of them carry **no licence at all**, and that nine of the
eleven subsystems §5–§17 asks for **already existed here**.

The expected risk was importing too much. **The measured risk was rebuilding what
exists**, and that inversion is what the audits bought.

---

## 1. Repository state

`main` at `9f80dbc` when this began; the work sits on
`claude/unit-tests-notification-search-file-4z0ok1`. **11 commits, 26 files
changed, 4 997 insertions, 177 deletions** — 22 new files, 4 modified.

## 2. Files created

**Code (7)** — `src/creative/intent.py`, `src/creative/cinema.py`, and
`src/creative/canvas/` (`__init__.py`, `ports.py`, `graph.py`, `privacy.py`,
`readiness.py`, `slice.py`).

**Tests (4)** — `test_intent.py`, `test_cinema.py`, `test_canvas_graph.py`,
`test_canvas_slice.py`.

**Documents (9)** — `docs/canvas/` (audit, repo-audit, licence-matrix,
obsolete-assumptions, architecture, provider-comparison, feasibility,
phase-plan, this report), **ADR-031**, and
`.claude/rules/post-integration-validation.md` — the owner's permanent rule,
established in §24.

## 3. Files modified

Four: `CLAUDE.md` and `docs/architecture/overview.md` (published counts, and the
new rule in the standards list), `docs/changelog/CHANGELOG.md`,
`docs/memory/phase-plan.md`.

**No existing source file was touched.** Not one line of `src/` outside the two
new modules and the new package.

## 4. Existing components reused

Nine, called rather than rewritten: `creative/reference/`, `world.py`,
`direction.py`, `verification.py`, `routing.py`, `jobs.py`, `style.py`,
`providers.py`, `security/trust.py`. Plus `mvp.py`'s outcome vocabulary and
`media/readiness.py`'s verdict shape.

## 5. New components

Five modules, and the count is the point: §11 alone lists fifteen registry-like
types, and the audits reduced the genuinely missing set to **one**
(`ProviderPrivacyPolicy`) plus the graph the programme is named after.

## 6. Providers evaluated

| Repository | Licence, read from source | §4 verdict |
|---|---|---|
| `opencanvasai/OpenCanvas` | MIT | **REFERENCE ONLY** — TypeScript/React/Electron, no Python |
| `abdrsan/Higgsfield-Open` | MIT (file) vs `null` (manifest) | **REFERENCE ONLY** |
| `higgsfield-ai/skills` | MIT — **the Markdown only** | **REFERENCE ONLY** |
| `clearsolid/open-higgsfield-ai` | **none** | **REJECT** |
| `troy1471-sys/open-higgsfield` | **none** | **REJECT** |

**0 KEEP, 0 ADAPT.** Not one line from any of them entered this platform.

## 7. Licence findings

Two candidates carry no `LICENSE`, `LICENSE.md`, `LICENSE.txt` or `COPYING` on
either `main` or `master`, and declare `"private": true`. **The directive states
MIT for both; that is false, measured.** Absence of a grant reserves every right.

`index.html` and `src/main.js` are **byte-identical (SHA-256)** between those
two: one repackages the other, so "which implementation is superior" has no
answer for the pair.

**120 direct dependencies** read from `registry.npmjs.org`, zero fetch failures:
106 MIT, 9 Apache-2.0, 2 OFL-1.1, 1 ISC, 1 BSD-2-Clause, 1 dual MIT/GPL
(`jszip`, so MIT may be elected). **No copyleft obligation triggered.**
Transitive licences remain **`UNKNOWN`** and are reported as such rather than as
clean.

## 8. Tests added

**130** — 32 intent, 37 cinema, 31 graph and ports, 30 privacy, readiness and
slice.

## 9–12. Total, passed, failed, skipped

```
python -m pytest -q
1 failed, 6363 passed, 11 skipped, 3 deselected, 2 warnings in 452.58s
```

6 233 → **6 363**. The single failure is the `v0.1.0` tag, which has never been
pushed; it predates all three programmes and fails identically on `main`.

## 13. Regression status

**PASS.** Five full-suite runs across the programme, one per pair of phases.

Two guards caught defects of mine, and both were right:

- `test_published_numbers.py` refused the ADR count until 31 → **32**;
- `test_lint.py` caught an **unused import** in `graph.py` — and it runs `ruff`
  over the **whole repository**, not just `src` and `tests`, which is worth
  knowing.

## 14. Performance measurements

Measured on this machine, 100 iterations except where noted:

| Operation | Time |
|---|---|
| Topological order (3 nodes) | **0.003 ms** |
| `render_for_provider` (text) | **0.005 ms** |
| `check_plan` | **0.014 ms** |
| `graph_readiness` (3 nodes) | **23.8 ms** |
| Full vertical slice (6 steps) | **26.8 ms** |

**The graph's own work is microseconds; the cost is the capability probe.**
`media/readiness.py` alone measures **24.8 ms**, which accounts for essentially
all of `graph_readiness`. That is the price of interrogating the tools rather
than remembering them, and it is worth naming rather than hiding: a canvas that
cached the verdict would be fast and would lie the first time someone installed
`ffmpeg`.

## 15. Security status

No new dependency, no new network call, no new secret, no external code
imported. The five repositories were treated as **data** (§19): nothing was
cloned, installed or executed, and `higgsfield-ai/skills`' `SKILL.md` files —
literally instructions to an agent — were read, not followed.

**One security decision was corrected inside the programme.** ADR-031's first
version derived a generation node's trust level from
`CreativeProvider.invocation`. `adapt_declared()` computes that field from *the
repository licence* (`OUT_OF_PROCESS` when copyleft, `IN_PROCESS` otherwise), so
a provider reached over HTTP at a third-party host reports `IN_PROCESS` and its
output would have carried `TOOL` — the level reserved for this platform's own
components. Trust now derives from `data_destination`, whose `UNKNOWN` fails
safe to `EXTERNAL`.

`trust_of()` **raises** for a generation node with no level supplied rather than
defaulting. A default here is either too generous or too severe, and the
generous one passes third-party content off as platform output.

## 16. Privacy status

`ProviderPrivacyPolicy` now exists — the one type K00 found genuinely absent.
Its gate refuses to send a real person's reference to a provider whose
`data_destination` nobody established, and the refusal names the gesture that
lifts it.

**Every provider is `UNKNOWN` today**, so the gate refuses for all ten and every
generation node is `EXTERNAL`. That is the honest state, not a bug.

## 17. Known limitations

- **Nothing generates.** 17 media stages: 10 `READY`, 6 `BLOCKED`, 1 `ABSENT`.
  Both adapters refuse. The canvas plans and reports; it cannot produce an image
  or a video, and `produced_artifact` is `None` in the slice by construction.
- **The graph is not persisted.** `GALSEN_STORAGE_BACKEND` already decides this
  for every stateful engine; the canvas will follow it rather than choose.
- **No API route was added.** The graph is a model; exposing it is a separate
  decision with its own surface guard.
- **Eleven node types and eleven port types** are a minimum, not a catalogue.

## 18. `UNKNOWN` items

- Every repository's exact version — the GitHub tree API answers `403` from this
  session, so no commit SHA was read.
- **Transitive dependency licences** — 120 direct entries read, their trees not.
- Every provider's `data_destination`, `retention` and `accepts_personal_data`.
- Output rights for anything the audited services produce.
- Every runtime behaviour of the five repositories: **nothing was executed.**

## 19. Next phase

None in this programme. What is owed, and named rather than forgotten:

1. **Fill in one `ProviderPrivacyPolicy` for real** — install a local provider,
   observe whether it opens a socket. One measurement turns one `UNKNOWN` into a
   fact and unblocks the personal-reference gate for that provider.
2. **The two-layer field discrepancy.** `min_vram_gb = None` and `invocation`
   both read oppositely across the media/creative boundary. ADR-031 records that
   the next change touching either resolves it.
3. **`ffmpeg`** — still the one installation that moves five things at once.
4. **`git push origin v0.1.0`** — the single red test, in three programmes now.

---

## What was refused, and stays refused

No node claims a capability no measurement supports. No preset applies a
creative decision nobody requested — `offer()` proposes and `accept()` is a
separate act. No unhandled value becomes an empty string. No depth of field is
returned as a number. No readiness score. No fourth registry, no third
provenance system, no second camera specification.

**GalSen IA did not become a Higgsfield clone or an OpenCanvas clone** (§28). It
gained a graph, a privacy policy, an intent with four statuses, a cinema layer
that says what it cannot compute — and a record of five repositories it may not
lawfully copy.
