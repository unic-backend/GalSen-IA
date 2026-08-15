"""
`/health` connaît enfin la moitié récente de la plateforme (phase 65.2).

Le rapport de santé couvrait sept composants — API, mémoire, modèles,
connaissance, outils, stockage, connecteurs — tous d'avant le VOLET 47. Les neuf
sous-systèmes construits ensuite n'y figuraient nulle part : un exploitant
pouvait lire `healthy` pendant que les routines, les greffons, la connaissance
mondiale ou l'orchestration étaient inutilisables.

Ce que ces tests gardent :

1. **Les sous-systèmes sont rapportés**, dans leur propre section.
2. **Une dégradation ne fait pas basculer le statut global.** Un canal externe
   sans identifiants est l'état normal de cette installation ; le compter comme
   une panne allumerait une alarme que plus personne ne lirait.
3. **Une dégradation ne rend pas la plateforme non prête.** C'est le titre même
   du VOLET : un moteur absent ne fait rien tomber.
4. **`/health` ne tombe pas** parce que la section refuse de se calculer.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.integration.degradation import DEGRADE, INDISPONIBLE, SOUS_SYSTEMES  # noqa: E402


@pytest.fixture
def client_sante(monkeypatch):
    """Client HTTP portant une clé nommée sur chaque appel."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    with TestClient(server_module.app, headers={"X-API-Key": "cle-awa"}) as essai:
        yield essai
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


# ----------------------------------------------------------------------
# 1. Les sous-systèmes sont là
# ----------------------------------------------------------------------

def test_la_sante_rapporte_les_sous_systemes(client_sante):
    """Ils n'apparaissaient dans aucun rapport avant cette phase."""
    sante = client_sante.get("/health?subsystems=true").json()

    assert "subsystems" in sante
    assert set(sante["subsystems"]["subsystems"]) == set(SOUS_SYSTEMES)


def test_la_route_dediee_publie_le_meme_rapport(client_sante):
    """Un exploitant qui ne veut que cela n'a pas à lire tout `/health`."""
    rapport = client_sante.get("/system/degradation").json()

    assert set(rapport["subsystems"]) == set(SOUS_SYSTEMES)
    assert rapport["counts"][INDISPONIBLE] == 0


def test_chaque_etat_dit_ce_qui_marche_encore_sans_lui(client_sante):
    """C'est ce qui distingue un rapport utile d'une liste de voyants."""
    rapport = client_sante.get("/system/degradation").json()

    for nom, etat in rapport["subsystems"].items():
        assert etat["still_works_without"], nom


# ----------------------------------------------------------------------
# 2. Dégradé ne fait pas basculer le statut global
# ----------------------------------------------------------------------

def test_une_degradation_ne_change_pas_le_statut_global(client_sante, monkeypatch):
    """Une alarme toujours allumée n'est plus lue."""
    avant = client_sante.get("/health?subsystems=true").json()["status"]

    monkeypatch.setitem(
        SOUS_SYSTEMES["plugins"], "probe",
        lambda: {"state": DEGRADE, "reason": "bac à sable absent", "detail": {}},
    )
    apres = client_sante.get("/health?subsystems=true").json()

    assert apres["status"] == avant
    assert apres["subsystems"]["degraded"] == ["plugins"]


def test_un_sous_systeme_en_panne_est_visible_sans_faire_tomber_la_sante(
    client_sante, monkeypatch
):
    """Rapporté, pas propagé — la règle de tout le VOLET."""
    def _casse():
        raise RuntimeError("panne franche")

    monkeypatch.setitem(SOUS_SYSTEMES["plugins"], "probe", _casse)

    sante = client_sante.get("/health?subsystems=true").json()

    assert sante["subsystems"]["unavailable"] == ["plugins"]
    assert sante["status"] in ("healthy", "degraded")


# ----------------------------------------------------------------------
# 3. Rien ne tombe
# ----------------------------------------------------------------------

def test_une_degradation_ne_rend_pas_la_plateforme_non_prete(client_sante, monkeypatch):
    """« Un moteur absent ne fait rien tomber » : c'est le titre du VOLET."""
    monkeypatch.setitem(
        SOUS_SYSTEMES["world_knowledge"], "probe",
        lambda: {"state": DEGRADE, "reason": "jamais construite", "detail": {}},
    )

    assert client_sante.get("/ready").status_code == 200


def test_la_sante_ne_tombe_pas_si_la_section_refuse_de_se_calculer(
    client_sante, monkeypatch
):
    """Une section qui échoue ne doit pas emporter le rapport entier."""
    import src.integration.degradation as module

    def _casse(*args, **kwargs):
        raise RuntimeError("registre illisible")

    monkeypatch.setattr(module, "degradation_report", _casse)

    sante = client_sante.get("/health?subsystems=true")

    assert sante.status_code == 200
    # La section est absente plutôt que rendue vide : « pas mesuré » et « rien
    # à signaler » ne sont pas la même chose.
    assert "subsystems" not in sante.json()
    assert sante.json()["status"] in ("healthy", "degraded", "unhealthy")


def test_la_sante_reste_publique(client_sante):
    """L'ajout ne referme pas une route qui ne l'était pas."""
    assert client_sante.get("/health").status_code == 200


# ----------------------------------------------------------------------
# 4. Ce que la mesure a imposé
# ----------------------------------------------------------------------

def test_la_sante_par_defaut_ne_sonde_pas_les_sous_systemes(client_sante):
    """
    Mesuré : sonder les neuf coûte ~70 ms, la cible de supervision est 50 ms.

    Une supervision qui interroge `/health` toutes les cinq secondes paierait
    ce prix sans arrêt pour une information qui change quelques fois par mois.
    La section est donc **demandée**, pas subie.
    """
    sante = client_sante.get("/health").json()

    assert "subsystems" not in sante


def test_le_rapport_de_degradation_exige_une_cle():
    """Il nomme les dépendances internes et la cause de chaque manque."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module

    with TestClient(server_module.app) as anonyme:
        assert anonyme.get("/system/degradation").status_code in (401, 403)
        # `/health` reste la porte publique : c'est elle que sonde un
        # orchestrateur, et elle ne dit rien d'interne.
        assert anonyme.get("/health").status_code == 200
