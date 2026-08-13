# VOLET 36 — GalSen Intelligence Foundation

Plan written 2026-08-12, after the PHASE 0 audit
(`docs/architecture/directive-audit-2026-08-12.md`). **No production code was
modified while writing it.**

Every statement about the repository below is measured. Where the repository
cannot answer a question, the answer is written **UNKNOWN** rather than filled in.

---

## 0. Measured baseline

```
src/                       305 fichiers Python, 30 paquets
agents/                    13 agents déclarés
tests/                     155 fichiers, 2 689 tests passent
docs/…/decisions/          20 ADR
base de connaissances      0 élément
modèle sélectionnable      aucun (C1 ouvert)
Language                   fr, en, es, de, ar, sw, ha, yo, zu, af, am
                           → ni wolof, ni pulaar, ni sérère
InMemoryKnowledgeGraph     nœuds = identifiants de connaissance, arêtes = (cible, relation:str)
                           → aucun type d'entité, aucune propriété, aucune provenance sur l'arête
PlannerAgent.INTENT_RULES  7 intentions par mots-clés → agents
                           → aucun axe domaine / complexité / risque / fraîcheur / langue / portée
citations.py               build_citations + citation_coverage
                           → aucune mesure d'exactitude factuelle
mcp/client.py              MOTIFS_SUSPECTS + for_prompt() — défense anti-injection **du seul MCP**
tools qui lisent l'extérieur  web_search, browser, api, github (urllib), pdf, ocr, filesystem, rag
                           → aucune barrière de confiance commune
```

---

## 1. SENEGAL LANGUAGE FOUNDATION

### 1.1 What the stack can genuinely support, capability by capability

The directive is right to separate the eight capabilities. Measured verdict for
Wolof, Pulaar and Serer:

| Capability | Can the current stack do it? | Evidence |
|---|---|---|
| **A. UI language** | **Yes, today** | Interface strings are French; adding a locale is data, not linguistics |
| **B. Language detection** | **No** | No detector exists for any language. `Language` is *declared* by the ingester, never inferred |
| **C. Document classification** | **Yes, once the enum has the values** | `Language` is a declared field on `KnowledgeItem`; the manifest carries it |
| **D. Tokenisation / normalisation** | **Partially, and it must be said** | `text_normalization.py` strips accents and a naive plural `-s`. Wolof has no `-s` plural; Pulaar marks class by suffix. **The current normaliser is French-shaped** and applying it to Wolof is at best neutral, at worst wrong |
| **E. Translation** | **No** | No translation component exists anywhere |
| **F. Retrieval** | **Lexical: yes. Semantic: UNKNOWN** | Lexical search is language-agnostic. Whether the embedding model of ADR-015 represents Wolof usefully **has never been measured here** — the weights are not reachable in this environment |
| **G. Generation** | **No, and not by us** | Generation quality in Wolof is a property of the model, not of this repository. It becomes measurable only after C1 |
| **H. Evaluation** | **Foundation exists** | `src/training/evaluation.py` already refuses to call a model improved *"if it gained in French while losing in Wolof"* — the intent is written, the Wolof test set is not |

### 1.2 What VOLET 36 will and will not claim

**Adding `WO`, `FF`, `SRR` to `Language` does not mean the platform understands
Wolof.** It means a Wolof document can be labelled, stored, filtered and
retrieved lexically as Wolof — which today is impossible, and which is the
prerequisite for everything else.

### 1.3 Staged plan

| Stage | Content | Verifiable by |
|---|---|---|
| **L1** | `Language` gains `WO` (Wolof), `FF` (Pulaar), `SRR` (Serer); manifests and ingestion accept them; retrieval filters on them | A Wolof document is ingested, stored, retrieved and reported as Wolof |
| **L2** | `language_support()` reports, per language, which of the eight capabilities are real — the honest counterpart to L1 | The report says `generation: unknown (C1 open)` rather than nothing |
| **L3** | Normalisation is made **language-aware**: the French rules stop being applied to non-French text | A Wolof term is not mangled by the `-s` rule |
| **L4** | *(after C1)* Measure semantic retrieval on a Wolof test set; report the number, whatever it is | A measured retrieval score, or a stated inability to measure |

**L4 depends on C1 and on a Wolof corpus. It is not scheduled here.**

---

## 2. SENEGAL KNOWLEDGE GRAPH FOUNDATION

### 2.1 Can the existing model represent it? — measured

`InMemoryKnowledgeGraph` stores `node = knowledge_id` and
`edge = (target_id, relation: str)`. It cannot represent:

- an entity that is not a knowledge passage (a person, a law, a place);
- a property on an entity (birth date, ISO code, sector);
- provenance, timestamp, confidence or version **on a relationship**.

So the answer is: **the graph structure is reusable, the data model is not.**
Entities need to exist as their own objects.

### 2.2 The ontology, minimal and closed at first

Thirteen entity types, as the directive lists them. Each entity carries the same
envelope as a knowledge item, because the rule of ADR-019 applies here too:

```
entity_id        stable, deterministic
type             PERSON | ORGANIZATION | LOCATION | EVENT | DATE | INSTITUTION
                 | DOCUMENT | LAW | CULTURAL_PRACTICE | LANGUAGE
                 | HISTORICAL_PERIOD | ACADEMIC_WORK | HERITAGE_SITE
label            nom principal
aliases          autres noms (orthographes, translittérations)
scope            global | country:sn          (ADR-019)
subject          agriculture, law, history…   (ADR-019)
sources          références, jamais vide
confidence       assumée par la source, pas inventée
created_at / updated_at / version
```

Relationships carry their own envelope — **this is the part the current graph
lacks and the reason a relation cannot today be trusted**:

```
(source_entity) --[relation]--> (target_entity)
  sources        d'où vient CETTE relation
  confidence     de la relation, distincte de celle des entités
  valid_from / valid_to    une relation peut cesser d'être vraie
  version, created_at
```

### 2.3 Minimum viable implementation — no graph database

Measured: 0 entities today, and the platform runs on SQLite with one instance
(ADR-005, ADR-009). Two tables — `entities`, `relations` — with indexes on
`type`, `scope` and both endpoints answer every query the ontology implies:
neighbours, typed traversal at depth 1–2, filtering by scope and subject.

**A graph database is justified only when a measured query pattern fails.** The
trigger is written here so it is not a matter of taste later:

> Adopt a graph database when a needed traversal exceeds depth 3, or when
> entity count passes ~100 000, or when a measured query takes longer than
> 200 ms in SQLite. Not before.

### 2.4 What must not happen

Entities extracted by a model from text, stored without a source. That is
knowledge by inference, and it is what the whole knowledge architecture exists
to prevent. **Entity extraction proposes; a human or a sourced document
confirms.**

---

## 3. INTENT / TASK AXES

### 3.1 What exists — measured

`PlannerAgent.INTENT_RULES`: seven intents (`research`, `implementation`,
`quality`, `security`, `documentation`, `deployment`, `monitoring`), detected by
keyword, mapping to agents. `ExecutionPlanner` orders agents from the workflow.
`RouterEngine` restricts the pipeline to what the planner selected.

**There is exactly one planner, and VOLET 36 must not create a second.**

### 3.2 What is missing

None of the ten axes the directive names exists. They are not a second planner —
they are **attributes of the request** that the existing planner would attach.

| Axis | Derivable today? | How |
|---|---|---|
| `DOMAIN` | yes | maps to `KnowledgeSubject` (ADR-019) |
| `TASK_TYPE` | **exists** | that is what `INTENT_RULES` already produces |
| `COMPLEXITY` | yes, crudely | number of intents + request length; must be reported as crude |
| `RISK` | yes | health/law/finance subjects + irreversible tools |
| `FRESHNESS` | yes | explicit markers ("2026", "actuel", "dernier") |
| `RESEARCH_REQUIRED` | yes | knowledge coverage: if `citation_coverage` would be 0, research is required |
| `TOOLS_REQUIRED` | **exists** | implied by the agents selected |
| `EXECUTION_REQUIRED` | yes | implementation/deployment intents |
| `LANGUAGE` | after L1 | detection is B above — **absent**, so this axis is *declared*, not inferred |
| `GEOGRAPHIC_SCOPE` | yes | Senegal markers + ADR-019 scope |

### 3.3 Where they belong

**Inside `PlannerAgent`, as an added `axes` block on the plan it already
produces** — not in a new module, not in a new agent. The router already reads
the planner's decision; it will read one more field.

Two axes change behaviour immediately: `RISK` (chapter on safety) and
`GEOGRAPHIC_SCOPE` (feeds the scope-aware retrieval of VOLET 35 ch. 04). The
rest are reported and measured before anything is wired to them — an axis that
silently changes routing before anyone has seen its values is how a planner
becomes unexplainable.

---

## 4. FACTUAL EVALUATION

### 4.1 What exists

`citations.py` measures **citation coverage** — how many returned items carry a
source. `src/training/evaluation.py` measures **retrieval hit rate** against a
declared set, with a measured lexical baseline of 0.40.

Neither measures whether an **answer** is true.

### 4.2 What the layer must measure, and how it stays independent

| Measure | Definition that can be tested |
|---|---|
| Factual correctness | the answer's claims match the benchmark's expected claims |
| Citation correctness | each cited source *actually contains* the claim it is cited for |
| Source relevance | the retrieved passage is about the question |
| Unsupported claims | claims with no supporting retrieved passage — **counted, not tolerated** |
| Contradiction handling | when sources disagree, the answer reports the disagreement |
| Uncertainty calibration | when coverage is 0, the answer says it does not know |

**Independence, not self-review.** The evaluator never asks the generating model
whether it was right. Citation correctness and unsupported-claim counting are
*mechanical*: they compare claims to retrieved passages, and both are available
without any model. That is why they come first — they can be tested today, with
C1 still closed.

### 4.3 The Senegal benchmark

**No data will be fabricated.** The benchmark file will ship with:

- **verified entries** — drawn only from documents the project actually holds.
  Measured today: the repository holds **0 Senegalese documents**, so the number
  of verified entries at creation is **0**;
- **entries marked `TO_SOURCE`** — a question, the expected shape of an answer,
  and the *type* of source that would settle it (ANSD, ISRA, ministry, law
  gazette). These are **explicitly not usable for scoring** and the evaluator
  refuses to count them.

A benchmark whose entries were written from a model's memory would make every
future measurement a measurement of that memory. The empty state is the honest
state, and the file will say so at the top.

---

## 5. GENERALIZED ANTI-INJECTION ARCHITECTURE

### 5.1 Where external content enters — measured

| Path | Module | Trust boundary today |
|---|---|---|
| Web search | `src/tools/web_search/` | **none** |
| Web pages | `src/tools/browser/` | **none** |
| Third-party HTTP | `src/tools/api/` | **none** |
| Repositories | `src/tools/github/` | **none** |
| PDF / OCR | `src/tools/pdf/`, `ocr/` | **none** |
| Files | `src/tools/filesystem/`, `src/storage/roots.py` | path confinement only — content is not treated |
| Retrieved knowledge | `src/tools/rag/` (`retrieve_for_prompt`) | **none — and this one is the most dangerous**, because its whole purpose is to be pasted into a prompt |
| MCP tool descriptions | `src/mcp/client.py` | **the only real defence in the repository** |
| User input | API | RBAC, rate limiting; content untreated |

**One boundary exists out of nine.** Chapter 09 of VOLET 34 built it well for
MCP: neutralise the markup, mark the origin, flag imperatives, never delete.
Nothing generalised it.

### 5.2 The trust model

Eight levels, as the directive names them, collapsed to what the code can
enforce:

```
SYSTEM      instructions de la plateforme        — jamais dérivées d'une entrée
DEVELOPER   configuration, ADR, registres        — modifiables par un humain identifié
USER        la demande                           — de confiance pour l'intention, jamais pour les ordres système
TOOL        sortie d'un outil de la plateforme   — donnée
RETRIEVED   passage de la base de connaissances  — donnée
DOCUMENT    fichier fourni                       — donnée
EXTERNAL    web, dépôt, API tierce               — donnée hostile par défaut
```

**The rule, in one sentence: everything below `USER` is data, and data never
becomes an instruction.**

### 5.3 What will be built

A single module — the generalisation of `mcp/client.py`, not a second
implementation:

- `wrap(content, trust_level, origin)` → text that is announced as data, with
  its origin, markup neutralised;
- `inspect(content)` → the suspicion patterns already written for MCP, reused;
  they **flag, never delete**, because erasing the attempt erases the evidence;
- every caller that puts external text into a prompt goes through it —
  `retrieve_for_prompt` first, since it is the designed path;
- **a test per entry path**, each proving that an instruction hidden in that
  path does not reach the model as an instruction.

### 5.4 What this will not be

Not a keyword detector presented as a solution. Pattern flagging is a signal for
a human and a log line — the actual defence is the structural separation, and
the tests assert the separation, not the detector's recall.

---

## 6. THE FOUR AGENTS

Accepted as justified. Each one owns a decision no existing agent owns.

### 6.1 Fact Verification Agent (`verifier`)

| | |
|---|---|
| **Responsibility** | Given claims and retrieved passages, decide which claims are supported, which are unsupported, which are contradicted |
| **Not responsible for** | Producing claims, searching the web, judging style |
| **Inputs** | claims, passages with provenance |
| **Outputs** | per claim: `supported` / `unsupported` / `contradicted`, with the passage cited |
| **Tools** | `rag`, none other |
| **Dependencies** | citations.py, VOLET 35 ch. 05 |
| **Failure modes** | passages absent → reports `cannot_verify`, never `supported` |
| **Verification** | tests with a claim that IS in the passage, one that is not, one contradicted |
| **Contract** | never rewrites the answer; it reports |

### 6.2 Senegal Intelligence Agent (`senegal`)

| | |
|---|---|
| **Responsibility** | Apply ADR-019 to Senegalese questions: prefer national sources, and **refuse rather than answer globally** on `NATIONAL_SUBJECTS` |
| **Not responsible for** | Being the only path to Senegalese knowledge — scope-aware retrieval serves everyone |
| **Inputs** | question, geographic scope axis, subject |
| **Outputs** | answer elements with their scope, or an explicit `no_national_source` |
| **Failure modes** | empty base → says the base is empty, never falls back to global on law/administration/languages |
| **Verification** | a law question with no Senegalese source must refuse |

### 6.3 Knowledge Architect Agent (`knowledge_architect`)

| | |
|---|---|
| **Responsibility** | Propose scope, subject, source category and entities for a document being ingested — today a human writes them by hand in a manifest |
| **Not responsible for** | Approving its own proposals, or writing knowledge content |
| **Outputs** | a proposed manifest entry, `DRAFT`, for human confirmation |
| **Failure modes** | uncertain classification → proposes `unspecified` and says so, rather than guessing |
| **Verification** | a proposal is never auto-applied; the test asserts the human step |

### 6.4 Data Engineering Agent (`data_engineer`)

| | |
|---|---|
| **Responsibility** | Structured data — CSV/statistical series: schema, units, period, source; a different pipeline from prose documents |
| **Not responsible for** | Document ingestion (that is the existing `DocumentIngestor`) |
| **Failure modes** | a series without declared units or period is refused — an ANSD figure without its year is a wrong figure waiting to be cited |
| **Verification** | refusal tested before the happy path |

**No fifth agent.** Anything else the directive lists is a tool, a library, or
`coder` under another name.

---

## 7. Architectural consistency check

| Risk | Verdict |
|---|---|
| Duplicate planner | **avoided** — axes attach to `PlannerAgent`, no new planner |
| Duplicate memory | **avoided** — nothing here touches `src/memory_engine/` |
| Duplicate retrieval | **avoided** — entities are a new store, retrieval stays one path |
| Duplicate orchestration | **avoided** — the four agents run under the existing router |
| Unnecessary database | **avoided** — SQLite tables, with the written trigger for a graph DB |
| Unnecessary agents | **four, each with a decision of its own** |
| Unnecessary services | none introduced |

---

## 8. Ollama and C1 — documented, not touched

Per the directive: nothing is installed, downloaded or modified.

| Question | Measured answer |
|---|---|
| Which interface does GalSen expect? | `LocalProvider` speaks Ollama's HTTP API at `http://localhost:11434`: `GET /api/tags` to list, `POST /api/generate` to generate |
| Is the integration path verified? | **Yes, without a real model.** `tests/test_generation_end_to_end.py::TestChaineComplete` starts a minimal HTTP server speaking Ollama's protocol and traverses tool → manager → selector → provider → HTTP |
| Behaviour with no model? | `check_availability()` returns a named reason; generation returns `unavailable`; `/agri/advice` answers `503` with the reason. **Nothing is fabricated** |
| Deterministic smoke test? | **It already exists** — the fake-server test above. It runs today, green, with C1 closed |
| Minimum model capability? | Context window **≥ 8192** (`ProviderSelector`: `reasoning` and `code_generation` require it; `analysis` and `summarization` require 32 000; `document_analysis` 100 000) |

**The distinction the directive draws is exactly right and already encoded**: a
running server is infrastructure; the fake-server test proves the chain; only a
real end-to-end task on a real model proves functionality — and that test is
written and skips itself with a stated reason until a provider answers.

---

## 9. Implementation order

Dependency-driven, and it differs from the directive's default in one place,
with the reason.

| Rank | Chapter | Why here |
|---|---|---|
| **P0** | **A. Anti-injection foundation** | Every later chapter puts more external text into prompts — entities, benchmark, Senegalese sources. Building acquisition before the boundary means retrofitting it through nine paths instead of one |
| **P1** | **B. Language foundation L1–L3** | Small, blocks Senegalese ingestion, and nothing else depends on it being late |
| **P1** | **C. Factual evaluation, mechanical half** | Citation correctness and unsupported-claim counting need no model — they are measurable today |
| **P2** | **D. `verifier` + `senegal` agents** | Depend on C and on VOLET 35 ch. 04–05 |
| **P2** | **E. Entity/relation store + ontology** | Depends on A (entities come from documents) |
| **P2** | **F. Intent axes** | Depends on nothing; placed here because two of its axes feed D |
| **P3** | **G. `knowledge_architect` + `data_engineer`** | Depend on E |
| **P3** | **H. Acquisition deepening, infrastructure** | Triggers unmet — see §2.3 and the audit's §3.2 |

**Change from the directive's suggested order:** anti-injection moves from P1 to
**P0**. Evidence: nine entry paths, one boundary. Every chapter of VOLET 35 and
36 increases the volume of external text flowing into prompts, and the cost of
adding the boundary grows with each one.

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| Adding language codes is mistaken for language support | L2 ships the honest capability report **in the same chapter** as L1 |
| The benchmark stays empty and evaluation looks built but measures nothing | The evaluator **refuses to score** on `TO_SOURCE` entries and reports the count of verified entries — 0 is visible, not hidden |
| Entity extraction becomes knowledge by inference | Entities require a source; extraction proposes, never approves |
| The four agents drift into eleven | §6 names the non-responsibilities; a fifth agent needs an ADR |
| Anti-injection becomes a keyword filter | Tests assert the *structural separation* per entry path, not detector recall |
| Everything is built and C1 stays closed | Half of VOLET 36 (A, B, C mechanical, E, F) is measurable **without a model**. That is why it is ordered first |

---

## 11. Tests required

- **A**: one test per entry path proving a hidden instruction arrives as data; one proving flags do not delete content.
- **B**: a Wolof document ingested, stored, filtered and retrieved; the capability report says what is unknown.
- **C**: citation correctness on a claim present in the passage, absent from it, and contradicted; the evaluator refuses to score `TO_SOURCE`.
- **D**: `verifier` reports `cannot_verify` with no passages; `senegal` refuses a law question with no national source.
- **E**: entity round-trip with provenance; a relation carries its own sources and validity; traversal at depth 2.
- **F**: axes computed and reported; `RISK` and `GEOGRAPHIC_SCOPE` change behaviour, the others are observed only.

---

## 12. Acceptance criteria

1. No second planner, no second retrieval path, no new database — verified by the import graph.
2. A Wolof document is ingested and retrieved as Wolof; the capability report states what is UNKNOWN.
3. A prompt-injection attempt through **each** of the nine entry paths is neutralised, with a test per path.
4. Citation correctness and unsupported claims are measured on a benchmark whose verified-entry count is reported, even when it is 0.
5. The four agents exist, each refusing rather than guessing in its stated failure mode.
6. Entities and relations carry provenance; no entity exists without a source.
7. Full suite green, `ruff` clean, and CI green — the last one measured on GitHub, not locally.

---

## 13. Exact first implementation task

**Chapter A.1 — the trust envelope.**

Create `src/security/trust.py` generalising `src/mcp/client.py`: `TrustLevel`,
`wrap(content, level, origin)`, `inspect(content)`. Wire **one** caller —
`RAGTool._op_retrieve_for_prompt`, the designed path from external content to a
prompt — and ship the test proving an instruction hidden in a retrieved passage
reaches the model as data.

One caller, one test, one chapter. The other eight paths follow in A.2 and A.3.

---

## What VOLET 36 will **not** build

- No graph database (trigger written: depth > 3, ~100 000 entities, or > 200 ms).
- No vector database, object storage or event streams (VOLET 34 audit §3.2).
- No translation engine.
- No claim of Wolof, Pulaar or Serer *understanding* — only labelling, storage,
  lexical retrieval, and an honest report of what remains UNKNOWN.
- No fifth agent.
- No benchmark data written from memory.

---

## 14. Closing measurement — 2026-08-13

The eight chapters are delivered. Each criterion of §12, measured rather than
declared:

| # | Criterion | Measured verdict |
|---|---|---|
| 1 | No second planner, retrieval path or database | **Held.** The axes are a field on the existing plan (`agents/planner/agent.py`); a test asserts one planner in the registry. Entities use SQLite through `src/storage/`, no new engine |
| 2 | A Wolof document ingested and retrieved as Wolof | **Done** (`tests/test_languages.py`), and `language_support()` states what is `unknown` rather than `no` |
| 3 | A test per entry path | **Done** — nine paths wrapped, `src/security/trust.py::report()` publishes them and keeps `unwrapped_paths` at zero rather than removing the field |
| 4 | Citation correctness and unsupported claims measured on a benchmark reporting its verified count | **Done** — `docs/evaluation/senegal-facts.jsonl`: 10 questions, **0 verified**, and `score_entry()` refuses to score `to_source` entries |
| 5 | The four agents exist, each refusing in its failure mode | **Done** — `verifier` (`cannot_verify` with no passage), `senegal` (no national source, no answer), `knowledge_architect` (proposes, never applies), `data_engineer` (refuses an undeclared series) |
| 6 | Entities and relations carry provenance | **Done** — construction refuses either without a source; the report publishes `entities_without_source` so a bypass would show |
| 7 | Suite green, `ruff` clean, CI green | Suite and `ruff` measured green locally at each chapter. **CI measured on GitHub on 2026-08-13** (run 31704148980, branch head `ea54664`): **2893 passed, 5 skipped, 1 failed** — the failure is `test_release_check.py::test_l_etiquette_de_la_version_courante_existe_bien`, red because the `v0.1.0` tag was never pushed. It predates VOLET 36 and is **blocked on the operator**: the development proxy refuses tag pushes (403, re-checked today) and no available API tool creates a tag. The test is correct and stays as it is |

**What VOLET 36 did not build, and why it did not**: no vector database, no
graph database, no queue, no object storage for knowledge, no automated
acquisition. Those triggers are no longer a paragraph — they are measured at
every proactive scan (`src/knowledge_engine/deferred_triggers.py`), and the
detector stays silent until one is crossed.

**What is still open, and depends on nobody in this repository**: C1 — a local
model — gates generation and semantic retrieval, in Wolof as elsewhere; and the
Senegalese corpus needs real declared documents. Both are named in
`docs/memory/session-state.md`, neither is hidden behind a plausible number.
