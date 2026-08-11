# Notifications

What VOLET_13 asks of the Notification Engine, and what the platform actually does.
Measured against the repository on 2026-08-11.

---

## The seven components (chapter 02), against the code

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| Event Sources | any caller of `send_notification()` — API, agents, approval engine | present |
| Notification Orchestrator | `NotificationManagerImpl` (`src/services/notification/manager.py`) | present |
| Notification History | `InMemoryNotificationStore` / `SQLiteNotificationStore` | present |
| **Rules Engine** | — | **absent**: no routing rule, priority is passed by the caller |
| **Channel Connectors** | — | **absent**: one channel, the internal inbox |
| **Delivery Queue** | — | **absent**: `send_notification()` writes synchronously |
| **User Preference Manager** | — | **absent**: no per-user opt-out, no quiet hours |

Three of seven. What is missing describes multi-channel, rule-driven delivery; this
engine writes into one inbox that the recipient reads through `/notification/list`.

That single channel is not a defect to hide: creating the notification *is* the
delivery, so nothing is claimed about an e-mail or a push that never left. The
distinction with the e-mail service — which used to claim exactly that — is drawn in
`docs/architecture/communication.md`.

## The lifecycle (chapter 03), stage by stage

| Stage | State |
|-------|-------|
| 1. Event Detection | caller's responsibility |
| 2. Notification Creation | `send_notification()` |
| 3. Validation | Pydantic on the route, unknown type/priority fall back to `info`/`normal` |
| 4. Priority Assignment | caller-supplied; `list_notifications` sorts urgent first |
| 5. Channel Selection | n/a — one channel |
| 6. Delivery | stored in the recipient's inbox |
| 7. Acknowledgement | `mark_read`, `mark_all_read` |
| 8. Archival | the store *is* the history |
| 9. **Retention and Secure Deletion** | **added by this VOLET** — see below |

Two of the chapter's five quality controls were missing, and both were found by
measurement rather than by reading:

### Duplicate prevention

Sending the same alert five times produced five notifications:

```
5 envois identiques → 5 entrées, 5 identifiants
```

A "disk full" alert repeating every minute buried the recipient's inbox — that is, it
buried *the notifications they had not yet read*. The manual lists duplicate prevention
among its quality controls for exactly this reason.

Now, an identical notification that is **unread** and inside a configurable window is
not duplicated: its `metadata["occurrences"]` is incremented, `last_occurrence_at` is
stamped, and the **same identifier** is returned.

Three boundaries were chosen deliberately:

- **`created_at` never moves.** It says when the problem started, which is more useful
  than watching it slide forward at every repetition. `last_occurrence_at` carries the
  latest.
- **A read notification is never grouped.** The recipient has seen it; a new occurrence
  is new information.
- **Identity requires type, title, message *and* recipient to match.** Two different
  incidents never merge, and two recipients each keep their own copy — grouping across
  recipients would deprive somebody of their alert.

### Retention

Nothing purged anything. An inbox grew forever, the same unbounded-log failure the
platform has already paid for once.

`purge_expired(max_age_days=None, include_unread=False)` deletes **read** notifications
older than the retention period. `include_unread` defaults to `False` on purpose:
deleting a notification nobody has seen decides on their behalf that it did not matter.
A caller who really wants that must ask for it explicitly.

Purging is a method, not a schedule — nothing calls it periodically yet. That is stated
rather than faked with a background task that would silently die.

## The bug the fix uncovered: two stores, one contract, two behaviours

Grouping first used `store.save()` to write the incremented counter back. It appeared to
work and did not:

- `InMemoryNotificationStore.save()` raises `ValueError("… existe déjà")` on a known id.
- `SQLiteNotificationStore.save()` does `INSERT OR REPLACE` — it overwrites silently.

The manager's `try/except` swallowed the exception, so in memory the mutation only landed
because the object was shared by reference; with SQLite it would have taken a different
path entirely. Two implementations of one interface, disagreeing on what `save` means.

The fix keeps `save()` meaning **create** — an existing test rightly protects the raise —
and adds an explicit `update()` to `NotificationStore` and to both implementations,
returning `False` when the notification is gone. The manager treats that `False` as "do
not count into the void" and returns `None`.

Verified against both backends, not just the default one.

## The second manual (VOLET 17)

`VOLET_17.md` is a **second Notification Engine manual**, despite its folder being named
"Agent Framework Engine". It restates most of VOLET 13 and asks three things that one did
not. Only those three were treated; re-measuring the rest would have produced a duplicate
of the sections above.

### Template Manager — was absent, now exists

Chapter 02 names a Template Manager among its components and chapter 04 makes template
management a domain of its own. Nothing of the sort existed: every caller composed title
and message by hand, so the same event announced itself differently depending on which
part of the code reported it — and deduplication, which compares exact strings, could not
bring those variants together.

`src/services/notification/templates.py` adds a registry and
`send_from_template(name, values, …)`. Three decisions inside it:

- **A missing parameter sends nothing.** "Le disque {nom} est plein" looks like a real
  alert and says nothing; failing is better than delivering a message with holes.
- **The registry ships empty.** Providing ready-made templates would fabricate messages
  nobody asked for. Callers register their own.
- **Values are text, never re-interpreted.** Substitution goes through `string.Template`,
  not `str.format`: the latter accepts `{a.__class__}` and `{a[0]}`, which on a template
  read from configuration hands out attribute access on whatever objects were passed.

### Delivery analytics — three of the manual's metrics do not apply

Chapters 06 and 09 both ask for a delivery success rate, a queue latency and a count of
failed deliveries. None of the three means anything here, and returning them anyway would
return flattering numbers: the channel is an internal inbox, creating the notification
*is* the delivery, there is no queue and nothing can fail. A "100 % delivery rate" would
measure only that tautology.

`delivery_report()` measures what actually happens **after** delivery, which is where the
real risk lives — a notification delivered and never read has accomplished nothing:

| Measure | What it tells |
|---------|---------------|
| `acknowledgement_rate` | share that a human actually opened |
| `oldest_unread_seconds` | the signal that an inbox is no longer being read |
| `most_repeated` | the incidents that keep coming back — only measurable because grouping exists |
| `unavailable` | the three metrics above, named with why they do not apply |

`GET /notification/stats` now serves it alongside the counts by type and priority.

### Retry, and why there is none

Chapter 03's management practices include "retry failed deliveries". There is nothing to
retry: a send either lands in the store or raises, and the store is local. Retries become
meaningful the day an external channel exists — the e-mail service is where delivery can
genuinely fail, and it is measured there (`docs/architecture/communication.md`).

### Governance and compliance (chapters 05, 07, 08, 10)

Security and compliance restate what already applies: ownership per recipient (ADR-010),
RBAC on every route, retention with a configurable period, and no personal data beyond the
recipient identifier. Chapter 08 and chapter 10 assign work to a Notification Governance
Board and an operations team — bodies this project does not have. Recording a review
cadence nobody performs would be the same fabrication as an invented delivery rate.

## Configuration

| Variable | Default | Effect |
|----------|---------|--------|
| `GALSEN_NOTIFICATION_DEDUP_SECONDS` | 300 | grouping window |
| `GALSEN_NOTIFICATION_RETENTION_DAYS` | 90 | age at which a *read* notification may be purged |

Both are validated by `src/config/environment.py`: an unreadable or non-positive value
falls back to the default and is reported at startup, never guessed.

## Access control

`/notification/send` requires `MEMORY_WRITE`, `/notification/stats` requires
`MEMORY_READ`. Reading, acknowledging and deleting are bounded by ownership (ADR-010,
exit criterion C2): a caller only sees notifications addressed to them, and a
`mark-read` or `DELETE` on someone else's notification answers 404 — not 403, which
would confirm that it exists.

## What is still missing

- **No queue, no retry**: a send is synchronous and either lands in the store or fails.
- **No rules engine**: nothing decides *who* should receive an event; the caller does.
- **No channels**: no push, no SMS, no e-mail bridge. Only the internal inbox.
- **No user preferences**: a recipient cannot mute a source or set quiet hours.
- **No scheduled purge**: `purge_expired()` exists and must be called.

None of these got a placeholder. The engine reports what it does: one channel, one
inbox, deduplicated, with a retention policy that an operator has to run.
