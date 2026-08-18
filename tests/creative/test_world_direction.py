"""
Tests for WorldState, the memories, the director and the shot planner
(§14–§20, ADR-025/026).

The properties that matter are separations. World memory and character memory
stay apart so a set can be corrected without touching a person. Style stays out
of the world so continuity does not compare a documentary to a cartoon. Target
duration stays apart from measured duration so nobody invents a measurement.
And a shot names its own dependencies, which is the only reason one shot can be
redone without redoing the production.
"""

import pytest

from src.creative.direction import (
    A_REFAIRE,
    GENERE,
    PLANIFIE,
    DirectionRefused,
    DirectorSpec,
    Shot,
    ShotPlanner,
    allocate_effort,
    check_intent,
    direction_report,
)
from src.creative.world import (
    ABSENT,
    ARRIERE_PLAN,
    DECLARE,
    FOULE,
    HERO,
    CharacterMemory,
    EntityState,
    WorldFact,
    WorldMemory,
    WorldRefused,
    WorldState,
    world_report,
)


@pytest.fixture
def monde():
    """Un marché avec trois entités de fidélités différentes."""
    etat = WorldState(environment="marché de Sandaga")
    etat.place(EntityState(entity_id="e1", entity_type="human", fidelity=HERO))
    etat.place(EntityState(entity_id="e2", entity_type="human",
                           fidelity=ARRIERE_PLAN))
    etat.place(EntityState(entity_id="e3", entity_type="vehicle",
                           fidelity=FOULE))
    return etat


# --------------------------------------------------------------------------
# Le monde
# --------------------------------------------------------------------------


def test_une_fidelite_non_declaree_est_refusee():
    with pytest.raises(WorldRefused) as erreur:
        EntityState(entity_id="e", entity_type="human", fidelity="important")
    # Elle décide du budget, donc elle ne se devine pas.
    assert "budget" in str(erreur.value)


def test_une_position_absolue_est_refusee():
    with pytest.raises(WorldRefused) as erreur:
        EntityState(entity_id="e", entity_type="human", position=(1920.0, 0.5))
    assert "relatives" in str(erreur.value)


def test_un_fait_jamais_pose_rend_une_absence_declaree(monde):
    fait = monde.fact("weather")
    assert fait.origin == ABSENT
    # Un monde dont les trous ne sont pas nommés se lit comme un monde complet.
    assert "personne ne l'a établi" in fait.reason


def test_un_fait_absent_sans_raison_est_refuse():
    with pytest.raises(WorldRefused) as erreur:
        WorldFact(name="lighting", origin=ABSENT)
    assert "monde complet" in str(erreur.value)


def test_le_style_n_est_pas_dans_le_monde(monde):
    resume = monde.as_dict()
    assert "style" not in resume
    # Le même monde peut être photoréaliste ou animé.
    assert "§46" in resume["note"]


def test_les_entites_sont_rangees_par_fidelite(monde):
    resume = monde.as_dict()
    assert resume["by_fidelity"][HERO] == ["e1"]
    assert resume["by_fidelity"][FOULE] == ["e3"]
    assert resume["by_fidelity"]["SUPPORTING"] == []


def test_un_fait_pose_est_conserve_avec_son_origine(monde):
    monde.set_fact(WorldFact(name="time_of_day", value="matin",
                             origin=DECLARE, source="brief client"))
    assert monde.fact("time_of_day").value == "matin"
    assert monde.as_dict()["established_facts"] == ["time_of_day"]


# --------------------------------------------------------------------------
# Les deux mémoires, séparées
# --------------------------------------------------------------------------


def test_la_memoire_des_mondes_ne_retient_aucun_personnage(monde):
    memoire = WorldMemory()
    memoire.record(monde)
    rapport = memoire.report()
    assert rapport["holds_characters"] is False
    # Fusionner empêcherait de déplacer la boutique sans toucher au boutiquier.
    assert "boutiquier" in rapport["note"]


def test_un_decor_vu_une_fois_n_est_pas_encore_recurrent(monde):
    memoire = WorldMemory()
    memoire.record(monde)
    assert memoire.recurring() == []

    memoire.record(WorldState(environment="marché de Sandaga"))
    assert memoire.recurring() == [{"environment": "marché de Sandaga",
                                    "seen": 2}]


def test_une_memoire_de_personnage_conditionne_sans_garantir():
    memoire = CharacterMemory(entity_id="e1")
    memoire.remember(WorldFact(name="clothing", value="boubou bleu",
                               origin=DECLARE, source="brief"))
    memoire.link_reference("ref-123")
    memoire.relate("e2", "sœur")

    conditionnement = memoire.conditioning()
    # Aucune clé n'affirme que le résultat sera conforme.
    assert conditionnement["guarantees"] is None
    assert "ADR-026" in conditionnement["note"]
    assert conditionnement["references"] == ["ref-123"]


# --------------------------------------------------------------------------
# La réalisation
# --------------------------------------------------------------------------


def test_une_valeur_de_realisation_inventee_est_refusee():
    with pytest.raises(DirectionRefused) as erreur:
        DirectorSpec(shot_size="très_serré")
    # Une valeur inventée se comporte comme un adjectif : elle ne décide rien.
    assert "adjectif" in str(erreur.value)


def test_chaque_axe_de_realisation_est_declare():
    for champ, valeur in (("camera_height", "en_hauteur"),
                          ("movement", "flottant"),
                          ("lighting", "joli"),
                          ("transition_in", "magique")):
        with pytest.raises(DirectionRefused):
            DirectorSpec(shot_size="wide", **{champ: valeur})


def test_une_instruction_structuree_est_acceptee_et_relisible():
    spec = DirectorSpec(shot_size="medium_close_up", camera_height="eye_level",
                        movement="dolly_in", lens_mm=50,
                        depth_of_field="shallow", lighting="soft_key")
    resume = spec.as_dict()
    # Chaque champ se remplace seul, sans toucher aux autres.
    assert resume["lens_mm"] == 50
    assert resume["depth_of_field"] == "shallow"


def test_les_adjectifs_d_ambiance_sont_releves_et_non_supprimes():
    resultat = check_intent("Un plan cinematic, beautiful et dramatic")
    assert resultat["mood_adjectives"] == ["beautiful", "cinematic", "dramatic"]
    assert resultat["decides_nothing"] is True
    # Le texte reste tel quel : le supprimer laisserait croire à une décision.
    assert "cinematic" in resultat["intent"]


def test_une_intention_concrete_ne_declenche_aucun_releve():
    resultat = check_intent("Montrer la main du vendeur qui pèse le mil")
    assert resultat["mood_adjectives"] == []
    assert resultat["decides_nothing"] is False


# --------------------------------------------------------------------------
# Le plan de tournage
# --------------------------------------------------------------------------


def test_un_plan_nomme_ses_dependances(monde):
    planificateur = ShotPlanner(monde)
    plan = planificateur.add(DirectorSpec(shot_size="wide"),
                             entity_ids=["e1", "e2"],
                             reference_ids=["ref-1"],
                             audio_segment_ids=["s1"],
                             target_duration=6.0)
    resume = plan.as_dict()
    assert resume["world_id"] == monde.world_id
    assert resume["entity_ids"] == ["e1", "e2"]
    assert resume["reference_ids"] == ["ref-1"]
    assert resume["audio_segment_ids"] == ["s1"]


def test_un_plan_sans_monde_est_refuse():
    with pytest.raises(DirectionRefused) as erreur:
        Shot(shot_id="s", index=1, world_id="",
             director=DirectorSpec(shot_size="wide"))
    assert "hérité en silence" in str(erreur.value)


def test_un_plan_citant_une_entite_absente_est_refuse(monde):
    planificateur = ShotPlanner(monde)
    with pytest.raises(DirectionRefused) as erreur:
        planificateur.add(DirectorSpec(shot_size="wide"),
                          entity_ids=["fantome"])
    assert "ne les contient pas" in str(erreur.value)


def test_duree_visee_et_duree_constatee_restent_deux_champs(monde):
    planificateur = ShotPlanner(monde)
    plan = planificateur.add(DirectorSpec(shot_size="wide"),
                             target_duration=6.0)
    assert plan.duration_gap is None  # rien n'a encore été mesuré

    planificateur.mark_generated(plan.shot_id, measured_duration=6.4)
    assert plan.target_duration == 6.0
    assert plan.measured_duration == 6.4
    assert plan.duration_gap == 0.4


def test_un_plan_genere_sans_mesure_reste_sans_mesure(monde):
    planificateur = ShotPlanner(monde)
    plan = planificateur.add(DirectorSpec(shot_size="wide"),
                             target_duration=6.0)
    planificateur.mark_generated(plan.shot_id)
    assert plan.state == GENERE
    # La durée visée n'est jamais recopiée dans la durée constatée.
    assert plan.measured_duration is None
    assert plan.duration_gap is None


def test_le_total_mesure_n_est_jamais_complete_par_le_total_vise(monde):
    planificateur = ShotPlanner(monde)
    premier = planificateur.add(DirectorSpec(shot_size="wide"),
                                target_duration=6.0)
    planificateur.add(DirectorSpec(shot_size="close_up"), target_duration=3.0)
    planificateur.mark_generated(premier.shot_id, measured_duration=6.4)

    rapport = planificateur.report()
    assert rapport["target_duration_total"] == 9.0
    assert rapport["measured_duration_total"] == 6.4
    assert len(rapport["shots_without_measurement"]) == 1


def test_refaire_un_plan_ne_touche_aucun_autre(monde):
    planificateur = ShotPlanner(monde)
    premier = planificateur.add(DirectorSpec(shot_size="wide"))
    second = planificateur.add(DirectorSpec(shot_size="close_up"),
                               entity_ids=["e1"], reference_ids=["ref-1"])

    demande = planificateur.mark_for_regeneration(second.shot_id, "cadrage")
    assert demande["affects_other_shots"] is False
    assert demande["requires"]["reference_ids"] == ["ref-1"]
    assert second.state == A_REFAIRE
    assert premier.state == PLANIFIE


def test_un_plan_inconnu_est_refuse(monde):
    with pytest.raises(DirectionRefused):
        ShotPlanner(monde).mark_generated("shot-jamais-vu")


def test_l_effort_est_relatif_et_ne_pretend_pas_etre_un_cout(monde):
    repartition = allocate_effort(monde)
    assert repartition["cost_estimate"] is None
    assert repartition["relative_share"][HERO] > repartition["relative_share"][FOULE]
    # Aucun calcul n'a tourné : rendre des minutes de GPU serait inventé.
    assert "chronométrées" in repartition["note"]


def test_les_rapports_nomment_ce_qu_ils_refusent():
    refus_monde = " ".join(world_report()["does_not"]).lower()
    assert "style" in refus_monde
    assert "mêler" in refus_monde

    refus_direction = " ".join(direction_report()["does_not"]).lower()
    assert "adjectif" in refus_direction
    assert "compléter une durée" in refus_direction
