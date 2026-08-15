# End-to-end demonstration

What one piece of work crosses when it goes through GalSen IA, measured by
running it.

```bash
python scripts/demonstration.py          # human-readable report
python scripts/demonstration.py --json   # same report, for a pipeline
```

The 4308 tests prove that each piece behaves as its author expected. They do not
prove that a piece of work can cross the platform from one end to the other —
the seams are where things break, and the seams are what nobody tests. This is
the check that covers them, and it found a real defect the first time it ran
(see *What it caught* below).

## The steps

| Step | What it exercises |
|---|---|
| `subsystems` | The ten subsystems of volets 47–64, probed in isolation. |
| `knowledge_routing` | The declared routing: which layer answers, and why. |
| `world_knowledge` | The derived world reference, asked in a real sentence. |
| `routine_fires_workflow` | The central seam: a declared routine, a turn with nobody watching, the shared orchestrator, a checkpoint, a correlation identifier. |
| `trail` | That same job, read back out of every store that saw it. |
| `generation` | Whether a model provider answers here. |
| `acquisition` | Whether any source is enabled and reachable. |

## The three rules

**Nothing is simulated.** Every step calls the same code a caller would. A
demonstration that stubbed the orchestrator would demonstrate the stub.

**A step that cannot run here says so, with the reason.** `generation` and
`acquisition` report `NOT_CONFIGURED`: no model provider is configured, no source
is enabled, and the network proxy refuses the Senegalese institutional domains.
They never report success, and they never report failure either — nothing failed.
The blockage is **verified at run time**, not repeated from a stale note: the day
a provider is configured, that step will say so instead.

**The verdict is the sum of what was measured.** `OK` when everything ran,
`PARTIAL` when something is not configured, `FAILED` when a step actually broke.
A demonstration that always ends green is a slide, not a check. The script's exit
code is 1 only on `FAILED`.

`UNKNOWN` is not a failure: it is the honest answer when the knowledge is not
there, and the report carries it as such.

## What it caught

The first run reported `world_knowledge: UNKNOWN` for *Quelle est la capitale du
Ghana ?* — while the world reference holds 249 countries, Ghana included.

`answer_country()` expects a country **name**; the routing was handing it the
whole question. So the world layer, wired as an answering layer since volet 57,
could only answer a question already reduced to `Ghana`. Every unit test passed:
each one called the function correctly. Only the end-to-end run put the two
sides together.

Fixed by `find_country()`, which looks for a known country name **inside** a
sentence by exact match, longest first — `Guinée équatoriale` is never read as
`Guinée`, `Niger` is never read as `Nigeria`, and ISO codes are not matched
inside prose (`EST` and `LA` are codes and French words alike, a trap volet 54
had already sprung).

## What it does not do

- It does not reach the network, and it acquires nothing.
- It does not write to the platform's stores: registries and journals are built
  for the run.
- It does not prove correctness of answers — only that the work crosses, and
  what each step reported.
