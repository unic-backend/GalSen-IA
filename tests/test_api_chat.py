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


class TestQuandLeChercheurTrouve:
    """
    Le cas que personne ne pouvait voir sur une machine sans réseau.

    **Mesuré en CI le 2026-08-23** : six tests de ce fichier sont passés au
    rouge sur un commit ne touchant qu'un fichier de documentation. La cause
    n'était ni l'ordre ni le hasard — `pytest-randomly` n'est pas installé et
    l'ordre est identique. C'était le réseau : les exécuteurs GitHub en ont un,
    cette machine n'en a pas.

    Quand la recherche web aboutissait, le chercheur rendait des `findings`, et
    la route **répondait 503** — c'est-à-dire qu'elle échouait précisément
    quand la plateforme trouvait quelque chose. Le pire mode de défaillance
    possible, et invisible ici.

    Ces tests pilotent les fonctions directement plutôt que la route : un test
    qui ne peut passer que là où le réseau existe n'est pas un test ici.
    """

    @staticmethod
    def _resultat(constats, lacunes=None):
        """Un résultat d'orchestration, à la forme réelle de `agents/researcher/`."""
        return {
            "agent_results": [
                {"agent": "planner", "result": {"axes": {}}},
                {
                    "agent": "researcher",
                    "result": {
                        "findings": constats,
                        "gaps": lacunes or [],
                        "sources_consulted": {"web": len(constats)},
                        "documents": [],
                    },
                },
            ],
            "aggregated_result": {"status": "success"},
        }

    def test_des_constats_ne_donnent_jamais_une_reponse_vide(self):
        """C'est l'échec de CI, réduit à une ligne."""
        import src.api.server as serveur

        resultat = self._resultat(
            [{"source": "https://exemple.org", "content": "le mil se sème en juin",
              "verified": False}]
        )
        assert serveur._texte_de_reponse(resultat).strip()

    def test_un_extrait_web_n_est_pas_un_ancrage(self):
        """
        `verified: False` vient du chercheur lui-même.

        Compter les sources *consultées* aurait dit `GROUNDED` pour trois
        extraits web — exactement le défaut que cette route existe pour ne pas
        reproduire. La fiabilité vient du registre de sources, jamais du
        document qui l'affirme.
        """
        import src.api.server as serveur

        ancrage = serveur._ancrage_de(
            self._resultat(
                [{"source": "https://exemple.org", "content": "x", "verified": False}]
            )
        )
        assert ancrage.status == "UNGROUNDED"
        assert ancrage.sources == []

    def test_un_constat_verifie_ancre_la_reponse(self):
        import src.api.server as serveur

        ancrage = serveur._ancrage_de(
            self._resultat(
                [{"source": "corpus:senegal", "content": "x", "verified": True}]
            )
        )
        assert ancrage.status == "GROUNDED"
        assert ancrage.sources == ["corpus:senegal"]

    def test_chaque_constat_garde_son_origine(self):
        """
        Trois extraits fondus dans un paragraphe se liraient comme une réponse
        de la plateforme, alors qu'ils viennent d'ailleurs.
        """
        import src.api.server as serveur

        texte = serveur._texte_de_reponse(
            self._resultat(
                [{"source": "https://exemple.org", "content": "une affirmation",
                  "verified": False}]
            )
        )
        assert "https://exemple.org" in texte
        assert "non vérifié" in texte

    def test_un_constat_sans_texte_est_compte_jamais_invente(self):
        import src.api.server as serveur

        texte = serveur._texte_de_reponse(
            self._resultat([{"source": "https://exemple.org", "content": ""}])
        )
        assert "1 élément(s)" in texte


class TestContexteDeReponse:
    """
    Ce que la rédaction reçoit — et ce qu'elle ne doit jamais recevoir.

    Le contexte est le seul endroit où l'on choisit ce que le modèle voit. Un
    rouage qui s'y glisse ressort en prose : donner à un modèle la liste des
    tâches du planner, c'est lui demander d'écrire un rapport d'exécution.
    """

    @staticmethod
    def _resultat(senegal=None, chercheur=None):
        agents = [{"agent": "planner", "result": {"axes": {"language": {"value": "fr"}}}}]
        if chercheur is not None:
            agents.append({"agent": "researcher", "result": chercheur})
        if senegal is not None:
            agents.append({"agent": "senegal", "result": senegal})
        return {"agent_results": agents, "aggregated_result": {}}

    def test_un_element_du_corpus_est_une_preuve_verifiee(self):
        """
        Rien n'entre dans le corpus sans source (ADR-019), et
        `apply_scope_policy` a déjà tranché. Ces éléments sont donc vérifiés —
        parce que le corpus l'exige, pas parce que c'est pratique.
        """
        import src.api.server as serveur

        contexte = serveur._contexte_de_reponse(
            self._resultat(senegal={
                "status": "grounded",
                "elements": [{"id": "sn-001", "content": "14 régions.",
                              "scope": "country:sn"}],
            }),
            "Combien de régions ?", [], serveur.ChatGrounding(status="GROUNDED"),
        )
        assert len(contexte.constats_verifies) == 1
        assert contexte.constats_verifies[0]["scope"] == "country:sn"
        assert contexte.constats_verifies[0]["source"] == "sn-001"

    def test_un_refus_est_transporte_mot_pour_mot(self):
        """Reformuler un refus, c'est déjà commencer à l'adoucir."""
        import src.api.server as serveur

        raison = "La base ne contient rien sur ce sujet — ce n'est pas une réponse négative."
        contexte = serveur._contexte_de_reponse(
            self._resultat(senegal={"status": "empty_base", "reason": raison,
                                    "what_would_settle_it": "ingérer le corpus"}),
            "Question", [], serveur.ChatGrounding(status="UNGROUNDED"),
        )
        assert raison in contexte.agent_notes
        assert any("ingérer le corpus" in n for n in contexte.agent_notes)

    def test_aucun_rouage_n_entre_dans_le_contexte(self):
        """
        Le plan, les tâches et les durées restent dehors (§8 du brief).

        Ce test regarde l'invite réellement construite, pas le contexte : c'est
        l'invite que le modèle lit, et c'est donc là que la fuite se verrait.
        """
        import src.api.server as serveur
        from src.chat import construire_invite

        resultat = self._resultat(chercheur={"findings": [], "gaps": []})
        resultat["agent_results"][0]["result"]["tasks"] = ["étape secrète"]
        resultat["agent_results"][0]["result"]["task_count"] = 7

        invite = construire_invite(serveur._contexte_de_reponse(
            resultat, "Bonjour", [], serveur.ChatGrounding(status="NOT_CHECKED")))
        assert "étape secrète" not in invite
        assert "task_count" not in invite


class TestLaGenerationNAncreRien:
    """
    L'invariant que ce VOLET ne doit jamais casser.

    Le §12 du brief le dit, et c'est la seule phrase de tout le document qui
    protège l'utilisateur : *« the system must never claim that a response is
    grounded simply because a model generated it »*. Un modèle qui écrit bien
    ne rend rien plus sourcé.
    """

    def _reponse(self, client, texte):
        import src.api.server as serveur

        async def faux(prompt, task_requirements, **k):
            return texte

        precedent = serveur.model_manager.generate_text_with_fallback
        serveur.model_manager.generate_text_with_fallback = faux
        try:
            return client.post("/chat", json={"message": "Qui était Einstein ?"},
                               headers=ENTETE)
        finally:
            serveur.model_manager.generate_text_with_fallback = precedent

    def test_une_reponse_generee_reste_non_ancree(self, client):
        reponse = self._reponse(client, "Einstein était un physicien.")
        assert reponse.status_code == 200
        charge = reponse.json()
        assert charge["generated"] is True
        assert charge["answer"].startswith("Einstein")
        # La fluidité n'ancre pas.
        assert charge["grounding"]["status"] != "GROUNDED"

    def test_sans_modele_la_reponse_n_est_pas_marquee_generee(self, client):
        """Le champ qui empêche de confondre un refus composé et une réponse."""
        reponse = client.post("/chat", json={"message": "Qui était Einstein ?"},
                              headers=ENTETE)
        if reponse.status_code == 200:
            charge = reponse.json()
            assert charge["generated"] is False
            assert charge["generation_unavailable"]


class TestPanneEtMemoire:
    """
    Ce qu'on dit quand ça rate, et ce dont on se souvient (§14 et §15).
    """

    def test_aucune_infrastructure_ne_fuit_dans_la_reponse(self, client):
        """
        **Mesuré le 2026-08-23 : ce défaut a existé.** Le motif rendu par
        l'API portait `http://localhost:11434` — un hôte et un port livrés à
        quiconque appelle la route. Le §14 l'interdit, et un message d'erreur
        est le dernier endroit où l'on pense à regarder.
        """
        charge = client.post("/chat", json={"message": "Explique Linux."},
                             headers=ENTETE).json()
        motif = charge.get("generation_unavailable") or ""
        assert "http://" not in motif
        assert "localhost" not in motif
        assert ":11434" not in motif

    def test_la_cause_reelle_est_conservee_a_l_interieur(self):
        """
        Cacher une panne n'est pas la traiter. Le détail entier reste dans
        `failure_detail`, journalisé, et il porte le geste à faire.
        """
        from src.chat import ContexteReponse, RedacteurConversation
        from src.model_engine.model_manager import ModelManagerImpl

        finale = RedacteurConversation(ModelManagerImpl()).rediger(
            ContexteReponse(message="Explique Linux.")
        )
        assert finale.generated is False
        assert finale.failure_detail
        # Plus long que le motif public : c'est tout l'intérêt.
        assert len(finale.failure_detail) > len(finale.failure_reason or "")

    def test_un_motif_public_est_stable_et_court(self):
        """
        Une valeur énumérée ne change pas quand le fournisseur change, donc un
        client peut s'y fier. Une prose de fournisseur, non.
        """
        from src.chat.response import AUCUN_FOURNISSEUR, _classer_panne
        from src.model_engine.providers.base import ProviderUnavailableError

        class FausseRaison:
            value = "no_credentials"

        erreur = ProviderUnavailableError("ollama", FausseRaison(), "http://localhost:11434")
        assert _classer_panne(erreur) == AUCUN_FOURNISSEUR
        assert "localhost" not in _classer_panne(erreur)

    def test_le_tour_precedent_atteint_le_modele(self, client):
        """
        §15 : « j'apprends le Python » puis « quelle bibliothèque pour les
        API ? » — la seconde réponse doit pouvoir se servir de la première.

        Aucun second système de mémoire n'est créé : l'historique voyage de la
        requête jusqu'à l'invite, en passant par le contexte de réponse.
        """
        import src.api.server as serveur

        vu = {}

        async def faux(prompt, task_requirements, **k):
            vu["invite"] = prompt
            return "FastAPI ou Flask conviennent."

        precedent = serveur.model_manager.generate_text_with_fallback
        serveur.model_manager.generate_text_with_fallback = faux
        try:
            client.post("/chat", json={
                "message": "Quelle bibliothèque pour les API ?",
                "history": [
                    {"role": "user", "content": "J'apprends le Python."},
                    {"role": "assistant", "content": "Par où veux-tu commencer ?"},
                ],
            }, headers=ENTETE)
        finally:
            serveur.model_manager.generate_text_with_fallback = precedent

        assert "apprends le Python" in vu["invite"]
        assert "User:" in vu["invite"] and "Assistant:" in vu["invite"]
