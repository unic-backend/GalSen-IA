# O03 — Tool permission model (§7) and sandbox (§8)

**Built**: 2026-08-19. Sources: `tools/tools.yaml` and `src/sandbox/policy.py`
(VERIFIED FROM REPOSITORY), `docs/gateway/sandboxing.md` and
`docs/gateway/permission-modes.md` (VERIFIED FROM OFFICIAL SOURCE, read
2026-08-19 and quoted in O01).

Nothing was installed and no sandbox was tested. §8's question — *is OpenClaw's
sandboxing sufficient for GalSen IA* — is answered from what both projects
**say** about themselves, and the phase says so where a claim is untested.

---

# O03.1 — The allowlist (§7)

## The allowlist is derived, not invented

`tools/tools.yaml` already declares, for each of the 24 tools, the three
dimensions §7 cares about: **effects** (`read` / `write` / `external`),
**data scope** (`public` / `system` / `user_private`), and whether a human must
approve. The allowlist below is a filter over that table, so it cannot drift
from the tools it governs.

| Tool | Effects | Scope | Approval | OpenClaw |
|---|---|---|---|---|
| `rag` | read | public | no | **ALLOWED** |
| `embeddings` | read | public | no | **ALLOWED** |
| `web_search` | read, external | public | no | **ALLOWED** |
| `metrics` | read | system | no | **ALLOWED** |
| `model` | read | public | no | DENIED — §7, model infrastructure |
| `agri_advice` | read | public | no | DENIED — advice needing a verified source |
| `github` | read, external | public | no | DENIED — acts on a remote repository |
| `browser` | read, external | public | no | DENIED — fetches pages in the platform's name |
| `git` | read | system | no | DENIED — §7, repository state |
| `rag`/`memory` | read, write | user_private | no | DENIED — §7, user private data |
| `ocr`, `pdf`, `media` | read / read+write | user_private | no | DENIED — §7, user private data |
| `email`, `calendar`, `media_generation` | read, write, external | user_private | **yes** | DENIED — acts for a person, and needs a human |
| `filesystem`, `database`, `screen`, `logging` | read/write | system | no | DENIED — §7, filesystem / database / private display |
| `terminal`, `gui`, `docker`, `api` | write / external | system, public | **yes** | DENIED — §7, shell, GUI control, infrastructure |

**Four tools out of twenty-four.** All read-only or read-plus-outbound-search,
all `public` scope except `metrics`, none requiring approval, none touching a
person's data.

`metrics` is included deliberately and is the only `system`-scope entry: it
reports platform state and writes nothing. If that reads as too generous later,
it is one line to remove, which is the point of a table rather than a rule.

## Why this list differs from the MCP one, and why that is correct

`src/mcp/exposure.py` already exposes a whitelist to external MCP clients:
`rag`, `memory`, `embeddings`, `web_search`, `pdf`, `ocr`, `metrics`, `logging`.
That list includes three `user_private` tools, and it is right to, because an
MCP client acts **under an authenticated caller's identity** — the memory it
reads is the caller's own.

**OpenClaw is not that.** It is a runtime executing actions a *model* chose,
inside a session whose permission mode was set at the start
(`permission-modes.md`, O01). §7 names *user private data* explicitly. So the
OpenClaw list is the MCP list **minus** `memory`, `pdf`, `ocr`, and minus
`logging` because it writes.

**Two allowlists, two callers, two justifications** — recorded here so a later
reader does not "harmonise" them into one and quietly widen the narrower.

## What the allowlist does not do

It does not replace `authorize()`. Every call still passes
`src/tool/authorization.py` — role ceiling, effect ceiling, data-scope ceiling,
and `REQUIRES_APPROVAL` as a third answer. The allowlist narrows *what may be
asked for*; the existing gate decides *whether this actor may have it now*.

`INFERENCE`: an allowlist alone would be a static grant, and a static grant is
what §6 forbids when it says OpenClaw *"must NOT independently redefine GalSen
IA permissions."*

---

# O03.2 — Sandbox (§8)

## The two sandboxes, measured side by side

| §8 asks about | GalSen IA (`src/sandbox/policy.py`) | OpenClaw (`docs/gateway/sandboxing.md`) |
|---|---|---|
| Default | **on by design**; the module is the execution path | **off** — *"Sandboxing is off by default"* |
| Filesystem isolation | **not bounded** — *"un fils lit et écrit là où l'utilisateur le peut"* | `none` / `ro` / `rw` workspace levels, **but** *"Binds bypass the sandbox filesystem"* |
| Process isolation | **partial** — `RLIMIT_NPROC` bounds the *user*, not the sandbox; the group is killed after each run | container-level under Docker/Podman |
| Network restrictions | **not bounded** — *"aucune coupure réseau sans espaces de noms"* | Docker default *"network: 'none' (no egress)"*; `host` and `container:<id>` blocked |
| CPU limits | **yes** — `cpu_seconds` | *"PID/memory/CPU limits"* under Fleet cells |
| Memory limits | **yes** — `memory_bytes` | same |
| Timeout | **yes** — `wall_seconds`, distinct from CPU time | not stated in what was read |
| Temporary storage | working directory isolated and cleaned — *"c'est un rangement, pas une frontière"* | workspace mounts |
| Container isolation | **none** — needs privileges the platform does not have | Docker/Podman/SSH/OpenShell backends |
| Credential isolation | **yes** — only `PATH, LANG, LC_ALL, TZ, HOME, TMPDIR` are passed; everything else is stripped | *"The default-off secret egress proxy is Gateway-loopback only… Sandbox/container proxy reachability is not implemented"* |

## The answer to §8's question

**OpenClaw's sandboxing is not sufficient for GalSen IA**, and the strongest
evidence is the project's own sentence: *"This is not a perfect security
boundary, but it materially limits filesystem and process access when the model
does something dumb."*

Three specifics, all VERIFIED FROM OFFICIAL SOURCE:

1. **It is off by default.** A subsystem whose protection depends on an operator
   having set `agents.defaults.sandbox` is a subsystem that is unprotected on
   the day someone forgets.
2. **The Gateway process itself is not sandboxed** — only tool execution is. The
   Gateway is the part that holds credentials, channel accounts and sessions.
3. **`tools.elevated` runs on the host**, by design, *"or configured escape
   path"*. An allowlist that a configuration file can widen is not a boundary
   GalSen IA can rely on.

**§8's instruction is then explicit: do not weaken GalSen IA security; design an
additional isolation layer.** This phase designs it and then reports what it
costs, because the honest answer is uncomfortable.

## The additional isolation layer, and the blocker it hits

The layer §8 asks for is a **container boundary around the whole OpenClaw
process** — not around its tool calls, since the Gateway is the part holding
secrets. Concretely: a container with no host bind mounts, no Docker socket, a
dedicated network namespace with egress denied except to the platform's own
loopback API, its own credential store, and cgroup limits.

**GalSen IA cannot create that boundary today, and this is measured, not
feared.** `src/sandbox/policy.py` already records the reason in its own
`NON_GARANTI` tuple: bounding the filesystem and the network requires
namespaces, and a per-execution process cap requires cgroups — *"donc des
privilèges que la plateforme n'a pas."* The `docker` tool is declared and
**disabled**, and ADR-017 records why: the obvious implementation, mounting the
host socket, hands out host root.

So the layer §8 requires is not something this programme can write. It is
something an **operator** provisions — a container runtime the platform is
allowed to drive, or a separate host.

`INFERENCE`, recorded as a blocker for O12 rather than resolved here:
**running OpenClaw with the isolation §8 demands requires infrastructure this
platform does not currently have.** Running it without that isolation would put
an unsandboxed-by-default gateway holding credentials next to the platform —
which is the outcome §8 exists to prevent.

## What was not done, and must not be claimed

**No escape test was run.** ADR-017 §5 says no new execution power ships without
one, and `src/sandbox/policy.py` opens with *"un bac à sable est une affirmation
tant que personne n'a essayé de s'en échapper."*

Everything above about OpenClaw's sandbox is **what OpenClaw says about
OpenClaw**. It is unusually candid — it names its own gaps — but candour is not
verification. If O12 approves anything, ADR-017 §5 applies unchanged: the escape
test ships with the adapter, or the adapter does not ship.

---

## What O03 hands to the volets that follow

1. **A four-tool allowlist, derived from the existing capability table**, and
   the reason it is narrower than the MCP one. → O11.
2. **A permission arrangement**: allowlist narrows the request, `authorize()`
   decides the call. → O11.
3. **A named infrastructure blocker**: the isolation §8 requires needs
   privileges the platform does not have. → O12, gate 5 (*can it be
   sandboxed?*).
4. **An untested claim, labelled**: OpenClaw's sandbox description is candid and
   unverified. → O12, gate 12 (*unacceptable security risks?*).
