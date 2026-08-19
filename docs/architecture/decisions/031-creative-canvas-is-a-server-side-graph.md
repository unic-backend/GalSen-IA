# ADR-031 — The Creative Canvas is a server-side graph, and trust follows the data's destination

**Status**: accepted
**Date**: 2026-08-19
**Directive**: Creative Canvas & Cinema Orchestration Extension, §2, §4, §5, §7, §11, §18, §19, §20, §24, §28
**Volets**: K00–K02 (evidence), K03–K04 (this decision), K05–K08 (implementation)

## Context

The directive asks for a Creative Canvas built with reference to five external
repositories, and forbids rebuilding GalSen IA around them (§13, §28). Four
audit volets produced the evidence this decision rests on, and one of them
overturned a rule written in this same programme.

**Nothing in the five repositories is adoptable** (K01, K02). Four are browser
or Electron applications in JavaScript or TypeScript; this platform is Python
and FastAPI (ADR-001). §4's classification came out **0 KEEP, 0 ADAPT, 3
REFERENCE ONLY, 2 REJECT**, and the two rejections are legal, not technical: two
candidates carry **no licence** on any of four filenames across two branches and
declare `"private": true`. Absence of a grant reserves every right.

**The directive's own premise was wrong on that point.** It states MIT for both.
Measured: 404, every path, both branches.

**Nine of the eleven subsystems §5–§17 names already exist** (K00): reference
entities and consent, world state, shot planning, continuity and identity
verification, capability routing, artefact provenance, style, provider
declaration with licence, and the trust boundary. §11 lists fifteen
registry-like types; **three registries already exist**, and `CreativeProvider`
already carries fifteen fields.

**Exactly one type is genuinely missing**: `ProviderPrivacyPolicy`. §20 asks
where user media goes, whether it is retained, and whether local execution is
possible, and nothing in this platform can record the answer.

**Nothing here generates.** Seventeen media stages: 10 `READY`, 6 `BLOCKED`,
1 `ABSENT`; both provider adapters refuse; zero of ten candidates is
commercially cleared.

## Decisions

### 1. The canvas is a graph model on the server, with no opinion about rendering

`src/creative/canvas/` — four modules: `ports.py`, `graph.py`, `privacy.py`,
`readiness.py`. Nodes, typed ports, an edge legality rule, and a topological
order that produces a **plan**; execution runs through the one existing
orchestrator.

A client may draw it with React Flow, with an SVG, or not at all. The
orchestration is identical either way, and that is what makes this not an
OpenCanvas embed — §5's instruction, expressed as an architecture rather than as
a prohibition.

**Rejected**: adopting `@xyflow/react`. It is MIT and it is good; it is also
React, and taking it would mean shipping a second runtime beside a Python
platform to obtain a data structure that is nodes, ports and an acyclicity
check.

### 2. An edge is legal only when the two port types are equal

No implicit conversion, no "compatible enough", no widening. A type mismatch is
refused naming both types; a cycle is refused; an unconnected required input
leaves the node `BLOCKED`, naming the port.

The port vocabulary is drawn from vocabularies that already exist — `jobs.GENRES`,
the reference entities, `WorldState`, `DirectorSpec`, the style families, the
voice assignments — and never invented for the canvas.

**Why so strict**: K01 measured what the alternative costs. The reference
implementation's `FOCAL_PERSPECTIVE[focalLength] || ""` turns an unhandled focal
length into an empty string — no perspective, no warning, no trace. §7's rule is
that `UNKNOWN` is reported, never converted into an assumption.

### 3. A node's output trust level derives from `data_destination`, not from `invocation`

| `ProviderPrivacyPolicy.data_destination` | Output trust level |
|---|---|
| `LOCAL_ONLY` | `TOOL` |
| `THIRD_PARTY_HOST` | `EXTERNAL` |
| `UNKNOWN` | **`EXTERNAL`** — unknown is not permission |

**This decision replaces one written three phases earlier in this same
programme**, and the correction is the reason the ADR exists in this shape.

K03.2 derived the trust level from `CreativeProvider.invocation`, which reads
like the right field. `src/creative/providers.py:580` computes it from **the
repository licence**:

```python
invocation=(HORS_PROCESSUS
            if "GPL" in str(entree.get("repository_license", ""))
            else DANS_LE_PROCESSUS),
```

That derivation is correct for the question it answers — calling a copyleft tool
out-of-process rather than linking it is a deliberate legal decision. It is
wrong for a security decision. MoneyPrinterTurbo is `API` in the media layer
(ADR-030: called by HTTP, never imported) and `IN_PROCESS` in the creative layer
because its licence is MIT. Under the first rule, a provider reached at a
third-party host would have carried `TOOL` — the level reserved for this
platform's own components — and `src/security/trust.py`'s entire point is that
external content is data, hostile by default.

**Consequence, stated plainly**: `ProviderPrivacyPolicy` does not exist yet, so
every provider's `data_destination` is `UNKNOWN`, so **every generation node is
`EXTERNAL` today**. That is uncomfortable and it is correct.

### 4. `ProviderPrivacyPolicy` is added; nothing else is

Seven fields, each carrying its own evidence — the discipline
`corpus/creative/providers.yaml` already applies to licences: `data_destination`,
`host`, `retention`, `local_execution_possible`, `accepts_personal_data`,
`verified_from`, `evidence`.

**The gate it creates**: a node carrying a reference to a real person may not
route to a provider whose `data_destination` is `UNKNOWN`. The same rule K02
applied to a missing licence, applied to a missing privacy answer.

**Rejected**: a fourth registry, a third provenance system, a second memory
layer, a parallel camera specification. K00 found three registries and two
provenance systems; §3 forbids duplicating them, and M00.2 already recorded the
cost of not noticing.

### 5. A node reports its state; it never returns a plausible result

`READY` / `BLOCKED` (naming what blocks) / `NOT_IMPLEMENTED` / `ABSENT`,
computed the way `src/media/readiness.py` computes its seventeen stages. No
global boolean, no score — `src/security/posture.py` refuses a global grade
because an average hides the one gap that matters.

### 6. Two layers reading one field oppositely is now a pattern, and it is recorded

Twice, two adjacent layers have given one field opposite meanings:

| Field | One layer says | The other says |
|---|---|---|
| `min_vram_gb = None` | *no GPU required* (`media/providers/base.py`) | *nothing was declared* → `UNKNOWN` (`creative/routing.py`) |
| `invocation` | *how the provider is called* (`media/providers/moneyprinterturbo.py`) | *is the licence copyleft* (`creative/providers.py`) |

Both are defensible inside their own module. Both mislead across the boundary,
and the second nearly became load-bearing for a security decision.

**Neither is resolved here.** Resolving either means changing a meaning every
caller relies on, and doing that inside an audit programme would be exactly the
kind of unrequested change §13 forbids. The decision is that **the next change
touching either field resolves it**, and this table is where that obligation
lives.

## Consequences

**Positive.** The canvas costs four modules against nine reused subsystems.
Nothing is adopted, so nothing is inherited: no npm tree, no second runtime, no
licence exposure — the dependency count this programme adds is **zero**. The
privacy question finally has a home, and it fails safe.

**Negative, and stated rather than softened.** Every generation node is
`EXTERNAL` and `BLOCKED` today; the canvas can be designed, tested and reported
on, but it cannot produce an image or a video until a provider runs. Filling in
`data_destination` requires reading terms or installing a provider and observing
its sockets — work outside this repository.

**Neutral.** The four ideas taken from the audited repositories — a typed node
graph, camera controls as first-class values, motion as four signed axes, an
identity referenced by id — are ideas, not expressions, and two of them the
platform had already implemented before this programme began.

## What this ADR does not decide

- **`CreativeIntent`** — §6's required / optional / forbidden split (K05).
- **`CameraSpec` / `LensSpec`** — whether `DirectorSpec` needs a camera body and
  a real aperture value, or whether its ten declared vocabularies already
  suffice (K06).
- **A shared `GenerationResult`** — moot until two providers run. One does.
- **Graph persistence** — `GALSEN_STORAGE_BACKEND` already decides this for
  every stateful engine; the canvas follows it rather than choosing.
