# Documentation Rules — GalSen IA

## Language
- Technical documentation → English
- User-facing explanations → French
- Code comments → French

## Principles
- Never duplicate information. Update the existing file instead.
- Prefer short and clear documentation over long texts.
- Always keep documentation synchronized with the actual state of the project.
- When you create or change important knowledge, update `docs/memory/knowledge-index.md`.

## After significant work
You must update:
1. `docs/memory/completed-work.md`
2. `docs/changelog/CHANGELOG.md`
3. `docs/tasks/TASKS.md` (move the task to Done)

## Architecture decisions
All important technical decisions must be written as Architecture Decision Records (ADRs) in:
`docs/architecture/decisions/`