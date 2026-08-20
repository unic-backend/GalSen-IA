# E04.3 — §4E whisper.cpp as a local speech backend, §4F where OpenHands belongs

**Written**: 2026-08-20. E03.4 filled the twenty fields for both. This phase
answers the two questions §4 actually asks, and one of them produced **a finding
about GalSen IA, not about the candidate**.

---

## §4E — Should whisper.cpp become the local/offline speech backend?

### The seam it would enter, verified

`src/multimodal/` is already a provider architecture for transcription:

- `interfaces.py` — `TranscriptionProvider` (ABC: `provider_id`, `model_name`,
  …), `TranscriptionProviderInfo`, `TranscriptionResult`,
  `TranscriptionUnavailable`
- `registry.py` — `set_transcriber()`, `active_transcriber()`,
  `transcription_status()`
- `whisper_provider.py` — 200 lines, the one implementation

So §4E's *"design it as a provider if useful"* is not work to invent: **a second
implementation of an existing ABC**, registered through an existing registry.
That is the cheapest possible shape, and it is the same conclusion the seam
produced for the coding engine in ADR-035.

### What decides it, and it is not the seam

`whisper_provider.py` states its choice with a written reason:

> *"`faster-whisper` est préféré à `openai-whisper` pour une raison mesurable :
> il fait tourner le même modèle sur CTranslate2, environ quatre fois plus vite
> sur CPU et avec moins de mémoire."*

whisper.cpp is the **same argument, one step further**: C/C++, quantized, four
unconditional dependencies against CTranslate2's stack. The candidate does not
lose on merits. It loses because **nothing here can compare the two**:

| | |
|---|---|
| `faster-whisper` installed? | **No** — `requirements-audio.txt` is not in the production image, and not installed here |
| whisper.cpp installed? | **No** |
| A model to load? | **No** — Hugging Face answers **403** through this proxy |
| **`ffmpeg` on this host?** | **`command not found`** (measured 2026-08-20) — so no audio could be decoded to 16 kHz PCM even if a model existed |

That last row is new and worth stating plainly: **the platform's notes describe
an `ffmpeg` built `--disable-everything`; in this container there is no `ffmpeg`
at all.** The measurement is what counts, and it is `command not found`.

### Recommendation

**`KEEP_EXISTING`** — unchanged from E03.4, and now for a sharper reason.

Replacing a decision that carries its own written justification with an
unmeasured alternative would be **exactly** the move the directive's final rule
forbids: *"Never destroy working architecture simply to use a popular
open-source project."*

**What would reopen it**, named and not invented: a host where both can actually
run, transcribing the same audio, with Wolof in the sample — because Wolof is
where model size matters most, and `whisper_provider.py` already records that
`medium` and `large-v3` do better there at several gigabytes. That is a
measurement, and it is not available here.

**One thing that is true regardless**: a second transcription provider costs a
class and a registry call. If it ever enters, it enters **beside**
`faster-whisper`, not instead of it — the registry already supports exactly one
active transcriber, chosen at runtime.

---

## §4F — Inside, a specialised agent, an external tool, or nowhere?

### The repository answered before the audit opened

`src/coding_engine/adapters/openhands_adapter.py` is one of three declared
adapters. §4F's four options collapse: OpenHands is **a specialised agent behind
a capability router, reached over HTTP, chosen by `CodingCapability` and never
by name** (ADR-028). Nothing to decide.

So the real question is the second half of §4F — the constraint:

> *"Do not expose unrestricted repository modification capabilities to ordinary
> users. Preserve security boundaries."*

**That one was measured, and it does not hold as written.**

### What was measured

```
POST /coding/task
  dependencies=[rate_limit, require_permission(Permission.TOOL_EXECUTE)]
```

Roles holding `tool:execute`, resolved through `get_permissions_for_role`:

| Role | Permissions | Reaches `/coding/task` |
|---|---:|---|
| `admin` | 21 | **yes** |
| `operator` | 9 | **yes** |
| **`user`** | 8 | **yes** |
| `readonly` | 4 | no |
| `student`, `parent`, `teacher`, `school_admin`, `education_authority`, `researcher` | 2–5 | no |

**`Role.USER` — the ordinary user role — reaches the coding engine.**

And the request body decides the rest of the parameters:

- **`workspace`** — `resolve_workspace()` accepts *any existing directory* on the
  host. It resolves symlinks and checks the path is a directory. **There is no
  permitted root**; confinement (`confine()`) applies to paths *relative to* the
  workspace the caller chose.
- **`allow_network`**, **`allow_push`**, **`dry_run`**, **`timeout_seconds`** —
  all taken from the body.
- **`GALSEN_CODING_REQUIRE_CONTAINER`** defaults to **off**
  (`os.environ.get(VARIABLE_CONTENEUR, "")` → falsy).

### What stands in the way, stated fairly

This is an exposure, not an open door. Four things are real:

1. **`inspect_instruction()`** refuses some instructions outright and marks
   others as needing approval — including *"publication distante"*, which
   `allow_push` relaxes.
2. **The sandbox environment allowlist** — `ENVIRONMENT_TRANSMIS` is six
   variables; no credential is inherited (proved by
   `tests/test_sovereignty_subordinate_runtimes.py`).
3. **`user_id=ctx.subject`** — execution is attributed to the authenticated
   subject and never to an identifier in the body. That comment is in the code,
   and it is right.
4. **All three engines are unavailable today.** Nothing executes. The exposure
   is **latent**, and saying otherwise would be the exaggeration this method
   refuses.

### The finding, stated as a finding and not a fix

**§4F's constraint is not currently met by the RBAC table.** An ordinary `user`
can submit a repository-modifying task, naming any directory on the host, with
network and push at their discretion — and the only reason nothing happens is
that no engine is installed.

That is the third time an external audit has produced a finding about **this**
repository rather than about its subject: ADR-034 found the sovereignty blind
spot, ADR-035 found the missing `LICENSE`, and this one finds a permission that
is one role too wide.

**Nothing is changed here.** §12 forbids implementation during the audit, and a
permission table is not something to edit in passing. It goes to **Ch. 07** as
the security chapter's first entry and to the final report as a named item, with
the fix that suggests itself — a distinct `CODE_EXECUTE` permission held by
`operator` and `admin` but not `user`, and a permitted workspace root — recorded
as *a suggestion, not a task* (`.claude/rules/spec-driven-governance.md`).

### Recommendation

**`ALREADY_PRESENT`** for OpenHands, unchanged. **The boundary §4F asks about is
where the work is**, and it belongs to GalSen IA.

---

## What E04.3 refuses to conclude

- **That whisper.cpp is slower or faster than `faster-whisper`.** Neither is
  installed, no model is reachable, and there is no `ffmpeg` to decode audio.
  Two `UNKNOWN`s, not a ranking.
- **That `/coding/task` is exploitable.** No engine is available; the exposure is
  latent and is reported as latent.
- **That the RBAC table should be changed by this programme.** It should be
  changed by someone who was asked to change it.
