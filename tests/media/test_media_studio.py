"""
Tests for the Media Studio (§34).

The tests that matter here are not about layout. A studio is easy to fake — a
black frame with a play button, a timeline of coloured blocks, a progress bar
that climbs — and every one of those reads, to the person looking at it, as a
capability the platform has. So what is pinned is that each zone is driven by
what the server **measured**, and that the decorative version was not built.

The JavaScript itself is not executed here: ADR-008 already states that gap and
makes it the signal that will justify a JS test runner. What these tests can
check is the source and the contract it depends on — which is exactly where a
studio starts lying.
"""

import os
import re

import pytest

from src.web import STATIC_DIRECTORY

STUDIO_JS = os.path.join(STATIC_DIRECTORY, "js", "studio.js")
STUDIO_HTML = os.path.join(STATIC_DIRECTORY, "studio.html")
CLIENT_JS = os.path.join(STATIC_DIRECTORY, "js", "api-client.js")


def _lire(chemin: str) -> str:
    """Lit un fichier livré."""
    with open(chemin, encoding="utf-8") as fichier:
        return fichier.read()


@pytest.fixture(scope="module")
def studio() -> str:
    """Le source du studio."""
    return _lire(STUDIO_JS)


@pytest.fixture(scope="module")
def page() -> str:
    """La page du studio."""
    return _lire(STUDIO_HTML)


# --------------------------------------------------------------------------
# Les cinq zones de §34
# --------------------------------------------------------------------------


def test_les_cinq_zones_de_la_directive_existent(page):
    for zone in ("studio-haut", "studio-gauche", "studio-centre",
                 "studio-droite", "studio-bas"):
        assert zone in page, zone


def test_la_page_porte_les_points_de_montage_du_script(page, studio):
    # Un identifiant présent dans le script et absent de la page produit une
    # zone qui ne se remplit jamais, sans erreur visible.
    for identifiant in re.findall(r'\$\("#([a-z-]+)"\)', studio):
        assert f'id="{identifiant}"' in page, identifiant


def test_la_grille_s_empile_sur_un_telephone():
    css = _lire(os.path.join(STATIC_DIRECTORY, "css", "studio.css"))
    assert "@media (max-width: 900px)" in css
    assert "grid-template-areas" in css


# --------------------------------------------------------------------------
# Ce que le studio refuse de dessiner
# --------------------------------------------------------------------------


def test_aucun_lecteur_video_n_est_pose_sur_un_fichier_inexistant(page, studio):
    # Un cadre noir avec un bouton de lecture est la façon la plus efficace de
    # faire croire qu'une vidéo a été produite.
    assert "<video" not in page
    assert "<video" not in studio


def test_l_apercu_nomme_la_capacite_manquante(studio):
    assert "missing_capabilities" in studio
    assert "Un lecteur vide affiché ici se lirait comme une vidéo produite." in studio


def test_la_timeline_reste_vide_tant_que_rien_n_est_mesure(studio):
    assert "piste-vide" in studio
    assert "se liraient comme des plans détectés" in studio


def test_un_avancement_inconnu_n_est_pas_affiche_en_zero(studio):
    # `0 %` se lirait comme un travail commencé.
    assert "travail.progress === null" in studio
    assert "Avancement : inconnu" in studio


def test_les_questions_d_une_demande_incomplete_sont_affichees(studio):
    assert "CLARIFICATION_REQUIRED" in studio
    assert "Aucun n'est choisi à votre place" in studio


def test_l_etat_d_aptitude_vient_du_serveur_pas_du_script(studio):
    # Le verdict est calculé côté serveur sur les dix-sept étapes ; le studio
    # l'affiche. Une chaîne écrite ici en dur dirait la même chose pour
    # toujours.
    assert "readiness.state" in studio
    assert "ENGINE READY" not in studio


def test_les_etats_affiches_viennent_de_la_reponse(studio):
    # Chaque état montré est lu dans la réponse du serveur. Une comparaison
    # (`=== "AVAILABLE"`) choisit une couleur ; elle n'écrit pas l'état.
    assert "detail.state" in studio
    assert "etape.state" in studio
    assert "travail.status" in studio


# --------------------------------------------------------------------------
# Le contrat avec l'API
# --------------------------------------------------------------------------


def test_le_studio_passe_par_le_client_d_api(studio):
    assert 'from "./api-client.js"' in studio
    assert "fetch(" not in studio


def test_le_client_expose_les_routes_media_reellement_servies():
    from src.api.server import app

    client = _lire(CLIENT_JS)
    chemins = {getattr(route, "path", "") for route in app.routes}

    for litteral in ("/media/capabilities", "/media/projects"):
        assert litteral in client
        assert litteral in chemins

    # Les routes paramétrées sont écrites en gabarit dans le client : on
    # vérifie que leur forme servie existe, pas la chaîne interpolée.
    for parametree in ("/media/projects/{project_id}", "/media/jobs/{job_id}",
                       "/media/jobs/{job_id}/cancel"):
        assert parametree in chemins


def test_le_studio_est_atteignable_depuis_le_tableau_de_bord():
    # Une page qu'on ne peut pas atteindre n'existe pas pour celui qui l'utilise.
    accueil = _lire(os.path.join(STATIC_DIRECTORY, "index.html"))
    assert "/ui/studio.html" in accueil
