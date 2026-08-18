"""
Tests de la structure du projet (VOLET 03, chapitre 03).

`.claude/rules/testing.md` exige que les tests vivent dans `tests/`. 27 fichiers
sont restés à la racine pendant des mois, verts et collectés : rien ne pouvait le
signaler puisque tout passait. Ce test le signale.
"""

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def test_aucun_fichier_de_test_a_la_racine():
    """Les tests appartiennent à `tests/`, pas à la racine du dépôt."""
    egares = sorted(p.name for p in RACINE.glob("test_*.py"))
    assert egares == [], (
        "Ces fichiers de test doivent être déplacés dans tests/ : " + ", ".join(egares)
    )


def test_les_tests_deplaces_calculent_bien_la_racine():
    """Un test dans `tests/` qui ajoute `dirname(__file__)` au path vise le mauvais dossier.

    C'est l'erreur qu'a produite le déplacement : le dossier du test n'est plus la
    racine du dépôt, et l'import de `src` ne tenait que par accident.
    """
    fautifs = []
    for chemin in sorted((RACINE / "tests").glob("test_*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            cible = getattr(noeud.func, "attr", None)
            if cible != "insert" or len(noeud.args) < 2:
                continue
            argument = ast.dump(noeud.args[1])
            # `dirname(__file__)` seul, sans remontée d'un niveau, désigne tests/.
            if "'dirname'" in argument and "'..'" not in argument and "'join'" not in argument:
                fautifs.append(chemin.name)
                break
    assert fautifs == [], (
        "Ces tests ajoutent tests/ au sys.path au lieu de la racine : " + ", ".join(fautifs)
    )


def test_la_racine_ne_porte_pas_de_module_orphelin():
    """Un script de vérification à la racine est soit un test, soit dans `scripts/`."""
    attendus = {"conftest.py", "serveur_cerveau.py"}
    modules = {p.name for p in RACINE.glob("*.py")} - attendus
    assert modules == {"check_rbac_integration.py"}, (
        "Nouveau module à la racine : le placer dans scripts/ ou tests/ — " + ", ".join(sorted(modules))
    )
