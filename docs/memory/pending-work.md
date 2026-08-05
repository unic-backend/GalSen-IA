# GalSen IA — Pending Work

## High Priority
- Write an ADR on provider credentials, then implement it. The provider architecture
  is done (ADR-003) and `HostedProvider._call_api` is the single method left to fill.
  The ADR must cover: source of keys (environment only, never committed), how they are
  supplied per deployment, rotation, and what happens when a key is present but
  rejected. Until then only the local Ollama provider can generate.
- Write an ADR choosing the persistent storage backend, then implement it behind the
  existing store interfaces (every engine is in-memory, so nothing survives a restart)
- Add a `requirements.txt` / dependency manifest: optional libraries (PyPDF2, python-docx,
  openpyxl, python-pptx, Pillow, markdown) are imported lazily but never declared anywhere.
  The deployment agent reports its absence as a critical blocker.

## Medium Priority
- Add log rotation. `logs/application.log` reached 6 MB and had silently broken the
  monitor agent before a `tail` operation was added. Nothing caps its growth.
- Review the model catalogue periodically: context windows and prices are declared in
  code (`src/model_engine/providers/*_provider.py`) and drift as vendors change them
- Implement the 11 remaining tools declared in `tools/tools.yaml` (api, database, memory,
  rag, embeddings, ocr, pdf, email, calendar, docker, logging, metrics). They currently
  fail to load with `Could not load class`.
- Migrate the root `test_*.py` scripts to pytest, as required by `.claude/rules/testing.md`
- Speed up the orchestration suites: `test_integration.py` takes ~4 minutes because the
  tester agent runs eight real suites on every pipeline execution
- Create deployment documentation
- Create API / dataset / research templates

## Low Priority
- Set up GitHub repository and contribution guidelines
- Remove the empty stray directories at the repository root (`C:GalSen`,
  `IAsrcmodel_engine`, `IAsrcweb_intelligence_engine`), created by a Windows path bug

## Notes
This file is the backlog.  
Move items to `completed-work.md` when they are finished.
Update priorities in `priorities.md` when the order changes.