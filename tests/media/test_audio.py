"""
Un son posé sur un événement réel, et une musique dont les droits sont connus
(VOLET M10 du moteur média).

La directive §12 le dit sans détour : *les effets sonores doivent être placés
selon les événements réels de la timeline. Ne place pas de sons au hasard.*

« Au hasard » est généreux. Ce qui arrive vraiment est pire et a meilleure
allure : un système pose un riser « sur la révélation » en demandant à un modèle
où elle se trouve, reçoit 4,2 secondes avec aplomb, et dépose le son là. Il tombe
une demi-seconde avant la coupe — à chaque fois — et le montage sonne
vaguement faux d'une façon que personne ne sait nommer en relecture.

Et la §14 finit sur la phrase qui prime sur toutes les autres : *respecte les
métadonnées de licence et ne prétends jamais connaître un statut de droits
inconnu.* Se tromper sur les autres champs produit une vidéo qui sonne mal ; se
tromper sur celui-ci produit un retrait, une facture, ou un client qui ne peut
pas diffuser ce qu'il a payé.

Ce que ces tests gardent :

1. **Un son porte l'événement qui l'a causé**, et la source de son instant.
2. **Un événement sans famille reste sans son.**
3. **Les fenêtres d'atténuation qui se touchent sont fusionnées.**
4. **`UNKNOWN` bloque l'emploi d'un morceau.**
5. **Aucun BPM n'est estimé** : `None` n'est jamais 120.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.audio.music import (  # noqa: E402
    CHAMPS_ANALYSE,
    DROITS_CONNUS,
    DROITS_INCONNUS,
    DROITS_REFUSES,
    MusicRefused,
    MusicTrack,
    analyse_status,
    credits_for,
    music_report,
    require_rights,
    sync_to_scenes,
)
from src.media.audio.sound_design import (  # noqa: E402
    EVENEMENTS,
    FAMILLES,
    SoundRefused,
    TimelineEvent,
    duck_windows,
    families_for,
    loudness_status,
    place_sounds,
    sound_design_report,
)


def _libre(**extra):
    """Un morceau dont les droits ont été lus."""
    champs = {"track_id": "t1", "title": "Sabar", "rights": DROITS_CONNUS,
              "licence": "CC-BY-4.0", "source": "https://exemple/sabar.flac"}
    champs.update(extra)
    return MusicTrack(**champs)


# ----------------------------------------------------------------------
# 1. Un son est posé sur un événement
# ----------------------------------------------------------------------

def test_chaque_son_porte_l_evenement_et_la_source_de_son_instant():
    """
    Un instant demandé à un modèle tombe une demi-seconde avant la coupe.

    À chaque fois, et personne ne sait le nommer en relecture.
    """
    resultat = place_sounds([
        TimelineEvent(kind="cut", at=3.5, source="scene_boundary"),
        TimelineEvent(kind="highlight", at=7.0, source="edit_plan"),
    ])

    assert [c["event_kind"] for c in resultat["cues"]] == ["cut", "highlight"]
    assert resultat["cues"][0]["derived_from"] == "scene_boundary"
    assert resultat["cues"][1]["derived_from"] == "edit_plan"


def test_un_evenement_sans_source_est_refuse():
    """Un instant que personne ne peut vérifier est un instant inventé."""
    with pytest.raises(SoundRefused) as refus:
        TimelineEvent(kind="cut", at=3.5, source="  ")

    assert "tombe à côté de la coupe" in str(refus.value)


def test_un_evenement_non_declare_est_refuse():
    """Un son demandé pour un événement inconnu n'a pas de moment."""
    with pytest.raises(SoundRefused) as refus:
        TimelineEvent(kind="explosion_dramatique", at=1.0, source="x")

    assert "pas de place" in str(refus.value)


def test_un_riser_commence_avant_son_evenement():
    """Un son qui doit **arriver** sur l'événement démarre avant lui."""
    resultat = place_sounds(
        [TimelineEvent(kind="reveal", at=10.0, source="edit_plan")],
        choices={"reveal": "riser"},
    )

    cue = resultat["cues"][0]
    assert cue["at"] == 10.0 - FAMILLES["riser"]["lead_in_s"]
    assert cue["event_at"] == 10.0


def test_une_amorce_ne_produit_jamais_un_instant_negatif():
    """Un son qui démarrerait avant la vidéo ne serait jamais entendu."""
    resultat = place_sounds(
        [TimelineEvent(kind="reveal", at=0.3, source="edit_plan")],
        choices={"reveal": "riser"},
    )

    assert resultat["cues"][0]["at"] == 0.0


def test_les_sons_sont_rendus_dans_l_ordre_du_temps():
    """Un mixage se lit dans l'ordre où il s'entend."""
    resultat = place_sounds([
        TimelineEvent(kind="cut", at=9.0, source="s"),
        TimelineEvent(kind="cut", at=2.0, source="s"),
    ])

    assert [c["at"] for c in resultat["cues"]] == [2.0, 9.0]


# ----------------------------------------------------------------------
# 2. Un événement sans famille reste sans son
# ----------------------------------------------------------------------

def test_une_famille_qui_ne_sert_pas_l_evenement_est_refusee():
    """Rapprocher un « impact » d'un « marker » est une décision de montage."""
    resultat = place_sounds(
        [TimelineEvent(kind="highlight", at=4.0, source="s")],
        choices={"highlight": "impact"},
    )

    assert resultat["cues"] == []
    assert "ne sert pas" in resultat["events_without_sound"][0]["reason"]


def test_aucune_famille_voisine_n_est_proposee():
    """Le silence est une réponse ; une substitution n'en est pas une."""
    assert families_for("scene_start") == ["transition"]
    assert "impact" not in families_for("highlight")


def test_chaque_evenement_declare_est_servi_ou_nomme():
    """Un événement qui n'apparaît nulle part est un trou invisible."""
    evenements = [
        TimelineEvent(kind=nom, at=1.0 + rang, source="s")
        for rang, nom in enumerate(EVENEMENTS)
    ]

    resultat = place_sounds(evenements)

    traites = {c["event_kind"] for c in resultat["cues"]} | {
        e["event_kind"] for e in resultat["events_without_sound"]
    }
    assert traites == set(EVENEMENTS)


# ----------------------------------------------------------------------
# 3. L'atténuation sous la voix
# ----------------------------------------------------------------------

def test_la_musique_descend_sous_la_voix():
    """La seule partie du mixage réellement calculable sans décoder d'audio."""
    resultat = duck_windows([(2.0, 4.0)], music_start=0.0, music_end=10.0)

    fenetre = resultat["windows"][0]
    assert fenetre["start"] < 2.0 and fenetre["end"] > 4.0
    assert fenetre["gain_db"] < 0


def test_deux_regions_proches_sont_fusionnees():
    """
    Les laisser séparées ferait remonter la musique entre deux mots.

    Cela s'entend comme un pompage.
    """
    resultat = duck_windows([(2.0, 3.0), (3.1, 4.0)],
                            music_start=0.0, music_end=10.0)

    assert len(resultat["windows"]) == 1
    assert resultat["merged_from"] == 2


def test_deux_regions_eloignees_restent_separees():
    """Fusionner tout ferait taire la musique pendant tout le film."""
    resultat = duck_windows([(1.0, 2.0), (8.0, 9.0)],
                            music_start=0.0, music_end=10.0)

    assert len(resultat["windows"]) == 2


def test_l_attenuation_ne_deborde_pas_du_lit_musical():
    """Atténuer hors du morceau n'atténue rien et fausse le taux couvert."""
    resultat = duck_windows([(0.0, 20.0)], music_start=5.0, music_end=10.0)

    assert resultat["windows"][0]["start"] >= 5.0
    assert resultat["windows"][0]["end"] <= 10.0
    assert resultat["ducked_ratio"] == 1.0


def test_un_lit_musical_vide_est_refuse():
    """Il n'y a rien à atténuer."""
    with pytest.raises(SoundRefused):
        duck_windows([(1.0, 2.0)], music_start=5.0, music_end=5.0)


def test_aucune_sonie_n_est_estimee():
    """Une cible calculée sur une sonie non mesurée pousserait le mixage."""
    etat = loudness_status()

    assert etat["integrated_loudness_lufs"] is None
    assert etat["true_peak_dbfs"] is None
    if not etat["measurable"]:
        assert "n'est estimée" in etat["reason"]


# ----------------------------------------------------------------------
# 4. `UNKNOWN` bloque l'emploi
# ----------------------------------------------------------------------

def test_des_droits_inconnus_bloquent_l_emploi():
    """
    Un morceau dont personne n'a lu les termes n'est pas « probablement libre ».

    Le traiter comme utilisable est le moment où plus personne ne regarde.
    """
    inconnu = MusicTrack(track_id="t2", rights=DROITS_INCONNUS)

    with pytest.raises(MusicRefused) as refus:
        require_rights(inconnu)

    assert inconnu.usable is False
    assert "sortent du logiciel" in str(refus.value)


def test_des_droits_refuses_bloquent_aussi():
    """Une licence lue qui refuse l'usage est un refus, pas un avertissement."""
    with pytest.raises(MusicRefused):
        require_rights(MusicTrack(track_id="t3", rights=DROITS_REFUSES))


def test_libere_sans_licence_nommee_est_refuse():
    """L'écrire ainsi fait que personne ne regardera plus."""
    with pytest.raises(MusicRefused) as refus:
        MusicTrack(track_id="t4", rights=DROITS_CONNUS, licence="")

    assert "personne ne regardera plus" in str(refus.value)


def test_un_morceau_libere_est_employable():
    """Le cas nominal existe."""
    require_rights(_libre())

    assert _libre().usable is True


def test_une_mention_exigee_oubliee_est_une_violation():
    """Aussi sûrement qu'un emploi sans droits."""
    resultat = credits_for([
        _libre(attribution_required=True),
        MusicTrack(track_id="t5", rights=DROITS_INCONNUS),
    ])

    assert resultat["credits"][0]["licence"] == "CC-BY-4.0"
    assert resultat["blocked_tracks"][0]["track_id"] == "t5"
    assert resultat["complete"] is False


# ----------------------------------------------------------------------
# 5. Aucun BPM n'est estimé
# ----------------------------------------------------------------------

def test_un_bpm_non_mesure_vaut_none_pas_cent_vingt():
    """Un tempo supposé met chaque coupe légèrement à côté du temps."""
    piste = _libre()

    assert piste.get("bpm") is None
    assert set(piste.unmeasured_fields) == set(CHAMPS_ANALYSE)


def test_l_analyse_dit_pourquoi_elle_n_a_pas_eu_lieu():
    """« Non mesuré » sans raison laisse chercher au hasard."""
    etat = analyse_status(_libre())

    if not etat["measurable"]:
        assert "audio_decode" in etat["reason"]
        assert "par défaut" in etat["reason"]


def test_la_synchronisation_sur_les_scenes_ne_demande_pas_le_tempo():
    """Elle ne demande que des instants de scène mesurés (VOLET M04)."""
    resultat = sync_to_scenes(_libre(), scene_times=[0.0, 4.2, 9.8])

    assert [p["at"] for p in resultat["sync_points"]] == [0.0, 4.2, 9.8]
    assert all(p["derived_from"] == "scene_boundary"
               for p in resultat["sync_points"])


def test_l_alignement_sur_le_tempo_est_refuse_sans_bpm_mesure():
    """Il s'entend sans qu'on sache le nommer."""
    resultat = sync_to_scenes(_libre(), scene_times=[1.0])

    assert resultat["beat_aligned"] is False
    assert resultat["bpm"] is None
    assert "supposé" in resultat["beat_alignment_reason"]


def test_l_alignement_sur_le_tempo_devient_possible_avec_un_bpm_mesure():
    """La raison doit disparaître quand la mesure existe."""
    piste = _libre(measured={"bpm": 96.0})

    resultat = sync_to_scenes(piste, scene_times=[1.0])

    assert resultat["bpm"] == 96.0
    assert "possible" in resultat["beat_alignment_reason"]


def test_sans_instant_de_scene_aucun_rythme_n_est_fabrique():
    """Des points réguliers fabriqueraient un rythme que la vidéo n'a pas."""
    with pytest.raises(MusicRefused) as refus:
        sync_to_scenes(_libre(), scene_times=[])

    assert "rythme que la vidéo n'a pas" in str(refus.value)


def test_synchroniser_exige_les_droits_avant_tout():
    """L'ordre compte : on ne calcule pas sur un morceau qu'on ne peut employer."""
    with pytest.raises(MusicRefused):
        sync_to_scenes(MusicTrack(track_id="t6"), scene_times=[1.0])


# ----------------------------------------------------------------------
# 6. Ce que le volet refuse
# ----------------------------------------------------------------------

def test_le_rapport_sonore_refuse_le_placement_sans_evenement():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(sound_design_report()["does_not"])

    assert "sans événement de timeline" in interdits
    assert "Demander un instant à un modèle" in interdits
    assert "Estimer une sonie" in interdits


def test_le_rapport_musical_refuse_les_droits_inconnus():
    """C'est la phrase de la directive §14 qui prime sur toutes les autres."""
    rapport = music_report()

    interdits = " ".join(rapport["does_not"])
    assert "droits sont inconnus" in interdits
    assert "tempo supposé" in interdits
    assert set(rapport["analysis_fields"]) == set(CHAMPS_ANALYSE)
