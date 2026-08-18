"""
Le contrat de données d'un connecteur (phase 41.1).

Le contrat existant (ADR-007) répondait à trois questions sans rien déclencher :
qui es-tu, es-tu configuré, réponds-tu. Cela suffisait tant qu'un connecteur
parlait à une **machine** — un relais SMTP, un magasin d'objets — avec les
identifiants de la plateforme.

Gmail, Drive et Agenda, non. Ils lisent la donnée d'**une personne**, et deux
questions que l'ancien contrat ne posait pas deviennent tout le problème :
quelle classe de données, et pour le compte de qui.

Ce que ces tests gardent :

1. **Portée privée et lien à une personne vont ensemble, dans les deux sens.**
   Un connecteur privé non lié à quelqu'un n'isole rien ; un connecteur lié à
   quelqu'un mais déclaré public le ferait entrer dans le magasin commun.
2. **Le contrat est exigé à l'enregistrement**, seul endroit par lequel un
   connecteur devient atteignable.
3. **Le propriétaire vient du contrat**, jamais de l'appelant.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.connectors.contract import (  # noqa: E402
    ContractError,
    DataContract,
    conformance,
    contract_of,
    verify_contract,
)
from src.connectors.email_connector import SMTPEmailConnector  # noqa: E402
from src.connectors.registry import ConnectorRegistry  # noqa: E402
from src.connectors.storage_connector import LocalDiskStorageConnector  # noqa: E402
from src.connectors.types import ConnectorCheck, ConnectorDescription, ConnectorKind, ConnectorStatus  # noqa: E402
from src.security.isolation import IsolationError, OwnerKind, Visibility, may_store  # noqa: E402
from src.tool.capabilities import DataScope, Effect  # noqa: E402


class _Connecteur:
    """Un connecteur minimal, dont le contrat est fourni par le test."""

    def __init__(self, contrat, identifiant="essai"):
        self._contrat = contrat
        self._identifiant = identifiant

    @property
    def connector_id(self):
        return self._identifiant

    @property
    def kind(self):
        return ConnectorKind.OTHER

    @property
    def data_contract(self):
        return self._contrat

    def describe(self):
        return ConnectorDescription(
            connector_id=self._identifiant, kind=self.kind, summary="essai"
        )

    def is_configured(self):
        return True

    def check(self):
        return ConnectorCheck(
            connector_id=self._identifiant, kind=self.kind,
            status=ConnectorStatus.NOT_CONFIGURED,
        )


def _prive(**remplacements):
    """Un contrat privé cohérent, que chaque test déforme à sa façon."""
    champs = {
        "data_scope": DataScope.USER_PRIVATE,
        "per_subject": True,
        "effects": frozenset({Effect.READ, Effect.EXTERNAL}),
        "retention": "Rien : les messages ne sont pas conservés après l'appel.",
        "rationale": "Lecture d'une boîte de courrier, pour son titulaire.",
    }
    champs.update(remplacements)
    return DataContract(**champs)


# ----------------------------------------------------------------------
# 1. Les deux sens de la règle
# ----------------------------------------------------------------------

def test_un_connecteur_prive_doit_etre_lie_a_une_personne():
    """Sans personne pour qui isoler, l'isolation n'a pas de sens."""
    with pytest.raises(ContractError, match="personne pour qui isoler"):
        verify_contract("gmail", _prive(per_subject=False))


def test_un_connecteur_lie_a_une_personne_ne_peut_pas_se_dire_public():
    """L'autre sens : cette donnée entrerait dans le magasin commun."""
    with pytest.raises(ContractError, match="magasin commun"):
        verify_contract("gmail", _prive(data_scope=DataScope.PUBLIC))


def test_un_connecteur_prive_dit_ce_qu_il_conserve():
    """
    Le silence sur la rétention est la façon la plus courante de garder des
    données sans l'avoir décidé.
    """
    with pytest.raises(ContractError, match="rétention"):
        verify_contract("gmail", _prive(retention="   "))


def test_les_effets_sont_declares():
    """Un connecteur sans effet déclaré ne dit rien de ce qu'il fait."""
    with pytest.raises(ContractError, match="effets"):
        verify_contract("gmail", _prive(effects=frozenset()))


def test_un_contrat_prive_coherent_est_accepte():
    """La symétrie : la déclaration correcte passe."""
    contrat = verify_contract("gmail", _prive())

    assert contrat.data_scope is DataScope.USER_PRIVATE
    assert contrat.per_subject is True


# ----------------------------------------------------------------------
# 2. L'exigence à l'enregistrement
# ----------------------------------------------------------------------

def test_un_connecteur_sans_contrat_n_est_pas_enregistre():
    """
    Le vérifier plus tard reviendrait à le vérifier **après** le premier appel.
    Une intégration non déclarée est celle dont on découvre ensuite qu'elle
    lisait tout.
    """
    registre = ConnectorRegistry()

    with pytest.raises(ContractError, match="aucun contrat"):
        registre.register(_Connecteur(None))

    assert registre.count() == 0


def test_un_contrat_incoherent_n_est_pas_enregistre():
    """Le registre ne garde rien qu'il n'a pas pu vérifier."""
    registre = ConnectorRegistry()

    with pytest.raises(ContractError):
        registre.register(_Connecteur(_prive(per_subject=False)))

    assert registre.get("essai") is None


def test_un_contrat_qui_n_en_est_pas_un_est_refuse():
    """Un dictionnaire qui ressemble à un contrat n'en est pas un."""
    registre = ConnectorRegistry()

    with pytest.raises(ContractError, match="`DataContract`"):
        registre.register(_Connecteur({"data_scope": "public"}))


def test_un_connecteur_conforme_s_enregistre_normalement():
    """Exiger n'est pas bloquer."""
    registre = ConnectorRegistry()

    registre.register(_Connecteur(_prive()))

    assert registre.count() == 1
    assert contract_of(registre.get("essai")).per_subject is True


# ----------------------------------------------------------------------
# 3. Le propriétaire vient du contrat
# ----------------------------------------------------------------------

def test_le_proprietaire_est_deduit_du_contrat_pas_de_l_appelant():
    """Un connecteur privé produit de la donnée privée, quoi qu'il en pense."""
    proprietaire = _prive().owner_of("fatou")

    assert proprietaire.kind is OwnerKind.USER
    assert proprietaire.subject == "fatou"


def test_un_connecteur_prive_sans_sujet_ne_produit_rien_d_attribuable():
    """Appeler un connecteur privé pour personne est une erreur, pas un défaut."""
    with pytest.raises(IsolationError, match="obligatoire"):
        _prive().owner_of(None)


def test_ce_qu_un_connecteur_prive_produit_ne_va_pas_dans_un_magasin_partage():
    """Le bout de la chaîne : contrat → propriétaire → frontière (VOLET 40)."""
    autorise, raison = may_store(_prive().owner_of("fatou"), Visibility.SHARED)

    assert autorise is False
    assert "aucun filtre postérieur" in raison


# ----------------------------------------------------------------------
# 4. Les connecteurs réels du dépôt
# ----------------------------------------------------------------------

@pytest.mark.parametrize("connecteur", [
    SMTPEmailConnector(), LocalDiskStorageConnector(),
])
def test_les_connecteurs_existants_sont_conformes(connecteur):
    """Le contrat est ajouté à l'existant, il ne le remplace pas."""
    rapport = conformance(connecteur)

    assert rapport["conformant"] is True, rapport["missing"]
    assert rapport["coherent"] is True


def test_le_relais_smtp_n_est_lie_a_personne():
    """
    Il relaie le courrier **de la plateforme** : notifications, alertes, sous
    les identifiants du déploiement. Le connecteur Gmail de la vague II sera
    l'inverse exact — d'où deux déclarations et non une.
    """
    contrat = contract_of(SMTPEmailConnector())

    assert contrat.per_subject is False
    assert contrat.data_scope is DataScope.SYSTEM
    assert contrat.retention.strip() != ""


def test_le_rapport_de_conformite_nomme_les_manques():
    """Un connecteur incomplet doit apparaître, pas passer pour conforme."""
    class _Incomplet:
        connector_id = "incomplet"

    rapport = conformance(_Incomplet())

    assert rapport["conformant"] is False
    assert "data_contract" in rapport["missing"]
    assert "check" in rapport["missing"]


def test_un_contrat_serialise_ne_porte_aucun_secret():
    """Une description de connecteur finit dans une réponse d'API."""
    serialise = _prive().as_dict()

    assert serialise["data_scope"] == "user_private"
    assert serialise["per_subject"] is True
    assert set(serialise) == {
        "data_scope", "per_subject", "effects", "retention", "rationale",
    }
