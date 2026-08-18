"""
Tests for the media tools exposed to the agent system (§24).

What is pinned: an impossible chain is refused before anything is encoded, a
missing capability is named instead of being replaced by a plausible result,
and the generative tool cannot be reached through the local declaration.
"""

import pytest

from src.media.tools.catalog import (
    CATALOGUE,
    OUTIL_GENERATIF,
    OUTIL_LOCAL,
    ToolCatalogError,
    availability,
    catalog_report,
    plan_chain,
    producers_of,
    runnable_now,
    spec_for,
)
from src.tool.capabilities import DataScope, Effect, load_capabilities
from src.tools.media.tool import MediaGenerationTool, MediaTool


# --------------------------------------------------------------------------
# Le catalogue
# --------------------------------------------------------------------------


def test_les_seize_outils_de_la_directive_sont_declares():
    noms = [spec.name for spec in CATALOGUE]
    assert noms == [
        "create_video_project", "analyze_media", "transcribe_media",
        "detect_scenes", "create_storyboard", "create_edit_plan",
        "generate_visual", "generate_video", "create_motion_graphic",
        "generate_subtitles", "select_music", "select_sfx", "render_video",
        "inspect_video", "repair_video", "export_video",
    ]


def test_un_nom_inconnu_est_refuse_jamais_rapproche():
    # Rapprocher « render_vidéo » de « render_video » exécuterait un outil que
    # personne n'a appelé.
    with pytest.raises(ToolCatalogError) as erreur:
        spec_for("render_vidéo")
    assert "inconnu" in str(erreur.value)


def test_un_plan_de_montage_consomme_une_transcription_mesuree():
    # C'est la garantie §5 rendue structurelle : sans transcription, aucune
    # coupe ne peut être planifiée, donc aucun modèle ne peut en inventer une.
    assert spec_for("create_edit_plan").consumes == ("transcript",)
    assert producers_of("transcript") == ["transcribe_media"]


def test_seule_la_generation_sort_de_la_machine():
    externes = {spec.name for spec in CATALOGUE if spec.external}
    assert externes == {"generate_visual", "generate_video"}
    assert all(spec.tool_id == OUTIL_GENERATIF
               for spec in CATALOGUE if spec.external)


# --------------------------------------------------------------------------
# L'enchaînement
# --------------------------------------------------------------------------


def test_un_rendu_avant_le_plan_est_refuse_avant_tout_encodage():
    resultat = plan_chain(["render_video"], available=["media"])
    assert resultat["ordered"] is False
    assert resultat["failed_at"]["tool"] == "render_video"
    assert resultat["failed_at"]["missing_inputs"] == ["edit_plan"]
    # Le refus dit **quel outil** aurait produit l'entrée manquante.
    assert resultat["failed_at"]["produced_by"]["edit_plan"] == ["create_edit_plan"]


def test_un_enchainement_possible_est_accepte_et_dit_ce_qui_est_bloque():
    resultat = plan_chain(
        ["analyze_media", "transcribe_media", "create_edit_plan",
         "render_video"],
        available=["media"],
    )
    assert resultat["ordered"] is True
    assert [etape["tool"] for etape in resultat["steps"]][0] == "analyze_media"
    # Ordonnable n'est pas exécutable : ce qui bloque ici est une capacité.
    assert "render_video" in resultat["blocked"]


def test_un_enchainement_sans_media_de_depart_est_refuse_au_premier_maillon():
    resultat = plan_chain(["analyze_media"])
    assert resultat["ordered"] is False
    assert resultat["failed_at"]["position"] == 1
    assert resultat["failed_at"]["missing_inputs"] == ["media"]


def test_l_ordre_compte_pas_seulement_la_presence():
    inverse = plan_chain(["create_edit_plan", "transcribe_media"],
                         available=["media"])
    assert inverse["ordered"] is False
    endroit = plan_chain(["transcribe_media", "create_edit_plan"],
                         available=["media"])
    assert endroit["ordered"] is True


# --------------------------------------------------------------------------
# Les capacités mesurées
# --------------------------------------------------------------------------


def test_une_capacite_absente_est_nommee_pas_remplacee():
    etat = availability("analyze_media")
    # `media_probe` est absent de cette machine : mesuré, pas supposé.
    assert etat["status"] == "NOT_CONFIGURED"
    assert [m["capability"] for m in etat["missing"]] == ["media_probe"]
    assert etat["missing"][0]["without_it"]


def test_un_outil_sans_dependance_est_disponible():
    assert availability("generate_subtitles")["status"] == "AVAILABLE"
    assert availability("create_edit_plan")["status"] == "AVAILABLE"


def test_le_rapport_d_execution_nomme_ce_qui_bloque_chaque_outil():
    rapport = runnable_now()
    assert rapport["count"] == 16
    assert set(rapport["runnable"]) & {"create_video_project",
                                       "generate_subtitles"}
    # Chaque outil bloqué l'est par une capacité **nommée**.
    assert all(capacites for capacites in rapport["not_configured"].values())


# --------------------------------------------------------------------------
# L'outil enregistré
# --------------------------------------------------------------------------


def test_l_outil_local_ne_liste_pas_les_operations_generatives():
    operations = MediaTool({"tool_id": OUTIL_LOCAL}).available_operations()
    assert "render_video" in operations
    assert "generate_video" not in operations
    assert "plan_chain" in operations


def test_l_outil_generatif_ne_porte_que_la_generation():
    operations = MediaGenerationTool().available_operations()
    assert set(operations) == {
        "availability", "catalog", "plan_chain", "runnable",
        "generate_visual", "generate_video",
    }


def test_appeler_la_generation_depuis_l_outil_local_est_refuse():
    with pytest.raises(ValueError) as erreur:
        MediaTool({"tool_id": OUTIL_LOCAL}).execute("generate_video")
    assert OUTIL_GENERATIF in str(erreur.value)


def test_une_operation_inconnue_est_refusee_avec_la_liste():
    with pytest.raises(ValueError) as erreur:
        MediaTool().execute("make_me_a_movie")
    assert "inconnue" in str(erreur.value)


def test_un_outil_dont_la_capacite_manque_rend_son_etat_pas_un_resultat():
    resultat = MediaTool().execute("analyze_media", "/tmp/inexistant.mp4")
    assert resultat["status"] == "NOT_CONFIGURED"
    # Aucune durée, aucun codec, aucune valeur par défaut.
    assert "info" not in resultat


def test_un_refus_du_moteur_est_rendu_mot_pour_mot():
    resultat = MediaTool().execute("create_edit_plan", [], [])
    assert resultat["status"] == "REFUSED"
    assert "Aucun mot transcrit" in resultat["reason"]
    assert resultat["error"] == "EditPlanRefused"


def test_une_production_est_ouverte_avec_son_identite():
    resultat = MediaTool().execute("create_video_project",
                                   "Documentaire de 60 secondes")
    assert resultat["status"] == "OK"
    assert resultat["project_id"].startswith("prj-")


def test_la_reparation_ne_propose_que_des_defauts_constates():
    # La règle vit dans le contrôle qualité, à côté des trois issues qu'elle
    # départage. L'outil `repair_video` exige en plus un encodeur, absent ici.
    from src.media.qc.checks import repairable

    resultat = repairable([
        {"check": "file_exists", "outcome": "PASS"},
        {"check": "audio_track", "outcome": "NOT_CHECKED"},
    ])
    assert resultat["status"] == "NOTHING_TO_REPAIR"
    assert resultat["failures"] == []
    # Un contrôle qui n'a pas pu tourner n'est pas un défaut à corriger.
    assert [c["check"] for c in resultat["not_checked"]] == ["audio_track"]


def test_un_defaut_constate_est_reparable_lui():
    from src.media.qc.checks import repairable

    resultat = repairable([
        {"check": "file_exists", "outcome": "FAIL"},
        {"check": "audio_track", "outcome": "NOT_CHECKED"},
    ])
    assert resultat["status"] == "REPAIRABLE"
    assert [c["check"] for c in resultat["failures"]] == ["file_exists"]


def test_reparer_exige_un_encodeur_et_le_dit():
    resultat = MediaTool().execute("repair_video", {"checks": []})
    assert resultat["status"] == "NOT_CONFIGURED"
    assert [m["capability"] for m in resultat["missing"]] == ["video_encode"]


# --------------------------------------------------------------------------
# La frontière du registre
# --------------------------------------------------------------------------


def test_le_registre_declare_les_deux_outils_media():
    registre = load_capabilities()
    local = registre.get(OUTIL_LOCAL)
    generatif = registre.get(OUTIL_GENERATIF)

    assert local.declared and generatif.declared
    assert local.touches(DataScope.USER_PRIVATE)
    assert not local.has(Effect.EXTERNAL)
    assert generatif.has(Effect.EXTERNAL)


def test_la_generation_ne_tourne_jamais_sans_humain():
    registre = load_capabilities()
    # Donnée privée + sortie de la machine : la forme d'un chemin
    # d'exfiltration. Le registre l'exige approuvée, et non surveillée.
    assert registre.get(OUTIL_GENERATIF).requires_approval is True
    assert registre.get(OUTIL_GENERATIF).unattended is False
    assert OUTIL_GENERATIF not in registre.unattended_ids()


def test_le_rapport_du_catalogue_nomme_ce_qu_il_refuse():
    rapport = catalog_report()
    assert rapport["count"] == 16
    assert len(rapport["by_tool_id"][OUTIL_GENERATIF]) == 2
    refus = " ".join(rapport["does_not"]).lower()
    assert "deviner" in refus
    assert "plausible" in " ".join(rapport["rules"]).lower()
