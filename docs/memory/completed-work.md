# GalSen IA — Completed Work

## Foundation Phase

### 2026-07-28
- Created root `CLAUDE.md` with project rules and memory pointers.
- Created `docs/memory/vision.md` (long-term vision and principles).
- Created `docs/memory.md` (long-term vision and principles).
- Created `docs/memory/current-objectives.md` (active objectives).
- Created the Router Engine and its components (Agent Loader, Workflow Loader, Config Loader, Execution Planner, Result Aggregator, Retry Manager, Logger, Agent Dispatcher) and placeholder agents for Planner, Researcher, Coder, Reviewer, Tester, Security, Documentation, Deployment, and Monitor.
- Updated `docs/changelog/CHANGELOG.md` to reflect completed work through 0.2.0.
- Ran and verified all test suites (test_router.py, test_agent_runtime.py, test_tool_engine.py, test_memory_engine.py).

### 2026-07-29
- Created the Agent Runtime for executing agent workflows with parallel/sequential execution, retry handling, and result aggregation.
- Updated agent registry to include module paths for dynamic agent loading.
- Verified placeholder agents for all agent types.
- Implemented the Database tool with French comments and ensured compliance with coding conventions (comments in French, clear method names, proper docstrings). Updated related tests pass.
- Implemented the Embeddings tool for generating text embeddings using sentence-transformers models, with French comments and ensured compliance with coding conventions. Updated related tests pass.
- Implemented the Memory tool with French comments and ensured compliance with coding conventions (comments in French, clear method names, proper docstrings). Updated related tests pass.
- Implémenté la couche d'API exposant les fonctionnalités de la plateforme via un serveur REST FastAPI, incluant des points de terminaison pour la mémoire, les modèles, les outils et la connaissance. Créé src/api/server.py et requirements.txt.
- Implémenté l'outil de conseil agricole pour fournir des conseils sur les cultures en wolof/français, intégré au Tool Engine via le registre des outils. Créé src/tools/agri_advice/tool.py.
- Implémenté l'authentification par clé API pour sécuriser les endpoints sensibles de l'API, chargé depuis la variable d'environnement GALSEN_API_KEYS. Mis à jour le middleware FastAPI et ajouté des tests unitaires. Créé tests/test_api_auth.py.

### 2026-07-30
- Created the Tool Engine architecture for dynamic tool loading and execution.
- Created Tool Loader, Tool Executor, Tool Engine, and BaseTool interface.
- Updated tools registry with module and class information for each tool.
- Verified the tool engine loads correctly and provides tool discovery and execution interfaces.

### 2026-07-31
- Created the Memory Engine for managing short-term, long-term, user, agent shared, conversation, session, workspace/project, and knowledge memories.
- Implemented Memory Manager, Memory Store (in-memory), Memory Retriever, Memory Indexer, Memory Cache (LRU), Memory Summarizer, and Memory Ranking.
- Provided a unified API for agents to interact with memories without knowing the storage backend.
- Designed for future extension to vector databases, SQL databases, local storage, and cloud storage.
- Verified the memory engine stores, retrieves, searches, ranks, summarizes, and expires memories correctly.

### 2026-08-01
- Created the Model Engine for managing AI models from multiple providers (OpenAI, Anthropic, Google, etc.).
- Implemented Model Manager, Model Store (in-memory), Model Loader, Model Selector, Model Router, Model Context Manager, Prompt Optimizer, Response Validator, Token Tracker, Cost Tracker, Rate Limiter, Retry Manager, Stream Handler, Parallel Executor, Response Ranker, Health Monitor, and Capability Discoverer.
- Provided a unified API for agents to interact with AI models without knowing the provider-specific details.
- Implemented intelligent model selection based on task requirements, fallback mechanisms, load balancing, and health monitoring.
- Added Model Engine provider layer, making providers interchangeable (See ADR-003). Implemented Provider Registry, Capability Detector, Provider Selector, and support for OpenAI, Anthropic, Google, and Local (Ollama) providers.
- Added Knowledge Engine for unified knowledge management and RAG capabilities (Knowledge Store, Loader Factory, Indexer, Retriever, Validator, Graph, Cache, Ranker).
- Added Document Intelligence Engine for document processing (loading, chunking, indexing, search, summarization, QA, comparison, duplicate detection, metadata/table/image extraction, versioning).
- Added Vision Intelligence Engine for image analysis (metadata extraction, quality analysis, object detection, scene description).
- Created 9 rewritten agents (planner, researcher, coder, reviewer, tester, security, documentation, deployment, monitor) calling real engines.
- Created 4 new Tool Engine connectors: filesystem, terminal, git, github.
- Added SQLite memory store (ADR-005) with persistent storage option.

### 2026-08-03
- Implémenté le limiteur de taux de production pour l'API FastAPI.
  - Créé `src/api/rate_limiter.py` avec l'algorithme du seau à jetons (InMemoryRateLimiter).
  - Interface abstraite `APIRateLimiter` permettant une migration future vers Redis sans modifier le code appelant.
  - Configuration via variables d'environnement : GALSEN_RATE_LIMIT_ENABLED, GALSEN_RATE_LIMIT_AUTHENTICATED_RPM, GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM, GALSEN_RATE_LIMIT_BURST_MULTIPLIER.
  - Limites différentes pour clients authentifiés (clé API, 60 RPM par défaut) et non authentifiés (IP, 30 RPM par défaut).
  - Multiplicateur de rafale (2.0 par défaut) permettant des pics temporaires au-dessus de la limite RPM.
  - Thread-safe avec verrou RLock pour les accès concurrents.
  - Dépendance FastAPI `rate_limit_dependency` appliquée à tous les endpoints protégés (exécutée avant l'auth : 429 avant 401).
  - Réponses HTTP 429 avec en-têtes Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset.
  - Identification du client : clé API pour les authentifiés, adresse IP (y compris X-Forwarded-For) pour les non authentifiés.
  - Pattern singleton avec double-checked locking pour une instance unique par processus.
  - Créé `src/api/__init__.py` exportant tous les composants publics du limiteur de taux.
  - Intégré avec l'authentification API Key existante dans `src/api/server.py`.
  - Créé 34 tests unitaires dans `tests/test_api_rate_limiter.py` — tous passent.

### 2026-07-30
- Implémenté la Phase 3 de Production Readiness — Health & Monitoring.
  - Créé `src/api/health.py` avec l'interface abstraite `HealthChecker` et l'implémentation `ComponentHealthChecker`.
  - Ajouté trois endpoints de santé Kubernetes-compatibles dans `src/api/server.py` :
    - `GET /health` — Rapport de santé détaillé (API, memory engine, model engine, knowledge engine, tool engine, storage) avec métadonnées (version, uptime, backend, providers).
    - `GET /ready` — Test de readiness vérifiant les composants requis (API + tool engine). 200 si prêt, 503 sinon.
    - `GET /live` — Test de liveness minimal. Toujours 200.
  - Vérifications par composant : memory engine (écriture → lecture → suppression), model engine (comptage providers disponibles), knowledge engine (get_stats()), tool engine (list_tools()), storage (GALSEN_STORAGE_BACKEND).
  - Codes HTTP : 200 pour healthy, 503 quand dépendances requises indisponibles.
  - Interface abstraite conçue pour intégration future Prometheus/Grafana sans modifier le code appelant.
  - Pattern singleton avec `threading.RLock()` et double-checked locking, identique au limiteur de taux.
  - Late binding via `set_tool_engine()` pour le moteur d'outils initialisé dans l'événement startup FastAPI.
  - Calcul du statut global : tout unhealthy → unhealthy, sinon tout degraded → degraded, sinon healthy.
  - `src/api/__init__.py` mis à jour pour exporter tous les composants du module health.
  - Créé 58 tests unitaires dans `tests/test_api_health.py` — tous passent.
  - Adapté `test_api_auth.py::test_health_endpoint_no_auth` au nouveau format du endpoint /health.
  - Suite de tests complète : 271 tests, 0 échecs.
  - Implémenté la Phase 4 de Production Readiness — Docker & Deployment Foundation.
    - Créé `Dockerfile` multi-stage (builder + production) avec `python:3.11-slim`, utilisateur non-root `galsen`, healthcheck Docker utilisant `/health`, dépendances de build séparées.
    - Créé `docker-compose.yml` avec services `api` (production, port 8000) et `api-dev` (développement avec `--reload`, port 8001), volumes nommés pour persistance SQLite et logs, healthcheck Docker Compose, limites de ressources, réseau bridge dédié.
    - Créé `.env.example` documentant toutes les variables d'environnement : stockage, sécurité, limiteur de taux, ports, fournisseurs IA, dépendances optionnelles.
    - Créé `.dockerignore` excluant secrets, caches, tests, docs, IDE, virtualenvs, fichiers Git.
    - Créé `docs/deployment/docker.md` : guide complet avec démarrage rapide, construction, exécution (Docker et Compose), variables, persistance, optimisation, compatibilité Kubernetes (exemple Deployment inclus), troubleshooting.
    - Compatible Kubernetes : probes `/health`/`/ready`/`/live`, configuration par variables d'environnement, utilisateur non-root.

### 2026-07-30 (Stockage Persistant — ADR-005)
- Créé le package `src/storage/` avec `__init__.py` exportant les classes publiques.
- Créé `src/storage/base_repository.py` : interface abstraite générique `BaseRepository[T]` définissant le contrat CRUD (save, get, update, delete, list_items, clear, count, exists) pour tout backend de stockage, conformément à ADR-005.
- Corrigé `src/storage/sqlite_store.py` :
  - Imports relatifs → absolus pour compatibilité avec les tests.
  - Code mort dans `cleanup_expired()` remplacé par `time.time()` propre.
  - Base `:memory:` partagée via `cache=shared` avec connexion persistante pour l'isolation des tests.
  - `MemoryPriority` (IntEnum) : conversion `str` → `int` à la désérialisation.
- Créé `tests/test_storage.py` : 50 tests unitaires (8 classes) couvrant BaseRepository, CRUD, list_items avec filtres, pagination, clear, cleanup_expired, cas limites (Unicode, contenu long, concurrence), persistance fichier et exports du package. Tous les tests passent.

### 2026-08-04
- Stabilisé la codebase et restauré une suite de tests propre : 213 tests, 0 échecs.
  - Corrigé 4 tests échouant : `test_vision_engine.py` (np.float32), `test_integration.py` (echo sur Windows), `test_model_engine.py` (décorateur asyncio manquant), `test_rag_tool.py` (version non incrémentée + variable non définie).
  - Corrigé 2 bugs dans le code source : `KnowledgeManagerImpl.get_store()` manquant, `RAGTool._op_update` n'incrémentant pas la version.
  - Aucun changement d'architecture, aucune nouvelle fonctionnalité, aucun placeholder.
### 2026-08-04 (Phase 1 — Verifiable Knowledge Hierarchy)
- Implémenté la hiérarchie de fiabilité P1–P4 conforme au VOLET_01 (chapitre 04).
  - Créé `KnowledgePriority` (IntEnum, P1 = 1 → P4 = 4) avec `from_source_category()`.
  - Créé `SourceCategory` (Enum, 12 catégories de sources).
  - Étendu `KnowledgeSource` (source_category, title, author, url, citation, retrieved_at) et `KnowledgeItem` (priorité, défaut P3, préservée par update_content()).
  - Renforcé la validation : P1/P2 exigent une source traçable, types vérifiés, priorité contrôlée.
  - Ajouté le classement par priorité dans `KnowledgeRankerImpl` (rank_by_priority, critère priority, nouveaux poids équilibrés).
  - Ajouté les filtres priority/min_priority/max_priority/source_category dans `InMemoryKnowledgeStore`.
  - Implémenté `KnowledgeManager.retrieve_reliable()` renforçant le comportement « Je ne sais pas ».
  - Mis à jour l'outil RAG (`src/tools/rag/tool.py`) : conversion P1–P4, provenance/citation sérialisées, option `require_reliable`.
  - Ajouté 5 nouveaux tests (4 knowledge engine + 1 RAG) — tous passent.
- Suite de tests Phase 1 : tous les tests collectables passent (knowledge engine, RAG, API, intégration registre/contexte). Deux fichiers préexistants (`test_model_engine.py`, `test_integration.py`) déclenchent des appels réels aux modèles/providers et bloquent — non liés à la Phase 1.

- Consolidé les manuels d'architecture : fusion de 250 fichiers de chapitres (10 par volet) en 25 documents Markdown uniques `VOLET_01.md` → `VOLET_25.md` dans `docs/architecture/`.
  - Créé `scripts/merge_architecture_volets.py` : concaténation binaire stricte (contenu préservé octet pour octet), tri par numéro de chapitre, séparateur de fin de ligne inséré uniquement quand un fichier ne se termine pas par `\n`, vérification d'intégrité (chaque source présent dans le fichier fusionné + taille exacte).
  - Aucun dossier ni fichier source supprimé ou modifié. Dossier vide `Enterprise Governance & Operations Manual. V20` ignoré (le volet 20 réel vient de `Memory Engine. Volet 20`).
  - Anomalies détectées dans les sources (non corrigées, hors périmètre) : dans `Memory Engine. Volet 20`, le fichier `CHAPTER 02 – MEMORY ENGINE ARCHITECTURE.txt` est un doublon exact de `Chapitre 01 Memory Engine Vision.txt` ; dans `ENTERPRISE GOVERNANCE & GLOBAL ARCHITECTURE MANUAL. Volet 25`, le fichier `CHAPTER 08 – ENTERPRISE VISION.txt` est un doublon exact de `CHAPTER 07 – ENTERPRISE VISION.txt`.

### 2026-08-04 (Phase 2 — Structured Audit System)
- Implémenté le système d'audit structuré conforme au VOLET_01 (chapitre 03, AUDITABILITY).
  - Créé le package `src/audit_engine/` : `types.py` (modèles de données), `interfaces.py` (contrats ABC), `audit_store.py` (store en mémoire), `audit_manager.py` (manager best-effort), `__init__.py` (exports publics).
  - Modèles : `AuditEventType` (request, agent, tool, generation, knowledge), `AuditStatus` (success, partial_success, failure, unavailable, skipped, running), `AuditEvent` (timestamp, request_id, agent_id, user_request, model_id, confidence, knowledge_sources, status, execution_time_seconds, detail, metadata, id), `KnowledgeSourceRef`, `generate_request_id()`.
  - Store : `InMemoryAuditStore` thread-safe (RLock), filtres par event_type/status/agent_id/request_id/since/until, recherche plein texte, stats agrégées (par statut/type/agent, temps moyen d'exécution).
  - Manager : `AuditManagerImpl` ne lève JAMAIS (chaque méthode est protégée → logger.warning + valeur vide), export JSON avec `ensure_ascii=False` (accents préservés).
  - Intégré à `EngineRegistry` (`audit` engine, pur en mémoire, toujours disponible — la comparaison dynamique du test registre reste satisfaite).
  - `AgentContext` enrichi : `record_audit()`, propriété `audit`, normalisation statut/type, traçage automatique de `search_knowledge`, `add_knowledge`, `use_tool`, `generate` (statuts SUCCESS/FAILURE/SKIPPED/UNAVAILABLE, sources de connaissance avec confiance, arguments secrets masqués).
  - `BaseAgent` : chaque exécution d'agent (succès et échec) est consignée (`action=agent:<id>`, engines_used, durée).
  - `AgentRuntime.execute_task()` et `RouterEngine.process_request()` : `request_id` généré en tête, événement REQUEST résumant la requête (statut global, workflow, compteurs agents), `request_id` présent dans la réponse succès ET erreur.
  - Créé `test_audit_engine.py` : 35 tests unitaires couvrant types, store, manager, contexte, registre — tous passent.
- Suite de tests complète Phase 2 : 352 tests passent. 5 échecs préexistants dans `test_model_engine.py` (Ollama local disponible avec 9 modèles vs ≥ 10 attendus — environnement, non liés à la Phase 2). 4 tests de `test_integration.py` appelant de vrais modèles désélectionnés (`--deselect`) car ils bloquent dans cet environnement — préexistants, non liés à la Phase 2.

### 2026-08-04 (Phase 3 — Human Approval Gate)
- Implémenté le portillon d'approbation humaine conforme au VOLET_01 (chapitre 06, GOVERNANCE) et à l'ADR-006.
  - Créé le package `src/approval_engine/` : `types.py` (modèles de données), `interfaces.py` (contrats ABC), `approval_store.py` (store en mémoire), `approval_manager.py` (manager best-effort), `__init__.py` (exports publics).
  - Modèles : `ApprovalStatus` (pending, approved, rejected), `ApprovalRequest` (id, agent_id, action, description, reason, confidence, created_at, decided_at, decided_by, status), `generate_approval_request_id()`.
  - Store : `InMemoryApprovalStore` thread-safe (RLock), soumission (id unique), approbation/refus (idempotents, état inconnu → None), liste filtrée + triée, liste des pending (plus anciennes d'abord), stats agrégées, suppression.
  - Manager : `ApprovalManagerImpl` ne lève JAMAIS (chaque méthode est protégée → logger.warning + valeur vide par défaut).
  - Intégré à `EngineRegistry` (`approval` engine, pur en mémoire, toujours disponible — la comparaison dynamique du test registre reste satisfaite).
  - `AgentContext` enrichi : propriété `approval`, `submit_approval()`, `approve_approval()`, `reject_approval()` (délégation best-effort au registre).
  - `BaseAgent` : attributs `approval_required` (défaut False), `approval_description`, `approval_confidence` ; exécution à statut `requires_approval` quand le portillon est requis, erreur contrôlée si le moteur d'approbation est indisponible.
  - `RetryManager` : statuts terminaux étendus à `requires_approval` (jamais ré-exécuté) ; seules les vraies erreurs sont retentées.
  - `ResultAggregator` : priorité `errors > requires_approval > success` ; `failed_agents = len - successful - pending` ; `requires_approval` réévalué en `partial_success` si toutes les actions ont finalement abouti.
  - `AgentRuntime.execute_task()` et `RouterEngine.process_request()` : statut global `requires_approval`, liste `approval_request_ids` collectée, agrégation cohérente avec le routeur.
  - API REST : 5 endpoints d'approbation dans `src/api/server.py` — `GET /approval/pending`, `GET /approval/stats`, `GET /approval/{request_id}`, `POST /approval/{request_id}/approve`, `POST /approval/{request_id}/reject` (404/409 gérés).
  - Créé `test_approval_engine.py` : 33 tests unitaires couvrant types, store, manager, registre, contexte, BaseAgent, RetryManager, ResultAggregator — tous passent.
- Suite de tests complète Phase 3 : 385 tests passent (352 Phase 2 + 33 Phase 3), 4 désélectionnés. 5 échecs préexistants dans `test_model_engine.py` (Ollama local disponible avec 9 modèles vs ≥ 10 attendus — environnement, non liés à la Phase 3). 4 tests de `test_integration.py` appelant de vrais modèles désélectionnés (`--deselect`) car ils bloquent dans cet environnement — préexistants, non liés à la Phase 3.

### 2026-08-04 (Phase 4 — Generalized Persistence)
- Implémenté la persistance généralisée des moteurs Model et Knowledge sur SQLite, conforme au VOLET_01 (chapitre 03, PERSISTENCE) et à l'ADR-005.
  - `SQLiteModelStore` (`src/storage/sqlite_model_store.py`) : réplique la sémantique de `InMemoryModelStore` (mêmes filtres, même tri `updated_at` décroissant, même limite) via une boucle de filtrage identique en Python sur `list_items` (ordre `rowid` = ordre d'insertion). Sérialisation via `ModelItem.to_dict()/from_dict()`. Verrou `RLock` + `PRAGMA busy_timeout = 5000`. `cleanup_expired()` supprime les modèles DEPRECATED.
  - `SQLiteKnowledgeStore` (`src/storage/sqlite_knowledge_store.py`) : 26 colonnes couvrant la hiérarchie de fiabilité Phase 1 (source_category, priority, confidence, citation, retrieved_at…), sérialisation des enums en `.value`, dates en `isoformat()`, listes/dicts en JSON. `list_items` réplique fidèlement la boucle de filtrage en mémoire. `cleanup_old_versions()` → 0 (une version par ID).
  - Répertoire de données configurable : `GALSEN_DATA_DIR` (défaut `"data"`) résolu par `src/storage/paths.py` → `default_sqlite_path(filename)` ; backend sélectionné par `GALSEN_STORAGE_BACKEND` ("in-memory" par défaut, "sqlite" pour persister).
  - Branchement des moteurs via injection de dépendance par variable d'environnement dans `ModelManagerImpl` et `KnowledgeManagerImpl` : store injecté prioritaire → sinon env var sqlite → sinon store en mémoire. Imports différés **absolus** (`from storage.sqlite_*_store import ...`) à l'intérieur de `__init__` (évite l'import circulaire ET est compatible avec la convention top-level du projet).
  - Corrigé `InMemoryKnowledgeIndexer._rebuild_index()` : accédait au dictionnaire privé `_data` du store en mémoire (crash `AttributeError` avec un store SQLite) → utilise désormais l'interface publique `list_items()`. L'index (structure dérivée) reste reconstruit en mémoire à la construction du gestionnaire.
  - Concurrence : verrou `RLock` par instance + `PRAGMA busy_timeout = 5000` ; base partagée `:memory:` via `cache=shared` pour l'isolation des tests.
  - Créé `tests/test_storage_engines.py` : 43 tests unitaires couvrant CRUD, sémantique des versions, filtres, cleanup, persistance à travers réouverture, `:memory:`, aller-retour de sérialisation (enums, dates, JSON, priorité), concurrence et sélection du backend des moteurs (env var + injection explicite + `GALSEN_DATA_DIR`) — tous passent.
  - Aligné `src/memory_engine/memory_manager.py` sur la convention du projet : l'import module-level `from ..storage.sqlite_store import SQLiteMemoryStore` (relatif) est devenu `from storage.sqlite_store import SQLiteMemoryStore` (absolu top-level) — le dernier import `..storage` restant dans un gestionnaire de moteur, identique à la classe de bug corrigée dans Model/Knowledge. Vérifié : les tests mémoire + storage passent (96 tests), aucune régression.
- Suite de tests complète Phase 4 : 432 tests passent, 5 échecs préexistants dans `test_model_engine.py` (Ollama local disponible avec 9 modèles vs ≥ 10 attendus — environnement, non liés à la Phase 4). Les 4 tests de `test_integration.py` appelant de vrais modèles (préalablement désélectionnés car ils bloquent quand Ollama est indisponible) ont cette fois tourné et réussi (Ollama réactif). Aucune régression introduite.

### 2026-08-04 (VOLET 02 Phase 2 — Services Backend)
- Implémenté les 3 services backend conformément au VOLET_02 (chapitres 03, 07, 09).
  - **Notification Service** (`src/services/notification/`) : types (8 types, 4 priorités), interfaces (NotificationStore, NotificationManager), InMemoryNotificationStore thread-safe, NotificationManagerImpl best-effort.
  - **Search Service** (`src/services/search/`) : types (SearchQuery, SearchResultItem, SearchResponse), interfaces (SearchProvider, SearchManager), SearchManagerImpl avec fusion multi-source pondérée et 3 modes de tri.
  - **File Service** (`src/services/file/`) : types (FileItem, FileUploadResult, mapping MIME → catégorie), interfaces (FileStore, FileManager), InMemoryFileStore thread-safe, FileManagerImpl avec validation upload.
  - Intégrés à `EngineRegistry` (notification, search, file comme moteurs lazy).
  - Exposés via 14 endpoints API REST dans `src/api/server.py` avec permissions RBAC.
  - Créé `tests/test_services.py` : 93 tests unitaires — tous passent.
- Suite de tests complète Phase 2 : 519 tests passent, 33 désélectionnés, 0 échecs. Aucune régression.
### 2026-08-05 (VOLET 02 Phase 2 — Couverture de tests des services)
- Étendu `tests/test_services.py` de 93 à 135 tests : sérialisation (`read_at`, champs optionnels omis, base64, dates ISO), filtres avancés (min_priority, rôle, tags, content_type), pondération et pagination de la recherche fusionnée, pannes du store fichier. Couverture `src/services/` : 92 % → 99 % (seule ligne non couverte : `_priority_value(None)` dans `notification/store.py`, branche défensive inatteignable par l'API publique).
- Corrigé 3 `NameError` préexistants qui empêchaient la collecte pytest de la suite complète : `Optional` manquant dans `src/memory_engine/memory_summarizer.py` et `src/vision_intelligence_engine/vision_analyzer.py`, référence avant définition de `ColorAnalyzer` dans `src/vision_intelligence_engine/interfaces.py` (annotations en chaîne).
- Suite complète : 591 tests passent, 3 échecs environnementaux dans `test_embeddings_tool.py` (`sentence_transformers` non installé, dépendance optionnelle). `cv2` et `fastapi` doivent être installés pour que la suite se collecte entièrement.
- 2026-08-05 - Dépendances manquantes déclarées dans `requirements.txt` : `opencv-python-headless` (importé au niveau module par 4 fichiers de `src/vision_intelligence_engine/`, son absence rend le moteur `vision` indisponible et fait échouer `test_integration.py`) et `httpx` (requis par `starlette.testclient.TestClient`, sans lui 4 fichiers de tests API ne se collectent pas).
- 2026-08-05 - Mémoire réalignée sur l'état réel du code : `priorities.md`, `current-objectives.md`, `pending-work.md` et `CLAUDE.md` annonçaient encore « everything is in-memory, persistent storage needs an ADR » alors que l'ADR-005 est acceptée et appliquée (memory, model, knowledge via `GALSEN_STORAGE_BACKEND`). Reste en mémoire seule : audit, approval et les 3 services backend.
- 2026-08-05 - `test_embeddings_tool.py` : les 3 tests qui patchent `sentence_transformers` sont marqués `skipif` quand la dépendance optionnelle est absente (elle tire torch). Le comportement du tool sans la dépendance reste couvert par `test_embeddings_tool_missing_sentence_transformer`. Suite complète : 591 passent, 3 ignorés, 0 échec.

### 2026-08-05 (Correctifs bloquants — l'API ne démarrait pas)
- **Convention d'import unifiée sur `src.<module>`** : `src/memory_engine/memory_manager.py`, les 3 `src/storage/sqlite_*_store.py` et les imports différés de `knowledge_manager.py` / `model_manager.py` utilisaient des imports absolus top-level (`from storage...`, `from memory_engine...`) qui supposaient `src/` dans `sys.path`. Conséquence : `uvicorn src.api.server:app` (la commande du Dockerfile) échouait sur `ModuleNotFoundError: No module named 'storage'`, et l'outil `memory` était inchargeable. Effet de bord corrigé dans la foulée : `tests/test_storage.py` et `tests/test_storage_engines.py` importaient les mêmes modules sous l'autre convention, ce qui créait deux exemplaires distincts de `MemoryPriority`/`MemoryItem` (comparaisons d'enums en échec) — ils pointent désormais sur la racine du dépôt.
- **`startup_event()` de l'API réécrit** : il appelait `tool_loader.load_tools()`, `ToolEngine(tools)` et `tool_engine.set_executor()` — trois méthodes inexistantes. Le `ToolEngine` construit lui-même son chargeur et son exécuteur à partir du chemin du registre ; un échec est journalisé sans empêcher l'API de démarrer. Le global `tool_executor`, inutilisé, a été retiré.
- **`/tool/execute` corrigé** : appelait `tool_engine.execute()` (inexistante, → `execute_tool()`) et transmettait `config` en argument positionnel au lieu d'arguments nommés, si bien qu'aucune option n'atteignait l'outil.
- **`ToolLoader.get_tool_class()` ne masque plus les erreurs** : l'ancien `except (ImportError, AttributeError): return None` rendait un outil introuvable sans aucune trace. La cause est journalisée. Les 20 outils de `tools/tools.yaml` se chargent désormais.
- **`tests/test_api_startup.py` créé** (7 tests) : aucun test ne démarrait réellement l'application (`TestClient(app)` sans `with` ne déclenche pas le cycle de vie), ce qui rendait ces deux pannes invisibles pour la suite. Les tests couvrent le démarrage, la publication tardive du moteur d'outils au vérificateur de santé, la résilience à un moteur d'outils cassé, et l'exécution d'un vrai outil de bout en bout.
- Vérifié en exécution : `uvicorn src.api.server:app` démarre, `/health` répond `degraded` (seul le moteur de modèles l'est, faute de fournisseur configuré), `/tool/execute` exécute réellement l'outil `filesystem`. Suite complète : 598 tests passent, 3 ignorés.
