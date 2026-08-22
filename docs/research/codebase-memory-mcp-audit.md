# codebase-memory-mcp — component audit #01

**Owner's brief**: 2026-08-22, phases 0–12 + a 25-point report.
**Phase plan**: `docs/memory/phase-plan.md` — 13 chapters, 16 phases.
**Status**: *in progress*, written phase by phase. A section not yet reached is
absent rather than guessed.

**Audit only.** Nothing is integrated, no schema, API or test is modified.

---

## PHASE 0 — GalSen IA's own state, measured

Measured on the repository at `8f64379`, not recalled. The brief's 16 points,
answered in the order they were asked.

### 1–2. Architecture and memory

| Subsystem | Size | What it is |
|---|---|---|
| `src/memory_engine/` | **13 modules** | The product's memory: layers, cache, indexer, ranker, retriever, summariser, quality, store |
| `src/embeddings/` | 6 modules | `vector_store.py` (SQLite + NumPy cosine), `semantic_index.py`, `registry.py`, a sentence-transformers provider |
| `docs/memory/` | 7 files | The **repository's** engineering memory, injected at session start |

Two memories, different lifetimes, deliberately separate.

### 3. Knowledge

`src/knowledge_engine/` — **38 modules.** Two axes on every item (scope,
subject); law, administration and languages never fall back to global knowledge;
nothing enters without a source (ADR-021).

### 4. Graph — `src/agent/repo_graph.py`, 404 lines

`RepoGraph` builds an **import graph** from Python AST: `build()`, `files()`,
`imports_of()`, `imported_by()`, with dotted-name resolution to repository
modules. **Nodes are files; edges are imports.** Nothing finer.

### 5. Code index — `src/agent/symbol_index.py`, 323 lines

`SymbolIndex` parses with `ast`, extracts `Symbol` (classes, functions, async
functions, nested via a `descendre` walk), plus `_noms_utilises` — names *used*
in a file. Public surface: `definitions(name)`, `symbols_in(path)`.
`repo_map.py` (263 lines) sits beside it.

**So GalSen IA already has an AST-based symbol index and an import graph.** They
are `ast`-based, Python-only, in-process, rebuilt by `build()`.

### 6. MCP — `src/mcp/`, 4 modules

`server.py` (`MCPServer`) speaks JSON-RPC: `initialize`, `tools/list`,
`tools/call`, with an identity per token, an audit trace on every call
(`_tracer`), and `exposure_report()`. `client.py` treats external text as data
(`src/security/trust.py`). `exposure.py` decides what is exposed.

**GalSen IA is an MCP *server*, and a client.** A third-party MCP server would be
a peer, not a new capability class.

### 7–8. Code and file search

`src/services/search/` — `manager.py`, `providers.py`, `governance.py`,
`excerpt.py`. Measured earlier this session: vision reports *"the engine analyses
an image and produces no indexed text"* rather than pretending four sources
answered.

### 9. Structural understanding

`repo_graph` + `symbol_index` + `repo_map`, plus the **`code-review-graph` MCP
server already wired into this repository** (`CLAUDE.md`): Tree-sitter parsing,
callers/dependents/test-coverage, `get_impact_radius_tool`,
`get_affected_flows_tool`, communities, wiki generation.

**That last one matters for the whole audit**: a persistent, incremental,
Tree-sitter code graph exposed over MCP is *already in use here*. The subject is
not entering empty space.

### 10. Impact analysis

`src/agent/capabilities_reach.py` — `agent_reach()`, which reports what an agent
context can reach. **Not** a code-level blast radius; that is
`code-review-graph`'s `get_impact_radius_tool`.

### 11. Provenance

`src/acquisition/` — `record.py`, `parsing.py`, `metadata.py`, `gate.py`,
`quality.py`, `manifest.py`. Entities *and* relations carry their own provenance;
reliability comes from `corpus/sources/senegal.yaml`, never from the document
claiming it.

### 12. Security

`src/security/` (`trust.py`, `checkpoints.py`, `isolation.py`, `posture.py`,
`redaction.py`), `src/sandbox/` (`policy.py`, `runner.py`), `src/api/rbac.py`
(10 roles, 24 permissions), `src/tool/authorization.py` (role ceilings),
`src/approval_engine/`, ADR-018's unconditional refusals.

### 13. Self-healing

`src/agent/` — 23 modules: `self_healer.py`, `policies/immutability.py`,
`policies/integrity.py`, `guarded_editor.py`, `audit/journal.py`,
`tools/commands.py` (a command is a list, never a string).

### 14. Tests

**7027 passed, 9 skipped, 3 deselected** — measured in this message.
333 files. Relevant here: `tests/test_repo_graph.py`, `tests/test_mcp.py`,
`tests/agent/` (8 files).

### 15. ADRs

**39.** Relevant: ADR-005 (SQLite persistence), ADR-015 (embeddings and semantic
retrieval), ADR-021 (acquisition and provenance), ADR-037 (twelve projects, zero
integrated), ADR-038 (Superpowers as prose, nothing installed).

### 16. Dependencies

**19 runtime dependencies**, all pinned. `fastapi`, `pydantic`, `uvicorn`,
`PyYAML`, `starlette`, `Pillow`, `opencv-python-headless`, `numpy`,
`cryptography`, `pypdf`, `python-docx`, `openpyxl`, `python-pptx`, `markdown`,
`pytesseract`, `boto3`, `PyJWT`, `bcrypt`, `requests`.

**No graph database, no Tree-sitter, no embedding model, no MCP client library.**
That is the baseline any integration cost is measured against.

---

## PHASE 1 — The official repository

| | |
|---|---|
| Repository | `https://github.com/DeusData/codebase-memory-mcp` |
| **Commit examined** | **`010569fa6ce1bc5d6430f858129243ea1a2e3fd5`** |
| Date | 2026-08-21T10:44:22+02:00 |
| Subject | *"Merge pull request #1678 from musichen/fix/pi-extension-tool-schemas"* |
| How obtained | `git clone --depth 1` through the session git proxy; `origin` verified before reading |
| **Size** | **1.3 GB** excluding `.git` — 2 052 files in the working tree |

`raw.githubusercontent.com` → 200, `api.github.com` → 403. As in the previous
audit, the clone is what makes the commit measurable instead of `UNKNOWN`.

### What it is made of — measured, and the first surprise

| Extension | Files |
|---|---:|
| `.c` | **842** |
| `.h` | **683** |
| `.sh` | 109 |
| `.tsx` | 38 |
| `.py` | 35 |
| `.ts` | 15 |

**This is a C project.** Not Python, not TypeScript. The README states it
directly — *"Pure C — no language runtime"*.

| Directory | Size |
|---|---:|
| `internal/cbm/` | **1.2 GB** |
| `vendored/` | 43 MB |
| `tests/` | 11 MB |
| `src/` | 6.2 MB |
| `graph-ui/` | 636 KB (the `.tsx`) |

The 1.2 GB is `internal/cbm/vendored/grammars/` — **160 Tree-sitter grammars**,
each a generated `parser.c`. That is not bloat; it is what "158 languages" costs
on disk.

### Licence — MIT, and the vendored tree is where the real work is

`LICENSE`: **MIT, Copyright (c) 2025 DeusData**, 21 lines.

`THIRD_PARTY.md` (154 lines) is unusually complete, and **§6 of the brief
forbids assuming the main licence covers the rest**, so the vendored components
are listed as they are declared:

| Component | Declared licence |
|---|---|
| Tree-sitter runtime + 160 grammars | MIT (per-grammar summary in the file) |
| SQLite 3 | **Public Domain** |
| mimalloc, yyjson, Verstable | MIT |
| xxHash, TRE, LZ4 | BSD-2-Clause |
| Zstandard | BSD-3-Clause (**dual BSD/GPLv2 — BSD selected**) |
| simplecpp | 0BSD |
| wyhash | Unlicense |
| **`vendored/nomic/`** | **Apache-2.0** — `nomic-ai/nomic-embed-code` |

**`vendored/nomic/` is the finding of this phase.** It is a **30 MB int8-quantised
token-vector blob** derived from an embedding model, compiled into the binary via
`code_vectors_blob.S`. So the project ships model weights — Apache-2.0, with a
`NOTICE` naming the source model and Nomic AI.

Verification of each declared licence against its upstream is **phase 6**, not
this one. What is recorded here is that the declarations exist, are specific, and
name paths.

### Security posture, as the project states it

`SECURITY.md` exists. The README's own security paragraph is quoted rather than
paraphrased, because §1 says not to use the README as proof — this is the claim,
not the evidence:

> *"This tool reads your codebase and **writes to your agent configuration
> files**. That is what it is designed to do… All processing happens 100% locally;
> your code never leaves your machine."*

Also claimed: three executable candidates submitted to VirusTotal per release,
SLSA 3, OpenSSF Scorecard. **Phase 7 verifies the writes and the network claim in
code.** The configuration-file write is the surface to examine first.

### CI

Eight workflows: `_build`, `_lint`, `_security`, `_smoke`, `_soak`, `_test`,
`bug-repro`, `cache-warm`. Plus `.clang-format`, `.clang-tidy`, `.cppcheck`,
`flake.nix`, a `DCO`, `MAINTAINERS.md`, `CONTRIBUTING.md`, `install.sh`,
`install.ps1`.

### Claims recorded, not accepted

The README asserts: 6 768 tests, 158 languages, full index of an average
repository in milliseconds, the Linux kernel (28M LOC) in 3 minutes, sub-1 ms
structural queries, 15 MCP tools, 43 client surfaces, and an arXiv preprint
(2603.27277) reporting 83 % answer quality, 10× fewer tokens and 2.1× fewer tool
calls across 31 repositories.

**None of these is verified yet.** They are the subject of phases 2 and 8.
Recorded here so phase 8 measures rather than repeats them.

---

## PHASE 2 — What the project actually does

The brief's 16 points, answered from the C source rather than the README.

### 1–2. Indexing and graph construction

Tree-sitter AST parsing → a pipeline (`src/pipeline/`) → SQLite. The persisted
schema, read from the `CREATE TABLE` statements in the source:

```
projects            nodes            edges            file_hashes
node_vectors        token_vectors    project_summaries
```

with indexes on `nodes(file, label, name)` and on
`edges(source, target, type, source_type, target_type, url_path)`.

**A property graph in SQLite**, not a graph database. The `url_path` index on
`edges` is the HTTP-route/cross-service claim made concrete.

### 3. Node types

Counted from string literals in the C: `function`, `class`, `method`, `struct`,
`interface`, `enum`, `trait`, `field`, `variable`, `module`, `package`, `import`,
`file`, `type`.

**Fourteen kinds.** GalSen IA's `symbol_index.py` has three (class, function,
async function) and `repo_graph.py` has one (file).

### 4. Relation types

`CALLS`, `IMPORTS`, `EXTENDS`, `IMPLEMENTS`, `DEFINES`, `CONTAINS`, `RETURNS`,
`THROWS` — appearing in both upper and lower case in the source.

**GalSen IA has exactly one relation: `imports`.** That is the single widest
capability gap measured so far.

### 5. Queries and the MCP surface

Tool names read from the source: `index_repository`, `index_status`,
`list_projects`, `get_project`, `explore_codebase`, `get_architecture`,
`get_code_snippet`, `get_graph_schema`, `find_arch_docs`, `graph_ui`.

`src/daemon/application.c` carries a **tool profile** concept
(`CBM_MCP_TOOL_PROFILE_ALL`, `…_SCOUT`) — the exposed set is configurable.

### 6–7. Change detection and incremental update

`file_hashes` in the schema, and `src/pipeline/pipeline_incremental.c` —
`cbm_store_get_file_hashes` compares stored hashes against the tree and reindexes
only what moved. **Incremental indexing is real and content-hash-based**, not a
timestamp heuristic.

### 8–9. Persistence and location

SQLite at `%s/%s.db` under a `.cbm` directory in `$HOME`. **On the user's
machine, in their home directory.**

### 10. Does data leave the machine? — verified, not taken from the README

The README claims *"All processing happens 100% locally; your code never leaves
your machine."* Checked in the C rather than believed:

- `curl_*`, `getaddrinfo`, `gethostbyname`, `SSL_connect` → **no matches in
  `src/`.**
- Three `AF_INET` sites exist. `src/main.c:1906` sets
  `s_addr = htonl(0x7F000001U)` — **127.0.0.1**, the daemon control socket.
  `src/ui/httpd.c` is the local graph UI server. `src/daemon/ipc.c` uses
  `AF_UNIX`, with a comment stating it keeps *"the only raw connect call at a
  sockaddr_un-typed boundary"*.

**The claim survives this check**: no outbound network path was found in `src/`.
Recorded as *no outbound path found in `src/`*, which is narrower than "none
exists" — `internal/cbm/` was not swept, and phase 7 owns that.

### 11. How MCP is used

It **is** an MCP server, spoken over stdio/local socket by a client. It is not an
MCP client of anything.

### 12–13. What needs an LLM, and what is deterministic

Grepping `openai`, `anthropic`, `api_key`, `gemini` in `src/` returns hits in
four files — and reading them changes the answer entirely. In
`src/cli/agent_profiles.c` the only matches are
`CBM_GRAPH_DIALECT_CLAUDE` and `…_GEMINI`: **output dialects**, not API clients.

**Nothing in the indexing, graph or query path requires a model.** Tree-sitter
parsing, hashing and SQLite queries are deterministic. The one model-derived
artefact is the vendored 30 MB `nomic` token-vector blob used for semantic
similarity — **shipped weights, computed locally, no key, no endpoint**.

### 14–16. External dependencies, mandatory and optional

**None external.** Everything is vendored: SQLite, mimalloc, yyjson, xxHash, TRE,
LZ4, Zstandard, simplecpp, Verstable, wyhash, Tree-sitter and 160 grammars.
No package manager, no language runtime — the README's *"Pure C"* claim is
consistent with the tree.

### The surface that matters most, found here rather than in phase 7

`src/cli/agent_profiles.c` writes into **agent configuration files in `$HOME`**:

```
~/.claude.json                      ~/.codeium/windsurf/mcp_config.json
~/.augment/settings.json            ~/.codeium/windsurf/memories/global_rules.md
~/.augment/rules/codebase-memory.md ~/.config/crush/crush.json
~/.augment/agents/codebase-memory.md ~/.config/amp/AGENTS.md
~/.bob/rules/codebase-memory.md     ~/.config/kilo/agents/codebase-memory.md
~/.codebuddy/CODEBUDDY.md           …
```

The README says so plainly — *"writes to your agent configuration files. That is
what it is designed to do"* — and the code confirms it. **It writes instruction
files that steer coding agents**, which is the same class of surface ADR-038
weighed for Superpowers and decided against on the plugin path.

Phase 7 prices it. Recorded here because it was found while answering point 9.

---

## PHASE 3 — Comparison matrix

**The comparison is three-sided, and reducing it to two would produce the wrong
answer.** GalSen IA's structural understanding today comes from *two* places: its
own Python modules, and **the `code-review-graph` MCP server already wired into
this repository** (`CLAUDE.md`). Any capability the subject offers must be
compared against both.

`CRG` = code-review-graph, already in use. `GIA` = GalSen IA's own code.

| # | Capability | codebase-memory-mcp | GalSen IA existing | Overlap | Advantage | Risk | Action |
|---|---|---|---|---|---|---|---|
| 1 | Code intelligence | 158 languages | GIA: Python only · CRG: Tree-sitter, multi-language | **CRG: high** | Subject, on breadth | Duplicates CRG | **KEEP** |
| 2 | AST | Tree-sitter, 160 grammars | GIA: `ast`, Python · CRG: Tree-sitter | **CRG: high** | Subject, marginally | — | **KEEP** |
| 3 | Knowledge graph | SQLite property graph, 14 node kinds | GIA: files+imports · CRG: full graph | **CRG: high** | Subject over GIA | — | **KEEP** |
| 4 | Structural search | 15 MCP tools | CRG: `query_graph_tool` | **CRG: high** | Comparable | — | **KEEP** |
| 5 | Semantic search | 30 MB vendored `nomic` blob, local | GIA: `semantic_index.py` + `vector_store.py` (**needs a provider, C1 open**) · CRG: `semantic_search_nodes_tool` | Partial | **Subject: works with no provider** | — | **NOTE** |
| 6 | Symbol relations | 8 relation types | GIA: **1** (`imports`) · CRG: callers/callees | **CRG: high** | Subject over GIA | — | **KEEP** |
| 7 | Call graph | `CALLS` edges | GIA: **none** · CRG: yes | **CRG: high** | Subject over GIA | — | **KEEP** |
| 8 | Data flow | Not found in the schema | Neither | — | — | — | **NONE** |
| 9 | Architecture | `get_architecture`, `project_summaries` | CRG: `get_architecture_overview_tool` | **CRG: high** | Comparable | — | **KEEP** |
| 10 | Impact analysis | Graph traversal | GIA: `agent_reach()` (agent scope, not code) · CRG: `get_impact_radius_tool` | **CRG: high** | Comparable | — | **KEEP** |
| 11 | Dead code | Not found | CRG: `refactor_tool` | CRG | CRG | — | **KEEP** |
| 12 | Cross-service | `edges.url_path` index, HTTP routes | **Neither** | **None** | **Subject, uniquely** | — | **NOTE** |
| 13 | Cross-repository | Multi-project (`projects` table) | CRG: `cross_repo_search_tool` | CRG | Comparable | — | **KEEP** |
| 14 | MCP | Server, 15 tools, tool profiles | GIA: **server + client**, per-token identity, audit trace · CRG: server | High | GIA on governance | — | **KEEP** |
| 15 | Persistent memory | SQLite in `~/.cbm/` | GIA: `memory_engine` (13) + `docs/memory/` | **None — different objects** | Not comparable | — | **NONE** |
| 16 | Incremental indexing | Content hashes, `file_hashes` | GIA: `build()` **rebuilds everything** · CRG: auto-updates on file change via hooks | **CRG: high** | Subject over GIA | — | **KEEP** |
| 17 | Synchronisation | Daemon, loopback control socket | CRG: hooks | CRG | Comparable | — | **KEEP** |
| 18 | Long context | Not its subject | — | — | — | — | **NONE** |
| 19 | Context reduction | Claims 10× fewer tokens (**unverified**) | CRG: `get_minimal_context_tool`, `detail_level="minimal"`, documented target ≤ 800 tokens | **CRG: high** | `UNKNOWN` until phase 8 | — | **KEEP** |
| 20 | Targeted retrieval | `get_code_snippet` | CRG: `get_review_context_tool` | **CRG: high** | Comparable | — | **KEEP** |
| 21 | Security | Local-only, **writes agent config files** | GIA: `trust.py`, RBAC, sandbox, ADR-018 | None | **GIA, decisively** | **The config write** | **PHASE 7** |
| 22 | Provenance | Not found in the schema | GIA: `src/acquisition/`, per-entity and per-relation | **None** | **GIA, decisively** | — | **KEEP** |
| 23 | Observability | `index_status` | GIA: `trail.py`, `audit_engine`, `decision_trace` | Low | **GIA** | — | **KEEP** |
| 24 | Performance | Claims sub-1 ms, kernel in 3 min | GIA vector store: **0.463 ms at 271 vectors** (measured) | — | `UNKNOWN` until phase 8 | — | **PHASE 8** |

### What the matrix says

**Sixteen of 24 rows are `KEEP` because `code-review-graph` already covers them.**
Not because GalSen IA's own Python covers them — on rows 6, 7 and 16 its own code
is measurably behind. The thing that closes those gaps is already installed.

**Three rows are not covered by anything here:**

- **Row 12, cross-service links.** `edges.url_path` indexes HTTP routes across
  services. Neither GIA nor CRG has this. Genuinely unique.
- **Row 5, semantic search with no provider.** GalSen IA's semantic retrieval is
  gated on criterion C1 (`ollama serve`), open since the beginning. The subject
  ships a 30 MB quantised blob and needs nothing. **That is the one place where
  the subject solves a problem this repository actually has today.**
- **Row 8, data flow** — neither has it, and the subject does not claim it.

**Two rows are `GIA, decisively`**: provenance (rows 22) and security
governance (21). The subject has no provenance model at all, which for an
indexing tool is normal and for GalSen IA would be a regression if it replaced
anything.

**One row is a risk rather than a capability**: row 21. It writes instruction
files into `$HOME` that steer coding agents.

### The comparison that decides more than the table

The subject is **1.3 GB of C** producing a graph in SQLite. `code-review-graph`
is **already running**, already hooked to file changes, and already answering the
same questions through MCP. Adopting the subject would mean **running two code
graphs over the same repository**.

`.claude/rules/spec-driven-governance.md`: *"Prefer reuse over rebuild. A working
component is not replaced because another approach looks cleaner."*

---

## PHASE 4 — Two usages, kept apart

The brief insists these are different questions, and it is right: the same
component can be excellent in one and wrong in the other.

### A. Used by the coding agent while GalSen IA is being built

**This is where the tool belongs, if anywhere.** It indexes a repository and
answers structural questions over MCP — exactly the job `code-review-graph` does
here today.

The honest comparison is therefore **not** *"tool versus nothing"* but *"tool
versus the tool already installed"*:

| | codebase-memory-mcp | code-review-graph (installed) |
|---|---|---|
| Languages | 158 | Tree-sitter, multi-language |
| Semantic search | **local blob, no provider** | `semantic_search_nodes_tool` |
| Cross-service HTTP routes | **yes** | not offered |
| Incremental | content hashes | auto-updates on file change |
| Context reduction | claimed 10× (**unverified**) | documented ≤ 800 tokens/task |
| Install cost | **1.3 GB, a C build or a binary**, writes to `$HOME` config | already running |

**Replacing a working, wired-in tool with a 1.3 GB one to gain two capabilities —
one of them unverified — is not a trade this repository's rules support.** Running
both means two graphs over the same tree.

**Verdict for usage A: the case is not made, and it is not close.** The one thing
that would change it is a measured context-reduction win over CRG — phase 8.

### B. Integrated into GalSen IA after deployment

**No.** And the reasons are structural rather than a matter of taste.

1. **GalSen IA is a Python platform with 19 pinned pure-Python dependencies and
   no compiled extension of its own.** This is 1.3 GB of C requiring a toolchain
   or a per-platform binary. Every platform GalSen IA must serve — web, Windows,
   macOS, Linux, Android, iOS (`.claude/rules/core-rules.md`) — would need one.
2. **GalSen IA does not index its users' code.** It serves agriculture, health,
   education, administration and Wolof knowledge. A code-intelligence engine has
   no user-facing function in it. The only in-repo consumer would be
   `src/coding_engine/`, whose three backends are all unavailable and which
   refuses every execution until `GALSEN_CODING_WORKSPACE_ROOTS` is declared.
3. **It writes instruction files into `$HOME`.** In a deployed platform that is
   not a feature; it is an unbounded write outside any workspace, and
   `src/coding_engine/workspace.py` exists precisely to forbid that class of act.

**Verdict for usage B: rejected, on architecture rather than on quality.**

### The distinction that matters

The subject is a **developer tool**, and a good one. GalSen IA is a **platform for
end users**. The brief's warning — *"do not reduce its architecture to coding"* —
cuts against usage B: adopting a code-intelligence engine into the runtime would
be exactly that reduction.

---

## PHASE 5 — Model independence

Checked in the C, not inferred from the README.

| Provider | Found in `src/`? |
|---|---|
| Claude / Anthropic API | **No.** `CBM_GRAPH_DIALECT_CLAUDE` is an **output dialect**, not a client |
| OpenAI | **No.** |
| Gemini | **No.** `CBM_GRAPH_DIALECT_GEMINI`, same thing |
| Any external API key | **No.** No `api_key` read, no endpoint constant |
| Embedded LLM | **No.** |
| Local model server | **Not required.** |

`curl_*`, `getaddrinfo`, `gethostbyname`, `SSL_connect`: **no matches in `src/`.**
The only `AF_INET` connect targets `htonl(0x7F000001)` — 127.0.0.1.

### The one model-derived artefact

`vendored/nomic/` — a **30 MB int8-quantised token-vector blob** derived from
`nomic-ai/nomic-embed-code`, Apache-2.0, compiled in via `code_vectors_blob.S`.

**It is weights, not a client.** No download, no key, no endpoint, no inference
server. Semantic similarity is computed locally from a table that ships with the
binary.

### Verdict

**The project is genuinely provider-independent**, and more so than GalSen IA is
today: GalSen IA's own semantic retrieval is blocked on criterion C1
(`ollama serve`) and answers `503` without it, while this needs nothing.

Two limits stated rather than glossed:

- The sweep covered **`src/`**. `internal/cbm/` (1.2 GB, mostly generated
  grammars) was not swept; phase 7 owns it. The claim is *"no provider dependency
  found in `src/`"*, not *"none exists anywhere"*.
- Provider independence says nothing about the **agent-config write**. That is a
  different risk, and it is phase 7's.

---

## PHASE 6 — Licence matrix

Declared licences counted from `THIRD_PARTY.md` (154 lines), which is unusually
specific — it names paths, not just projects.

### LICENCE COMPATIBLE

| Component | Licence | Note |
|---|---|---|
| codebase-memory-mcp itself | **MIT** © 2025 DeusData | Compatible with ADR-036 (Apache-2.0) |
| Tree-sitter runtime + grammars | MIT (14 declarations) | |
| mimalloc, yyjson, Verstable | MIT | |
| SQLite 3 | **Public Domain** | |
| wyhash | Unlicense | |
| xxHash, TRE, LZ4 | BSD-2-Clause | |
| Zstandard | BSD-3-Clause | Dual BSD/GPLv2 upstream — **BSD explicitly selected** |
| simplecpp | 0BSD | |
| Several grammars | Apache-2.0 (6), BSD-3 (3), BSD-2 (3), ISC (2) | |
| **`vendored/nomic/`** | **Apache-2.0**, © Nomic AI | Weights, with a `NOTICE` naming the source model |

### LICENCE À SURVEILLER

**One, and it is a discipline note rather than a defect**: `vendored/nomic/` is
**model weights**, not code. Apache-2.0 applies as declared, and the `NOTICE`
file must travel with any redistribution. GalSen IA redistributes nothing here,
so the obligation is dormant — but it would wake the moment a binary were
shipped.

### LICENCE INCOMPATIBLE

**None found.**

### A false finding, caught and recorded

A first count reported **7 MPL matches** — MPL being weak copyleft, that would
have been the audit's most important licence finding. Reading the matches in
context rather than trusting the count:

```
/vendored/simplecpp/` | 0BS        ← si·mpl·ecpp
 Reference implementation /        ← i·mpl·ementation
```

**There is no MPL anywhere**; `grep -iE "MPL-|Mozilla Public"` returns nothing.
Recorded because a licence matrix built on that count would have been wrong in
its headline, and because `.claude/skills/systematic-debugging` phase 1 says to
read the output completely rather than act on a number.

### The limit of this phase

These are **declarations**. §6 warns against assuming a repository's licence
covers its dependencies — that is why each is listed separately. It does **not**
extend to verifying each of 160 grammars against its own upstream: that would be
160 fetches, and `api.github.com` answers 403 here.

**Verified-against-upstream count: `UNKNOWN`.** What is verified is that the
declarations exist, name paths, and contain no copyleft.

---

## PHASE 7 — Security

Thirteen surfaces, measured.

| Surface | Finding |
|---|---|
| Filesystem read | The indexed repository — its purpose |
| **Filesystem write** | **`~/.cbm/*.db`, and agent config files in `$HOME`** — see below |
| Process execution | Runs as a daemon; **`internal/cbm/` swept, no outbound call** |
| **Network** | The phase-2 debt is now paid: `curl_*`, `gethostbyname`, `SSL_connect`, `socket(AF_INET` → **no matches in `internal/cbm/`**. One `getaddrinfo` hit, in `lsp/generated/python_stdlib_data.c` — a **generated table of Python stdlib symbol names**, not a call. Second false positive of this audit, caught by reading the match. |
| Config writes | **The finding.** See below |
| Permissions | No privilege escalation found; `install.sh` does not call `sudo` |
| Local storage | SQLite under `$HOME/.cbm/` |
| Sensitive data | Source code and its graph, local |
| Secrets | No `api_key` read, no credential constant |
| Sandboxing | **None of its own.** It is a native binary |
| Injection | Not assessed — `UNKNOWN` |
| **Supply chain** | `curl … | bash`, mitigated — see below |
| Automatic install | `install.sh` / `install.ps1` |

### The privileged operation, named precisely

`src/cli/agent_profiles.c` writes into **agent configuration and instruction
files under `$HOME`**:

```
~/.claude.json                        ~/.config/crush/crush.json
~/.augment/settings.json              ~/.config/amp/AGENTS.md
~/.augment/rules/codebase-memory.md   ~/.config/kilo/agents/codebase-memory.md
~/.codeium/windsurf/mcp_config.json   ~/.codeium/windsurf/memories/global_rules.md
~/.bob/rules/codebase-memory.md       ~/.codebuddy/CODEBUDDY.md
```

Two kinds, and the second is the one that matters:

1. **MCP registration** (`mcp_config.json`, `.claude.json`) — declaring itself to
   a client. Ordinary for an MCP server.
2. **Instruction files** (`global_rules.md`, `AGENTS.md`,
   `codebase-memory.md`) — **text that steers a coding agent's behaviour.**

The README states it without hedging: *"This tool reads your codebase and writes
to your agent configuration files. That is what it is designed to do."* The code
confirms it. **It is disclosed, not hidden**, which is the difference between a
risk and a defect.

But it is **the same class of surface ADR-038 weighed for Superpowers and decided
against on the plugin path**: an external component writing instructions that
steer the agent working on this repository, outside any review. There, the
instructions arrived by auto-update; here they arrive by installer. The property
that mattered — *`src/security/trust.py`: external text is data with an origin,
never an instruction* — is inverted the same way.

### Supply chain

The documented install is `curl -fsSL … | bash`. Mitigations found in the script
itself, not claimed:

- Wrapped so a partial transfer cannot execute (`install.sh:14`)
- `CBM_DOWNLOAD_URL` must be `https://` or an explicit loopback address
- **`checksums.txt` is downloaded and verified**, with a 1 MiB sanity bound

Better than most `curl | bash` installers. It remains `curl | bash`.

### Verdict

**No destructive or hidden operation found.** One privileged operation, disclosed
and real: writing agent instruction files into `$HOME`.

Two limits: injection resistance was **not assessed** (`UNKNOWN`), and the sweeps
covered `src/` and `internal/cbm/` C sources — not the 160 generated grammar
parsers, which are Tree-sitter output.

---

*Phases 0 to 7 complete (11 of 16). Phase 8 — performance — has not started.*
