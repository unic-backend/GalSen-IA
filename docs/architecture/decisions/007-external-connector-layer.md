# ADR-007: External Connector Layer

## Status
Accepted

## Date
2026-08-06

## Context
The Architecture Manual (VOLET_02, chapter 09, *Integration Architecture*) requires
the platform to reach external systems — authentication providers, email services,
payment providers, cloud storage, calendar services — under one directive: *"Every
integration must be modular, documented and replaceable without disrupting the rest
of the platform."*

Today the platform reaches the outside world only through tools
(`src/tools/email/`, `src/tools/calendar/`, `src/tools/api/`). A tool is the right
shape for *an agent performing an action*, but it is the wrong shape for *an
integration the platform owns*, for three reasons observed in the current code:

- **No configuration state.** `EmailTool` accepts an SMTP host in its config and
  fails at call time when it is absent. Nothing can answer "is email configured on
  this deployment?" without attempting to send a message.
- **No health.** The platform's `/health` endpoint reports every engine, but an
  external dependency being unreachable is invisible until an agent tries to use it
  and fails.
- **No ownership.** Chapter 09 asks for "clear ownership of every integration".
  A tool declared in `tools/tools.yaml` has no owner, no credential contract and no
  documented failure mode.

The engines already solve this shape: an abstract contract, a concrete
implementation, a façade that never raises, and a registry that builds lazily and
reports unavailability as data. The provider layer of the Model Engine (ADR-003)
is the closest precedent: interchangeable vendors behind one contract, credentials
read from the environment (ADR-004), and unavailability expressed as a status
rather than an exception.

## Decision
Introduce an **external connector layer** in `src/connectors/`, following the
established engine shape rather than inventing a new one.

A **connector** is the platform's owner of one external system. It declares:

- an **identity**: a stable `connector_id` and a `ConnectorKind`
  (`email`, `calendar`, `storage`, `authentication`, `payment`, `other`), so the
  categories named in chapter 09 are enumerable rather than implicit;
- its **configuration state**: `is_configured()` answers from the environment
  alone, without any network call, so a deployment can be audited offline;
- its **reachability**: `check()` performs the cheapest possible verification and
  returns a `ConnectorCheck` carrying a status, never an exception;
- its **description**: `describe()` returns what the connector is, which
  environment variables it reads, and what it can do — the documentation
  requirement of chapter 09, kept next to the code so it cannot drift.

A `ConnectorRegistry` holds the registered connectors, exactly as
`ProviderRegistry` holds model providers: registration, lookup by id or kind, and
an aggregate status report suitable for `/health` and for an operator endpoint.

### Rules
- **Credentials come from the environment only** (ADR-004). A connector never
  accepts a secret in its configuration dictionary, never stores one in an
  attribute, and never writes one to a log or to a `describe()` payload.
- **A missing connector is data, not a crash.** An unconfigured or unreachable
  connector reports `NOT_CONFIGURED` or `UNREACHABLE`; the caller decides what to
  do. This mirrors the Model Engine's `unavailable` response and the
  `EngineRegistry` behaviour.
- **Connectors do not replace tools.** A tool remains the agent-facing action
  (`send an email`). A connector owns the integration itself (`is email configured,
  reachable, and who owns it`). A tool may delegate to a connector; a connector
  never depends on a tool.
- **One connector, one external system.** Supporting a second email provider means
  a second connector behind the same contract, not a branch inside the first.

## Consequences

### Positive
- Chapter 09's directive becomes verifiable: every integration is enumerable,
  describable and checkable without being exercised.
- `/health` can report external dependencies alongside internal engines.
- A deployment can be audited offline: `is_configured()` answers from the
  environment, with no traffic and no credentials exposed.
- Replacing a provider (SMTP → a transactional email API) is a new class behind an
  unchanged contract.

### Negative
- One more layer between the platform and the outside world, and a small amount of
  duplication with the existing tools until those delegate to connectors.
- Every new integration now carries an obligation: a contract implementation, a
  description and tests, rather than a direct call.

### Neutral
- The layer starts empty. This ADR introduces the contract, the types and the
  registry; each concrete connector arrives as its own change, with its own tests.

## Alternatives Considered

**Extend the tools instead.** Adding `is_configured()` and `check()` to
`BaseTool` was rejected: it would impose an integration contract on the fourteen
tools that touch nothing external (`filesystem`, `memory`, `metrics`…), and it
would leave the ownership and documentation requirements of chapter 09 unanswered.

**One `IntegrationManager` with a method per external system.** Rejected as a God
Object: adding a provider would mean editing a shared class, which contradicts
"replaceable without disrupting the rest of the platform".

**Wait for the first concrete need.** Rejected because the need already exists in
three places — email, calendar and cloud storage are all named in chapter 09 and
all three have half-implementations in `src/tools/`. Defining the contract after
three implementations would mean rewriting all three.
