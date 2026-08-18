"""
Tests des routes du Coding Engine (ADR-028).

Une route qui répond 200 pour une indisponibilité fait passer une absence de
travail pour un résultat. Le défaut existait déjà sur `/agri/advice` et avait
coûté un aller-retour complet ; ces tests l'empêchent de revenir ici.

Aucun moteur externe n'est installé pendant la suite, ce qui est précisément le
cas à éprouver : la plateforme doit répondre proprement, avec le geste qui
répare, plutôt que planter ou mentir.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CLE = "cle-de-test-coding"
ENTETE = {"X-API-Key": CLE}


@pytest.fixture
def client(monkeypatch):
    """
    Client API avec une clé d'administration, sans recharger aucun module.

    Le RBAC lit `GALSEN_API_KEYS` à la construction, mais il expose `reload()` :
    c'est cette voie qui est prise ici. Un `importlib.reload` du module aurait
    remplacé la classe `Role` par une nouvelle, et les suites voisines qui
    comparent `role is Role.ADMIN` auraient échoué — c'est arrivé, et c'est
    exactement pourquoi ce chemin est évité.
    """
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin:testeur")
    for variable in ("GALSEN_AIDER_BIN", "GALSEN_SWE_AGENT_BIN", "GALSEN_OPENHANDS_URL"):
        monkeypatch.delenv(variable, raising=False)

    import src.api.server as serveur
    serveur.rbac_manager.reload()
    serveur.set_valid_api_key_digests(serveur.rbac_manager.active_key_digests())
    try:
        with TestClient(serveur.app) as client:
            yield client
    finally:
        # L'environnement est restauré par monkeypatch ; le gestionnaire, lui,
        # garde la clé en mémoire jusqu'à ce qu'on le relise.
        monkeypatch.delenv("GALSEN_API_KEYS", raising=False)
        serveur.rbac_manager.reload()
        serveur.set_valid_api_key_digests(serveur.rbac_manager.active_key_digests())


@pytest.fixture
def espace(tmp_path):
    """Un espace de travail réel, sur disque."""
    espace = tmp_path / "projet"
    espace.mkdir()
    (espace / "module.py").write_text("x = 1\n", encoding="utf-8")
    return str(espace)


class TestEtatDesMoteurs:
    """`/coding/engines` doit dire ce qui manque et comment le réparer."""

    def test_la_cle_est_exigee(self, client):
        """Ces routes lancent des programmes : elles ne sont pas publiques."""
        assert client.get("/coding/engines").status_code == 401

    def test_les_trois_moteurs_sont_decrits(self, client):
        """Un moteur absent doit apparaître, pas disparaître de la liste."""
        charge = client.get("/coding/engines", headers=ENTETE).json()
        assert {e["engine_id"] for e in charge["engines"]} == {
            "aider", "swe_agent", "openhands"
        }

    def test_chaque_moteur_absent_porte_un_motif_actionnable(self, client):
        """« indisponible » sans mode d'emploi ne fait avancer personne."""
        for moteur in client.get("/coding/engines", headers=ENTETE).json()["engines"]:
            if not moteur["available"]:
                assert moteur["reason"]
                assert moteur["detail"]

    def test_la_politique_de_conteneur_est_visible(self, client):
        """L'exploitant doit pouvoir vérifier que sa contrainte est bien lue."""
        charge = client.get("/coding/engines", headers=ENTETE).json()
        assert "container_required" in charge
        assert "in_container" in charge


class TestSoumissionDeTache:
    """`/coding/task` : le code HTTP doit suivre le sort réel de la tâche."""

    def _tache(self, espace, **extras) -> dict:
        """Corps de requête minimal."""
        corps = {"instruction": "Modifie module.py", "workspace": espace}
        corps.update(extras)
        return corps

    def test_la_cle_est_exigee(self, client, espace):
        """Sans elle, n'importe qui ferait tourner un moteur sur le disque."""
        assert client.post("/coding/task", json=self._tache(espace)).status_code == 401

    def test_une_instruction_vide_est_refusee(self, client, espace):
        """Rien à faire n'est pas une tâche."""
        reponse = client.post(
            "/coding/task", json=self._tache(espace, instruction="   "), headers=ENTETE
        )
        assert reponse.status_code == 422

    def test_aucun_moteur_disponible_donne_503(self, client, espace):
        """Répondre 200 ferait passer une indisponibilité pour un résultat.

        C'est exactement le défaut qu'`/agri/advice` avait : une réponse vide
        avec un code de succès.
        """
        reponse = client.post("/coding/task", json=self._tache(espace), headers=ENTETE)
        assert reponse.status_code == 503
        assert reponse.json()["detail"]["status"] == "unavailable"

    def test_un_espace_inexistant_donne_422(self, client, tmp_path):
        """Le confinement s'applique avant tout choix de moteur."""
        reponse = client.post(
            "/coding/task",
            json=self._tache(str(tmp_path / "absent")),
            headers=ENTETE,
        )
        assert reponse.status_code == 422

    def test_une_instruction_destructrice_donne_403(self, client, espace):
        """Refusée sans recours : ce n'est ni un échec ni une indisponibilité."""
        reponse = client.post(
            "/coding/task",
            json=self._tache(espace, instruction="fais un rm -rf / complet"),
            headers=ENTETE,
        )
        assert reponse.status_code == 403
        assert reponse.json()["detail"]["status"] == "rejected"

    def test_une_instruction_sensible_donne_202_et_une_demande(self, client, espace):
        """202 dit « pris en compte, en attente » — ni succès ni échec."""
        reponse = client.post(
            "/coding/task",
            json=self._tache(espace, instruction="git push origin main"),
            headers=ENTETE,
        )
        assert reponse.status_code == 202
        assert reponse.json()["detail"]["approval_request_id"]

    def test_la_demande_arrive_dans_la_file_d_approbation(self, client, espace):
        """Elle doit être visible par les routes d'approbation existantes."""
        client.post(
            "/coding/task",
            json=self._tache(espace, instruction="git push origin main"),
            headers=ENTETE,
        )
        pendantes = client.get("/approval/pending", headers=ENTETE).json()
        contenu = str(pendantes)
        assert "coding" in contenu

    def test_un_moteur_inconnu_est_signale(self, client, espace):
        """Une faute de frappe ne doit pas basculer vers un autre moteur."""
        reponse = client.post(
            "/coding/task", json=self._tache(espace, engine_id="aidre"), headers=ENTETE
        )
        assert reponse.status_code == 503
        assert "aider" in reponse.json()["detail"]["summary"]

    def test_un_delai_hors_bornes_est_refuse_par_le_schema(self, client, espace):
        """La borne est déclarée dans le modèle, pas seulement dans le moteur."""
        reponse = client.post(
            "/coding/task", json=self._tache(espace, timeout_seconds=99999), headers=ENTETE
        )
        assert reponse.status_code == 422

    def test_la_reponse_porte_la_forme_normalisee(self, client, espace):
        """L'appelant lit toujours la même structure, quel que soit le moteur."""
        charge = client.post(
            "/coding/task", json=self._tache(espace), headers=ENTETE
        ).json()["detail"]
        assert set(charge) >= {
            "status", "ok", "engine_id", "task_id", "summary", "files_changed",
            "tests", "errors", "warnings", "execution_time_seconds", "audit_id",
        }
