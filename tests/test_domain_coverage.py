"""
Architecture / construction, et la couverture des domaines (phases 55.1 et 55.2).

**55.1 — le sujet `construction` entre dans la taxonomie**, après relecture,
comme cette énumération l'exige. Ce n'est pas un doublon d'`engineering`, et la
raison est la règle de tout le VOLET : la physique d'une poutre est universelle,
**ce qu'il est permis de bâtir ne l'est pas**. Règles parasismiques, permis,
coefficients réglementaires sont fixés par un territoire, souvent par décret —
une norme étrangère appliquée ici n'est pas une approximation, c'est une autre
règle.

Le sujet n'est donc pas rangé parmi les `NATIONAL_SUBJECTS` — l'en couper
priverait d'un savoir matériau qui, lui, voyage — mais sa **part normative** est
déclarée et voyage avec chaque réponse.

**55.2 — la couverture des domaines devient mesurée.** Deux listes de domaines
vides existaient, écrites à la main dans un script, sur le Sénégal seulement.
Elles étaient justes le jour où elles ont été écrites : c'est précisément le
problème d'une liste écrite à la main.

Ce que ces tests gardent :

1. **Trois absences qui se ressemblent appellent trois gestes différents** :
   inscrire une source, en activer une, ou chercher pourquoi une acquisition
   active n'a rien rapporté.
2. **Sans compteur, le nombre d'éléments vaut `null`** — jamais zéro.
3. **Pour un sujet national, une source mondiale n'est pas un repli** : elle est
   hors sujet.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.domains import (  # noqa: E402
    EMPTY,
    NO_SOURCE,
    NOT_ENABLED,
    NOT_MEASURED,
    POPULATED,
    domain_coverage,
    domain_state,
)
from src.knowledge_engine.scope import (  # noqa: E402
    NATIONAL_SUBJECTS,
    KnowledgeSubject,
    normative_split,
    parse_subject,
)

REGISTRE = {
    "sources": [
        {"name": "Norme mondiale", "scope": "global", "subjects": ["construction"],
         "enabled": False},
        {"name": "Institut national", "scope": "country:sn",
         "subjects": ["agriculture"], "enabled": True},
        {"name": "Journal officiel", "scope": "country:sn", "subjects": ["law"],
         "enabled": False},
    ],
    "deny": [], "files": [], "loaded": True,
}


# ----------------------------------------------------------------------
# 1. Le sujet construction (55.1)
# ----------------------------------------------------------------------

def test_construction_est_un_sujet_declare():
    """Ajouté après relecture, comme l'énumération l'exige."""
    assert parse_subject("construction") is KnowledgeSubject.CONSTRUCTION


def test_construction_n_est_pas_coupee_du_savoir_mondial():
    """
    L'en couper priverait d'une physique des matériaux qui, elle, voyage. Ce
    n'est pas un sujet national au sens de `law` ou `languages`.
    """
    assert KnowledgeSubject.CONSTRUCTION not in NATIONAL_SUBJECTS


def test_la_part_normative_de_la_construction_est_declaree_territoriale():
    """
    **La règle du VOLET.** Une norme étrangère appliquée ici n'est pas une
    approximation, c'est une autre règle.
    """
    partage = normative_split("construction")

    assert "ne change pas de pays" in partage["universal"]
    assert "parasismiques" in partage["territorial"]
    assert "une autre règle" in partage["territorial"]


def test_un_sujet_sans_part_normative_n_en_declare_pas():
    """Le partage doit vouloir dire quelque chose là où il existe."""
    assert normative_split("agriculture") is None
    assert normative_split("pas-un-sujet") is None


def test_l_etat_d_un_domaine_normatif_porte_son_partage():
    """La règle voyage avec la réponse, pas seulement dans un fichier."""
    etat = domain_state("construction", "country:sn", registre=REGISTRE)

    assert "normative_split" in etat
    assert "jamais ce qu'un territoire prescrit" in etat["note"]


# ----------------------------------------------------------------------
# 2. Trois absences, trois gestes (55.2)
# ----------------------------------------------------------------------

def test_aucune_source_inscrite_demande_d_en_inscrire_une():
    """La lacune est en amont de toute acquisition."""
    etat = domain_state("history", "country:sn", registre=REGISTRE)

    assert etat["state"] == NO_SOURCE
    assert "Inscrire une source" in etat["action"]


def test_une_source_inscrite_mais_endormie_demande_une_activation():
    """
    Inscrire n'est pas activer (ADR-021) : un domaine dont les sources dorment
    n'a jamais eu le droit d'essayer.
    """
    etat = domain_state("construction", "country:sn", registre=REGISTRE)

    assert etat["state"] == NOT_ENABLED
    assert etat["declared_sources"] == ["Norme mondiale"]
    assert etat["enabled_sources"] == []


def test_une_source_active_et_une_base_vide_est_un_echec_reel():
    """Et non une absence de permission : les deux appellent des gestes opposés."""
    etat = domain_state(
        "agriculture", "country:sn", counter=lambda *_: 0, registre=REGISTRE,
    )

    assert etat["state"] == EMPTY
    assert "n'a rien rapporté" in etat["action"]


def test_un_domaine_qui_porte_quelque_chose_est_peuple():
    """Le seul état qui n'appelle rien."""
    etat = domain_state(
        "agriculture", "country:sn", counter=lambda *_: 212, registre=REGISTRE,
    )

    assert etat["state"] == POPULATED
    assert etat["items"] == 212


def test_sans_compteur_le_nombre_d_elements_est_nul_pas_zero():
    """
    **Le défaut que ce test a trouvé dans le module lui-même.** Sans compteur,
    l'état retombait sur `SOURCES_ENABLED_BUT_EMPTY` : le module annonçait « la
    base est vide » là où il fallait lire « personne n'a regardé » — exactement
    la confusion qu'il prétend empêcher, commise par lui.
    """
    etat = domain_state("agriculture", "country:sn", registre=REGISTRE)

    assert etat["items"] is None
    assert etat["state"] == NOT_MEASURED
    assert "n'est pas « vide »" in etat["action"]


# ----------------------------------------------------------------------
# 3. Un sujet national ne se remplit pas de mondial
# ----------------------------------------------------------------------

def test_une_source_mondiale_ne_couvre_pas_un_sujet_national():
    """
    Pour le droit, une source mondiale n'est pas un repli : elle est hors
    sujet. Le Journal officiel est inscrit mais endormi — c'est lui, et lui
    seul, qui compte ici.
    """
    registre = {
        **REGISTRE,
        "sources": REGISTRE["sources"] + [
            {"name": "Organisation mondiale", "scope": "global",
             "subjects": ["law"], "enabled": True},
        ],
    }

    etat = domain_state("law", "country:sn", registre=registre)

    assert etat["national_subject"] is True
    assert etat["declared_sources"] == ["Journal officiel"]
    assert etat["state"] == NOT_ENABLED


def test_une_source_mondiale_couvre_un_sujet_qui_voyage():
    """La contre-épreuve : sans elle, la règle serait un refus général."""
    etat = domain_state("construction", "country:sn", registre=REGISTRE)

    assert etat["declared_sources"] == ["Norme mondiale"]


# ----------------------------------------------------------------------
# 4. La couverture, sur le dépôt réel
# ----------------------------------------------------------------------

def test_la_couverture_couvre_tous_les_sujets_sauf_le_non_classe():
    """`unspecified` dit « pas encore classé » ; le mesurer n'aurait pas de sens."""
    couverture = domain_coverage("country:sn")

    sujets = {domaine["subject"] for domaine in couverture["domains"]}
    assert sujets == {
        sujet.value for sujet in KnowledgeSubject
        if sujet is not KnowledgeSubject.UNSPECIFIED
    }


def test_le_depot_reel_n_a_aucune_source_activee():
    """
    Mesuré, pas supposé : **aucune** source n'est activée dans cette
    installation, donc aucun domaine ne peut être `EMPTY` — il faudrait avoir
    eu le droit d'essayer.
    """
    couverture = domain_coverage("country:sn")

    assert EMPTY not in couverture["by_state"]
    assert NOT_MEASURED not in couverture["by_state"]
    assert couverture["by_state"][NOT_ENABLED] > 0


def test_la_couverture_dit_qu_elle_n_a_rien_compte():
    """Sans compteur branché, elle le déclare plutôt que de rendre des zéros."""
    couverture = domain_coverage("country:sn")

    assert couverture["measured"] is False
    assert all(domaine["items"] is None for domaine in couverture["domains"])


def test_la_couverture_nomme_ses_regles_et_ses_limites():
    """Ce qu'un lecteur doit savoir avant de lire les états."""
    couverture = domain_coverage()

    regles = " ".join(couverture["rules"])
    assert "trois gestes" in regles
    assert "Inscrire n'est pas activer" in regles
    assert any("il ne va rien chercher" in ligne for ligne in couverture["does_not"])


def test_une_portee_invalide_est_refusee():
    """Rien n'est deviné : une portée mal écrite ne retombe pas sur mondial."""
    with pytest.raises(ValueError):
        domain_coverage("pays:xx")
