# Writing a connector for GalSen IA

A connector reaches an outside provider — a mailbox, a drive, a calendar — on
someone's behalf. It is not a plugin, and the differences matter more than the
similarities.

This page is written from `src/connectors/sdk.py`, and a test confronts the two.
A rule added to the code and forgotten here **fails the suite** rather than being
discovered by the author it refuses.

Contract version: **1.0**

## A connector is not a plugin

| | Plugin | Connector |
|---|---|---|
| Where it runs | In the sandbox (`src/sandbox/`) | **In the process** — there is no sandbox for it |
| What it declares | Capabilities (effect, scope) | A **data contract**, retention included |
| Who it acts for | Nobody in particular | Often a **named person**, and it is bound to them |

Claiming a connector is sandboxed would be the dangerous lie. It is not. That is
why its contract is stricter about what it may touch.

## What a connector declares

```python
class MyConnector:
    data_contract = DataContract(
        data_scope=DataScope.USER_PRIVATE,   # public | user_private | system
        per_subject=True,                     # acts for a named person
        effects=frozenset({Effect.READ}),     # read | write | external
        retention="nothing",                  # in plain words
        rationale="Why this contract is this one.",
    )
```

`retention` is the field people skip. "nothing" is a valid answer and the best
one; silence is not an answer.

## Privileges

Four values, deliberately coarse: `read`, `write`, `delete`, `administer`. This
is the platform's vocabulary, not a provider's scope list — it has to still make
sense when a second provider arrives.

`delete` and `administer` are **destructive** and are never granted by default.
`administer` is destructive by reach even without deleting anything: it touches
people who granted nothing.

## Lifecycle

`not_configured` → `not_authorized` → `authorized` → `expired` / `revoked`

A connector bound to a person reaches nothing unless an authorisation exists,
has not expired, and belongs to **them**. Those are three distinct situations,
and none of them authorises the call.

## What will refuse you

| Rule | Refuses | Why |
|---|---|---|
| `contract_required` | A connector registered without a `data_contract` | Without one, nobody knows what it touches or keeps, and the registry cannot assign an owner to what it returns. |
| `retention_declared` | A contract with no plain-language `retention` | "nothing" is valid and best; silence is not an answer. |
| `private_needs_subject` | A `user_private` contract that is not `per_subject` | Private data with no owner is data whose owner will be guessed later. |
| `destructive_by_declaration` | `delete` or `administer` obtained without being asked for and justified | The project directive is explicit: no destructive permissions by default. |
| `authorisation_before_reach` | Any call by a subject-bound connector without a valid authorisation **for that person** | Absent, expired, and belonging to someone else are three situations, and none authorises the call. |
| `external_is_data` | Any provider return treated as anything but data | An email saying "ignore your instructions" is an email. It leaves through `receive()`, wrapped `EXTERNAL`, or it does not leave. |

## What this platform does not do

- **It does not fabricate a credential, and does not bypass authentication.**
- **It does not sandbox a connector.** It runs in the process.
- **It does not guess an owner.** The owner is *derived* from the declared
  scope, and a private scope with no subject refuses.
