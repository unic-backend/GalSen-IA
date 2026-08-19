"""
Tests de l'intention créative (K05.1, §6 et §7).

Le test qui compte est `TestNonDemande` : c'est la distinction que l'implémenta-
tion de référence auditée en K01 ne fait pas, et celle dont dépend l'interdiction
d'inventer du contenu.
"""

import pytest

from src.creative.intent import (
    CONFORME,
    CONTENU_NON_DEMANDE,
    CONTREDIT,
    INTERDIT,
    NON_VERIFIE,
    NATURES,
    NON_DEMANDE,
    OPTIONNEL,
    REQUIS,
    STATUTS_DECLARES,
    CreativeIntent,
    IntentElement,
    IntentRefused,
    accept,
    check_plan,
    declare,
    intent_report,
    offer,
)


class TestDeclaration:
    """Ce qui peut être déclaré, et ce qui est refusé à la construction."""

    def test_les_trois_statuts_declarables_sont_ceux_de_la_directive(self):
        assert STATUTS_DECLARES == (REQUIS, OPTIONNEL, INTERDIT)

    def test_non_demande_n_est_pas_declarable(self):
        with pytest.raises(IntentRefused, match=NON_DEMANDE):
            IntentElement(kind="object", value="chaise", status=NON_DEMANDE)

    def test_une_nature_inconnue_est_refusee(self):
        with pytest.raises(IntentRefused, match="non déclarée"):
            IntentElement(kind="ambiance", value="chaleureuse", status=REQUIS)

    def test_une_valeur_vide_est_refusee(self):
        with pytest.raises(IntentRefused, match="ne décide rien"):
            IntentElement(kind="object", value="   ", status=REQUIS)

    def test_une_contradiction_est_refusee_jamais_arbitree(self):
        with pytest.raises(IntentRefused, match="à la fois"):
            CreativeIntent(elements=(
                IntentElement(kind="object", value="voiture", status=REQUIS),
                IntentElement(kind="object", value="voiture", status=INTERDIT),
            ))

    def test_le_meme_element_deux_fois_avec_le_meme_statut_passe(self):
        intention = CreativeIntent(elements=(
            IntentElement(kind="object", value="voiture", status=REQUIS),
            IntentElement(kind="object", value="Voiture", status=REQUIS),
        ))

        assert intention.status_of("object", "voiture") == REQUIS

    def test_declare_construit_les_trois_listes_separement(self):
        intention = declare(
            "une scène de marché",
            required=[("place", "marché de Sandaga")],
            optional=[("audio", "musique douce")],
            forbidden=[("effect", "ralenti")],
        )

        assert [e.value for e in intention.by_status(REQUIS)] == ["marché de Sandaga"]
        assert [e.value for e in intention.by_status(OPTIONNEL)] == ["musique douce"]
        assert [e.value for e in intention.by_status(INTERDIT)] == ["ralenti"]

    def test_declare_ne_deduit_rien_du_texte_de_la_demande(self):
        """Le texte nomme un marché ; rien n'en est extrait sans déclaration."""
        intention = declare("une scène au marché avec de la musique")

        assert intention.elements == ()
        assert intention.status_of("place", "marché") == NON_DEMANDE

    def test_by_status_refuse_non_demande(self):
        with pytest.raises(IntentRefused, match="n'a pas de liste"):
            declare("x").by_status(NON_DEMANDE)


class TestNonDemande:
    """La distinction dont dépend l'interdiction d'inventer (§6)."""

    def test_un_element_jamais_mentionne_est_non_demande(self):
        intention = declare("un plan", required=[("entity", "Awa")])

        assert intention.status_of("camera_movement", "pan") == NON_DEMANDE

    def test_non_demande_n_autorise_pas(self):
        intention = declare("un plan", required=[("entity", "Awa")])

        verdict = intention.may_include("camera_movement", "pan")

        assert verdict["allowed"] is False
        assert verdict["status"] == NON_DEMANDE

    def test_les_deux_refus_ne_donnent_pas_le_meme_motif(self):
        """Un interdit se lève en changeant d'avis ; un non-demandé, en le demandant."""
        intention = declare("un plan", forbidden=[("effect", "ralenti")])

        interdit = intention.may_include("effect", "ralenti")
        jamais_dit = intention.may_include("effect", "flou")

        assert interdit["status"] == INTERDIT
        assert jamais_dit["status"] == NON_DEMANDE
        assert interdit["reason"] != jamais_dit["reason"]
        assert interdit["allowed"] is jamais_dit["allowed"] is False

    def test_requis_et_optionnel_autorisent_tous_les_deux(self):
        intention = declare("un plan",
                            required=[("entity", "Awa")],
                            optional=[("audio", "musique")])

        assert intention.may_include("entity", "Awa")["allowed"] is True
        assert intention.may_include("audio", "musique")["allowed"] is True

    def test_la_comparaison_plie_les_accents_des_deux_cotes(self):
        intention = declare("un plan", forbidden=[("style", "animé")])

        assert intention.status_of("style", "anime") == INTERDIT
        assert intention.status_of("style", "ANIMÉ") == INTERDIT

    def test_la_valeur_demandee_est_conservee_telle_qu_ecrite(self):
        intention = declare("un plan", required=[("place", "Marché de Sandaga")])

        assert intention.by_status(REQUIS)[0].value == "Marché de Sandaga"


class TestSuggestions:
    """Une suggestion est proposée, jamais posée — le contre-exemple de K01."""

    def test_offer_n_applique_rien(self):
        intention = declare("un plan", required=[("entity", "Awa")])

        rapport = offer(intention, [("camera_movement", "pan")],
                        source="LENS_MOTION_PRESET")

        assert rapport["applied_count"] == 0
        assert rapport["intent_unchanged"] is True
        assert all(s["applied"] is False for s in rapport["suggestions"])

    def test_offer_ne_modifie_pas_l_intention(self):
        intention = declare("un plan", required=[("entity", "Awa")])

        offer(intention, [("camera_movement", "pan")])

        assert intention.status_of("camera_movement", "pan") == NON_DEMANDE

    def test_une_suggestion_interdite_est_rendue_avec_son_refus(self):
        """Elle n'est pas retirée : la personne doit voir ce qu'on lui a proposé."""
        intention = declare("un plan", forbidden=[("effect", "ralenti")])

        rapport = offer(intention, [("effect", "ralenti")])

        assert len(rapport["suggestions"]) == 1
        assert rapport["suggestions"][0]["status"] == INTERDIT
        assert rapport["suggestions"][0]["would_be_allowed"] is False

    def test_accept_est_la_seule_porte_d_entree(self):
        intention = declare("un plan", required=[("entity", "Awa")])

        apres = accept(intention, [("camera_movement", "pan")],
                       stated_as="la personne a accepté la proposition")

        assert apres.status_of("camera_movement", "pan") == OPTIONNEL
        assert apres.by_status(OPTIONNEL)[0].stated_as != ""

    def test_accept_ne_modifie_pas_l_intention_d_origine(self):
        intention = declare("un plan", required=[("entity", "Awa")])

        accept(intention, [("camera_movement", "pan")])

        assert intention.status_of("camera_movement", "pan") == NON_DEMANDE

    def test_accept_refuse_de_contredire_un_interdit(self):
        intention = declare("un plan", forbidden=[("effect", "ralenti")])

        with pytest.raises(IntentRefused, match="à la fois"):
            accept(intention, [("effect", "ralenti")], status=REQUIS)

    def test_accept_refuse_un_statut_non_declarable(self):
        with pytest.raises(IntentRefused, match="non déclarable"):
            accept(declare("x"), [("object", "chaise")], status=NON_DEMANDE)


class TestVerificationDuPlan:
    """Trois manquements distincts, et un plan absent n'est pas un plan vide."""

    def test_un_plan_conforme_l_est(self):
        intention = declare("un plan",
                            required=[("entity", "Awa")],
                            optional=[("audio", "musique")])

        rapport = check_plan(intention, [("entity", "Awa"),
                                         ("audio", "musique")])

        assert rapport["verdict"] == CONFORME
        assert rapport["checked_count"] == 2

    def test_un_interdit_present_contredit_l_intention(self):
        intention = declare("un plan",
                            required=[("entity", "Awa")],
                            forbidden=[("effect", "ralenti")])

        rapport = check_plan(intention, [("entity", "Awa"),
                                         ("effect", "ralenti")])

        assert rapport["verdict"] == CONTREDIT
        assert rapport["forbidden_present"] == [{"kind": "effect",
                                                 "value": "ralenti"}]

    def test_un_requis_manquant_contredit_l_intention(self):
        intention = declare("un plan", required=[("entity", "Awa")])

        rapport = check_plan(intention, [])

        assert rapport["verdict"] == CONTREDIT
        assert rapport["required_missing"] == [{"kind": "entity",
                                                "value": "Awa"}]
        assert rapport["checked_count"] == 0

    def test_un_element_jamais_demande_a_son_propre_verdict(self):
        """Le cas LENS_MOTION_PRESET : rien d'interdit, rien qui manque."""
        intention = declare("un plan", required=[("entity", "Awa")])

        rapport = check_plan(intention, [("entity", "Awa"),
                                         ("camera_movement", "pan")])

        assert rapport["verdict"] == CONTENU_NON_DEMANDE
        assert rapport["not_requested_present"] == [
            {"kind": "camera_movement", "value": "pan"}
        ]
        assert rapport["forbidden_present"] == []
        assert rapport["required_missing"] == []

    def test_une_faute_franche_l_emporte_sur_un_non_demande(self):
        intention = declare("un plan", required=[("entity", "Awa")])

        rapport = check_plan(intention, [("camera_movement", "pan")])

        assert rapport["verdict"] == CONTREDIT
        assert rapport["not_requested_present"] != []

    def test_un_plan_absent_n_est_pas_un_plan_vide(self):
        intention = declare("un plan", required=[("entity", "Awa")])

        absent = check_plan(intention, None)
        vide = check_plan(intention, [])

        assert absent["verdict"] == NON_VERIFIE
        assert absent["checked_count"] is None
        assert absent["required_missing"] == []
        assert vide["verdict"] == CONTREDIT
        assert vide["checked_count"] == 0

    def test_le_plan_est_compare_accents_plies(self):
        intention = declare("un plan", forbidden=[("style", "animé")])

        rapport = check_plan(intention, [("style", "Anime")])

        assert rapport["verdict"] == CONTREDIT


class TestRapport:
    """Le rapport dit ce qui est tenu, pas ce qui est souhaité."""

    def test_le_rapport_seul_donne_le_vocabulaire(self):
        rapport = intent_report()

        assert rapport["declarable_statuses"] == list(STATUTS_DECLARES)
        assert rapport["returned_status_for_absent"] == NON_DEMANDE
        assert rapport["kinds"] == list(NATURES)
        assert "intent" not in rapport

    def test_le_rapport_avec_intention_la_serialise(self):
        intention = declare("une scène",
                            required=[("entity", "Awa")],
                            forbidden=[("effect", "ralenti")])

        rapport = intent_report(intention)

        assert rapport["intent"]["required"] == ["Awa"]
        assert rapport["intent"]["forbidden"] == ["ralenti"]
        assert rapport["intent"]["optional"] == []
        assert rapport["intent"]["request"] == "une scène"

    def test_la_regle_qui_compte_est_ecrite_dans_le_rapport(self):
        regles = " ".join(intent_report()["rules"])

        assert NON_DEMANDE in regles
        assert OPTIONNEL in regles
