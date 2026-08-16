"""
Où l'image change — calculé sur les trames, jamais proposé par un modèle
(VOLET M04 du moteur média).

C'est la directive §1 à son point le plus net. Un modèle à qui l'on demande
« où sont les changements de plan ? » répond par des horodatages, tout de suite
et avec aplomb, et ils sont inventés. Une frontière de plan est une **mesure** :
deux trames consécutives diffèrent ou non, et l'écart se recalcule.

Le second piège est `importance_score`. Il est dangereux parce qu'il est facile
à produire : un `0.5` par défaut, ou un flottant demandé à un modèle, et un
nombre apparaît qui se lit comme une mesure. Le montage automatique trie dessus
et coupe le bas du classement. Un réalisateur demande alors pourquoi sa
meilleure prise a sauté, et la réponse honnête est : parce qu'une valeur par
défaut l'a classée dernière.

Ce que ces tests gardent :

1. **Une frontière est mesurée**, et vérifiée sur de vraies trames.
2. **Pas de temps sans cadence mesurée.**
3. **Le seuil est déclaré et rendu** avec les distances brutes.
4. **Une importance sans signal mesuré n'existe pas.**
5. **Un signal absent ne contribue pas** — il ne vaut pas zéro.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.analysis.scene_model import (  # noqa: E402
    ABSENT,
    DERIVE_IA,
    MESURE,
    SIGNAUX_IMPORTANCE,
    Scene,
    SceneRefused,
    describe,
    importance,
    scene_report,
    scenes_from_shots,
)
from src.media.analysis.scenes import (  # noqa: E402
    SEUIL_COUPURE,
    SceneDetectionRefused,
    detect_cuts,
    frame_distances,
    load_frames,
    scene_detection_report,
)


def _plan(couleur, nombre=6, grain=3, graine=0):
    """Des trames d'un même plan : une couleur, un léger grain de compression."""
    rng = np.random.default_rng(graine)
    return [
        np.clip(
            np.full((60, 80, 3), couleur, dtype=np.int16)
            + rng.integers(-grain, grain, (60, 80, 3)),
            0, 255,
        ).astype(np.uint8)
        for _ in range(nombre)
    ]


@pytest.fixture
def trois_plans():
    """Trois plans nettement différents, 18 trames."""
    return _plan((20, 30, 200)) + _plan((200, 180, 40)) + _plan((10, 150, 60))


# ----------------------------------------------------------------------
# 1. Une frontière est mesurée
# ----------------------------------------------------------------------

def test_les_coupures_sont_trouvees_sur_de_vraies_trames(trois_plans):
    """Trois plans de six trames : les frontières tombent à 6 et 12."""
    resultat = detect_cuts(trois_plans)

    assert resultat["boundaries"] == [6, 12]
    assert [(p["start"], p["end"]) for p in resultat["shots"]] == \
        [(0, 6), (6, 12), (12, 18)]


def test_le_grain_de_compression_ne_declenche_pas_de_coupure(trois_plans):
    """Sinon chaque trame serait un plan, et le découpage ne dirait rien."""
    distances = frame_distances(trois_plans)

    dans_un_plan = [d for i, d in enumerate(distances) if i not in (5, 11)]
    assert max(dans_un_plan) < SEUIL_COUPURE
    assert min(distances[5], distances[11]) > SEUIL_COUPURE


def test_une_video_sans_coupure_est_un_plan_pas_zero():
    """Zéro plan laisserait croire qu'il n'y a rien à monter."""
    resultat = detect_cuts(_plan((30, 30, 30), nombre=10))

    assert resultat["boundaries"] == []
    assert len(resultat["shots"]) == 1
    assert resultat["shots"][0]["frames"] == 10


def test_deux_coupures_trop_rapprochees_ne_font_pas_deux_plans():
    """Un scintillement n'est pas un montage."""
    trames = _plan((10, 10, 10), nombre=4) + _plan((240, 240, 240), nombre=1) \
        + _plan((10, 10, 10), nombre=4)

    resultat = detect_cuts(trames, min_shot=3)

    assert len(resultat["boundaries"]) == 1


def test_une_seule_trame_ne_contient_aucune_transition():
    """Rendre une liste vide laisserait croire qu'on a cherché."""
    with pytest.raises(SceneDetectionRefused) as refus:
        frame_distances(_plan((10, 10, 10), nombre=1))

    assert "laisserait croire qu'on a cherché" in str(refus.value)


def test_une_trame_illisible_arrete_la_detection(tmp_path):
    """La sauter décalerait toutes les frontières suivantes en silence."""
    cassee = tmp_path / "cassee.png"
    cassee.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

    with pytest.raises(SceneDetectionRefused) as refus:
        load_frames([str(cassee)])

    assert "décalerait toutes les frontières" in str(refus.value)


# ----------------------------------------------------------------------
# 2. Pas de temps sans cadence mesurée
# ----------------------------------------------------------------------

def test_sans_cadence_aucun_temps_n_est_rendu(trois_plans):
    """
    Le piège central.

    Convertir avec une cadence supposée fabriquerait un horodatage habillé en
    mesure — et une coupe posée dessus tombe au milieu d'un mot.
    """
    resultat = detect_cuts(trois_plans)

    assert resultat["times"] is None
    assert resultat["times_available"] is False
    assert "habillé en mesure" in resultat["why_no_times"]


def test_avec_une_cadence_mesuree_les_temps_apparaissent(trois_plans):
    """Le cas nominal existe."""
    resultat = detect_cuts(trois_plans, fps=24.0)

    assert resultat["times"] == [0.25, 0.5]
    assert resultat["shot_times"][0] == {"start": 0.0, "end": 0.25}


def test_une_cadence_impossible_est_refusee(trois_plans):
    """Une cadence nulle ou négative ne convertit rien."""
    with pytest.raises(SceneDetectionRefused):
        detect_cuts(trois_plans, fps=0.0)


# ----------------------------------------------------------------------
# 3. Le seuil est déclaré et vérifiable
# ----------------------------------------------------------------------

def test_le_resultat_porte_son_seuil_et_ses_distances(trois_plans):
    """Un désaccord doit être vérifiable, pas une affaire d'opinion."""
    resultat = detect_cuts(trois_plans, threshold=0.6)

    assert resultat["threshold"] == 0.6
    assert len(resultat["distances"]) == len(trois_plans) - 1


def test_un_seuil_hors_intervalle_est_refuse(trois_plans):
    """Au-delà de 1, il ne déclencherait jamais — et personne ne le verrait."""
    with pytest.raises(SceneDetectionRefused) as refus:
        detect_cuts(trois_plans, threshold=1.5)

    assert "ne déclencherait jamais" in str(refus.value)


def test_le_rapport_refuse_de_rendre_une_confiance():
    """Remettre un écart à l'échelle inventerait une probabilité."""
    interdits = " ".join(scene_detection_report()["does_not"])

    assert "confiance" in interdits
    assert "sans cadence mesurée" in interdits


# ----------------------------------------------------------------------
# 4. Une importance sans signal n'existe pas
# ----------------------------------------------------------------------

def _scene(**extra):
    """Une scène de six trames."""
    champs = {"scene_id": "s1", "start_frame": 0, "end_frame": 6}
    champs.update(extra)
    return Scene(**champs)


def test_sans_aucun_signal_mesure_il_n_y_a_pas_de_score():
    """Un `0.5` par défaut se lit comme une mesure, et le montage trie dessus."""
    verdict = importance(_scene())

    assert verdict["score"] is None
    assert "trierait dessus" in verdict["reason"]
    assert set(verdict["missing_signals"]) == set(SIGNAUX_IMPORTANCE)


def test_un_seul_signal_mesure_suffit_a_composer():
    """Refuser tout tant que tout n'est pas mesuré serait aussi faux."""
    verdict = importance(_scene(), visual_change=0.8)

    assert verdict["score"] == 0.8
    assert verdict["used_signals"] == ["visual_change"]
    assert verdict["partial"] is True


def test_un_signal_absent_ne_contribue_pas():
    """
    Le compter pour zéro traiterait une absence comme une valeur basse.

    C'est exactement ainsi qu'une bonne scène finit mal classée : deux signaux
    manquants sur quatre plafonneraient mécaniquement son score.
    """
    partiel = importance(_scene(), visual_change=1.0, speech_ratio=1.0)

    assert partiel["score"] == 1.0
    assert set(partiel["missing_signals"]) == {"duration_share", "audio_quality"}


def test_le_score_est_renormalise_sur_les_signaux_presents():
    """Sinon l'absence de mesure serait punie au lieu d'être signalée."""
    complet = importance(_scene(audio_quality=0.5), visual_change=0.5,
                         speech_ratio=0.5, duration_share=0.5)

    assert complet["score"] == 0.5
    assert complet["partial"] is False
    assert sum(complet["contributions"].values()) == pytest.approx(0.5, abs=1e-3)


def test_les_poids_sont_declares_et_discutables():
    """Un poids implicite est un jugement que personne ne peut discuter."""
    verdict = importance(_scene(), visual_change=1.0, speech_ratio=0.0,
                         weights={"visual_change": 1.0, "speech_ratio": 3.0})

    assert verdict["score"] == 0.25
    assert verdict["weights"] == {"speech_ratio": 3.0, "visual_change": 1.0}


def test_un_signal_hors_intervalle_est_refuse():
    """Une part hors de [0, 1] n'est pas une part."""
    with pytest.raises(SceneRefused):
        importance(_scene(), visual_change=1.4)


# ----------------------------------------------------------------------
# 5. Mesuré et supposé ne se mélangent pas
# ----------------------------------------------------------------------

def test_les_bornes_en_trames_sont_mesurees(trois_plans):
    """Elles viennent du détecteur, pas d'un modèle."""
    scenes = scenes_from_shots(detect_cuts(trois_plans)["shots"])

    assert [s.scene_id for s in scenes] == ["scene-01", "scene-02", "scene-03"]
    assert scenes[0].origin_of("start_frame") == MESURE
    assert scenes[0].origin_of("start_time") == ABSENT


def test_une_description_de_modele_est_etiquetee_comme_telle(trois_plans):
    """Les fondre dans un bloc « analyse » détruit la distinction pour de bon."""
    scene = scenes_from_shots(detect_cuts(trois_plans)["shots"])[0]

    decrite = describe(scene, summary="Un plan large sur la ville",
                       tags=["ville", "extérieur"])

    assert decrite.origin_of("visual_summary") == DERIVE_IA
    assert decrite.origin_of("start_frame") == MESURE
    assert decrite.ai_derived_fields == ("semantic_tags", "visual_summary")


def test_decrire_ne_modifie_pas_la_scene_d_origine(trois_plans):
    """Une scène est figée : décrire produit une nouvelle scène."""
    scene = scenes_from_shots(detect_cuts(trois_plans)["shots"])[0]

    describe(scene, summary="Une description")

    assert scene.visual_summary is None


def test_une_duree_absente_n_est_pas_une_duree_nulle():
    """Les deux ne se traitent pas pareil."""
    sans_temps = _scene()
    avec_temps = _scene(start_time=0.0, end_time=0.25)

    assert sans_temps.duration is None
    assert avec_temps.duration == 0.25


def test_une_seule_borne_temporelle_est_refusee():
    """Une durée se calculerait sur une borne inventée."""
    with pytest.raises(SceneRefused) as refus:
        _scene(start_time=0.0)

    assert "borne inventée" in str(refus.value)


def test_une_scene_sans_trame_est_refusee():
    """Elle apparaîtrait dans un montage sans rien à montrer."""
    with pytest.raises(SceneRefused) as refus:
        Scene(scene_id="vide", start_frame=5, end_frame=5)

    assert "rien à montrer" in str(refus.value)


def test_le_rapport_refuse_le_score_par_defaut():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(scene_report()["does_not"])

    assert "score d'importance par défaut" in interdits
    assert "Demander une importance à un modèle" in interdits
