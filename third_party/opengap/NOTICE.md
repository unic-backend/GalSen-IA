# OpenGAP — third-party notice and vendored specification

| | |
|---|---|
| Upstream | `https://github.com/open-gitagent/opengap` |
| Spec version implemented | `0.1.0` |
| Licence | MIT — full text in `LICENSE`, next to this file |
| Copyright | 2025 Shreyas Kapale / Lyzr AI |
| Retrieved | 2026-08-09 |
| What was taken | **The specification only.** No upstream source code is present in this repository. |

## Why no code was copied

OpenGAP's reference implementation is TypeScript. ADR-001 fixes Python as the
implementation language, so vendoring the CLI would put Node in the runtime
path of a Python platform to read two text files.

The upstream specification states that the format "is a plain specification any
language can implement". GalSen IA therefore implements the format in Python
(`src/interop/opengap.py`) and keeps this notice as the record of where the
format comes from.

The reasoning and the alternatives considered are in
`docs/architecture/decisions/011-opengap-interop.md`.

## Why this file exists

If the upstream repository disappears — deleted, renamed, relicensed, or simply
abandoned — nothing in GalSen IA stops working. Our implementation depends on
no upstream package, and the field reference below is the copy of the format we
build against. That is the whole point of vendoring a specification rather than
depending on a project.

MIT survives deletion: the grant was made at the moment the code was published
and cannot be withdrawn from a copy already obtained. Attribution is preserved
here because MIT requires it, and this file is that attribution.

## Field reference implemented by GalSen IA

An OpenGAP agent is a directory. Two files are mandatory.

### `agent.yaml` — the manifest

Required:

| Field | Type | Constraint |
|---|---|---|
| `name` | string | kebab-case, `^[a-z][a-z0-9-]*$` |
| `version` | string | semantic version, `X.Y.Z[-prerelease][+build]` |
| `description` | string | one line |

Recommended:

| Field | Type | Constraint |
|---|---|---|
| `spec_version` | string | the spec version the manifest targets, e.g. `0.1.0` |

Optional, read and written by `src/interop/opengap.py`:

| Field | Type | Constraint |
|---|---|---|
| `author` | string | person or organisation |
| `license` | string | SPDX identifier |
| `model.preferred` | string | model identifier |
| `model.fallback` | string[] | ordered fallbacks |
| `model.constraints.temperature` | number | 0.0–2.0 |
| `model.constraints.max_tokens` | integer | > 0 |
| `skills` | string[] | kebab-case |
| `tools` | string[] | kebab-case |
| `tags` | string[] | free categorisation |
| `metadata` | object | string, number or boolean values only |

The upstream specification defines further optional sections — `extends`,
`dependencies`, `runtime`, `delegation`, `a2a` and a large `compliance` tree.
GalSen IA does not interpret them. They are **preserved verbatim** on read and
written back unchanged, so an agent authored elsewhere loses nothing by passing
through this platform.

### `SOUL.md` — the identity

No enforced schema. At minimum one non-empty paragraph describing the agent's
identity. Sections suggested upstream, and used by our exporter: Core Identity,
Communication Style, Values & Principles, Domain Expertise, Collaboration Style.

### Optional files and directories

`RULES.md`, `DUTIES.md`, `AGENTS.md`, `README.md`, `skills/`, `tools/`,
`knowledge/`, `memory/`, `workflows/`, `hooks/`, `examples/`, `agents/`,
`compliance/`, `config/`, `.gitagent/`.

GalSen IA neither requires nor generates them. `hooks/` in particular contains
executable scripts; see the security note below.

## Security note

`src/interop/opengap.py` reads third-party agent directories. It never executes
anything found in them:

- YAML is parsed with `yaml.safe_load` — no object construction from the file.
- `hooks/`, `tools/` and any other executable content are not run, not imported
  and not resolved.
- `extends` and `dependencies` are not fetched. A manifest cannot make this
  platform reach the network by being read.
- A manifest whose `name` is not kebab-case is rejected before any path is
  built from it, so a crafted name cannot escape the destination directory.

An imported agent is **data**. Running one under GalSen IA requires a Python
class bound to it in `agents/registry.yaml`, written deliberately by a human.
