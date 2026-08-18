"""
Tests for verification, drift, continuity (§48–§51, ADR-026) and crowds (§20).

The property that matters most is an absence: there is no composite identity
score, and no field can receive one. Everything else follows from it — three
outcomes rather than two, a drift of UNKNOWN rather than 0.0, and a verdict that
stays INCOMPLETE while anything applicable went unmeasured.
"""

import pytest

from src.creative.crowd import (
    AmbientMotion,
    CrowdRefused,
    Population,
    budget,
    crowd_report,
    promote_to_entity,
)
from src.creative.verification import (
    DIMENSIONS_DE_CONTINUITE,
    ECHOUEE,
    EN_ECHEC,
    INCOMPLET,
    MESUREE,
    NON_MESURABLE,
    VERIFIE,
    DimensionResult,
    ShotVerification,
    VerificationRefused,
    continuity_check,
    drift,
    drift_across,
    identity_dimensions_here,
    not_measurable,
    quality_loop,
    verdict,
    verification_report,
)
from src.creative.world import ARRIERE_PLAN, FOULE, HERO, EntityState, WorldState


def _mesuree(dimension="colour_consistency", valeur=0.8):
    """Une dimension réellement mesurée, méthode et échelle nommées."""
    return DimensionResult(
        dimension=dimension, outcome=MESUREE, value=valeur,
        method="distance de Bhattacharyya sur histogrammes",
        scale="0 = identique, 1 = totalement différent",
    )


# --------------------------------------------------------------------------
# L'absence qui structure tout
# --------------------------------------------------------------------------


def test_aucun_score_composite_n_existe():
    rapport = verification_report()
    assert rapport["composite_score"] is None
    # Aucune clé du verdict ne peut en recevoir un.
    resume = verdict([_mesuree()])
    assert "score" not in resume
    assert "composite" in resume["note"]


def test_une_mesure_sans_methode_est_refusee():
    with pytest.raises(VerificationRefused) as erreur:
        DimensionResult(dimension="facial_similarity", outcome=MESUREE,
                        value=0.9, scale="0 à 1")
    assert "invention habillée en mesure" in str(erreur.value)


def test_une_mesure_sans_echelle_est_refusee():
    with pytest.raises(VerificationRefused) as erreur:
        DimensionResult(dimension="facial_similarity", outcome=MESUREE,
                        value=0.9, method="comparaison de plongements")
    assert "ce que le nombre signifie" in str(erreur.value)


def test_une_dimension_non_mesurable_nomme_ce_qui_manque():
    with pytest.raises(VerificationRefused) as erreur:
        DimensionResult(dimension="facial_similarity", outcome=NON_MESURABLE)
    # Le rapport doit servir de liste d'installation.
    assert "liste d'installation" in str(erreur.value)


def test_une_dimension_non_mesurable_ne_porte_pas_de_valeur():
    with pytest.raises(VerificationRefused) as erreur:
        DimensionResult(dimension="facial_similarity", outcome=NON_MESURABLE,
                        value=0.0, missing_capability="face_detection")
    assert "L'un des deux est faux" in str(erreur.value)


# --------------------------------------------------------------------------
# L'état réel sur cette machine
# --------------------------------------------------------------------------


def test_toutes_les_dimensions_d_identite_sont_non_mesurables_ici():
    dimensions = identity_dimensions_here()
    assert len(dimensions) == 7
    assert all(d.outcome == NON_MESURABLE for d in dimensions)
    # Aucune détection de visage ici : rien de facial n'est calculable.
    facial = [d for d in dimensions if d.dimension == "facial_similarity"][0]
    assert facial.missing_capability == "face_detection"


def test_le_verdict_ici_est_incomplet_et_nomme_les_capacites():
    resume = verdict(identity_dimensions_here())
    assert resume["verdict"] == INCOMPLET
    assert "face_detection" in resume["missing_capabilities"]
    assert "n'a pas été vérifiée" in resume["reason"]


def test_une_seule_dimension_non_mesurable_suffit_a_rendre_incomplet():
    resultats = [_mesuree(), not_measurable("facial_similarity",
                                            "face_detection")]
    assert verdict(resultats)["verdict"] == INCOMPLET


def test_tout_mesure_et_conforme_donne_verifie():
    assert verdict([_mesuree(), _mesuree("clothing_consistency", 0.1)])[
        "verdict"] == VERIFIE


def test_un_ecart_constate_donne_un_echec():
    echec = DimensionResult(dimension="clothing_consistency", outcome=ECHOUEE,
                            severity="MAJOR")
    assert verdict([_mesuree(), echec])["verdict"] == EN_ECHEC


def test_un_rapport_vide_n_est_pas_une_conformite():
    resume = verdict([])
    assert resume["verdict"] == INCOMPLET
    assert "absence de vérification" in resume["reason"]


# --------------------------------------------------------------------------
# La dérive
# --------------------------------------------------------------------------


def test_une_derive_entre_deux_mesures_est_calculee():
    resultat = drift(_mesuree(valeur=0.82), _mesuree(valeur=0.61))
    assert resultat["state"] == "MEASURED"
    assert resultat["drift"] == pytest.approx(0.21)


def test_une_derive_sur_une_dimension_non_mesuree_est_inconnue():
    absente = not_measurable("facial_similarity", "face_detection")
    resultat = drift(absente, absente)
    assert resultat["state"] == "UNKNOWN"
    # `0.0` affirmerait l'absence de dérive.
    assert resultat["drift"] is None
    assert "chaîne cassée" in resultat["reason"]


def test_comparer_deux_dimensions_differentes_est_refuse():
    with pytest.raises(VerificationRefused) as erreur:
        drift(_mesuree("facial_similarity"), _mesuree("clothing_consistency"))
    assert "aucun sens" in str(erreur.value)


def test_la_derive_sur_un_seul_plan_n_existe_pas():
    resultat = drift_across([ShotVerification(shot_id="s1")])
    assert resultat["comparisons"] == []
    assert "entre deux états" in resultat["reason"]


def test_les_dimensions_inconnues_ne_comptent_ni_stables_ni_derivantes():
    absente = not_measurable("facial_similarity", "face_detection")
    plans = [
        ShotVerification(shot_id="s1", dimensions=(absente, _mesuree(valeur=0.2))),
        ShotVerification(shot_id="s2", dimensions=(absente, _mesuree(valeur=0.7))),
    ]
    resultat = drift_across(plans)
    assert resultat["unknown_dimensions"] == ["facial_similarity"]
    assert resultat["affected_shots"] == ["s2"]


# --------------------------------------------------------------------------
# La continuité
# --------------------------------------------------------------------------


def test_une_dimension_applicable_jamais_examinee_est_signalee():
    resultat = continuity_check([_mesuree("lighting", 0.1)],
                                applicable=["lighting", "clothing"])
    assert resultat["never_examined"] == ["clothing"]
    assert resultat["verdict"] == INCOMPLET
    # Un contrôle qui ne liste que ce qu'il a regardé se lit comme complet.
    assert "contrôle complet" in resultat["reason"]


def test_la_continuite_parfaite_n_est_jamais_affirmee():
    resultat = continuity_check(
        [_mesuree(dimension, 0.0) for dimension in DIMENSIONS_DE_CONTINUITE])
    assert resultat["claims_perfect_continuity"] is False
    assert resultat["verdict"] == VERIFIE


# --------------------------------------------------------------------------
# La boucle qualité
# --------------------------------------------------------------------------


def test_seuls_les_plans_en_ecart_sont_regeneres():
    echec = DimensionResult(dimension="clothing_consistency",
                            outcome=ECHOUEE, severity="MAJOR")
    plans = [
        ShotVerification(shot_id="s1", dimensions=(_mesuree(),)),
        ShotVerification(shot_id="s2", dimensions=(echec,)),
    ]
    boucle = quality_loop(plans)
    assert boucle["regenerate"] == ["s2"]
    assert boucle["passed"] == ["s1"]
    assert boucle["next_stage"] == "REGENERATE"


def test_un_plan_incomplet_est_a_verifier_pas_a_refaire():
    plans = [ShotVerification(shot_id="s1",
                              dimensions=tuple(identity_dimensions_here()))]
    boucle = quality_loop(plans)
    assert boucle["regenerate"] == []
    assert boucle["needs_verification"] == ["s1"]
    assert boucle["next_stage"] == "VERIFY"
    # Les confondre ferait régénérer sans fin sur une machine sans mesure.
    assert "sans fin" in boucle["note"]


def test_tout_conforme_mene_a_la_finalisation():
    plans = [ShotVerification(shot_id="s1", dimensions=(_mesuree(),))]
    assert quality_loop(plans)["next_stage"] == "FINALIZE"


# --------------------------------------------------------------------------
# La foule
# --------------------------------------------------------------------------


def test_une_population_non_declaree_est_refusee():
    with pytest.raises(CrowdRefused) as erreur:
        Population(population_id="p", kind="dragon")
    assert "trajectoire" in str(erreur.value)


def test_une_densite_numerique_est_refusee():
    with pytest.raises(CrowdRefused) as erreur:
        Population(population_id="p", kind="pedestrian", density="0.73")
    assert "densité 0.73" in str(erreur.value)


def test_une_population_ne_monte_pas_au_dessus_de_l_arriere_plan():
    with pytest.raises(CrowdRefused) as erreur:
        Population(population_id="p", kind="pedestrian", fidelity=HERO)
    # Une population qui mérite mieux n'est plus une population.
    assert "elle a un nom" in str(erreur.value)
    assert Population(population_id="p", kind="pedestrian",
                      fidelity=ARRIERE_PLAN).fidelity == ARRIERE_PLAN


def test_les_individus_d_une_foule_ne_sont_pas_nommes():
    population = Population(population_id="p", kind="pedestrian")
    assert population.as_dict()["individuals_named"] is False


def test_la_promotion_en_entite_est_explicite_et_dit_son_coût():
    population = Population(population_id="p", kind="pedestrian")
    promotion = promote_to_entity(population, "e-vendeur")
    assert promotion["entity_id"] == "e-vendeur"
    assert "une vérification d'identité" in promotion["gains"]
    assert "budget d'une entité" in promotion["costs"]


def test_un_mouvement_d_ambiance_non_declare_est_refuse():
    with pytest.raises(CrowdRefused):
        AmbientMotion(kind="magie")
    assert AmbientMotion(kind="wind", intensity=0.4).intensity == 0.4


def test_le_budget_est_relatif_et_ne_pretend_pas_etre_un_cout():
    monde = WorldState(environment="rue")
    monde.place(EntityState(entity_id="e1", entity_type="human", fidelity=HERO))
    populations = [Population(population_id="p1", kind="pedestrian"),
                   Population(population_id="p2", kind="vehicle")]

    resultat = budget(monde, populations)
    assert resultat["cost_estimate"] is None
    assert resultat["relative_share"][HERO] > resultat["relative_share"][FOULE]
    assert "chronométrées" in resultat["note"]


def test_les_rapports_nomment_ce_qu_ils_refusent():
    refus_verification = " ".join(verification_report()["does_not"]).lower()
    assert "composite" in refus_verification
    assert "0.0" in refus_verification

    refus_foule = " ".join(crowd_report()["does_not"]).lower()
    assert "nommer les individus" in refus_foule
    assert "premier rôle" in refus_foule
