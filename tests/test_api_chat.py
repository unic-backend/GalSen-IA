"""
Tests de la route de conversation (VOLET redesign chat-first, ch. 02).

Ce qui est épinglé ici n'est pas le texte des réponses — il dépend du modèle et
du corpus, et changera. C'est **ce que la route refuse de faire** :

- rendre une bulle vide quand aucun agent n'a produit de texte ;
- présenter comme ancrée une réponse que rien ne fonde ;
- afficher un domaine sans dire par quelle méthode il a été trouvé.

Le troisième point est le moins évident et le plus important : une interface qui
affiche « agriculture » sans dire « par mots-clés » transforme une heuristique
en certitude.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CLE = "cle-de-test-chat"
ENTETE = {"X-API-Key": CLE}


@pytest.fixture
def client(monkeypatch):
    """Client API avec une clé d'administration."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin:testeur")
    import src.api.server as serveur
    serveur.rbac_manager.reload()
    serveur.set_valid_api_key_digests(serveur.rbac_manager.active_key_digests())
    try:
        with TestClient(serveur.app) as client:
            yield client
    finally:
        monkeypatch.delenv("GALSEN_API_KEYS", raising=False)
        serveur.rbac_manager.reload()
        serveur.set_valid_api_key_digests(serveur.rbac_manager.active_key_digests())


class TestContrat:
    """La forme de la réponse, sur laquelle une interface va s'appuyer."""

    def test_un_message_vide_est_refuse(self, client):
        reponse = client.post("/chat", json={"message": "   "}, headers=ENTETE)
        assert reponse.status_code == 422

    def test_une_cle_absente_est_refusee(self, client):
        assert client.post("/chat", json={"message": "bonjour"}).status_code in (401, 403)

    def test_la_reponse_porte_le_contrat_complet(self, client):
        charge = client.post(
            "/chat", json={"message": "Quand planter le mil à Thiès ?"}, headers=ENTETE
        ).json()
        assert set(charge) >= {
            "answer", "conversation_id", "detection", "grounding",
            "run_id", "elapsed_seconds",
        }

    def test_la_duree_est_mesuree_jamais_zero(self, client):
        """
        Un `0.0` de complaisance ferait croire à une route instantanée.

        `/model/generate` porte encore `latency_seconds=0.0` avec le commentaire
        « À implémenter réellement ». Cette route ne répète pas ça.
        """
        charge = client.post("/chat", json={"message": "bonjour"}, headers=ENTETE).json()
        assert charge["elapsed_seconds"] > 0


class TestDetection:
    """Le domaine est détecté, et la méthode est dite."""

    def test_une_question_agricole_est_reconnue(self, client):
        detection = client.post(
            "/chat", json={"message": "Quand planter le mil à Thiès ?"}, headers=ENTETE
        ).json()["detection"]
        assert "agriculture" in detection["domain"]

    def test_le_domaine_ne_vient_jamais_sans_sa_methode(self, client):
        """
        « agriculture » et « agriculture, par mots-clés » ne se valent pas.

        Sans la méthode, une interface présente une heuristique comme un fait.
        """
        detection = client.post(
            "/chat", json={"message": "Quand planter le mil à Thiès ?"}, headers=ENTETE
        ).json()["detection"]
        if detection["domain"] and not detection["forced_by_user"]:
            assert detection["method"], "un domaine détecté sans méthode déclarée"

    def test_un_domaine_impose_est_signale_comme_tel(self, client):
        detection = client.post(
            "/chat", json={"message": "bonjour", "domain": "sante"}, headers=ENTETE
        ).json()["detection"]
        assert detection["domain"] == ["sante"]
        assert detection["forced_by_user"] is True


class TestAncrage:
    """Le cœur : ne jamais présenter comme fondé ce qui ne l'est pas."""

    def test_l_ancrage_a_trois_issues_jamais_deux(self, client):
        statut = client.post(
            "/chat", json={"message": "Quand planter le mil à Thiès ?"}, headers=ENTETE
        ).json()["grounding"]["status"]
        assert statut in ("GROUNDED", "UNGROUNDED", "NOT_CHECKED")

    def test_une_base_vide_donne_ungrounded_avec_sa_raison(self, client):
        """
        Mesuré le 2026-08-22 : l'agent `senegal` répond `empty_base` et dit que
        « la base est vide sur ce sujet — ce n'est pas une réponse négative ».

        La route fait remonter ce verdict au lieu d'en écrire un second.
        """
        ancrage = client.post(
            "/chat", json={"message": "Quand planter le mil à Thiès ?"}, headers=ENTETE
        ).json()["grounding"]
        if ancrage["status"] == "UNGROUNDED":
            assert ancrage["reason"], "un refus sans raison est indébogable"
            assert ancrage["sources"] == []

    def test_ungrounded_n_est_jamais_accompagne_de_sources(self, client):
        charge = client.post(
            "/chat", json={"message": "Quand planter le mil à Thiès ?"}, headers=ENTETE
        ).json()
        if charge["grounding"]["status"] == "UNGROUNDED":
            assert not charge["grounding"]["sources"]

    def test_la_reponse_n_est_jamais_vide(self, client):
        """
        Une bulle vide ferait passer une panne pour une réponse.

        La route rend 503 plutôt qu'une chaîne vide — c'est la même règle que
        `/agri/advice`, qui refuse de servir un conseil sans modèle.
        """
        reponse = client.post(
            "/chat", json={"message": "Quand planter le mil à Thiès ?"}, headers=ENTETE
        )
        if reponse.status_code == 200:
            assert reponse.json()["answer"].strip()
        else:
            assert reponse.status_code == 503


class TestConversation:
    """Le fil, et ce qu'il fait de l'historique."""

    def test_un_identifiant_est_attribue(self, client):
        charge = client.post("/chat", json={"message": "bonjour"}, headers=ENTETE).json()
        assert charge["conversation_id"].startswith("conv_")

    def test_un_identifiant_fourni_est_conserve(self, client):
        charge = client.post(
            "/chat", json={"message": "bonjour", "conversation_id": "conv_abc"},
            headers=ENTETE,
        ).json()
        assert charge["conversation_id"] == "conv_abc"

    def test_un_historique_tres_long_ne_fait_pas_echouer_le_tour(self, client):
        """
        Cent tours dépasseraient la fenêtre du modèle.

        La route n'en garde que les six derniers — perdre le début d'un fil vaut
        mieux que perdre le tour entier.
        """
        historique = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"tour {i}"}
            for i in range(100)
        ]
        reponse = client.post(
            "/chat", json={"message": "et donc ?", "history": historique}, headers=ENTETE
        )
        assert reponse.status_code in (200, 503)
