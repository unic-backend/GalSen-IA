# ADR-035 — DeepSeek Harness would enter as a fourth coding backend, and not yet

**Status**: accepted
**Date**: 2026-08-20
**Directive**: DeepSeek Harness — GalSen IA Compatibility Audit, Phases 1–8
**Volets**: D00–D09 (evidence), D10 (this decision)
**Report**: `docs/deepseek-harness/feasibility-gates.md`
**Subject**: `github.com/deepseek-ai/deepseek-harness` at `0.1.0-rc.8`,
release `v0.1.0-rc.8` published 2026-08-19, read 2026-08-20

## Context

The directive asked whether DeepSeek Harness can provide useful capabilities
**without replacing, weakening, duplicating or breaking** GalSen IA's
orchestration, and set the default assumption explicitly: GalSen IA remains the
strategic orchestration layer.

Ten audit phases answered it. **Nothing was installed and no `src/` file was
changed**, as Phases 1 and 8's preamble require.

This decision follows ADR-034, which declined OpenClaw. **The two subjects are
not alike, and the audit was run without inheriting that verdict** — the phase
plan said so before the first source was read, and the evidence bore it out.

## Decisions

### 1. Option C — a specialized coding-agent backend

Of Phase 8's five options, **C** is the only one the evidence supports.

- **Not A** (do not integrate): no gate fails outright. Three of Phase 7's
  eleven are `UNKNOWN` and **one permitted installation would close all three**.
- **Not B** (generic isolated adapter): too vague for a seam that already exists
  and is specific. `src/coding_engine/` routes on `CodingCapability` and
  *"ne connaît aucun des trois moteurs par son nom"* (ADR-028).
- **Not D** (selected components): ill-defined against a system where
  *"everything is a plugin, including the model adapter, the tool registry, the
  session log, and the agent loop itself"*. There is no privileged core to take
  a component from.
- **Not E** (replace a subsystem): the directive forbids choosing E for
  popularity, and nothing here comes close to the *"exceptionally strong
  evidence"* it demands. `BENCHMARK.md` publishes **no scores**.

**Where it would sit**: as a fourth `CodingEngineAdapter` beside `aider`,
`openhands` and `swe_agent`. Nothing else. Not the orchestrator, not a model
router, not a memory, not a plugin host.

### 2. Implementation is not authorized by this ADR

The directive's own header says *"DO NOT INTEGRATE IT YET"* and its closing rule
says *AUDIT → MEASURE → DECIDE → THEN IMPLEMENT ONLY IF JUSTIFIED*. This ADR is
the **decide** step. Three conditions must close first, and each is cheap and
named:

1. **Measure quality.** Install one existing engine and one DSH variant in an
   environment permitted to install; run the same task set through both, on this
   repository, with a reachable provider. Phase 7 gate 7 is `UNKNOWN` today, and
   it is the gate the whole *"better coding agent"* question rests on.
2. **Read one licence file.** `@anthropic-ai/claude-agent-sdk` is listed
   `SEE LICENSE IN` in `THIRD_PARTY_NOTICES.md` and was not read.
3. **Answer what `dsh-headless` persists.** Open since D00.2 and unclosed after
   three phases; `persistence.md` *"does not distinguish persistence behavior
   between one-shot runs and server deployments."*

### 3. One configuration, and the rejected one is named

If it enters, DSH is configured with `@deepseek-ai/dsh-llm-pi-ai` pointed at
GalSen IA's **own OpenAI-compatible endpoint**, so every inference passes
through `ModelRouter` and ADR-014's sovereign default holds.

**Rejected**: DSH holding its own provider credentials. That reaches a hosted
provider outside `ModelRouter`, and — as ADR-034 already recorded for a
different project — **the existing sovereignty test would keep passing while the
guarantee was false**, because it exercises GalSen IA's model path and a second
runtime is not on it.

DSH does not force this: `config-catalog.md` states DeepSeek is *"supported but
not mandated as default"*.

### 4. The sandbox is a host property, not a project property

DSH's file confinement is `bwrap`/Landlock on Linux. **On this host it cannot
run**: `bwrap` absent, `landlock_create_ruleset` → `ENOSYS`, a weak stub in
`/proc/kallsyms`, no LSM in `securityfs`. Kernel `6.18.5-fc-v20` has Landlock
compiled out.

Its own rule — *"Silent unconfined passthrough is never legal for a confined
policy"* — means it would **refuse to confine rather than pretend to**, which is
correct behaviour and is why this is recorded as a host constraint rather than a
fault.

**Consequence**: the complementarity D04 found — our sandbox bounds CPU, memory
and environment but not filesystem; theirs bounds exactly the filesystem — is
**real as architecture and unavailable as deployment here**. On a host with
Landlock compiled in, it holds.

### 5. Nothing from its plugin ecosystem is exposed

The four-tool allowlist derived in ADR-034 — `rag`, `embeddings`, `web_search`,
`metrics` — transfers unchanged, because it is a filter over **our** declared
effects, data scopes and approvals rather than a property of any runtime.

DSH's own plugin model is gated (*"An unauthorized Client Package waits for
approval"*) but weaker than ours on one point: *"Plugin-wide authorization
covers later versions"*, where `src/plugins/review.py` **disables a plugin the
moment it is edited**, because the authorisation was granted for what its author
wrote.

## Consequences

**Positive.** The seam already exists and was built for this in ADR-028, so the
experiment costs a declaration and is removable by deleting it. Failure
detection and fallback are already in place at three layers, and the coding
router **already runs with all three declared engines unavailable** — so a
fourth that is absent changes nothing that works today.

**Negative, stated rather than softened.** **Quality is unmeasured**, and this
ADR chooses a *shape* on structural evidence while the empirical question stays
open. That is defensible only because the shape is cheap and reversible; it
would not be defensible for anything load-bearing.

**Neutral.** Two points of genuine alignment were found and are worth keeping
whatever happens: approval **fails closed** on both sides — DSH's `never`
*"resolves `'rejected'` deterministically"*, and a missing answerer yields
`'unavailable'` — and DSH refuses silent unconfined passthrough exactly as this
repository refuses plausible answers from unfinished capabilities.

## What this ADR does not decide

- **Whether DSH is a better coding agent.** Nothing measured it, the project
  publishes no scores, and the directive forbids the claim.
- **Whether to install it.** That is condition 1, and it needs an environment
  that may install.
- **Anything about the other three adapters.** They remain declared and
  unavailable, each naming its own repair.

## Findings about GalSen IA produced by this audit

Recorded for `pending-work`, none fixed here:

1. **This repository has no `LICENSE` file** — `ls LICENSE*` returns nothing.
   Five programmes spent on *a manifest is a declaration, a file is a grant*,
   and GalSen IA has neither.
2. **The sovereignty test does not cover subordinate runtimes** — second
   occurrence, after ADR-034. Two different projects, the same hole, which makes
   it a missing test here.
3. **`load_capabilities()` is uncached at ~22 ms** — carried from ADR-034,
   still latent.
