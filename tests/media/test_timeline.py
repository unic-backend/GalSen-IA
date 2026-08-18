"""
Le modèle dit ce qui reste, la timeline dit où la coupe tombe
(VOLET M06 du moteur média).

La directive §5 pose le partage et la §1 dit pourquoi : *ne jamais laisser le
modèle inventer un horodatage qu'une analyse déterministe peut calculer.* Toute
implémentation approuve cette phrase, puis la casse au même endroit — en
définissant une interface où le modèle rend `{"start": 4.2, "end": 9.8}`. Dès
que cette forme existe, la règle n'est plus qu'un commentaire.

Ici la structure de sélection **n'a pas de champ temporel**. Un modèle ne peut
pas inventer ce qu'aucun objet ne peut porter.

Et la §21 ferme l'autre bout : un rendu terminé n'est pas un rendu vérifié. Tout
peut être correct en amont et produire une coupe qui enlève le mot « pas » —
l'encodeur rapporte un succès, le fichier se lit, la phrase dit le contraire.

Ce que ces tests gardent :

1. **Une sélection ne porte qu'une citation.**
2. **Correspondance exacte** : ni voisinage, ni choix entre deux occurrences.
3. **Les coupes tombent dans les silences.**
4. **Sans re-transcription, le verdict est `NOT_VERIFIED`**, jamais une réussite.
"""

import dataclasses
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.timeline.edit_plan import (  # noqa: E402
    AMBIGU,
    INTROUVABLE,
    LOCALISE,
    EditPlanRefused,
    Segment,
    Selection,
    build_plan,
    edit_plan_report,
    intended_transcript,
    locate_quote,
)
from src.media.timeline.verify import (  # noqa: E402
    CONFORME,
    DIVERGENT,
    NON_VERIFIE,
    VerificationRefused,
    boundary_losses,
    compare_transcripts,
    verification_report,
    verify_render,
)
from src.media.transcription.words import (  # noqa: E402
    WordTiming,
    WordTimingUnavailable,
    words_from_segments,
)

#: Une prise réelle : une hésitation, la thèse, une reprise de la même phrase.
PRISE = [
    ("Alors", 0.0, 0.4), ("euh", 0.5, 0.7),
    ("il", 1.2, 1.35), ("faut", 1.4, 1.7), ("comparer", 1.75, 2.4),
    ("deux", 2.5, 2.7), ("fractions", 2.75, 3.4),
    ("voila", 3.9, 4.3),
    ("il", 5.0, 5.15), ("faut", 5.2, 5.5), ("comparer", 5.55, 6.2),
]


@pytest.fixture
def mots():
    """Les mots de la prise, avec des temps mesurés."""
    return [WordTiming(word=m, start=a, end=b) for m, a, b in PRISE]


# ----------------------------------------------------------------------
# 1. Une sélection ne peut pas porter de temps
# ----------------------------------------------------------------------

def test_une_selection_n_a_aucun_champ_temporel():
    """
    Le mécanisme entier du module.

    Dès qu'un champ `start` existe, un modèle le remplit — avec aplomb — et
    personne en aval ne distingue un 4.2 inventé d'un 4.2 mesuré.
    """
    champs = {champ.name for champ in dataclasses.fields(Selection)}

    assert champs == {"quote", "reason"}
    assert not {"start", "end", "time", "timestamp", "duration"} & champs


def test_une_selection_vide_est_refusee():
    """Un extrait sans mots produirait un segment de durée arbitraire."""
    with pytest.raises(EditPlanRefused) as refus:
        Selection(quote="   ")

    assert "ne désigne rien" in str(refus.value)


# ----------------------------------------------------------------------
# 2. Correspondance exacte, jamais approchée
# ----------------------------------------------------------------------

def test_une_citation_unique_est_localisee(mots):
    """Le cas nominal existe."""
    resultat = locate_quote("il faut comparer deux fractions", mots)

    assert resultat["status"] == LOCALISE
    assert (resultat["first_word"], resultat["last_word"]) == (2, 6)


def test_la_casse_et_la_ponctuation_ne_font_pas_echouer(mots):
    """Un modèle cite avec une majuscule et un point ; ce n'est pas une erreur."""
    assert locate_quote("Il faut comparer, deux fractions.", mots)["status"] == \
        LOCALISE


def test_une_citation_qui_apparait_deux_fois_est_ambigue(mots):
    """
    Prendre la première garderait en silence une autre prise que celle relue.

    C'est le défaut de « mauvaise prise » que la directive §5 demande de
    détecter — fabriqué par le monteur lui-même.
    """
    resultat = locate_quote("il faut comparer", mots)

    assert resultat["status"] == AMBIGU
    assert resultat["occurrences"] == [2, 8]
    assert "relue" in resultat["reason"]


def test_une_citation_jamais_dite_est_rapportee(mots):
    """Le modèle a halluciné une phrase : c'est ce qu'il faut faire remonter."""
    resultat = locate_quote("bonjour tout le monde", mots)

    assert resultat["status"] == INTROUVABLE
    assert "jamais été dite" in resultat["reason"]


def test_un_pluriel_ne_vaut_pas_un_singulier(mots):
    """Rendre « fraction » et « fractions » identiques garderait un autre mot."""
    assert locate_quote("deux fraction", mots)["status"] == INTROUVABLE


def test_une_citation_refusee_n_entre_pas_dans_le_plan(mots):
    """Elle est listée avec sa raison, pas approximée."""
    plan = build_plan([
        Selection(quote="il faut comparer deux fractions"),
        Selection(quote="il faut comparer"),
        Selection(quote="phrase inventee"),
    ], mots)

    assert len(plan["segments"]) == 1
    assert {refus["status"] for refus in plan["refused"]} == {AMBIGU, INTROUVABLE}


# ----------------------------------------------------------------------
# 3. Les coupes tombent dans les silences
# ----------------------------------------------------------------------

def test_les_bornes_tombent_dans_le_silence_pas_sur_un_mot(mots):
    """La coupe se place entre « euh » et « il », puis après « fractions »."""
    plan = build_plan([Selection(quote="il faut comparer deux fractions")], mots)
    segment = plan["segments"][0]

    assert 0.7 < segment["start"] < 1.2
    assert 3.4 < segment["end"] < 3.9


def test_la_marge_est_bornee(mots):
    """
    Un silence long ne doit pas ramasser le mot d'à côté.

    « voila » finit à 4,3 et le mot suivant commence à 5,0 : la moitié du
    silence vaut 0,35, la marge la ramène à 0,1. Comparé avec `approx` — sur
    des flottants, `4.3 + 0.1` vaut 4,399999…, et un test qui échoue là-dessus
    parle de binaire, pas de montage.
    """
    plan = build_plan([Selection(quote="voila")], mots, margin=0.1)
    segment = plan["segments"][0]

    assert segment["start"] == pytest.approx(3.8, abs=1e-6)
    assert segment["end"] == pytest.approx(4.4, abs=1e-6)


def test_un_extrait_en_bord_de_prise_ne_deborde_pas(mots):
    """Il n'y a pas de silence avant le premier mot."""
    plan = build_plan([Selection(quote="Alors")], mots)

    assert plan["segments"][0]["start"] == 0.0


def test_un_bord_dans_un_silence_trop_court_est_signale_avant_le_rendu(mots):
    """
    Le défaut trouvé en relisant : `min_silence` traversait le calcul sans rien
    décider.

    « faut » finit à 1,7 et « comparer » commence à 1,75 : l'extrait « comparer
    deux fractions » n'a que 0,05 s de silence avant lui. Ce bord-là rogne une
    consonne, et le retrouver après coup dans la transcription du fichier fini
    coûte un rendu entier.

    La citation est choisie **unique** à dessein : « faut comparer » aurait été
    refusée comme ambiguë avant même d'atteindre le calcul des bornes.
    """
    plan = build_plan([Selection(quote="comparer deux fractions")], mots,
                      min_silence=0.08)

    assert plan["tight_boundaries"]
    assert plan["tight_boundaries"][0]["edges"] == ["start"]
    assert "rogne une consonne" in plan["tight_boundaries"][0]["reason"]


def test_un_extrait_entoure_de_vrais_silences_n_est_pas_signale(mots):
    """Le signal doit disparaître quand sa raison disparaît."""
    plan = build_plan([Selection(quote="voila")], mots, min_silence=0.08)

    assert plan["tight_boundaries"] == []


def test_les_segments_sont_remis_dans_l_ordre_de_la_source(mots):
    """Monter dans l'ordre des citations produirait un discours réarrangé."""
    plan = build_plan([
        Selection(quote="voila"),
        Selection(quote="Alors euh"),
    ], mots)

    assert [s["quote"] for s in plan["segments"]] == ["Alors euh", "voila"]


def test_deux_extraits_qui_se_recouvrent_sont_rapportes(mots):
    """Les fondre effacerait la question au lieu de la poser."""
    plan = build_plan([
        Selection(quote="il faut comparer deux fractions"),
        Selection(quote="comparer deux"),
    ], mots)

    assert plan["overlaps"]
    assert "fusionnés" in plan["overlaps"][0]["reason"]


def test_monter_sur_des_temps_estimes_est_refuse():
    """Les coupes seraient indistinguables de coupes mesurées."""
    estimes = words_from_segments(
        [{"text": "il faut comparer", "start": 0.0, "end": 1.2}],
        interpolate=True,
    )["words"]

    with pytest.raises(WordTimingUnavailable):
        build_plan([Selection(quote="il faut")], estimes)


def test_monter_sans_aucun_mot_est_refuse():
    """Un montage calculé là le serait sur du vide."""
    with pytest.raises(EditPlanRefused) as refus:
        build_plan([Selection(quote="x")], [])

    assert "sur du vide" in str(refus.value)


# ----------------------------------------------------------------------
# 4. Un rendu terminé n'est pas un rendu vérifié
# ----------------------------------------------------------------------

def test_sans_re_transcription_le_verdict_est_non_verifie(mots):
    """
    Le cœur de la directive §21.

    Une coupe qui enlève le mot « pas » produit un fichier qui s'encode, se
    lit, et dit le contraire de ce qui a été dit.
    """
    plan = build_plan([Selection(quote="il faut comparer deux fractions")], mots)

    verdict = verify_render(intended_transcript(plan), final_transcript=None)

    assert verdict["verdict"] == NON_VERIFIE
    assert "s'encode, se lit" in verdict["reason"]


def test_un_rendu_conforme_est_declare_conforme(mots):
    """Le cas nominal existe."""
    plan = build_plan([Selection(quote="il faut comparer deux fractions")], mots)
    prevu = intended_transcript(plan)

    verdict = verify_render(prevu, final_transcript=prevu)

    assert verdict["verdict"] == CONFORME
    assert verdict["retention"] == 1.0


def test_un_mot_manquant_fait_diverger(mots):
    """C'est exactement le cas que la directive §5 demande d'attraper."""
    plan = build_plan([Selection(quote="il faut comparer deux fractions")], mots)

    verdict = verify_render(intended_transcript(plan),
                            final_transcript="il faut comparer deux")

    assert verdict["verdict"] == DIVERGENT
    assert [perte["word"] for perte in verdict["missing"]] == ["fractions"]


def test_un_mot_duplique_est_detecte():
    """Un extrait collé deux fois ne se voit pas au seul décompte des manquants."""
    verdict = verify_render("il faut comparer",
                            final_transcript="il faut faut comparer")

    assert verdict["verdict"] == DIVERGENT
    assert verdict["duplicated"][0]["word"] == "faut"


def test_une_tolerance_par_defaut_stricte():
    """Tolérer une perte normaliserait la faute que ce contrôle cherche."""
    verdict = verify_render("un deux trois quatre",
                            final_transcript="un deux trois")

    assert verdict["tolerance"] == 1.0
    assert verdict["verdict"] == DIVERGENT


def test_comparer_a_un_texte_vide_est_refuse():
    """Le résultat dépendrait du sens de lecture, donc n'est pas une mesure."""
    with pytest.raises(VerificationRefused):
        compare_transcripts("", "quelque chose")


def test_une_perte_au_bord_est_distinguee_d_une_perte_au_milieu(mots):
    """Les deux ne se corrigent pas pareil."""
    plan = build_plan([Selection(quote="il faut comparer deux fractions")], mots)
    comparaison = compare_transcripts(intended_transcript(plan),
                                      "faut comparer deux fractions")

    bords = boundary_losses(plan, comparaison)

    assert [perte["word"] for perte in bords] == ["il"]
    assert "trop serrée" in bords[0]["reason"]


def test_ce_qui_est_hors_de_portee_est_nomme():
    """Une liste qui ne montre que le détectable se lit comme complète."""
    verdict = verify_render("un deux", final_transcript="un deux")

    assert "identical_mishearing" in verdict["out_of_scope"]
    assert "prosody" in verdict["out_of_scope"]


# ----------------------------------------------------------------------
# 5. Ce que le montage refuse
# ----------------------------------------------------------------------

def test_le_rapport_refuse_l_horodatage_venu_d_un_modele():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(edit_plan_report()["does_not"])

    assert "horodatage venant d'un modèle" in interdits
    assert "suite de mots voisine" in interdits
    assert "deux occurrences identiques" in interdits


def test_le_rapport_de_verification_refuse_de_certifier_sans_ecouter():
    """« Vérifié » sans contrôle fabrique de la confiance à partir d'une absence."""
    interdits = " ".join(verification_report()["does_not"])

    assert "n'a pas été ré-écouté" in interdits
    assert "modèle de juger la conformité" in interdits


def test_un_segment_connait_sa_duree():
    """Elle sert au budget de la production, donc elle doit être exacte."""
    segment = Segment(start=1.0, end=3.5, first_word=0, last_word=2,
                      words=("a", "b", "c"))

    assert segment.duration == 2.5
