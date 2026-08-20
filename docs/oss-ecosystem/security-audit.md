# E07 — Security audit (§9)

**Written**: 2026-08-20. §9 lists eleven surfaces to inspect **before**
integration, and adds one rule: *"Do not weaken existing GalSen IA security
controls."* Since E05 produced **zero `INTEGRATE`**, no control is weakened by
this programme — nothing is added.

What that leaves is the more useful half: **what the audit found about this
repository while looking at twelve others.**

---

## The eleven surfaces, per candidate class

| Surface | Verdict for the twelve |
|---|---|
| **Dependency risk** | Highest in the two GPU serving engines — vLLM **97 declared**, SGLang **128** — and in Open WebUI (**98 unconditional**) and OpenHands (**85**). Lowest in llama.cpp and whisper.cpp bindings (**4 each**). None is installed |
| **Arbitrary code execution** | **OpenHands is the only one whose purpose is executing code**, and it is already behind `authorize()`, the sandbox allowlist and an approval path |
| **Network access** | vLLM, SGLang, Qdrant, Open WebUI are servers; LiteLLM is a client to hosted vendors. All would be reached across a boundary, none in-process — **except** LiteLLM, which is the one that would be imported |
| **Credential handling** | **LiteLLM is the only candidate that would hold provider credentials.** ADR-014 refuses that shape; E04.1 places it `OUTSIDE` |
| **Sandboxing** | Nothing added. `src/sandbox/policy.py` remains the boundary: `ENVIRONMENT_TRANSMIS` is **six** variables, allowlist and never a denylist |
| **Filesystem access** | Training and coding candidates read and write real directories. See finding **S2** below |
| **Model download behaviour** | Transformers, Unsloth and both Whisper paths fetch weights from Hugging Face — **403 through this proxy**, so no download can occur here at all |
| **Remote execution** | None introduced |
| **Tool execution** | `src/tool/authorization.py` unchanged; ADR-034's four-tool allowlist (`rag`, `embeddings`, `web_search`, `metrics`) still stands |
| **Prompt-injection exposure** | Unchanged. `src/security/trust.py` keeps external text as **data with an origin**, never an instruction |
| **Data exfiltration** | The one new vector would be LiteLLM's unconditional `openai>=2.20.0`, which puts a hosted-vendor client in the environment whether or not a key exists |

**Nothing on that table requires action, because nothing is being installed.**

---

## The three findings about GalSen IA

These are the security chapter's real output. **None is fixed here** — §12
forbids implementation, and each fix is a suggestion, not a task
(`.claude/rules/spec-driven-governance.md`).

### S1 — `Role.USER` reaches the coding engine · **latent**

```
POST /coding/task   dependencies=[rate_limit, require_permission(TOOL_EXECUTE)]
```

`tool:execute` is held by `admin` (21 permissions), `operator` (9) **and `user`
(8)**. And the request body decides the rest:

- **`workspace`** — `resolve_workspace()` accepts *any existing directory on the
  host*. It resolves symlinks and checks it is a directory. **There is no
  permitted root.** `confine()` bounds paths *relative to* the workspace the
  caller chose.
- **`allow_network`, `allow_push`, `dry_run`, `timeout_seconds`** — all from the
  body.
- **`GALSEN_CODING_REQUIRE_CONTAINER`** defaults **off**.

**Why it is latent and must be reported as latent**: all three coding engines
are declared **unavailable**. Nothing executes. Calling this exploitable would
be the exaggeration this method exists to prevent.

**What stands in the way, stated fairly**: `inspect_instruction()` refuses some
instructions and flags others for approval; the sandbox inherits no credential
(proved by `tests/test_sovereignty_subordinate_runtimes.py`); and execution is
attributed to `ctx.subject`, never to an identifier in the body.

**Severity**: high **if** an engine is ever installed, negligible until then.
That conditional is the finding.

**Suggested shape, not a task**: a distinct `CODE_EXECUTE` permission held by
`operator` and `admin` but not `user`, plus a permitted workspace root read from
configuration.

### S2 — the training pipeline gates the run, not the data · **latent**

`scripts/training/train_adapter.py` **refuses to start without an approval
identifier** (line 94, *"Une approbation humaine est exigée (ADR-006)"*) and
hashes the dataset for lineage. Both are real.

But the input is `--paires data/exports/pairs.jsonl` — **a path chosen by
whoever runs the script**. The approval proves someone approved *a run*; it does
not prove *what was in the file*. The hash gives lineage **after the fact** —
that is how you find out later, not how you prevent.

§4G's rule: *"NEVER train on private user data without explicit authorization
and proper controls."* The authorisation exists. The control over *what the
dataset contains* does not.

**Latent**: nothing trains — no GPU, no authorised dataset, and ADR-014's SamP
and ToP families **do not exist yet**.

### S3 — `litellm==1.81.10` is installed, declared by nothing, imported by
nothing · **informational**

Traced in E01: absent from every requirements file, absent from every `import`
in `src/`, `agents/`, `scripts/` and `tests/`. Most likely pulled in by tooling
outside this repository.

**An importable package is not an executed one**, and saying otherwise would be
fabrication. But an inference client that ships `openai>=2.20.0` sitting inside
a sovereign-by-default platform is exactly the shape ADR-034 and ADR-035 each
described in the abstract. **This repository did not install it, so removing it
is not this programme's call.**

---

## What did not change, and that is the point

| Control | State after this programme |
|---|---|
| ADR-014 sovereign default | untouched — hosted providers still not registered |
| `ENVIRONMENT_TRANSMIS` allowlist | untouched — six variables |
| ADR-006 approval gate | untouched |
| `src/security/trust.py` | untouched |
| Four-tool allowlist (ADR-034) | untouched |
| Tests | **zero added, altered or removed** |

**§9's instruction — do not weaken existing controls — is satisfied trivially,
because nothing was added.** A security chapter whose main content is *what it
declined to touch* is the correct outcome for an audit that recommended no
integration.

---

## What E07 refuses to conclude

- **That S1 is exploitable today.** It is not. Three engines, all unavailable.
- **That S3 is a vulnerability.** It is an unowned package.
- **That the candidates are unsafe.** None was installed; every dependency
  count is a declaration read from metadata, not an executed audit of code.
- **That the fixes should be applied.** They are named so someone can decide.
