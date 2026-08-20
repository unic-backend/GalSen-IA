# D07 — Security audit (Phase 5)

**Built**: 2026-08-20. DSH facts VERIFIED FROM OFFICIAL SOURCE, documents named.
**The measurements in §1 were taken on this machine and are reproducible** —
commands given.

Phase 5's rule: *"DO NOT give the runtime broader permissions than necessary…
Do not bypass existing GALSEN-IA security boundaries."*

---

## 1. The measurement that decides this phase

D04 left one question open: DSH's Linux file confinement is `bwrap`/Landlock —
**is it available here?**

**No. Measured three ways, all reproducible:**

```bash
which bwrap                      # → ABSENT
```

```python
import ctypes, os
libc = ctypes.CDLL("libc.so.6", use_errno=True)
libc.syscall(444, None, 0, 1)    # landlock_create_ruleset(version query)
# → -1, errno 38, "Function not implemented"
```

```bash
grep landlock /proc/kallsyms | head -2
# → ffffffff8130ade0 W __pfx___x64_sys_landlock_create_ruleset
#   ffffffff8130adf0 W __x64_sys_landlock_create_ruleset      ← W = weak stub
cat /sys/kernel/security/lsm     # → no such file; /sys/kernel/security/ is empty
```

Kernel `6.18.5-fc-v20`. The `W` marks a **weak stub**, and `securityfs` lists no
LSM — so `ENOSYS` is the kernel having Landlock **compiled out**, not a
permission denial. `bwrap` is absent from the image as well.

**Consequence, stated plainly**: on this machine, DSH's sandbox would run in the
one mode it can — none of them. Its own rule says what happens then:

> *"Silent unconfined passthrough is never legal for a confined policy."*

`INFERENCE`: **the harness would refuse to confine rather than pretend to**,
which is the correct behaviour and also means **the complementarity D04 found is
not available in this environment.** D04's positive finding stands as an
architectural fact and fails as a deployable one, here, today. On a host with
Landlock compiled in, it would hold.

This is the third consecutive programme in which the blocker is **this
environment's privileges**, not the audited project.

## 2. Phase 5's eleven items

| # | Item | What the source says | Class |
|---|---|---|---|
| 1 | **Filesystem access** | three sandbox modes: `read-only` (*"only required sinks such as `/dev/null`"*), `workspace-write` (*"writes under the workspace root and the backend's promised temp area"*), `danger-full-access` (*"bypasses confinement"*) | VERIFIED |
| 2 | **Shell execution** | `bash`, `pwsh`, six `terminal_*` tools, `run_code` | VERIFIED |
| 3 | **Network access** | **outside the sandbox vocabulary** — *"Network and process visibility are outside this vocabulary"* | VERIFIED — and it is a gap |
| 4 | **Process spawning** | `job_*` tools, `subagent`, background execution on `bash`; process visibility **not confined** | VERIFIED |
| 5 | **Environment variables** | credential layers `env`, `file`, `project-env`, `user-env` | VERIFIED |
| 6 | **Credentials** | *"resolved once per operation"*, consumers *"must not cache across operations"*, *"an empty stored value is absent everywhere"*. Storage, form, encryption: **not stated** | Partial / `UNKNOWN` |
| 7 | **Secrets** | whether credentials reach plugins or tools: **not stated** | **`UNKNOWN`** |
| 8 | **Plugins** | everything is a plugin, including the model adapter and the agent loop | VERIFIED |
| 9 | **Third-party plugins** | installation procedures **not stated**; what a running plugin may access **not stated** | **`UNKNOWN`** |
| 10 | **Sandboxing** | kernel-level, three platforms — **and unavailable here** (§1) | VERIFIED |
| 11 | **Approval** | see §3 | VERIFIED |

**Six verified, three partial or `UNKNOWN`, and the `UNKNOWN`s are the ones
Phase 5 cares most about**: what a plugin may access, and whether credentials
reach it.

## 3. Approval — and a principle this repository already holds

`docs/subsystems/approval.md`, VERIFIED FROM OFFICIAL SOURCE:

- Two policies: **`ask`** (the default) *"delegate[s] to the composed
  answerers"*; **`never`** *"never prompt[s] anyone: every ask resolves
  `'rejected'` deterministically."*
- *"a missing or throwing answerer yields `'unavailable'` (fail closed)"*, and
  tools *"fail closed unless it is `allowed-once`."*
- Answerers: *"UI channels may provide human answerers; the ACP automation
  bridge provides one-shot machine decisions for its own agents."*

**`never` does not mean auto-approve. It means deterministic rejection.** And a
missing answerer fails closed.

That is GalSen IA's own rule, reached independently: *an approval is never
granted by the absence of someone to refuse it* (`orchestration_paths.py`).
**Two projects, same principle, different codebases** — worth recording as a
point of genuine alignment rather than as a coincidence.

**One tension, and it is recorded rather than resolved.** D00.3 measured that the
`danger-full-access` preset pairs that sandbox mode with approval policy
`never`. If `never` rejects everything, that pairing is stricter than its name
suggests; if `danger-full-access` simply gates nothing, `never` never fires.
**Which of the two holds is `UNKNOWN`**, and it matters, because a preset named
*danger-full-access* is the one an operator would most want to understand
exactly.

## 4. The sharpest question, and it does not close

D06 handed this phase one question: **`cordis_define` / `cordis_run` let an
agent register plugins at runtime — does that reach the model adapter?**

`docs/subsystems/extensions.md`, VERIFIED FROM OFFICIAL SOURCE:

- Agents can *"define versioned Cordis packages"*, and *"Define a new Plugin's
  first Package or append a Package to an existing Plugin"* is a programmatic
  capability. **Runtime registration is supported.**
- A gate exists: *"An unauthorized Client Package waits for approval;
  Plugin-wide authorization covers later versions."*
- **What a running plugin may access: not stated.**
- **How third-party plugins are installed and distributed: not stated.**

`INFERENCE`, labelled: an **approval gate on runtime plugin registration** is
the right shape, and *"Plugin-wide authorization covers later versions"* is a
real and quotable limitation — approving version 1 approves version 2. That is
precisely the rule `src/plugins/review.py` refuses on our side: **editing a
plugin disables it**, because *"the authorisation was granted for what its
author wrote."*

**So the question closes only halfway.** Runtime registration is gated by
approval; whether an approved plugin can reach the model adapter, credentials,
or the network is **`UNKNOWN`**, because the document that would say does not.

## 5. Phase 5's instruction, applied

*"DO NOT give the runtime broader permissions than necessary."*

The OpenClaw audit derived a four-tool allowlist from `tools/tools.yaml`. **The
same allowlist applies unchanged here** — `rag`, `embeddings`, `web_search`,
`metrics` — for the same reason: it is a filter over declared effects, data
scope and approval, and nothing about DSH changes what those four tools do.

But the shape of the risk differs, and D07 must say so:

| | OpenClaw | DSH |
|---|---|---|
| Holds credentials in a long-lived process | **yes** — unsandboxed gateway | **`UNKNOWN`** — depends on `dsh-headless` (still open) |
| Confines the filesystem | Docker, **off by default** | kernel-level, **unavailable on this host** |
| Confines the network | Docker default `none` | **not in scope**, by its own statement |
| Agent may register plugins at runtime | not found | **yes, behind an approval gate** |

`INFERENCE`: **DSH's file confinement is better designed and less available;
its network posture is worse — it declares network out of scope where OpenClaw
defaulted Docker egress to `none`.** Neither is a verdict; both are inputs to
D09.

## 6. The central question, still open after three phases

D00.2 asked what `dsh-headless` — *"a one-shot runner without a server"* —
actually persists. D00.3 found `persistence.md` *"does not distinguish
persistence behavior between one-shot runs and server deployments"*. D07 did not
close it either: nothing read in `approval.md`, `extensions.md` or
`config-catalog.md` addresses headless persistence.

**It stays `UNKNOWN`**, and it is now recorded as such for the third time rather
than quietly resolved. What would close it: reading
`packages/*/dsh-headless`'s source, or installing and running it — the second
being forbidden by the directive.

## 7. What D07 concludes

1. **DSH's Linux sandbox cannot run on this host.** `bwrap` absent, Landlock
   `ENOSYS`, weak stub in `kallsyms`, no LSM in `securityfs`. Measured, not
   assumed, and it converts D04's best finding from *deployable* to
   *architectural*.
2. **Approval fails closed, and `never` rejects rather than allows** — genuine
   alignment with this repository's own rule.
3. **Runtime plugin registration exists and is gated**, but *"Plugin-wide
   authorization covers later versions"* is weaker than our
   editing-disables-approval rule.
4. **Two `UNKNOWN`s remain and are security-relevant**: what a plugin may
   access, and whether credentials reach it.
5. **One `UNKNOWN` is now three phases old**: what `dsh-headless` persists.
6. **The four-tool allowlist transfers unchanged** from the previous programme,
   because it is a property of our tools rather than of the runtime.
