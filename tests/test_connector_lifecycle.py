"""
Le cycle de vie d'un connecteur lié à une personne (phase 41.2).

Un connecteur de la plateforme a deux états : configuré, ou non. Un connecteur
lié à une personne en a cinq, et les confondre coûte cher — « périmé » se
rafraîchit sans rien redemander, « retiré » se redemande et ne se rafraîchit
jamais.

Ce que ces tests gardent :

1. **Un connecteur par sujet ne s'appelle pas sans sujet.** C'est la leçon du
   `user_id` facultatif de la mémoire, qui voulait dire « tout le monde » quand
   on l'oubliait.
2. **Le retrait fonctionne quand rien d'autre ne fonctionne.** Non configuré,
   injoignable, déjà périmé : `revoke` réussit. Sinon, le seul moment où le
   consentement compte vraiment serait celui où le bouton ne marche pas.
3. **Aucun jeton ne sort**, ni par un rapport, ni par une réponse d'API.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.connectors.contract import DataContract, conformance  # noqa: E402
from src.connectors.lifecycle import (  # noqa: E402
    AuthorizationRefused,
    AuthorizationState,
    SubjectBoundConnector,
    is_subject_bound,
    lifecycle_report,
)
from src.connectors.registry import ConnectorRegistry  # noqa: E402
from src.connectors.types import (  # noqa: E402
    ConnectorCheck,
    ConnectorDescription,
    ConnectorKind,
    ConnectorStatus,
)
from src.security.isolation import OwnerKind  # noqa: E402
from src.tool.capabilities import DataScope, Effect  # noqa: E402

JETON = "ya29.SECRET-JETON-A-NE-JAMAIS-PUBLIER"


class _BoiteAuxLettres(SubjectBoundConnector):
    """Un connecteur par sujet, sans réseau : les états sont posés par le test."""

    CONNECTOR_ID = "boite"

    def __init__(self, etats=None, configure=True):
        self._etats = dict(etats or {})
        self._configure = configure
        # Un secret, pour vérifier qu'aucun rapport ne le publie.
        self._jetons = {sujet: JETON for sujet in self._etats}

    @property
    def connector_id(self):
        return self.CONNECTOR_ID

    @property
    def kind(self):
        return ConnectorKind.EMAIL

    @property
    def data_contract(self):
        return DataContract(
            data_scope=DataScope.USER_PRIVATE,
            per_subject=True,
            effects=frozenset({Effect.READ, Effect.EXTERNAL}),
            retention="Rien : les messages ne sont pas conservés après l'appel.",
            rationale="Lecture d'une boîte, pour son titulaire seul.",
        )

    def describe(self):
        return ConnectorDescription(
            connector_id=self.CONNECTOR_ID, kind=self.kind,
            summary="Boîte aux lettres d'une personne",
        )

    def is_configured(self):
        return self._configure

    def check(self):
        return ConnectorCheck(
            connector_id=self.CONNECTOR_ID, kind=self.kind,
            status=ConnectorStatus.READY if self._configure
            else ConnectorStatus.NOT_CONFIGURED,
        )

    def authorization_state(self, subject):
        if not self._configure:
            return AuthorizationState.NOT_CONFIGURED
        return self._etats.get(subject, AuthorizationState.NOT_AUTHORIZED)

    def revoke(self, subject):
        self._jetons.pop(subject, None)
        return self._etats.pop(subject, None) is not None

    def lire(self):
        """L'opération métier, atteinte seulement par un lien."""
        return ["message 1", "message 2"]


def _boite(etat=AuthorizationState.AUTHORIZED, sujet="fatou", configure=True):
    """Une boîte où `sujet` est dans l'état demandé."""
    return _BoiteAuxLettres({sujet: etat}, configure=configure)


# ----------------------------------------------------------------------
# 1. Le lien à une personne
# ----------------------------------------------------------------------

def test_un_connecteur_par_sujet_ne_s_appelle_pas_sans_sujet():
    """La leçon du `user_id` facultatif : l'oubli est le mode de panne."""
    with pytest.raises(ValueError, match="sans sujet"):
        _boite().for_subject("")

    with pytest.raises(ValueError):
        _boite().for_subject("   ")


def test_le_lien_sait_dire_le_proprietaire_de_ce_qu_il_rend():
    """Contrat → propriétaire → frontière. L'appelant ne choisit rien."""
    lien = _boite().for_subject("fatou")

    proprietaire = lien.owner()

    assert proprietaire.kind is OwnerKind.USER
    assert proprietaire.subject == "fatou"


def test_une_operation_passe_quand_l_acces_est_utilisable():
    """Encadrer n'est pas empêcher."""
    lien = _boite().for_subject("fatou")

    assert lien.call(lien.connector.lire) == ["message 1", "message 2"]


@pytest.mark.parametrize("etat", [
    AuthorizationState.NOT_AUTHORIZED,
    AuthorizationState.EXPIRED,
    AuthorizationState.REVOKED,
])
def test_une_operation_est_refusee_hors_autorisation(etat):
    """Trois façons de ne pas avoir accès, trois refus."""
    lien = _boite(etat).for_subject("fatou")

    with pytest.raises(AuthorizationRefused, match=etat.value):
        lien.call(lien.connector.lire)


def test_le_refus_dit_ce_qu_il_faut_faire_ensuite():
    """
    « Périmé » se rafraîchit sans rien redemander ; « retiré » se redemande et
    ne se rafraîchit jamais. Un message commun confondrait deux actions
    opposées.
    """
    with pytest.raises(AuthorizationRefused, match="rafraîchissement"):
        lien = _boite(AuthorizationState.EXPIRED).for_subject("fatou")
        lien.call(lien.connector.lire)

    with pytest.raises(AuthorizationRefused, match="redemande"):
        lien = _boite(AuthorizationState.REVOKED).for_subject("fatou")
        lien.call(lien.connector.lire)


def test_l_acces_d_une_personne_ne_vaut_pas_pour_une_autre():
    """L'autorisation est par personne, comme la donnée qu'elle ouvre."""
    boite = _boite(sujet="fatou")

    assert boite.for_subject("fatou").state().usable is True
    assert boite.for_subject("moussa").state() is AuthorizationState.NOT_AUTHORIZED


# ----------------------------------------------------------------------
# 2. Le retrait
# ----------------------------------------------------------------------

def test_le_retrait_fonctionne_meme_non_configure():
    """
    Le point qui compte. Faire dépendre ce chemin d'un identifiant présent
    reviendrait à ce que le seul moment où le consentement compte vraiment soit
    celui où le bouton ne marche pas.
    """
    boite = _BoiteAuxLettres({"fatou": AuthorizationState.AUTHORIZED}, configure=False)

    assert boite.revoke("fatou") is True
    assert boite._jetons == {}


@pytest.mark.parametrize("etat", list(AuthorizationState))
def test_le_retrait_reussit_depuis_n_importe_quel_etat(etat):
    """Périmé, retiré, jamais accordé : le retrait ne lève dans aucun cas."""
    boite = _BoiteAuxLettres({"fatou": etat})

    boite.revoke("fatou")

    assert boite.authorization_state("fatou") is AuthorizationState.NOT_AUTHORIZED


def test_le_retrait_dit_s_il_y_avait_quelque_chose():
    """Retirer un accès inexistant n'est pas une erreur, c'est un `False`."""
    boite = _boite()

    assert boite.revoke("fatou") is True
    assert boite.revoke("fatou") is False


def test_le_retrait_efface_le_jeton():
    """Retirer l'accès sans effacer le jeton ne retirerait rien du tout."""
    boite = _boite()

    boite.revoke("fatou")

    assert "fatou" not in boite._jetons


# ----------------------------------------------------------------------
# 3. Le rapport
# ----------------------------------------------------------------------

def test_un_connecteur_de_plateforme_n_a_pas_d_etat_par_personne():
    """Son accès ne dépend d'aucune personne : le dire vaut mieux que l'inventer."""
    from src.connectors.email_connector import SMTPEmailConnector

    rapport = lifecycle_report(SMTPEmailConnector(), subject="fatou")

    assert rapport["per_subject"] is False
    assert "ne dépend d'aucune personne" in rapport["detail"]


def test_un_connecteur_par_sujet_sans_sujet_ne_publie_aucun_etat_global():
    """
    Publier un état global agrégerait des personnes ; il n'y a pas d'état
    « du connecteur » quand l'accès est par personne.
    """
    rapport = lifecycle_report(_boite(), subject=None)

    assert rapport["per_subject"] is True
    assert rapport["state"] is None
    assert "personne nommée" in rapport["detail"]


def test_aucun_rapport_ne_publie_de_jeton():
    """Un rapport de cycle de vie finit dans une réponse d'API et dans l'audit."""
    boite = _boite()

    textes = [
        str(lifecycle_report(boite, "fatou")),
        str(boite.for_subject("fatou").as_dict()),
        str(conformance(boite)),
    ]

    for texte in textes:
        assert JETON not in texte
        assert "ya29" not in texte


def test_le_lien_par_sujet_se_lit_sur_le_contrat_pas_sur_la_classe():
    """
    C'est la déclaration qui fait foi. Hériter du contrat sans se déclarer par
    sujet est justement l'incohérence que `verify_contract` refuse.
    """
    from src.connectors.email_connector import SMTPEmailConnector

    assert is_subject_bound(_boite()) is True
    assert is_subject_bound(SMTPEmailConnector()) is False


# ----------------------------------------------------------------------
# 4. L'API
# ----------------------------------------------------------------------

@pytest.fixture
def cles(monkeypatch):
    """Une clé admin nommée, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin:fatou")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield "cle-admin"
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def registre_avec_boite(monkeypatch):
    """Un registre de connecteurs portant la boîte de test."""
    registre = ConnectorRegistry()
    registre.register(_boite())
    monkeypatch.setattr(
        server_module, "get_shared_connector_registry", lambda: registre
    )
    return registre


def test_la_route_publie_le_contrat_et_l_etat(cles, registre_avec_boite):
    """L'état publié est celui de **l'appelant**, pas d'un sujet du corps."""
    with TestClient(app) as client:
        reponse = client.get(
            "/connectors/boite/contract", headers={"X-API-Key": cles}
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["conformant"] is True
    assert corps["contract"]["per_subject"] is True
    assert corps["lifecycle"]["subject"] == "fatou"
    assert corps["lifecycle"]["state"] == "authorized"


def test_la_route_ne_publie_aucun_jeton(cles, registre_avec_boite):
    """Le dernier endroit où un secret pourrait sortir."""
    with TestClient(app) as client:
        reponse = client.get(
            "/connectors/boite/contract", headers={"X-API-Key": cles}
        )

    assert JETON not in reponse.text
    assert "ya29" not in reponse.text


def test_un_connecteur_inconnu_repond_quatre_cent_quatre(cles, registre_avec_boite):
    """Contrairement à un outil, un connecteur inconnu est réellement absent."""
    with TestClient(app) as client:
        reponse = client.get(
            "/connectors/jamais_vu/contract", headers={"X-API-Key": cles}
        )

    assert reponse.status_code == 404


def test_la_route_publie_ce_qui_ne_s_obtient_jamais(cles, registre_avec_boite):
    """
    Phase 42.2 : ce qu'une personne doit lire **avant** de consentir voyage
    avec la description du connecteur, pas dans un document à côté.
    """
    with TestClient(app) as client:
        reponse = client.get(
            "/connectors/boite/contract", headers={"X-API-Key": cles}
        )

    securite = reponse.json()["safety"]
    assert securite["destructive"] == []
    assert any("jamais une instruction" in ligne for ligne in securite["never"])
