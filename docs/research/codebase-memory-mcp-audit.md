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

*Phase 0 complete (2 of 16). Phase 1 — the official repository — has not started.*
