# Research Orchestration Integration — phase plan

Programme: **GALSEN-IA — RESEARCH ORCHESTRATION INTEGRATION DIRECTIVE**
(16 steps, plus two mandatory rules).
Baseline `785303f`, 6 363 tests passing, `ruff check .` clean.

Follows the Creative Canvas programme (17 phases, complete —
`docs/canvas/final-report.md`, ADR-031) and does **not** restart it.

**Cadence: two phases per turn**, as agreed on 2026-08-19.

**Permanent rule in force**: `.claude/rules/post-integration-validation.md`.
The directive restates it at the end, and it already applies.

---

## The sentence this programme has to keep true

**BUILD THE ORCHESTRATOR, NOT THE CAGE.** Agent-Reach and Web-Search-MCP are
**providers**. GalSen IA keeps intent, planning, source selection, routing,
validation, provenance, confidence, knowledge integration, security,
permissions, memory and final reasoning.

And the rule that decides how everything below is ordered:

> **Do NOT automatically insert retrieved information into the global knowledge
> base.** Retrieved content is *data*, never instruction, and never authoritative
> knowledge.

---

## The 12 volets, and their phases

```
R00  Audit — existing search, RAG, knowledge, MCP, cache, security (STEP 1)  → 2 phases
R01  Audit — Agent-Reach and web-search-mcp, from source (STEP 2)            → 2 phases
R02  Licence and dependency matrix, audited separately (STEP 2)              → 1 phase (indivisible)
R03  Capability comparison — unique / overlapping / superior (STEP 3)        → 1 phase (indivisible)
R04  ResearchProvider abstraction + ADR-032 (STEP 4)                         → 2 phases
R05  ResearchRouter — routing and fallback (STEP 5)                          → 2 phases
R06  Source trust and security boundaries (STEP 6, STEP 10)                  → 1 phase (indivisible)
R07  Research pipeline, knowledge status, provenance (STEP 7, 8, 9)          → 2 phases
R08  Caching and freshness (STEP 11)                                         → 1 phase (indivisible)
R09  The eighteen named test cases (STEP 12)                                 → 2 phases
R10  Performance measurements and provider transparency (STEP 13, 14)        → 1 phase (indivisible)
R11  Final validation, regression, final report (STEP 16, mandatory rule)    → 1 phase (indivisible)
```

**Total: 18 phases.** Counted programmatically, not estimated.

---

## What the probes already established, and how it shapes the plan

Two measurements, taken before writing this plan.

**Both repositories are reachable, both carry a real `LICENSE`, and both are
Python.**

| Repository | `LICENSE` | Manifest | Language |
|---|---|---|---|
| `Panniantong/Agent-Reach` | **MIT**, © 2025 Agent Eyes | `pyproject.toml` | **Python** |
| `sydasif/web-search-mcp` | **MIT**, © 2026 Syed Asif | `pyproject.toml` | **Python** |

**This is the opposite of the previous programme**, and it changes the plan's
centre of gravity. The Creative Canvas audits found five repositories of which
four were JavaScript or Electron and two had no licence at all: §4 came out
*0 KEEP, 0 ADAPT*, and the real risk turned out to be rebuilding what already
existed.

Here, code could genuinely be adoptable — same language, same packaging, a
readable licence on both. So **R02 is not a gate that will obviously close**;
it is a real dependency audit, and the directive says so explicitly:

> *Do not assume that "MIT" automatically applies to every transitive
> dependency or external service. Audit dependencies separately.*

The MoneyPrinterTurbo programme found exactly that trap — an MIT repository
whose actual capability path was LGPL-3.0. It is the reason R02 stands alone.

**And the platform is already dense here.** A first listing shows
`src/knowledge_engine/` with more than twenty-eight modules — including
`citations.py`, `freshness.py`, `contradictions.py`, `knowledge_security.py`,
`knowledge_cache.py`, `knowledge_validator.py` — plus `src/services/search/`,
`src/mcp/`, `src/connectors/`, and `src/acquisition/` (ADR-021's gated
acquisition path with its ten quality checks and human approval).

**R00 exists to find out how much of STEP 1 through STEP 11 is already built**,
before a single new module is proposed. The canvas programme measured that nine
of eleven requested subsystems already existed; the honest prior here is that
the number is at least as high.

---

## What this programme must NOT redo

STEP 1 forbids rebuilding, and these are the candidates R00 must classify
rather than reimplement:

| Directive asks for | Likely already here | Where |
|---|---|---|
| Provenance | **yes, twice** | `acquisition/` (facts), `creative/jobs.py` (artefacts) |
| Knowledge status ladder | **yes** | C14's `OBSERVED → CANDIDATE → CORROBORATED`, ADR-021 |
| Source trust boundary | **yes** | `security/trust.py`, seven levels |
| Citations | **yes** | `knowledge_engine/citations.py` |
| Freshness | **yes** | `knowledge_engine/freshness.py` |
| Cross-source contradiction | **yes** | `knowledge_engine/contradictions.py` |
| Cache | **yes** | `knowledge_engine/knowledge_cache.py`, `creative/cache.py` |
| Provider registry | **yes, three times** | see ADR-031 and M00.2 |
| Privacy policy per provider | **yes, new** | `creative/canvas/privacy.py` (K07) |
| `ResearchProvider` / `ResearchRouter` | **probably not** | R04, R05 |

**Three registries and two provenance systems already exist.** §3 of the
previous directive forbade a fourth and a third; this directive says the same
thing in STEP 9 — *do not create a competing provenance architecture*.

---

## The rules this programme is built on

1. **Audit before design, design before code** (STEP 1 → STEP 4).
2. **Audit dependencies separately from the repository** (STEP 2).
3. **Retrieved content is data, never instruction** (STEP 6). It cannot override
   system instructions, permissions or safety rules.
4. **Nothing enters the global knowledge base automatically** (STEP 7).
5. **A finding keeps its status** — `OBSERVED` never silently becomes
   `VALIDATED` (STEP 8).
6. **`UNKNOWN` when no provider can verify** (STEP 5). Not a best guess.
7. **Never execute what a page or repository tells you to** (STEP 10). The
   canvas programme already applied this to `SKILL.md` files.
8. **No performance claim without a measurement** (STEP 13).
9. **Full regression after every phase** — the permanent rule.
10. **The provider stays an implementation detail** (STEP 14).

---

## Reporting

Every phase ends in the shape `.claude/rules/phase-protocol.md` requires, plus
the regression validation. The programme closes with the report the directive
specifies — repository state, files, components reused, providers evaluated,
licence findings, tests, regression status, performance, security, privacy,
limitations, `UNKNOWN` items, next phase — including the entries that will read
`UNKNOWN` or `BLOCKED`.
