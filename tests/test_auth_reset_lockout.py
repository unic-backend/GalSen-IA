"""
Tests des routes de verrouillage et de réinitialisation (ADR-029, dette soldée).

Ces routes sont les seules de la plateforme qu'un attaquant appelle *avant*
d'avoir un compte. Deux choses s'y perdent facilement, et ce sont celles que ces
tests gardent :

1. **Le verrouillage ne doit pas devenir un annuaire.** Un échec est compté que
   l'adresse existe ou non. Ne compter que les comptes réels ferait du
   verrouillage un oracle d'existence — plus fiable qu'un message d'erreur,
   parce qu'il survit à la lecture du code.
2. **La demande de réinitialisation répond pareil dans tous les cas.** Une
   réponse différente pour une adresse inconnue transformerait ce formulaire en
   liste de comptes.

Le compteur du serveur est un exemplaire unique : chaque test le remet à zéro,
sinon un verrou posé ici ferait échouer une suite voisine pour une raison
introuvable.
"""

import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient

_GALSEN_TEST_DIR = tempfile.mkdtemp(prefix="galsen-test-reset-")
os.environ["GALSEN_DATA_DIR"] = _GALSEN_TEST_DIR
os.environ["GALSEN_RATE_LIMIT_ENABLED"] = "false"
os.environ.setdefault("GALSEN_JWT_SECRET", "secret-de-test-" + "y" * 40)

import src.api.server as serveur  # noqa: E402

MOT_DE_PASSE = "un-mot-de-passe-assez-long-42"


def _nettoyer():
    """Retire le dossier temporaire."""
    shutil.rmtree(_GALSEN_TEST_DIR, ignore_errors=True)


@pytest.fixture
def client():
    """
    Client API, avec le garde de connexion remis à zéro.

    Le garde est un exemplaire unique dans le serveur : un verrou laissé posé
    ferait échouer une suite voisine, et personne ne remonterait jusqu'ici.
    """
    serveur._login_guard = serveur.LoginGuard(max_failures=3, lock_seconds=60)
    serveur._password_reset = serveur.PasswordResetService()
    with TestClient(serveur.app) as client:
        yield client
    serveur._login_guard = serveur.LoginGuard()
    serveur._password_reset = serveur.PasswordResetService()


@pytest.fixture
def compte(client):
    """Un compte réel, inscrit par la route publique."""
    adresse = f"awa-{os.urandom(4).hex()}@example.test"
    reponse = client.post("/auth/register",
                          json={"email": adresse, "password": MOT_DE_PASSE,
                                "name": "Awa de test"})
    assert reponse.status_code in (200, 201), reponse.text
    return adresse


class TestVerrouillage:
    """Trop d'échecs met en attente, sans dire qui existe."""

    def test_un_mauvais_mot_de_passe_reste_401(self, client, compte):
        reponse = client.post("/auth/login",
                              json={"email": compte, "password": "faux"})
        assert reponse.status_code == 401

    def test_le_verrou_repond_429_et_non_401(self, client, compte):
        """429 dit « en attente » ; 401 dirait « mauvais identifiants »."""
        for _ in range(3):
            client.post("/auth/login", json={"email": compte, "password": "faux"})
        reponse = client.post("/auth/login",
                              json={"email": compte, "password": "faux"})
        assert reponse.status_code == 429
        assert "Retry-After" in reponse.headers

    def test_une_adresse_inconnue_se_verrouille_aussi(self, client):
        """Sinon le verrouillage dirait quelles adresses existent."""
        inconnue = "fantome@example.test"
        for _ in range(3):
            client.post("/auth/login",
                        json={"email": inconnue, "password": "faux"})
        reponse = client.post("/auth/login",
                              json={"email": inconnue, "password": "faux"})
        assert reponse.status_code == 429

    def test_le_verrou_bloque_meme_le_bon_mot_de_passe(self, client, compte):
        """Sinon il ne protégerait rien : l'attaquant continuerait d'essayer."""
        for _ in range(3):
            client.post("/auth/login", json={"email": compte, "password": "faux"})
        reponse = client.post("/auth/login",
                              json={"email": compte, "password": MOT_DE_PASSE})
        assert reponse.status_code == 429

    def test_une_connexion_reussie_efface_les_echecs(self, client, compte):
        client.post("/auth/login", json={"email": compte, "password": "faux"})
        assert client.post("/auth/login",
                           json={"email": compte,
                                 "password": MOT_DE_PASSE}).status_code == 200
        # Le compteur est reparti de zéro : deux échecs ne verrouillent plus.
        for _ in range(2):
            client.post("/auth/login", json={"email": compte, "password": "faux"})
        assert client.post("/auth/login",
                           json={"email": compte,
                                 "password": MOT_DE_PASSE}).status_code == 200


class TestReinitialisation:
    """La demande ne doit rien apprendre à personne."""

    def test_la_reponse_est_identique_pour_une_adresse_inconnue(self, client,
                                                                compte):
        connu = client.post("/auth/password-reset/request",
                            json={"email": compte})
        inconnu = client.post("/auth/password-reset/request",
                              json={"email": "fantome@example.test"})
        assert connu.status_code == inconnu.status_code == 200
        assert connu.json() == inconnu.json(), (
            "Deux réponses différentes feraient de ce formulaire un annuaire."
        )

    def test_le_jeton_n_est_jamais_rendu_dans_la_reponse(self, client, compte):
        """Le rendre à l'appelant rendrait le formulaire exploitable seul."""
        charge = client.post("/auth/password-reset/request",
                             json={"email": compte}).json()
        assert "token" not in charge and "ticket" not in charge

    def test_l_absence_de_canal_est_dite(self, client, compte):
        """Laisser attendre un courriel qui n'arrivera pas est pire que le dire."""
        charge = client.post("/auth/password-reset/request",
                             json={"email": compte}).json()
        assert charge["delivery"] == "NOT_CONFIGURED"

    def test_la_route_emet_reellement_un_jeton_pour_un_compte_reel(
            self, client, compte):
        """Le test qui a attrapé un vrai défaut.

        La route lisait `getattr(utilisateur, "user_id", None)` alors que le
        champ s'appelle `id`. Elle rendait donc `None` pour **tout** compte
        réel, n'émettait jamais de jeton — et répondait exactement comme si
        elle en avait émis un. Un défaut invisible depuis la réponse, par
        construction : c'est le prix de la règle « répondre pareil dans tous
        les cas », et il se paie avec ce test.
        """
        service = serveur.get_password_reset()
        client.post("/auth/password-reset/request", json={"email": compte})
        assert service.report()["live_tickets"] == 1

        client.post("/auth/password-reset/request",
                    json={"email": "fantome@example.test"})
        assert service.report()["live_tickets"] == 1, (
            "Une adresse inconnue ne doit produire aucun jeton."
        )

    def test_un_jeton_valide_change_le_mot_de_passe(self, client, compte):
        utilisateur = serveur.get_user_manager().get_user_by_email(compte)
        billet = serveur.get_password_reset().request_reset(
            compte, utilisateur.id)["ticket"]
        nouveau = "un-autre-mot-de-passe-long-77"
        reponse = client.post("/auth/password-reset/confirm",
                              json={"token": billet.token,
                                    "new_password": nouveau})
        assert reponse.status_code == 200
        assert client.post("/auth/login",
                           json={"email": compte,
                                 "password": nouveau}).status_code == 200
        assert client.post("/auth/login",
                           json={"email": compte,
                                 "password": MOT_DE_PASSE}).status_code == 401

    def test_un_jeton_deja_utilise_est_refuse(self, client, compte):
        utilisateur = serveur.get_user_manager().get_user_by_email(compte)
        billet = serveur.get_password_reset().request_reset(
            compte, utilisateur.id)["ticket"]
        corps = {"token": billet.token, "new_password": "encore-un-autre-88x"}
        assert client.post("/auth/password-reset/confirm",
                           json=corps).status_code == 200
        assert client.post("/auth/password-reset/confirm",
                           json=corps).status_code == 400

    def test_un_jeton_invente_est_refuse(self, client):
        reponse = client.post("/auth/password-reset/confirm",
                              json={"token": "jeton-invente",
                                    "new_password": "peu-importe-vraiment-99"})
        assert reponse.status_code == 400

    def test_la_reinitialisation_leve_le_verrou(self, client, compte):
        """La personne a prouvé qu'elle contrôle son adresse."""
        for _ in range(3):
            client.post("/auth/login", json={"email": compte, "password": "faux"})
        utilisateur = serveur.get_user_manager().get_user_by_email(compte)
        billet = serveur.get_password_reset().request_reset(
            compte, utilisateur.id)["ticket"]
        nouveau = "mot-de-passe-apres-verrou-55"
        client.post("/auth/password-reset/confirm",
                    json={"token": billet.token, "new_password": nouveau})
        assert client.post("/auth/login",
                           json={"email": compte,
                                 "password": nouveau}).status_code == 200


def test_nettoyage_final():
    """Retire le dossier temporaire de la suite."""
    _nettoyer()
