# O08 — Provenance (§13) and observability (§14)

**Built**: 2026-08-19. GalSen IA facts VERIFIED FROM REPOSITORY with paths;
OpenClaw facts VERIFIED FROM OFFICIAL SOURCE, `docs/gateway/audit.md` read
today.

O02 left observability `UNKNOWN` and assigned it here. This phase closes it.

---

## 1. §13's twelve fields, mapped to both sides

§13 requires every OpenClaw execution be traceable, and lists what to record.

| §13 requires | GalSen IA | OpenClaw's audit ledger |
|---|---|---|
| user | `RBACContext.subject` (ADR-010); `AuditEvent.agent_id` | `actor`, plus *"represented subject and sponsor"* in execution-identity contexts |
| task ID | `request_id`, and it **survives boundaries** — a routine turn's `correlation_id` becomes the workflow's `request_id` and its audit events' | *"a stable event id, a monotonic owner sequence"* |
| OpenClaw version | n/a | *"agent definition, and runtime instance"* |
| model / provider | `AuditEvent.model_id` | **not stated** |
| skill / tool | `AuditEventType.TOOL`, `action` | `tool.action.started` / `finished` |
| **input** | `AuditEvent.user_request` | **never stored** — *"does not store prompts, message bodies, tool arguments…"* |
| permissions | `ToolDecision` with role, effect, scope, reason | *"applicable grants and assurance evidence"* |
| execution time | `execution_time_seconds` | *"a lifecycle timestamp"* |
| **output** | `detail`, `metadata` | **never stored** — *"tool results, attachments, filenames, URLs, command output"* |
| **errors** | `AuditStatus` + `detail` | **normalized outcome codes only**; *"raw error text"* excluded |
| generated artifacts | job stores, owned by subject | **not stated** |
| hashes | `key_fingerprint`; `Observation` fingerprints | *"installation-local keyed pseudonyms (`hmac-sha256:v1:<keyId>:<digest>`)"* |

**Eight of twelve are covered on both sides. Three are covered only by GalSen
IA — input, output, errors — and one only by OpenClaw: its own version.**

## 2. The asymmetry, and why it is a feature on both sides

OpenClaw's ledger is deliberately **metadata-only**: `redaction:
"metadata_only"`, and contexts *"never contain prompt or message text, command
bodies, arguments, paths, credentials, environment values, or arbitrary plugin
payloads."*

That is a good decision for a gateway that sits on WhatsApp and Signal. It is
also **exactly what §13 asks to be recorded** — input, output, errors — for an
execution GalSen IA is accountable for.

`INFERENCE`, and it resolves rather than creates a problem: **the two ledgers
answer different questions and must not be merged.** OpenClaw's says *an action
of this shape happened, by this actor, with this outcome code.* GalSen IA's says
*this request, with this content, produced this result.*

§13's instruction — *"Do not create a conflicting provenance system"* — is
therefore satisfied by **not writing one**, and by making the boundary explicit:

> **GalSen IA's `AuditEvent` is the record of the execution. OpenClaw's ledger
> is the record of the gateway's own lifecycle. The adapter writes the first and
> reads the second; it never merges them, and it never treats an OpenClaw event
> id as a `request_id`.**

The mechanism to make that hold already exists: `request_id` **survives
boundaries** by design (`observability/trail.py`, VOLET 66.1). The adapter
creates the `AuditEvent` with GalSen IA's `request_id` **before** calling
OpenClaw, and carries that identifier into the call. The trail then answers *what
happened to this one job?* across the boundary, which is the question the trail
module was written for.

## 3. What the adapter must record that neither side records today

`model / provider` is **not stated** in OpenClaw's audit, and `AuditEvent.model_id`
is filled by GalSen IA's own model path.

O06 established that the only viable arrangement points OpenClaw at GalSen IA's
OpenAI-compatible endpoint. **That arrangement is what makes `model_id`
recordable at all** — the inference comes back through `ModelRouter`, so the
provider is known on our side. Under the rejected arrangement, where OpenClaw
holds its own keys, `model_id` would be `UNKNOWN` for every call and §13's field
would be permanently unfillable.

`INFERENCE`: §13 and §10 point at the same conclusion from different directions,
and neither was written knowing about the other. That is a reason to weigh it.

## 4. §14 — controlled telemetry

§14 asks for execution status, latency, failures, retries, tool calls, resource
usage, sandbox events and provider failures, and adds: *"Do not expose sensitive
internal information to normal users."*

**GalSen IA already holds the second half harder than the first.**
`src/security/redaction.py` is the single list of names whose value is never
written down, and its reasoning is the operational one:

> *"A token that reaches a log file has left the platform. Log files are copied,
> shipped to an aggregator, pasted into a bug report, and read by people who were
> never granted the access that token carries — and unlike a database row, nobody
> ever goes back and deletes a line from last month's log."*

And its design rule — **names, not values**: *"Nothing here tries to recognise a
secret in a string"*. A redactor that guesses is a redactor that misses.

| §14 asks for | Where |
|---|---|
| execution status | `AuditStatus` — seven values including `REQUIRES_APPROVAL` and `UNAVAILABLE` |
| latency | `execution_time_seconds`; `src/api/tracing.py` sums measured durations |
| failures | `AuditStatus.FAILURE`, `PARTIAL_SUCCESS` |
| retries | `router/retry_manager.py`, `model_engine/retry_manager.py` |
| tool calls | `AuditEventType.TOOL` |
| resource usage | `src/api/metrics.py` |
| sandbox events | `SandboxPolicy` outcomes; `NON_GARANTI` reported alongside |
| provider failures | `model_engine/health_monitor.py` |
| **not exposing secrets** | `src/security/redaction.py` — one list, names not values |

**Nothing new is required for §14.** The adapter emits into the existing
surfaces; a second telemetry path would be the *"conflicting system"* §13
forbids, arriving through the observability door instead.

`UNKNOWN`, recorded rather than assumed: OpenClaw's `opentelemetry.md`,
`prometheus.md` and `logging.md` exist in `docs/gateway/` and were **not read**.
Whether its telemetry can be scraped into ours, or must be discarded, is not
settled. It does not block the design above, because that design does not depend
on OpenClaw's telemetry — it depends on GalSen IA recording its own call.

## 5. One thing OpenClaw does that this repository does not

*"Platform identifiers are exported only as installation-local keyed pseudonyms
(`hmac-sha256:v1:<keyId>:<digest>`)"* — so an identifier leaving one
installation cannot be correlated with the same identifier from another.

GalSen IA has `key_fingerprint` for the same purpose at one point
(`RBACContext` carries the fingerprint, never the key), but does not apply keyed
pseudonymisation across exported identifiers generally.

**`OPTIONAL SUGGESTION — NOT IMPLEMENTED`**: installation-keyed pseudonyms for
exported identifiers. It is a genuine idea, it belongs to the audit layer rather
than to this programme, and recording it here is the whole of the action taken —
`.claude/rules/spec-driven-governance.md` calls anything more scope expansion.

## 6. What O08 concludes

- **§13 is satisfiable, and by writing nothing new.** The boundary is: our
  `AuditEvent` records the execution, their ledger records their lifecycle, the
  `request_id` crosses, and the two are never merged.
- **§14 needs no new component.** Every field it lists already has a home, and
  the redaction rule that matters is already the stricter one.
- **One dependency**: `model_id` is only recordable under O06's viable
  arrangement. Two sections of the directive, written independently, exclude the
  same option.
- **One `UNKNOWN` left open**: OpenClaw's OTel/Prometheus/logging documents were
  not read. It does not gate the design and is recorded rather than smoothed
  over.
