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

*Phases 0, 1 and 2 complete (5 of 16). Phase 3 — the comparison matrix — has not
started.*
