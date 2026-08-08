# GalSen IA — Claude Code Context

## Project
GalSen IA is a long-term AI platform starting in Senegal, expanding to Africa, then globally.  
Focus: practical AI agents, data platforms, and tools for African contexts first.

**Languages**
- User-facing explanations & code comments → French
- Technical documentation → English
- File & folder names → English
- Commit messages → English
- Prompt files → English

## Critical Behavior (MUST follow)
- ALWAYS answer the user in French, even if the user writes in English.
- Write all code comments in French.
- Before any architectural or priority decision → read `docs/memory/` files first.
- Prefer reusing existing architecture over creating new patterns.
- Never duplicate documentation. Update the existing file instead.
- Keep answers under 8 lines by default → `.claude/rules/response-style.md`.
- **One phase per turn. Never two, never a whole chapter** → `.claude/rules/phase-protocol.md`.
  Opening a VOLET starts with a phase plan (chapters → phases) and nothing else.
  Every phase ends with `Je continue ?` and waits for an explicit confirmation.
- Work in phases of ≤ 8 min; at 25 min elapsed, stop and ask → `.claude/rules/work-cadence.md`.
- Ask for clarification when requirements are ambiguous.
- Never call work done without running it → `.claude/rules/verification.md`.
- After completing significant work → update `docs/memory/` and `docs/changelog/CHANGELOG.md` following `.claude/rules/memory.md`.

## Memory System (consult first)
Read/write protocol → `.claude/rules/memory.md`

`docs/memory/session-state.md` is injected automatically at session start by the
`SessionStart` hook (`scripts/session_bootstrap.py`) — it already tells you where the
last session stopped. Keep it up to date; it is the project's continuity.

| File | Purpose |
|------|---------|
| `docs/memory/phase-plan.md` | The VOLET's phase plan and the one pending phase — auto-loaded |
| `docs/memory/session-state.md` | Where the last session stopped — auto-loaded |
| `docs/memory/priorities.md` | Current ranking of work — read first |
| `docs/memory/current-objectives.md` | Active goals |
| `docs/memory/pending-work.md` | Backlog |
| `docs/memory/vision.md` | Long-term vision & principles |
| `docs/memory/knowledge-index.md` | Index of domain knowledge |
| `docs/memory/multi-platform-directive.md` | Platform coverage constraints |
| `docs/memory/completed-work.md` | Append-only log — search it, never read it whole |

## Architecture & Decisions
- High-level: `docs/architecture/overview.md`
- All technical decisions: `docs/architecture/decisions/` (ADR format)

## Standards (load on demand)
- Phase protocol → `.claude/rules/phase-protocol.md`
- Memory → `.claude/rules/memory.md`
- Answer style → `.claude/rules/response-style.md`
- Work cadence & token economy → `.claude/rules/work-cadence.md`
- Verification & definition of done → `.claude/rules/verification.md`
- Coding → `.claude/rules/coding-conventions.md` + `docs/standards/coding.md`
- Security → `.claude/rules/security.md`
- Documentation → `.claude/rules/documentation.md`
- Prompts → `.claude/rules/prompts.md`
- Git → `.claude/rules/git-workflow.md`
- Testing → `.claude/rules/testing.md`

## Hard Rules
- NEVER commit secrets or `.env` files.
- NEVER push directly to `main`.
- NEVER invent architecture that contradicts existing ADRs.
- ALWAYS update `docs/memory/completed-work.md` and `CHANGELOG.md` after meaningful progress.

## Current Status
Foundation phase is complete (ADR-001 Python, ADR-002 technology stack).
The project is now building its **core engines** in `src/` — see `docs/architecture/overview.md`
for the list, the shared conventions and what remains.

Persistence is decided and implemented (ADR-005, SQLite): memory, model and knowledge
select their store through `GALSEN_STORAGE_BACKEND` (`in-memory` by default, `sqlite` to
persist) and `GALSEN_DATA_DIR`. The audit and approval engines and the three backend
services are still in-memory only — extending them reuses `src/storage/`, no new ADR.