# Integration

What VOLET_10 asks for, and what the connector layer does. Measured against the repository
on 2026-08-11. The decision that shapes it is ADR-007: **every external integration is a
declared connector.**

---

## The seven components (chapter 02), against the code

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| API Gateway | FastAPI, `src/api/server.py` | present |
| Integration Hub | `ConnectorRegistry` (`src/connectors/registry.py`) | present |
| Authentication Layer | `RBACManager`, per-route permissions | present |
| Monitoring Module | `/connectors/status`, and `/health` since this VOLET | present |
| Governance Module | each connector declares an owner and its variables | partial |
| **Message Broker** | — | **absent**: calls are synchronous, no queue |
| **Synchronization Service** | — | **absent**: nothing reconciles external state |

Five of seven. The two missing ones describe a platform exchanging data with systems it
does not control on a schedule; this one makes direct calls when an agent asks. That is
recorded so "Integration Engine" is not read as more than it is.

## Two connectors, both unconfigured

Measured on a default deployment:

```
email_smtp          kind=email    owner=plateforme  not_configured (GALSEN_SMTP_HOST absent)
storage_local_disk  kind=storage  owner=plateforme  not_configured (GALSEN_FILE_STORAGE_DIR absent)
```

Both are **visible while unconfigured**, which is deliberate (ADR-007): hiding them would
deprive an operator of the list of what the installation could reach once wired.

Each connector declares what it reads — the **names** of its environment variables, never
their values — so a deployment can be audited offline. `/connectors` describes without
calling anyone; `/connectors/status` contacts the remote services and needs a separate
permission. Describing is not verifying, and the two routes keep that distinction.

## `/health` ignored the integration layer

The platform had two ways to answer "what is wrong" and they did not overlap: `/health`
covered engines and storage, `/connectors/status` covered integrations. An operator had to
call both, and nothing said so.

`/health` now carries a `connectors` component. **The rule that shapes it is the opposite
of the intuition: an unconfigured connector does not degrade anything.** Most deployments
configure none; a health endpoint that turns `degraded` because SMTP is absent is red
permanently, and a permanently red indicator is an ignored indicator. Only a connector that
is **configured and failing** degrades the platform.

The component carries a `note` saying exactly that, so nobody investigates a fault that
does not exist. The check reads configuration and contacts nothing — `/connectors/status`
remains the route that reaches out.

| Situation | `connectors` status |
|-----------|---------------------|
| No connector registered | healthy |
| Connector present, unconfigured | healthy, `ready: 0` |
| Connector configured and ready | healthy, `ready: 1` |
| Connector in error or unreachable | **degraded** |

This closes the P2 backlog entry "report connector health inside `/health`".

## Integration lifecycle (chapter 03), against the code

Nine stages. What exists is the middle of the list:

| Stage | State |
|-------|-------|
| Development, Validation | connectors implement a contract; the registry refuses a duplicate id |
| Deployment | registration at API startup (`_register_builtin_connectors`) |
| Monitoring | `/connectors/status`, `/health`, latency per check |
| Documentation | `describe()` lives beside the code, so it cannot drift |
| **Versioning** | **absent**: a connector carries no version |
| **Retirement** | `unregister()` exists; nothing marks a connector deprecated |

A connector failing its check never raises into the caller: `_safe_check()` turns an
exception into a status. One broken integration cannot take down the inventory of the
others — the same principle the engine registry applies.

---

# The second manual (VOLET 24)

`VOLET_24.md` is a **second Integration Engine manual**, after VOLET 10. Its component list
overlaps VOLET 15's gateway (API Gateway, Authentication Service, Monitoring Service) and
VOLET 10's connector layer (Connector Manager). Only what it asks beyond both is treated
here.

| Component the manual names | What plays it | State |
|----------------------------|---------------|-------|
| API Gateway, Authentication Service | the FastAPI app, `require_auth` | present → `gateway.md` |
| Connector Manager | `ConnectorRegistry`, ADR-007 | present |
| Monitoring Service | `check_all()`, `/health`, `/metrics` | present |
| **Event Bus, Message Broker** | — | **absent**: every call is synchronous |
| **Transformation Engine** | — | **absent**: no payload is transformed between systems |
| **Synchronization Engine** | — | **absent**: presupposes a second instance (ADR-009) |

## The finding: two storage backends no configuration could select

Chapter 03 makes **Configuration** stage 4 and **Deployment** stage 5. Measured:
`FileSystemCloudStore` and `S3CloudStore` are implemented, exported from
`src/services/cloud/__init__.py`, and covered by `tests/test_services_cloud_fs.py` — and
`CloudManagerImpl.__init__` only ever built `InMemoryCloudStore` or `SQLiteCloudStore`.

No environment variable reached them. A deployment could not choose them; only a caller
constructing the manager with an injected store could, and nothing in the platform does.
Two working integrations, kept alive by their tests and unreachable by anyone deploying the
thing.

That is a milder version of the pattern this series keeps finding. Not a capability
claiming success it never earned — a capability that works and that nobody can turn on.

### What it does now

`GALSEN_CLOUD_BACKEND` selects `in-memory` (default), `sqlite`, `filesystem` or `s3`, and
takes precedence over `GALSEN_STORAGE_BACKEND` for this service only — `filesystem` and
`s3` are meaningless for the other stores, so forcing them through the general variable
would be wrong.

Four decisions inside that:

- **The default did not change.** Making `filesystem` the default would start writing to
  disk on deployments that never asked for it.
- **An unknown value is reported, never guessed.** Interpreting `filesytem` as `filesystem`
  would write files somewhere other than where the operator believes they are.
- **`s3` construction does not require boto3.** The client is imported lazily, so
  configuring S3 cannot break startup; an unreachable bucket fails on upload with a real
  error rather than falling back to memory — a file "stored" in RAM would be worse than the
  failure.
- **An injected store still wins.** The existing contract is unchanged.

The tests do not stop at type checks: one writes through the filesystem backend and reads
it back from a second manager, because making a store reachable without checking that it
stores would have proved nothing.

## Chapters 04 to 10

Management, security, compliance, monitoring and governance restate VOLET 10 and VOLET 15:
connectors describe themselves without ever exposing a secret value (ADR-004), `check_all()`
reports status per connector, an unconfigured connector does not degrade health, and every
route is authenticated and rate-limited. The versioning stage (03.9) is answered by ADR-011.
Chapters 08 and 10 are both titled "Integration Engine Governance" and assign work to a
board the project does not have.
