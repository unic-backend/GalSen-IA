# Communication

What VOLET_12 asks for, and what the platform's channels actually deliver. Measured
against the repository on 2026-08-11.

---

## The seven components (chapter 02), against the code

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| Notification Service | `NotificationManagerImpl`, 6 routes | present |
| Messaging Gateway | `EmailManagerImpl` + `EmailTransport` | present |
| Channel Adapter Layer | `SmtpTransport`, `ConsoleTransport`, `NoopTransport` | present |
| Communication Monitoring | `/notification/stats`, email `stats()` | partial |
| Governance Module | ownership via `recipient`, RBAC on every route | partial |
| **Conversation Manager** | — | **absent**: no thread, no reply chain |
| **Message Queue** | — | **absent**: every send is synchronous |

Five of seven in some form. What is missing describes asynchronous, threaded messaging;
this platform sends one message at a time, when something asks it to.

## The finding: "sent" named messages nobody received

Step 5 of the chapter's flow is *deliver securely*. Measured before this VOLET, on a
default deployment with no SMTP configured:

```
EmailSendResult(success=True, message='Email envoyé à 1 destinataire(s).', ...)
stored status: sent
```

**No server was contacted.** `NoopTransport` — the default — returned `(True, "")` with a
docstring saying it "does nothing", and its comment justified this as *"historically
equivalent"* behaviour. So a lie was preserved for compatibility: the caller was told the
message was sent, the store recorded it as `sent`, and nothing distinguished a real send
from an imaginary one.

Worse, **six tests asserted that lie** — `assert result.success`,
`assert email.status.value == "sent"`, and one named
`test_noop_transport_default_behavior` that required `(True, "")`. This is exactly what
`.claude/rules/verification.md` forbids: *a test asserting the output of something that
does not really work makes the fabrication permanent.* The rule's own example is the
calendar tool inventing meetings; this is the same failure in a different service.

### What it does now

| | Before | After |
|---|--------|-------|
| `NoopTransport.send()` | `(True, "")` | `(False, "Aucun transport e-mail configuré… renseignez GALSEN_SMTP_HOST")` |
| `send_email()` result | `success=True` | `success=False`, with `delivered: False` |
| Stored status | `sent` | `failed` |
| Stored at all? | yes | **yes** — unchanged |
| `POST /email/send` | 400 | **503** when the deployment is unconfigured, 400 when the request is wrong |

Two decisions inside that table:

- **The message is still stored.** What a user wrote must not vanish because the
  infrastructure is missing. Only the *status* changes, because the status is the part
  that was lying.
- **503, not 400.** A 400 accuses the caller of an error they did not make; the fault is
  a deployment with no SMTP. Same distinction `/search` draws when no source is wired.

The six tests were rewritten to assert the real behaviour, and a new suite covers the
delivery contract end to end — including that a transport which *does* deliver still
returns a success, so the fix cannot be mistaken for "email is now impossible".

## Notifications do not have this problem

`send_notification()` writes to an internal inbox that the recipient reads through
`/notification/list`. There is no external channel, so nothing is claimed about delivery
elsewhere: no push, no SMS, no email bridge. Creating the notification *is* the delivery.

That distinction is worth stating because the two services look alike from the outside —
one sends into the platform, the other tried to send out of it.

## What is still missing

- **No queue**: a send blocks its caller. An SMTP server that hangs hangs the request.
- **No conversation**: messages carry no thread, no reply-to, no history between two
  parties.
- **No delivery receipt**: `SmtpTransport` reports that the server accepted the message,
  which is not the same as the recipient receiving it. Nothing tracks bounces.

None of these received a placeholder. The e-mail path now reports exactly what it knows:
accepted by a transport, or not sent at all.
