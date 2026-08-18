"""
Tests for multi-format adaptation (§22-§23) and the render queue (§28).

What is pinned here is not that the functions run, but that the two comfortable
lies they replace stay unavailable: reframing that is really a centre crop, and
progress computed from elapsed time.
"""

import pytest

from src.media.adapt.formats import (
    FORMATS,
    AdaptationRefused,
    Placement,
    adapt,
    adaptation_report,
    aspect_of,
    centre_crop_survivors,
    localise_cues,
)
from src.media.queue.jobs import (
    PRIORITE_BASSE,
    PRIORITE_HAUTE,
    PRIORITE_NORMALE,
    TENTATIVES_MAXIMUM,
    QueueRefused,
    RenderJob,
    RenderQueue,
    queue_report,
)
from src.media.subtitles.cues import Cue
from src.router.workflow_checkpoint import RunStatus


# --------------------------------------------------------------------------
# Formats et placements
# --------------------------------------------------------------------------


def test_les_formats_declares_ont_le_bon_rapport():
    assert aspect_of("16:9") == pytest.approx(16 / 9)
    assert aspect_of("9:16") == pytest.approx(9 / 16)
    assert aspect_of("1:1") == 1.0
    assert set(FORMATS) >= {"16:9", "9:16", "1:1", "4:5", "4:3", "2.39:1"}


def test_un_format_inconnu_est_refuse_pas_devine():
    with pytest.raises(AdaptationRefused) as erreur:
        aspect_of("21:9")
    assert "non déclaré" in str(erreur.value)


def test_les_coordonnees_hors_de_zero_un_sont_refusees():
    # Des pixels absolus passeraient ici sans bruit et casseraient tout
    # repositionnement dans un autre format.
    with pytest.raises(AdaptationRefused) as erreur:
        Placement(element_id="logo", x=1720.0, y=40.0, width=160.0, height=60.0)
    assert "relatives" in str(erreur.value)


def test_un_element_sans_surface_est_refuse():
    with pytest.raises(AdaptationRefused):
        Placement(element_id="vide", x=0.1, y=0.1, width=0.0, height=0.2)


# --------------------------------------------------------------------------
# §22 — le recadrage centré est mesuré, l'adaptation repose
# --------------------------------------------------------------------------


def _scene_16_9():
    """Un logo en haut à droite, un bandeau bas, un locuteur décentré."""
    return [
        Placement(element_id="logo", x=0.86, y=0.04, width=0.10, height=0.08,
                  anchor="top_right", protected=True),
        Placement(element_id="bandeau", x=0.05, y=0.82, width=0.50,
                  height=0.10, anchor="bottom_left"),
        Placement(element_id="locuteur", x=0.62, y=0.30, width=0.20,
                  height=0.40, anchor="center", protected=True),
    ]


def test_un_recadrage_centre_perdrait_le_logo_et_le_locuteur():
    mesure = centre_crop_survivors(_scene_16_9(), "16:9", "9:16")
    # Le fichier produit aurait la bonne forme et aurait perdu l'identité.
    assert "logo" in mesure["lost"]
    assert "locuteur" in mesure["lost"]
    assert mesure["crop_box"]["left"] > 0.0
    assert mesure["crop_box"]["right"] < 1.0


def test_l_adaptation_repose_les_elements_et_ne_perd_rien():
    resultat = adapt(_scene_16_9(), "16:9", "9:16")
    survivants = {p["element_id"] for p in resultat["placements"]}
    assert survivants == {"logo", "bandeau", "locuteur"}
    # Le coût du recadrage refusé est mesuré à côté : le refus est vérifiable.
    assert "logo" in resultat["crop_would_lose"]


def test_tout_element_adapte_reste_dans_la_zone_utile():
    resultat = adapt(_scene_16_9(), "16:9", "9:16", safe_margin=0.05)
    for element in resultat["objects"]:
        assert element.x >= 0.05 - 1e-6
        assert element.y >= 0.05 - 1e-6
        assert element.x + element.width <= 0.95 + 1e-6
        assert element.y + element.height <= 0.95 + 1e-6


def test_un_ancrage_est_respecte_apres_repositionnement():
    resultat = adapt(_scene_16_9(), "16:9", "9:16", safe_margin=0.05)
    place = {p.element_id: p for p in resultat["objects"]}
    # Le logo est ancré en haut à droite : il y reste, il ne dérive pas.
    assert place["logo"].y == pytest.approx(0.05, abs=1e-3)
    assert place["logo"].x + place["logo"].width == pytest.approx(0.95, abs=1e-3)
    # Le bandeau est ancré en bas à gauche.
    assert place["bandeau"].x == pytest.approx(0.05, abs=1e-3)


def test_un_element_protege_trop_grand_est_rapporte_jamais_reduit():
    trop_grand = [Placement(element_id="logo", x=0.0, y=0.1, width=0.95,
                            height=0.2, protected=True)]
    resultat = adapt(trop_grand, "16:9", "1:1", safe_margin=0.05)
    signales = {e["element_id"]: e for e in resultat["does_not_fit"]}
    assert "logo" in signales
    assert signales["logo"]["protected"] is True
    # Rapporté, et sa taille est intacte : réduire un logo change une marque.
    conserve = {p.element_id: p for p in resultat["objects"]}["logo"]
    assert conserve.width == pytest.approx(0.95)


def test_une_marge_absurde_est_refusee():
    with pytest.raises(AdaptationRefused) as erreur:
        adapt(_scene_16_9(), "16:9", "1:1", safe_margin=0.6)
    assert "0.4" in str(erreur.value)


def test_un_format_source_inconnu_est_refuse_avant_tout_calcul():
    with pytest.raises(AdaptationRefused):
        adapt(_scene_16_9(), "imax", "9:16")


# --------------------------------------------------------------------------
# §23 — une version linguistique ne retime rien
# --------------------------------------------------------------------------


def _master():
    return [
        Cue(index=1, start=0.0, end=2.5, text="Bonjour et bienvenue.",
            language="fr"),
        Cue(index=2, start=2.5, end=5.0, text="Voici le rapport annuel.",
            language="fr"),
        Cue(index=3, start=5.0, end=7.0, text="Merci de votre attention.",
            language="fr"),
    ]


def test_la_localisation_reprend_le_minutage_exactement():
    master = _master()
    version = localise_cues(
        master,
        {1: "Hello and welcome.", 2: "Here is the annual report.",
         3: "Thank you for your attention."},
        "en",
    )
    assert version["timing_preserved"] is True
    for origine, traduit in zip(master, version["objects"]):
        assert traduit.start == origine.start
        assert traduit.end == origine.end
    assert version["untranslated"] == []


def test_un_sous_titre_non_traduit_est_nomme_jamais_remplace_par_la_source():
    version = localise_cues(_master(), {1: "Hello and welcome."}, "en")
    manquants = [m["index"] for m in version["untranslated"]]
    assert manquants == [2, 3]
    # Aucune ligne française ne se glisse dans la version anglaise.
    assert all(cue.language == "en" for cue in version["objects"])
    assert [cue.index for cue in version["objects"]] == [1]


def test_une_traduction_trop_longue_est_signalee_pas_etiree():
    master = [Cue(index=1, start=0.0, end=1.0, text="Bonjour.", language="fr")]
    version = localise_cues(
        master,
        {1: "Good morning everyone and a very warm welcome to all of you."},
        "en",
    )
    assert [t["index"] for t in version["too_long"]] == [1]
    # La fenêtre est inchangée : étirer ferait dériver tout ce qui suit.
    assert version["objects"][0].start == 0.0
    assert version["objects"][0].end == 1.0


def test_la_direction_de_lecture_est_declaree_par_la_langue():
    version = localise_cues(_master(), {1: "مرحبا", 2: "التقرير", 3: "شكرا"}, "ar")
    assert version["direction"] == "rtl"
    assert version["objects"][0].direction == "rtl"


def test_une_langue_non_declaree_est_refusee():
    with pytest.raises(AdaptationRefused) as erreur:
        localise_cues(_master(), {1: "Hola"}, "es")
    assert "devin" in str(erreur.value)


def test_le_rapport_d_adaptation_nomme_ce_qu_il_refuse():
    rapport = adaptation_report()
    refus = " ".join(rapport["does_not"]).lower()
    assert "rogner" in refus
    assert "étirer" in refus or "etirer" in refus


# --------------------------------------------------------------------------
# §28 — file d'attente
# --------------------------------------------------------------------------


def test_un_avancement_sans_total_connu_rend_none_pas_zero():
    job = RenderJob(job_id="j1", total_units=None, done_units=0)
    assert job.progress is None
    # Un inconnu n'est pas 0 %, et la sérialisation le dit aussi.
    assert job.as_dict()["progress"] is None
    assert "n'est pas 0" in job.as_dict()["progress_note"]


def test_un_avancement_connu_est_compte_pas_estime():
    job = RenderJob(job_id="j1", total_units=200, done_units=50)
    assert job.progress == pytest.approx(0.25)


def test_une_priorite_non_declaree_est_refusee():
    with pytest.raises(QueueRefused) as erreur:
        RenderJob(job_id="j1", priority=99)
    assert "non déclarée" in str(erreur.value)


def test_un_total_nul_est_refuse():
    with pytest.raises(QueueRefused):
        RenderJob(job_id="j1", total_units=0)


def test_la_priorite_passe_devant_puis_l_ordre_de_depot():
    file = RenderQueue()
    ancien = file.submit(kind="render", priority=PRIORITE_NORMALE)
    file.submit(kind="render", priority=PRIORITE_BASSE)
    urgent = file.submit(kind="render", priority=PRIORITE_HAUTE)
    assert file.next_job().job_id == urgent.job_id

    file.cancel(urgent.job_id, by="operateur")
    assert file.next_job().job_id == ancien.job_id


def test_a_priorite_egale_le_plus_ancien_passe():
    file = RenderQueue()
    matin = file.submit(priority=PRIORITE_NORMALE)
    apres_midi = file.submit(priority=PRIORITE_NORMALE)
    # Horodatages distincts et volontairement à l'envers de l'ordre de dépôt :
    # c'est la date qui décide, pas l'ordre d'insertion du dictionnaire.
    file.get(matin.job_id).submitted_at = 1000.0
    file.get(apres_midi.job_id).submitted_at = 2000.0
    assert file.next_job().job_id == matin.job_id

    file.get(matin.job_id).submitted_at = 3000.0
    assert file.next_job().job_id == apres_midi.job_id


def test_un_avancement_qui_recule_est_refuse():
    file = RenderQueue()
    job = file.submit(total_units=100)
    file.advance(job.job_id, 40)
    with pytest.raises(QueueRefused) as erreur:
        file.advance(job.job_id, 30)
    assert "recul" in str(erreur.value)


def test_un_avancement_au_dela_du_total_est_refuse():
    file = RenderQueue()
    job = file.submit(total_units=100)
    with pytest.raises(QueueRefused):
        file.advance(job.job_id, 101)


def test_chaque_tentative_est_conservee_avec_son_erreur():
    file = RenderQueue()
    job = file.submit(total_units=10)
    file.record_attempt(job.job_id, "failed", error="encodeur absent")
    file.retry(job.job_id)
    final = file.record_attempt(job.job_id, "succeeded")

    assert final.status is RunStatus.COMPLETED
    assert final.attempt_count == 2
    # Le premier échec survit à la réussite : c'est lui qui apprend qu'un
    # problème existe en amont.
    assert final.attempts[0]["error"] == "encodeur absent"


def test_les_tentatives_sont_bornees():
    file = RenderQueue()
    job = file.submit(total_units=10)
    for tour in range(TENTATIVES_MAXIMUM):
        file.record_attempt(job.job_id, "failed", error=f"echec {tour}")
        if tour < TENTATIVES_MAXIMUM - 1:
            file.retry(job.job_id)

    with pytest.raises(QueueRefused) as erreur:
        file.retry(job.job_id)
    # L'échec reste consigné dans le refus lui-même.
    assert "echec 0" in str(erreur.value)
    assert file.get(job.job_id).can_retry is False


def test_une_annulation_est_terminale():
    file = RenderQueue()
    job = file.submit(total_units=100)
    file.advance(job.job_id, 80)
    annule = file.cancel(job.job_id, by="realisatrice")

    assert annule.status is RunStatus.CANCELLED
    # L'avancement est conservé : savoir qu'on a arrêté à 80 % est une donnée.
    assert annule.progress == pytest.approx(0.8)
    with pytest.raises(QueueRefused):
        file.retry(job.job_id)
    with pytest.raises(QueueRefused):
        file.record_attempt(job.job_id, "succeeded")
    assert file.next_job() is None


def test_un_travail_inconnu_est_refuse_pas_cree():
    file = RenderQueue()
    with pytest.raises(QueueRefused):
        file.advance("job-inexistant", 1)
    assert file.get("job-inexistant") is None


def test_les_reservations_sont_declaratives_et_additionnees():
    file = RenderQueue()
    file.submit(reserved={"vram_gb": 12.0})
    file.submit(reserved={"vram_gb": 8.0, "cpu": 4})
    reservations = file.reservations()

    assert reservations["declared_totals"]["vram_gb"] == pytest.approx(20.0)
    # Rien n'est imposé : ce module n'empêche aucun processus de prendre un GPU.
    assert reservations["enforced"] is False
    assert len(reservations["active_jobs"]) == 2


def test_une_reservation_ne_compte_plus_apres_annulation():
    file = RenderQueue()
    job = file.submit(reserved={"vram_gb": 12.0})
    file.cancel(job.job_id)
    assert file.reservations()["declared_totals"] == {}


def test_le_rapport_de_file_nomme_les_totaux_inconnus():
    file = RenderQueue()
    sans_total = file.submit(total_units=None)
    file.submit(total_units=50)
    rapport = file.report()

    assert rapport["count"] == 2
    assert rapport["unknown_progress"] == [sans_total.job_id]
    assert rapport["by_status"][RunStatus.RUNNING.value] == 2
    assert rapport["max_attempts"] == TENTATIVES_MAXIMUM


def test_la_file_reutilise_le_vocabulaire_d_etats_existant():
    # Un second vocabulaire pour la même idée finirait par diverger.
    assert set(queue_report()["statuses"]) == {etat.value for etat in RunStatus}
    assert queue_report()["priorities"] == [
        PRIORITE_BASSE, PRIORITE_NORMALE, PRIORITE_HAUTE
    ]


def test_le_rapport_de_file_nomme_ce_qu_elle_refuse():
    refus = " ".join(queue_report()["does_not"]).lower()
    assert "temps écoulé" in refus
    assert "annulé" in refus
