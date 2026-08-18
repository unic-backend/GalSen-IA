"""
Le Sénégal comme spécialisation, pas comme moteur parallèle (phases 57.1, 57.2).

À la fin de la vague IV, ce dépôt porte deux corps de connaissance qui peuvent
tous deux être interrogés sur le Sénégal, et qui ne sont pas de même nature : la
**référence mondiale** (249 pays, une fiche chacun — de la largeur) et la
**couche sénégalaise** (14 régions, 45 départements, fragments avec provenance,
corpus wolof — de la profondeur, pour un pays).

Deux moteurs capables de répondre à la même question ne sont pas une
fonctionnalité. C'est le défaut que ce routage existe pour empêcher — non parce
que l'un se tromperait, mais parce que **personne ne saurait lequel a répondu**,
et le jour où ils divergeraient, le désaccord serait invisible.

Ce que ces tests gardent :

1. **Un sujet national ne quitte pas son pays.** Pour le droit, la référence
   mondiale n'est pas un repli : elle est hors sujet, et répondrait à côté d'une
   façon qui se lit parfaitement.
2. **Là où les deux peuvent répondre, la profondeur passe d'abord.**
3. **La réponse dit quelle couche a parlé.** Un routeur dont la décision ne se
   lit pas est un routeur que personne ne peut déboguer.
4. **Aucune couche n'est un sous-ensemble de l'autre** — sinon la garder serait
   une implémentation parallèle, ce que la directive interdit.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.routing import (  # noqa: E402
    AUCUNE,
    COUCHE_MONDE,
    COUCHE_SENEGAL,
    PAYS_SPECIALISE,
    ask,
    layer_comparison,
    route,
    routing_report,
)


def _senegal(reponse="Le département de Podor.", **extra):
    """Une couche sénégalaise qui répond ce qu'on lui dit."""
    return lambda question: {"answer": reponse, "grounding": "grounded", **extra}


def _monde(statut="FOUND"):
    """Une référence mondiale qui répond ce qu'on lui dit."""
    return lambda question: {"status": statut, "country": {"iso3": "SEN"}}


# ----------------------------------------------------------------------
# 1. Un sujet national ne quitte pas son pays (57.1)
# ----------------------------------------------------------------------

def test_le_droit_senegalais_ne_va_jamais_a_la_reference_mondiale():
    """
    Une source mondiale répondrait à côté d'une façon qui se lit parfaitement :
    c'est le pire genre d'erreur.
    """
    decision = route("Quelle est la loi foncière à Dakar ?")

    assert decision["subject"] == "law"
    assert decision["layers"] == [COUCHE_SENEGAL]
    assert "hors sujet" in decision["reason"]


def test_le_droit_d_un_pays_sans_couche_nationale_n_interroge_personne():
    """
    Ce dépôt n'a de profondeur que pour un pays. Faute de couche nationale, la
    bonne réponse est « personne », pas « la référence mondiale ».
    """
    decision = route("Quel est le droit du travail ?", scope="country:fr")

    assert decision["layers"] == []
    assert "aucune source mondiale ne porte le droit d'un pays" in decision["reason"]


def test_les_trois_sujets_nationaux_suivent_la_meme_regle():
    """Droit, administration, langues : la règle ne connaît pas d'exception."""
    for sujet in ("law", "administration", "languages"):
        decision = route("une question", scope=PAYS_SPECIALISE, subject=sujet)

        assert decision["layers"] == [COUCHE_SENEGAL], sujet
        assert decision["national_subject"] is True


# ----------------------------------------------------------------------
# 2. Profondeur d'abord, largeur ensuite
# ----------------------------------------------------------------------

def test_sur_le_pays_specialise_la_profondeur_passe_d_abord():
    """Ni l'une ni l'autre n'est une meilleure version de l'autre."""
    decision = route("Quels départements dans la région de Saint-Louis ?")

    assert decision["scope"] == PAYS_SPECIALISE
    assert decision["layers"] == [COUCHE_SENEGAL, COUCHE_MONDE]


def test_hors_du_pays_specialise_seule_la_reference_mondiale_repond():
    """La couche sénégalaise ne répond pas d'un autre pays."""
    decision = route("Quelle est la capitale de la France ?")

    assert decision["scope"] == "global"
    assert decision["layers"] == [COUCHE_MONDE]


def test_la_largeur_complete_quand_la_profondeur_ne_sait_pas():
    """La seconde couche est interrogée, et cela se voit."""
    reponse = ask(
        "Quelle est la monnaie du Sénégal ?",
        senegal_answer=_senegal("UNKNOWN"),
        world_answer=_monde("FOUND"),
    )

    assert reponse["answered_by"] == COUCHE_MONDE
    assert [t["layer"] for t in reponse["attempted"]] == [COUCHE_SENEGAL, COUCHE_MONDE]


def test_la_profondeur_n_est_pas_court_circuitee_quand_elle_sait():
    """Sinon la spécialisation ne servirait à rien."""
    reponse = ask(
        "Quels départements dans la région de Saint-Louis ?",
        senegal_answer=_senegal(),
        world_answer=_monde("FOUND"),
    )

    assert reponse["answered_by"] == COUCHE_SENEGAL
    assert [t["layer"] for t in reponse["attempted"]] == [COUCHE_SENEGAL]


# ----------------------------------------------------------------------
# 3. La décision se lit
# ----------------------------------------------------------------------

def test_la_reponse_dit_quelle_couche_a_parle():
    """Un routeur dont la décision ne se lit pas ne se débogue pas."""
    reponse = ask("Quelle est la capitale de la France ?", world_answer=_monde())

    assert reponse["answered_by"] == COUCHE_MONDE
    assert reponse["reason"]
    assert reponse["scope_method"] in ("declared", "keywords", "default")


def test_une_question_sans_reponse_dit_qui_a_ete_interroge():
    """« Personne ne sait » et « personne n'a été interrogé » diffèrent."""
    reponse = ask(
        "Quelle est la monnaie du Sénégal ?",
        senegal_answer=_senegal("UNKNOWN"),
        world_answer=_monde("UNKNOWN"),
    )

    assert reponse["answered_by"] == AUCUNE
    assert reponse["status"] == "UNKNOWN"
    assert len(reponse["attempted"]) == 2
    assert "n'a été interrogé" in reponse["note"]


def test_un_sujet_declare_l_emporte_sur_les_marqueurs():
    """
    Les marqueurs repèrent des mots, ils ne comprennent rien — et le dire est
    la moitié de leur utilité.
    """
    decision = route("Quelle est la loi foncière à Dakar ?", subject="geography")

    assert decision["subject"] == "geography"
    assert decision["subject_method"] == "declared"
    assert decision["layers"] == [COUCHE_SENEGAL, COUCHE_MONDE]


def test_la_decision_ne_consulte_aucune_connaissance():
    """
    `route()` est une décision, pas une recherche : elle doit répondre sans
    couche branchée du tout.
    """
    decision = route("Quelle est la capitale de la France ?")

    assert decision["layers"] == [COUCHE_MONDE]


def test_une_portee_invalide_est_refusee():
    """Rien n'est deviné : une portée mal écrite ne retombe pas sur mondial."""
    with pytest.raises(ValueError):
        route("une question", scope="pays:xx")


# ----------------------------------------------------------------------
# 4. Deux couches, aucun sous-ensemble (57.2)
# ----------------------------------------------------------------------

def test_les_deux_couches_portent_des_choses_differentes():
    """
    Si l'une était un sous-ensemble de l'autre, la garder serait une
    implémentation parallèle — ce que la directive interdit. Mesuré.
    """
    comparaison = layer_comparison()

    assert comparaison[COUCHE_MONDE]["countries"] >= 200
    assert comparaison[COUCHE_SENEGAL]["regions"] == 14
    assert comparaison[COUCHE_SENEGAL]["departments"] == 45


def test_chaque_couche_dit_ce_qu_elle_ne_peut_pas_offrir():
    """C'est ce qui prouve qu'aucune ne remplace l'autre."""
    comparaison = layer_comparison()

    assert "Aucun détail sous le pays" in comparaison[COUCHE_MONDE]["cannot_offer"]
    assert "Tout autre pays" in comparaison[COUCHE_SENEGAL]["cannot_offer"]
    assert "sous-ensemble" in comparaison["overlap"]


def test_le_rapport_nomme_ses_regles_et_ses_limites():
    """Ce qu'un lecteur doit savoir avant de lire une décision."""
    rapport = routing_report()

    regles = " ".join(rapport["rules"])
    assert "ne quitte pas son pays" in regles
    assert "quelle couche" in regles
    assert any("Fusionner deux réponses" in ligne for ligne in rapport["does_not"])


def test_le_routage_ne_fusionne_jamais_deux_reponses():
    """Fusionner perdrait laquelle vient d'où."""
    reponse = ask(
        "Quels départements dans la région de Saint-Louis ?",
        senegal_answer=_senegal(),
        world_answer=_monde("FOUND"),
    )

    assert isinstance(reponse["answered_by"], str)
    assert reponse["answered_by"] != f"{COUCHE_SENEGAL}+{COUCHE_MONDE}"


# ----------------------------------------------------------------------
# 5. Les routes
# ----------------------------------------------------------------------

@pytest.fixture
def client_routage(monkeypatch):
    """Client HTTP et clé nommée."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    with TestClient(server_module.app) as essai:
        yield essai, {"X-API-Key": "cle-awa"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def test_la_route_repond_et_dit_quelle_couche(client_routage):
    """De bout en bout, sur les couches réelles du dépôt."""
    client, cle = client_routage

    reponse = client.get(
        "/knowledge/ask", params={"q": "Quelle est la monnaie du Sénégal ?"},
        headers=cle,
    ).json()

    assert reponse["answered_by"] in (COUCHE_SENEGAL, COUCHE_MONDE, AUCUNE)
    assert reponse["layers"] == [COUCHE_SENEGAL, COUCHE_MONDE]


def test_la_route_refuse_une_portee_invalide(client_routage):
    """400 : la cause est dans l'appel, et l'appelant peut la corriger."""
    client, cle = client_routage

    reponse = client.get(
        "/knowledge/ask", params={"q": "x", "scope": "pays:xx"}, headers=cle,
    )

    assert reponse.status_code == 400


def test_la_route_des_couches_publie_la_comparaison(client_routage):
    """Un lecteur doit pouvoir vérifier le non-recouvrement sans lire le code."""
    client, cle = client_routage

    couches = client.get("/knowledge/layers", headers=cle).json()

    assert couches[COUCHE_SENEGAL]["departments"] == 45
    assert couches["routing"]["specialised_country"] == PAYS_SPECIALISE


def test_les_routes_de_routage_exigent_une_cle(client_routage):
    """Aucune n'est publique."""
    client, _ = client_routage

    assert client.get("/knowledge/ask", params={"q": "x"}).status_code in (401, 403)
    assert client.get("/knowledge/layers").status_code in (401, 403)
