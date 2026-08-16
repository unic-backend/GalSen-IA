"""
Quand chaque mot a été dit — et l'interpolation qui ne doit jamais arriver
(VOLET M05 du moteur média).

La directive §5 interdit de couper au milieu d'un mot. Pour obéir, il faut des
frontières de mots, et elles viennent du transcripteur ou elles n'existent pas.

Le raccourci est le plus tentant de tout le moteur : un transcripteur rend des
segments — « il faut comparer deux fractions », 4,10 s → 6,30 s — dont les mots
sont connus mais pas les temps individuels. Une ligne d'arithmétique répartit
2,2 secondes sur cinq mots et on appelle ça des temps de mot.

C'est faux exactement là où ça compte. La parole n'est pas uniforme : un
locuteur marque, insiste, hésite. Une frontière interpolée tombe **dans** un mot
aussi souvent qu'entre deux, donc la coupe qui s'y appuie enlève une demi-
syllabe. L'auditeur l'entend tout de suite ; l'ingénieur qui relit le code voit
des horodatages qui ont l'air mesurés.

Ce que ces tests gardent :

1. **Aucune interpolation en silence** — sans temps mesurés, la liste est vide.
2. **Une estimation demandée reste `ESTIMATED`** et est refusée pour couper.
3. **Une coupe est déplacée vers un silence**, jamais posée dans un mot.
4. **Sans transcripteur, le fichier est refusé à voix haute.**
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.transcription.words import (  # noqa: E402
    ESTIME,
    MESURE,
    WordTiming,
    WordTimingUnavailable,
    safe_cut_points,
    snap_to_word_boundary,
    transcribe_media,
    word_timing_report,
    words_from_segments,
)

#: Un segment dont le transcripteur a donné les temps par mot.
AVEC_MOTS = [{
    "text": "il faut comparer", "start": 4.0, "end": 5.2,
    "words": [
        {"word": "il", "start": 4.0, "end": 4.15},
        {"word": "faut", "start": 4.30, "end": 4.60},
        {"word": "comparer", "start": 4.62, "end": 5.20},
    ],
}]

#: Le même, tel qu'un transcripteur sans horodatage par mot le rend.
SANS_MOTS = [{"text": "il faut comparer", "start": 4.0, "end": 5.2}]


# ----------------------------------------------------------------------
# 1. Aucune interpolation en silence
# ----------------------------------------------------------------------

def test_les_temps_mesures_sont_repris_tels_quels():
    """Le cas nominal : le transcripteur a fait le travail."""
    resultat = words_from_segments(AVEC_MOTS)

    assert resultat["all_measured"] is True
    assert [mot.word for mot in resultat["words"]] == ["il", "faut", "comparer"]
    assert resultat["words"][1].start == 4.30
    assert all(mot.source == MESURE for mot in resultat["words"])


def test_sans_temps_par_mot_rien_n_est_invente():
    """
    Le raccourci le plus tentant du moteur, fermé.

    Répartir la durée d'un segment produirait des frontières qui se lisent
    comme des mesures.
    """
    resultat = words_from_segments(SANS_MOTS)

    assert resultat["words"] == []
    assert resultat["segments_without_word_times"] == 1
    assert "se lisent comme des mesures" in resultat["reason"]


def test_l_estimation_existe_mais_doit_etre_demandee():
    """Une prévisualisation approximative est légitime — en le disant."""
    resultat = words_from_segments(SANS_MOTS, interpolate=True)

    assert len(resultat["words"]) == 3
    assert all(mot.source == ESTIME for mot in resultat["words"])
    assert resultat["all_measured"] is False
    assert resultat["interpolated"] is True


def test_un_melange_distingue_le_mesure_de_l_estime():
    """Les compter ensemble ferait passer l'estimé pour du mesuré."""
    resultat = words_from_segments(AVEC_MOTS + SANS_MOTS, interpolate=True)

    assert resultat["measured_count"] == 3
    assert resultat["estimated_count"] == 3
    assert resultat["all_measured"] is False


def test_un_mot_dont_la_fin_precede_le_debut_est_refuse():
    """Un intervalle inversé produirait une durée négative plus loin."""
    with pytest.raises(WordTimingUnavailable):
        WordTiming(word="x", start=2.0, end=1.0)


# ----------------------------------------------------------------------
# 2. Une estimation ne sert jamais à couper
# ----------------------------------------------------------------------

def test_couper_sur_des_temps_estimes_est_refuse():
    """
    Le point où l'engrenage se referme.

    Une coupe posée sur une frontière estimée enlève une demi-syllabe, et rien
    en aval ne distingue plus ce temps d'une mesure.
    """
    estimes = words_from_segments(SANS_MOTS, interpolate=True)["words"]

    with pytest.raises(WordTimingUnavailable) as refus:
        safe_cut_points(estimes)

    assert "demi-syllabe" in str(refus.value)


def test_un_seul_mot_estime_suffit_a_refuser():
    """Le mélange est le cas dangereux : il a l'air majoritairement mesuré."""
    melange = words_from_segments(AVEC_MOTS + SANS_MOTS, interpolate=True)["words"]

    with pytest.raises(WordTimingUnavailable):
        safe_cut_points(melange)


# ----------------------------------------------------------------------
# 3. Les points de coupe
# ----------------------------------------------------------------------

def test_les_points_de_coupe_tombent_au_milieu_des_silences():
    """Au milieu, pour laisser la même marge des deux côtés."""
    mots = words_from_segments(AVEC_MOTS)["words"]

    resultat = safe_cut_points(mots)

    assert resultat["cut_points"] == [4.225]
    assert resultat["gaps_too_short"] == 1


def test_un_silence_trop_court_n_est_pas_un_point_de_coupe():
    """Une coupe y rognerait une consonne."""
    mots = [
        WordTiming(word="a", start=0.0, end=1.0),
        WordTiming(word="b", start=1.01, end=2.0),
    ]

    resultat = safe_cut_points(mots, min_silence=0.1)

    assert resultat["cut_points"] == []
    assert resultat["gaps_too_short"] == 1


def test_un_seul_mot_n_offre_aucun_intervalle():
    """Rendre un point laisserait croire qu'un silence a été trouvé."""
    resultat = safe_cut_points([WordTiming(word="seul", start=0.0, end=1.0)])

    assert resultat["cut_points"] == []
    assert "aucun intervalle" in resultat["reason"]


def test_une_coupe_dans_un_mot_est_deplacee_et_le_dit():
    """
    Le partage de la directive §1, rendu exécutable.

    Le modèle décide *ce qui reste* ; ce module décide *où la coupe peut
    tomber*.
    """
    mots = words_from_segments(AVEC_MOTS)["words"]

    verdict = snap_to_word_boundary(4.9, mots)

    assert verdict["crossed_word"] == "comparer"
    assert verdict["cut_at"] == 4.225
    assert verdict["shift"] == -0.675


def test_une_coupe_deja_dans_un_silence_est_seulement_alignee():
    """Le cas nominal ne doit pas déplacer inutilement."""
    mots = words_from_segments(AVEC_MOTS)["words"]

    verdict = snap_to_word_boundary(4.22, mots)

    assert verdict["crossed_word"] is None
    assert verdict["cut_at"] == 4.225


def test_sans_point_sur_la_coupe_est_refusee_pas_repliee():
    """Se replier ferait exactement la coupe que la fonction empêche."""
    colles = [
        WordTiming(word="a", start=0.0, end=1.0),
        WordTiming(word="b", start=1.0, end=2.0),
    ]

    with pytest.raises(WordTimingUnavailable) as refus:
        snap_to_word_boundary(1.5, colles)

    assert "existe pour empêcher" in str(refus.value)


# ----------------------------------------------------------------------
# 4. Sans transcripteur, on le dit
# ----------------------------------------------------------------------

def test_sans_transcripteur_le_fichier_est_refuse(monkeypatch):
    """Une transcription vide se confondrait avec « la personne n'a rien dit »."""
    import src.multimodal.registry as registre

    monkeypatch.setattr(registre, "active_transcriber", lambda: None)

    with pytest.raises(WordTimingUnavailable) as refus:
        transcribe_media("/x/entretien.wav")

    assert "n'a rien dit" in str(refus.value)


def test_une_transcription_rend_ses_mots_mesures(monkeypatch):
    """Le chemin complet, sur un transcripteur injecté."""
    import src.multimodal.registry as registre

    class _Faux:
        provider_id = "faux"

        def transcribe(self, chemin, language=None):
            from src.multimodal.interfaces import TranscriptionResult
            return TranscriptionResult(
                text="il faut comparer", language="fr",
                segments=AVEC_MOTS, model_name="faux-1",
            )

    monkeypatch.setattr(registre, "active_transcriber", lambda: _Faux())

    resultat = transcribe_media("/x/entretien.wav")

    assert resultat["word_timings_measured"] is True
    assert len(resultat["words"]) == 3
    assert resultat["model"] == "faux-1"


def test_le_rapport_refuse_l_interpolation_silencieuse():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(word_timing_report()["does_not"])

    assert "Interpoler des temps de mot en silence" in interdits
    assert "frontière estimée" in interdits
    assert "comme un silence" in interdits
