# Coding Engine — integration guide

How GalSen IA performs repository-level software engineering, and how to operate
it. The decision and its reasoning are in
`docs/architecture/decisions/012-coding-engine.md`; this page is the operator's
and integrator's view.

**Claude Code is not part of the GalSen IA runtime.** It is the development tool
used to build this project. GalSen IA is model-provider agnostic: every model
comes from the Model Engine (ADR-003), whatever provider is configured.

---

## Shape

```
Router / Agent Runtime / API
            │
     CodingEngineManager          ← governance lives here, not in the engines
            │
     CodingRouter (capabilities)
            │
     CodingEngineAdapter          ← the contract GalSen IA owns
       ├── AiderAdapter        subprocess   targeted edits
       ├── SweAgentAdapter     subprocess   issue resolution
       └── OpenHandsAdapter    HTTP         autonomous implementation
            │
     workspace.py + execution.py  ← confinement, env filtering, bounded processes
            │
     Model Engine · Approval Engine · Audit Engine · Storage
```

| File | Role |
|---|---|
| `src/coding_engine/types.py` | `CodingTask`, `CodingTaskResult`, capabilities, `ModelSpec` |
| `src/coding_engine/interfaces.py` | `CodingEngineAdapter` — the only thing the platform depends on |
| `src/coding_engine/manager.py` | Order of operations: confine → policy → approval → route → model → execute → audit |
| `src/coding_engine/router.py` | Capability scoring; contains no engine name |
| `src/coding_engine/workspace.py` | Path confinement, environment allowlist, change detection |
| `src/coding_engine/execution.py` | Bounded subprocesses, process-group cleanup, output truncation |
| `src/coding_engine/adapters/` | One adapter per external engine |

---

## Installing the engines

None of them is required. The platform runs with zero engines available and says
so; each missing engine reports how to fix it.

```bash
scripts/install_coding_engines.sh              # aider + swe_agent, isolated venvs
scripts/install_coding_engines.sh aider        # just one
```

Each engine gets its own virtualenv under `/opt/galsen-engines` (override with
`GALSEN_ENGINES_ROOT`). This is not tidiness: installing `aider-chat` into the
platform environment downgraded numpy and broke the Vision Engine. Measured, not
predicted — see ADR-028.

OpenHands has no local install; it is a container:

```bash
docker run -d -p 8010:8000 ghcr.io/openhands/agent-server:latest-python
export GALSEN_OPENHANDS_URL=http://localhost:8010
```

### Configuration

| Variable | Effect |
|---|---|
| `GALSEN_AIDER_BIN` | Path to the `aider` executable |
| `GALSEN_SWE_AGENT_BIN` | Path to the `sweagent` executable |
| `GALSEN_OPENHANDS_URL` | Agent server address |
| `GALSEN_OPENHANDS_API_KEY` | Session key, if the server requires one |
| `GALSEN_CODING_ENGINES` | Restrict and order the engines, e.g. `aider,openhands` |
| `GALSEN_CODING_REQUIRE_CONTAINER` | `1` refuses any execution outside a container |
| `GALSEN_ENGINES_ROOT` | Where the install script puts the virtualenvs |

---

## Using it

```
GET  /coding/engines     which engines can work, and why the others cannot
POST /coding/task        run a task
```

Both require `tool:execute`. The task is attributed to the authenticated
subject, never to an id supplied in the request body.

```python
from src.integration.engine_registry import get_shared_registry
from src.coding_engine import CodingTask

moteur = get_shared_registry().get("coding")
resultat = moteur.execute(CodingTask(
    instruction="Corrige le bogue de pagination dans le service de recherche",
    workspace="/srv/projets/galsen",
    timeout_seconds=600,
))
print(resultat.status.value, [f.path for f in resultat.files_changed])
```

HTTP status follows the outcome rather than being a uniform 200 — 503
unavailable, 403 rejected, 202 awaiting approval, 504 timeout, 422 failure. A
503 returned as 200 would make an absence of work look like a result.

---

## Routing

The router maps language signals to capabilities, then scores engines. A
speciality weighs 3, a covered capability weighs 1, ties break on registration
order. Both French and English are recognised.

| Request | Capability inferred | Engine |
|---|---|---|
| "Corrige ce bug et enquête dans le dépôt" | `issue_resolution` | SWE-agent |
| "Modifie ces fichiers selon mes instructions" | `targeted_edit` | Aider |
| "Implémente cette fonctionnalité, lance les tests, itère" | `autonomous_implementation` | OpenHands |

Pass `engine_id` to override. An imposed engine that is unavailable returns
unavailable — it never silently falls back, because another engine is not what
was asked for.

Adding a fourth engine: implement `CodingEngineAdapter`, declare its
capabilities and speciality, call `manager.register(...)`. Nothing in the router
changes.

---

## Security

| Guard | What it does |
|---|---|
| Confinement | Paths resolved, symlinks included; anything outside the workspace is refused |
| Environment allowlist | Subprocesses never see `GALSEN_API_KEYS`, `GITHUB_TOKEN` or provider keys |
| Bounded execution | Finite timeout, capped at one hour; on expiry the process **group** is killed |
| Destructive refusal | `rm -rf /`, `mkfs`, `dd of=/dev/…`, fork bombs, `chmod -R 777 /`, shutdown — refused, not approvable |
| Approval gate | Push, publish, secrets, production config, recursive delete → Approval Engine |
| Container policy | `GALSEN_CODING_REQUIRE_CONTAINER=1` refuses execution outside a container |
| Key handling | Keys travel by environment, never on a command line; `ModelSpec` carries only the variable's *name* |

**What this does not do:** it does not sandbox a local subprocess. A subprocess
can read what the user running GalSen IA can read. The only real isolation is a
container — which is why OpenHands's shape is the safest of the three, and why
the container policy exists.

---

## Governance

Approvals use the existing Approval Engine (ADR-006); audit uses the existing
Audit Engine. No second queue, no second trace.

A task needing approval returns `requires_approval` with an
`approval_request_id`, and nothing runs. After a human approves, resubmit the
same task with that id in `approval_request_id`. If the Approval Engine is
unavailable, the task is **refused** — a missing gate is not an open gate.

Every execution, including refusals, is recorded as an `AuditEvent` of type
`coding`: task, engine, routing decision and its reasons, files changed, tests,
errors, approval id, model. No secret enters the trace — `ModelSpec` holds only
a variable name, and process metadata holds only the executable's name, never
its arguments.

---

## Testing

```bash
pytest tests/test_coding_engine.py tests/test_coding_adapters.py   # deterministic
pytest -m live                                                     # real programs
```

The ordinary suite never talks to a model, a real engine or the network, and no
test can hang: every process call has a finite timeout, and a zero or negative
one is refused outright. Live tests are excluded by default (`pytest.ini`) and
skip themselves with the engine's own reason when it is not installed.

Subprocess adapters are tested against a **fake executable** that records its
argv and environment, so the command actually built is verified rather than
assumed. OpenHands is tested against a real local HTTP server speaking its
agent-server paths.

---

## Known limitations

They are listed in full in ADR-028, section *Known limitations*. The two that
matter most day to day:

- **Aider's exit code is not trustworthy** — verified against 0.86.2, a run whose
  every model call failed still exits 0. The adapter reads litellm error
  signatures from stdout; a wording change upstream would blunt that, so a
  success with no file changed also raises a warning.
- **OpenHands's conversation schema evolves.** The adapter sends the minimal
  documented body and surfaces a 422's detail verbatim rather than claiming
  success. It has been exercised against a local server speaking those paths,
  not against a running agent-server.
