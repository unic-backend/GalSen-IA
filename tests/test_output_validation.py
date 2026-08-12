"""
Le contrat de sortie d'un agent (backlog P2 — VOLET 06, ch. 02, étape 6).

L'étape « valider les sorties » était déclarée par le manuel et n'existait pas.
Ces tests portent sur les trois défauts mesurés avant qu'elle existe, et sur la
propriété qui les évitait tous : **une seule règle de statut**, partagée par
l'agrégateur et le routeur.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.router.output_validation import (  # noqa: E402
    EMPTY_PIPELINE_ERROR,
    counts,
    is_valid,
    overall_status,
    validated,
    violations,
)
from src.router.result_aggregator import ResultAggregator  # noqa: E402


@pytest.fixture
def agregateur():
    """Agrégateur de résultats."""
    return ResultAggregator()


# ----------------------------------------------------------------------
# Le contrat
# ----------------------------------------------------------------------

def test_un_resultat_conforme_traverse_sans_modification():
    """Le contre-test : valider ne doit pas réécrire ce qui est correct."""
    resultat = {"agent": "coder", "status": "success", "result": "x"}

    assert validated(resultat) is resultat


@pytest.mark.parametrize("statut", ["success", "error", "skipped", "requires_approval"])
def test_les_quatre_statuts_declares_sont_acceptes(statut):
    """
    `skipped` est déclaré par `AgentResult` et traité comme terminal par
    `RetryManager` : le refuser ici recréerait la divergence qu'on corrige.
    """
    resultat = {"agent": "coder", "status": statut}
    if statut == "error":
        resultat["error"] = "boum"
    if statut == "requires_approval":
        resultat["approval_request_id"] = "appr_1"

    assert is_valid(resultat)


def test_un_statut_non_declare_est_nomme():
    """Deviner ce qu'un statut inconnu voulait dire serait fabriquer un verdict."""
    manquements = violations({"agent": "coder", "status": "done"})

    assert len(manquements) == 1
    assert "done" in manquements[0]


def test_une_erreur_sans_message_est_une_violation():
    """Une erreur sans message est une erreur que personne ne peut corriger."""
    assert violations({"agent": "coder", "status": "error"})


def test_une_approbation_sans_identifiant_est_une_violation():
    """
    Une action suspendue sans identifiant de demande ne peut plus être approuvée
    par personne : elle attendrait indéfiniment (ADR-006).
    """
    assert violations({"agent": "coder", "status": "requires_approval"})


def test_toutes_les_violations_sont_rendues_pas_seulement_la_premiere():
    """Corriger un agent une clause à la fois demanderait autant d'exécutions."""
    manquements = violations({"status": "error"})

    assert len(manquements) == 2  # agent absent, et erreur sans message


def test_un_resultat_invalide_devient_une_erreur_qui_se_nomme():
    """
    Écarter ferait disparaître un agent de la réponse ; deviner fabriquerait un
    résultat plausible. Il reste à dire ce qui ne va pas.
    """
    verifie = validated("juste du texte", agent_id="coder")

    assert verifie["agent"] == "coder"
    assert verifie["status"] == "error"
    assert "n'est pas un dictionnaire" in verifie["error"]
    # La sortie d'origine est conservée : c'est souvent la seule trace de ce que
    # l'agent a voulu dire.
    assert verifie["invalid_output"] == "juste du texte"


def test_un_objet_non_serialisable_ne_fait_pas_tomber_la_validation():
    """Le défaut à signaler est celui de l'agent, pas celui de la sérialisation."""
    class Opaque:
        pass

    verifie = validated(Opaque(), agent_id="coder")

    assert verifie["status"] == "error"
    assert isinstance(verifie["invalid_output"], str)


# ----------------------------------------------------------------------
# La règle de statut unique
# ----------------------------------------------------------------------

def test_un_agent_ecarte_ne_compte_pas_comme_une_panne():
    """
    Le défaut central. `skipped` n'entrait dans aucune des trois listes de
    l'agrégateur : l'agent **disparaissait** de la réponse et le statut restait
    `success`. Le routeur, lui, comptait ce même agent dans `failed_agents` et
    rendait `partial_success`. Une seule réponse portait les deux verdicts.
    """
    resultats = [
        {"agent": "planner", "status": "success", "result": "plan"},
        {"agent": "coder", "status": "skipped", "result": None},
    ]

    assert overall_status(resultats) == "success"
    assert counts(resultats)["skipped"] == 1
    assert counts(resultats)["error"] == 0


def test_aucun_agent_execute_n_est_pas_un_succes():
    """
    Il suffit que tous les agents soient désactivés pour que chaque requête soit
    déclarée servie sans que personne ne l'ait traitée.
    """
    assert overall_status([]) == "error"


def test_une_erreur_prime_sur_une_approbation():
    """Une requête qui a échoué quelque part n'est pas « en attente »."""
    resultats = [
        {"agent": "a", "status": "requires_approval", "approval_request_id": "appr_1"},
        {"agent": "b", "status": "error", "error": "boum"},
    ]

    assert overall_status(resultats) == "error"


def test_une_erreur_parmi_des_succes_donne_un_succes_partiel():
    """La distinction que l'opérateur lit en premier."""
    resultats = [
        {"agent": "a", "status": "success", "result": "x"},
        {"agent": "b", "status": "error", "error": "boum"},
    ]

    assert overall_status(resultats) == "partial_success"


def test_une_sortie_non_conforme_compte_comme_un_echec():
    """
    Un agent dont la sortie est illisible n'a pas réussi. Le compter ailleurs
    que dans les échecs le rendrait invisible.
    """
    resultats = [
        {"agent": "a", "status": "success", "result": "x"},
        {"agent": "b"},
    ]

    assert overall_status(resultats) == "partial_success"
    assert counts(resultats)["invalid"] == 1


# ----------------------------------------------------------------------
# L'agrégateur applique le contrat
# ----------------------------------------------------------------------

def test_aucun_agent_ne_disparait_de_la_reponse(agregateur):
    """
    La branche « tout a réussi » ne rendait que `successful_results` : un agent
    au statut non reconnu sortait de `agent_results` sans laisser de trace.
    """
    agrege = agregateur.aggregate([
        {"agent": "planner", "status": "success", "result": "plan"},
        {"agent": "coder", "status": "skipped"},
        {"agent": "tester", "status": "done"},
    ])

    assert [r["agent"] for r in agrege["agent_results"]] == ["planner", "coder", "tester"]


def test_une_sortie_qui_n_est_pas_un_dictionnaire_ne_fait_plus_tomber_la_requete(agregateur):
    """
    `r.get('status')` sur une chaîne levait une `AttributeError` au milieu de
    l'agrégation, convertie plus haut en échec de **toute** la requête : un agent
    mal écrit emportait les agents qui avaient réussi avant lui.
    """
    agrege = agregateur.aggregate([
        {"agent": "planner", "status": "success", "result": "plan"},
        "sortie mal formée",
    ])

    assert agrege["status"] == "partial_success"
    # Le travail du premier agent est conservé.
    assert agrege["aggregated_result"] == ["plan"]
    assert len(agrege["errors"]) == 1


def test_un_pipeline_vide_le_dit(agregateur):
    """Le statut et la raison, pas seulement le statut."""
    agrege = agregateur.aggregate([])

    assert agrege["status"] == "error"
    assert agrege["errors"] == [EMPTY_PIPELINE_ERROR]


def test_l_agregateur_et_la_regle_ne_peuvent_pas_diverger(agregateur):
    """
    La propriété qui compte pour la suite : l'agrégateur ne recalcule pas le
    statut, il appelle la règle. Le routeur lit ensuite le statut de
    l'agrégateur au lieu d'en déduire un second.
    """
    for resultats in (
        [],
        [{"agent": "a", "status": "success", "result": "x"}],
        [{"agent": "a", "status": "skipped"}],
        [{"agent": "a", "status": "error", "error": "boum"}],
        [{"agent": "a", "status": "requires_approval", "approval_request_id": "i"}],
        [{"agent": "a", "status": "success", "result": "x"}, {"agent": "b"}],
    ):
        assert agregateur.aggregate(resultats)["status"] == overall_status(resultats)


# ----------------------------------------------------------------------
# Le routeur et l'agrégateur, sur une vraie requête
# ----------------------------------------------------------------------

def test_le_routeur_et_l_agregateur_rendent_le_meme_statut(monkeypatch):
    """
    Le défaut se voyait sur la réponse complète : `response["status"]` venait du
    routeur, `response["aggregated_result"]["status"]` de l'agrégateur, et un
    agent `skipped` suffisait à les faire diverger — `partial_success` d'un
    côté, `success` de l'autre, dans le même dictionnaire.
    """
    from src.router.router_engine import RouterEngine

    moteur = RouterEngine()
    sorties = iter([
        {"agent": "planner", "status": "success", "result": {"plan": []}},
        {"agent": "researcher", "status": "skipped", "result": None},
    ])
    monkeypatch.setattr(
        moteur, "_dispatch_agent",
        lambda config, data, contexte=None: next(
            sorties, {"agent": "autre", "status": "skipped", "result": None}
        ),
    )

    reponse = moteur.process_request("test", workflow_id="standard")

    assert reponse["status"] == reponse["aggregated_result"]["status"] == "success"
    # L'agent écarté est compté comme tel, non comme une panne.
    assert reponse["metadata"]["skipped_agents"] == 1
    assert reponse["metadata"]["failed_agents"] == 0
    assert [r["agent"] for r in reponse["agent_results"]] == ["planner", "researcher"]


def test_le_dispatcher_refuse_la_sortie_d_un_module_ancien(tmp_path, monkeypatch):
    """
    La convention historique — un module exposant `execute(input_data)` — rend
    ce que son auteur a écrit. C'est elle qui rend la validation nécessaire
    plutôt que défensive : le contrôle est fait une fois, à la frontière.
    """
    import sys
    import types

    from src.router.agent_dispatcher import AgentDispatcher

    module = types.ModuleType("agent_ancien_pour_test")
    module.execute = lambda entree: "une chaîne, pas un résultat"
    monkeypatch.setitem(sys.modules, "agent_ancien_pour_test", module)

    resultat = AgentDispatcher().dispatch(
        {"id": "ancien", "module": "agent_ancien_pour_test"}, "demande",
    )

    assert resultat["status"] == "error"
    assert resultat["agent"] == "ancien"
    assert "n'est pas un dictionnaire" in resultat["error"]
