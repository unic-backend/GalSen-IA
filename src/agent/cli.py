"""
The harness from a terminal.

    python -m src.agent.cli status
    python -m src.agent.cli health [--with-tests]
    python -m src.agent.cli test [--target tests/agent]
    python -m src.agent.cli diagnose --trace "<traceback>"
    python -m src.agent.cli repair --trace "<traceback>" --patch fichier.json
    python -m src.agent.cli audit [--incident inc-x]

One rule governs the whole surface: **no command modifies the repository unless
it is `repair`, and `repair` writes only inside its isolated worktree.** Reading
about a failure must never be the thing that changes it — an operator diagnosing
at three in the morning should be able to type anything here and know the tree
is the same afterwards.

`repair` takes its patch from a file rather than the command line. A patch is
source code; passing it as an argument would mean shell quoting decides what
gets written, and the values involved come from tracebacks.

Exit codes: 0 when the command answered, 1 when it refused or the repair was
rolled back, 2 on a usage error. A rolled-back repair is a **successful**
refusal, and the code says 1 so a pipeline notices.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.agent.audit import AuditJournal  # noqa: E402
from src.agent.health import observability, repository_health  # noqa: E402
from src.agent.policies.integrity import inventory  # noqa: E402
from src.agent.self_healer import GalSenSelfHealer  # noqa: E402
from src.agent.tools.commands import run_test_suite  # noqa: E402
from src.agent.tools.git_tools import git_status, list_repair_workspaces  # noqa: E402
from src.agent.tools.workspace import read_file, repo_root  # noqa: E402


def _ecrire(donnees: Dict[str, Any], json_sortie: bool) -> None:
    """Écrit un rapport, en JSON ou en clair."""
    if json_sortie:
        print(json.dumps(donnees, ensure_ascii=False, indent=2, default=str))
        return
    for cle, valeur in donnees.items():
        if isinstance(valeur, (dict, list)):
            print(f"{cle}:")
            print("  " + json.dumps(valeur, ensure_ascii=False, indent=2,
                                    default=str).replace("\n", "\n  "))
        else:
            print(f"{cle}: {valeur}")


def commande_status(arguments: argparse.Namespace) -> int:
    """L'état git et les réparations en cours. Ne modifie rien."""
    depot = arguments.root or repo_root()
    _ecrire({
        "root": depot,
        "git": git_status(depot),
        "open_workspaces": list_repair_workspaces(depot),
        "tests": {k: v for k, v in inventory(depot).items()
                  if k in ("file_count", "test_count")},
    }, arguments.json)
    return 0


def commande_health(arguments: argparse.Namespace) -> int:
    """La santé du dépôt du point de vue d'un réparateur."""
    sante = repository_health(
        root=arguments.root, journal=AuditJournal(persist=False),
        with_tests=arguments.with_tests,
    )
    _ecrire(sante, arguments.json)
    return 0 if sante["status"] == "OK" else 1


def commande_test(arguments: argparse.Namespace) -> int:
    """Lance la suite, ou une partie. Ne modifie rien."""
    resultat = run_test_suite(
        target=arguments.target, cwd=arguments.root, root=arguments.root,
    )
    _ecrire({
        "passed": resultat["passed"], "failed": resultat["failed"],
        "errors": resultat["errors"], "skipped": resultat["skipped"],
        "meaningful": resultat["meaningful"], "timed_out": resultat["timed_out"],
        "elapsed_ms": resultat["elapsed_ms"],
    }, arguments.json)
    return 0 if resultat["meaningful"] else 1


def commande_diagnose(arguments: argparse.Namespace) -> int:
    """Lit une trace et dit ce qu'elle permet d'affirmer. Ne modifie rien."""
    soigneur = GalSenSelfHealer(root=arguments.root, journal=AuditJournal(persist=False))
    diagnostic = soigneur.diagnose(_trace(arguments))
    _ecrire(diagnostic.as_dict(), arguments.json)
    return 0 if diagnostic.confident else 1


def commande_repair(arguments: argparse.Namespace) -> int:
    """
    Tente une réparation, **dans un espace isolé**.

    Le correctif vient d'un fichier JSON `{"chemin": "contenu complet"}` : un
    correctif passé en argument ferait décider au shell ce qui s'écrit, et les
    valeurs en jeu viennent de traces d'exécution.
    """
    if not arguments.patch:
        print(
            "Aucun correctif fourni. `repair` applique un correctif écrit par "
            "quelqu'un ou par un agent, il n'en invente pas : --patch "
            "fichier.json, de la forme {\"src/x.py\": \"contenu complet\"}.",
            file=sys.stderr,
        )
        return 2

    try:
        changes = json.loads(read_file(arguments.patch, root=arguments.root))
    except Exception as erreur:
        print(f"Correctif illisible : {erreur}", file=sys.stderr)
        return 2
    if not isinstance(changes, dict) or not all(
        isinstance(c, str) and isinstance(v, str) for c, v in changes.items()
    ):
        print(
            "Le correctif doit être un objet {chemin: contenu}. Toute autre "
            "forme serait interprétée, et interpréter est ce qu'on évite ici.",
            file=sys.stderr,
        )
        return 2

    journal = AuditJournal()
    soigneur = GalSenSelfHealer(root=arguments.root, journal=journal)
    diagnostic = soigneur.diagnose(_trace(arguments))
    contexte = soigneur.create_patch_context(
        diagnostic, repair_class=arguments.repair_class,
    )

    avant = inventory(soigneur.root)
    try:
        soigneur.apply_patch(contexte, changes)
    except Exception as refus:
        _ecrire({"decision": "REFUSED", "reason": str(refus),
                 "incident_id": contexte.incident_id}, arguments.json)
        return 1

    rapport = soigneur.resolve(contexte, before=avant, merge=arguments.merge)
    _ecrire(rapport, arguments.json)
    return 0 if rapport["decision"] == "KEEP" else 1


def commande_audit(arguments: argparse.Namespace) -> int:
    """Le journal des actions autonomes, et ce qu'elles ont donné."""
    journal = AuditJournal()
    _ecrire({
        "report": journal.journal_report(),
        "observability": observability(journal),
        "entries": journal.entries(incident_id=arguments.incident, limit=arguments.limit),
    }, arguments.json)
    return 0


def _trace(arguments: argparse.Namespace) -> str:
    """
    La trace, prise à l'argument ou à l'entrée standard.

    Elle reste une **donnée** dans les deux cas : rien de ce qu'elle contient
    n'est exécuté ni suivi comme une consigne.
    """
    if arguments.trace:
        return str(arguments.trace)
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def build_parser() -> argparse.ArgumentParser:
    """Construit l'analyseur d'arguments."""
    analyseur = argparse.ArgumentParser(
        prog="python -m src.agent.cli",
        description="Harnais d'ingénierie autonome de GalSen IA.",
    )
    analyseur.add_argument("--root", default=None, help="Le dépôt gardé.")
    analyseur.add_argument("--json", action="store_true", help="Sortie JSON.")

    # Les mêmes options après la sous-commande : `cli health --json` est ce que
    # tout le monde tape en premier, et un piège d'ordre d'arguments n'apprend
    # rien à personne.
    commun = argparse.ArgumentParser(add_help=False)
    commun.add_argument("--root", default=None, help="Le dépôt gardé.")
    commun.add_argument("--json", action="store_true", help="Sortie JSON.")

    sous = analyseur.add_subparsers(dest="command", required=True)

    sous.add_parser("status", parents=[commun],
                    help="État git et réparations en cours.")

    sante = sous.add_parser("health", parents=[commun],
                            help="Santé du dépôt pour un réparateur.")
    sante.add_argument("--with-tests", action="store_true",
                       help="Lance aussi la suite complète (coûteux).")

    essai = sous.add_parser("test", parents=[commun], help="Lance la suite ou une partie.")
    essai.add_argument("--target", default=None, help="Fichier ou répertoire.")

    diagnostic = sous.add_parser("diagnose", parents=[commun], help="Lit une trace d'exécution.")
    diagnostic.add_argument("--trace", default=None, help="La trace ; sinon stdin.")

    reparation = sous.add_parser("repair", parents=[commun], help="Tente une réparation isolée.")
    reparation.add_argument("--trace", default=None, help="La trace ; sinon stdin.")
    reparation.add_argument("--patch", default=None,
                            help="Fichier JSON {chemin: contenu}.")
    reparation.add_argument("--repair-class", dest="repair_class", default="ORDINARY",
                            choices=["ORDINARY", "SECURITY_MAINTENANCE"])
    reparation.add_argument("--merge", action="store_true",
                            help="Valide sur la branche de réparation si tout passe.")

    journal = sous.add_parser("audit", parents=[commun], help="Le journal des actions autonomes.")
    journal.add_argument("--incident", default=None, help="Filtrer un incident.")
    journal.add_argument("--limit", type=int, default=20)

    return analyseur


COMMANDES = {
    "status": commande_status,
    "health": commande_health,
    "test": commande_test,
    "diagnose": commande_diagnose,
    "repair": commande_repair,
    "audit": commande_audit,
}


def main(argv: Optional[List[str]] = None) -> int:
    """Point d'entrée."""
    arguments = build_parser().parse_args(argv)
    return COMMANDES[arguments.command](arguments)


if __name__ == "__main__":
    sys.exit(main())
