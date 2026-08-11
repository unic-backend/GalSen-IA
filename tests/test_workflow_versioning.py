"""
Gestion des versions de workflow (VOLET 18, chapitre 03 étape 7).

Chaque workflow déclarait une `version`, le validateur exigeait qu'elle soit
présente, et **rien ne la lisait** : l'historique enregistrait l'identifiant du
workflow sans la version qui avait tourné. Changer un pipeline laissait donc les
deux définitions sous le même nom, et le taux de succès mélangeait exactement ce
qu'on cherchait à comparer.
"""

import os
import tempfile

import pytest
import yaml

from src.router.workflow_history import VERSION_INCONNUE, WorkflowHistory
from src.router.workflow_loader import WorkflowLoader


@pytest.fixture
def historique():
    """Historique vide."""
    return WorkflowHistory()


@pytest.fixture
def registre(tmp_path):
    """Registre de deux workflows, l'un versionné, l'autre non."""
    chemin = tmp_path / "workflows.yaml"
    chemin.write_text(yaml.safe_dump({
        "version": "1.0",
        "default_workflow": "standard",
        "workflows": {
            "standard": {"description": "d", "owner": "o", "version": "1.1",
                         "pipeline": ["planner"]},
            "sans_version": {"description": "d", "owner": "o", "pipeline": ["planner"]},
        },
    }), encoding="utf-8")
    return WorkflowLoader(str(chemin))


def test_la_version_declaree_est_lisible(registre):
    """Le champ existait dans le YAML sans aucun accesseur pour le lire."""
    assert registre.get_version("standard") == "1.1"


def test_un_workflow_sans_version_n_en_invente_pas(registre):
    """
    Rendre « 1.0 » ferait disparaître l'avertissement du validateur, et deux
    définitions sans version se confondraient à nouveau.
    """
    assert registre.get_version("sans_version") == "unversioned"


def test_un_workflow_inconnu_ne_leve_pas(registre):
    """Un rapport ne doit pas tomber parce qu'un workflow a été retiré."""
    assert registre.get_version("disparu") == "unversioned"


def test_l_execution_conserve_la_version(historique):
    """C'est le défaut central : elle n'était nulle part."""
    historique.record("standard", "success", 0.5, workflow_version="1.1")

    assert historique.recent(1)[0]["workflow_version"] == "1.1"


def test_deux_versions_ne_se_confondent_plus(historique):
    """
    Le cas qui motivait tout : l'ancienne définition échoue, la nouvelle non.

    Le taux global reste le même mélange qu'avant — c'est la ventilation qui
    dit laquelle des deux est en cause.
    """
    for _ in range(4):
        historique.record("standard", "error", 0.5, workflow_version="1.0")
    for _ in range(4):
        historique.record("standard", "success", 0.5, workflow_version="1.1")

    stats = historique.stats("standard")
    assert stats["success_rate"] == 0.5
    assert stats["by_version"]["1.0"]["success_rate"] == 0.0
    assert stats["by_version"]["1.1"]["success_rate"] == 1.0
    assert stats["by_version"]["1.1"]["executions"] == 4


def test_une_execution_sans_version_est_marquee_comme_telle(historique):
    """
    « Non enregistrée » et « non versionnée » sont deux cas différents.

    Le premier est un appelant qui n'a pas transmis la version ; le second un
    workflow qui n'en déclare pas. Les confondre cacherait l'un des deux.
    """
    historique.record("standard", "success", 0.5)

    assert historique.recent(1)[0]["workflow_version"] == VERSION_INCONNUE
    assert VERSION_INCONNUE in historique.stats()["by_version"]


def test_la_ventilation_est_vide_sans_execution(historique):
    """Une ventilation inventée sur zéro exécution serait pire que vide."""
    assert historique.stats()["by_version"] == {}


def test_la_ventilation_suit_le_filtre_par_workflow(historique):
    """Regarder un workflow ne doit pas faire apparaître les versions d'un autre."""
    historique.record("standard", "success", 0.5, workflow_version="1.1")
    historique.record("revue", "error", 0.5, workflow_version="2.0")

    assert list(historique.stats("standard")["by_version"]) == ["1.1"]


def test_les_agents_en_echec_sont_nommes(historique):
    """
    Compter les échecs ne dit pas si c'est toujours le même agent.

    L'analyse des défaillances du chapitre 06 demande de nommer la cause ;
    `failed_agents: 3` laisse chercher lequel des trois.
    """
    historique.record("standard", "partial_success", 1.0, failed_agents=1,
                      failing_agents=["tester"])
    historique.record("standard", "partial_success", 1.0, failed_agents=2,
                      failing_agents=["tester", "security"])

    classement = historique.stats("standard")["failing_agents"]
    assert classement == {"tester": 2, "security": 1}
    assert list(classement)[0] == "tester"


def test_un_agent_ne_compte_qu_une_fois_par_execution(historique):
    """Un agent réessayé trois fois dans la même exécution a échoué une fois."""
    historique.record("standard", "partial_success", 1.0,
                      failing_agents=["tester", "tester", "tester"])

    assert historique.stats()["failing_agents"] == {"tester": 1}


def test_sans_echec_le_classement_est_vide(historique):
    """Un classement d'échecs sans échec n'existe pas."""
    historique.record("standard", "success", 0.5, workflow_version="1.1")

    assert historique.stats()["failing_agents"] == {}
