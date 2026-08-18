"""
Tests de l'agent `tester` (VOLET 06, chapitres 06 et 09).

L'agent lançait `python <suite>`, ce qui n'exécute que le bloc `__main__` d'un
fichier. **20 des 92 suites en ont un** : les 72 autres s'importaient sans lancer
un test et sortaient à 0, donc l'agent les comptait comme réussies. Un rapport
disant « 92 suites vertes » alors que 72 n'ont rien exécuté est une fabrication,
pas une mesure.
"""

import sys
from pathlib import Path

import pytest

from src.agent.context import AgentContext
from src.integration.engine_registry import get_shared_registry

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.tester.agent import TesterAgent  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture
def agent():
    """Agent testeur et contexte partagé."""
    contexte = AgentContext(request="Tester le projet", agent_id="router",
                            registry=get_shared_registry())
    return TesterAgent(), contexte


def test_une_suite_sans_bloc_main_execute_ses_tests(agent):
    """Le cas qui échouait en silence : un fichier pytest sans `__main__`."""
    testeur, contexte = agent
    cible = "tests/test_knowledge_domain.py"
    assert "__main__" not in (RACINE / cible).read_text(encoding="utf-8"), (
        "Ce test perd son sens si la suite gagne un bloc __main__"
    )

    resultat = testeur._run_suite(contexte, cible)
    assert resultat["passed"] is True
    assert resultat["tests"] > 0, "La suite n'a exécuté aucun test"


def test_une_suite_sans_test_collecte_n_est_pas_verte(agent, tmp_path):
    """Zéro test exécuté n'est pas un succès, même avec un code de retour nul."""
    vide = tmp_path / "test_vide_sans_aucun_test.py"
    vide.write_text('"""Fichier sans aucun test."""\n', encoding="utf-8")

    testeur, contexte = agent
    resultat = testeur._run_suite(contexte, str(vide))
    assert resultat["passed"] is False
    assert resultat["tests"] == 0
    assert "aucun test" in resultat["reason"]


def test_le_compte_de_tests_lit_le_resume_de_pytest(agent):
    """Le compte vient de la sortie réelle, jamais d'une estimation."""
    testeur, _ = agent
    assert testeur._count_tests("7 passed in 0.12s") == 7
    assert testeur._count_tests("5 passed, 2 failed in 1.0s") == 7
    assert testeur._count_tests("3 passed, 1 error in 0.4s") == 4
    # Aucun résumé : on ne suppose rien.
    assert testeur._count_tests("sortie sans résumé") == 0


def test_les_suites_d_orchestration_restent_ecartees(agent):
    """Lancer l'orchestration depuis un agent orchestré reste circulaire."""
    testeur, contexte = agent
    suites = ["tests/test_router.py", "tests/test_agent_runtime.py", "tests/test_rbac.py"]
    executables, ecartees = testeur._exclude_orchestration_suites(suites, contexte)
    assert executables == ["tests/test_rbac.py"]
    assert {e["suite"] for e in ecartees} == {"tests/test_router.py", "tests/test_agent_runtime.py"}


def test_le_lot_attribue_chaque_echec_a_sa_suite(agent, tmp_path):
    """Un lot unique ne doit pas noyer l'information : qui échoue reste nommé.

    C'est la contrepartie du gain de vitesse — 97 s en 92 processus contre
    38,6 s en un seul. Un rapport plus rapide qui ne dit plus quelle suite a
    échoué serait un mauvais échange.
    """
    (tmp_path / "test_lot_qui_passe.py").write_text("def test_ok():\n    assert True\n",
                                                    encoding="utf-8")
    (tmp_path / "test_lot_qui_echoue.py").write_text("def test_ko():\n    assert 1 == 2\n",
                                                     encoding="utf-8")

    testeur, contexte = agent
    resultats = testeur._run_batch(contexte, [
        str(tmp_path / "test_lot_qui_passe.py"),
        str(tmp_path / "test_lot_qui_echoue.py"),
    ])

    par_suite = {Path(r["suite"]).name: r["passed"] for r in resultats}
    assert par_suite == {"test_lot_qui_passe.py": True, "test_lot_qui_echoue.py": False}
    # L'échec conserve la sortie qui permet de comprendre.
    echec = next(r for r in resultats if not r["passed"])
    assert echec.get("output")


def test_un_lot_sans_aucun_test_ne_passe_pas(agent, tmp_path):
    """Zéro test collecté sur le lot entier : aucune suite ne peut être verte."""
    (tmp_path / "test_lot_vide.py").write_text('"""Rien."""\n', encoding="utf-8")

    testeur, contexte = agent
    resultats = testeur._run_batch(contexte, [str(tmp_path / "test_lot_vide.py")])
    assert all(not r["passed"] for r in resultats)
    assert all("aucun test" in r["reason"] for r in resultats)


def test_un_lot_vide_ne_lance_rien(agent):
    """Aucune suite retenue : pas d'appel, pas de résultat inventé."""
    testeur, contexte = agent
    assert testeur._run_batch(contexte, []) == []
