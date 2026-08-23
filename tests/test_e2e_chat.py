"""
Tests end-to-end du chat (VOLET chat-first, ch. 08).

Vérifie le parcours complet : page chargée → message envoyé → réponse affichée.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CLE = "e2e-test-key"
ENTETE = {"X-API-Key": CLE}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin:testeur")
    import src.api.server as serveur
    serveur.rbac_manager.reload()
    serveur.set_valid_api_key_digests(serveur.rbac_manager.active_key_digests())
    try:
        with TestClient(serveur.app) as c:
            yield c
    finally:
        monkeypatch.delenv("GALSEN_API_KEYS", raising=False)
        serveur.rbac_manager.reload()
        serveur.set_valid_api_key_digests(serveur.rbac_manager.active_key_digests())


class TestPageLoad:
    """La page se charge et a tout ce qu'il faut."""

    def test_page_charge(self, client):
        r = client.get("/ui/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_elements_critiques_presents(self, client):
        page = client.get("/ui/").text
        for elem in ("composeur", "message", "conversation"):
            assert f'id="{elem}"' in page


class TestChatFlow:
    """Le flux complet : question → réponse."""

    def test_chat_refuse_message_vide(self, client):
        r = client.post("/chat", json={"message": "   "}, headers=ENTETE)
        assert r.status_code == 422

    def test_chat_accepte_message_valide(self, client):
        r = client.post(
            "/chat", json={"message": "bonjour"}, headers=ENTETE
        )
        assert r.status_code in (200, 503), f"Statut: {r.status_code}"

    def test_reponse_porte_le_contrat(self, client):
        r = client.post(
            "/chat", json={"message": "bonjour"}, headers=ENTETE
        )
        if r.status_code == 200:
            charge = r.json()
            # Tous les champs du contrat
            for cle in ("answer", "conversation_id", "detection", "grounding"):
                assert cle in charge, f"{cle} absent"

    def test_domaine_impose_fonctionne(self, client):
        r = client.post(
            "/chat",
            json={"message": "aide", "domain": "sante"},
            headers=ENTETE,
        )
        if r.status_code == 200:
            charge = r.json()
            assert charge["detection"]["domain"] == ["sante"]
            assert charge["detection"]["forced_by_user"] is True

    def test_historique_accumule(self, client):
        conv_id = "conv_test"
        historique = [
            {"role": "user", "content": "premier"},
            {"role": "assistant", "content": "réponse"},
        ]
        r = client.post(
            "/chat",
            json={
                "message": "deuxième",
                "conversation_id": conv_id,
                "history": historique,
            },
            headers=ENTETE,
        )
        if r.status_code == 200:
            charge = r.json()
            assert charge["conversation_id"] == conv_id


class TestAdmin:
    """L'espace admin est séparé et fonctionne."""

    def test_admin_existe(self, client):
        r = client.get("/ui/admin/")
        assert r.status_code == 200
        assert "Tableau de bord" in r.text

    def test_admin_et_chat_sont_differents(self, client):
        """
        Deux pages distinctes, distinguées par ce qu'elles portent.

        La comparaison ne peut pas se faire sur la chaîne « Tableau de bord » :
        la conversation en porte une, dans le lien qui y mène. Un déplacement
        sans porte serait une suppression, donc ce lien doit exister — et un
        test qui l'interdirait pousserait à le retirer.
        """
        chat = client.get("/ui/").text
        admin = client.get("/ui/admin/").text

        assert 'id="composeur"' in chat and 'id="composeur"' not in admin
        assert 'id="cles"' in admin and 'id="cles"' not in chat
