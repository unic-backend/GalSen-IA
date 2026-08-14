"""
La session OAuth : les trois pièces tenues ensemble, et le retrait (phase 43.3).

Le point le plus discutable de ce chantier est **l'ordre dans `revoke()`**, et
ces tests existent surtout pour le fixer.

L'ordre tentant est : prévenir le fournisseur, puis effacer localement s'il
confirme. Il échoue exactement quand il ne faut pas — réseau coupé, fournisseur
en erreur, jeton déjà invalide — et la plateforme garde alors un accès que
quelqu'un lui a demandé d'oublier. Effacer d'abord peut laisser un jeton vivant
**chez le fournisseur**, que la personne peut aussi tuer depuis son compte ;
en garder un **ici** est une promesse rompue par nous, et nous seuls pouvons la
réparer.

Le reste vérifie que rien ne fuit, et que les portées **accordées** priment sur
celles demandées.
"""

import os
import sys
import time

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.connectors.lifecycle import AuthorizationState  # noqa: E402
from src.connectors.oauth import FlowRefused, ScopeRefused, get_provider  # noqa: E402
from src.connectors.oauth.session import ExchangeRefused, OAuthSession  # noqa: E402
from src.connectors.oauth.tokens import TokenStorageUnavailable  # noqa: E402
from src.storage import encryption  # noqa: E402

ACCES = "ya29.a0AfB-JETON-SECRET"
RAFRAICHISSEMENT = "1//04-RAFRAICHISSEMENT-SECRET"
LECTURE_GMAIL = "https://www.googleapis.com/auth/gmail.readonly"
LECTURE_DRIVE = "https://www.googleapis.com/auth/drive.readonly"


@pytest.fixture
def environnement(monkeypatch):
    """Chiffrement et identifiants **factices**, posés par le test."""
    monkeypatch.setenv(encryption.KEY_VARIABLE, Fernet.generate_key().decode("ascii"))
    fournisseur = get_provider("google")
    monkeypatch.setenv(fournisseur.client_id_variable, "id-de-test")
    monkeypatch.setenv(fournisseur.client_secret_variable, "secret-de-test")
    monkeypatch.setenv(fournisseur.redirect_uri_variable, "https://exemple.test/retour")
    return fournisseur


@pytest.fixture
def session(environnement):
    """Une session demandant Gmail et Drive en lecture."""
    return OAuthSession(environnement, [LECTURE_GMAIL, LECTURE_DRIVE])


def _reponse(scope=LECTURE_GMAIL, rafraichissement=RAFRAICHISSEMENT, duree=3599):
    """Une réponse de jetons telle qu'un fournisseur en rend une."""
    reponse = {"access_token": ACCES, "expires_in": duree, "scope": scope}
    if rafraichissement:
        reponse["refresh_token"] = rafraichissement
    return reponse


def _autoriser(session, sujet="fatou", **kwargs):
    """Fait passer une personne par tout le flux."""
    depart = session.begin(sujet)
    return session.complete(depart.pending.state, "code-recu", _reponse(**kwargs))


# ----------------------------------------------------------------------
# 1. Le flux, de bout en bout
# ----------------------------------------------------------------------

def test_le_flux_complet_change_l_etat(session):
    """De « jamais accordé » à « utilisable », par le seul chemin prévu."""
    assert session.authorization_state("fatou") is AuthorizationState.NOT_AUTHORIZED

    _autoriser(session)

    assert session.authorization_state("fatou") is AuthorizationState.AUTHORIZED


def test_sans_reponse_la_methode_rend_la_requete_a_envoyer(session):
    """Aucun appel réseau n'est fait ici ; la requête est construite."""
    depart = session.begin("fatou")

    requete = session.complete(depart.pending.state, "code-recu")

    assert requete["method"] == "POST"
    assert requete["data"]["code_verifier"] == depart.pending.verifier


def test_un_etat_rejoue_ne_conserve_rien(session):
    """Le second passage ne doit rien retrouver, donc rien enregistrer."""
    depart = session.begin("fatou")
    session.complete(depart.pending.state, "code", _reponse())

    with pytest.raises(FlowRefused):
        session.complete(depart.pending.state, "code", _reponse())


def test_les_portees_accordees_priment_sur_celles_demandees(session):
    """
    Une personne peut ne cocher qu'une partie. Enregistrer ce qu'on a demandé
    laisserait croire à un accès qu'on n'a pas.
    """
    _autoriser(session, scope=LECTURE_GMAIL)

    assert session.granted_scopes("fatou") == [LECTURE_GMAIL]
    assert LECTURE_DRIVE in session.scopes


def test_une_reponse_sans_jeton_est_refusee(session):
    """Rien n'est conservé, et la cause du fournisseur est relayée telle quelle."""
    depart = session.begin("fatou")

    with pytest.raises(ExchangeRefused, match="invalid_grant"):
        session.complete(
            depart.pending.state, "code", {"error": "invalid_grant"}
        )

    assert session.authorization_state("fatou") is AuthorizationState.NOT_AUTHORIZED


def test_une_portee_hors_configuration_est_refusee(environnement):
    """Le moindre privilège vaut aussi pour un connecteur mal déclaré."""
    session = OAuthSession(environnement, ["https://www.googleapis.com/auth/gmail.modify"])

    with pytest.raises(ScopeRefused):
        session.begin("fatou")


def test_un_jeton_perime_n_est_pas_dit_absent(session):
    """« Périmé » et « jamais accordé » appellent deux suites différentes."""
    _autoriser(session, duree=1)

    assert session.authorization_state("fatou") is AuthorizationState.EXPIRED


def test_sans_identifiants_l_etat_est_non_configure(session, monkeypatch):
    """L'état de cet environnement, et il n'est pas confondu avec un refus."""
    monkeypatch.delenv(session.provider.client_id_variable, raising=False)

    assert session.authorization_state("fatou") is AuthorizationState.NOT_CONFIGURED


# ----------------------------------------------------------------------
# 2. Le retrait — l'ordre qui compte
# ----------------------------------------------------------------------

def test_l_effacement_local_a_toujours_lieu(session):
    """La seule partie que la plateforme maîtrise, et elle n'est conditionnée à rien."""
    _autoriser(session)

    verdict = session.revoke_detailed("fatou")

    assert verdict.forgotten_locally is True
    assert verdict.had_access is True
    assert session.authorization_state("fatou") is AuthorizationState.NOT_AUTHORIZED


def test_le_retrait_efface_meme_sans_cle_de_chiffrement(session, monkeypatch):
    """
    Le jeton à révoquer chez le fournisseur devient illisible, et l'effacement
    a lieu quand même. L'inverse serait un magasin incapable d'oublier.
    """
    _autoriser(session)
    monkeypatch.delenv(encryption.KEY_VARIABLE, raising=False)

    verdict = session.revoke_detailed("fatou")

    assert verdict.forgotten_locally is True
    assert session.tokens.raw_entry("google", "fatou") is None


def test_le_retrait_efface_meme_sans_identifiants(session, monkeypatch):
    """Reprendre son accès n'est pas une faveur demandée à la plateforme."""
    _autoriser(session)
    monkeypatch.delenv(session.provider.client_id_variable, raising=False)

    assert session.revoke_detailed("fatou").forgotten_locally is True


def test_nous_avons_oublie_ne_se_lit_pas_comme_le_fournisseur_a_oublie(session):
    """
    Le champ existe pour cette distinction précise. Cet environnement ne peut
    pas envoyer la requête de révocation, et le rapport le dit.
    """
    _autoriser(session)

    verdict = session.revoke_detailed("fatou")

    assert verdict.provider_request is not None
    assert verdict.provider_notified is False
    assert verdict.as_dict()["provider_notification_required"] is True


def test_la_requete_de_revocation_vise_le_jeton_de_rafraichissement(session):
    """Le révoquer invalide chez la plupart des fournisseurs toute la grappe."""
    _autoriser(session)

    verdict = session.revoke_detailed("fatou")

    assert verdict.provider_request["data"]["token"] == RAFRAICHISSEMENT
    assert verdict.provider_request["url"] == session.provider.revocation_endpoint


def test_sans_jeton_de_rafraichissement_le_jeton_d_acces_est_vise(session):
    """Tous les consentements n'en produisent pas."""
    _autoriser(session, rafraichissement=None)

    verdict = session.revoke_detailed("fatou")

    assert verdict.provider_request["data"]["token"] == ACCES


def test_retirer_un_acces_inexistant_n_est_pas_une_erreur(session):
    """C'est un rapport, pas une exception."""
    verdict = session.revoke_detailed("jamais-vu")

    assert verdict.had_access is False
    assert verdict.provider_request is None


def test_le_rapport_de_retrait_ne_porte_aucun_jeton(session):
    """Il finit dans une réponse d'API et dans l'audit."""
    _autoriser(session)

    serialise = str(session.revoke_detailed("fatou").as_dict())

    assert ACCES not in serialise
    assert RAFRAICHISSEMENT not in serialise


def test_le_rapport_de_session_ne_porte_aucun_jeton(session):
    """Le dernier chemin de sortie possible."""
    _autoriser(session)

    serialise = str(session.session_report("fatou"))

    assert ACCES not in serialise
    assert "secret-de-test" not in serialise
    assert "id-de-test" not in serialise


# ----------------------------------------------------------------------
# 3. Les routes
# ----------------------------------------------------------------------

@pytest.fixture
def cle(monkeypatch):
    """Une clé nommée, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin:fatou")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield "cle-admin"
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def sans_identifiants(monkeypatch):
    """L'état réel de cet environnement : aucun fournisseur configuré."""
    fournisseur = get_provider("google")
    for variable in (
        fournisseur.client_id_variable, fournisseur.client_secret_variable,
        fournisseur.redirect_uri_variable,
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(server_module, "_oauth_sessions", {})


def test_la_route_publie_l_etat_non_configure(cle, sans_identifiants):
    """Le verdict honnête de cet environnement, nommant ce qui manque."""
    with TestClient(app) as client:
        reponse = client.get("/oauth/providers", headers={"X-API-Key": cle})

    corps = reponse.json()
    assert reponse.status_code == 200
    assert "google" in corps["not_configured"]
    assert corps["configured"] == []


def test_sans_identifiants_la_route_d_autorisation_repond_cinq_cent_trois(
    cle, sans_identifiants
):
    """
    Mieux vaut 503 qu'une adresse de consentement qui ne mènerait nulle part —
    une personne la suivrait.
    """
    with TestClient(app) as client:
        reponse = client.post("/oauth/google/authorize", headers={"X-API-Key": cle})

    assert reponse.status_code == 503
    assert "GALSEN_OAUTH_GOOGLE_CLIENT_ID" in reponse.json()["detail"]


def test_un_fournisseur_inconnu_repond_quatre_cent_quatre(cle, sans_identifiants):
    """Aucun point d'accès n'est deviné."""
    with TestClient(app) as client:
        reponse = client.post("/oauth/microsoft/authorize", headers={"X-API-Key": cle})

    assert reponse.status_code == 404


def test_le_retrait_par_l_api_reussit_meme_non_configure(cle, sans_identifiants):
    """Le bouton doit marcher au moment précis où tout le reste ne marche pas."""
    with TestClient(app) as client:
        reponse = client.delete(
            "/oauth/google/authorization", headers={"X-API-Key": cle}
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["forgotten_locally"] is True
    assert corps["provider_notified"] is False


def test_l_autorisation_est_demandee_pour_l_appelant(cle, monkeypatch):
    """
    Demander l'accès au courrier de quelqu'un d'autre ne doit pas être une
    requête que l'on peut formuler : le sujet vient de la clé.
    """
    monkeypatch.setenv(encryption.KEY_VARIABLE, Fernet.generate_key().decode("ascii"))
    fournisseur = get_provider("google")
    monkeypatch.setenv(fournisseur.client_id_variable, "id-de-test")
    monkeypatch.setenv(fournisseur.client_secret_variable, "secret-de-test")
    monkeypatch.setenv(fournisseur.redirect_uri_variable, "https://exemple.test/retour")
    monkeypatch.setattr(server_module, "_oauth_sessions", {})

    with TestClient(app) as client:
        reponse = client.post(
            "/oauth/google/authorize",
            headers={"X-API-Key": cle},
            json={"subject": "moussa"},
        )

    assert reponse.status_code == 200
    assert reponse.json()["subject"] == "fatou"


def test_les_routes_oauth_exigent_une_cle(sans_identifiants):
    """Aucune de ces routes n'est publique."""
    with TestClient(app) as client:
        assert client.get("/oauth/providers").status_code in (401, 403)
        assert client.post("/oauth/google/authorize").status_code in (401, 403)
        assert client.delete("/oauth/google/authorization").status_code in (401, 403)


def test_aucune_reponse_de_route_ne_porte_de_jeton(cle, monkeypatch):
    """Vérifié sur le texte brut des réponses, pas sur leur structure."""
    monkeypatch.setenv(encryption.KEY_VARIABLE, Fernet.generate_key().decode("ascii"))
    fournisseur = get_provider("google")
    monkeypatch.setenv(fournisseur.client_id_variable, "id-de-test")
    monkeypatch.setenv(fournisseur.client_secret_variable, "secret-de-test")
    monkeypatch.setenv(fournisseur.redirect_uri_variable, "https://exemple.test/retour")
    monkeypatch.setattr(server_module, "_oauth_sessions", {})

    with TestClient(app) as client:
        for reponse in (
            client.get("/oauth/providers", headers={"X-API-Key": cle}),
            client.post("/oauth/google/authorize", headers={"X-API-Key": cle}),
            client.delete("/oauth/google/authorization", headers={"X-API-Key": cle}),
        ):
            assert "secret-de-test" not in reponse.text
            assert ACCES not in reponse.text


def test_un_jeton_conserve_survit_entre_deux_requetes(cle, monkeypatch):
    """
    Une session par processus, et non par requête : sans cela, un consentement
    serait perdu à la requête suivante.
    """
    monkeypatch.setenv(encryption.KEY_VARIABLE, Fernet.generate_key().decode("ascii"))
    fournisseur = get_provider("google")
    monkeypatch.setenv(fournisseur.client_id_variable, "id-de-test")
    monkeypatch.setenv(fournisseur.client_secret_variable, "secret-de-test")
    monkeypatch.setenv(fournisseur.redirect_uri_variable, "https://exemple.test/retour")
    monkeypatch.setattr(server_module, "_oauth_sessions", {})

    with TestClient(app) as client:
        premiere = client.post("/oauth/google/authorize", headers={"X-API-Key": cle})
        seconde = client.post("/oauth/google/authorize", headers={"X-API-Key": cle})

    session = server_module._oauth_sessions["google"]
    assert len(session.pending) == 2
    assert premiere.json()["state"] != seconde.json()["state"]


def test_le_magasin_sans_cle_refuse_de_conserver(environnement, monkeypatch):
    """La règle de 43.2 tient jusque dans la session : pas de repli en clair."""
    session = OAuthSession(environnement, [LECTURE_GMAIL])
    depart = session.begin("fatou")
    monkeypatch.delenv(encryption.KEY_VARIABLE, raising=False)

    with pytest.raises(TokenStorageUnavailable):
        session.complete(depart.pending.state, "code", _reponse())


def test_l_expiration_est_calculee_depuis_la_duree_annoncee(session):
    """`expires_in` est une durée ; la stocker telle quelle daterait de 1970."""
    instant = time.time()
    jeton = _autoriser(session, duree=3600)

    assert jeton.expires_at is not None
    assert instant + 3500 < jeton.expires_at < instant + 3700
