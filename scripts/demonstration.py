#!/usr/bin/env python3
"""
Run the end-to-end demonstration and print what actually happened.

Usage:
    python scripts/demonstration.py
    python scripts/demonstration.py --json

Exit code is 1 only when a step **failed**. A step that cannot run in this
installation — generation without a model provider, acquisition without an
enabled source — is reported `NOT_CONFIGURED` and does not fail the run: it is a
capability that was never switched on, not a breakage.
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.demonstration import ECHOUE, run_demonstration  # noqa: E402

#: Largeur du nom d'étape à l'affichage.
COLONNE = 24


def afficher(rapport: dict) -> None:
    """Écrit le rapport en clair, une ligne par étape."""
    print()
    print("Démonstration de bout en bout — GalSen IA")
    print("=" * 72)
    for etape in rapport["steps"]:
        print(
            f"{etape['step']:<{COLONNE}} {etape['status']:<16} "
            f"{etape['elapsed_ms']:>8.1f} ms"
        )
        if etape.get("detail"):
            print(f"{'':<{COLONNE}} {etape['detail']}")
    print("=" * 72)
    print(f"Verdict : {rapport['verdict']}")
    if rapport["blocked"]:
        # Nommé séparément des échecs : une capacité non activée n'est pas une
        # panne, et les confondre ferait ignorer les vraies.
        print(f"Non configuré : {', '.join(rapport['blocked'])}")
    if rapport["failed"]:
        print(f"En échec : {', '.join(rapport['failed'])}")
    print()


def main() -> int:
    """Point d'entrée."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--json", action="store_true",
                           help="Écrit le rapport en JSON, pour un enchaînement.")
    arguments = analyseur.parse_args()

    # Les journaux des moteurs noieraient le rapport ; les erreurs restent.
    # `disable` plutôt qu'un niveau : chaque moteur règle le sien au démarrage,
    # et un niveau posé ici serait écrasé par le premier d'entre eux.
    logging.disable(logging.WARNING)

    rapport = run_demonstration()
    if arguments.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2, default=str))
    else:
        afficher(rapport)

    # Seul un échec fait échouer le script. Un blocage connu, non.
    return 1 if any(e["status"] == ECHOUE for e in rapport["steps"]) else 0


if __name__ == "__main__":
    sys.exit(main())
