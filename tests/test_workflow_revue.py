"""
Tests du second workflow (VOLET_04 ch. 02, critère de sortie C3).

C3 exige que `workflows/workflows.yaml` déclare **au moins deux** workflows et
qu'un test en exécute un de bout en bout, produisant un résultat différent de
`standard`. Un seul pipeline ne démontrait pas l'automatisation : il démontrait
le chargeur.

`revue` a été choisi parce qu'il est réellement utile et réellement testable :
ses deux agents font de l'analyse statique, donc aucun modèle n'est requis et le
pipeline complet s'exécute en une fraction de seconde.

Ce fichier n'exécute **jamais** `standard`. Ce workflow contient l'agent
`tester`, qui lance de vraies suites — l'exécuter ici ferait tourner pytest à
l'intérieur de pytest. Les deux workflows sont donc comparés sur leur *plan*,
et seul `revue` est exécuté.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.router.router_engine import RouterEngine  # noqa: E402
from src.router.workflow_loader import WorkflowLoader  # noqa: E402

REGISTRE = os.path.join(os.path.dirname(__file__), "..", "workflows", "workflows.yaml")


@pytest.fixture(scope="module")
def chargeur():
    """Chargeur lisant le registre livré."""
    return WorkflowLoader(os.path.abspath(REGISTRE))


@pytest.fixture(scope="module")
def execution_revue():
    """Exécute `revue` une seule fois et partage son résultat.

    Portée module : le pipeline relit tout `src/`, ce qui est rapide mais pas
    gratuit. Le refaire à chaque test n'apprendrait rien de plus.
    """
    return RouterEngine().process_request(
        "Relis les modifications récentes", workflow_id="revue"
    )


class TestDeclaration:
    """Le registre doit porter plus d'un workflow, et ils doivent différer."""

    def test_au_moins_deux_workflows(self, chargeur):
        """C'est la première moitié de C3, littéralement."""
        assert len(chargeur.workflows) >= 2, list(chargeur.workflows)

    def test_revue_est_declare(self, chargeur):
        """Le second workflow doit exister sous un nom stable."""
        assert chargeur.get_workflow("revue")

    def test_les_deux_pipelines_different(self, chargeur):
        """Deux workflows identiques ne prouveraient rien de plus qu'un seul."""
        standard = chargeur.get_workflow("standard")["pipeline"]
        revue = chargeur.get_workflow("revue")["pipeline"]
        assert revue != standard
        assert set(revue) < set(standard), "revue doit être un sous-ensemble ciblé"

    def test_revue_n_execute_ni_test_ni_deploiement(self, chargeur):
        """Un workflow de relecture ne doit rien lancer ni rien déployer.

        C'est aussi ce qui le rend testable : `tester` lancerait de vraies
        suites depuis l'intérieur de la suite.
        """
        revue = chargeur.get_workflow("revue")["pipeline"]
        assert "tester" not in revue
        assert "deployment" not in revue

    def test_le_defaut_reste_standard(self, chargeur):
        """Ajouter un workflow ne doit pas changer le comportement par défaut."""
        assert chargeur.get_default_workflow() == "standard"

    def test_revue_porte_sa_propre_strategie(self, chargeur):
        """Le bloc `execution` du workflow, pas celui de la racine du fichier.

        C'est ce qui permet à deux workflows d'avoir des stratégies
        d'exécution différentes ; sans lui, `revue` hériterait des groupes de
        `standard`.
        """
        execution = chargeur.get_workflow("revue")["execution"]
        assert execution["sequential_agents"] == ["reviewer", "security"]
        assert execution["parallel_agents"] == []


class TestExecution:
    """La seconde moitié de C3 : le workflow tourne réellement."""

    def test_il_aboutit(self, execution_revue):
        """Un workflow déclaré mais qui échoue ne démontre rien."""
        assert execution_revue["status"] == "success"
        assert execution_revue["workflow_used"] == "revue"

    def test_seuls_ses_deux_agents_s_executent(self, execution_revue):
        """Le pipeline doit décider de l'exécution, pas le workflow par défaut."""
        agents = [entree["agent"] for entree in execution_revue["agent_results"]]
        assert agents == ["reviewer", "security"]

    def test_les_deux_agents_reussissent(self, execution_revue):
        """Un agent en échec passerait inaperçu dans un statut global agrégé."""
        for entree in execution_revue["agent_results"]:
            assert entree["status"] == "success", entree

    def test_le_resultat_est_reel(self, execution_revue):
        """Des fichiers doivent avoir été réellement lus, pas un résultat vide.

        C'est la garantie qui compte : un pipeline qui « réussit » sans rien
        examiner serait la fabrication que le VOLET_04 ch. 06 interdit.
        """
        par_agent = {e["agent"]: e["result"] for e in execution_revue["agent_results"]}
        assert par_agent["reviewer"]["files_reviewed"] > 0
        assert par_agent["security"]["files_scanned"] > 0

    def test_chaque_agent_rend_un_verdict(self, execution_revue):
        """Relire sans conclure ne sert à rien à l'appelant."""
        par_agent = {e["agent"]: e["result"] for e in execution_revue["agent_results"]}
        assert "approved" in par_agent["reviewer"]["verdict"]
        assert "safe" in par_agent["security"]["verdict"]

    def test_il_reste_rapide(self, execution_revue):
        """Un workflow de relecture qui prend des minutes ne sera pas utilisé.

        Le seuil est large : il attrape l'introduction d'un agent lourd, pas
        une machine lente.
        """
        assert execution_revue["execution_time_seconds"] < 30
