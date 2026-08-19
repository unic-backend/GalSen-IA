# K04.2 — feasibility of the Creative Canvas

Creative Canvas directive, §25. Measured 2026-08-19.

The ten gates are the ones `docs/creative/feasibility.md` established for the
previous programme: **(1)** possible today · **(2)** an appropriate provider
exists · **(3)** GPU feasible · **(4)** latency acceptable · **(5)** quality
acceptable · **(6)** measurable · **(7)** failure detectable · **(8)** fallback
possible · **(9)** removable later · **(10)** licence compatible.

That document answers them for the creative capabilities. This one answers them
for **the four things ADR-031 decided to build**, and for the one thing the
canvas exists to do.

---

## Summary

| Capability | Verdict | The gate that decides it |
|---|---|---|
| Graph model — ports, edge legality, order | **FEASIBLE** | Pure orchestration. No provider, no GPU, no licence question. |
| Trust level per node type | **FEASIBLE** | A table over `TrustLevel`, which already exists. |
| `ProviderPrivacyPolicy` — the type | **FEASIBLE** | A dataclass with evidence fields, like `LicenceRecord`. |
| `ProviderPrivacyPolicy` — the **values** | **BLOCKED** (gate 1) | Nobody has read a provider's terms or watched its sockets. |
| Per-node readiness | **FEASIBLE** | `src/media/readiness.py` is the working precedent. |
| **Running a generation node** | **BLOCKED** (gates 1, 2) | Nothing in this platform generates an image or a video. |
| A canvas executing end to end | **BLOCKED** (gate 2) | Follows from the row above; the plan is producible, the run is not. |

**Four of seven are feasible today, and they are the four ADR-031 decided to
build.** That is not a coincidence — the audits are what reduced the scope to
the feasible part.

---

## The three blocked rows, in detail

### Running a generation node — gates 1 and 2

Gate 1 (*possible today*): **no.** K00 re-measured the media engine — 17 stages,
10 `READY`, 6 `BLOCKED`, 1 `ABSENT`. Both provider adapters refuse:
`wangp` needs a GPU this machine does not have, `moneyprinterturbo` needs a real
`ffmpeg`, a running service and a stock-library key.

Gate 2 (*an appropriate provider exists*): **one, partially.** Routing measured
across ten candidates gives exactly one selection —
`stock_assembly`, non-commercial → `moneyprinterturbo` — and `NO_PROVIDER` for
`text_to_video` and for any commercial request, because no output right is
established.

Gates 3–5 are unreachable: **you cannot measure the latency or the quality of
something that does not run**, and inventing a number for those columns is the
one thing `.claude/rules/verification.md` names as making a fabrication
permanent.

Gates 6–9 are satisfied in advance, and that matters: failures are detectable
(each adapter raises a named exception rather than returning a placeholder), the
fallback is a refusal rather than a substitution (`routing.py`), and a node type
is removable because nothing else depends on it.

Gate 10 (*licence compatible*): **`UNKNOWN`** — zero of ten candidates is
commercially cleared, eight weight licences are unreadable from this container.

### `ProviderPrivacyPolicy`'s values — gate 1

The *type* is trivially feasible. Its *content* is not, and the distinction is
the whole row.

`data_destination` has three possible answers and only two ways to establish
one: read the provider's published terms, or install it and observe whether it
opens a socket. Neither has been done for any of the ten candidates, and neither
can be faked from a repository README.

So every provider is `data_destination: UNKNOWN` on the day this ships, and
ADR-031's rule makes that mean `EXTERNAL` — the safe reading. **The capability
works from day one; it just answers `UNKNOWN` honestly**, which is the same
shape as `readiness()` reporting `ABSENT` for speech synthesis.

### A canvas executing end to end

The graph plans, orders and reports. It cannot run, because its terminal nodes
cannot. **A canvas that rendered Image and Video nodes as available would be
claiming a capability no measurement supports** — the largest fabrication either
programme has come near, and the reason node readiness is computed rather than
written.

---

## What is feasible, and why it is worth building anyway

An orchestrator whose providers all refuse is not useless — it is the part that
does not change when they stop refusing.

- The **graph, ports and legality rule** are provider-independent. They are the
  same the day `ffmpeg` is installed.
- The **trust mapping** is what decides whether a returned artefact is treated
  as platform output or as hostile data. It has to be right *before* anything
  runs, not after.
- The **privacy policy** is the field that will refuse to send a person's
  likeness to an unchecked host. Its value is entirely in existing before the
  first upload, not after the first incident.
- **Per-node readiness** is how an operator learns that one `ffmpeg` install
  moves five things at once — which is what the previous programme measured.

## Environment constraints, restated rather than assumed away

Three of the seven gaps `src/security/posture.py` reports bear on this
programme, and none of them is a blocker for what ADR-031 builds:

| Gap | Effect here |
|---|---|
| A child process reads and writes wherever the user can | An upload node inherits it — the design states it, it does not fix it |
| No network cut without namespaces | A provider node inherits it |
| The approval gate is in memory | A consent decision does not survive a restart unless `GALSEN_STORAGE_BACKEND=sqlite` |

Machine unchanged: 4 cores, 15.7 GiB RAM, **no GPU**, VRAM `NOT_MEASURED`.

## What would move the blocked rows

1. **A real `ffmpeg`** — moves four media stages and one provider at once.
2. **Reading the Pexels and Pixabay terms** — moves `commercial_status` off
   `UNKNOWN` for the only routable provider.
3. **Installing one local provider and observing its sockets** — turns one
   `data_destination` from `UNKNOWN` into a measurement.
4. **A GPU host** — moves the eight adapters that declare a VRAM requirement.

All four are outside this repository. None is a design question.
