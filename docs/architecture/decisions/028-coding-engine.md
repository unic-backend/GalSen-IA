# ADR-028: Integrate OpenHands, Aider and SWE-agent behind a native Coding Engine

## Status
Accepted

## Date
2026-08-09

## Context

GalSen IA has a `coder` agent that reads code and, since the edit-block work,
can apply changes a model proposes. What it cannot do is run a multi-step
software-engineering task: explore a repository, run the tests, react to the
failures, iterate.

Three open-source projects do exactly that, and each is strongest at a different
thing. The hypothesis handed to this work was checked against the actual
repositories rather than assumed:

| Project | Verified licence | What it actually is | Strongest at |
|---|---|---|---|
| Aider | Apache-2.0 | Python CLI, ~100k lines, own litellm model layer, own git handling | Targeted edits to named files, with a repo map for context |
| SWE-agent | MIT | Python CLI, containerised agent environment | Turning a problem statement into a repository-level fix |
| OpenHands | MIT | `OpenHands/OpenHands` is now a **TypeScript** app (agent-canvas); the working engine is `ghcr.io/openhands/agent-server`, a Python service with a REST API | Autonomous end-to-end implementation with shell and tests |

Two findings changed the design.

**OpenHands is no longer a Python program you import.** Its repository is
TypeScript; the agent that does the work runs as a container exposing
`/health`, `/api/conversations`, `/api/conversations/{id}/run` and
`/api/conversations/{id}/agent_final_response`. Any integration is a network
integration.

**Installing these into the platform environment breaks the platform.** This was
measured, not predicted: `pip install aider-chat` into the main environment
downgraded numpy to 1.26 to satisfy its own tree, which broke
`opencv-python-headless` and with it the Vision Intelligence Engine —
`import cv2` failed platform-wide. The environment was restored and the finding
kept.

SWE-agent's own README additionally states that `mini-SWE-agent` has superseded
it and is now recommended. That is recorded here because it dates this decision:
the adapter boundary is what makes replacing it cheap.

## Decision

**Add `src/coding_engine/`, a native GalSen IA engine. The three projects are
implementations behind its interface, never dependencies of it.**

```
Router / Agent Runtime
        │
   Coding Engine  ──── CodingEngineAdapter (the contract GalSen owns)
        │                     │
        │            ┌────────┼────────┐
        │        Aider    SWE-agent  OpenHands
        │      subprocess subprocess   HTTP
        │
   Workspace + Execution  (confinement, env filtering, bounded processes)
        │
   Model Engine (ADR-003)  ·  Approval Engine (ADR-006)  ·  Audit Engine
```

### The contract

`CodingEngineAdapter` requires three things: `check_availability()` (fast, no
side effect), `execute()` (always returns a `CodingTaskResult`, never raises),
and `capabilities` / `primary_capability`. Every result is normalised to
`CodingTaskResult` — status, engine, summary, files changed, tests, errors,
warnings, execution time, audit id, approval id, model, raw metadata.

No engine-specific structure crosses that boundary.

### Installation strategy: isolated, optional, never a dependency

Each engine is installed in its **own virtualenv**
(`scripts/install_coding_engines.sh`), and GalSen IA calls the resulting
executable. Their dependency trees never meet the platform's. OpenHands needs no
local install at all — it is a container the operator runs.

Nothing in `requirements.txt` changed. The platform runs with zero, one, two or
three engines available; `status()` reports what is missing and how to fix it,
and the router simply never selects an unavailable engine.

### Routing by capability, never by name

`CodingRouter` maps language signals — French and English — to capabilities, then
scores engines: a capability that is an engine's *speciality* weighs 3, a
capability it merely covers weighs 1, ties break on registration order so a
routing decision is reproducible. The router contains no engine name. A fourth
engine is routed by registering it.

Every decision carries its reason, the scores considered, and why each engine
was rejected.

### Model independence

The model always comes from the Model Engine. Adapters receive a `ModelSpec` and
translate it into their own convention (`ollama_chat/…` for Aider, `ollama/…`
for SWE-agent, `provider/model` for OpenHands). **An adapter given `None`
reports unavailable — it never picks a model of its own.** `ModelSpec` carries
the *name* of the key's environment variable, never the key, because it travels
through audit records.

Claude, Anthropic and Claude Code are not part of this engine or any other.
Claude Code is the tool used to build GalSen IA; it is not in its runtime. A
test enumerates forbidden imports, hosts and key variables across
`src/coding_engine/` to keep it that way.

### Security boundary

- **Confinement.** Every path is resolved, symlinks included, and refused if it
  leaves the workspace.
- **Environment filtering.** Subprocesses start from an allowlist. `GALSEN_API_KEYS`,
  `GITHUB_TOKEN` and provider keys do not reach them; only the model's address
  and key are added, explicitly.
- **Bounded execution.** Every process has a finite timeout, capped at one hour.
  On expiry the whole process **group** is killed — SIGTERM, then SIGKILL — so a
  container or server the engine spawned does not survive it.
- **Instruction inspection.** Destructive patterns (`rm -rf /`, `mkfs`,
  `dd of=/dev/…`, fork bombs, `chmod -R 777 /`, shutdown) are refused outright
  and cannot be unlocked by approval. Sensitive ones (push, publish, secrets,
  production config, recursive delete) go to the Approval Engine.
- **Container policy.** `GALSEN_CODING_REQUIRE_CONTAINER=1` refuses any execution
  outside a container.

### Governance reuses what exists

The Approval Engine (ADR-006) and the Audit Engine are the platform's, unchanged.
No second queue, no second trace. `AuditEventType` gains one member, `CODING`:
filed under `tool` these executions would drown among file reads, and they are
the first thing an audit reads.

**If the Approval Engine is unavailable, a task needing approval is refused.** A
missing governance gate is not an open gate.

## Consequences

- The platform gains repository-level software engineering without owning an
  agent loop for it, and without a dependency it would have to maintain.
- Replacing an engine — SWE-agent by mini-SWE-agent, for instance — is an
  adapter, not a refactor.
- The operator now has three things to install and keep working. The failure
  mode is graceful and self-describing, but it is real operational surface.
- Live behaviour depends on programs whose flags change between versions. The
  adapters record the flags they use and where they were read; `tests -m live`
  is how a drift is caught.

## Known limitations

1. **No real isolation from a local subprocess.** `workspace.py` confines paths
   and filters the environment; it does not sandbox the process. A subprocess
   can read whatever the user running GalSen IA can read. The only real
   isolation is a container — hence the container policy, and hence OpenHands's
   HTTP-plus-container shape being the safest of the three.
2. **OpenHands conversation schema.** The body of `POST /api/conversations`
   follows the published example, but the server's schema evolves with its
   versions. The adapter sends the minimal documented body and **surfaces a 422's
   detail verbatim** rather than claiming success. It has been exercised against
   a local server speaking those paths, not against a running agent-server.
3. **SWE-agent needs Docker**, and reports that separately from "not installed"
   because the two call for different actions. Its live path has not been run
   here: no Docker in this environment.
4. **Aider's exit code is not trustworthy.** Verified against aider 0.86.2: a run
   whose every model call failed still exits 0. The adapter reads litellm's
   error signatures from stdout and reports `unavailable`. That is inference
   from output, and a change in aider's wording would blunt it — which is why a
   success with no file changed also raises a warning.
5. **Instruction inspection is textual and coarse.** It catches the obvious
   catastrophe and the obvious escape. It is not semantic analysis, and it is
   the outer layer, not the guarantee. The guarantee is confinement.

## Alternatives considered

**Vendor the three projects.** Rejected. Roughly 200k lines of code we do not
develop, each carrying its own model layer, agent loop and configuration — three
parallel architectures beside the ones ADR-003 and the overview define, and a
fork to maintain for each.

**Install them as dependencies of the platform.** Rejected on evidence: it broke
the Vision Engine within one command. Isolated environments cost a script;
a broken platform costs a session.

**Import the OpenHands SDK as a library.** Rejected. It would add a large Python
tree to serve a REST client, and it would not give the container isolation that
is the main reason to prefer OpenHands for autonomous work.

**One adapter with a mode switch.** Rejected. The three engines take different
inputs, use different transports and fail differently; folding them together
would erase exactly the capability differences the router needs.

## Notes

Licences verified from each repository's licence file on 2026-08-09: Aider
Apache-2.0; SWE-agent MIT (2024 John Yang, Carlos E. Jimenez, Alexander Wettig,
Shunyu Yao, Karthik Narasimhan, Ofir Press); OpenHands MIT (2025 OpenHands
contributors). **No source code from any of the three is present in this
repository**, so no redistribution obligation is triggered; the notices in
`third_party/` exist for traceability. Full statements per project:
`third_party/aider/NOTICE.md`, `third_party/swe_agent/NOTICE.md`,
`third_party/openhands/NOTICE.md`.
