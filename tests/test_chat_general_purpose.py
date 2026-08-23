"""
La matrice du §16 du brief : GalSen IA est généraliste, pas sénégalais seul.

Ces tests parcourent le **vrai chemin `/chat`** — HTTP, orchestration, contexte
de réponse, moteur de modèles, `ChatResponse` — comme le §17 l'exige. La seule
chose simulée est la frontière du fournisseur : un test qui ne passe que là où
il y a Internet n'est pas un test, c'est un sondage réseau.

Ce qu'ils vérifient tient en une phrase : **l'utilisateur reçoit une réponse,
pas un rapport d'exécution**, et le Sénégal n'entre que lorsqu'on l'appelle.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CLE = "matrice-chat"
ENTETE = {"X-API-Key": CLE}

# Ce que le faux modèle rend. Reconnaissable, pour distinguer une vraie
# génération d'un repli composé par la plateforme.
MARQUEUR = "REPONSE-DU-MODELE"

# Les noms qu'un utilisateur ne doit jamais lire (§11). Ce sont des rouages.
ROUAGES = ("planner", "researcher", "verifier", "agent_results",
           "aggregated_result", "workflow")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin:testeur")
    import src.api.server as serveur

    serveur.rbac_manager.reload()
    serveur.set_valid_api_key_digests(serveur.rbac_manager.active_key_digests())
    try:
        with TestClient(serveur.app) as instance:
            yield instance
    finally:
        monkeypatch.delenv("GALSEN_API_KEYS", raising=False)
        serveur.rbac_manager.reload()
        serveur.set_valid_api_key_digests(serveur.rbac_manager.active_key_digests())


class Tour:
    """
    Un tour de conversation, avec un modèle simulé et les agents observés.

    Deux choses sont capturées : l'invite réellement envoyée au modèle, et les
    agents réellement exécutés. La seconde demande d'instrumenter
    `RouterEngine._dispatch_agent` — c'est le seul endroit où le passage d'un
    agent est un fait plutôt qu'une déclaration.
    """

    def __init__(self, client, texte=MARQUEUR):
        self.client, self.texte = client, texte
        self.invite = None
        self.agents = []

    def envoyer(self, message, history=None):
        import src.api.server as serveur
        from src.router.router_engine import RouterEngine

        async def faux_modele(prompt, task_requirements, **kwargs):
            self.invite = prompt
            self.exigences = task_requirements
            return self.texte

        vrai_dispatch = RouterEngine._dispatch_agent

        def espion(moteur, config, data, contexte):
            self.agents.append(config.get("id") or config.get("agent"))
            return vrai_dispatch(moteur, config, data, contexte)

        precedent = serveur.model_manager.generate_text_with_fallback
        serveur.model_manager.generate_text_with_fallback = faux_modele
        RouterEngine._dispatch_agent = espion
        try:
            corps = {"message": message}
            if history:
                corps["history"] = history
            self.reponse = self.client.post("/chat", json=corps, headers=ENTETE)
        finally:
            serveur.model_manager.generate_text_with_fallback = precedent
            RouterEngine._dispatch_agent = vrai_dispatch
        self.charge = self.reponse.json() if self.reponse.status_code == 200 else {}
        return self


def _est_une_vraie_reponse(charge):
    """Une réponse, pas un rapport : générée, non vide, sans nom d'agent."""
    assert charge.get("generated") is True
    texte = charge.get("answer") or ""
    assert texte.strip()
    minuscule = texte.lower()
    for rouage in ROUAGES:
        assert rouage not in minuscule, f"« {rouage} » ne doit pas atteindre l'utilisateur"


# --------------------------------------------------------------------------
# A — Connaissance générale
# --------------------------------------------------------------------------

class TestAConnaissanceGenerale:
    """
    *« Qui était Albert Einstein ? »* — une question à laquelle un modèle sait
    répondre, et sur laquelle la plateforme n'a et n'aura jamais de corpus.

    C'est le cas qui a motivé tout ce VOLET : mesuré le 2026-08-23, cette
    question et « bonjour » recevaient **la réponse identique, mot pour mot** —
    les lacunes du chercheur.
    """

    def test_une_question_generale_recoit_une_vraie_reponse(self, client):
        tour = Tour(client).envoyer("Qui était Albert Einstein ?")
        assert tour.reponse.status_code == 200
        _est_une_vraie_reponse(tour.charge)
        assert MARQUEUR in tour.charge["answer"]

    def test_elle_reste_non_ancree(self, client):
        """
        La plateforme n'a aucune source sur Einstein, et le dire est le travail.
        Un modèle fluide ne rend rien sourcé (§12).
        """
        tour = Tour(client).envoyer("Qui était Albert Einstein ?")
        assert tour.charge["grounding"]["status"] != "GROUNDED"

    def test_aucun_agent_senegalais_n_est_mobilise(self, client):
        tour = Tour(client).envoyer("Qui était Albert Einstein ?")
        assert "senegal" not in tour.agents


# --------------------------------------------------------------------------
# B — Conversation simple
# --------------------------------------------------------------------------

class TestBConversationSimple:
    """*« Bonjour »* — et surtout : rien d'autre ne doit se déclencher."""

    def test_une_salutation_recoit_une_vraie_reponse(self, client):
        tour = Tour(client).envoyer("Bonjour")
        assert tour.reponse.status_code == 200
        _est_une_vraie_reponse(tour.charge)

    def test_une_salutation_ne_lance_aucune_recherche(self, client):
        """
        Le §9 le demande, et le chiffre le justifie : mesuré le 2026-08-23,
        « bonjour » traversait le `researcher` pendant **1 095 ms** pour
        chercher des sources sur une salutation.
        """
        tour = Tour(client).envoyer("Bonjour")
        assert "researcher" not in tour.agents
        assert "senegal" not in tour.agents
        assert tour.agents == ["planner"]

    def test_une_salutation_reste_rapide(self, client):
        """Un seuil large : ce test constate un ordre de grandeur, pas une machine."""
        tour = Tour(client).envoyer("Bonjour")
        assert tour.charge["elapsed_seconds"] < 0.9


# --------------------------------------------------------------------------
# D — Question technique
# --------------------------------------------------------------------------

class TestDQuestionTechnique:
    """*« Explique Linux. »* — général, et sans dépendance sénégalaise."""

    def test_une_question_technique_recoit_une_vraie_reponse(self, client):
        tour = Tour(client).envoyer("Explique Linux.")
        assert tour.reponse.status_code == 200
        _est_une_vraie_reponse(tour.charge)

    def test_le_senegal_n_est_pas_une_dependance(self, client):
        tour = Tour(client).envoyer("Explique Linux.")
        assert "senegal" not in tour.agents
        assert tour.charge["detection"]["domain"] != ["senegal"]

    def test_l_invite_dit_au_modele_qu_il_est_generaliste(self, client):
        """
        Le §2 du brief : le Sénégal est une identité et une spécialité, pas une
        frontière. La consigne doit le dire au modèle, pas seulement au lecteur.
        """
        tour = Tour(client).envoyer("Explique Linux.")
        assert "general-purpose" in tour.invite
        assert "not your\nboundary" in tour.invite or "not your boundary" in tour.invite


# --------------------------------------------------------------------------
# C — Sénégal
# --------------------------------------------------------------------------

class TestCSenegal:
    """
    *« Quelles sont les régions du Sénégal ? »* — la spécialité, activée.

    Le §10 demande que le Sénégal reste spécialisé. Ces tests vérifient
    l'autre moitié, celle qu'on oublie : qu'il s'active **quand on l'appelle**.
    Une spécialité qui ne se déclenche jamais n'est pas une spécialité.
    """

    def test_une_question_senegalaise_mobilise_l_agent_senegal(self, client):
        tour = Tour(client).envoyer("Quelles sont les régions du Sénégal ?")
        assert "senegal" in tour.agents

    def test_elle_recoit_une_vraie_reponse(self, client):
        tour = Tour(client).envoyer("Quelles sont les régions du Sénégal ?")
        assert tour.reponse.status_code == 200
        _est_une_vraie_reponse(tour.charge)

    def test_l_ancrage_reste_coherent(self, client):
        """
        Trois issues, jamais deux — et jamais `GROUNDED` du seul fait qu'un
        modèle a écrit. L'ancrage est calculé avant la rédaction.
        """
        tour = Tour(client).envoyer("Quelles sont les régions du Sénégal ?")
        assert tour.charge["grounding"]["status"] in (
            "GROUNDED", "UNGROUNDED", "NOT_CHECKED")
        if tour.charge["grounding"]["status"] != "GROUNDED":
            # Une réponse non ancrée ne s'accompagne jamais de sources.
            assert tour.charge["grounding"]["sources"] == []


# --------------------------------------------------------------------------
# E — Code
# --------------------------------------------------------------------------

class TestECode:
    """
    *« Écris une fonction Python qui trie une liste. »*

    Ce test dit **deux choses vraies**, dont une inconfortable : la réponse
    finale est bien générée, et la capacité de codage n'est **pas** atteinte.

    L'intention est corrigée — le planner classe désormais cette demande en
    `implementation` et recommande `coder` — mais le workflow `question` ne
    déclare pas `coder`, donc la recommandation est inutilisable et le pipeline
    entier s'applique. Brancher un message de conversation sur un agent qui
    écrit des fichiers est une décision d'exploitant (§19), pas un détail.

    **Ce test épingle l'état réel, pas l'état souhaité.** Le jour où la
    décision est prise, il échouera — et c'est exactement ce qu'on attend de
    lui.
    """

    def test_une_demande_de_code_recoit_une_vraie_reponse(self, client):
        tour = Tour(client).envoyer("Écris une fonction Python qui trie une liste.")
        assert tour.reponse.status_code == 200
        _est_une_vraie_reponse(tour.charge)

    def test_l_intention_est_bien_une_implementation(self, client):
        """Mesuré avant/après le 2026-08-23 : c'était `research`."""
        import src.api.server as serveur

        resultat = serveur.get_router_engine().process_request(
            "Écris une fonction Python qui trie une liste.", workflow_id="question")
        planner = serveur._resultat_agent(resultat, "planner")
        assert "implementation" in (planner.get("detected_intents") or [])
        assert "coder" in (planner.get("agents_required") or [])

    def test_le_coder_n_est_pas_encore_atteint_et_c_est_dit(self, client):
        """
        L'état réel, épinglé pour qu'il ne soit pas confondu avec l'état voulu.

        `coder` n'est pas déclaré dans le pipeline du workflow `question`, donc
        il ne tourne pas. Ce test tombera le jour où l'exploitant le déclare —
        c'est sa raison d'être.
        """
        tour = Tour(client).envoyer("Écris une fonction Python qui trie une liste.")
        assert "coder" not in tour.agents


# --------------------------------------------------------------------------
# F — Historique de conversation
# --------------------------------------------------------------------------

class TestFHistorique:
    """Plusieurs tours, et le fil qui les relie."""

    def test_le_tour_precedent_arrive_au_modele(self, client):
        tour = Tour(client).envoyer(
            "Quelle bibliothèque pour les API ?",
            history=[
                {"role": "user", "content": "J'apprends le Python."},
                {"role": "assistant", "content": "Par où veux-tu commencer ?"},
            ],
        )
        assert "apprends le Python" in tour.invite
        assert "User:" in tour.invite and "Assistant:" in tour.invite

    def test_un_fil_tres_long_ne_casse_rien(self, client):
        """
        Cent tours dépasseraient la fenêtre du modèle. Ils sont tronqués, et
        le tour **le plus récent** doit survivre à la troncature — perdre la
        fin plutôt que le début serait exactement l'inverse du besoin.
        """
        historique = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"tour numéro {i}"}
            for i in range(100)
        ]
        historique[-1]["content"] = "le tout dernier tour"
        tour = Tour(client).envoyer("Et ensuite ?", history=historique)
        assert tour.reponse.status_code == 200
        assert "le tout dernier tour" in tour.invite
        assert "tour numéro 3" not in tour.invite

    def test_l_identifiant_de_conversation_est_conserve(self, client):
        reponse = client.post("/chat", json={
            "message": "Bonjour", "conversation_id": "conv_fil_stable",
        }, headers=ENTETE)
        assert reponse.json()["conversation_id"] == "conv_fil_stable"
