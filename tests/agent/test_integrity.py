"""
Un correctif n'a pas le droit de faire taire les tests (phase 5).

La façon la moins chère de rendre une suite verte est de retirer ce qui la rend
rouge. Une réparation automatique a toutes les raisons de trouver ce raccourci
et aucun jugement pour le refuser, donc il est fermé ici.

Ce que ces tests gardent :

1. **Un fichier ou une fonction de test disparue est vue.**
2. **Une désactivation ajoutée compte comme une perte** : une suite ignorée
   n'est pas une suite qui passe.
3. **Un test qui garde son nom et perd ses assertions est vu** — c'est le cas
   qu'un simple compte de fichiers manque.
4. **Ajouter des tests reste permis** : une réparation qui apporte sa
   non-régression fait ce qu'il faut.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.agent.policies.integrity import (  # noqa: E402
    compare_inventories,
    compare_protected_hashes,
    protected_test_hashes,
)
# Importé sous un autre nom : `test_inventory` commence par `test_`, et pytest
# collecterait la fonction du harnais comme s'il s'agissait d'un test.
from src.agent.policies.integrity import test_inventory as inventaire  # noqa: E402


@pytest.fixture
def depot(tmp_path):
    """Un faux dépôt avec deux fichiers de test."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_calcul.py").write_text(
        "def test_somme():\n"
        "    assert 1 + 1 == 2\n"
        "\n"
        "def test_produit():\n"
        "    assert 2 * 3 == 6\n"
        "    assert 2 * 0 == 0\n",
        encoding="utf-8",
    )
    (tests / "test_bord.py").write_text(
        "def test_limite():\n    assert True\n", encoding="utf-8",
    )
    return tmp_path


def _ecrire(depot, relatif, contenu):
    """Réécrit un fichier de test du faux dépôt."""
    (depot / relatif).write_text(contenu, encoding="utf-8")


# ----------------------------------------------------------------------
# 1. Disparitions
# ----------------------------------------------------------------------

def test_un_inventaire_identique_est_intact(depot):
    """Le cas nominal : rien n'a bougé."""
    pris = inventaire(str(depot))

    assert compare_inventories(pris, pris)["intact"] is True


def test_un_fichier_de_test_supprime_est_vu(depot):
    """Supprimer le test supprime l'information et garde le défaut."""
    avant = inventaire(str(depot))
    os.remove(depot / "tests" / "test_bord.py")

    verdict = compare_inventories(avant, inventaire(str(depot)))

    assert verdict["intact"] is False
    assert verdict["deleted_files"] == ["tests/test_bord.py"]


def test_une_fonction_de_test_supprimee_est_vue(depot):
    """Le fichier survit, le cas qui comptait non."""
    avant = inventaire(str(depot))
    _ecrire(depot, "tests/test_calcul.py", "def test_somme():\n    assert 1 + 1 == 2\n")

    verdict = compare_inventories(avant, inventaire(str(depot)))

    assert verdict["deleted_tests"] == ["tests/test_calcul.py::test_produit"]


# ----------------------------------------------------------------------
# 2. Désactivations
# ----------------------------------------------------------------------

def test_une_desactivation_ajoutee_compte_comme_une_perte(depot):
    """Une suite ignorée n'est pas une suite qui passe."""
    avant = inventaire(str(depot))
    _ecrire(
        depot, "tests/test_bord.py",
        "import pytest\n\n@pytest.mark.skip(reason='plus tard')\n"
        "def test_limite():\n    assert True\n",
    )

    verdict = compare_inventories(avant, inventaire(str(depot)))

    assert verdict["intact"] is False
    assert verdict["disabled_tests"] == ["tests/test_bord.py::test_limite"]


def test_un_xfail_ajoute_est_aussi_une_desactivation(depot):
    """Un échec attendu ne vérifie plus la chose attendue."""
    avant = inventaire(str(depot))
    _ecrire(
        depot, "tests/test_bord.py",
        "import pytest\n\n@pytest.mark.xfail\ndef test_limite():\n    assert True\n",
    )

    verdict = compare_inventories(avant, inventaire(str(depot)))

    assert verdict["disabled_tests"] == ["tests/test_bord.py::test_limite"]


# ----------------------------------------------------------------------
# 3. Assertions retirées
# ----------------------------------------------------------------------

def test_un_test_vide_de_ses_assertions_est_vu(depot):
    """Le nom reste, la vérification part : c'est le cas le plus discret."""
    avant = inventaire(str(depot))
    _ecrire(
        depot, "tests/test_calcul.py",
        "def test_somme():\n    assert 1 + 1 == 2\n\ndef test_produit():\n    pass\n",
    )

    verdict = compare_inventories(avant, inventaire(str(depot)))

    assert verdict["intact"] is False
    assert verdict["weakened_tests"][0]["test"] == "tests/test_calcul.py::test_produit"
    assert verdict["weakened_tests"][0]["before"] == 2
    assert verdict["weakened_tests"][0]["after"] == 0


def test_une_assertion_retiree_sur_deux_est_vue(depot):
    """L'affaiblissement partiel est le plus facile à laisser passer."""
    avant = inventaire(str(depot))
    _ecrire(
        depot, "tests/test_calcul.py",
        "def test_somme():\n    assert 1 + 1 == 2\n\n"
        "def test_produit():\n    assert 2 * 3 == 6\n",
    )

    verdict = compare_inventories(avant, inventaire(str(depot)))

    assert verdict["weakened_tests"][0]["after"] == 1


def test_un_pytest_raises_compte_comme_une_verification(depot):
    """Sinon remplacer un `assert` par un `raises` paraîtrait un affaiblissement."""
    avant = inventaire(str(depot))
    _ecrire(
        depot, "tests/test_bord.py",
        "import pytest\n\ndef test_limite():\n"
        "    with pytest.raises(ValueError):\n        raise ValueError('x')\n",
    )

    verdict = compare_inventories(avant, inventaire(str(depot)))

    assert verdict["weakened_tests"] == []


# ----------------------------------------------------------------------
# 4. Ajouter est permis
# ----------------------------------------------------------------------

def test_ajouter_un_test_ne_casse_pas_l_integrite(depot):
    """Une réparation qui apporte sa non-régression fait ce qu'il faut."""
    avant = inventaire(str(depot))
    _ecrire(
        depot, "tests/test_bord.py",
        "def test_limite():\n    assert True\n\ndef test_nouveau():\n    assert 1\n",
    )

    verdict = compare_inventories(avant, inventaire(str(depot)))

    assert verdict["intact"] is True
    assert verdict["added_tests"] == ["tests/test_bord.py::test_nouveau"]


def test_un_fichier_illisible_est_nomme_pas_compte_vide(depot):
    """« Je n'ai pas pu lire » et « il n'y a rien » mènent à deux conclusions."""
    _ecrire(depot, "tests/test_casse.py", "def test_(:\n")

    pris = inventaire(str(depot))

    assert pris["unparsed"][0]["path"] == "tests/test_casse.py"


# ----------------------------------------------------------------------
# 5. Les tests protégés, par empreinte
# ----------------------------------------------------------------------

def test_les_tests_proteges_du_depot_sont_empreints():
    """Un test de sécurité réécrit proprement reste réécrit par un automate."""
    empreintes = protected_test_hashes()

    assert len(empreintes) >= 15
    assert any(nom.startswith("tests/agent/") for nom in empreintes)
    assert "tests/test_rbac.py" in empreintes


def test_une_modification_de_test_protege_est_vue():
    """C'est une comparaison d'empreintes, pas une lecture de bonne foi."""
    avant = {"tests/test_rbac.py": "aaa", "tests/test_trust.py": "bbb"}
    apres = {"tests/test_rbac.py": "ccc", "tests/test_trust.py": "bbb"}

    verdict = compare_protected_hashes(avant, apres)

    assert verdict["unchanged"] is False
    assert verdict["modified"] == ["tests/test_rbac.py"]


def test_un_test_protege_disparu_est_vu():
    """La disparition est une modification comme une autre, en pire."""
    verdict = compare_protected_hashes({"tests/test_rbac.py": "aaa"}, {})

    assert verdict["removed"] == ["tests/test_rbac.py"]
    assert verdict["unchanged"] is False
