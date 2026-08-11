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
# Le VOLET 22 a ajouté `src/router/decision_trace.py`, qui **rapporte** l'écart
# entre les agents recommandés et ceux qui tournent, sans rien changer à
# l'exécution. C'est l'exception voulue par ce garde-fou : un branchement doit
# être un choix visible, et celui-ci l'est — la trace dit elle-même
# `applied: false`.
LECTEURS_AUTORISES = {"src/router/decision_trace.py"}


def test_les_intentions_detectees_ne_pilotent_toujours_pas_l_execution():
    """`agents_required` est calculé par le planner et ne route rien.

    Verrouillé pour que le branchement, quand il aura lieu, soit un choix visible
    et non un effet de bord. Un nouveau lecteur fait échouer ce test : c'est le
    moment de dire s'il rapporte ou s'il décide.
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


def test_la_trace_de_decision_ne_change_pas_l_execution():
    """Le pendant comportemental du test précédent.

    Lire la recommandation sans la suivre est acceptable ; la suivre en silence
    ne l'est pas. La trace le déclare, et ce test le vérifie.
    """
    from src.router.decision_trace import decision_trace

    trace = decision_trace(
        [{"agent": "planner", "status": "success",
          "result": {"agents_required": ["monitor"]}}],
        ["planner", "coder", "tester"],
    )

    assert trace["applied"] is False
    assert trace["executed_agents"] == ["planner", "coder", "tester"]
