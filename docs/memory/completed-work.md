# GalSen IA — Completed Work

## Conseil Agricole (priorité #7) — première slice verticale

### 2026-08-08
- **Outil `AgriAdviceTool` réparé** (`src/tools/agri_advice/tool.py`) : appelait
  `generate_text_with_fallback()` asynchrone de façon synchrone (coroutine non
  attendue) + méthode inexistante `get_default_model_name()`. Basculé sur l'API
  synchrone `select_model_for_task()` + `generate()` (même pattern que le tool
  `model`). Génération réelle vérifiée via Ollama (qwen2.5-coder:14b).
- **Endpoint `POST /agri/advice`** (`src/api/server.py`) : question agricole en
  fr/wo, options model_id/max_tokens, protégé par RBAC (`model:generate`, rôle
  user suffit). Validations : question vide → 422, langue invalide → 422,
  clé absente/invalide → 401, succès → 200.
- **17 tests unitaires** (`tests/test_agri_advice.py`) : tool (sélection modèle,
  langues, erreurs) + endpoint (auth, validations, réponse) — tous verts.
  Suite complète : **914 passed, 5 failed** (les 5 échecs sont les mêmes pré-
  existants de `test_model_engine.py` : Ollama actif + catalogue 9 < 10).

## Service Cloud Phase

### 2026-08-05
- **Provider Credentials (ADR-004)** : `HostedProvider._call_api` implémenté pour
  OpenAI, Anthropic et Google — chaque provider a son appel HTTP basé sur `urllib`
  (stdlib, zéro dépendance). Lecture des clés via variables d'environnement
  (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`. Correctifs : imports
  manquants `ProviderStatus`/`UnavailabilityReason` dans `openai_provider.py`,
  imports `urllib` manquants dans `google_provider.py`, enum `UNAUTHORIZED` ajouté
  à `UnavailabilityReason`, commentaires arabes → français dans `AnthropicProvider`.
  **24 nouveaux tests — tous verts.** Le dernier bloc avant l'utilisation de modèles
  hosted est levé.
- Implémentation de `S3CloudStore` et `FileSystemCloudStore`...
- Implémentation de `S3CloudStore` et `FileSystemCloudStore` — connecteurs S3/Minio (boto3, lazy import, configurable par 6 variables d'env `CLOUD_S3_*`) et système de fichiers local (index JSON + fichiers binaires, zéro dépendance). Exportés dans `src/services/cloud/__init__.py`. 19 nouveaux tests.
- Implémentation de `SmtpTransport` dans `src/services/email/transport.py` — connecteur SMTP réel avec STARTTLS, SSL, MIME multipart, pièces jointes, html-to-text alternatif. Configuration via 6 variables d'environnement (`EMAIL_SMTP_*`). `ConsoleTransport` pour le développement, `NoopTransport` pour le comportement historique. 18 nouveaux tests.
- Écriture de **59 tests unitaires** pour le service Cloud (types, store, manager, inference de catégorie, gestion des erreurs)
- Correction de `__post_init__` dans `CloudFileItem` pour normaliser `provider` et `category` passés en chaîne
- Les 3 services externes (email, calendrier, cloud) ont maintenant **185 tests — tous verts**
- **VOLET 02 Phase 4 — Frontend minimal** : Dashboard web (`src/frontend/`, 5 templates Jinja2), monté sur `/admin` dans `server.py`. SDK Client Python (`src/client/`, zéro dépendance, basé sur urllib stdlib). **48 tests** pour le SDK — tous verts.
- **Stockage persistant (ADR-005)** : 8 stores SQLite concrets couvrant Memory, Model, Knowledge, Notification, Calendar, Email, Cloud, File. Backend sélectionnable via `GALSEN_STORAGE_BACKEND=sqlite` ou par injection constructor. 92 tests — tous verts. Correctif : mode `:memory:` sur `SQLiteFileStore` (connexion persistante).

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