# ADR-023: Adopt the OpenGAP format by implementing the specification, not by vendoring the code

## Status
Accepted

## Date
2026-08-09

## Context

GalSen IA declares its nine agents in `agents/registry.yaml`, a format invented
here. It works, and it is understood by exactly one program: this one. An agent
written for GalSen IA cannot be run by Claude Code, CrewAI or LangChain, and an
agent published for those cannot be described here.

OpenGAP (`https://github.com/open-gitagent/opengap`) is a git-native, framework
agnostic format for defining agents. An agent is a directory holding
`agent.yaml` (the manifest) and `SOUL.md` (the identity). Both are text, both
are versioned with the code, and the format is deliberately not tied to a
runtime.

Two questions had to be answered before touching anything.

**Is the licence compatible?** Yes — MIT. It permits use, modification and
redistribution, commercial use included, and requires only that the copyright
notice be preserved. It is also irrevocable for a copy already obtained: if the
upstream repository is deleted or relicensed tomorrow, the grant on what we hold
stands.

**Should we vendor the reference implementation?** No, and this is the decision.

## Decision

**We implement the OpenGAP specification in Python. We do not copy upstream
code into this repository.**

Concretely:

| Where | What |
|---|---|
| `third_party/opengap/LICENSE` | Upstream MIT licence, verbatim, as attribution |
| `third_party/opengap/NOTICE.md` | The field reference we build against, plus the security note |
| `src/interop/opengap.py` | The Python implementation: validate, read, write |
| `scripts/export_opengap.py` | Exports `agents/registry.yaml` to the format |
| `interop/opengap/<agent>/` | The nine agents plus the router, exported and versioned |
| `tests/test_opengap.py` | 48 tests, including a drift test against the registry |

Three rules govern the layer.

**Reading a foreign agent has no effect.** YAML is parsed with
`yaml.safe_load`, so a manifest cannot construct Python objects. `hooks/`,
`tools/` and any other executable content in an imported directory are neither
run nor imported. `extends` and `dependencies` are not fetched — reading a
manifest never reaches the network. A `name` that is not kebab-case is rejected
before it is used to build a path, so a crafted name cannot write outside its
destination.

**An imported agent is data.** Running one under GalSen IA still requires a
Python class bound to it in `agents/registry.yaml`, written by a human. The
format describes an agent; it does not authorise one.

**Nothing is lost in transit.** Sections we do not interpret — `compliance`,
`a2a`, `runtime`, `delegation`, `extends`, `dependencies` — are preserved
verbatim on read and written back unchanged. Dropping them would corrupt work
authored elsewhere.

## Consequences

- The nine agents are portable. Any tool that reads OpenGAP can load them
  without knowing this project exists.
- Agents published by others can be validated and described here, under a
  licence review, without adopting their runtime.
- The platform gains no new dependency. No Node, no npm, no upstream package.
  If the upstream repository disappears, nothing here stops working — that was
  the requirement that shaped this decision.
- We carry the cost of tracking the specification ourselves. `spec_version` in
  `src/interop/opengap.py` records what we implement; moving to a later spec
  version is a deliberate change with its own tests.
- `interop/opengap/` is committed, not generated at build time. It can drift
  from `agents/registry.yaml`, so `tests/test_opengap.py` re-exports into a
  temporary directory and fails on any difference.

## Alternatives considered

**Vendor the TypeScript CLI.** Rejected. ADR-001 fixes Python as the
implementation language; this would put Node in the runtime path of a Python
platform in order to read two text files. It would also freeze a copy of code we
would then have to maintain without upstream's tests.

**Depend on the upstream npm package.** Rejected for the reason the user raised
directly: a dependency disappears when its repository does. A specification
copied into `third_party/` does not.

**Keep `agents/registry.yaml` as the only format.** Rejected. It is the reason
the agents are locked to this platform, and it is the thing OpenGAP fixes. The
registry stays — it is what the runtime dispatches on — and the export is
derived from it.

## Notes

Upstream copyright: 2025 Shreyas Kapale / Lyzr AI. Specification version
implemented: 0.1.0. Retrieved 2026-08-09.

The full field reference, including the optional sections we preserve without
interpreting, is in `third_party/opengap/NOTICE.md`.
