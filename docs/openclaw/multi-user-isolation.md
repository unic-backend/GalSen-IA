# O04 — Multi-user isolation (§9)

**Built**: 2026-08-19. GalSen IA facts are VERIFIED FROM REPOSITORY with paths;
OpenClaw facts are VERIFIED FROM OFFICIAL SOURCE, quoted from
`docs/gateway/multi-tenant-hosting.md` read 2026-08-19 (O01).

§9 calls itself critical and gives the exact shape to evaluate:

```
USER A → GALSEN-IA → OpenClaw instance/session
USER B → GALSEN-IA → OpenClaw instance/session
```

This phase answers it, and the answer is a fork where **both branches are
blocked** — for different reasons, both measured.

---

## 1. How GalSen IA isolates users today

Not an intention; a set of mechanisms with paths.

| §9's list | Where it is scoped | Class |
|---|---|---|
| **Identity** | ADR-010 — *"a key belongs to a subject"*; `RBACContext.subject`; the context carries the key's **fingerprint, never the key** | VERIFIED FROM REPOSITORY |
| **Memory** | `MemoryItem.user_id` — *"Identifier of the user this memory belongs to (for isolation)"*; `sqlite_store.py` indexes `idx_memories_user_id` and filters `WHERE user_id = ?` | VERIFIED FROM REPOSITORY |
| **Jobs** | `CreativeJob.user`, refused when empty — *"un artefact sans demandeur ne peut…"* | VERIFIED FROM REPOSITORY |
| **References / consent** | `ConsentScope.subject`; `live_context/memory.py` refuses a write whose consent names somebody else | VERIFIED FROM REPOSITORY |
| **Learner data** | `darra_j/access.require_own()` and `require_declared_link()` — permission **and** a declared link | VERIFIED FROM REPOSITORY |
| **Credentials** | never in a context; `src/sandbox/policy.py` passes only `PATH, LANG, LC_ALL, TZ, HOME, TMPDIR` to a child | VERIFIED FROM REPOSITORY |
| **Every tool call** | `authorize(tool_id, actor)` — role ceiling, effect ceiling, data-scope ceiling, `REQUIRES_APPROVAL` | VERIFIED FROM REPOSITORY |

**The shape**: **one process, many subjects, authorisation checked per call.**
Isolation is a property of every request, not of the deployment.

**Two gaps this phase found and will not hide.**

- **`ApprovalRequest` carries `agent_id`, not a subject.** An approval is
  attributed to the agent that asked, not to the person on whose behalf it was
  asked. Internal to GalSen IA, unrelated to OpenClaw, and recorded here because
  §9 made me look.
- **Revocation state lives in process memory.** `src/api/instance_lock.py`
  states it: rate counters and *"la liste de révocation des clés"* are
  in-process, so *"une clé compromise révoquée sur une instance continue
  d'ouvrir les autres."* The platform's answer is to **forbid a second
  instance** — an exclusive lock on the data directory at startup.

That second one matters for this programme far more than it looks. It is
already a statement that **GalSen IA does not horizontally scale by running
several of itself**, and any design that runs several OpenClaws next to it
inherits the question.

---

## 2. How OpenClaw isolates tenants

All VERIFIED FROM OFFICIAL SOURCE:

**What exists** — per-tenant *cells*: *"a full Gateway in a hardened container
with its own state, credentials, workspace, channel accounts, token, and
loopback-only host port"*, with dropped Linux capabilities, `no-new-privileges`,
PID/memory/CPU limits, separate mounts, per-cell networks.

**What does not**, in the document's own words:

- *"Session IDs select routing; they do not authorize one tenant against
  another."*
- *"The Fleet operator and the host are trusted by every tenant. Resistance to a
  compromised host is a non-goal."*
- *"Do not co-locate hostile tenants in one OpenClaw process or OS user."*
- Fleet is *"experimental: its commands, flags, and container profile can change
  between releases without a deprecation window."*

**The shape**: **one container per tenant, no authorisation between tenants.**
Isolation is a property of the deployment, not of the request.

---

## 3. The two shapes do not compose, and §9's fork proves it

Only two arrangements are possible. Both are blocked.

### Branch A — one shared OpenClaw for all users

User A and User B reach the same Gateway, distinguished by session ID.

**Blocked by the source's own sentence**: *"Session IDs select routing; they do
not authorize one tenant against another."* A session identifier that routes but
does not authorise is precisely the failure §9 exists to prevent — it is a
lookup key, not a permission.

And the document's operational instruction is unambiguous: *"Do not co-locate
hostile tenants in one OpenClaw process or OS user."* A multi-user platform
cannot promise its users are not hostile to each other; that promise is the
thing a platform is supposed to remove the need for.

`INFERENCE`: GalSen IA's per-call `authorize()` would still guard the **four
allowlisted tools** (O03), because those calls come back through GalSen IA. But
anything OpenClaw holds *itself* — session state, transcripts, workspace files,
channel accounts — sits behind a routing key rather than an authorisation check.
GalSen IA cannot enforce what it does not mediate.

### Branch B — one OpenClaw container per user

Each user gets a cell. This is the arrangement OpenClaw itself recommends.

**Blocked by O03's measured finding**: creating that boundary needs container
privileges the platform does not have — `src/sandbox/policy.py`'s own
`NON_GARANTI` records that namespaces and cgroups are *"des privilèges que la
plateforme n'a pas"*, and the `docker` tool is declared **disabled** because the
obvious implementation hands out host root (ADR-017).

Two further costs, measured rather than estimated:

- **Fleet is experimental**, and can change *"without a deprecation window"*. A
  per-user isolation boundary that may change shape between releases is not a
  boundary a platform can promise its users.
- **A container per user does not scale the way a per-call check does.** GalSen
  IA today serves N subjects in one process; branch B serves N subjects in N
  containers, each a full Gateway holding its own credentials.

---

## 4. What §9 asked, answered line by line

*Ensure User A cannot access User B's…* — `unless explicitly authorized`.

| Asset | Under GalSen IA alone | Under branch A | Under branch B |
|---|---|---|---|
| files | scoped by declared roots + per-call authorise | **not mediated** by GalSen IA | per-cell mount |
| references | `ConsentScope.subject` | **not mediated** | per-cell |
| memory | `MemoryItem.user_id`, filtered in SQL | **not mediated** — OpenClaw persists its own turns | per-cell |
| credentials | never passed to a child process | Gateway holds its own, **unsandboxed** | per-cell, host trusted |
| jobs | `CreativeJob.user`, refused when empty | `runId` is an identifier, not an owner | per-cell |
| conversations | not applicable today — no conversational channel exists | session ID routes, does not authorise | per-cell |
| generated assets | owned by the requesting subject | **not mediated** | per-cell |

**Branch A fails seven of seven** on the mediation question, because the assets
live inside a system whose own documentation says session IDs do not authorise.
**Branch B passes all seven** and is blocked on infrastructure the platform does
not have, plus an experimental status.

---

## 5. What O04 concludes, and what it refuses to conclude

**Concludes**: §9's requirement is **not satisfiable today by either
arrangement**. Branch A is refused on the source's own evidence; branch B is
blocked on privileges O03 already measured as absent.

**Refuses to conclude** that this settles the programme. §19 has twelve gates
and this is gate 6. A subsystem can be worth having for a **single-user
deployment** — which is what OpenClaw's own description implies, *"Your own
personal AI assistant"* — and GalSen IA is not multi-user in production today.
Whether that is an acceptable scoping is O12's call and the owner's, not this
phase's.

**Records for O12, gate 6**: multi-user isolation is `NO` for branch A and
`BLOCKED — requires container privileges` for branch B.

**Records for `pending-work`, unrelated to OpenClaw**: `ApprovalRequest` has no
subject field, and revocation state is in-process. Both are GalSen IA's own, and
both were found by taking §9 seriously rather than by looking for them.
