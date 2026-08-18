"""
Proving a repair did not quietly make the tests agree with it.

The cheapest way to turn a red suite green is to remove what turns it red. An
automated repair has every incentive to find that shortcut and no judgement to
refuse it, so the shortcut is closed here rather than trusted away.

An inventory is taken before the repair and compared after. Four things are
watched, and the fourth is the one a naive check misses:

- **A test file that disappeared.** Deleting the test deletes the information.
- **A test function that disappeared.** The file can survive while the case that
  mattered does not.
- **A test that was disabled** — `@pytest.mark.skip`, `xfail`, a body reduced to
  `pass`. A skipped suite is not a passing suite.
- **A test whose assertions were removed.** The file is there, the function is
  there, the name is there, and it no longer checks anything. Counting `assert`
  per function is coarse, and coarse is the right shape here: this reports a
  **suspicion** to a gate, not a verdict to a user.

Adding tests is always allowed. A repair that brings its own regression test is
doing the right thing, and treating that as tampering would punish it.

This module reads text. It never edits, never reverts, never decides what to do
about what it found — that belongs to the validation gates.
"""

from __future__ import annotations

import ast
import os
from typing import Any, Dict, List, Optional

from ..tools.workspace import file_hash, repo_root

#: Décorateurs qui neutralisent un test.
DESACTIVATEURS = ("skip", "skipif", "xfail")


def _fichiers_de_test(racine: str, sous_repertoire: str = "tests") -> List[str]:
    """Les fichiers de test du dépôt, chemins relatifs triés."""
    base = os.path.join(racine, sous_repertoire)
    if not os.path.isdir(base):
        return []

    trouves = []
    for dossier, sous_dossiers, fichiers in os.walk(base):
        sous_dossiers[:] = [d for d in sous_dossiers if d != "__pycache__"]
        for nom in fichiers:
            if nom.startswith("test_") and nom.endswith(".py"):
                trouves.append(
                    os.path.relpath(os.path.join(dossier, nom), racine).replace(os.sep, "/")
                )
    return sorted(trouves)


def _analyser(chemin_absolu: str) -> Dict[str, Any]:
    """
    Décrit les tests d'un fichier : noms, assertions, désactivations.

    Un fichier illisible ou syntaxiquement cassé rend `parsed: False` plutôt
    qu'un inventaire vide — « je n'ai pas pu lire » et « il n'y a rien » mènent
    à des conclusions opposées.
    """
    try:
        with open(chemin_absolu, "r", encoding="utf-8") as fichier:
            source = fichier.read()
        arbre = ast.parse(source)
    except (OSError, SyntaxError) as erreur:
        return {"parsed": False, "reason": f"{type(erreur).__name__}: {erreur}",
                "tests": {}, "disabled": []}

    tests: Dict[str, int] = {}
    desactives: List[str] = []

    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not noeud.name.startswith("test_"):
            continue

        tests[noeud.name] = sum(
            1 for enfant in ast.walk(noeud)
            if isinstance(enfant, ast.Assert)
            or (isinstance(enfant, ast.Call)
                and isinstance(enfant.func, ast.Attribute)
                and enfant.func.attr in ("raises", "warns"))
        )

        for decorateur in noeud.decorator_list:
            texte = ast.dump(decorateur)
            if any(f"'{mot}'" in texte or f'"{mot}"' in texte or f"attr='{mot}'" in texte
                   for mot in DESACTIVATEURS):
                desactives.append(noeud.name)
                break

    return {"parsed": True, "tests": tests, "disabled": sorted(set(desactives))}


def inventory(root: Optional[str] = None) -> Dict[str, Any]:
    """
    L'inventaire des tests : fichiers, fonctions, assertions, empreintes.

    Args:
        root: La racine mesurée — le dépôt, ou un espace de réparation isolé.

    Returns:
        Un inventaire comparable, pris **avant** et **après** un correctif.
    """
    racine = os.path.realpath(root or repo_root())
    fichiers = _fichiers_de_test(racine)

    inventaire: Dict[str, Any] = {
        "root": racine,
        "files": {},
        "file_count": len(fichiers),
        "test_count": 0,
        "unparsed": [],
    }
    for relatif in fichiers:
        analyse = _analyser(os.path.join(racine, relatif))
        if not analyse["parsed"]:
            inventaire["unparsed"].append({"path": relatif, "reason": analyse["reason"]})
        inventaire["files"][relatif] = {
            "sha256": file_hash(relatif, racine),
            "tests": analyse["tests"],
            "disabled": analyse["disabled"],
        }
        inventaire["test_count"] += len(analyse["tests"])
    return inventaire


def compare_inventories(avant: Dict[str, Any], apres: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare deux inventaires et dit ce qui a été perdu.

    Args:
        avant: L'inventaire pris avant le correctif.
        apres: Celui pris après.

    Returns:
        Ce qui a disparu, ce qui a été désactivé, ce qui a perdu ses assertions,
        et ce qui a été ajouté. **Ajouter est toujours permis** : une réparation
        qui apporte son test de non-régression fait ce qu'il faut.
    """
    fichiers_avant = set(avant.get("files", {}))
    fichiers_apres = set(apres.get("files", {}))

    fichiers_supprimes = sorted(fichiers_avant - fichiers_apres)
    tests_supprimes: List[str] = []
    tests_desactives: List[str] = []
    assertions_retirees: List[Dict[str, Any]] = []
    tests_ajoutes: List[str] = []

    for relatif in sorted(fichiers_avant & fichiers_apres):
        anciens = avant["files"][relatif]["tests"]
        nouveaux = apres["files"][relatif]["tests"]

        tests_supprimes.extend(
            f"{relatif}::{nom}" for nom in sorted(set(anciens) - set(nouveaux))
        )
        tests_ajoutes.extend(
            f"{relatif}::{nom}" for nom in sorted(set(nouveaux) - set(anciens))
        )
        tests_desactives.extend(
            f"{relatif}::{nom}"
            for nom in sorted(set(apres["files"][relatif]["disabled"])
                              - set(avant["files"][relatif]["disabled"]))
        )
        for nom in sorted(set(anciens) & set(nouveaux)):
            if nouveaux[nom] < anciens[nom]:
                assertions_retirees.append({
                    "test": f"{relatif}::{nom}",
                    "before": anciens[nom], "after": nouveaux[nom],
                })

    for relatif in sorted(fichiers_apres - fichiers_avant):
        tests_ajoutes.extend(
            f"{relatif}::{nom}" for nom in sorted(apres["files"][relatif]["tests"])
        )

    perdu = bool(fichiers_supprimes or tests_supprimes or tests_desactives
                 or assertions_retirees)
    return {
        "intact": not perdu,
        "deleted_files": fichiers_supprimes,
        "deleted_tests": tests_supprimes,
        "disabled_tests": tests_desactives,
        "weakened_tests": assertions_retirees,
        "added_tests": tests_ajoutes,
        "test_count_before": avant.get("test_count", 0),
        "test_count_after": apres.get("test_count", 0),
        "rules": [
            "Supprimer un test supprime l'information et garde le défaut.",
            "Une suite ignorée n'est pas une suite qui passe : une "
            "désactivation ajoutée compte comme une perte.",
            "Un test qui garde son nom et perd ses assertions ne vérifie plus "
            "rien — c'est le cas qu'un simple compte de fichiers manque.",
            "Ajouter des tests est toujours permis : une réparation qui apporte "
            "sa non-régression fait ce qu'il faut.",
        ],
    }


def protected_test_hashes(root: Optional[str] = None) -> Dict[str, str]:
    """
    Les empreintes des tests protégés par la politique d'immuabilité.

    Ce sont ceux dont la moindre modification doit être vue, même si l'inventaire
    global paraît intact : un test de sécurité réécrit « proprement » reste un
    test de sécurité réécrit par un automate.
    """
    from .immutability import TESTS_PROTEGES

    racine = os.path.realpath(root or repo_root())
    empreintes: Dict[str, str] = {}
    for motif in TESTS_PROTEGES:
        chemin = os.path.join(racine, motif)
        if motif.endswith("/"):
            if not os.path.isdir(chemin):
                continue
            for relatif in _fichiers_de_test(racine, motif.rstrip("/")):
                empreintes[relatif] = file_hash(relatif, racine)
        elif os.path.isfile(chemin):
            empreintes[motif] = file_hash(motif, racine)
    return empreintes


def compare_protected_hashes(avant: Dict[str, str], apres: Dict[str, str]) -> Dict[str, Any]:
    """
    Dit si un test protégé a changé, disparu ou été ajouté.

    Returns:
        Les écarts. `unchanged` ne veut pas dire « rien n'a été tenté » : il
        veut dire que ce qui est arrivé jusqu'ici n'a rien changé.
    """
    modifies = sorted(
        nom for nom in set(avant) & set(apres) if avant[nom] != apres[nom]
    )
    return {
        "unchanged": not modifies and set(avant) <= set(apres),
        "modified": modifies,
        "removed": sorted(set(avant) - set(apres)),
        "added": sorted(set(apres) - set(avant)),
    }
