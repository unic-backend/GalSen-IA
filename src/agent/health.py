"""
Is this repository in a state where a repair could run at all?

Health here is not "are the tests green" — that costs three minutes and answers a
different question. It is: **would an autonomous repair start from solid ground,
and did the previous ones leave anything behind?**

Four things are worth knowing before letting an engine touch a repository, and
each is cheap:

- **Git state.** A dirty tree is not a fault, but a repair that starts from one
  cannot tell its own changes from someone else's.
- **Protected-file integrity.** The policy names files it protects; if one no
  longer exists, the protection is a name and not a guard.
- **Leftovers.** Orphaned worktrees and `auto-patch/` branches are the trace of
  repairs that never finished. Nobody cleans what nobody names.
- **What the journal has seen.** Repairs attempted, kept, rolled back — the
  numbers that say whether this engine is useful or just busy.

Running the test suite is **not** part of this. `--with-tests` exists for the
caller who wants it and is willing to wait; the default answers in under a
second, because a health check nobody runs is worse than a shallow one.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from .audit import AuditJournal
from .policies.immutability import protected_paths
from .policies.integrity import inventory
from .tools.commands import run_ruff, run_test_suite
from .tools.git_tools import PREFIXE_BRANCHE, git_status, list_repair_workspaces
from .tools.workspace import repo_root


def repair_branches(root: Optional[str] = None) -> List[str]:
    """
    Les branches de réparation existantes.

    Une branche `auto-patch/` sans espace de travail est une réparation dont
    personne n'a décidé le sort : ni fusionnée, ni annulée.
    """
    from .tools.commands import run_command

    depot = root or repo_root()
    resultat = run_command(
        ["git", "branch", "--list", f"{PREFIXE_BRANCHE}*"], cwd=depot, root=depot,
    )
    return [
        ligne.strip().lstrip("* ").strip()
        for ligne in resultat.stdout.splitlines() if ligne.strip()
    ]


def repository_health(
    root: Optional[str] = None,
    journal: Optional[AuditJournal] = None,
    with_tests: bool = False,
) -> Dict[str, Any]:
    """
    L'état du dépôt du point de vue d'un réparateur automatique.

    Args:
        root: Le dépôt observé.
        journal: Le journal d'audit, s'il y en a un vivant.
        with_tests: Lancer aussi la suite et `ruff`. Coûteux, donc **demandé**.

    Returns:
        L'état, les restes des réparations passées, et ce qui n'a pas été
        mesuré — nommé plutôt que supposé bon.
    """
    depot = os.path.realpath(root or repo_root())
    debut = time.perf_counter()

    git = git_status(depot)
    politique = protected_paths(depot)
    espaces = list_repair_workspaces(depot)
    branches = repair_branches(depot)
    tests = inventory(depot)

    # Un espace sans branche, ou une branche sans espace : les deux sont des
    # réparations interrompues, et se voient différemment.
    chemins_ouverts = {os.path.basename(e["path"]) for e in espaces}
    branches_orphelines = sorted(
        b for b in branches if b.removeprefix(PREFIXE_BRANCHE) not in chemins_ouverts
    )

    sante: Dict[str, Any] = {
        "root": depot,
        "git": git,
        "protected_files": {
            "declared": sum(len(f["declared"]) for f in politique["families"].values()),
            "missing": politique["missing"],
            "intact": not politique["missing"],
        },
        "tests": {"files": tests["file_count"], "functions": tests["test_count"],
                  "unparsed": len(tests["unparsed"])},
        "repairs": {
            "open_workspaces": espaces,
            "repair_branches": branches,
            "orphaned_branches": branches_orphelines,
        },
        "journal": journal.journal_report() if journal is not None else {
            "measured": False,
            "reason": "Aucun journal fourni : ce processus n'a pas d'historique.",
        },
        "suite": {
            "measured": False,
            "reason": (
                "Non mesurée : la suite complète coûte des minutes. "
                "`--with-tests` la lance pour qui veut attendre."
            ),
        },
        "elapsed_ms": 0.0,
    }

    if with_tests:
        resultat = run_test_suite(cwd=depot, root=depot)
        lint = run_ruff("src", cwd=depot, root=depot)
        sante["suite"] = {
            "measured": True,
            "passed": resultat["passed"], "failed": resultat["failed"],
            "errors": resultat["errors"], "meaningful": resultat["meaningful"],
            "ruff_clean": lint["clean"],
        }

    # Le verdict porte sur ce qui a été **mesuré**. Une suite non lancée ne rend
    # pas la santé « bonne » : elle la rend partielle, et le dire est la moitié
    # de l'intérêt de ce rapport.
    problemes = []
    if politique["missing"]:
        problemes.append(
            f"{len(politique['missing'])} chemins protégés n'existent pas : la "
            "protection porte sur des noms."
        )
    if branches_orphelines:
        problemes.append(
            f"{len(branches_orphelines)} branches de réparation sans espace : "
            "des réparations dont personne n'a décidé le sort."
        )
    if tests["unparsed"]:
        problemes.append(f"{len(tests['unparsed'])} fichiers de test illisibles.")
    if with_tests and not sante["suite"]["meaningful"]:
        problemes.append("La suite ne passe pas.")

    sante["issues"] = problemes
    sante["status"] = "OK" if not problemes else "ATTENTION"
    sante["complete"] = with_tests
    sante["elapsed_ms"] = round((time.perf_counter() - debut) * 1000, 1)
    return sante


def observability(journal: AuditJournal) -> Dict[str, Any]:
    """
    Ce que les réparations ont donné, compté.

    Args:
        journal: Le journal d'audit.

    Returns:
        Tentatives, réussites, annulations, catégories les plus fréquentes.
        Les moyennes ne sont rendues **que** s'il y a de quoi les calculer :
        une moyenne sur zéro réparation est un chiffre inventé.
    """
    entrees = journal.entries(limit=2000)
    par_action: Dict[str, int] = {}
    categories: Dict[str, int] = {}

    for entree in entrees:
        par_action[entree["action"]] = par_action.get(entree["action"], 0) + 1
        if entree["action"] == "diagnosis" and "→" in entree["detail"]:
            categorie = entree["detail"].split("→")[-1].strip()
            categories[categorie] = categories.get(categorie, 0) + 1

    incidents = journal.incidents()
    annulations = par_action.get("rollback", 0)
    fusions = par_action.get("merge", 0)

    rapport: Dict[str, Any] = {
        "incidents": len(incidents),
        "by_action": dict(sorted(par_action.items())),
        "rollbacks": annulations,
        "merges": fusions,
        "failure_categories": dict(
            sorted(categories.items(), key=lambda p: p[1], reverse=True)
        ),
    }

    if incidents:
        rapport["attempts_per_incident"] = round(
            par_action.get("write", 0) / len(incidents), 2
        )
    else:
        rapport["attempts_per_incident"] = None
        rapport["note"] = (
            "Aucun incident : les moyennes ne sont pas calculées. Une moyenne "
            "sur zéro réparation serait un chiffre inventé."
        )
    return rapport
