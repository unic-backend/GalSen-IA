"""
Tests for the media API surface (§29) and the boundary that guards it (§30).

The routes are the place where an untrusted path arrives, so what is pinned
here is that it is judged **once**, before the engine sees it, and that a
refusal names the path rather than rewriting it.
"""

import os

import pytest
from fastapi.testclient import TestClient

from src.api import server as server_module
from src.api.server import app
from src.media.security.boundary import (
    EXTENSIONS_AUTORISEES,
    MediaPathRefused,
    boundary_report,
    media_root,
    safe_bitrate,
    safe_media_path,
    safe_output_name,
)


@pytest.fixture
def racine_media(tmp_path, monkeypatch):
    """Une racine média isolée, sous un répertoire de données jetable."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    return media_root()


@pytest.fixture
def cles(monkeypatch):
    """Clés admin et lecture seule, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin,cle-lecture:readonly")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield {"admin": "cle-admin", "readonly": "cle-lecture"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def client():
    """Client HTTP sur l'application réelle."""
    with TestClient(app) as essai:
        yield essai


# --------------------------------------------------------------------------
# §30 — la frontière
# --------------------------------------------------------------------------


def test_un_chemin_sous_la_racine_est_accepte(racine_media):
    fichier = os.path.join(racine_media, "rush.mp4")
    open(fichier, "wb").write(b"x")
    assert safe_media_path("rush.mp4", must_exist=True) == fichier


def test_une_remontee_est_refusee_meme_avec_une_extension_permise(racine_media):
    # Résolu avant d'être jugé : `..` ne se détecte pas à l'orthographe.
    with pytest.raises(MediaPathRefused) as erreur:
        safe_media_path("../../secret.mp4")
    assert "sort de l'espace" in str(erreur.value)


def test_une_remontee_interne_qui_revient_est_acceptee(racine_media):
    # `sous/../rush.mp4` atterrit dans la racine : refuser à l'orthographe
    # interdirait un chemin légitime.
    open(os.path.join(racine_media, "rush.mp4"), "wb").write(b"x")
    assert safe_media_path("sous/../rush.mp4", must_exist=True).endswith("rush.mp4")


def test_un_lien_symbolique_sortant_est_refuse(racine_media, tmp_path):
    dehors = tmp_path / "dehors.mp4"
    dehors.write_bytes(b"x")
    lien = os.path.join(racine_media, "piege.mp4")
    os.symlink(dehors, lien)
    # Le lien est suivi **avant** le jugement : c'est l'évasion qu'une simple
    # comparaison de préfixe laisse passer.
    with pytest.raises(MediaPathRefused):
        safe_media_path("piege.mp4")


def test_un_nom_commencant_par_un_tiret_est_refuse(racine_media):
    with pytest.raises(MediaPathRefused) as erreur:
        safe_media_path("-i.mp4")
    # Pour un codec, ce n'est pas un fichier : c'est une option.
    assert "option" in str(erreur.value)


def test_une_extension_hors_liste_blanche_est_refusee(racine_media):
    with pytest.raises(MediaPathRefused) as erreur:
        safe_media_path("charge.exe")
    assert "blanche" in str(erreur.value)
    assert ".exe" not in EXTENSIONS_AUTORISEES


def test_un_caractere_de_controle_est_refuse(racine_media):
    with pytest.raises(MediaPathRefused):
        safe_media_path("rush\x00.mp4")


def test_un_fichier_absent_n_est_pas_un_fichier_vide(racine_media):
    with pytest.raises(MediaPathRefused) as erreur:
        safe_media_path("jamais_vu.mp4", must_exist=True)
    assert "n'est pas un fichier vide" in str(erreur.value)


def test_un_nom_de_sortie_garde_ce_qui_etait_reconnaissable():
    assert safe_output_name("Ma Vidéo Finale!!.mov") == "Ma-Vid-o-Finale.webm"
    # Un identifiant tiré au sort ferait perdre le seul repère de l'utilisateur.
    with pytest.raises(MediaPathRefused):
        safe_output_name("!!!")


def test_un_debit_invalide_est_refuse_avant_le_rendu():
    assert safe_bitrate("800k") == "800k"
    with pytest.raises(MediaPathRefused):
        safe_bitrate("800k -f matroska /etc/passwd")


def test_la_frontiere_reutilise_au_lieu_de_reecrire():
    rapport = boundary_report()
    assert "workspace" in rapport["reuses"]["traversal_and_symlinks"]
    assert "trust" in rapport["reuses"]["external_text"]
    # Elle ne prétend pas protéger d'un shell qui n'existe pas.
    assert "shell" in " ".join(rapport["does_not"]).lower()
    assert "-c:v" in rapport["codec_note"]


# --------------------------------------------------------------------------
# §29 — les routes
# --------------------------------------------------------------------------


def test_les_sept_routes_de_la_directive_existent():
    chemins = {
        (chemin, methode)
        for route in app.routes
        if getattr(route, "path", "").startswith("/media")
        for chemin in [route.path]
        for methode in route.methods
        if methode != "HEAD"
    }
    for attendu in [
        ("/media/projects", "POST"),
        ("/media/projects/{project_id}", "GET"),
        ("/media/projects/{project_id}/analyze", "POST"),
        ("/media/projects/{project_id}/plan", "POST"),
        ("/media/projects/{project_id}/render", "POST"),
        ("/media/jobs/{job_id}", "GET"),
        ("/media/jobs/{job_id}/cancel", "POST"),
    ]:
        assert attendu in chemins, attendu


def test_une_production_s_ouvre_et_se_relit(client, cles, racine_media):
    creation = client.post(
        "/media/projects", json={"objective": "Documentaire de 60 secondes"},
        headers={"X-API-Key": cles["admin"]},
    )
    assert creation.status_code == 201
    identite = creation.json()["project_id"]

    manifeste = client.get(f"/media/projects/{identite}",
                           headers={"X-API-Key": cles["admin"]})
    assert manifeste.status_code == 200
    # Le manifeste montre **toutes** les versions, pas seulement la courante.
    assert manifeste.json()["version_count"] == 1


def test_une_production_sans_objectif_est_refusee(client, cles, racine_media):
    reponse = client.post("/media/projects", json={"objective": "  "},
                          headers={"X-API-Key": cles["admin"]})
    assert reponse.status_code == 400
    assert "objectif" in reponse.json()["detail"]


def test_une_production_inconnue_repond_404(client, cles):
    reponse = client.get("/media/projects/prj-jamais-vu",
                         headers={"X-API-Key": cles["admin"]})
    assert reponse.status_code == 404


def test_un_chemin_hors_cadre_est_refuse_par_la_route(client, cles, racine_media):
    identite = client.post(
        "/media/projects", json={"objective": "Test"},
        headers={"X-API-Key": cles["admin"]},
    ).json()["project_id"]

    reponse = client.post(
        f"/media/projects/{identite}/analyze",
        json={"path": "../../etc/passwd"},
        headers={"X-API-Key": cles["admin"]},
    )
    assert reponse.status_code == 400
    # Le chemin est **nommé** dans le refus, pas réécrit en silence.
    assert "passwd" in reponse.json()["detail"]


def test_une_capacite_absente_repond_503_avec_ce_qui_manque(
        client, cles, racine_media):
    identite = client.post(
        "/media/projects", json={"objective": "Test"},
        headers={"X-API-Key": cles["admin"]},
    ).json()["project_id"]
    open(os.path.join(racine_media, "rush.mp4"), "wb").write(b"x")

    reponse = client.post(
        f"/media/projects/{identite}/analyze", json={"path": "rush.mp4"},
        headers={"X-API-Key": cles["admin"]},
    )
    # 503 et non 500 : la mesure est impossible **ici**, et ce qui manque est
    # nommé. Aucune durée par défaut n'est rendue.
    assert reponse.status_code == 503
    detail = reponse.json()["detail"]
    assert detail["status"] == "NOT_CONFIGURED"
    assert [m["capability"] for m in detail["missing"]] == ["media_probe"]


def test_une_demande_incomplete_rend_ses_questions_pas_un_plan(
        client, cles, racine_media):
    identite = client.post(
        "/media/projects", json={"objective": "Test"},
        headers={"X-API-Key": cles["admin"]},
    ).json()["project_id"]

    reponse = client.post(
        f"/media/projects/{identite}/plan",
        json={"request": "Rends cette vidéo plus jolie."},
        headers={"X-API-Key": cles["admin"]},
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["status"] == "CLARIFICATION_REQUIRED"
    assert corps["chain"] is None


def test_un_rendu_depose_repond_202_pas_200(client, cles, racine_media):
    identite = client.post(
        "/media/projects", json={"objective": "Test"},
        headers={"X-API-Key": cles["admin"]},
    ).json()["project_id"]

    reponse = client.post(
        f"/media/projects/{identite}/render",
        json={"output_name": "master final", "total_units": 300},
        headers={"X-API-Key": cles["admin"]},
    )
    # 202 : la file a **accepté** le travail, elle n'a rien produit.
    assert reponse.status_code == 202
    corps = reponse.json()
    assert corps["output_name"] == "master-final.webm"
    assert corps["progress"] == 0.0

    etat = client.get(f"/media/jobs/{corps['job_id']}",
                      headers={"X-API-Key": cles["admin"]})
    assert etat.json()["status"] == "running"


def test_un_rendu_sans_total_connu_rend_un_avancement_nul_pas_zero(
        client, cles, racine_media):
    identite = client.post(
        "/media/projects", json={"objective": "Test"},
        headers={"X-API-Key": cles["admin"]},
    ).json()["project_id"]

    corps = client.post(
        f"/media/projects/{identite}/render", json={"output_name": "sortie"},
        headers={"X-API-Key": cles["admin"]},
    ).json()
    assert corps["progress"] is None

    etat = client.get(f"/media/jobs/{corps['job_id']}",
                      headers={"X-API-Key": cles["admin"]}).json()
    assert etat["progress"] is None
    assert "n'est pas 0" in etat["progress_note"]


def test_une_priorite_non_declaree_est_refusee_par_la_route(
        client, cles, racine_media):
    identite = client.post(
        "/media/projects", json={"objective": "Test"},
        headers={"X-API-Key": cles["admin"]},
    ).json()["project_id"]

    reponse = client.post(
        f"/media/projects/{identite}/render",
        json={"output_name": "sortie", "priority": 99},
        headers={"X-API-Key": cles["admin"]},
    )
    assert reponse.status_code == 400
    assert "non déclarée" in reponse.json()["detail"]


def test_une_annulation_est_terminale_par_la_route(client, cles, racine_media):
    identite = client.post(
        "/media/projects", json={"objective": "Test"},
        headers={"X-API-Key": cles["admin"]},
    ).json()["project_id"]
    job = client.post(
        f"/media/projects/{identite}/render",
        json={"output_name": "sortie", "total_units": 10},
        headers={"X-API-Key": cles["admin"]},
    ).json()["job_id"]

    annulation = client.post(
        f"/media/jobs/{job}/cancel", json={"reason": "changement de brief"},
        headers={"X-API-Key": cles["admin"]},
    )
    assert annulation.status_code == 200
    assert annulation.json()["status"] == "cancelled"
    assert annulation.json()["does_not"]

    etat = client.get(f"/media/jobs/{job}",
                      headers={"X-API-Key": cles["admin"]}).json()
    assert etat["can_retry"] is False


def test_annuler_un_travail_inconnu_repond_404(client, cles):
    reponse = client.post("/media/jobs/job-jamais-vu/cancel", json={},
                          headers={"X-API-Key": cles["admin"]})
    assert reponse.status_code == 404


def test_les_capacites_media_sont_publiees_mesurees(client, cles, racine_media):
    reponse = client.get("/media/capabilities",
                         headers={"X-API-Key": cles["admin"]})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["capabilities"]["state"] in ("AVAILABLE", "DEGRADED",
                                              "UNAVAILABLE")
    assert corps["tools"]["count"] == 16
    assert corps["boundary"]["allowed_extensions"]
    # L'aptitude est calculée sur les 17 étapes de §40 et nomme ce qui manque.
    assert sum(corps["readiness"]["counts"].values()) == 17
    assert "PENDING" in corps["readiness"]["state"]


def test_une_cle_en_lecture_seule_ne_lance_aucun_rendu(client, cles, racine_media):
    reponse = client.post(
        "/media/projects/prj-x/render", json={"output_name": "sortie"},
        headers={"X-API-Key": cles["readonly"]},
    )
    # Refusé sur la permission, avant même de savoir si la production existe.
    assert reponse.status_code == 403
