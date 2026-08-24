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

    def __init__(self, client, texte=MARQUEUR, echec=None, resultats=None):
        self.client, self.texte, self.echec = client, texte, echec
        # Résultats à substituer, par identifiant d'agent. Substituer **à la
        # frontière de l'agent** garde tout le chemin réel — HTTP, orchestration,
        # contexte, invite — et n'invente que ce que cette machine ne peut pas
        # produire : un chercheur qui trouve, sans réseau.
        self.resultats = resultats or {}
        self.invite = None
        self.agents = []

    def envoyer(self, message, history=None):
        import src.api.server as serveur
        from src.router.router_engine import RouterEngine

        async def faux_modele(prompt, task_requirements, **kwargs):
            self.invite = prompt
            self.exigences = task_requirements
            if self.echec is not None:
                raise self.echec
            return self.texte

        vrai_dispatch = RouterEngine._dispatch_agent

        def espion(moteur, config, data, contexte):
            identifiant = config.get("id") or config.get("agent")
            self.agents.append(identifiant)
            reel = vrai_dispatch(moteur, config, data, contexte)
            if identifiant in self.resultats and isinstance(reel, dict):
                reel = dict(reel)
                reel["result"] = self.resultats[identifiant]
                reel["status"] = "success"
            return reel

        precedent = serveur.model_manager.generate_text_with_source
        serveur.model_manager.generate_text_with_source = faux_modele
        RouterEngine._dispatch_agent = espion
        try:
            corps = {"message": message}
            if history:
                corps["history"] = history
            self.reponse = self.client.post("/chat", json=corps, headers=ENTETE)
        finally:
            serveur.model_manager.generate_text_with_source = precedent
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
    """
    *« Bonjour »* — et surtout : rien d'autre ne doit se déclencher.

    **Ce contrat a changé le 2026-08-24, en mieux.** Une salutation recevait une
    réponse *générée* ; elle reçoit maintenant une réponse *composée*, sans
    aucun appel de modèle. Un échange de politesse n'affirme rien sur le monde,
    et c'est le seul endroit où une phrase écrite d'avance est honnête —
    `generated` reste faux pour que personne ne s'y trompe.

    Ce que le test exige n'a pas faibli : une **vraie** réponse, pas un refus.
    C'est précisément ce qui manquait à la première version du raccourci, qui
    rendait « je n'ai pas de quoi répondre à cette question » à un « bonjour ».
    """

    def test_une_salutation_recoit_une_vraie_reponse(self, client):
        tour = Tour(client).envoyer("Bonjour")
        assert tour.reponse.status_code == 200
        texte = tour.charge["answer"]
        assert texte.strip()
        # Une vraie réponse d'accueil, et surtout pas un refus.
        assert "n'ai pas de quoi répondre" not in texte
        assert "rien trouvé" not in texte
        for rouage in ROUAGES:
            assert rouage not in texte.lower()

    def test_une_salutation_ne_consomme_aucun_modele(self, client):
        """
        L'idée du propriétaire, mesurée : à 1,7 ms d'orchestration, tout le coût
        restant d'un « bonjour » serait l'appel au modèle. Il n'a plus lieu.
        """
        tour = Tour(client).envoyer("Bonjour")
        assert tour.charge["generated"] is False
        assert tour.invite is None, "aucune invite ne doit être construite"

    def test_une_question_qui_commence_poliment_est_bien_generee(self, client):
        """
        La limite du raccourci, épinglée. « Bonjour, explique-moi la relativité »
        est une question, pas un salut — lui répondre « bonjour ! » serait pire
        que la milliseconde économisée.
        """
        tour = Tour(client).envoyer("Bonjour, explique-moi la relativité générale")
        assert tour.charge["generated"] is True
        assert tour.invite is not None

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


# --------------------------------------------------------------------------
# G — Aucun modèle disponible
# --------------------------------------------------------------------------

class TestGAucunModele:
    """
    L'état réel de cette machine : **zéro modèle enregistré**, mesuré après le
    démarrage complet de l'application.

    Ce n'est pas un cas de bord simulé, c'est la situation par défaut — et
    c'est pour ça qu'il compte : la plateforme doit rester utilisable et
    honnête quand personne n'a lancé `ollama serve`.
    """

    def test_la_reponse_n_est_jamais_marquee_generee(self, client):
        charge = client.post("/chat", json={"message": "Qui était Einstein ?"},
                             headers=ENTETE).json()
        assert charge["generated"] is False
        assert charge["generation_unavailable"]

    def test_rien_n_est_fabrique(self, client):
        """
        Le §14 : pas de réponse inventée. Ce que la plateforme rend est ce que
        ses agents ont constaté — un refus, ou rien.
        """
        charge = client.post("/chat", json={"message": "Qui était Einstein ?"},
                             headers=ENTETE).json()
        assert MARQUEUR not in charge["answer"]
        assert charge["answer"].strip()

    def test_la_route_ne_tombe_pas(self, client):
        reponse = client.post("/chat", json={"message": "Explique Linux."},
                              headers=ENTETE)
        assert reponse.status_code in (200, 503)


# --------------------------------------------------------------------------
# H — Constat non vérifié
# --------------------------------------------------------------------------

CONSTAT_NON_VERIFIE = {
    "findings": [{
        "content": "Le sac de ciment se négocie autour de 3 900 FCFA.",
        "source": "https://exemple.sn/prix",
        "confidence": 0.4,
        "verified": False,
    }],
    "gaps": [],
    "sources_consulted": {"web": 1},
    "documents": [],
}


class TestHConstatNonVerifie:
    """
    Un extrait externe peut servir de contexte. Il ne devient jamais un fait.

    C'est le défaut que ce dépôt a déjà corrigé une fois, le 2026-08-23 :
    l'ancrage comptait les sources *consultées*, si bien que trois extraits web
    auraient été rapportés `GROUNDED`.
    """

    def test_le_constat_atteint_le_modele_marque_non_verifie(self, client):
        tour = Tour(client, resultats={"researcher": CONSTAT_NON_VERIFIE}).envoyer(
            "Quel est le prix du ciment à Dakar ?")
        assert "3 900 FCFA" in tour.invite
        assert "[UNVERIFIED" in tour.invite
        assert "VERIFIED]" not in tour.invite.replace("[UNVERIFIED", "")

    def test_un_extrait_externe_n_ancre_pas_la_reponse(self, client):
        tour = Tour(client, resultats={"researcher": CONSTAT_NON_VERIFIE}).envoyer(
            "Quel est le prix du ciment à Dakar ?")
        assert tour.charge["grounding"]["status"] != "GROUNDED"
        assert tour.charge["grounding"]["sources"] == []

    def test_la_consigne_interdit_de_le_presenter_comme_etabli(self, client):
        tour = Tour(client, resultats={"researcher": CONSTAT_NON_VERIFIE}).envoyer(
            "Quel est le prix du ciment à Dakar ?")
        assert "Never present it as established fact" in tour.invite


# --------------------------------------------------------------------------
# I — Constat vérifié
# --------------------------------------------------------------------------

CONSTAT_VERIFIE = {
    "findings": [{
        "content": "Le Sénégal compte 14 régions.",
        "source": "corpus:senegal/administration",
        "confidence": 1.0,
        "verified": True,
    }],
    "gaps": [],
    "sources_consulted": {"knowledge_base": 1},
    "documents": [],
}


class TestIConstatVerifie:
    """
    Ce que la plateforme a réellement sourcé, et qui l'ancre.

    **La question posée n'est pas sénégalaise, et c'est délibéré.** Écrite
    d'abord avec « combien de régions compte le Sénégal ? », elle échouait :
    `_ancrage_de()` est construit autour du verdict de l'agent `senegal` et ne
    consulte le chercheur que lorsque cet agent n'a pas tourné. Sur une question
    sénégalaise dont la base est vide, le verdict de `senegal` l'emporte donc
    sur un constat vérifié du chercheur.

    C'est défendable — l'agent `senegal` fait autorité sur la portée nationale,
    et une réponse sénégalaise dont la base nationale est vide ne devrait pas
    se lire comme ancrée. **Constat noté, rien corrigé** : ce n'est pas le
    périmètre de ce VOLET, et le changer sans décision serait exactement ce que
    `spec-driven-governance.md` interdit.
    """

    QUESTION = "Quelle est la vitesse de la lumière ?"

    def test_un_constat_verifie_ancre_la_reponse(self, client):
        tour = Tour(client, resultats={"researcher": CONSTAT_VERIFIE}).envoyer(self.QUESTION)
        assert tour.charge["grounding"]["status"] == "GROUNDED"
        assert tour.charge["grounding"]["sources"]

    def test_il_atteint_le_modele_marque_verifie(self, client):
        tour = Tour(client, resultats={"researcher": CONSTAT_VERIFIE}).envoyer(self.QUESTION)
        assert "[VERIFIED" in tour.invite
        assert "14 régions" in tour.invite

    def test_la_source_est_nommee_et_non_inventee(self, client):
        tour = Tour(client, resultats={"researcher": CONSTAT_VERIFIE}).envoyer(self.QUESTION)
        assert "corpus:senegal/administration" in tour.charge["grounding"]["sources"]

    def test_un_verdict_senegalais_vide_prime_sur_le_chercheur(self, client):
        """
        Le constat ci-dessus, épinglé plutôt que laissé dans un commentaire.

        **Les deux agents sont imposés, et c'est la correction du 2026-08-24.**
        La première version n'imposait que le chercheur et laissait l'agent
        `senegal` répondre depuis le corpus réel : elle passait ici, où la base
        est vide, et **échouait en CI**, où elle a su répondre — `assert
        'GROUNDED' != 'GROUNDED'`.

        Le test épinglait une préséance, mais à travers un état ambiant qu'il ne
        contrôlait pas. Un test dont le verdict dépend du contenu de la base ne
        mesure pas la règle qu'il prétend mesurer.
        """
        tour = Tour(client, resultats={
            "researcher": CONSTAT_VERIFIE,
            "senegal": {
                "status": "empty_base",
                "reason": "La base ne contient rien sur ce sujet.",
                "elements": [],
            },
        }).envoyer("Combien de régions compte le Sénégal ?")
        assert "senegal" in tour.agents
        # Le verdict de `senegal` l'emporte, malgré un constat vérifié du
        # chercheur : il fait autorité sur la portée nationale.
        assert tour.charge["grounding"]["status"] != "GROUNDED"


# --------------------------------------------------------------------------
# J — La génération échoue
# --------------------------------------------------------------------------

class TestJEchecDeGeneration:
    """
    Un fournisseur qui tombe en cours de route. Différent du cas G : ici un
    modèle existait, et il a échoué.
    """

    def test_un_echec_ne_produit_aucun_texte_de_remplacement(self, client):
        tour = Tour(client, echec=RuntimeError("le fournisseur a coupé")).envoyer(
            "Explique Linux.")
        assert tour.reponse.status_code in (200, 503)
        if tour.reponse.status_code == 200:
            assert tour.charge["generated"] is False
            assert MARQUEUR not in tour.charge["answer"]

    def test_le_motif_reste_sans_detail_d_infrastructure(self, client):
        tour = Tour(client, echec=RuntimeError("connexion refusée sur 10.0.0.5:8080")).envoyer(
            "Explique Linux.")
        if tour.reponse.status_code == 200:
            motif = tour.charge.get("generation_unavailable") or ""
            assert "10.0.0.5" not in motif
            assert "8080" not in motif


# --------------------------------------------------------------------------
# §18, §19, §20 — coût, sécurité, observabilité
# --------------------------------------------------------------------------

class TestCoutSecuriteObservabilite:
    """
    Trois exigences qui n'ont pas de cas dans la matrice, et qui se vérifient
    quand même — c'est justement pour cela qu'on les oublie.
    """

    def test_un_tour_ne_declenche_qu_une_generation(self, client):
        """
        §18 : ne pas faire écrire la réponse par chaque agent puis la réécrire.
        Un tour, une génération.
        """
        import src.api.server as serveur

        appels = []

        async def faux(prompt, task_requirements, **k):
            appels.append(prompt)
            return MARQUEUR

        precedent = serveur.model_manager.generate_text_with_source
        serveur.model_manager.generate_text_with_source = faux
        try:
            client.post("/chat", json={"message": "Explique Linux."}, headers=ENTETE)
        finally:
            serveur.model_manager.generate_text_with_source = precedent

        assert len(appels) == 1

    def test_la_couche_de_reponse_ne_gagne_aucune_permission(self):
        """
        §19 : rédiger n'est pas l'autorisation d'exécuter.

        Le test lit le module plutôt que d'invoquer quoi que ce soit : une
        permission qui n'est pas nommée dans le fichier ne peut pas être
        obtenue par accident.
        """
        import pathlib

        source = pathlib.Path("src/chat/response.py").read_text(encoding="utf-8")
        for interdit in ("Permission.", "require_permission", "tool_engine",
                         "ToolExecutor", "approval"):
            assert interdit not in source, f"« {interdit} » n'a rien à faire ici"

    def test_la_route_garde_sa_permission_d_origine(self, client):
        """La couche n'élargit rien : `/chat` exige toujours `MODEL_GENERATE`."""
        reponse = client.post("/chat", json={"message": "Bonjour"})
        assert reponse.status_code in (401, 403)

    def test_l_issue_la_duree_et_le_run_id_sont_rendus(self, client):
        """
        §20 : ce qui est observable l'est vraiment.

        Et ce qui n'existe pas n'est pas inventé — il n'y a pas de compteur
        `/metrics` pour la génération, pas d'événement d'audit dédié, et ce
        test ne prétend pas le contraire.
        """
        tour = Tour(client).envoyer("Explique Linux.")
        charge = tour.charge
        assert charge["generated"] is True
        assert charge["elapsed_seconds"] > 0
        assert "run_id" in charge
