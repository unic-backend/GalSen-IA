"""
L'exposition des capacités d'outils : par `ToolEngine`, puis par l'API.

Phase 38.1 a écrit ce que chaque outil touche. Sans cette phase, la réponse
restait dans un fichier YAML que trois chantiers auraient dû relire chacun de
leur côté — c'est ainsi qu'on obtient trois vérités divergentes.

Ce que ces tests gardent :

1. **La capacité voyage avec l'outil.** Apprendre qu'un outil existe, c'est
   apprendre ce qu'il touche, dans la même réponse.
2. **Un outil inconnu n'est pas un 404.** La réponse utile est « je ne sais
   pas, donc non », pas « il n'y a rien à savoir ».
3. **Un registre incohérent empêche le moteur d'exister**, au lieu de le
   laisser exécuter sans savoir.
4. **Consulter une capacité n'exécute aucun outil.**
"""

import os
import sys

import pytest
import yaml
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.tool.capabilities import CapabilityError, DataScope, Effect  # noqa: E402
from src.tool.tool_engine import ToolEngine  # noqa: E402

REGISTRE_REEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "tools.yaml"
)


@pytest.fixture
def moteur():
    """Le moteur d'outils construit sur le registre réel du dépôt."""
    return ToolEngine(REGISTRE_REEL)


@pytest.fixture
def cles(monkeypatch):
    """Clés admin et lecture seule, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin,cle-lecture:readonly")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield {"admin": "cle-admin", "readonly": "cle-lecture"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def moteur_branche(moteur, monkeypatch):
    """Branche un vrai moteur d'outils sur le module serveur, le temps du test."""
    monkeypatch.setattr(server_module, "tool_engine", moteur)
    return moteur


@pytest.fixture
def client():
    """Client HTTP sur l'application réelle."""
    with TestClient(app) as essai:
        yield essai


# ----------------------------------------------------------------------
# 1. Le moteur
# ----------------------------------------------------------------------

def test_la_capacite_voyage_avec_l_information_d_outil(moteur):
    """Un appelant qui apprend qu'un outil existe apprend ce qu'il touche."""
    info = moteur.get_tool_info("email")

    assert info["capability"]["data_scope"] == "user_private"
    assert info["capability"]["requires_approval"] is True
    assert "external" in info["capability"]["effects"]


def test_tous_les_outils_listes_portent_leur_capacite(moteur):
    """Aucune entrée sans capacité : l'oubli serait invisible autrement."""
    manquants = [
        outil["id"] for outil in moteur.list_tools() if "capability" not in outil
    ]

    assert manquants == []
    assert len(moteur.list_tools()) == 24


def test_le_moteur_repond_aux_trois_questions_des_couches_suivantes(moteur):
    """Permissions, connecteurs, routines : les trois lisent d'ici."""
    assert moteur.may_run_unattended("email")[0] is False
    assert moteur.may_reach("email", DataScope.USER_PRIVATE)[0] is True
    assert "email" in moteur.list_tools_by_effect(Effect.EXTERNAL)
    assert "email" not in moteur.list_unattended_tools()


def test_un_outil_inconnu_recoit_un_refus_motive_pas_une_exception(moteur):
    """Demander pour un outil absent est une question valide."""
    autorise, raison = moteur.may_run_unattended("outil_qui_n_existe_pas")

    assert autorise is False
    assert "non déclarée" in raison
    assert moteur.get_tool_capability("outil_qui_n_existe_pas").declared is False


def test_un_registre_incoherent_empeche_le_moteur_d_exister(tmp_path):
    """
    Mieux vaut un moteur d'outils absent — `/tool/execute` répond 503 — qu'un
    moteur qui exécute sans savoir ce que ses outils touchent.
    """
    chemin = tmp_path / "tools.yaml"
    chemin.write_text(yaml.safe_dump({"version": "1.0", "tools": [{
        "id": "contradictoire",
        "module": "tools.metrics.tool",
        "class": "MetricsTool",
        "capability": {
            "effects": ["read"], "data_scope": "public",
            "requires_approval": True, "unattended": True,
        },
    }]}, allow_unicode=True), encoding="utf-8")

    with pytest.raises(CapabilityError, match="incompatibles"):
        ToolEngine(str(chemin))


def test_consulter_une_capacite_n_execute_aucun_outil(moteur):
    """Demander si un outil est dangereux ne doit pas revenir à le lancer."""
    avant = set(sys.modules)

    moteur.get_capability_report()
    moteur.may_run_unattended("terminal")
    moteur.list_tools()

    nouveaux = {m for m in set(sys.modules) - avant if m.startswith("src.tools.")}
    assert nouveaux == set(), f"Modules d'outils chargés : {nouveaux}"


# ----------------------------------------------------------------------
# 2. L'API
# ----------------------------------------------------------------------

def test_le_rapport_publie_sa_propre_couverture(client, cles, moteur_branche):
    """Un outil oublié apparaîtrait dans `undeclared`, pas dans le silence."""
    reponse = client.get(
        "/tools/capabilities", headers={"X-API-Key": cles["admin"]}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["tools"] == 24
    assert corps["undeclared"] == []
    assert corps["coverage"] == 1.0
    assert "email" in corps["by_scope"]["user_private"]


def test_la_capacite_d_un_outil_est_consultable(client, cles, moteur_branche):
    """La route que le moteur de routines interrogera avant de planifier."""
    reponse = client.get(
        "/tools/email/capability", headers={"X-API-Key": cles["admin"]}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["declared"] is True
    assert corps["known_to_registry"] is True
    assert corps["may_run_unattended"] is False
    assert "ne revient pas" in corps["reason"]


def test_un_outil_inconnu_repond_deux_cents_avec_un_refus(client, cles, moteur_branche):
    """
    Un 404 dirait « il n'y a rien à savoir ». La réponse utile est
    « je ne sais pas, donc non ».
    """
    reponse = client.get(
        "/tools/jamais_vu/capability", headers={"X-API-Key": cles["admin"]}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["declared"] is False
    assert corps["known_to_registry"] is False
    assert corps["may_run_unattended"] is False
    assert corps["unattended_reason"].strip() != ""


def test_les_routes_de_capacite_exigent_une_cle(client, moteur_branche):
    """La liste des outils privilégiés n'est pas une donnée publique."""
    for route in ("/tools/capabilities", "/tools/email/capability"):
        assert client.get(route).status_code in (401, 403), route


def test_sans_moteur_d_outils_les_routes_disent_cinq_cent_trois(
    client, cles, monkeypatch
):
    """Un moteur absent se signale ; il ne rend pas un rapport vide."""
    monkeypatch.setattr(server_module, "tool_engine", None)

    reponse = client.get(
        "/tools/capabilities", headers={"X-API-Key": cles["admin"]}
    )

    assert reponse.status_code == 503


# ----------------------------------------------------------------------
# 3. L'autorisation par acteur (phase 39.1)
# ----------------------------------------------------------------------

def test_l_appelant_voit_les_trois_verdicts(client, cles, moteur_branche):
    """Afficher seulement `allowed` cacherait ce qu'il a le droit de demander."""
    reponse = client.get(
        "/tools/authorization", headers={"X-API-Key": cles["admin"]}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["role"] == "admin"
    assert "user_private" in corps["ceiling"]["scopes"]
    assert "terminal" in corps["tools"]["requires_approval"]
    assert "metrics" in corps["tools"]["allowed"]


def test_le_verdict_par_outil_porte_sa_raison(client, cles, moteur_branche):
    """Un « non » sans cause est indébogable pour qui le reçoit."""
    reponse = client.get(
        "/tools/terminal/authorization", headers={"X-API-Key": cles["admin"]}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["decision"] == "requires_approval"
    assert corps["reason"].strip() != ""


def test_le_role_evalue_vient_de_la_cle_pas_du_corps(client, cles, moteur_branche):
    """Un appelant ne choisit pas le rôle sous lequel il est évalué."""
    reponse = client.get(
        "/tools/authorization",
        headers={"X-API-Key": cles["admin"]},
        params={"role": "readonly"},
    )

    assert reponse.json()["role"] == "admin"


def test_la_matrice_est_reservee_a_l_administration(client, cles, moteur_branche):
    """La carte complète des privilèges n'est pas une donnée d'exploitation."""
    assert client.get(
        "/tools/authorization/matrix", headers={"X-API-Key": cles["admin"]}
    ).status_code == 200
    assert client.get(
        "/tools/authorization/matrix", headers={"X-API-Key": cles["readonly"]}
    ).status_code == 403


# ----------------------------------------------------------------------
# 4. L'application du plafond à l'exécution (phase 39.2)
# ----------------------------------------------------------------------

@pytest.fixture
def cles_quatre_roles(monkeypatch):
    """Une clé par rôle, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv(
        "GALSEN_API_KEYS",
        "k-admin:admin:awa,k-operator:operator:moussa,"
        "k-user:user:fatou,k-readonly:readonly:scrutin",
    )
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield {
        "admin": "k-admin", "operator": "k-operator",
        "user": "k-user", "readonly": "k-readonly",
    }
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def _executer(client, cle, tool_id, entree="exists", config=None):
    """Appelle `/tool/execute` avec la clé donnée."""
    return client.post(
        "/tool/execute",
        json={"tool_id": tool_id, "input": entree, "config": config or {}},
        headers={"X-API-Key": cle},
    )


def test_un_utilisateur_n_atteint_plus_l_etat_de_la_plateforme(
    client, cles_quatre_roles, moteur_branche
):
    """
    Le défaut corrigé par le VOLET 39 : `tool:execute` ouvrait `filesystem`
    à tout le monde. Le rôle `user` la détient toujours, et se voit refuser.
    """
    reponse = _executer(
        client, cles_quatre_roles["user"], "filesystem", config={"path": "README.md"}
    )

    assert reponse.status_code == 403
    detail = reponse.json()["detail"]
    assert detail["decision"] == "refused"
    assert "system" in detail["reason"]


def test_un_administrateur_atteint_le_meme_outil(
    client, cles_quatre_roles, moteur_branche
):
    """La symétrie : le refus vient du plafond, pas d'une panne."""
    reponse = _executer(
        client, cles_quatre_roles["admin"], "filesystem", config={"path": "README.md"}
    )

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["output"] is True


def test_personne_ne_saute_une_approbation_par_l_api(
    client, cles_quatre_roles, moteur_branche
):
    """
    Le test le plus important de la phase : l'administration elle-même est
    arrêtée devant `terminal`. Une approbation qualifie l'acte, pas l'acteur.
    """
    reponse = _executer(client, cles_quatre_roles["admin"], "terminal", entree=["echo"])

    assert reponse.status_code == 403
    assert reponse.json()["detail"]["decision"] == "requires_approval"


def test_le_refus_distingue_jamais_de_il_faut_un_humain(
    client, cles_quatre_roles, moteur_branche
):
    """
    Les deux sont des 403, et ce ne sont pas les mêmes : l'un se lève en
    ouvrant une demande d'approbation, l'autre jamais.
    """
    jamais = _executer(client, cles_quatre_roles["operator"], "email")
    humain = _executer(client, cles_quatre_roles["admin"], "gui")

    assert jamais.json()["detail"]["decision"] == "refused"
    assert humain.json()["detail"]["decision"] == "requires_approval"


def test_un_outil_inconnu_est_refuse_avant_toute_execution(
    client, cles_quatre_roles, moteur_branche
):
    """Un outil que nul n'a décrit ne s'exécute pour personne."""
    reponse = _executer(client, cles_quatre_roles["admin"], "outil_fantome")

    assert reponse.status_code == 403
    assert reponse.json()["detail"]["decision"] == "refused"


def test_le_verdict_annonce_par_la_lecture_est_celui_qui_est_applique(
    client, cles_quatre_roles, moteur_branche
):
    """
    Une politique consultable qui diffère de la politique appliquée est pire
    qu'aucune politique. Les deux routes sont confrontées, outil par outil.
    """
    cle = cles_quatre_roles["user"]
    annonce = client.get(
        "/tools/authorization", headers={"X-API-Key": cle}
    ).json()["tools"]

    for tool_id in annonce["refused"] + annonce["requires_approval"]:
        assert _executer(client, cle, tool_id).status_code == 403, tool_id
