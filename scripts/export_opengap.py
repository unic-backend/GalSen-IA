#!/usr/bin/env python3
"""
Exporte les agents de GalSen IA au format OpenGAP (ADR-023).

Chaque agent de `agents/registry.yaml` devient un dossier
`interop/opengap/<nom>/` contenant `agent.yaml` et `SOUL.md`. Ces dossiers sont
versionnés : ils sont le livrable, pas un artefact de build. `tests/test_opengap.py`
échoue si le registre change sans que l'export soit refait.

Usage :

    python scripts/export_opengap.py
    python scripts/export_opengap.py --destination /un/autre/dossier
"""

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.interop.opengap import OpenGAPError, exporter_registre  # noqa: E402
from src.version import __version__  # noqa: E402

REGISTRE = RACINE / "agents" / "registry.yaml"
DESTINATION = RACINE / "interop" / "opengap"


def main() -> int:
    """Exporte le registre et rapporte ce qui a été écrit."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument(
        "--destination",
        default=str(DESTINATION),
        help="Dossier parent des agents exportés.",
    )
    arguments = analyseur.parse_args()

    try:
        dossiers = exporter_registre(REGISTRE, arguments.destination, __version__)
    except OpenGAPError as erreur:
        print(f"Export impossible : {erreur}", file=sys.stderr)
        return 1

    for dossier in dossiers:
        print(f"  {dossier.relative_to(RACINE) if RACINE in dossier.parents else dossier}")
    print(f"{len(dossiers)} agents exportés en version {__version__}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
