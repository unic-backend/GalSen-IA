# GalSen IA

**GalSen IA** is a long-term artificial intelligence platform designed first for Senegal, then Africa, and eventually the world.

## Current Status
The foundation phase is complete. The platform now runs: eleven engines behind a
REST API, nine agents and their router, twenty tools, and SQLite persistence for
memory, models and knowledge (ADR-005).

What is not there yet: no frontend, no external connectors (email, calendar,
cloud), and no configured model provider — text generation reports itself as
unavailable until an API key is present in the environment.

## Getting Started

```bash
pip install -r requirements.txt

# Lancer l'API
uvicorn src.api.server:app --reload

# Lancer la suite de tests
python -m pytest -q
```

The API answers on `http://127.0.0.1:8000`. `GET /health` reports the state of
every engine. All other endpoints require an API key, declared as
`GALSEN_API_KEYS="votre-cle:admin"` — see `.env.example`.

Optional dependencies live in `requirements-optional.txt`: their absence disables
one feature (OCR, document loaders, embeddings) and never the platform.

## Project Structure
- `CLAUDE.md` → Main instructions for Claude Code
- `src/` → The engines, the services, the API and the tools
- `agents/` → Agent definitions, registered in `agents/registry.yaml`
- `tools/tools.yaml` → Tool registry read by the Tool Engine
- `tests/` → Test suite
- `docs/memory/` → Permanent project memory
- `docs/architecture/` → Architecture, the 25 volets and the decisions (ADR)
- `docs/roadmap/` → Product and technical roadmap
- `docs/changelog/` → History of changes
- `docs/tasks/` → Current tasks
- `.claude/rules/` → Coding, security and workflow rules

Start with `docs/architecture/overview.md` for how the pieces fit together.

## Languages
- User-facing content & code comments → French
- Technical documentation → English
- File and folder names → English
- Commit messages → English

## Contributing
Never push directly to `main`: work on a branch and open a pull request
(`.claude/rules/git-workflow.md`). The test suite must be green before a change
is called done (`.claude/rules/verification.md`).
