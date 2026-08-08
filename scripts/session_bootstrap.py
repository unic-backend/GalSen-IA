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
    ("phase-plan.md", "PHASE EN COURS - N'EN EXECUTER QU'UNE", 20, True),
    ("session-state.md", "ETAT DE LA DERNIERE SESSION", 40, True),
    ("priorities.md", "PRIORITES", 20, False),
    ("current-objectives.md", "OBJECTIFS ACTIFS", 20, False),
    ("pending-work.md", "BACKLOG", 25, False),
]

MAX_CHARS = 6000

# Le protocole de phases est repete a chaque demarrage plutot que laisse dans un
# fichier de regles : une regle qu'il faut penser a ouvrir est une regle oubliee.
PHASE_PROTOCOL = """
=== PROTOCOLE DE PHASES - OBLIGATOIRE ===
Le travail va par VOLET > chapitre > phase. Seules les phases s'executent.
1. Nouveau VOLET : publier d'abord le plan (nb de chapitres -> nb de phases),
   l'ecrire dans docs/memory/phase-plan.md, puis S'ARRETER.
2. Ensuite : UNE phase par tour. Jamais deux. Jamais un chapitre entier,
   sauf si ce chapitre ne contient qu'une seule phase.
3. Fin de phase : verifier, annoncer "Phase X.Y terminee", nommer la suivante,
   demander "Je continue ?" et ATTENDRE.
   Seul un "continuer" / "confirmer" / "oui" explicite relance le travail.
4. Mettre a jour docs/memory/phase-plan.md avant chaque arret.
Detail : `.claude/rules/phase-protocol.md`
"""


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
        PHASE_PROTOCOL.strip(),
    ]
    for filename, heading, max_lines, skip_preamble in SOURCES:
        body = read_trimmed(MEMORY / filename, max_lines, skip_preamble)
        if not body:
            continue
        blocks.append("\n=== {} ({}) ===\n{}".format(heading, filename, body))

    blocks.append(
        "\nRegles: `.claude/rules/phase-protocol.md` (une phase par tour), "
        "`.claude/rules/memory.md` (memoire), "
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


def current_phase() -> str:
    """Return the pending phase, so the banner names it before any work starts."""
    try:
        raw = (MEMORY / "phase-plan.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in raw.splitlines():
        if line.strip().startswith("**Phase courante**"):
            _, _, value = line.partition(":")
            value = value.strip()
            return "" if value in ("", "-", "—") else value
    return ""


def main() -> int:
    if not MEMORY.is_dir():
        return 0  # nothing to inject, never block the session

    banner = "Memoire GalSen IA chargee"
    phase = current_phase()
    if phase:
        # La phase passe avant l'etat de session : c'est la seule chose a faire.
        banner = "{} - phase {} (une seule)".format(banner, phase)
    else:
        task = current_task()
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
