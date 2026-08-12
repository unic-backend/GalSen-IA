"""
La vue : lire un écran, ou dire pourquoi on ne peut pas (VOLET 34, ch. 05).

Trois propriétés sont éprouvées ici, et elles viennent de décisions déjà prises
plutôt que d'un benchmark :

1. **Un élément porte son identité** — rôle, libellé, bornes. Le portillon
   d'approbation doit pouvoir dire *quoi* sera touché ; « cliquer en (412, 380) »
   est un tampon accompagné d'une ligne de journal (ADR-017 §4).
2. **Un refus nomme sa raison.** « Aucun élément » et « je ne sais pas regarder »
   conduisent à deux actions différentes.
3. **Une lecture d'écran ne part pas chez un tiers**, sans condition et sans
   drapeau à consulter (ADR-018).

Les backends de plateforme ne sont pas éprouvés ici : les vérifier demande une
machine avec un bureau, comme TEST 2 et TEST 6 en demandent une avec Docker.
Ce que les tests fournissent est un lecteur vérifiable — trois opérations, comme
un vrai — pour que le chemin complet soit éprouvé sans prétendre avoir vu un
écran.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.screen import (  # noqa: E402
    ScreenBackend,
    ScreenCaptureLeavingHost,
    ScreenElement,
    ScreenSnapshot,
    ScreenTool,
    ScreenUnavailable,
    assert_stays_local,
    backends_disponibles,
)


class LecteurDeTest(ScreenBackend):
    """
    Lecteur d'écran en mémoire.

    Il ne prétend pas voir un écran : il fournit les trois opérations du contrat
    pour que le chemin de l'outil soit éprouvé sans bureau.
    """

    name = "test"
    family = "accessibility"

    def __init__(self, elements=None, indisponible=None):
        self.elements = elements or []
        self.indisponible = indisponible

    def unavailable_reason(self):
        return self.indisponible

    def snapshot(self):
        if self.indisponible:
            raise ScreenUnavailable(self.indisponible)
        return ScreenSnapshot(elements=self.elements, backend=self.name)


class LecteurPixels(LecteurDeTest):
    """Le même, présenté comme un repli en pixels."""

    name = "pixels-test"
    family = "pixels"


@pytest.fixture
def ecran():
    """Un écran de test avec trois éléments identifiés."""
    return [
        ScreenElement(role="button", label="Enregistrer", bounds=(10, 20, 80, 24),
                      application="Éditeur"),
        ScreenElement(role="button", label="Supprimer", bounds=(100, 20, 80, 24),
                      application="Éditeur", enabled=False),
        ScreenElement(role="text", label="rapport.txt", bounds=(10, 60, 200, 18),
                      application="Éditeur", identifier="champ_nom"),
    ]


# ----------------------------------------------------------------------
# Un élément se nomme
# ----------------------------------------------------------------------

def test_un_element_se_decrit_pour_une_approbation(ecran):
    """C'est la phrase qu'un humain lira avant d'autoriser une action."""
    assert ecran[0].describe() == "button « Enregistrer » dans Éditeur"
    assert "(désactivé)" in ecran[1].describe()


def test_un_element_sans_libelle_le_dit_au_lieu_de_l_inventer():
    """
    Un libellé fabriqué serait pire qu'absent : l'humain approuverait une
    description qui ne correspond à rien.
    """
    sans_nom = ScreenElement(role="button", bounds=(0, 0, 10, 10))

    assert "sans libellé" in sans_nom.describe()


def test_un_identifiant_sert_de_repli_au_libelle(ecran):
    """Quand l'application donne un identifiant stable, il vaut mieux que rien."""
    anonyme = ScreenElement(role="text", identifier="champ_nom")

    assert "[champ_nom]" in anonyme.describe()


# ----------------------------------------------------------------------
# Lire
# ----------------------------------------------------------------------

def test_un_instantane_dit_par_quoi_il_a_ete_lu(ecran):
    """
    Une lecture par l'arbre et une déduction par pixels n'ont pas la même
    fiabilité — comme la recherche dit déjà si elle fut sémantique ou lexicale.
    """
    resultat = ScreenTool(backends=[LecteurDeTest(ecran)]).execute("snapshot")

    assert resultat["backend"] == "test"
    assert resultat["element_count"] == 3


def test_la_recherche_par_libelle_rend_des_elements_decrits(ecran):
    """Ce que trouve la recherche doit être directement approuvable."""
    resultat = ScreenTool(backends=[LecteurDeTest(ecran)]).execute("find", "supprimer")

    assert resultat["match_count"] == 1
    assert "Supprimer" in resultat["elements"][0]["description"]


def test_la_recherche_peut_exiger_un_role(ecran):
    """« Le bouton nommé rapport.txt » et « le texte » ne sont pas la même cible."""
    outil = ScreenTool(backends=[LecteurDeTest(ecran)])

    assert outil.execute("find", "rapport", role="text")["match_count"] == 1
    assert outil.execute("find", "rapport", role="button")["match_count"] == 0


def test_une_requete_vide_est_refusee(ecran):
    """Chercher « rien » rendrait tout l'écran, ce qui n'est pas une recherche."""
    with pytest.raises(ValueError):
        ScreenTool(backends=[LecteurDeTest(ecran)]).execute("find", "   ")


# ----------------------------------------------------------------------
# Refuser en nommant la raison
# ----------------------------------------------------------------------

def test_sans_lecteur_l_outil_refuse_au_lieu_de_rendre_du_vide():
    """
    Le mode d'échec que ce dépôt traque : une liste vide se lirait « l'écran est
    vide » alors qu'elle veut dire « je ne sais pas regarder ».
    """
    outil = ScreenTool(backends=[LecteurDeTest(indisponible="pas de session graphique")])

    with pytest.raises(ScreenUnavailable, match="pas de session graphique"):
        outil.execute("snapshot")


def test_l_etat_repond_toujours_meme_aveugle():
    """
    C'est l'opération qui permet à un opérateur de savoir quoi installer, et à un
    agent de constater qu'il est aveugle. Elle ne doit jamais lever.
    """
    etat = ScreenTool(backends=[LecteurDeTest(indisponible="module absent")]).execute(
        "availability"
    )

    assert etat["can_see"] is False
    assert etat["preferred"] is None
    assert etat["backends"][0]["reason"] == "module absent"


def test_sur_cette_machine_sans_ecran_la_raison_est_nommee():
    """
    Mesuré ici, pas supposé : ce conteneur n'a pas de session graphique, et
    l'outil le dit plutôt que de se déclarer simplement indisponible.
    """
    etat = ScreenTool().execute("availability")

    assert etat["can_see"] is False
    raisons = " ".join(ligne["reason"] for ligne in etat["backends"])
    assert "session graphique" in raisons


def test_une_operation_inconnue_liste_celles_qui_existent():
    """Un refus qui n'aide pas à se corriger est un refus à moitié."""
    with pytest.raises(ValueError, match="availability"):
        ScreenTool().execute("regarde_par_la_fenetre")


# ----------------------------------------------------------------------
# L'ordre de préférence, et le repli qui se déclare
# ----------------------------------------------------------------------

def test_l_accessibilite_passe_avant_les_pixels(ecran):
    """
    ADR-017 §3. L'ordre n'est pas une préférence de performance : une capture
    envoyée à un modèle est ce qu'ADR-014 refuse, et des pixels ne portent aucune
    identité, donc aucune approbation lisible.
    """
    utilisables = backends_disponibles([LecteurPixels(ecran), LecteurDeTest(ecran)])

    assert [backend.family for backend in utilisables] == ["accessibility", "pixels"]


def test_un_repli_par_pixels_se_declare_dans_le_resultat(ecran):
    """
    Mélanger silencieusement les deux fiabilités ferait traiter une déduction
    comme une lecture.
    """
    resultat = ScreenTool(backends=[LecteurPixels(ecran)]).execute("snapshot")

    assert resultat["backend"] == "pixels-test"
    assert any("repli en pixels" in note for note in resultat["notes"])


# ----------------------------------------------------------------------
# Ce qui est lu ne quitte pas la machine
# ----------------------------------------------------------------------

class FournisseurLocal:
    """Un fournisseur souverain."""


class OpenAIProvider:
    """Nom volontairement identique au fournisseur hébergé du projet."""


class HostedProvider:
    """Base des fournisseurs hébergés."""


class UnAutreHeberge(HostedProvider):
    """Un tiers qui hérite de la base hébergée."""


def test_une_lecture_d_ecran_ne_part_pas_chez_un_tiers():
    """
    ADR-018 range les captures d'écran parmi les charges qu'**aucune dérogation**
    ne couvre : une image de l'écran de quelqu'un est la plus révélatrice que
    cette plateforme manipulera jamais.
    """
    with pytest.raises(ScreenCaptureLeavingHost, match="OpenAIProvider"):
        assert_stays_local(OpenAIProvider())


def test_le_refus_suit_l_heritage():
    """
    Un fournisseur tiers ajouté demain héritera de la base hébergée. Ne regarder
    que le nom de la classe laisserait passer le suivant.
    """
    with pytest.raises(ScreenCaptureLeavingHost):
        assert_stays_local(UnAutreHeberge())


def test_un_fournisseur_local_est_accepte():
    """Le contre-test : le refus ne doit pas tout bloquer."""
    assert_stays_local(FournisseurLocal())


def test_le_refus_ne_consulte_aucun_drapeau(monkeypatch):
    """
    Inconditionnel veut dire inconditionnel : couper le mode souverain ne doit
    rien changer. Le ranger derrière un drapeau, c'est accepter qu'un jour le
    drapeau soit mal positionné.
    """
    monkeypatch.setenv("GALSEN_SOVEREIGN_MODE", "false")

    with pytest.raises(ScreenCaptureLeavingHost):
        assert_stays_local(OpenAIProvider())
