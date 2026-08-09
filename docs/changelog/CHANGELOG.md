# Changelog — GalSen IA

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.
This project follows Semantic Versioning; the version lives in `src/version.py` and
nowhere else. Versioning policy and release types → `docs/roadmap/roadmap.md`.

Nothing has been released yet: the platform is a **prototype** at `0.1.0`.

## [Unreleased]
### Added
- **`GET /metrics` (VOLET 04 ch. 09, half of exit criterion C5)** — request count,
  error rate and per-route latency. `/health` answers what is configured; this
  answers what is happening. It feeds the `metrics` tool that already existed and
  that nothing had ever called, rather than adding a second mechanism
  - series are named by route template, so a URL scan cannot grow the collector
  - a failed measurement never fails the measured request
  - requires a key (read-only is enough); `/health` stays open
  - the reading does not count itself, and the response states `scope: "instance"`
  - `tests/test_api_metrics.py`: 12 tests
- **Versioning and release procedure (VOLET 04 ch. 03)**
  - `src/version.py` is the single source for the version and the release type.
    The application imports it; the Dockerfile redeclares it as
    `ARG GALSEN_VERSION` and `tests/test_version.py` fails if the two drift
  - `scripts/release_check.py`: eight executable checks (version, git tag,
    working tree, tracked secrets, changelog, documentation, startup, test
    suite), non-zero exit when one blocks. The two requirements needing
    judgement — features complete, performance targets verified — are printed
    and never ticked automatically
  - The release type is recorded as `prototype`; the series stays `0.x` while it
    is prototype, alpha or beta, and a stable label is refused while `/health`
    does not report healthy
- **Scaling posture made explicit (VOLET 02 ch. 10, ADR-009)** — closes VOLET 02
  - `src/api/scaling.py`: inventory of every subsystem holding state, with where
    it lives, what a second instance would do to it, and whether that is a loss
    of correctness or harmless duplication. Recomputed on each call so a change
    of `GALSEN_STORAGE_BACKEND` is reflected instead of frozen at import
  - `/health` carries a `scaling` section: instance identity,
    `multi_instance_ready` verdict and the names of the blocking subsystems
  - `POST /auth/keys/{fingerprint}/revoke`, `/restore` and `GET /auth/keys` now
    state `scope: "instance"` — a revoked key keeps opening any other instance,
    and an operator responding to a compromise must not learn that afterwards
  - `GALSEN_INSTANCE_ID` names an instance; unset, `<host>:<pid>` is used
  - `tests/test_scaling.py`: 20 tests, including a demonstration that a key
    revoked on one manager still authenticates on another

- **Conseil Agricole page on `/ui`** (ADR-008) — `api.agri.conseil()` in the API
  client, a full-width section rendered with `textContent`, line breaks
  preserved. `tests/test_web_agri.py` (18 tests) replaces the removed
  `tests/test_dashboard_agri.py`
- `tests/test_import_convention.py` — walks every module under `src/` and fails
  on the first internal import written without the `src.` prefix, and on any
  logic in `src/__init__.py`. The convention had been broken twice, both times
  invisibly, because the tests imported by the bare name too

### Changed
- Two development lines reconciled. `src/frontend/` (Jinja2, mounted on
  `/admin`) is removed: ADR-008 stands, and its page was rebuilt on `/ui`
- `src/api/scaling.py` derives the scope of files and notifications from
  `GALSEN_STORAGE_BACKEND` instead of declaring them process-local. Under
  `sqlite`, only key revocations and rate-limit counters still block a second
  instance
- `data/` is no longer tracked; five `*.sqlite` databases and
  `.claude/settings.json.bak` were removed from version control

### Fixed
- **`POST /agri/advice` answered 200 with an empty answer** when no model
  provider is configured: only exceptions were translated to 503, and the tool
  reports unavailability as a status. Any non-`ready` status now yields 503
  carrying the tool's own detail
- **The `src.` import convention was broken again** by the five services merged
  from the parallel branch, and hidden by `src/__init__.py` inserting `src/`
  into `sys.path`. The same file was importable under two names, so Python
  built two distinct classes and `isinstance` failed. Ten modules and six test
  files converted; `src/__init__.py` emptied of logic
- Three dashboard rendering defects, all found by driving a real browser and
  invisible to HTTP tests: identifiers broken mid-word, a table column silently
  cut off, and overlapping column headers
- `tests/test_api_startup.py`: seven integration tests that actually boot the
  application (`with TestClient(app)`), covering the lifespan, the late binding
  of the tool engine into the health checker, resilience to a broken tool engine
  and a real end-to-end tool execution. No test booted the app before, which is
  why the two startup defects above went unnoticed
- **Backend services test coverage (VOLET 02 Phase 2)**
  - `tests/test_services.py` extended from 93 to 135 unit tests: notification
    serialization edge cases (`read_at`, omitted optional fields, enum instances
    in `from_mapping`), advanced store filters (`min_priority`, role, tags,
    content type), search source weighting, offset pagination, `DATE_ASC` sort,
    provider-query construction and single-source failures, file base64
    round-trip and best-effort failure handling of `FileManagerImpl`
  - `src/services/` statement coverage raised from 92% to 99%

### Fixed
- **The API could not start.** `uvicorn src.api.server:app` — the command the
  Dockerfile runs — failed with `ModuleNotFoundError: No module named 'storage'`
  because `memory_manager.py`, the three `src/storage/sqlite_*_store.py` modules
  and the deferred imports in `knowledge_manager.py` / `model_manager.py` used
  top-level absolute imports assuming `src/` was on `sys.path`. Every import
  inside `src/` now uses the single `src.<module>` convention, which also fixes
  the duplicate-module identity bug (two distinct `MemoryPriority` classes)
- **The startup handler was dead code.** `startup_event()` called
  `tool_loader.load_tools()`, `ToolEngine(tools)` and
  `tool_engine.set_executor()` — none of which exist. It now builds the engine
  from the registry path and logs a failure instead of taking the API down
- **`/tool/execute` never worked**: it called `tool_engine.execute()` (absent —
  the method is `execute_tool()`) and passed `config` as a positional dict, so
  the tool never received its options
- `ToolLoader.get_tool_class()` no longer swallows `ImportError` /
  `AttributeError` silently; the cause is logged. All 20 tools in
  `tools/tools.yaml` now load
- `test_embeddings_tool.py`: the three tests that patch `sentence_transformers`
  are now skipped when that optional dependency is absent, so the suite is green
  out of the box. The behaviour without the dependency stays covered by
  `test_embeddings_tool_missing_sentence_transformer`
- `requirements.txt` now declares two dependencies the code already required:
  `opencv-python-headless` (imported at module level by four
  `src/vision_intelligence_engine/` modules — without it the `vision` engine is
  unavailable in the registry) and `httpx` (required by
  `starlette.testclient.TestClient`, without which four API test files cannot be
  collected)
- Three pre-existing `NameError` failures that prevented the full pytest suite
  from being collected: missing `Optional` import in
  `src/memory_engine/memory_summarizer.py` and
  `src/vision_intelligence_engine/vision_analyzer.py`, and a forward reference to
  `ColorAnalyzer` in `src/vision_intelligence_engine/interfaces.py` (now a string
  annotation)

### Added
- **Priorité #7 — Conseil Agricole (première feature réelle)** : outil
  `AgriAdviceTool` réparé (passage à l'API synchrone `select_model_for_task()` +
  `generate()`, corrigeait un bug d'appel de coroutine asynchrone et une méthode
  inexistante), endpoint `POST /agri/advice` dans `src/api/server.py` (question
  agricole en fr/wo, options model_id/max_tokens, protégé par RBAC
  `model:generate`), 17 tests unitaires dans `tests/test_agri_advice.py` — tous
  verts. Génération réelle vérifiée via Ollama (qwen2.5-coder:14b).
- **Credentials providers (ADR-004)** : `_call_api` implémenté pour OpenAI,
  Anthropic et Google (stdlib urllib, zéro dépendance). Lecture des clés via
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`. Correctifs : imports
  manquants dans `openai_provider.py` et `google_provider.py`, enum `UNAUTHORIZED`,
  commentaires arabes → français. 24 tests unitaires — tous verts.
- **Stockage persistant complet (ADR-005)** : 8 stores SQLite pour Memory, Model,
  Knowledge, Notification, Calendar, Email, Cloud, File. 92 tests — tous verts.
  Backend sélectionnable via `GALSEN_STORAGE_BACKEND=sqlite` ou injection. Correctif
  `:memory:` mode sur `SQLiteFileStore` (connexion persistante).
- **Connecteur S3/Minio + FileSystem pour le service Cloud** : `S3CloudStore` (`src/services/cloud/store_s3.py`) avec upload/download via boto3 (lazy import, configuration par variables d'environnement `CLOUD_S3_*`). `FileSystemCloudStore` (`src/services/cloud/store_fs.py`) pour un stockage persistant local zéro dépendance (index JSON + fichiers binaires). 19 nouveaux tests. **185 tests pour les 3 services externes — tous verts**.
- **Connecteur SMTP pour le service Email** : `SmtpTransport` (`src/services/email/transport.py`) avec support STARTTLS et SSL, configuration par variables d'environnement, construction MIME complète. `ConsoleTransport` et `NoopTransport`. 18 nouveaux tests.
- **Dashboard web (`src/frontend/`)** : 5 templates Jinja2 (base, accueil, santé, services, modèles, mémoire), monté comme sous-application FastAPI sur `/admin` dans `src/api/server.py`. Interface sombre avec sidebar et badges de statut.
- **SDK Client Python (`src/client/`)** : Client REST sans dépendances externes (stdlib `urllib`), couvrant tous les endpoints (santé, mémoire, modèles, notifications, fichiers, cloud, calendrier, email). Retourne des objets Pydantic, pattern best-effort (pas d'exception levée). **48 tests — tous verts**.
- **VOLET 02 Phase 2 — Services Backend (Ch. 03, 07, 09)**
  - **Notification Service** (`src/services/notification/`): types.py, interfaces.py, store.py, manager.py. 8 types de notification (info, warning, error, approval_request, approval_decided, system, task_completed, task_failed), 4 niveaux de priorité, stockage en mémoire thread-safe avec filtres (type, destinataire, rôle, priorité minimale), marquage de lecture individuel et groupé, statistiques agrégées
  - **Search Service** (`src/services/search/`): types.py, interfaces.py, manager.py. Recherche unifiée multi-source (knowledge, memory, document, vision) avec fusion pondérée par source, tri par pertinence/date, filtrage par score minimum. Architecture extensible : tout moteur implémentant `SearchProvider` peut être branché
  - **File Service** (`src/services/file/`): types.py, interfaces.py, store.py, manager.py. Upload avec validation (taille max 10 Mo, nom requis, contenu non vide), mapping automatique type MIME → catégorie (12 catégories), stockage mémoire thread-safe, mise à jour des métadonnées, statistiques par catégorie/type
  - **Integration EngineRegistry** : 3 nouveaux moteurs (notification, search, file) dans ENGINE_NAMES avec builders lazy, propriétés et availability()
  - **API REST** : 14 nouveaux endpoints — notification (POST /notification/send, POST /notification/list, POST /notification/mark-read, POST /notification/mark-all-read, GET /notification/stats, DELETE /notification/{id}), search (POST /search), file (POST /file/upload, GET /file/{id}, POST /file/list, GET /file/stats, DELETE /file/{id})
  - **Tests** : 93 tests unitaires dans `tests/test_services.py` couvrant les 3 services (types, store, manager, cas d'échec, résilience aux pannes store)
- **Phase 4 — Generalized Persistence (VOLET_01, chapitre 03, PERSISTENCE; ADR-005)**
  - `SQLiteModelStore` (`src/storage/sqlite_model_store.py`): replicates the
    `InMemoryModelStore` semantics (same filters, same `updated_at` descending
    sort, same limit) with a verbatim Python filter loop over `list_items`
    (`rowid` order = insertion order); serialization through
    `ModelItem.to_dict()/from_dict()`; `RLock` + `PRAGMA busy_timeout = 5000`;
    `cleanup_expired()` removes DEPRECATED models
  - `SQLiteKnowledgeStore` (`src/storage/sqlite_knowledge_store.py`): 26 columns
    covering the Phase 1 reliability hierarchy (source_category, priority,
    confidence, citation, retrieved_at…); enums serialized as `.value`, datetimes
    as `isoformat()`, lists/dicts as JSON; `list_items` faithfully replicates the
    in-memory filter loop; `cleanup_old_versions()` returns 0 (one version per ID)
  - Configurable data directory: `GALSEN_DATA_DIR` (default `"data"`) resolved by
    `src/storage/paths.py` → `default_sqlite_path(filename)`; backend selected by
    `GALSEN_STORAGE_BACKEND` ("in-memory" by default, "sqlite" for durability)
  - Engine wiring via environment-variable dependency injection in
    `ModelManagerImpl` and `KnowledgeManagerImpl`: injected store wins → else
    sqlite env var → else in-memory store. Deferred **absolute** imports
    (`from storage.sqlite_*_store import ...`) inside `__init__` (avoids the
    circular import AND stays compatible with the project's top-level package
    convention)
  - Fixed `InMemoryKnowledgeIndexer._rebuild_index()`: it accessed the in-memory
    store's private `_data` dict (crashed with `AttributeError` on a SQLite
    store) → now uses the public `list_items()` interface. The index (a derived
    structure) is still rebuilt in memory at manager construction
  - Concurrency: per-instance `RLock` + `PRAGMA busy_timeout = 5000`; shared
    `:memory:` base via `cache=shared` for test isolation
  - `tests/test_storage_engines.py`: 43 unit tests covering CRUD, version
    semantics, filters, cleanup, persistence across reopen, `:memory:`,
    serialization round-trips (enums, dates, JSON, priority) and engine backend
    selection (env var + explicit injection + `GALSEN_DATA_DIR`)
  - Aligned `src/memory_engine/memory_manager.py` with the project convention:
    the module-level relative import `from ..storage.sqlite_store import
    SQLiteMemoryStore` became the absolute `from storage.sqlite_store import
    SQLiteMemoryStore` — the last remaining `..storage` relative import in an
    engine manager (same bug class fixed in Model/Knowledge managers); memory
    and storage tests still pass (96 tests)
- **Phase 3 — Human Approval Gate (VOLET_01, chapitre 06, GOVERNANCE; ADR-006)**
  - `src/approval_engine/` package: `types.py`, `interfaces.py`,
    `approval_store.py`, `approval_manager.py`, `__init__.py`
  - `ApprovalStatus` enum (pending, approved, rejected) and `ApprovalRequest`
    dataclass (id, agent_id, action, description, reason, confidence, timestamps,
    decided_by, status) with serialization
  - `generate_approval_request_id()` producing unique `appr_<hex>` identifiers
  - `InMemoryApprovalStore`: thread-safe store (RLock), unique submission,
    idempotent approve/reject, filtered and ordered listing, pending-queue
    (oldest first), aggregated stats, clear
  - `ApprovalManagerImpl`: best-effort manager that never raises (every method is
    guarded and returns an empty default)
  - Registered as the `approval` engine in `EngineRegistry` (purely in-memory,
    always available — satisfies the dynamic registry test comparison)
  - `AgentContext`: `approval` property plus `submit_approval()`,
    `approve_approval()` and `reject_approval()` delegating best-effort to the
    registry
  - `BaseAgent`: `approval_required`, `approval_description` and
    `approval_confidence` attributes; execution returns status
    `requires_approval` when the gate is required, and a controlled error when
    the approval engine is unavailable
  - `RetryManager`: terminal statuses extended with `requires_approval`
    (never re-executed); only genuine errors are retried
  - `ResultAggregator`: priority `errors > requires_approval > success`;
    `failed_agents = len - successful - pending`; `requires_approval` re-evaluated
    to `partial_success` once all actions eventually succeed
  - `AgentRuntime.execute_task()` and `RouterEngine.process_request()`: global
    status `requires_approval`, collected `approval_request_ids`, aggregation
    consistent with the router
  - API: 5 approval endpoints in `src/api/server.py` — `GET /approval/pending`,
    `GET /approval/stats`, `GET /approval/{request_id}`,
    `POST /approval/{request_id}/approve`, `POST /approval/{request_id}/reject`
    (404/409 handled)
  - `test_approval_engine.py`: 33 unit tests covering types, store, manager,
    registry, context, BaseAgent, RetryManager and ResultAggregator
- **Phase 2 — Structured Audit System (VOLET_01, chapitre 03, AUDITABILITY)**
  - `src/audit_engine/` package: `types.py`, `interfaces.py`, `audit_store.py`,
    `audit_manager.py`, `__init__.py`
  - `AuditEventType` enum (request, agent, tool, generation, knowledge) and
    `AuditStatus` enum (success, partial_success, failure, unavailable, skipped,
    running)
  - `AuditEvent` dataclass logging timestamp, request_id, agent_id, user_request,
    model_id, confidence, knowledge_sources, execution status and execution time
    — the nine fields required by the AUDITABILITY spec
  - `KnowledgeSourceRef` for provenance/citation of knowledge sources used
  - `generate_request_id()` producing unique `req_<hex>` identifiers
  - `InMemoryAuditStore`: thread-safe store (RLock), event_type/status/agent_id/
    request_id/since/until filters, case-insensitive full-text search, aggregated
    stats (by status/type/agent, average execution time)
  - `AuditManagerImpl`: best-effort manager that never raises (every method is
    guarded and returns an empty default), JSON export with accents preserved
    (`ensure_ascii=False`)
  - Registered as the `audit` engine in `EngineRegistry` (purely in-memory, always
    available — satisfies the dynamic registry test comparison)
  - `AgentContext.record_audit()` plus automatic audit tracing of `search_knowledge`,
    `add_knowledge`, `use_tool` and `generate` (SUCCESS/FAILURE/SKIPPED/UNAVAILABLE
    statuses, confidence and knowledge sources recorded, sensitive arguments
    redacted as `key=***`)
  - `BaseAgent`: every agent execution (success and failure) is audited with
    `action=agent:<id>`, engines used and duration
  - `AgentRuntime.execute_task()` and `RouterEngine.process_request()`: request_id
    generated up front, a summarizing REQUEST event on success and failure, and
    request_id present in both success and error responses
  - `test_audit_engine.py`: 35 unit tests covering types, store, manager, context
    integration and registry integration
- Architecture manual consolidation
  - `scripts/merge_architecture_volets.py`: merges the chapter files of all 26 manual
    folders in `docs/architecture/` into 25 single Markdown documents
    (`VOLET_01.md` → `VOLET_25.md`, 10 chapters each), preserving the original
    content byte-for-byte and the original chapter order. Source folders and
    chapter files are left untouched. Integrity is verified per file (each source
    present in the merge + exact byte count).
- Embassions Tool for generating text embeddings using sentence-transformers models
  - `EmbeddingsTool` (`src/tools/embeddings/tool.py`): provides interface for generating embeddings for one or more texts
  - Supports lazy loading of models, configurable model name, device, and normalization
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- OCR Tool for optical character recognition
  - `OCRTool` (`src/tools/ocr/tool.py`): provides interface for extracting text from images using Tesseract OCR
  - Supports lazy loading of dependencies (Pillow, pytesseract), configurable language and Tesseract command path
  - Returns extracted text, confidence scores, and optional bounding boxes
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Database Tool for SQLite database operations
  - `DatabaseTool` (`src/tools/database/tool.py`): provides simple SQL execution, table listing, and schema inspection
  - Supports executing raw SQL with parameters, fetching results, listing tables, retrieving table schema
  - Includes proper connection handling, autocommit mode, and foreign key enforcement
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Memory Tool for GalSen IA memory engine
  - `MemoryTool` (`src/tools/memory/tool.py`): provides interface for memory operations (store, retrieve, search, update, delete, list)
  - Supports short-term, long-term, user, agent shared, conversation, session, workspace/project, and knowledge memories
  - Integrates with the Memory Engine via the MemoryManager
  - Integrated with the Tool Engine via the tools registry
- Browser Tool for web browsing capabilities
  - `BrowserTool` (`src/tools/browser/tool.py`): provides web browsing capabilities to fetch and interact with web pages
  - Supports visiting URLs, extracting text content, extracting links, and getting page titles
  - Includes error handling, retry mechanisms, and proper HTTP headers
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
  - This is one of the remaining tools declared in `tools/tools.yaml` to be implemented.
- PDF Tool for PDF text extraction
  - `PDFTool` (`src/tools/pdf/tool.py`): provides interface for extracting text from PDF files using PyPDF2
  - Supports lazy loading of PyPDF2 dependency, configurable page selection (specific pages or all pages)
  - Returns extracted text, total page count, and list of pages that were processed
  - Includes proper error handling for missing files, invalid paths, and missing dependencies
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Email Tool for sending emails via SMTP
- Calendar Tool for managing calendar events
  - `CalendarTool` (`src/tools/calendar/tool.py`): provides interface for managing calendar events (list, add, delete)
  - Supports listing events, adding new events with validation, deleting events by ID
  - Includes proper error handling for invalid parameters and missing data
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Docker Tool for Docker container management
  - `DockerTool` (`src/tools/docker/tool.py`): provides interface for managing Docker containers (list, run, stop, remove)
  - Supports listing containers, running containers with options, stopping containers, and removing containers
  - Includes proper error handling for Docker daemon unavailability and API errors
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Logging Tool for managing application logs
  - `LoggingTool` (`src/tools/logging/tool.py`): provides interface for managing application logs (list, add, clear)
  - Supports listing logs, adding log entries with levels, clearing logs
  - Includes proper error handling for invalid parameters
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Metrics Tool for collecting and retrieving metrics
  - `MetricsTool` (`src/tools/metrics/tool.py`): provides interface for collecting and retrieving metrics (counters, gauges, histograms)
  - Supports incrementing counters, setting gauges, recording histogram values, retrieving all metrics, resetting
  - Includes proper error handling for invalid parameters
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)

- Model Engine provider layer, making providers interchangeable (see ADR-003)
  - `ModelProvider` (`src/model_engine/providers/base.py`): the single contract —
    declared catalogue, availability check, generation. No code above this file
    refers to a specific vendor.
  - `ProviderRegistry`: which providers exist and which can answer right now
  - `ModelRegistry` (`src/model_engine/model_registry.py`): catalogue of every known
    model with context window, capabilities and price. Readable with no provider
    configured, so the platform can explain what a task would need.
  - `CapabilityDetector`: asks the provider that serves the model, falling back to
    the pre-existing `StaticCapabilityDiscoverer` for hand-registered models
  - `ProviderSelector`: derives requirements from the task type and complexity,
    then picks the cheapest capable model among available providers
  - Providers: `OpenAIProvider`, `AnthropicProvider`, `GoogleProvider` (catalogues
    declared, generation unavailable until credits are decided) and
    `LocalProvider` (Ollama, fully implemented and generating today when a server runs)
  - `GenerationResponse` carries a status, an empty text on failure, a machine
    readable `reason` and an actionable `detail`
  - `ModelManagerImpl.generate()`: structured generation API; `get_provider_status()`,
    `list_catalogue()`, `select_provider_for_task()`, `explain_selection()`,
    `register_provider()`, `sync_catalogue_to_store()`
- `model` tool exposing the Model Engine through the Tool Engine
- `tail` operation on the filesystem tool, reading the end of a file without a
  size limit
- ADR-003 recording the model provider architecture
- Nine provider tests in `test_model_engine.py` covering the registry, provider
  interchangeability, unavailability reporting, the catalogue, capability
  detection, automatic selection, cost preference, the local probe and the
  cross-engine integrations
- Engine integration layer connecting the engines to the agents and orchestrators
  - `EngineRegistry` (`src/integration/engine_registry.py`): builds each engine once,
    lazily, and shares the instance across the platform. An engine that cannot be
    built is reported unavailable rather than raising into unrelated code.
  - `AgentContext` (`src/agent/context.py`): the object handed to every agent,
    carrying the request, the results of earlier agents, and shortcuts to memory,
    knowledge, documents, vision, tools and models
  - `BaseAgent` / `AgentResult` (`src/agent/base_agent.py`): result shape, error
    containment, timing and memory tracing, so agents only implement `perform`
  - `src/agent/legacy.py`: preserves the historical `execute(input_data)` contract
- Nine agents rewritten to call real engines instead of returning formatted strings
  - `planner`, `researcher`, `coder`, `reviewer`, `tester`, `security`,
    `documentation`, `deployment`, `monitor`
  - Agents that would act outside the process (deploy, push, rewrite docs) report
    what should be done instead of doing it
- Four Tool Engine connectors, previously declared in `tools/tools.yaml` but missing
  - `filesystem`: 13 operations, confined to the project root including through
    symbolic links, writing disabled by default
  - `terminal`: executes without a shell, with an executable allowlist and a timeout
  - `git`: read-only by default; pushing to a protected branch and force pushing are
    refused in code, per `.claude/rules/git-workflow.md`
  - `github`: read-only REST client reading its token from `GITHUB_TOKEN` at call time
- `test_integration.py`: 18 tests covering the registry, the context, the four tool
  connectors, all nine agents, error containment and both orchestrators
- Knowledge Engine for unified knowledge management and RAG capabilities
  - KnowledgeManagerImpl: Main orchestrator with dependency injection for all components
  - KnowledgeStore: In-memory storage with thread-safe operations
  - KnowledgeLoaderFactory: Automatic loader selection by file extension/source type
    - TextFileLoader, JSONFileLoader, CSVFileLoader, WebPageLoader, APIDatasourceLoader
    - PDFLoader, DocxLoader (with graceful degradation if dependencies missing)
  - KnowledgeIndexer: In-memory inverted index for fast keyword search with TF-like scoring
  - KnowledgeRetriever: Semantic retrieval using TF-IDF cosine similarity
  - KnowledgeValidator: Input validation (content length, confidence, date consistency, spam detection)
  - KnowledgeGraph: In-memory directed graph for knowledge relationships with BFS path finding
  - KnowledgeCache: LRU cache with TTL support for frequently accessed knowledge
  - KnowledgeRanker: Configurable weighted ranking algorithm (confidence, recency, length, popularity, custom functions)
- Support for multiple input formats: TXT, JSON, CSV, PDF, DOCX, HTML, Markdown, web pages, APIs, databases
- Features: CRUD operations, full-text search, knowledge graph relationships, validation, caching, ranking, versioning, multi-language support (English, French, Spanish, etc.)
- Comprehensive test suite covering all components and integration scenarios
- Model Engine (unified AI model management system)
  - Model Manager, Model Store (in-memory), Model Loader, Model Selector, Model Router
  - Model Context Manager, Prompt Optimizer, Response Validator, Token Tracker
  - Rate Limiter, Retry Manager, Stream Handler, Parallel Executor, Response Ranker
  - Health Monitor, Capability Discoverer
- Support for multiple providers (OpenAI, Anthropic, Google, etc.)
- Intelligent model selection based on task requirements
- Fallback mechanisms, load balancing, and health monitoring
- Prompt optimization per model type, response validation, hallucination detection
- Token usage tracking, cost tracking, rate limiting, retry mechanisms
- Streaming support, parallel execution, and response ranking
- Web Search Tool for intelligent web search
  - WebSearchTool: Multi‑provider search engine with caching, rate limiting, retry, parallel execution
  - Supports web, news, image, video search; suggestions; filters; language/country selection; safe search
  - Features: duplicate removal, ranking, metadata/snippet extraction, citation generation
  - Integrates with Tool Engine, Memory Engine, Model Engine, Knowledge Engine
- Document Intelligence Engine for unified document processing and understanding
  - DocumentManagerImpl: Main orchestrator with dependency injection for all components
  - DocumentStore: In‑memory storage with thread‑safe operations
  - DocumentLoaderFactory: Automatic loader selection by file extension/source type
  - Features: document loading, chunking, indexing, search, retrieval, summarization, question answering, comparison, duplicate detection, metadata/table/image extraction, versioning, caching, validation
- Vision Intelligence Engine for image understanding and analysis
  - Supports image formats: JPG, JPEG, PNG, WEBP, BMP, TIFF
  - Features: metadata extraction, quality analysis, object detection via provider interface, scene description, face detection without identification
  - Integrated with Router Engine, Agent Runtime, Tool Engine, Memory Engine, Model Engine, Knowledge Engine
- Embeddings Tool for generating text embeddings using sentence-transformers models
  - `EmbeddingsTool` (`src/tools/embeddings/tool.py`): provides interface for generating embeddings for one or more texts
  - Supports lazy loading of models, configurable model name, device, and normalization
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- ADR-005: Select SQLite as persistent storage backend
  - Added SQLite memory store (`src/storage/sqlite_store.py`) implementing the `MemoryStore` interface for persistent storage.
  - Modified `MemoryManager` to accept an optional `MemoryStore` dependency, enabling persistence while maintaining backward compatibility with in-memory storage. The storage backend can be selected via the `GALSEN_STORAGE_BACKEND` environment variable (values: "in-memory" or "sqlite", default: "in-memory").
- API Layer for exposing platform functionality via RESTful API
  - Created `src/api/server.py`: FastAPI-based server exposing memory, model, knowledge, and tool endpoints.
  - Provides endpoints for memory storage/retrieval/search, model generation, tool execution, and knowledge search.
  - Integrates with existing engines: MemoryManager, ModelManagerImpl, KnowledgeManagerImpl, ToolEngine.
  - Includes Pydantic models for request/response validation.
  - Updated requirements.txt with fastapi, uvicorn, pydantic.
  - Verified basic functionality with manual tests.
- Agricultural Advisory Tool for providing crop advice in Wolof/French
    - `AgriAdviceTool` (`src/tools/agri_advice/tool.py`): provides interface for generating agricultural advice using AI models.
    - Supports generating advice in French or Wolof based on user query.
    - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- API Authentication via API Key
    - Added API key authentication middleware (dependency) loaded from environment variable GALSEN_API_KEYS.
    - Protected all sensitive endpoints (memory, model, tool, knowledge) while keeping /health public.
    - Returns 401 for missing/invalid keys.
    - Created unit tests in tests/test_api_auth.py.
- Production-Grade API Rate Limiting
    - `src/api/rate_limiter.py`: Token bucket algorithm (InMemoryRateLimiter) with abstract
      `APIRateLimiter` interface enabling future migration to Redis without code changes.
    - `src/api/__init__.py`: Public API exports for all rate limiting components.
    - Configurable via environment variables: `GALSEN_RATE_LIMIT_ENABLED`, `GALSEN_RATE_LIMIT_AUTHENTICATED_RPM`
      (default 60), `GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM` (default 30),
      `GALSEN_RATE_LIMIT_BURST_MULTIPLIER` (default 2.0).
    - Different limits for authenticated (API key) and unauthenticated (IP) clients.
    - Burst multiplier allows short traffic bursts above the RPM average.
    - Thread-safe implementation with `threading.RLock()`.
    - FastAPI dependency `rate_limit_dependency` applied to all protected endpoints;
      rate limiting runs before authentication (429 before 401).
    - HTTP 429 responses include standard headers: `Retry-After`, `X-RateLimit-Limit`,
      `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
    - Client identification: API key for authenticated clients, IP address
      (including `X-Forwarded-For` for reverse proxies) for unauthenticated clients.
    - Singleton pattern with double-checked locking ensures one rate limiter instance per process.
    - Integrated with existing API key authentication in `src/api/server.py`.
    - 34 comprehensive unit tests in `tests/test_api_rate_limiter.py` — all passing.
- Production-Grade Health & Monitoring Endpoints
    - `src/api/health.py`: Abstract `HealthChecker` interface and `ComponentHealthChecker` implementation
      for monitoring all platform components.
    - Three Kubernetes-compatible endpoints in `src/api/server.py`:
      - `GET /health` — Detailed health report of all components (API, memory engine, model engine,
        knowledge engine, tool engine, storage) with metadata (version, uptime, storage backend,
        configured providers). Always returns HTTP 200; overall status in response body.
      - `GET /ready` — Readiness probe verifying required components (API, tool engine) are available.
        Returns 200 when ready, 503 otherwise.
      - `GET /live` — Liveness probe (minimal check that the process is alive). Always returns 200.
    - `ComponentHealth` and `HealthReport` dataclasses with `to_dict()` for clean JSON serialization.
    - Per-component health checks: memory engine (write → read → delete test item), model engine
      (provider availability counts), knowledge engine (get_stats()), tool engine (list_tools()),
      storage (GALSEN_STORAGE_BACKEND env var).
    - Proper HTTP status codes: 200 for healthy, 503 when required dependencies unavailable.
    - Abstract `HealthChecker` interface designed for future Prometheus/Grafana integration without
      modifying calling code.
    - Singleton pattern with `threading.RLock()` and double-checked locking, identical to rate limiter.
    - Late binding via `set_tool_engine()` for tool engine initialized during FastAPI startup event.
    - Overall status computation: any unhealthy → unhealthy, else any degraded → degraded, else healthy.
    - `src/api/__init__.py` updated to export all health module components.
    - Integrated with existing rate limiting dependency on all health endpoints.
    - 58 comprehensive unit tests in `tests/test_api_health.py` — all passing.
- Production-Grade Docker & Deployment Foundation
    - `Dockerfile` — Image de production multi-stage avec `python:3.11-slim`, utilisateur
      non-root `galsen`, healthcheck Docker intégré via `/health`, et couche de
      dépendances séparée pour minimiser la taille de l'image.
    - `docker-compose.yml` — Deux services : `api` (production, port 8000) et `api-dev`
      (développement avec rechargement automatique, port 8001). Volumes nommés pour la
      persistance des données SQLite et des logs. Healthcheck Docker Compose intégré.
      Limites de ressources CPU/mémoire configurables. Réseau bridge dédié `galsen-network`.
    - `.env.example` — Documentation complète de toutes les variables d'environnement :
      stockage, sécurité, limiteur de taux, ports, fournisseurs de modèles IA,
      dépendances optionnelles.
    - `.dockerignore` — Exclusion du contexte Docker : secrets, caches, tests, docs,
      IDE files, virtualenvs, Git.
    - `docs/deployment/docker.md` — Guide complet de déploiement Docker : démarrage
      rapide, construction d'image, exécution avec et sans Compose, variables
      d'environnement, persistance des données, optimisation de taille, compatibilité
      Kubernetes avec exemple de Deployment, troubleshooting.
    - Compatibilité Kubernetes : endpoints `/health`/`/ready`/`/live` pour les probes,
      configuration entièrement par variables d'environnement, utilisateur non-root,
      signal handling via uvicorn.
- Persistent Storage Package (ADR-005) — `src/storage/`
    - `BaseRepository[T]` — Interface abstraite générique définissant le contrat CRUD
      (save, get, update, delete, list_items, clear, count, exists) pour tout backend
      de stockage, permettant de remplacer SQLite par PostgreSQL sans modifier le code
      appelant.
    - `SQLiteMemoryStore` — Implémentation concrète de `MemoryStore` avec persistance
      SQLite. Supporte les bases fichier et `:memory:` (cache partagé avec connexion
      persistante). Gère la sérialisation JSON pour le contenu, les tags et les
      métadonnées.
    - `cleanup_expired()` — Suppression des mémoires expirées basée sur `time.time()`.
    - `src/storage/__init__.py` — Package exportant `BaseRepository` et `SQLiteMemoryStore`.
    - `tests/test_storage.py` — 50 tests unitaires (8 classes) : BaseRepository, CRUD,
      filtrage, pagination, clear, cleanup_expired, cas limites (Unicode, contenu long,
      concurrence), persistance fichier et exports du package.
- **Phase 1 — Verifiable Knowledge Hierarchy (VOLET_01, chapitre 04)**
  - `KnowledgePriority` (IntEnum) : hiérarchie de fiabilité P1 → P4 (P1 = textes
    officiels, publications gouvernementales, normes et documentation officielles ;
    P2 = recherche évaluée par les pairs, documentation technique de confiance,
    institutions réputées ; P3 = références industrielles fiables, consensus d'experts ;
    P4 = estimations ou opinions clairement étiquetées). Classe utilitaire
    `KnowledgePriority.from_source_category()` qui dérive la priorité par défaut
    depuis la catégorie de source.
  - `SourceCategory` (Enum) : 12 catégories de sources (OFFICIAL, GOVERNMENT,
    STANDARD, OFFICIAL_DOCUMENTATION, PEER_REVIEWED, TRUSTED_DOCUMENTATION,
    INSTITUTIONAL, INDUSTRY, EXPERT_CONSENSUS, ESTIMATE, OPINION, UNKNOWN).
  - `KnowledgeSource` enrichi : `source_category`, `title`, `author`, `url`,
    `citation`, `retrieved_at` — traçabilité et citation complètes.
  - `KnowledgeItem.priority` : champ avec valeur par défaut P3 ; préservé par
    `update_content()`.
  - Validation renforcée (`knowledge_validator.py`) : type de source obligatoire
    pour P1/P2 (source traçable avec `id` et `location` définis), vérification des
    types de `source_category`/`retrieved_at`, priorité doit être un
    `KnowledgePriority`, avertissement de cohérence priorité/source.
  - Classement par priorité (`knowledge_ranker.py`) : critère `priority`
    (score `1.0 - (priority-1)/3.0`), méthode `rank_by_priority()`, poids
    équilibrés mis à jour (confidence 0.35, priority 0.25, recency 0.2, ...).
  - Filtres de priorité dans le store (`knowledge_store.py`) : `priority`,
    `min_priority`, `max_priority`, `source_category`.
  - `KnowledgeManager.retrieve_reliable()` : récupération fiable uniquement,
    retourne `{items, reliable, best_priority, best_confidence, reason}` ; renforce
    le comportement « Je ne sais pas » quand aucune connaissance fiable n'est
    disponible.
  - Outil RAG mis à jour (`src/tools/rag/tool.py`) : conversion P1–P4, provenance
    et citation sérialisées, option `require_reliable`/`min_priority` sur
    `retrieve_for_prompt`.
  - Nouveaux tests : 4 tests knowledge engine (hiérarchie P1–P4, provenance,
    filtrage de fiabilité, validation priorité) + 1 test RAG
    (round-trip priorité/provenance).

### Fixed
- Suite de tests stabilisée — 213 tests passent, 0 échecs
  - `test_vision_engine.py::test_image_classification` : `np.float32` n'est pas une sous-classe de `float` Python — corrigé avec `isinstance(score, (float, np.floating))`
  - `test_integration.py::test_terminal_tool` : `echo` n'existe pas comme exécutable standalone sur Windows — remplacé par `python -c "print(...)"`
  - `test_model_engine.py::test_model_engine` : fonction async sans décorateur `@pytest.mark.asyncio` — ajouté
  - `test_rag_tool.py::test_add_and_retrieve` : variable `update_data` non définie après mise à jour + échec de mise à jour car la version n'était pas incrémentée — corrigé
  - `src/tools/rag/tool.py::_op_update` : `KnowledgeItem` créé sans incrémenter la version, causant le rejet de la mise à jour par le store — corrigé
  - `src/knowledge_engine/knowledge_manager.py` : méthode `get_store()` manquante, appelée par `_op_list` du RAGTool — ajoutée
- Infinite recursion in the agent pipeline: `test_router.py` runs every agent,
  including `tester`, which ran `test_router.py` again. Nested execution is now
  detected through an inherited environment flag, and orchestration suites are
  excluded from agent-driven runs because running them there is circular.
- Orchestration suites went from 222s to 34s once the circular runs were removed
  and the web search timeout was shortened
- Reviewer agent reported declarations found inside docstrings as undocumented code
- Missing docstrings on the three `_HTMLTextExtractor` callbacks
- Dead `pass` block in `csv_loader.py` header handling
- Fourteen over-long lines in the document engine loaders and interfaces
- Document Intelligence Engine could not be imported at all: 9 loaders used `from ..types import`,
  which raised `ImportError: attempted relative import beyond top-level package`
- `html_loader` imported `html.parser.Parser`, which does not exist (correct name is `HTMLParser`)
- `ocr_loader` referenced an undefined variable `st` and shadowed the `format` builtin
- `DocumentLoaderFactory()` instances registered no loader; only the module-level singleton did,
  so a directly constructed factory silently failed to recognise most formats
- `DocumentManagerImpl.load_document()` called `DocumentItem.from_dict()` on an object that was
  already a `DocumentItem`
- `CompositeMetadataExtractor` raised `NameError` on an undefined `me`
- `DocumentMetadata` was missing the `line_count` field that its own extractor wrote to
- Document IDs derived from `time.time()` collided when several documents were saved within the
  same millisecond; they now use UUIDs
- `SimpleChunker` could emit chunks up to 100 characters larger than requested and could loop
  forever when the overlap left no progress
- `LRUDocumentCache` accepted a TTL argument and ignored it
- New document versions were built but never stored, so they could not be retrieved by ID
- `unregister_document` deleted the document but left it in the search index
- `json_loader` used the JSON `name` field as document title, which is an entity name, not a title
- Removed `text_loader.py`, an unregistered duplicate of `txt_loader.py`
- Document engine test suite crashed on Windows before running any assertion, because its own
  ✓ output characters are not encodable in cp1252
- KnowledgeIndexer.search() now returns List[tuple[KnowledgeItem, float]] instead of List[str]
- KnowledgeManagerImpl.search_knowledge() and retrieve_for_prompt() updated to correctly unpack search results
- KnowledgeManagerImpl stats output format changed to match test expectations ("store" instead of "knowledge_store")
- KnowledgeManagerImpl now exposes ranking methods: rank_by_confidence, rank_by_recency, rank
- Fixed date handling in tests to use timezone-aware datetime objects
- Fixed knowledge item setup in tests to properly set both created_at and updated_at for age simulation
- KnowledgeValidator date comparison now works with timezone-aware datetime objects
- Fixed missing imports and updated credential detail message in hosted providers to enable environment‑based credential handling (ADR-004)

## [0.2.0] - 2026-07-31
### Added
- Project foundation structure
- Root `CLAUDE.md` with permanent memory system
- Core memory files (`vision`, `current-objectives`, `completed-work`, `pending-work`, `priorities`, `knowledge-index`)
- Complete folder structure for long-term development
- Router Engine (core orchestration component)
- Agent Loader, Workflow Loader, Config Loader, Execution Planner, Result Aggregator, Retry Manager, Logger, Agent Dispatcher
- Agent Runtime (parallel/sequential execution engine with retry handling)
- Placeholder agents for all agent types (Planner, Researcher, Coder, Reviewer, Tester, Security, Documentation, Deployment, Monitor)
- Updated agent registry with module paths for dynamic loading
- Tool Engine architecture (dynamic tool loading and execution)
- Tool Loader, Tool Executor, Tool Engine, and BaseTool interface
- Updated tools registry with module and class information for each tool
- Memory Engine (unified memory management system)
  - Memory Manager, Memory Store (in-memory), Memory Retriever, Memory Indexer, Memory Cache (LRU), Memory Summarizer, Memory Ranking
  - Designed for future storage backends (vector databases, SQL, local, cloud)
  
### Changed
- Nothing yet

### Fixed
- Nothing yet

## [0.1.0] - 2026-07-28
- Initial project foundation created