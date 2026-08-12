"""
Un passage de découverte proactive, lancé par un opérateur ou par `cron`.

Rien ne tourne tout seul dans l'API : ce script est le déclencheur explicite, et
c'est un choix. Un fil de fond dans le processus demanderait de décider ce qu'il
se passe avec deux instances (ADR-009 n'en autorise qu'une) et de le vérifier
sans horloge ; à moitié fait, il donnerait la pire des situations — une
découverte qu'on croit active et qui ne tourne pas.

    python scripts/proactive_scan.py            # affiche ce qui mérite d'être dit
    python scripts/proactive_scan.py --json     # même chose, pour un pipeline

Sortie : 0 si rien ne bloque, 1 s'il existe au moins une observation
« blocking ». Un `cron` peut donc alerter sur le code de retour.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.proactive import scan  # noqa: E402


def main() -> int:
    """Exécute un passage et rend le code de sortie."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--json", action="store_true", help="Sortie JSON brute.")
    analyseur.add_argument(
        "--no-record", action="store_true",
        help="Ne pas inscrire au journal ce qui a été montré.",
    )
    arguments = analyseur.parse_args()

    resultat = scan(record=not arguments.no_record)

    if arguments.json:
        print(json.dumps(resultat, ensure_ascii=False, indent=2))
    else:
        _afficher(resultat)

    bloquantes = [o for o in resultat["observations"] if o["priority"] == "blocking"]
    return 1 if bloquantes else 0


def _afficher(resultat) -> None:
    """Affiche le résultat pour un humain."""
    if not resultat["observations"]:
        print("Rien à signaler.")
        if resultat["silenced"]:
            print(f"({resultat['silenced']} observation(s) déjà écartée(s), inchangée(s).)")
    for observation in resultat["observations"]:
        print(f"[{observation['priority']}] {observation['finding']}")
        print(f"    → {observation['suggested_action']}")
        print(f"    preuve : {observation['evidence']}")
        print(f"    écarter : id={observation['id']} empreinte={observation['fingerprint']}")

    for panne in resultat["detectors_failed"]:
        print(f"[détecteur en panne] {panne['detector']} : {panne['reason']}")


if __name__ == "__main__":
    sys.exit(main())
