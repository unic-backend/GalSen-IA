"""
Le contrat des connecteurs, lisible par un programme (phase 59.2).

La vague II avait construit les pièces qu'un connecteur doit porter — contrat de
données, cycle de vie lié à une personne, privilèges, frontière de confiance — et
le registre refuse un connecteur qui ne les porte pas. Ce qui n'avait jamais été
écrit, c'est ce dont un auteur extérieur a réellement besoin : **la liste
complète de ce qui va le refuser, avant qu'il écrive quoi que ce soit**.

Un connecteur n'est pas un greffon, et les différences comptent plus que les
ressemblances : un greffon tourne dans un bac à sable, **un connecteur tourne
dans le processus**. Prétendre le contraire serait le mensonge dangereux, et le
contrat le dit à voix haute.

Ce que ces tests gardent :

1. **Chaque règle de refus dit pourquoi.** Une règle sans raison se lit comme un
   caprice, et se contourne.
2. **La page ne peut pas dériver du code** : elle est confrontée au contrat.
3. **La différence avec un greffon est déclarée**, pas laissée à deviner.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.connectors.sdk import (  # noqa: E402
    VERSION_DU_CONTRAT,
    connector_contract,
    connector_refusal_rules,
)

PAGE = os.path.join(os.path.dirname(__file__), "..", "docs", "connectors", "README.md")


def test_le_contrat_liste_toutes_les_regles_de_refus():
    """Un auteur qui découvre un refus au moment d'être refusé a mal lu — ou on
    a mal écrit."""
    regles = {refus["rule"] for refus in connector_refusal_rules()}

    assert regles == {
        "contract_required", "retention_declared", "private_needs_subject",
        "destructive_by_declaration", "authorisation_before_reach",
        "external_is_data",
    }


def test_chaque_regle_dit_ce_qu_elle_refuse_et_pourquoi():
    """Une règle sans raison se contourne."""
    for regle in connector_refusal_rules():
        assert regle["refuses"].strip(), regle["rule"]
        assert regle["why"].strip(), regle["rule"]


def test_la_page_ne_peut_pas_deriver_du_code():
    """
    **La garde de la phase.** Une règle ajoutée au code et oubliée dans la page
    fait échouer la suite, au lieu d'être découverte par l'auteur qu'elle
    refuse.
    """
    with open(PAGE, "r", encoding="utf-8") as flux:
        texte = flux.read()

    for regle in connector_refusal_rules():
        assert regle["rule"] in texte, f"Règle « {regle['rule']} » absente de la page"
    assert VERSION_DU_CONTRAT in texte


def test_le_contrat_dit_qu_un_connecteur_n_est_pas_en_bac_a_sable():
    """C'est la différence la plus dangereuse à laisser deviner."""
    differences = " ".join(connector_contract()["differences_from_plugins"])

    assert "dans le processus" in differences
    assert "mensonge dangereux" in differences


def test_la_retention_est_exigee_en_clair():
    """« rien » est la meilleure réponse ; le silence n'en est pas une."""
    retention = connector_contract()["declares"]["data_contract"]["retention"]

    assert "rien" in retention
    assert "silence" in retention


def test_les_privileges_destructeurs_sont_nommes():
    """Ne pas donner de permissions destructrices par défaut, dit la directive."""
    privileges = connector_contract()["declares"]["privileges"]

    assert set(privileges["destructive"]) == {"delete", "administer"}
    assert "fournisseur" in privileges["note"]


def test_le_cycle_de_vie_distingue_ses_cinq_etats():
    """Absente, expirée et révoquée ne sont pas la même chose."""
    cycle = connector_contract()["lifecycle"]

    assert set(cycle) == {
        "not_configured", "not_authorized", "authorized", "expired", "revoked",
    }


def test_le_contrat_dit_ce_que_la_plateforme_ne_fait_pas():
    """Y compris ce qui est inconfortable à écrire."""
    ne_fait_pas = " ".join(connector_contract()["does_not"])

    assert "Fabriquer un identifiant" in ne_fait_pas
    assert "bac à sable" in ne_fait_pas
    assert "Deviner un propriétaire" in ne_fait_pas
