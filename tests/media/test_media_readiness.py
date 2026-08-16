"""
Tests for the readiness report (§40, §32).

The pinned property is that the verdict is *computed*: a report whose
conclusion is a constant says the same thing the day the engine works and the
day it does not.
"""

from src.media.readiness import (
    ABSENT,
    BLOQUE,
    COUVERTURE,
    ETAPES,
    PRET,
    Stage,
    coverage_map,
    readiness,
    readiness_report,
    stage_state,
)


# --------------------------------------------------------------------------
# Les dix-sept étapes de §40
# --------------------------------------------------------------------------


def test_les_dix_sept_etapes_sont_declarees_dans_l_ordre():
    noms = [etape.name for etape in ETAPES]
    assert noms == [
        "IDEA", "SCRIPT", "MEDIA_ANALYSIS", "STORYBOARD", "SCENES",
        "VISUAL_GENERATION", "VIDEO_GENERATION", "MOTION_DESIGN", "VOICE",
        "MUSIC", "SOUND_DESIGN", "SUBTITLES", "EDITING", "QUALITY_CONTROL",
        "MULTI_FORMAT", "MULTILINGUAL", "FINAL_MASTER",
    ]


def test_chaque_module_cite_existe_reellement():
    # Un rapport qui nomme un fichier absent décrit un moteur qui n'est pas là.
    for entree in readiness()["stages"]:
        if entree["module"]:
            assert entree["state"] in (PRET, BLOQUE), entree


def test_une_etape_sans_module_est_absente_pas_bloquee():
    voix = [e for e in readiness()["stages"] if e["stage"] == "VOICE"][0]
    assert voix["state"] == ABSENT
    assert voix["module"] is None
    assert voix["missing"] == []
    # Aucune installation ne la corrige : le dire évite d'envoyer un exploitant
    # chercher un paquet qui n'a jamais été le problème.
    assert "n'a pas été écrit" in voix["reason"]


def test_un_module_cite_et_absent_est_rapporte_absent():
    invente = Stage("INVENTED", "src/media/jamais_ecrit.py")
    etat = stage_state(invente)
    assert etat["state"] == ABSENT
    assert "n'existe pas" in etat["reason"]


def test_une_etape_bloquee_nomme_ce_qui_lui_manque():
    analyse = [e for e in readiness()["stages"]
               if e["stage"] == "MEDIA_ANALYSIS"][0]
    assert analyse["state"] == BLOQUE
    assert [m["capability"] for m in analyse["missing"]] == ["media_probe"]
    # Le module est écrit ; ce qui manque s'installe.
    assert analyse["module"] == "src/media/ingestion/inspect.py"


def test_une_etape_sans_dependance_est_prete_ici():
    sous_titres = [e for e in readiness()["stages"]
                   if e["stage"] == "SUBTITLES"][0]
    assert sous_titres["state"] == PRET
    assert sous_titres["missing"] == []


def test_le_motion_design_est_pret_sur_cette_machine():
    # `frame_encode` est mesuré disponible ici : c'est le seul chemin de la
    # directive qui rend et encode réellement sur cette machine.
    motion = [e for e in readiness()["stages"]
              if e["stage"] == "MOTION_DESIGN"][0]
    assert motion["state"] == PRET


# --------------------------------------------------------------------------
# Le verdict
# --------------------------------------------------------------------------


def test_le_verdict_est_calcule_pas_ecrit_d_avance():
    rapport = readiness()
    # Il nomme l'étape non écrite, donc il change si elle est écrite.
    assert "VOICE" in rapport["state"]
    assert "NOT IMPLEMENTED" in rapport["state"]
    assert rapport["counts"][ABSENT] == 1


def test_le_verdict_distingue_ce_qui_s_installe_de_ce_qui_s_ecrit():
    from src.media.readiness import _verdict

    seulement_bloque = {PRET: ["A"], BLOQUE: ["B"], ABSENT: []}
    tout_pret = {PRET: ["A"], BLOQUE: [], ABSENT: []}
    assert _verdict(seulement_bloque) == (
        "ENGINE READY — MEDIA RUNTIME DEPENDENCIES PENDING")
    assert "ALL STAGES RUNNABLE HERE" in _verdict(tout_pret)


def test_les_capacites_manquantes_sont_agregees_une_seule_fois():
    manquantes = readiness()["missing_capabilities"]
    assert manquantes == sorted(set(manquantes))
    assert "media_probe" in manquantes
    assert "transcription" in manquantes


def test_les_comptes_couvrent_toutes_les_etapes():
    rapport = readiness()
    assert sum(rapport["counts"].values()) == len(ETAPES)


# --------------------------------------------------------------------------
# La couverture de tests (§32)
# --------------------------------------------------------------------------


def test_les_quinze_domaines_de_la_directive_sont_declares():
    assert len(COUVERTURE) == 15
    assert "wangp_integration" in COUVERTURE
    assert "rollback" in COUVERTURE


def test_chaque_fichier_de_test_cite_existe_sur_le_disque():
    couverture = coverage_map()
    # Publier une couverture appuyée sur un fichier absent est la façon la plus
    # simple de la fausser.
    assert couverture["missing_files"] == {}
    assert len(couverture["covered"]) == 15


def test_le_rapport_nomme_ce_qu_il_refuse():
    rapport = readiness_report()
    assert rapport["stage_count"] == 17
    refus = " ".join(rapport["does_not"]).lower()
    assert "vérifier" in refus
    assert "d'avance" in refus
