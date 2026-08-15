"""
La boucle d'ingénierie atteint les greffons (phases 62.1 et 62.2).

La plateforme sait déjà lire un dépôt et l'éditer sous approbation
(`src/agent/guarded_editor.py`). Pointer cette boucle sur un greffon pose une
question qu'elle n'avait jamais eu à trancher, parce que jusqu'ici **tout** ce
qu'elle touchait avait été écrit ici.

**62.1 — modifier un greffon le désactive.** L'autorisation portait sur ce que
son auteur avait écrit. Une fois que quelqu'un d'autre l'a modifié, ce qui
tourne n'est plus ce qui a été approuvé — et le laisser activé transférerait
silencieusement cette approbation à du code que l'auteur n'a jamais vu.

**62.2 — une relecture statique trouve des contradictions, jamais des
intentions.** Un manifeste qui dit « pas de réseau » à côté d'un fichier qui
importe `urllib` est un **écart** : un fait sur deux documents, pas un jugement
sur leur auteur. Et surtout : « aucun écart » ne veut **pas** dire « sûr ».

Ce que ces tests gardent :

1. Une modification désactive, et le dire fait partie du résultat.
2. Un écart cite le fait qui l'atteste, et ne conclut pas sur l'intention.
3. Un fichier illisible n'est pas un fichier sans import.
4. Le rapport refuse d'être lu comme une preuve d'innocuité.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.plugins import PluginRegistry  # noqa: E402
from src.plugins.review import (  # noqa: E402
    MODULES_RESEAU,
    ReviewRefused,
    discrepancies,
    edited_plugin_must_be_reenabled,
    review_plugin,
    review_report,
)

DECLARE = {
    "plugin_id": "meteo-sn",
    "version": "1.0.0",
    "author": "Awa Diop",
    "description": "Prévisions locales.",
    "entry_point": "main.py",
    "effects": ["read"],
    "scopes": ["public"],
}


@pytest.fixture
def registre():
    """Un registre portant un greffon installé et activé."""
    registre = PluginRegistry()
    registre.install(dict(DECLARE))
    registre.enable("meteo-sn", "awa", "pilote agricole")
    return registre


# ----------------------------------------------------------------------
# 1. Modifier un greffon le désactive (62.1)
# ----------------------------------------------------------------------

def test_modifier_un_greffon_le_desactive(registre):
    """
    **La règle du VOLET.** Le laisser activé transférerait l'approbation de
    l'auteur à du code qu'il n'a jamais vu.
    """
    resultat = edited_plugin_must_be_reenabled("meteo-sn", registre, "claude")

    assert resultat["was_enabled"] is True
    assert resultat["enabled"] is False
    assert registre.get("meteo-sn").enabled is False


def test_la_desactivation_dit_pourquoi_et_qui_a_modifie(registre):
    """La trace de l'activation a disparu ; celle de la modification reste."""
    resultat = edited_plugin_must_be_reenabled("meteo-sn", registre, "claude")

    assert resultat["edited_by"] == "claude"
    assert "n'est plus ce qui a été approuvé" in resultat["reason"]
    assert registre.activation_of("meteo-sn") is None


def test_modifier_un_greffon_deja_inactif_ne_ment_pas(registre):
    """`was_enabled: false` distingue « je l'ai arrêté » de « il l'était déjà »."""
    registre.disable("meteo-sn")

    resultat = edited_plugin_must_be_reenabled("meteo-sn", registre, "claude")

    assert resultat["was_enabled"] is False
    assert resultat["enabled"] is False


def test_un_modificateur_anonyme_est_rendu_comme_inconnu(registre):
    """Mieux vaut `UNKNOWN` écrit qu'une chaîne vide qui se lit comme un nom."""
    resultat = edited_plugin_must_be_reenabled("meteo-sn", registre, "   ")

    assert resultat["edited_by"] == "UNKNOWN"


def test_modifier_un_greffon_inconnu_est_refuse(registre):
    """Ni désactivation fantôme, ni erreur obscure."""
    with pytest.raises(ReviewRefused, match="inconnu"):
        edited_plugin_must_be_reenabled("fantome", registre, "claude")


# ----------------------------------------------------------------------
# 2. Les écarts (62.2)
# ----------------------------------------------------------------------

def test_un_import_reseau_sans_effet_declare_est_un_ecart(registre):
    """Deux documents se contredisent — c'est un fait, pas un jugement."""
    ecarts = discrepancies(
        registre.get("meteo-sn"), "import urllib.request\nprint(1)\n",
    )

    assert ecarts[0]["kind"] == "network_without_external"
    assert "urllib" in ecarts[0]["evidence"]
    assert "ne sait pas lequel" in ecarts[0]["note"]


def test_le_meme_import_avec_l_effet_declare_n_est_pas_un_ecart():
    """La contre-épreuve : sans elle, la règle refuserait tout accès réseau."""
    from src.plugins import read_manifest

    manifeste = read_manifest({**DECLARE, "effects": ["read", "external"]})

    assert discrepancies(manifeste, "import urllib.request\n") == []


def test_un_import_systeme_est_signale(registre):
    """La portée `system` est refusée à la déclaration ; l'atteindre par le
    code atteint ce qu'aucun manifeste ne peut accorder."""
    ecarts = discrepancies(registre.get("meteo-sn"), "import subprocess\n")

    assert ecarts[0]["kind"] == "system_reach_without_scope"
    assert "aucun manifeste" in ecarts[0]["note"]


def test_un_code_sans_import_suspect_ne_produit_aucun_ecart(registre):
    """Un écart doit vouloir dire quelque chose."""
    assert discrepancies(registre.get("meteo-sn"), "import json\nprint(1)\n") == []


def test_un_fichier_illisible_est_refuse_pas_declare_vide(registre):
    """Un fichier qu'on ne peut pas analyser n'est pas un fichier sans import."""
    with pytest.raises(ReviewRefused, match="illisible"):
        discrepancies(registre.get("meteo-sn"), "def x(:\n")


def test_la_relecture_rend_la_methode_avec_le_resultat(registre):
    """`ast` lit des noms ; elle ne comprend rien, et le dit."""
    resultat = review_plugin("meteo-sn", registre, source="import json\n")

    assert resultat["method"] == "ast"
    assert resultat["imports"] == ["json"]


def test_la_relecture_refuse_d_etre_lue_comme_une_preuve(registre):
    """
    **Le point le plus important de la phase.** Lire « aucun écart » comme
    « sans danger » serait la chose la plus nuisible que ce module puisse
    provoquer.
    """
    resultat = review_plugin("meteo-sn", registre, source="print(1)\n")

    assert resultat["discrepancies"] == []
    assert "ne veut pas dire « sûr »" in resultat["proves_nothing"]


def test_la_liste_des_modules_reseau_est_declaree_incomplete():
    """Une liste présentée comme exhaustive serait une promesse intenable."""
    rapport = review_report()

    assert "urllib" in rapport["known_network_modules"]
    assert set(rapport["known_network_modules"]) == set(MODULES_RESEAU)
    assert any("incomplète" in ligne for ligne in rapport["does_not"])


def test_le_rapport_dit_qu_il_ne_modifie_rien():
    """L'écriture reste au `GuardedEditor`, sous approbation."""
    ne_fait_pas = " ".join(review_report()["does_not"])

    assert "l'écriture reste au `GuardedEditor`" in ne_fait_pas.replace("L'é", "l'é")


def test_relire_un_greffon_sans_code_est_refuse(registre):
    """Il a été déclaré, pas installé depuis un répertoire : il n'y a rien à lire."""
    with pytest.raises(ReviewRefused, match="rien à relire"):
        review_plugin("meteo-sn", registre)


# ----------------------------------------------------------------------
# 3. La route
# ----------------------------------------------------------------------

def test_la_route_relit_le_greffon_d_exemple(monkeypatch):
    """Sur le greffon réel du dépôt, installé depuis son répertoire."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    monkeypatch.setattr(server_module, "plugin_registry", PluginRegistry())

    with TestClient(server_module.app) as client:
        cle = {"X-API-Key": "cle-awa"}
        client.post("/plugins/discover", headers=cle)
        relecture = client.get("/plugins/exemple-meteo/review", headers=cle).json()
        inconnu = client.get("/plugins/fantome/review", headers=cle)

    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())

    assert relecture["discrepancies"] == []
    assert relecture["imports"] == ["json"]
    assert "sûr" in relecture["proves_nothing"]
    assert inconnu.status_code == 404
