"""
Ce qui arrive réellement aux agents (phases 63.1 et 63.2).

Cinq vagues ont ajouté des outils, de la connaissance, des greffons, des
routines, des couches. Chacune a été testée là où elle a été écrite. Rien de
tout cela ne répond à la question pour laquelle cette vague existe : **un agent
peut-il s'en servir ?**

Le mode de panne est précis et silencieux. Une capacité arrive dans `src/`,
reçoit une route, reçoit des tests, et n'apparaît jamais dans `AgentContext` :
elle marche alors pour tout le monde **sauf** pour les agents dont la plateforme
est faite. Personne ne s'en aperçoit, parce que rien n'échoue — les agents
continuent simplement de faire ce qu'ils faisaient avant.

**63.1** referme le cas mesuré : la connaissance mondiale de la vague IV
n'était atteignable que par HTTP.

**63.2** mesure l'écart au lieu de le supposer, et nomme ce qui est
**volontairement** hors de portée — une capacité manquante et une capacité
écartée se ressemblent, et seule la seconde est une décision.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.capabilities_reach import (  # noqa: E402
    CAPACITES,
    HORS_DE_PORTEE,
    agent_reach,
)
from src.agent.context import AgentContext  # noqa: E402
from src.integration.engine_registry import EngineRegistry  # noqa: E402


def _contexte():
    """Un contexte d'agent, sans moteur branché."""
    return AgentContext(request="une question", agent_id="researcher",
                        registry=EngineRegistry())


# ----------------------------------------------------------------------
# 1. La connaissance mondiale arrive aux agents (63.1)
# ----------------------------------------------------------------------

def test_un_agent_atteint_la_connaissance_mondiale():
    """
    La capacité existait depuis la vague IV et **ne leur arrivait pas** : elle
    n'était joignable que par HTTP.
    """
    reponse = _contexte().ask_knowledge("Quelle est la monnaie du Sénégal ?")

    assert reponse["status"] in ("FOUND", "UNKNOWN")
    assert reponse["answered_by"] in ("senegal", "world", "none")
    assert reponse["layers"] == ["senegal", "world"]


def test_l_agent_sait_quelle_couche_a_repondu():
    """
    Le routage est celui du VOLET 57, pas un second : sans `answered_by`, un
    désaccord entre couches serait invisible pour l'agent aussi.
    """
    reponse = _contexte().ask_knowledge("Quelle est la capitale de la France ?")

    assert reponse["layers"] == ["world"]
    assert "reason" in reponse


def test_un_sujet_national_ne_quitte_pas_son_pays_pour_un_agent_non_plus():
    """La règle ne s'assouplit pas parce que l'appelant est un agent."""
    reponse = _contexte().ask_knowledge(
        "Quel est le droit du travail ?", scope="country:fr",
    )

    assert reponse["layers"] == []
    assert reponse["answered_by"] == "none"


def test_une_portee_mal_ecrite_revient_a_l_agent_sans_faire_tomber_son_tour():
    """Une erreur d'appel n'est pas une panne de moteur."""
    reponse = _contexte().ask_knowledge("x", scope="pays:xx")

    assert reponse["status"] == "UNKNOWN"
    assert reponse["answered_by"] == "none"
    assert "reason" in reponse


# ----------------------------------------------------------------------
# 2. L'écart est mesuré, pas supposé (63.2)
# ----------------------------------------------------------------------

def test_toutes_les_capacites_declarees_arrivent_aux_agents():
    """
    **Le test de la vague.** Une capacité qui n'arrive pas aux agents marche
    pour tout le monde sauf pour eux, et rien n'échoue.
    """
    rapport = agent_reach()

    assert rapport["missing"] == []
    assert rapport["reached"] == len(CAPACITES)


def test_chaque_capacite_declare_la_methode_qui_l_atteint():
    """Sans le nom de la méthode, le rapport ne serait pas vérifiable."""
    for nom, declaration in CAPACITES.items():
        assert declaration["method"], nom
        assert declaration["what"].strip(), nom


def test_ce_qui_est_volontairement_hors_de_portee_est_nomme():
    """
    Une capacité manquante et une capacité écartée se ressemblent ; seule la
    seconde est une décision.
    """
    rapport = agent_reach()

    assert set(rapport["out_of_reach_by_design"]) == set(HORS_DE_PORTEE)
    assert "décision humaine" in rapport["out_of_reach_by_design"]["plugins"]
    assert "sans témoin" in rapport["out_of_reach_by_design"]["routines"]


def test_une_capacite_absente_du_contexte_est_signalee():
    """Le rapport doit savoir échouer, sinon il ne prouve rien."""

    class _ContexteAmpute:
        """Un contexte auquel il manque tout."""

    rapport = agent_reach(_ContexteAmpute)

    assert set(rapport["missing"]) == set(CAPACITES)
    assert rapport["reached"] == 0


def test_le_rapport_refuse_d_etre_lu_comme_une_preuve_de_fonctionnement():
    """« Atteint » veut dire « la méthode existe », pas « elle marche »."""
    rapport = agent_reach()

    ne_fait_pas = " ".join(rapport["does_not"])
    assert rapport["method"] == "attribute_lookup"
    assert "serait la mauvaise leçon" in ne_fait_pas


def test_la_liste_est_ecrite_a_la_main_et_le_dit():
    """
    Dérivée du code, elle dirait seulement que le code est cohérent avec
    lui-même.
    """
    regles = " ".join(agent_reach()["rules"])

    assert "écrite à la main" in regles
    assert "cohérent avec lui-même" in regles


def test_le_rapport_parle_meme_quand_rien_ne_manque():
    """Un contrôle qui ne s'exprime qu'en cas d'échec n'apprend rien."""
    rapport = agent_reach()

    assert rapport["capabilities"], "Le rapport doit lister les capacités atteintes"
    assert any("même quand rien ne manque" in ligne for ligne in rapport["rules"])


# ----------------------------------------------------------------------
# 3. La route
# ----------------------------------------------------------------------

def test_la_route_publie_ce_qui_arrive_aux_agents(monkeypatch):
    """Un opérateur doit pouvoir le lire sans ouvrir le code."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())

    with TestClient(server_module.app) as client:
        rapport = client.get(
            "/agents/reach", headers={"X-API-Key": "cle-awa"},
        ).json()

    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())

    assert rapport["missing"] == []
    assert "world_knowledge" in {c["capability"] for c in rapport["capabilities"]}
