"""
Le journal des routines et leurs routes (phase 47.3).

Une routine tourne sans personne devant : le journal est **le seul endroit** où
quelqu'un apprendra un jour ce qu'elle a fait. D'où une exigence dure et une
façon facile de la trahir.

L'exigence : rester borné. Une routine horaire produit neuf mille entrées par
an, et un journal qui grossit sans fin est un journal que quelqu'un tronquera en
manquant de disque — en perdant justement les preuves les plus anciennes.

La trahison : ne garder que les N derniers tours fait paraître saine une routine
cassée. Échouer lundi, réussir vingt fois d'ici jeudi, et le journal ne montre
plus que des succès pendant que l'échec qui comptait a défilé. **Les compteurs
survivent donc à l'oubli des entrées.**

Les routes tiennent une dernière règle : une routine inconnue et une routine
appartenant à quelqu'un d'autre rendent **le même 404**. Dire « elle existe mais
elle n'est pas à vous » renseignerait sur ce qu'une autre personne surveille.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.routines import (  # noqa: E402
    TOURS_CONSERVES,
    ActionOutcome,
    RoutineJournal,
    RoutineRegistry,
    RoutineRun,
)

HEURE = 3600


def _tour(routine_id="veille", ok=True, instant=0.0, saute="", arret=False):
    """Un compte rendu de tour, réussi ou non."""
    actions = [] if saute else [ActionOutcome(
        tool_id="metrics",
        status="success" if ok else "error",
        detail="" if ok else "service indisponible",
    )]
    return RoutineRun(
        routine_id=routine_id, started_at=instant, actions=actions,
        skipped=saute, disabled_after=arret,
    )


@pytest.fixture
def journal():
    """Un journal vide."""
    return RoutineJournal()


# ----------------------------------------------------------------------
# 1. Borné, mais pas amnésique
# ----------------------------------------------------------------------

def test_le_journal_reste_borne(journal):
    """Un journal qui grossit sans fin est un journal que quelqu'un tronque."""
    for numero in range(TOURS_CONSERVES + 40):
        journal.record(_tour(instant=numero))

    assert len(journal.runs("veille", limit=1000)) == TOURS_CONSERVES


def test_les_compteurs_survivent_a_l_oubli_des_entrees(journal):
    """
    Le test qui justifie ce module. L'échec du premier tour a défilé ; le
    compteur, lui, est toujours là.
    """
    journal.record(_tour(ok=False, instant=0))
    for numero in range(1, TOURS_CONSERVES + 20):
        journal.record(_tour(ok=True, instant=numero))

    tours = journal.runs("veille", limit=1000)
    stats = journal.stats("veille")

    assert all(tour["ok"] for tour in tours), "L'échec devrait avoir défilé"
    assert stats["failures"] == 1
    assert stats["last_failure_at"] == 0
    assert "indisponible" in stats["last_failure_detail"]


def test_le_taux_de_reussite_est_calcule_sur_tout_l_historique(journal):
    """Pas seulement sur ce qui reste affiché."""
    for numero in range(3):
        journal.record(_tour(ok=False, instant=numero))
    for numero in range(3, 10):
        journal.record(_tour(ok=True, instant=numero))

    stats = journal.stats("veille")

    assert stats["runs"] == 10
    assert stats["failures"] == 3
    assert stats["success_rate"] == 0.7


def test_une_routine_sans_tour_n_a_pas_de_taux(journal):
    """
    `None` et non `1.0` : une routine qui n'a jamais tourné n'a pas un succès
    parfait, elle n'a pas de taux.
    """
    assert journal.stats("jamais-tournee") is None

    journal.record(_tour(saute="tour précédent en cours"))
    assert journal.stats("veille")["success_rate"] == 0.0


def test_un_tour_saute_est_compte_a_part(journal):
    """Il n'a rien fait : le confondre avec un échec d'outil serait faux."""
    journal.record(_tour(saute="tour précédent en cours"))

    stats = journal.stats("veille")

    assert stats["skipped"] == 1
    assert stats["failures"] == 1
    assert "tour précédent" in stats["last_failure_detail"]


def test_l_arret_automatique_est_date(journal):
    """Savoir *quand* une routine s'est tue est ce qui permet de la reprendre."""
    journal.record(_tour(ok=False, instant=42, arret=True))

    assert journal.stats("veille")["disabled_at"] == 42


def test_les_tours_sont_rendus_du_plus_recent_au_plus_ancien(journal):
    """C'est l'ordre dans lequel on cherche ce qui vient de casser."""
    for numero in range(5):
        journal.record(_tour(instant=numero))

    tours = journal.runs("veille", limit=3)

    assert [tour["started_at"] for tour in tours] == [4, 3, 2]


def test_le_journal_ne_garde_pas_ce_qu_une_routine_a_lu(journal):
    """Un journal n'est pas un magasin de données."""
    journal.record(_tour())

    serialise = str(journal.runs("veille"))

    assert "result" not in serialise
    assert "body" not in serialise


# ----------------------------------------------------------------------
# 2. Le journal se filtre comme les routines
# ----------------------------------------------------------------------

def test_le_journal_d_une_personne_n_est_pas_lisible_par_une_autre(journal):
    """Le journal de quelqu'un dit ce qu'il surveille."""
    journal.record(_tour(routine_id="a-fatou"), subject="fatou")

    assert journal.runs("a-fatou", subject="moussa") == []
    assert journal.stats("a-fatou", subject="moussa") is None
    assert journal.stats("a-fatou", subject="fatou") is not None


def test_le_journal_d_une_routine_de_plateforme_est_commun(journal):
    """Elle n'appartient à personne : son journal non plus."""
    journal.record(_tour(routine_id="commune"), subject=None)

    assert journal.stats("commune", subject="moussa") is not None
    assert journal.stats("commune") is not None


def test_le_rapport_ne_montre_que_ce_qui_est_visible(journal):
    """Y compris dans le décompte."""
    journal.record(_tour(routine_id="commune"), subject=None)
    journal.record(_tour(routine_id="a-fatou", ok=False), subject="fatou")

    vue_moussa = journal.journal_report(subject="moussa")
    vue_fatou = journal.journal_report(subject="fatou")

    assert vue_moussa["routines"] == 1
    assert vue_fatou["routines"] == 2
    assert vue_fatou["failing"] == ["a-fatou"]
    assert "a-fatou" not in str(vue_moussa)


# ----------------------------------------------------------------------
# 3. Les routes
# ----------------------------------------------------------------------

@pytest.fixture
def cles(monkeypatch):
    """Deux clés nommées, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv(
        "GALSEN_API_KEYS", "cle-fatou:admin:fatou,cle-moussa:user:moussa"
    )
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield {"fatou": "cle-fatou", "moussa": "cle-moussa"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def routines_neuves(monkeypatch):
    """Un registre et un journal propres pour ce test."""
    monkeypatch.setattr(server_module, "routine_registry", RoutineRegistry())
    monkeypatch.setattr(server_module, "routine_journal", RoutineJournal())
    monkeypatch.setattr(server_module, "_routine_scheduler", None)


@pytest.fixture
def client():
    """Client HTTP sur l'application réelle."""
    with TestClient(app) as essai:
        yield essai


def _declarer(client, cle, identifiant="veille", outil="metrics", operation="read",
              intervalle=HEURE):
    """Déclare une routine par l'API."""
    return client.post("/routines", headers={"X-API-Key": cle}, json={
        "routine_id": identifiant,
        "description": "Surveiller les métriques chaque heure",
        "actions": [{"tool_id": outil, "operation": operation}],
        "interval_seconds": intervalle,
    })


def test_une_routine_declaree_par_l_api_nait_desactivee(client, cles, routines_neuves):
    """Écrire et faire tourner sont deux décisions."""
    reponse = _declarer(client, cles["fatou"])

    assert reponse.status_code == 201
    assert reponse.json()["enabled"] is False
    assert reponse.json()["subject"] == "fatou"


def test_le_proprietaire_vient_de_la_cle(client, cles, routines_neuves):
    """Déclarer au nom de quelqu'un d'autre ne doit pas être formulable."""
    reponse = client.post("/routines", headers={"X-API-Key": cles["fatou"]}, json={
        "routine_id": "detournee", "description": "Essai",
        "actions": [{"tool_id": "metrics", "operation": "read"}],
        "interval_seconds": HEURE, "subject": "moussa",
    })

    assert reponse.json()["subject"] == "fatou"


def test_une_routine_refusee_dit_pourquoi(client, cles, routines_neuves):
    """`terminal` hors de sa borne exige une approbation ; une routine n'en a pas."""
    reponse = client.post("/routines", headers={"X-API-Key": cles["fatou"]}, json={
        "routine_id": "dangereuse", "description": "Essai",
        "actions": [{"tool_id": "terminal", "operation": ["python", "-c", "1"]}],
        "interval_seconds": HEURE,
    })

    assert reponse.status_code == 400
    assert "approbation humaine" in reponse.json()["detail"]


def test_une_personne_ne_voit_pas_les_routines_d_une_autre(client, cles, routines_neuves):
    """La liste de ce que quelqu'un surveille dit quelque chose de lui."""
    _declarer(client, cles["fatou"], identifiant="a-fatou")

    vues = client.get("/routines", headers={"X-API-Key": cles["moussa"]}).json()

    assert [r["routine_id"] for r in vues["routines"]] == []


def test_activer_la_routine_d_une_autre_rend_le_meme_404_qu_une_inconnue(
    client, cles, routines_neuves
):
    """
    Dire « elle existe mais elle n'est pas à vous » renseignerait sur ce qu'une
    autre personne surveille.
    """
    _declarer(client, cles["fatou"], identifiant="a-fatou")

    autre = client.post(
        "/routines/a-fatou/enable", headers={"X-API-Key": cles["moussa"]}
    )
    inconnue = client.post(
        "/routines/jamais-vue/enable", headers={"X-API-Key": cles["moussa"]}
    )

    assert autre.status_code == inconnue.status_code == 404
    # Le message ne diffère que par l'identifiant que l'appelant a lui-même
    # fourni : il n'apprend donc rien. Comparer les chaînes entières serait
    # trop fort — c'est la **forme** du message qui ne doit pas trahir.
    assert (autre.json()["detail"].replace("a-fatou", "X")
            == inconnue.json()["detail"].replace("jamais-vue", "X"))


def test_activer_puis_arreter_fonctionne(client, cles, routines_neuves):
    """Une routine qu'on ne peut pas arrêter est pire qu'une routine absente."""
    _declarer(client, cles["fatou"])

    active = client.post("/routines/veille/enable", headers={"X-API-Key": cles["fatou"]})
    arretee = client.post("/routines/veille/disable", headers={"X-API-Key": cles["fatou"]})

    assert active.json()["enabled"] is True
    assert arretee.json()["enabled"] is False


def test_aucune_boucle_ne_tourne_d_elle_meme(client, cles, routines_neuves):
    """
    Une plateforme qui se met à déclencher des routines au démarrage, sans que
    personne l'ait demandé, est ce qu'un moteur de routines ne doit pas être.
    """
    _declarer(client, cles["fatou"])
    client.post("/routines/veille/enable", headers={"X-API-Key": cles["fatou"]})

    etat = client.get("/routines/status", headers={"X-API-Key": cles["fatou"]}).json()

    assert etat["due_now"] == ["veille"]
    assert server_module.routine_journal.stats("veille") is None


def test_le_declenchement_est_reserve_a_l_administration(client, cles, routines_neuves):
    """Déclencher toutes les routines dues est un acte d'exploitation."""
    reponse = client.post("/routines/tick", headers={"X-API-Key": cles["moussa"]})

    assert reponse.status_code == 403


def test_un_tour_declenche_est_consigne(client, cles, routines_neuves):
    """Le journal est le seul endroit où l'on apprendra ce qui s'est passé."""
    _declarer(client, cles["fatou"])
    client.post("/routines/veille/enable", headers={"X-API-Key": cles["fatou"]})

    tick = client.post("/routines/tick", headers={"X-API-Key": cles["fatou"]})

    assert tick.json()["count"] == 1
    journal = client.get(
        "/routines/veille/journal", headers={"X-API-Key": cles["fatou"]}
    ).json()
    assert journal["stats"]["runs"] == 1


def test_le_journal_d_une_routine_sans_tour_repond_404(client, cles, routines_neuves):
    """Rendre des compteurs à zéro laisserait croire qu'elle a tourné."""
    _declarer(client, cles["fatou"])

    reponse = client.get(
        "/routines/veille/journal", headers={"X-API-Key": cles["fatou"]}
    )

    assert reponse.status_code == 404


def test_les_routes_de_routines_exigent_une_cle(client, routines_neuves):
    """Aucune n'est publique."""
    for methode, route in (
        ("get", "/routines"), ("get", "/routines/status"),
        ("post", "/routines/tick"),
    ):
        reponse = getattr(client, methode)(route)
        assert reponse.status_code in (401, 403), route
