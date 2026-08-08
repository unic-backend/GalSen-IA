# GalSen IA — Pending Work

## High Priority
- ✅ **ADR-004 (Provider Credentials)** — implémenté. OpenAI, Anthropic et Google
  peuvent générer si les variables d'environnement sont définies. 24 tests.
- ✅ **ADR-005 + SQLite** — fait et livré. 8 stores concrets, 92 tests verts. La
  priorité #5 de `priorities.md` est à jour.
- ✅ **Manifeste de dépendances** — `requirements.txt` couvre maintenant les
  dépendances obligatoires, optionnelles et de test ; `requirements-optional.txt`
  sépare les libs lazy. Le blocage déploiement est levé.

## Medium Priority
- **Conseil Agricole (priorité #7)** : page « Conseil Agricole » dans le dashboard
  web (`src/frontend/`, monté sur `/admin`) qui appelle `POST /agri/advice`, ou
  clôturer la feature côté API. L'API (tool + endpoint + 17 tests) est livrée.
- Add log rotation. `logs/application.log` reached 6 MB and had silently broken the
  monitor agent before a `tail` operation was added. Nothing caps its growth.
- Review the model catalogue periodically: context windows and prices are declared in
  code (`src/model_engine/providers/*_provider.py`) and drift as vendors change them
- ✅ **Tools `tools/tools.yaml`** — les 20 outils chargent tous (correctif
  `src/__init__.py` pour le `sys.path` ; le tool `memory` cassait le chargement).
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