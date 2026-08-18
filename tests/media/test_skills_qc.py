"""
Des règles promues par quelqu'un, et un contrôle qui refuse de se croire complet
(VOLETs M13 et M14 du moteur média).

La directive §17 dit : *les corrections peuvent devenir des skills candidats,
mais NE DOIVENT PAS devenir une vérité permanente sans validation.* Le défaut
qu'elle vise est silencieux : un client demande des sous-titres plus grands un
mardi ; le système, serviable, retient la préférence ; trois mois plus tard un
autre client sur un autre continent reçoit des sous-titres plus grands, et
personne ne sait dire pourquoi — la règle n'a ni auteur, ni date, ni motif, donc
personne ne peut la contester non plus.

La §21 ferme l'autre bout : un rendu terminé n'est pas une production réussie.
Cette distinction ne survit que si un contrôle qui n'a pas pu tourner est
impossible à confondre avec un contrôle qui est passé. « 12 contrôles passés »
quand quatre n'ont jamais tourné produit un rapport vert qu'un humain croit au
lieu de regarder la vidéo.

Ce que ces tests gardent :

1. **Une candidate ne s'applique pas.**
2. **La promotion exige un validateur nommé qui n'est pas la plateforme.**
3. **Une règle de projet ne sort pas de son projet.**
4. **`NOT_CHECKED` n'est jamais compté comme `PASS`.**
5. **`PRODUCTION_SUCCESS` exige que rien ne soit resté non vérifié.**
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.assets.registry import Asset  # noqa: E402
from src.media.core.project import ORIGINE_SOURCEE  # noqa: E402
from src.media.qc.checks import (  # noqa: E402
    ECHOUE,
    FAMILLES,
    NON_VERIFIE,
    PASSE,
    PRODUCTION_ECHOUEE,
    PRODUCTION_INCOMPLETE,
    PRODUCTION_REUSSIE,
    check_audio,
    check_black_frames,
    check_content,
    check_file,
    check_frames,
    check_subtitles,
    qc_report,
    verdict,
)
from src.media.skills.registry import (  # noqa: E402
    PORTEE_GLOBALE,
    PORTEE_PROJET,
    SkillRefused,
    SkillRegistry,
    is_platform_identity,
    skill_report,
)
from src.media.subtitles.cues import Cue  # noqa: E402


@pytest.fixture
def registre():
    """Un registre de styles avec une candidate en attente."""
    depot = SkillRegistry()
    depot.suggest("documentaire", "subtitles",
                  "Sous-titres à 32 px minimum",
                  evidence=["correction du 2026-08-04"], project_id="prj-1")
    return depot


def _candidate(depot, skill_id="documentaire"):
    """La première candidate d'un style."""
    return depot.get(skill_id).candidates[0]


# ----------------------------------------------------------------------
# 1. Une candidate ne s'applique pas
# ----------------------------------------------------------------------

def test_une_correction_devient_candidate_pas_regle(registre):
    """
    Le défaut visé est silencieux.

    Sans auteur, sans date et sans motif, une telle règle ne peut pas être
    contestée non plus.
    """
    style = registre.get("documentaire")

    assert len(style.candidates) == 1
    assert style.rules == []
    assert style.rules_for("subtitles", project_id="prj-1") == []


def test_une_candidate_est_visible_et_denombrable(registre):
    """Sans effet, mais pas invisible : c'est ce qui permet de la promouvoir."""
    rapport = registre.report()

    assert rapport["total_candidates"] == 1
    assert rapport["total_rules"] == 0
    assert "sans effet" in rapport["note"]


def test_la_preuve_qui_a_suggere_la_regle_est_conservee(registre):
    """Une règle sans preuve ne se discute pas."""
    assert _candidate(registre).evidence == ("correction du 2026-08-04",)


# ----------------------------------------------------------------------
# 2. La promotion est un acte signé
# ----------------------------------------------------------------------

def test_la_promotion_exige_un_validateur(registre):
    """Une règle sans auteur s'appliquera à des clients qui ne l'ont jamais
    demandée."""
    with pytest.raises(SkillRefused) as refus:
        registre.promote("documentaire", _candidate(registre), validated_by="")

    assert "jamais demandée" in str(refus.value)


@pytest.mark.parametrize("nom", ["GalSen IA", "l'assistant", "Le système",
                                 "Claude", "Agent média"])
def test_la_plateforme_ne_peut_pas_valider_ses_propres_regles(registre, nom):
    """Une règle qu'elle valide pour elle-même est une règle que personne n'a
    choisie."""
    with pytest.raises(SkillRefused) as refus:
        registre.promote("documentaire", _candidate(registre), validated_by=nom)

    assert "personne n'a choisie" in str(refus.value)


@pytest.mark.parametrize("nom", ["Mariama Ba", "M. Diop", "Aïssatou Sy",
                                 "Conseil éditorial"])
def test_un_validateur_humain_n_est_pas_pris_pour_la_plateforme(registre, nom):
    """« ia » est contenu dans « Mariama »."""
    regle = registre.promote("documentaire", _candidate(registre),
                             validated_by=nom, project_id="prj-1")

    assert regle.validated_by == nom
    assert is_platform_identity(nom) is False


def test_une_regle_promue_devient_applicable(registre):
    """Le cas nominal existe."""
    registre.promote("documentaire", _candidate(registre),
                     validated_by="Mme Ndiaye", project_id="prj-1")

    style = registre.get("documentaire")
    assert len(style.rules_for("subtitles", project_id="prj-1")) == 1
    assert style.candidates == []


def test_la_promotion_est_datee_et_journalisee(registre):
    """Sans date, une règle ne peut pas être située dans une histoire."""
    registre.promote("documentaire", _candidate(registre),
                     validated_by="M. Diop", project_id="prj-1")

    actions = [entree["action"] for entree in registre.history()]
    assert actions == ["suggested", "promoted"]
    assert registre.get("documentaire").rules[0].validated_at > 0


# ----------------------------------------------------------------------
# 3. Une règle de projet reste dans son projet
# ----------------------------------------------------------------------

def test_une_regle_de_projet_ne_sort_pas_de_son_projet(registre):
    """
    « Cela a marché pour un client » et « c'est ainsi qu'on travaille » ne
    s'appuient pas sur les mêmes preuves.
    """
    registre.promote("documentaire", _candidate(registre),
                     validated_by="M. Diop", project_id="prj-1")
    style = registre.get("documentaire")

    assert len(style.rules_for("subtitles", project_id="prj-1")) == 1
    assert style.rules_for("subtitles", project_id="prj-2") == []


def test_atteindre_le_global_demande_sa_propre_promotion(registre):
    """Une seule signature ne fait pas d'un mardi une politique maison."""
    regle = registre.promote("documentaire", _candidate(registre),
                             validated_by="M. Diop", scope=PORTEE_GLOBALE)

    assert regle.scope == PORTEE_GLOBALE
    assert regle.project_id == ""
    assert len(registre.report()["global_rules"]) == 1


def test_une_regle_de_projet_sans_projet_est_refusee():
    """Elle s'appliquerait partout en prétendant le contraire."""
    depot = SkillRegistry()
    candidate = depot.suggest("x", "colors", "Fond sombre")

    with pytest.raises(SkillRefused) as refus:
        depot.promote("x", candidate, validated_by="M. Diop",
                      scope=PORTEE_PROJET, project_id="")

    assert "prétendant le contraire" in str(refus.value)


def test_les_interdits_sont_rendus_a_part():
    """« Jamais de texte plein écran sur un visage » évite une faute ;
    « utiliser du bleu » exprime un goût."""
    depot = SkillRegistry()
    candidate = depot.suggest("doc", "forbidden",
                              "Jamais de texte plein écran sur un visage",
                              project_id="p")
    depot.promote("doc", candidate, validated_by="Mme Ndiaye", project_id="p")

    assert depot.get("doc").forbidden == [
        "Jamais de texte plein écran sur un visage"
    ]


# ----------------------------------------------------------------------
# 4. `NOT_CHECKED` n'est jamais un `PASS`
# ----------------------------------------------------------------------

def test_un_fichier_absent_echoue(tmp_path):
    """Le premier contrôle, et le plus simple."""
    resultats = check_file(str(tmp_path / "jamais_rendu.webm"))

    assert resultats[0]["outcome"] == ECHOUE


def test_un_fichier_vide_echoue(tmp_path):
    """Un fichier de zéro octet s'encode « sans erreur » sur plus d'un
    encodeur."""
    vide = tmp_path / "vide.webm"
    vide.write_bytes(b"")

    resultats = check_file(str(vide))

    assert resultats[0]["check"] == "file_not_empty"
    assert resultats[0]["outcome"] == ECHOUE


def test_un_format_different_de_celui_demande_echoue(tmp_path):
    """Un fichier lisible mais dans le mauvais conteneur n'est pas livrable."""
    from PIL import Image

    fichier = tmp_path / "sortie.webm"
    Image.new("RGB", (8, 8)).save(fichier, format="PNG")

    resultats = check_file(str(fichier), expected_format="webm")

    conformite = [r for r in resultats if r["check"] == "format_matches_request"]
    assert conformite[0]["outcome"] == ECHOUE


def test_un_encodage_interrompu_est_detecte():
    """Il produit un fichier lisible et plus court : le format ne le voit pas."""
    resultats = check_frames({"frames_sent": 18, "expected_frames": 24})

    assert resultats[0]["outcome"] == ECHOUE
    assert "interrompu" in resultats[0]["detail"]


def test_les_trames_noires_ne_sont_pas_declarees_absentes(tmp_path):
    """
    Déclarer « aucune trame noire » sans avoir regardé une trame serait le
    mensonge que ce contrôle existe pour éviter.
    """
    resultats = check_black_frames(str(tmp_path / "x.webm"))

    assert resultats[0]["outcome"] == NON_VERIFIE
    assert resultats[0]["needs"] == "video_decode"


def test_les_controles_audio_sont_nommes_non_verifies(tmp_path):
    """Les taire ferait un rapport qui semble complet."""
    resultats = check_audio(str(tmp_path / "x.webm"))

    assert {r["check"] for r in resultats} == {"clipping", "silence", "loudness"}
    assert all(r["outcome"] == NON_VERIFIE for r in resultats)


def test_des_sous_titres_qui_se_recouvrent_sont_detectes():
    """Ils s'afficheront l'un sur l'autre — invisible dans une liste."""
    cues = [
        Cue(index=1, start=0.0, end=3.0, text="Premier sous-titre"),
        Cue(index=2, start=2.0, end=5.0, text="Second sous-titre"),
    ]

    resultats = check_subtitles(cues)

    recouvrement = [r for r in resultats if r["check"] == "subtitle_overlap"]
    assert recouvrement[0]["outcome"] == ECHOUE
    assert "l'une sur l'autre" in recouvrement[0]["detail"]


def test_des_sous_titres_corrects_passent():
    """Le cas nominal ne doit pas crier au loup."""
    cues = [
        Cue(index=1, start=0.0, end=2.5, text="Premier"),
        Cue(index=2, start=2.6, end=5.0, text="Second"),
    ]

    assert all(r["outcome"] == PASSE for r in check_subtitles(cues))


def test_un_asset_sans_provenance_fait_echouer_le_contenu():
    """Un média dont personne ne sait d'où il vient est un problème juridique."""
    resultats = check_content(assets=[
        Asset(asset_id="douteux", kind="image", origin=ORIGINE_SOURCEE,
              source="quelque part"),
    ])

    provenance = [r for r in resultats if r["check"] == "asset_provenance"]
    assert provenance[0]["outcome"] == ECHOUE


def test_sans_re_transcription_le_contenu_est_non_verifie():
    """C'est le contrôle qui attrape une coupe ayant enlevé le mot « pas »."""
    resultats = check_content(intended_transcript="il faut comparer")

    transcription = [r for r in resultats
                     if r["check"] == "transcript_matches_intent"]
    assert transcription[0]["outcome"] == NON_VERIFIE


def test_une_transcription_conforme_passe():
    """Le seul contrôle capable de voir ce que la vidéo dit."""
    resultats = check_content(intended_transcript="il faut comparer",
                              final_transcript="il faut comparer")

    transcription = [r for r in resultats
                     if r["check"] == "transcript_matches_intent"]
    assert transcription[0]["outcome"] == PASSE


# ----------------------------------------------------------------------
# 5. Le verdict d'ensemble est difficile à atteindre
# ----------------------------------------------------------------------

def test_un_controle_non_verifie_empeche_la_reussite():
    """
    « Passé avec réserves » n'existe pas.

    Une production que personne n'a pu inspecter entièrement n'a pas été
    inspectée entièrement.
    """
    resultat = verdict([
        {"check": "a", "family": "video", "outcome": PASSE, "detail": ""},
        {"check": "b", "family": "audio", "outcome": NON_VERIFIE, "detail": ""},
    ])

    assert resultat["verdict"] == PRODUCTION_INCOMPLETE
    assert resultat["not_checked"] == ["b"]


def test_un_echec_prime_sur_un_non_verifie():
    """Un défaut trouvé se corrige ; une absence de contrôle se comble."""
    resultat = verdict([
        {"check": "a", "family": "video", "outcome": ECHOUE, "detail": ""},
        {"check": "b", "family": "audio", "outcome": NON_VERIFIE, "detail": ""},
    ])

    assert resultat["verdict"] == PRODUCTION_ECHOUEE


def test_tout_passe_et_rien_de_non_verifie_donne_la_reussite():
    """Le cas nominal existe, et il est exigeant."""
    resultat = verdict([
        {"check": "a", "family": "video", "outcome": PASSE, "detail": ""},
        {"check": "b", "family": "content", "outcome": PASSE, "detail": ""},
    ])

    assert resultat["verdict"] == PRODUCTION_REUSSIE


def test_un_rapport_vide_n_est_pas_une_reussite():
    """C'est l'absence de contrôle."""
    resultat = verdict([])

    assert resultat["verdict"] == PRODUCTION_INCOMPLETE
    assert "absence de contrôle" in resultat["reason"]


def test_les_non_verifies_ne_sont_jamais_comptes_comme_passes():
    """L'effondrement que la directive §21 vise."""
    resultat = verdict([
        {"check": "a", "family": "video", "outcome": PASSE, "detail": ""},
        {"check": "b", "family": "audio", "outcome": NON_VERIFIE, "detail": ""},
        {"check": "c", "family": "audio", "outcome": NON_VERIFIE, "detail": ""},
    ])

    assert resultat["counts"][PASSE] == 1
    assert resultat["counts"][NON_VERIFIE] == 2
    assert "croit au lieu de regarder la vidéo" in resultat["note"]


def test_une_production_reelle_est_incomplete_sur_cette_machine(tmp_path):
    """
    Le verdict honnête ici, de bout en bout.

    Une vraie vidéo est rendue, les contrôles vidéo passent, et les contrôles
    audio restent non vérifiés faute de codec — donc `INCOMPLETE`, pas
    « réussie ».
    """
    from src.media.core.capabilities import find_ffmpeg

    if find_ffmpeg() is None:
        pytest.skip("aucun ffmpeg dans cet environnement")

    from src.media.motion.render import render_video
    from src.media.motion.scene import Element, MotionScene

    scene = MotionScene(width=64, height=36, fps=24, frames=6, elements=(
        Element(kind="rect", props={"x": 4, "y": 4, "width": 20, "height": 10}),
    ))
    sortie = tmp_path / "production.webm"
    rendu = render_video(scene, str(sortie))

    controles = (
        check_file(str(sortie), expected_format="webm")
        + check_frames(rendu)
        + check_audio(str(sortie))
    )
    resultat = verdict(controles)

    assert resultat["counts"][ECHOUE] == 0
    assert resultat["verdict"] == PRODUCTION_INCOMPLETE
    assert set(resultat["not_checked"]) == {"clipping", "silence", "loudness"}


# ----------------------------------------------------------------------
# 6. Ce que les deux volets refusent
# ----------------------------------------------------------------------

def test_le_rapport_des_skills_refuse_la_promotion_automatique():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(skill_report()["does_not"])

    assert "Promouvoir une correction toute seule" in interdits
    assert "plateforme comme validateur" in interdits
    assert "Appliquer une règle candidate" in interdits


def test_le_rapport_qualite_refuse_de_compter_un_non_verifie_comme_reussi():
    """C'est la distinction de la directive §21, rendue mécanique."""
    rapport = qc_report()

    interdits = " ".join(rapport["does_not"])
    assert "non vérifié comme réussi" in interdits
    assert "qu'aucun outil n'a cherché" in interdits
    assert rapport["outcomes"] == [PASSE, ECHOUE, NON_VERIFIE]
    assert set(rapport["families"]) == set(FAMILLES)
