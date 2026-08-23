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

## PHASE 8 — Performance

### Their published numbers, and their method

Unusually, the method is published rather than only the results.

| Operation | Claimed | Notes given |
|---|---|---|
| Linux kernel full index | **3 min** | 28M LOC, 75K files → 4.81M nodes, 7.72M edges |
| Linux kernel fast index | 1 min 12 s | 1.88M nodes |
| Django full index | ~6 s | 49K nodes, 196K edges |
| Graph query | **< 1 ms** | relationship traversal |
| Name search (regex) | < 10 ms | SQL `LIKE` pre-filter |
| Dead-code detection | ~150 ms | full graph scan |
| Call-path trace (depth 5) | < 10 ms | BFS |

**Platform: Apple M3 Pro.** Stated, which is more than most projects do.

`docs/BENCHMARK.md` publishes the answer-quality method too: 63 languages, 12
questions each, up to 5 attempts with escalating retries, real repositories
(78–49 000 nodes), PASS/PARTIAL/FAIL grading with N/A excluded, Apple M3 Pro,
dated 2026-03-01.

The token claim: *"Five structural queries consumed ~3 400 tokens versus
~412 000 via file-by-file grep exploration — a 99.2 % reduction."*
The arXiv preprint (2603.27277) claims 83 % answer quality, 10× fewer tokens and
2.1× fewer tool calls across 31 repositories.

### What is wrong with taking those numbers into a decision

Three things, and none is an accusation of dishonesty:

1. **The baseline is chosen by the author.** *"File-by-file grep exploration"* is
   the worst plausible alternative. The relevant baseline for GalSen IA is
   **`code-review-graph`**, which also returns targeted graph answers and
   documents a ≤ 800-token target per task. Against *that*, the reduction is
   **`UNKNOWN`** — and it is the only comparison that decides anything here.
2. **Apple M3 Pro is not this machine, and not a Senegalese deployment target.**
3. **"Up to 5 attempts with escalating retry strategies"** is a generous grading
   protocol. It is disclosed, which is to the project's credit, but a
   first-attempt figure would mean something different.

### The independent benchmark, defined — and not run

§8 says to define one and forbids fabricating results. Defined:

| | |
|---|---|
| **Question** | Does it answer a real GalSen IA structural question in fewer tokens than `code-review-graph`, on the same repository? |
| **Corpus** | This repository — 333 test files, ~500 Python modules |
| **Tasks** | The five that actually recur here: *who calls `resolve_workspace`* · *what breaks if `RunStatus` changes* · *which tests cover `src/embeddings/`* · *where is the approval gate for training exports* · *what does `/coding/task` reach* |
| **Metric** | Tokens returned and tool calls, per task, both engines |
| **Control** | Same questions, same day, same machine |
| **Refusal** | No number is written that was not produced by a run |

### Whether it could be run here — measured, not guessed

`cc` is **GCC 13.3.0**, `make` is **GNU Make 4.3**. `Makefile.cbm` exists. So a
build is **plausible** — and it was **not attempted**, deliberately:

- Compiling 842 `.c` files plus 160 grammar parsers is a long build whose
  duration is `UNKNOWN` here, and the container's writable disk is a fixed
  allowance already holding a 1.3 GB clone.
- **The benchmark's decisive arm cannot run at all**: measuring against
  `code-review-graph` requires its MCP tools, and this session has watched that
  server disconnect and reconnect twice. A one-sided measurement would answer the
  question the README already answers.

### Result

**`NOT_MEASURED`.** No performance figure in this audit is mine, and none of
theirs is treated as verified.

**The measurement that would matter — tokens against `code-review-graph` on this
repository — has not been made, and phase 9 must treat the context-reduction gain
as `UNKNOWN` rather than as claimed.**

---

## PHASE 9 — Feasibility gates

| # | Question | Answer |
|---|---|---|
| 1 | Technically possible? | **Yes** — MCP server, spoken by any MCP client |
| 2 | Architecturally sound? | **For development, contested** (it duplicates CRG). **For the runtime, no** — phase 4B |
| 3 | Performance sufficient? | **`UNKNOWN`** — phase 8, not measured here |
| 4 | Memory cost acceptable? | **`UNKNOWN`** — RAM-first pipeline, unmeasured here |
| 5 | Storage acceptable? | **1.3 GB source, plus a graph DB per project.** Acceptable on a workstation; not on this container's allowance |
| 6 | Latency acceptable? | Claimed sub-ms, **`UNKNOWN` here** |
| 7 | Context gain measurable? | **Measurable in principle, not measured.** Against CRG rather than against grep — the comparison that decides |
| 8 | Errors detectable? | **Yes** — `index_status`, and it is a separate process |
| 9 | Fallback exists? | **Yes, and it is the incumbent**: CRG, plus `grep`/`Glob` |
| 10 | Easy to remove? | **Yes** for the MCP registration. **Partly, no** for the instruction files it writes into `$HOME` — removing the tool does not remove `global_rules.md` |
| 11 | Replaceable later? | **Yes** — MCP is the seam |
| 12 | Creates provider lock-in? | **No.** Phase 5: genuinely provider-independent |
| 13 | Creates architectural lock-in? | **For development, no.** For the runtime, **yes** — a C dependency in a pure-Python platform serving six targets |
| 14 | Respects provenance / privacy / security? | **Privacy yes** — nothing leaves the machine, verified. **Provenance no** — it has no provenance model. **Security: one disclosed privileged write** |

### The three that decide

**#9 — a fallback exists, and it is already running.** That reframes everything:
this is not a capability GalSen IA lacks, it is a second supplier of one it has.

**#10 — removal is not clean.** Uninstalling leaves instruction files it wrote
into `$HOME`. For a component whose whole risk is *writing text that steers an
agent*, "easy to remove" not being fully true is the gate that matters.

**#3 and #7 are `UNKNOWN`** — and they are precisely the two that would justify
adopting it anyway.

---

## PHASE 10 — Four options

### OPTION A — Integrate nothing

**Architecture.** Unchanged. The clone is deleted; this document remains as the
record.

**Advantages.** Zero cost, zero risk. `code-review-graph` keeps answering the
structural questions, and 16 of 24 capability rows are already covered.

**Disadvantages.** Three capabilities stay unavailable: cross-service HTTP
route links, provider-free semantic search, 158-language coverage. Only one of
those maps to a problem this repository has today.

**Risks.** None. **Cost.** None. **Complexity.** None. **Reversibility.** N/A.
**Architectural impact.** None.

### OPTION B — Use it as an external tool during development only

**Architecture.** Installed on the developer's machine, registered as an MCP
server beside `code-review-graph`. Nothing enters the repository.

**Advantages.** Its strengths become available where they are useful, with no
repository change and no dependency. Reversible by uninstalling.

**Disadvantages.** **Two code graphs over one tree.** Two indexes to keep warm,
two sets of tools with overlapping names, and an agent that must choose between
them on every question. It writes instruction files into `$HOME`, and
**uninstalling does not remove them** (gate 10).

**Risks.** The `$HOME` instruction write — the ADR-038 surface. 1.3 GB and a
build or binary per developer machine.

**Cost.** Low in code, real in setup and in daily ambiguity.
**Complexity.** Moderate. **Reversibility.** High for the registration, partial
for the written files. **Architectural impact.** None on the repository.

### OPTION C — Adapt selected ideas into a native GalSen IA layer

**Architecture.** Extend `src/agent/symbol_index.py` and `repo_graph.py` with
relations they lack — `CALLS` first — and make `build()` incremental by content
hash instead of rebuilding.

**Advantages.** Closes the gaps measured in rows 6, 7 and 16 **in GalSen IA's own
code**, in Python, with its own tests, provenance and governance. No dependency,
no C, no `$HOME` write, no second graph. `ast` already provides call sites.

**Disadvantages.** Work to write and maintain. And — the honest objection —
**`code-review-graph` already answers those questions**, so the gain is limited
to what GalSen IA's own modules must do *without* an MCP server: the self-healing
agent, `capabilities_reach`, and anything running in the deployed platform.

**Risks.** Building something the installed tool already provides. Mitigated by
scoping it to what `src/agent/` needs at runtime, where CRG is not present.

**Cost.** Medium. **Complexity.** Medium. **Reversibility.** Total — it is our
code. **Architectural impact.** Additive, inside an existing module.

### OPTION D — Integrate it as an isolated, replaceable module

**Architecture.** A GalSen IA adapter speaking to the daemon over MCP, behind an
interface, registered like a provider.

**Advantages.** The full capability, behind a seam, replaceable later.

**Disadvantages.** Everything phase 4B found. A 1.3 GB C dependency in a
pure-Python platform that must serve web, Windows, macOS, Linux, Android and iOS.
**And no user-facing consumer**: GalSen IA does not index its users' code. The
only internal consumer is a coding engine whose three backends are unavailable
and which currently refuses every execution.

**Risks.** Platform coverage, build toolchain, binary distribution, the `$HOME`
write inside a deployed product, and a provenance model it does not have.

**Cost.** High. **Complexity.** High. **Reversibility.** Medium — the seam helps,
the platform packaging does not. **Architectural impact.** Significant, and in
the direction `.claude/rules/core-rules.md` forbids: coupling business capability
to one platform's toolchain.

---

## PHASE 11 — Decision

# USE DURING DEVELOPMENT ONLY — *conditional, and the condition is not met today*

Formally: **`KEEP FOR RESEARCH`**, with a named trigger that converts it to
Option B.

### Why not `INTEGRATE` or `INTEGRATE AS OPTIONAL MODULE`

Phase 4B, on architecture rather than quality. GalSen IA is a Python platform
serving six targets and **does not index its users' code**. A 1.3 GB C
code-intelligence engine has no user-facing function in it, and adopting one
would be exactly the reduction the brief's closing rule forbids — *"do not reduce
its architecture to coding"*.

### Why not `ADAPT` — yet

Option C is the most attractive of the four on paper, and rows 6, 7 and 16 are
real gaps in GalSen IA's own modules: one relation type against eight, no
`CALLS` edges, and a `build()` that rebuilds everything.

But **nothing in this repository currently needs those at runtime.**
`src/agent/`'s self-healer works, and `code-review-graph` answers the development
questions. Building it now would be `POSSIBLE → implemented`, one of the four
conversions `.claude/rules/spec-driven-governance.md` forbids by name.

**Recorded as an `OPTIONAL SUGGESTION — NOT IMPLEMENTED`**, with its trigger: the
day `src/agent/self_healer.py` needs a call graph to decide what a repair
touches.

### Why not `REJECT`

Because two findings are real and the project is well made. Its licence hygiene
is better than most audited here — `THIRD_PARTY.md` names paths, and the dual
BSD/GPLv2 choice is stated. Its installer verifies checksums. Its privacy claim
survived a code-level check. **`REJECT` would be a verdict on quality, and the
quality is not the problem.**

### Why `USE DURING DEVELOPMENT ONLY` is *conditional*

Option B's honest form is not *"tool versus nothing"* but *"a second code graph
beside the one already running"*. Gate 9 says the fallback exists and is the
incumbent; gate 10 says removal leaves instruction files behind; gates 3 and 7 —
the two that would justify it anyway — are **`UNKNOWN`**.

**Adopting it today would mean choosing on a claim rather than a measurement**,
which is the one thing this repository's rules refuse.

### The trigger that converts this to Option B

**A measured token-and-tool-call comparison against `code-review-graph`, on this
repository, on the five recurring structural questions defined in phase 8.**

If it wins materially, Option B becomes justified and the `$HOME` write is priced
against a known gain. If it does not, `KEEP FOR RESEARCH` was right.

That benchmark could not run here: its decisive arm needs CRG's MCP tools, and
that server disconnected twice during this session.

### What is decided, in one line

**Nothing is installed, nothing is integrated, nothing is adapted — and the one
thing that would change the answer is named and measurable.**

### Phase 12 does not apply

`ADAPT` was not chosen, so no target architecture is produced. The Option C
sketch above is the record of what an adaptation *would* touch, and it is
deliberately not a design.

---

## FINAL REPORT — the brief's 25 points

```
1.  REPOSITORY STATE
    GalSen IA at 8f64379, branch claude/galsen-ia-phases-ukwz7p, tree clean.
    Subject cloned read-only to /home/user/DeusData/codebase-memory-mcp.

2.  FILES CREATED
    docs/research/codebase-memory-mcp-audit.md  (this document)

3.  FILES MODIFIED
    docs/memory/phase-plan.md  (phase tracking, as the protocol requires)
    Zero files under src/, tests/, agents/, scripts/, workflows/ or .claude/.

4.  EXISTING COMPONENTS REUSED
    None — nothing was built. The audit measured, in GalSen IA:
    src/memory_engine/ (13) · src/knowledge_engine/ (38) · src/embeddings/ (6)
    src/agent/ (23, incl. repo_graph, repo_map, symbol_index, self_healer)
    src/mcp/ (4) · src/services/search/ · src/acquisition/ · src/security/
    src/api/rbac.py · src/tool/authorization.py · workflows/workflows.yaml
    and the code-review-graph MCP server already wired into this repository.

5.  NEW ARCHITECTURE IMPLEMENTED
    None. Audit only.

6.  PROVIDERS EVALUATED
    None as providers. The subject is a code-intelligence engine, not a model
    provider — and phase 5 verified it depends on no provider at all.

7.  SOURCES RESEARCHED
    The clone at 010569fa: README.md, LICENSE, THIRD_PARTY.md, SECURITY.md,
    docs/BENCHMARK.md, install.sh, .github/workflows/ (8), and the C sources in
    src/ and internal/cbm/.
    api.github.com and github.com answer 403 here, so issues, releases and PR
    history were NOT read.

8.  LICENSE FINDINGS
    MIT (c) 2025 DeusData. Compatible with ADR-036 (Apache-2.0).
    Vendored, declared with paths: SQLite public domain · mimalloc, yyjson,
    Verstable MIT · xxHash, TRE, LZ4 BSD-2 · Zstandard BSD-3 (dual GPLv2 NOT
    taken) · simplecpp 0BSD · wyhash Unlicense · nomic weights Apache-2.0.
    INCOMPATIBLE: none. TO WATCH: the nomic NOTICE, dormant unless redistributed.
    A first count reported 7 MPL matches — false positive, "simplecpp" and
    "implementation". There is no MPL.
    Verified-against-upstream count for 160 grammars: UNKNOWN.

9.  TESTS ADDED
    0. The audit adds no test because it adds no code.

10. TOTAL TESTS      7039 collected (7036 + 3 deselected)
11. PASSED           7027
12. FAILED           0
13. SKIPPED          9

14. REGRESSION STATUS
    PASS. Measured in this message: 7027 passed, 9 skipped, 3 deselected,
    0 failed; ruff check src tests scripts clean. Nothing executable changed.

15. PERFORMANCE MEASUREMENTS
    NOT_MEASURED. Their figures are recorded as claims with their method
    (Apple M3 Pro). The independent benchmark is DEFINED and NOT RUN: its
    decisive arm compares against code-review-graph, whose MCP server
    disconnected twice during this session. No performance number here is mine.

16. GPU / RESOURCE MEASUREMENTS
    Subject: 1.3 GB source, of which 1.2 GB is 160 Tree-sitter grammars.
    Host: cc GCC 13.3.0, GNU Make 4.3 present — a build is plausible and was
    not attempted. GPU: not required by the subject and absent from this host.

17. IDENTITY VERIFICATION MEASUREMENTS
    Not applicable to this subject. GalSen IA's own state is unchanged:
    whoever writes GALSEN_API_KEYS asserts who each key belongs to and nothing
    checks it (P0, docs/memory/pending-work.md).

18. CONTINUITY MEASUREMENTS
    Not applicable. GalSen IA's session continuity is unchanged: phase-plan.md
    and session-state.md injected by the SessionStart hook.

19. UNKNOWN ITEMS
    a. Performance and context gain against code-review-graph — the measurement
       that would change the decision.
    b. Memory cost and latency on this host.
    c. Licence of 160 grammars verified against their own upstreams.
    d. Injection resistance — not assessed.
    e. Issues, releases and PR history — api.github.com 403.

20. KNOWN LIMITATIONS
    - Sweeps covered src/ and internal/cbm C sources, not the 160 generated
      grammar parsers.
    - The subject was read and never built or executed. Every behavioural
      statement comes from its source, not from running it.
    - "No outbound path found" is narrower than "none exists", and is written
      that way throughout.

21. SECURITY STATUS
    No destructive or hidden operation found. No sudo. No privilege escalation.
    Installer verifies checksums with a size bound and refuses non-https,
    non-loopback download URLs.
    ONE DISCLOSED PRIVILEGED OPERATION: it writes MCP registrations AND agent
    instruction files into $HOME (~/.claude.json, global_rules.md, AGENTS.md,
    codebase-memory.md and others). Same class of surface ADR-038 weighed for
    Superpowers and decided against on the plugin path.

22. PRIVACY STATUS
    The "100% local" claim was checked in the C, not taken from the README:
    no curl_*, gethostbyname, SSL_connect or socket(AF_INET in src/ or
    internal/cbm/; the only AF_INET connect targets htonl(0x7F000001) —
    127.0.0.1; ipc.c is AF_UNIX. The single getaddrinfo hit is a generated
    table of Python stdlib symbol names, not a call.
    The claim survives. No telemetry found.

23. CONSENT STATUS
    Not applicable — no user data is involved. GalSen IA's consent model
    (ADR-021, src/creative/reference/consent.py) is untouched.

24. FINAL DECISION
    KEEP FOR RESEARCH
    — with a named trigger converting it to USE DURING DEVELOPMENT ONLY.
    Not INTEGRATE (phase 4B, architecture). Not ADAPT yet (POSSIBLE is not
    implemented). Not REJECT (the quality is not the problem).

25. NEXT IMPLEMENTATION PHASE
    NONE. Nothing is authorised by this audit.
    The one action that would change the decision, if the owner wants it:
    measure tokens and tool calls against code-review-graph on this repository,
    on the five structural questions defined in phase 8. That needs CRG's MCP
    server to stay connected.
    Recorded separately as an OPTIONAL SUGGESTION — NOT IMPLEMENTED: adding
    CALLS edges and content-hash incrementality to src/agent/, triggered the day
    self_healer.py needs a call graph to decide what a repair touches.
```

**Not production ready** is not claimed, and neither is the opposite: nothing was
built, so there is nothing to call ready.

---

**End of audit.** 16 phases of 16. Zero files under `src/`, `tests/`, `agents/`,
`scripts/`, `workflows/` or `.claude/` were created, modified or deleted. Nothing
was installed, integrated or adapted.
