# K03.2 — Creative Canvas architecture

Creative Canvas directive, §5 and §7. Designed 2026-08-19, **after** the four
audits, and deliberately not before.

§28 is the sentence this design has to keep true: *GalSen IA is not a Higgsfield
clone and not an OpenCanvas clone. The orchestrator owns creative intent,
references, world state, continuity, shot planning, routing, verification,
provenance, privacy, consent and safety.*

K03.1 reduced the work to **four things that do not exist**. This document
designs those four and nothing else.

---

## The shape of the decision

A canvas is usually built as a rendering surface with logic attached. That is
what all four JavaScript candidates are, and it is why none of them is
adoptable: their intelligence lives inside a React tree.

Here the canvas is **a graph model on the server**, expressed through the
existing API, with no opinion about how it is drawn. A client may render it with
React Flow, with an SVG, or not at all; the orchestration is identical. That is
the whole of §5's *"do not simply embed OpenCanvas"*, stated as an architecture
rather than as a prohibition.

**New module: `src/creative/canvas/`.** Four files, matching the four gaps.

```
src/creative/canvas/
    ports.py       the type vocabulary carried on an edge
    graph.py       nodes, edges, legality, order
    privacy.py     ProviderPrivacyPolicy — the one genuinely missing type
    readiness.py   per-node state, computed, never written
```

Nothing else is added. In particular: **no registry, no provenance store, no
memory layer, no reference system, no second camera specification.** K00 found
three registries and two provenance systems already; a fourth of either would be
the mistake this programme was ordered to avoid.

---

## 1. Ports — the type vocabulary

An edge carries a value. The value has a type, and the type is drawn from
vocabularies that already exist, never invented for the canvas:

| Port type | What flows | Where the type already lives |
|---|---|---|
| `text` | a written request or intent | — |
| `image`, `video`, `audio` | an artefact | `jobs.GENRES` |
| `analysis` | a report, not an artefact | `jobs.GENRES` |
| `reference` | an entity identity, by id | `creative/reference/` |
| `world` | a `WorldState` | `creative/world.py` |
| `direction` | a `DirectorSpec` | `creative/direction.py` |
| `style` | a style family | `creative/style.py` |
| `voice` | a voice/scene assignment | `creative/voice/` |

**An unknown port type is refused, not coerced.** This is the same rule
`DirectorSpec.__post_init__` already applies to shot scales and camera heights,
and for the same reason: a value invented at the edge behaves like an adjective
— it decides nothing and cannot be contested.

### Edge legality

An edge from `A.out[p]` to `B.in[q]` is legal **only when the two port types are
equal**. There is no implicit conversion, no "compatible enough", no widening.

Three refusals, all explicit:

- **Type mismatch** → refused, naming both types.
- **Cycle** → refused. A creative graph that feeds its own output back into its
  input has no defined order, and inventing one would invent a result.
- **Unconnected required input** → the node is `BLOCKED`, naming the port. It
  is not silently defaulted, which is exactly what `FOCAL_PERSPECTIVE[x] || ""`
  does in the reference implementation.

Execution order is the topological order of the graph. The graph produces a
**plan**; execution runs through the one existing orchestrator.

---

## 2. Trust level per node type — the mapping that did not exist

K00 found `src/security/trust.py` complete — seven levels, `wrap()`,
`inspect()`, `is_data()` — and **no node mapped to any of them**. That mapping
is the second gap, and it is a table, not a module:

| Node | `TrustLevel` | Why |
|---|---|---|
| Prompt / intent node | `USER` | the request: trusted for intent, never for a system order |
| Upload node (a photo, a recording) | `DOCUMENT` | a file supplied — data, whatever it says inside |
| Knowledge retrieval node | `RETRIEVED` | passage from the knowledge base |
| Direction, style, reference-registry nodes | `DEVELOPER` | values from a registry a human edits |
| World-state node | `TOOL` | output of a platform component |
| **Generation node** | **decided by the provider** | see below |

### The rule worth stating separately

**A generation node's output trust level is decided by where the provider sends
the data, not by the node's type.**

| `ProviderPrivacyPolicy.data_destination` | Output trust level |
|---|---|
| `LOCAL_ONLY` | `TOOL` — output of a platform component |
| `THIRD_PARTY_HOST` | **`EXTERNAL`** — *hostile by default*, in `trust.py`'s own words |
| `UNKNOWN` | **`EXTERNAL`** — unknown is not permission |

Two canvases with the same node types therefore carry different trust levels
depending on which provider was routed to. That is correct, and it is invisible
to any design that attaches trust to the node icon.

**This rule was written differently and corrected in K04.1.** The first version
derived the trust level from `CreativeProvider.invocation`, which reads like the
right field and is not: `adapt_declared()` computes it from *the repository
licence* — `OUT_OF_PROCESS` when the licence is copyleft, `IN_PROCESS`
otherwise — so a provider called over HTTP at a third-party host reports
`IN_PROCESS` and would have been trusted as platform output. `data_destination`
answers the question directly, and its `UNKNOWN` fails safe. Full account →
`docs/canvas/provider-comparison.md` §3.

---

## 3. `ProviderPrivacyPolicy` — the one type that is genuinely missing

§20 asks where user media goes, whether it is retained, and whether local
execution is possible. K00 measured that nothing in the platform records it.
K01 produced the concrete case: `higgsfield-ai/skills` sends prompts and user
media to a hosted commercial API, and the platform has nowhere to write that
down where a router could act on it.

Fields, each carrying its own evidence — the discipline
`corpus/creative/providers.yaml` already uses for licences:

| Field | Values |
|---|---|
| `data_destination` | `LOCAL_ONLY` / `THIRD_PARTY_HOST` / `UNKNOWN` |
| `host` | the named host, or `None` |
| `retention` | `NONE` / `TRANSIENT` / `RETAINED` / `UNKNOWN` |
| `local_execution_possible` | `True` / `False` / `UNKNOWN` |
| `accepts_personal_data` | `True` / `False` / `UNKNOWN` |
| `verified_from` | the URL the answer was read at |
| `evidence` | `AUTHORITATIVE` / `DECLARED` / `NONE` |

### The gate this creates

**A node carrying a reference to a real person may not route to a provider whose
`data_destination` is `UNKNOWN`.**

`UNKNOWN` is not permission — the same rule K02 applied to a missing licence,
applied to a missing privacy answer. A person's likeness is not sent to a host
nobody has checked because nobody has checked it.

This composes with what already exists rather than replacing it: consent lives
in `creative/reference/`, the artefact provenance in `jobs.py`, the licence gate
in `LicenceRecord`. The privacy policy is the fourth question in the same
sentence, and the only one with no home.

---

## 4. Node readiness — computed, never written

`src/media/readiness.py` walks seventeen stages and answers with a verdict it
computed. A canvas node answers the same way:

| State | Meaning |
|---|---|
| `READY` | the node can run now, measured |
| `BLOCKED` | it cannot, **and it names what blocks it** |
| `NOT_IMPLEMENTED` | the node type exists, its execution does not |
| `ABSENT` | no implementation can exist here (speech synthesis, today) |

Three rules, each of which the platform already enforces elsewhere:

1. **No global boolean.** A graph reports node by node. "The canvas is not
   ready" tells an operator nothing about what to install; "node 3 is blocked on
   `ffmpeg`" tells them everything.
2. **No score.** `src/security/posture.py` refuses a global grade because an
   average hides the one gap that matters. A canvas readiness score would hide
   it the same way.
3. **A blocked node reports; it never returns a plausible result.** Today
   **every generation node in this platform is `BLOCKED`** — nothing here can
   generate an image or a video (K00, re-measured). A canvas that renders those
   nodes as available would be claiming a capability no measurement supports.

---

## What the canvas explicitly does not own

| Concern | Owned by | Since |
|---|---|---|
| Reference entities, consent | `creative/reference/` | C05, C06 |
| World state | `creative/world.py` | C09 |
| Shot planning, camera, lens | `creative/direction.py` | C10 |
| Continuity, identity, drift | `creative/verification.py` | C11 |
| Capability routing, refusal to substitute | `creative/routing.py` | C15 |
| Artefact provenance | `creative/jobs.py` | C16 |
| Style, kept out of the world | `creative/style.py` | C19 |
| Provider declaration, licence | `creative/providers.py` | C04, M05 |
| Trust boundary | `security/trust.py` | — |

**A canvas node calls into these. It does not re-implement any of them**, and
the design is deliberately thin for that reason: four files against nine
existing subsystems.

---

## Open questions this design does not close

- **`CreativeIntent`** — §6's required / optional / forbidden split is K05, not
  here. Until it exists, a node cannot express "this element is forbidden", and
  the canvas can only carry what was requested.
- **`CameraSpec` / `LensSpec` extension** — K06. `DirectorSpec` already holds
  shot size, height, movement, focal, depth of field and lighting; a camera body
  and a real aperture value are the additions, and their necessity is not yet
  established.
- **A shared `GenerationResult`** — K00 called it moot until two providers run.
  One runs today (`stock_assembly`, non-commercial). It stays moot until two.
- **Persistence of a graph** — `GALSEN_STORAGE_BACKEND` already decides this for
  every stateful engine; the canvas will follow it rather than choose.

---

## Why this is small

The instinct, holding a directive with twenty-eight sections and a reference
implementation with twenty-five studios, is to build twenty-five things.

The audits measured that **nine of the eleven subsystems §5–§17 name already
exist**, that **zero lines from five repositories may be adopted**, and that
**one type is genuinely missing**. A design proportional to the directive would
be a design ignoring its own audits.

Four files. One of them is a table.
