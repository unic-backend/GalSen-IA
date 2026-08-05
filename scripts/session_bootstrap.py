"""Inject the project memory state into a starting Claude Code session.

Wired as a ``SessionStart`` hook in ``.claude/settings.json``. Prints a JSON
envelope whose ``additionalContext`` is added to the model's context, so a new
session already knows where the previous one stopped.

Kept deliberately small: memory that costs 10 000 tokens to load is memory that
nobody wants loaded.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMORY = ROOT / "docs" / "memory"

# (file, heading, max lines kept, drop everything above the first "---" rule)
SOURCES = [
    ("session-state.md", "ETAT DE LA DERNIERE SESSION", 40, True),
    ("priorities.md", "PRIORITES", 20, False),
    ("current-objectives.md", "OBJECTIFS ACTIFS", 20, False),
    ("pending-work.md", "BACKLOG", 25, False),
]

MAX_CHARS = 6000


def read_trimmed(path: Path, max_lines: int, skip_preamble: bool = False) -> str:
    """Return the file's meaningful lines, without its own usage instructions."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return ""

    source = raw.splitlines()
    if skip_preamble:
        for index, line in enumerate(source):
            if line.strip() == "---":
                source = source[index + 1 :]
                break

    lines = []
    for line in source:
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            continue
        lines.append(line.rstrip())
        if len(lines) >= max_lines:
            lines.append("... (tronque, lire le fichier pour la suite)")
            break
    return "\n".join(lines)


def build_context() -> str:
    blocks = [
        "MEMOIRE PROJET GALSEN IA - chargee automatiquement au demarrage.",
        "Reprends le travail a partir de cet etat. Ne refais pas ce qui est marque termine.",
    ]
    for filename, heading, max_lines, skip_preamble in SOURCES:
        body = read_trimmed(MEMORY / filename, max_lines, skip_preamble)
        if not body:
            continue
        blocks.append("\n=== {} ({}) ===\n{}".format(heading, filename, body))

    blocks.append(
        "\nRegles: `.claude/rules/memory.md` (memoire), "
        "`.claude/rules/work-cadence.md` (phases, 25 min), "
        "`.claude/rules/response-style.md` (reponses courtes)."
    )
    context = "\n".join(blocks)
    if len(context) > MAX_CHARS:
        context = context[:MAX_CHARS] + "\n... (contexte tronque)"
    return context


def current_task() -> str:
    """Return the 'En cours' line of the session state, for the startup banner."""
    try:
        raw = (MEMORY / "session-state.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in raw.splitlines():
        if line.strip().startswith("**En cours**"):
            _, _, value = line.partition(":")
            return value.strip()
    return ""


def main() -> int:
    if not MEMORY.is_dir():
        return 0  # nothing to inject, never block the session

    task = current_task()
    banner = "Memoire GalSen IA chargee"
    if task:
        banner = "{} - en cours : {}".format(banner, task)

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": build_context(),
        },
        "systemMessage": banner,
        "suppressOutput": True,
    }
    json.dump(payload, sys.stdout, ensure_ascii=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # a broken bootstrap must never stop a session
        sys.exit(0)
