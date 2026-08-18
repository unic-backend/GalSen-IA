"""
Ce qu'une réparation doit franchir pour être gardée (phase 7).

Le danger d'une réparation automatique n'est pas d'écrire le correctif : c'est
de **décider qu'il a marché**. Ces tests portent donc sur les portes, et sur ce
qui se passe quand elles ne peuvent pas être mesurées.

Ce qu'ils gardent :

1. **Ce qui est jugé est ce que l'espace contient réellement**, pas ce que
   l'appelant avait annoncé.
2. **Toutes les portes sont exécutées**, même après un échec.
3. **Une porte non mesurable est nommée**, jamais comptée comme franchie —
   et l'esquiver en supprimant sa cible est attrapé par l'intégrité.
4. **Les bornes de ressources arrêtent avant d'écrire.**
"""

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.agent.audit import AuditJournal  # noqa: E402
from src.agent.policies.integrity import inventory  # noqa: E402
from src.agent.self_healer import (  # noqa: E402
    MAX_OCTETS_CORRECTIF,
    GalSenSelfHealer,
)

CALCUL = "def moyenne(valeurs):\n    return sum(valeurs) / len(valeurs)\n"
CORRIGE = (
    "def moyenne(valeurs):\n"
    "    if not valeurs:\n        return 0\n"
    "    return sum(valeurs) / len(valeurs)\n"
)
TESTS = (
    "import sys\n\nsys.path.insert(0, '.')\n\nfrom src.calcul import moyenne\n\n\n"
    "def test_vide():\n    assert moyenne([]) == 0\n"
)
SECURITE = "def test_frontiere():\n    assert True\n"


def _git(arguments, cwd):
    """Lance git dans le dépôt jetable."""
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True,
    )


@pytest.fixture
def depot(tmp_path):
    """Un dépôt cassé, **avec** une suite de sécurité à `tests/agent`."""
    racine = tmp_path / "projet"
    (racine / "src").mkdir(parents=True)
    (racine / "tests" / "agent").mkdir(parents=True)
    (racine / "src" / "__init__.py").write_text("", encoding="utf-8")
    (racine / "src" / "calcul.py").write_text(CALCUL, encoding="utf-8")
    (racine / "tests" / "test_calcul.py").write_text(TESTS, encoding="utf-8")
    (racine / "tests" / "agent" / "test_frontiere.py").write_text(
        SECURITE, encoding="utf-8",
    )
    (racine / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")
    _git(["init", "-b", "principale"], racine)
    _git(["config", "user.email", "t@galsen.local"], racine)
    _git(["config", "user.name", "T"], racine)
    _git(["add", "."], racine)
    _git(["commit", "-m", "base"], racine)
    return str(racine)


@pytest.fixture
def soigneur(depot):
    """Un soigneur qui garde le dépôt jetable."""
    return GalSenSelfHealer(
        root=depot, journal=AuditJournal(persist=False),
        test_target="tests", security_target="tests/agent", lint_target="src",
    )


def _contexte(soigneur, depot, identifiant):
    """Un contexte de réparation prêt à recevoir un correctif."""
    trace = (
        "Traceback (most recent call last):\n"
        f'  File "{depot}/src/calcul.py", line 2, in moyenne\n'
        "ZeroDivisionError: division by zero\n"
    )
    return soigneur.create_patch_context(
        soigneur.diagnose(trace), incident_id=identifiant,
    )


# ----------------------------------------------------------------------
# 1. Ce qui est jugé est ce qui a été écrit
# ----------------------------------------------------------------------

def test_la_validation_lit_les_fichiers_reellement_modifies(soigneur, depot):
    """Un correctif qui touche un fichier de plus que prévu est le cas à attraper."""
    contexte = _contexte(soigneur, depot, "val-1")
    soigneur.apply_patch(contexte, {"src/calcul.py": CORRIGE})

    verdict = soigneur.validate_patch(contexte)

    assert verdict["valid"] is True
    assert verdict["changed_files"] == ["src/calcul.py"]
    assert "def moyenne" in verdict["diff"]


def test_un_fichier_ajoute_hors_correctif_est_vu(soigneur, depot):
    """La portée est mesurée sur l'espace, pas sur la déclaration."""
    contexte = _contexte(soigneur, depot, "val-2")
    applique = soigneur.apply_patch(contexte, {"src/calcul.py": CORRIGE})
    with open(os.path.join(applique["workspace"], "src", "intrus.py"),
              "w", encoding="utf-8") as fichier:
        fichier.write("x = 1\n")

    verdict = soigneur.validate_patch(contexte)

    assert "src/intrus.py" in verdict["changed_files"]


def test_valider_sans_correctif_applique_est_refuse(soigneur, depot):
    """Il n'y a rien à juger, et le dire vaut mieux que rendre « valide »."""
    contexte = _contexte(soigneur, depot, "val-3")

    verdict = soigneur.validate_patch(contexte)

    assert verdict["valid"] is False
    assert "Aucun correctif" in verdict["reason"]


# ----------------------------------------------------------------------
# 2. Toutes les portes sont exécutées
# ----------------------------------------------------------------------

def test_les_six_portes_sont_rapportees(soigneur, depot):
    """Savoir combien cèdent vaut mieux que savoir laquelle a cédé en premier."""
    contexte = _contexte(soigneur, depot, "val-4")
    soigneur.apply_patch(contexte, {"src/calcul.py": CORRIGE})

    validation = soigneur.run_validation(contexte, before=inventory(depot))

    assert set(validation["gates"]) == {
        "scope", "tests", "security_tests", "ruff",
        "test_integrity", "protected_tests",
    }
    assert validation["passed"] is True


def test_une_porte_qui_tombe_n_empeche_pas_les_autres(soigneur, depot):
    """Un correctif cassé **et** non conforme doit montrer les deux."""
    contexte = _contexte(soigneur, depot, "val-5")
    soigneur.apply_patch(contexte, {
        "src/calcul.py": "def moyenne(valeurs):\n    return 42\n",
    })

    validation = soigneur.run_validation(contexte, before=inventory(depot))

    assert "tests" in validation["failed_gates"]
    # Les autres portes ont bien été mesurées malgré l'échec.
    assert validation["gates"]["ruff"]["passed"] is True
    assert validation["gates"]["scope"]["passed"] is True


def test_ruff_fait_tomber_une_porte(soigneur, depot):
    """Le style n'est pas négociable au moment de franchir la porte."""
    contexte = _contexte(soigneur, depot, "val-6")
    soigneur.apply_patch(contexte, {
        "src/calcul.py": "import os\n\n\n" + CORRIGE,  # import inutilisé
    })

    validation = soigneur.run_validation(contexte, before=inventory(depot))

    assert "ruff" in validation["failed_gates"]


# ----------------------------------------------------------------------
# 3. Une porte non mesurable est nommée, jamais franchie
# ----------------------------------------------------------------------

def test_sans_suite_de_securite_la_porte_est_dite_non_mesuree(tmp_path):
    """
    Ce harnais garde d'autres dépôts que celui-ci.

    Une porte qui échouerait faute de cible ferait annuler **toute** réparation
    sur un dépôt sans `tests/agent` : ce n'est pas une garantie, c'est une panne.
    """
    racine = tmp_path / "sans-securite"
    (racine / "src").mkdir(parents=True)
    (racine / "tests").mkdir()
    (racine / "src" / "__init__.py").write_text("", encoding="utf-8")
    (racine / "src" / "calcul.py").write_text(CALCUL, encoding="utf-8")
    (racine / "tests" / "test_calcul.py").write_text(TESTS, encoding="utf-8")
    (racine / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")
    _git(["init", "-b", "principale"], racine)
    _git(["config", "user.email", "t@galsen.local"], racine)
    _git(["config", "user.name", "T"], racine)
    _git(["add", "."], racine)
    _git(["commit", "-m", "base"], racine)

    soigneur = GalSenSelfHealer(
        root=str(racine), journal=AuditJournal(persist=False),
        test_target="tests", lint_target="src",
    )
    contexte = _contexte(soigneur, str(racine), "val-7")
    soigneur.apply_patch(contexte, {"src/calcul.py": CORRIGE})

    validation = soigneur.run_validation(contexte, before=inventory(str(racine)))

    assert validation["gates"]["security_tests"]["applicable"] is False
    assert "not_measured" in validation
    assert validation["not_measured"] == ["security_tests"]
    assert validation["passed"] is True


def test_supprimer_la_suite_de_securite_ne_permet_pas_d_esquiver_la_porte(
    soigneur, depot
):
    """
    La porte n'est « non applicable » que si la cible manquait **déjà**.

    La faire disparaître pour l'esquiver est attrapé par l'intégrité des tests,
    qui voit les fichiers supprimés.
    """
    contexte = _contexte(soigneur, depot, "val-8")
    applique = soigneur.apply_patch(contexte, {"src/calcul.py": CORRIGE})
    os.remove(os.path.join(applique["workspace"], "tests", "agent", "test_frontiere.py"))

    validation = soigneur.run_validation(contexte, before=inventory(depot))

    assert validation["passed"] is False
    assert "test_integrity" in validation["failed_gates"]


# ----------------------------------------------------------------------
# 4. Les bornes arrêtent avant d'écrire
# ----------------------------------------------------------------------

def test_un_correctif_trop_gros_est_refuse_avant_ecriture(soigneur, depot):
    """Rien n'est écrit, donc aucun espace n'est ouvert."""
    contexte = _contexte(soigneur, depot, "val-9")

    verdict = soigneur.propose_patch(
        contexte, {"src/calcul.py": "x = 1\n" * (MAX_OCTETS_CORRECTIF // 3)},
    )

    assert verdict["accepted"] is False
    assert contexte.workspace is None


def test_le_refus_est_consigne_avec_sa_cause(depot):
    """Un refus sans cause fait réessayer à l'identique."""
    journal = AuditJournal(persist=False)
    soigneur = GalSenSelfHealer(
        root=depot, journal=journal, test_target="tests",
        security_target="tests/agent", lint_target="src",
    )
    contexte = _contexte(soigneur, depot, "val-10")

    soigneur.propose_patch(contexte, {"src/security/trust.py": "# vidé\n"})

    consignes = [e for e in journal.entries() if e["action"] == "policy"]
    assert consignes[0]["result"] == "refused"
    assert "frontière de sécurité" in consignes[0]["detail"]


def test_le_rapport_de_reparation_est_serialisable(soigneur, depot):
    """Il est lu par une chaîne d'intégration autant que par un humain."""
    contexte = _contexte(soigneur, depot, "val-11")
    soigneur.apply_patch(contexte, {"src/calcul.py": CORRIGE})

    rapport = soigneur.resolve(contexte, before=inventory(depot))

    json.dumps(rapport, default=str)
    assert rapport["decision"] == "KEEP"
    assert rapport["branch"].startswith("auto-patch/")
