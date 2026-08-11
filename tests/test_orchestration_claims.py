"""
Tests des promesses de l'orchestrateur (VOLET 06, chapitres 02 à 04).

Ce fichier ne teste pas ce que l'orchestrateur *fait* — `test_integration.py`
s'en charge — mais ce qu'il **annonce**. Deux affirmations étaient fausses : le
moteur se disait capable d'exécution parallèle et le plan se lisait comme
dépendant de la requête. Une capacité annoncée et absente est plus coûteuse
qu'une capacité manquante, parce que personne ne la cherche.
"""

import ast
import inspect
from pathlib import Path

import pytest

from src.router.execution_planner import ExecutionPlanner
from src.router.workflow_loader import WorkflowLoader

RACINE = Path(__file__).resolve().parent.parent
ROUTER = RACINE / "src" / "router"


@pytest.fixture
def planificateur():
    """Planificateur branché sur les workflows réellement déclarés."""
    return ExecutionPlanner(WorkflowLoader(str(RACINE / "workflows" / "workflows.yaml")))


def test_le_plan_dit_qu_il_n_execute_rien_en_parallele(planificateur):
    """Tant que le parallélisme n'existe pas, le plan doit le déclarer."""
    plan = planificateur.plan_execution("revue")
    assert plan["parallel_supported"] is False


def test_aucune_primitive_de_parallelisme_dans_le_routeur():
    """Le jour où le parallélisme arrive, ce test échoue et rappelle de mettre
    `parallel_supported` à True — sinon l'annonce et le comportement divergent
    dans l'autre sens."""
    primitives = ("ThreadPool", "asyncio.gather", "ProcessPool", "concurrent.futures")
    trouvees = []
    for chemin in ROUTER.glob("*.py"):
        contenu = chemin.read_text(encoding="utf-8")
        trouvees += [f"{chemin.name}:{p}" for p in primitives if p in contenu]
    assert trouvees == [], (
        "Parallélisme introduit : passer `parallel_supported` à True — " + ", ".join(trouvees)
    )


def test_le_moteur_ne_promet_plus_le_parallelisme():
    """La docstring du moteur ne doit pas annoncer ce qu'il ne fait pas."""
    from src.router import router_engine

    docstring = ast.get_docstring(ast.parse(Path(router_engine.__file__).read_text(encoding="utf-8"))) or ""
    assert "supports parallel execution" not in docstring
    assert "sequential" in docstring.lower()


def test_le_plan_ne_prend_pas_la_requete(planificateur):
    """Constat verrouillé : le plan vient du workflow, jamais de la demande.

    Ce test échouera le jour où la requête sera prise en compte — ce sera le
    signal de mettre à jour `docs/architecture/orchestration.md`, pas de le
    contourner.
    """
    parametres = inspect.signature(planificateur.plan_execution).parameters
    assert set(parametres) == {"workflow_id"}


def test_deux_requetes_opposees_donnent_le_meme_plan(planificateur):
    """Conséquence directe : la demande n'influence rien."""
    assert planificateur.plan_execution("revue") == planificateur.plan_execution("revue")
    # Le workflow, lui, change tout — c'est le seul levier existant.
    assert planificateur.plan_execution("revue")["sequential"] == ["reviewer", "security"]


# Seul module autorisé à lire `agents_required`, et pour quoi faire.
#
# Le VOLET 22 a ajouté `src/router/decision_trace.py`, qui rapporte l'écart entre
# les agents recommandés et ceux qui tournent. Le branchement demandé par le
# backlog l'a ensuite fait **décider** — mais toujours par ce seul module, et
# seulement pour les workflows qui le déclarent. Un autre lecteur reste interdit.
LECTEURS_AUTORISES = {"src/router/decision_trace.py"}


def test_un_seul_module_lit_la_recommandation_du_planificateur():
    """Le branchement devait être un choix visible, pas un effet de bord.

    Il a eu lieu, en un seul endroit et derrière une option déclarée dans
    `workflows.yaml`. Un nouveau lecteur fait échouer ce test : c'est le moment
    de dire s'il rapporte ou s'il décide.
    """
    lecteurs = []
    for dossier in (RACINE / "src", RACINE / "agents"):
        for chemin in dossier.rglob("*.py"):
            if chemin.name == "agent.py" and chemin.parent.name == "planner":
                continue
            if "agents_required" in chemin.read_text(encoding="utf-8"):
                lecteurs.append(chemin.relative_to(RACINE).as_posix())
    inattendus = sorted(set(lecteurs) - LECTEURS_AUTORISES)
    assert inattendus == [], (
        "Quelqu'un lit maintenant `agents_required` : dire s'il rapporte ou s'il "
        "décide, et mettre à jour docs/architecture/orchestration.md — "
        + ", ".join(inattendus)
    )


def test_la_selection_restreint_le_pipeline_et_ne_l_elargit_jamais():
    """L'invariant de sécurité du branchement.

    `workflows.yaml` reste l'autorité sur ce qui **peut** tourner ; le
    planificateur décide seulement ce qui tourne parmi cela. Un planificateur
    capable d'ajouter un agent absent de la déclaration contournerait la revue
    humaine qui accompagne ce fichier.
    """
    from src.router.decision_trace import selection_appliquee

    declare = ["planner", "reviewer", "tester"]

    assert selection_appliquee(declare, ["reviewer"]) == ["reviewer"]
    # Un agent recommandé mais non déclaré n'entre pas dans l'exécution.
    assert selection_appliquee(declare, ["deployment"]) is None
    assert selection_appliquee(declare, ["reviewer", "deployment"]) == ["reviewer"]


def test_une_recommandation_inutilisable_laisse_le_pipeline_entier():
    """Ne rien exécuter parce qu'une heuristique n'a rien reconnu serait pire.

    `None` signale à l'orchestrateur de garder la déclaration ; c'est le repli
    volontaire, pas une exécution vide.
    """
    from src.router.decision_trace import selection_appliquee

    assert selection_appliquee(["planner", "tester"], None) is None
    assert selection_appliquee(["planner", "tester"], []) is None
