"""
Tests de la liaison au moteur créatif (L12, ADR-033, §23, §24, §37).

Le test qui compte est `test_le_module_n_expose_aucune_fonction_qui_accepte` :
c'est la seule vérification qui tienne, parce que toutes les autres portent sur
un comportement que du code futur pourrait contourner en appelant `accept()`
directement.
"""

import pytest

from src.creative.intent import CONTENU_NON_DEMANDE, check_plan, declare
from src.live_context.creative import (
    CORRESPONDANCES,
    EXCLUSIONS,
    creative_link_report,
    eligible_couples,
    offer_from_session,
    suggestible,
    to_suggestions,
)
from src.live_context.state import MESURE, LiveContextState, Observation, unknown


def _obs(**kwargs) -> Observation:
    defauts = dict(subject="language", status=MESURE, modality="audio",
                   value="wo", provider="p1")
    defauts.update(kwargs)
    return Observation(**defauts)


def _etat(*observations) -> LiveContextState:
    return LiveContextState("s1").add(*observations)


class TestRienN_EstAccepte:
    """Observer quelque chose ne revient pas à le demander."""

    def test_le_module_n_expose_aucune_fonction_qui_accepte(self):
        import src.live_context.creative as creative

        exposees = [n for n in dir(creative) if not n.startswith("_")]

        assert not any("accept" in n or "apply" in n for n in exposees)

    def test_l_intention_n_est_pas_modifiee(self):
        intention = declare(request="une vidéo courte")

        resultat = offer_from_session(intention, _etat(_obs()))

        assert resultat["intent_unchanged"] is True
        assert resultat["applied_count"] == 0
        assert intention.elements == ()

    def test_le_resultat_declare_n_avoir_rien_accepte(self):
        resultat = offer_from_session(declare(request="x"), _etat(_obs()))

        assert resultat["accepted"] is False

    def test_le_rapport_declare_ne_rien_accepter(self):
        rapport = creative_link_report()

        assert rapport["accepts_anything"] is False
        assert rapport["modifies_intent"] is False


class TestCorrespondances:
    """Deux sujets, et ce qui n'y est pas porte sa raison."""

    def test_deux_correspondances_seulement(self):
        assert len(CORRESPONDANCES) == 2

    def test_une_langue_devient_un_element_de_langue(self):
        assert suggestible(_obs())["kind"] == "language"

    def test_un_locuteur_devient_une_entite(self):
        observation = _obs(subject="speaker", value="SPEAKER_01")

        assert suggestible(observation)["kind"] == "entity"

    def test_chaque_exclusion_porte_sa_raison(self):
        for raison in EXCLUSIONS.values():
            assert len(raison.strip()) > 20

    def test_une_transcription_ne_devient_pas_un_dialogue(self):
        observation = _obs(subject="transcript", value="bonjour à tous")

        verdict = suggestible(observation)

        assert verdict["eligible"] is False
        assert "pas ce qui est demandé" in verdict["reason"]

    def test_un_texte_d_ecran_ne_devient_pas_un_texte_incruste(self):
        observation = _obs(subject="screen_text", modality="screen",
                           value="Budget 2026")

        assert suggestible(observation)["eligible"] is False

    def test_un_sujet_sans_correspondance_le_dit(self):
        observation = _obs(subject="humeur", value="joyeuse")

        verdict = suggestible(observation)

        assert verdict["eligible"] is False
        assert "ne revient pas à le demander" in verdict["reason"]


class TestUneInconnueNeProposeRien:
    """Elle mettrait dans un plan ce que personne n'a mesuré."""

    def test_une_inconnue_est_inéligible(self):
        assert suggestible(unknown("language", "audio"))["eligible"] is False

    def test_une_inconnue_ne_produit_aucun_couple(self):
        assert eligible_couples(_etat(unknown("language", "audio"))) == []

    def test_elle_apparait_quand_meme_dans_le_detail(self):
        """Ce qui n'a pas été proposé est dit, jamais tu."""
        resultat = offer_from_session(declare(request="x"),
                                      _etat(unknown("language", "audio")))

        assert len(resultat["not_offered"]) == 1


class TestLangueDeclaree:
    """§24 : « wolof » et « wo » ne doivent pas devenir deux choses."""

    def test_un_code_declare_passe(self):
        assert suggestible(_obs(value="wo"))["eligible"] is True

    def test_un_nom_de_langue_non_declare_est_refuse(self):
        verdict = suggestible(_obs(value="wolof"))

        assert verdict["eligible"] is False
        assert "languages.yaml" in verdict["reason"]

    def test_le_refus_explique_la_consequence(self):
        verdict = suggestible(_obs(value="wolof"))

        assert "ne couvrirait pas l'autre" in verdict["reason"]


class TestProvenance:
    """§37 : une proposition anonyme ne peut pas être pesée."""

    def test_chaque_proposition_porte_sa_session_et_son_fournisseur(self):
        for entree in to_suggestions(_etat(_obs())):
            assert entree["provenance"]["session_id"] == "s1"
            assert entree["provenance"]["provider"] == "p1"

    def test_un_fournisseur_absent_est_dit_inconnu_pas_omis(self):
        entrees = to_suggestions(_etat(_obs(provider="")))

        assert entrees[0]["provenance"]["provider"] == "inconnu"

    def test_la_source_de_l_offre_nomme_la_session(self):
        resultat = offer_from_session(declare(request="x"), _etat(_obs()))

        assert "session:s1" in resultat["source"]


class TestOffre:
    """Ce que `offer()` répond, rendu tel quel."""

    def test_les_doublons_sont_retires(self):
        etat = _etat(_obs(), _obs())

        assert len(eligible_couples(etat)) == 1

    def test_une_suggestion_contre_un_interdit_est_rendue_avec_son_refus(self):
        """La personne doit voir ce qui lui a été proposé contre son intention."""
        intention = declare(request="x", forbidden=[("language", "wo")])

        resultat = offer_from_session(intention, _etat(_obs()))

        assert resultat["suggestions"][0]["would_be_allowed"] is False
        assert resultat["suggestions"][0]["applied"] is False

    def test_un_etat_vide_ne_propose_rien(self):
        resultat = offer_from_session(declare(request="x"),
                                      LiveContextState("s1"))

        assert resultat["suggestions"] == []
        assert resultat["not_offered"] == []

    def test_un_plan_construit_sur_une_proposition_non_acceptee_contredit(self):
        """La preuve que proposer n'est pas demander."""
        intention = declare(request="x")

        offer_from_session(intention, _etat(_obs()))
        verdict = check_plan(intention, [("language", "wo")])

        assert verdict["verdict"] == CONTENU_NON_DEMANDE
        assert verdict["not_requested_present"] == [
            {"kind": "language", "value": "wo"}]


class TestRapport:
    """Ce qui est réutilisé, et ce qui est refusé."""

    def test_les_modules_reutilises_sont_nommes(self):
        reutilises = " ".join(creative_link_report()["reused"])

        assert "creative/intent.py" in reutilises
        assert "scene.py" in reutilises

    def test_les_regles_qui_comptent_sont_ecrites(self):
        regles = " ".join(creative_link_report()["rules"])

        assert "n'est une demande" in regles
        assert "n'expose aucune fonction qui " in regles


def test_le_module_ne_leve_pas_pour_une_observation_ordinaire():
    """Aucun chemin ne casse sur une observation normale."""
    try:
        to_suggestions(_etat(_obs(), unknown("speaker", "audio")))
    except Exception as erreur:  # pragma: no cover - le test est l'assertion
        pytest.fail(f"levée inattendue : {erreur}")
