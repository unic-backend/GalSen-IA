# DeepSeek Harness — final report

**Programme**: DEEPSEEK HARNESS — GALSEN-IA COMPATIBILITY AUDIT
**Executed**: 11 volets, **14 phases**, cadence two phases per turn
**Decision**: [ADR-035](../architecture/decisions/035-deepseek-harness-is-a-coding-backend-not-an-orchestrator.md)
**Subject**: `github.com/deepseek-ai/deepseek-harness`, `0.1.0-rc.8`, read 2026-08-20
**Measured**: 2026-08-20, `Linux 6.18.5-fc-v20`, Python 3.11.15, 4 CPUs

The directive asks for exactly twenty-two items. They are answered in order.

---

### 1. Repository state

Branch `claude/unit-tests-notification-search-file-4z0ok1`, clean, all work
pushed. Baseline at programme start `c7cb1b6`; at close, the final commit of
this programme. PR #31 open, red on one test — see item 15.

### 2. Files created

**Ten documents**, all under `docs/deepseek-harness/` except the ADR:

`phase-plan.md`, `source-audit.md`, `overlap-matrix.md`, `coding-capability.md`,
`provider-independence.md`, `security-audit.md`, `licence-audit.md`,
`feasibility-gates.md`, `architecture-decision.md`, `test-plan.md`, and this
report — plus
`docs/architecture/decisions/035-deepseek-harness-is-a-coding-backend-not-an-orchestrator.md`.

### 3. Files modified

`CLAUDE.md` (ADR count 35 → 36, corrected after `test_published_numbers` caught
it), `docs/memory/phase-plan.md`, and this programme's own plan.

**Zero files under `src/`.**

### 4. Existing components reused

None consumed; **eight measured and cited**: `src/coding_engine/router.py` and
its three adapters, `src/tool/authorization.py`, `src/sandbox/policy.py`,
`src/integration/degradation.py`, `src/model_engine/` (`ModelRouter`,
`FailoverModelRouter`, providers), `src/plugins/review.py`,
`src/security/redaction.py`, `src/audit_engine/`.

### 5. DeepSeek Harness capabilities verified

From official sources, read 2026-08-20:

- **Architecture**: *"A running `dsh` is a plugin tree composed at boot from
  ordered layers"*; *"every part of the product is a plugin, including the model
  adapter, the tool registry, the session log, and the agent loop itself"*;
  *"no privileged core to patch"*. Framework: Cordis.
- **Bundles**: `dsh-base`, `dsh-web-app`, **`dsh-headless`** — *"a one-shot
  runner without a server"*.
- **Tools**: ~50, centre of gravity a repository — `bash`, `pwsh`, file ops,
  `glob`/`grep`, **`lsp`**, six persistent-PTY tools, `subagent`, `workflow`,
  `ralph`, `run_code`, `session_*`.
- **Sandbox**: kernel-level per platform — `bwrap`/Landlock, Seatbelt, ACL
  restricted-token; three modes; **file effects only**.
- **Approval**: `ask` and `never`; `never` *"resolves `'rejected'`
  deterministically"*; a missing answerer yields `'unavailable'` — **fail
  closed**.
- **Providers**: DeepSeek *"supported but not mandated as default"*; `pi-ai`
  gives OpenAI-compatible, Anthropic and Bedrock with `baseURL` override.
- **Persistence**: JSONL or SQLite schema 17; survives process exit; resume by
  session id.

### 6. GalSen IA overlaps

Nineteen subsystems: **4 complementary, 1 duplicate, 4 conflicting, 5
unnecessary, 5 `UNKNOWN`** (`overlap-matrix.md`).

The four conflicts are all orchestration and permission granularity. The five
`unnecessary` — creative state, video, reference entities, VoiceScene, world
representation — are what makes this a coding-backend question rather than an
orchestration one.

### 7. Provider comparison

| | GalSen IA | DSH |
|---|---|---|
| Provider abstraction | `providers/` + `ModelRouter` + externalised policy | model adapter as plugin |
| Sovereign default | **hosted providers not registered at all** (ADR-014) | none — configuration decides |
| Fallback | `FailoverModelRouter`, threshold 3, reset 300 s | not evaluated |

**Viable**: DSH via `pi-ai` at our own OpenAI-compatible endpoint.
**Rejected**: DSH holding its own credentials.

### 8. License findings

MIT, declared **and filed**. `THIRD_PARTY_NOTICES.md` published by the project:
~130 packages, ~100 MIT, ~15 Apache-2.0, 3 BSD-3, 2 ISC, 1 BSD-2; **two
copyleft** (LGPL-3.0-only, MPL-2.0) that the project scopes to development
tooling *"not linked into or distributed with any DeepSeek Harness artifact"*.

**One `UNKNOWN`**: `@anthropic-ai/claude-agent-sdk`, listed `SEE LICENSE IN`,
unread.

### 9. Security findings

- **Its sandbox cannot run on this host**: `bwrap` absent,
  `landlock_create_ruleset` → `ENOSYS`, weak stub in `/proc/kallsyms`, no LSM in
  `securityfs`. Kernel has Landlock compiled out. **Measured three ways.**
- Approval **fails closed**, matching this repository's own rule.
- Runtime plugin registration is gated, but *"Plugin-wide authorization covers
  later versions"* — weaker than `review.py`, where **editing disables**.
- **`UNKNOWN`**: what a plugin may access; whether credentials reach it; what
  `dsh-headless` persists.

### 10. Tests added

**Zero.** Thirteen suites are **defined** in `test-plan.md`; two are recorded as
**blocked** until conditions close.

### 11. Total tests

**6 970 collected** (6 958 passing + 12 skipped), 3 deselected.

### 12. Passed

**6 958.**

### 13. Failed

**1** — `tests/test_release_check.py::TestEtiquette::test_l_etiquette_de_la_version_courante_existe_bien`.

### 14. Skipped

**12** locally; 15 in CI, three tests skipping there that do not skip here.

### 15. Regression status

**PASS.** A full regression ran after **every phase** of this programme —
fourteen runs, all with the same single failure. That failure is the `v0.1.0`
tag: `git ls-remote --tags origin` returns nothing, so it fails identically on
`main` and is not caused by this branch. Explained on PR #31.

### 16. Performance measurements

| | |
|---|---|
| Node present | **`v22.22.2`** — satisfies DSH's `^22.19.0 \|\| >=24.0.0` |
| pnpm present | 10.33.0, against `pnpm@11.7.0` declared |
| CPUs | 4 · RAM 16 075 MB, 15 090 free · disk 28 G free |
| DSH latency / throughput | **`NOT_MEASURED`** — install forbidden |

### 17. GPU / resource measurements

**No GPU present** (`ls /dev/nvidia*` → none) and **none required** — DSH states
no GPU requirement. Gate 5 passes because the requirement is absent, not because
hardware is.

### 18. UNKNOWN items

1. What `dsh-headless` persists — open since D00.2, three phases.
2. What a running plugin may access.
3. Whether credentials reach plugins or tools.
4. `@anthropic-ai/claude-agent-sdk`'s licence.
5. Whether the provider configuration can be made unwritable by the agent.
6. Whether `danger-full-access` + `never` is stricter or vacuous.
7. Latency, quality, measurability — Phase 7 gates 6, 7, 8.
8. MCP depth; multimodal orchestration; a repair loop; memory architecture.

### 19. Known limitations

- **Its confinement does not work here**, so D04's complementarity is
  architectural rather than deployable on this host.
- **Quality is unmeasured by anyone whose evidence this audit could read.**
  `BENCHMARK.md` publishes **NO SCORES**.
- **`0.1.0-rc.8`**, with release candidates two days apart. Pre-1.0 interfaces
  move.
- A second language runtime beside Python, of `UNKNOWN` footprint.

### 20. Final architecture decision

**OPTION C — integrate as a specialized coding-agent backend**, as a fourth
`CodingEngineAdapter`. Not the orchestrator, not a model router, not a memory,
not a plugin host. **ADR-035.**

A, B, D and E were each argued and rejected in `architecture-decision.md`.

### 21. Integration recommendation

**Do not implement yet.** Three conditions, each cheap and named:

1. **Measure quality** — same task set through one existing engine and one DSH
   variant, in an environment permitted to install.
2. **Read one licence file** — `@anthropic-ai/claude-agent-sdk`.
3. **Determine what `dsh-headless` persists.**

Condition 1 closes Phase 7's three `UNKNOWN` gates at once and is the only one
that matters for the *"better coding agent"* question.

### 22. Next implementation phase

**Phase 9 — the adapter boundary — is now valid to design** and is **not
authorized**. When it opens, the order is in `test-plan.md`: baseline, then the
four suites writable **before anything is installed** (routing, fallback,
recovery, removal), then the conditions, then the rest.

---

## Two claims this report does not make

**Not "best coding model".** Nothing measured it; the project publishes no
scores; the directive forbids the claim without comparative evidence.

**Not "production ready".** `0.1.0-rc.8`, and its confinement does not run here.

## What the audit found about GalSen IA

Recorded for `pending-work`, none fixed:

1. **No `LICENSE` file** — `ls LICENSE*` returns nothing. Five programmes on
   *a manifest is a declaration, a file is a grant*, and this repository has
   neither.
2. **The sovereignty test does not cover subordinate runtimes** — second
   occurrence, after ADR-034. Two projects, one hole, which makes it ours.
3. **`load_capabilities()` uncached at ~22 ms** — latent, carried from ADR-034.

An audit whose answer differs from the previous one, run by the same method, is
the only evidence that the method is doing work.
