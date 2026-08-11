"""
Tests de la santé des connecteurs dans `/health` (VOLET 10, chapitre 06).

`/health` ignorait complètement la couche d'intégration : un opérateur devait
appeler deux routes pour savoir ce qui n'allait pas. La règle qui décide de tout
ici est l'inverse de l'intuition : **un connecteur non configuré ne dégrade
rien.** La plupart des déploiements n'en configurent aucun ; un indicateur rouge
en permanence est un indicateur qu'on ignore.
"""

import pytest

from src.api.health import ComponentHealthChecker
from src.connectors import get_shared_connector_registry, reset_shared_connector_registry
from src.connectors.types import ConnectorCheck, ConnectorKind, ConnectorStatus


class _ConnecteurFactice:
    """Connecteur minimal dont on choisit le statut."""

    def __init__(self, identifiant: str, statut: ConnectorStatus):
        self._id = identifiant
        self._statut = statut

    @property
    def connector_id(self) -> str:
        return self._id

    @property
    def kind(self) -> ConnectorKind:
        return ConnectorKind.EMAIL

    def describe(self):
        from src.connectors.types import ConnectorDescription
        return ConnectorDescription(connector_id=self._id, kind=self.kind, summary="factice")

    def is_configured(self) -> bool:
        return self._statut is not ConnectorStatus.NOT_CONFIGURED

    def check(self) -> ConnectorCheck:
        return ConnectorCheck(connector_id=self._id, kind=self.kind,
                              status=self._statut, detail="factice")


@pytest.fixture(autouse=True)
def registre_neuf():
    """Le registre de connecteurs est partagé par le processus."""
    reset_shared_connector_registry()
    yield
    reset_shared_connector_registry()


@pytest.fixture
def verificateur():
    """Vérificateur de santé sans moteur : seuls les connecteurs comptent ici."""
    return ComponentHealthChecker(start_time=0.0, version="test")


def test_les_connecteurs_apparaissent_dans_la_sante(verificateur):
    """Un opérateur doit lire « ce qui ne va pas » en une seule route."""
    rapport = verificateur.check_health().to_dict()
    assert "connectors" in rapport["components"]


def test_un_connecteur_non_configure_ne_degrade_pas(verificateur):
    """Sinon `/health` serait rouge sur tout déploiement qui n'en configure aucun."""
    get_shared_connector_registry().register(
        _ConnecteurFactice("email_absent", ConnectorStatus.NOT_CONFIGURED))

    connecteurs = verificateur.check_health().to_dict()["components"]["connectors"]
    assert connecteurs["status"] == "healthy"
    assert connecteurs["by_status"] == {"not_configured": 1}
    assert connecteurs["ready"] == 0


def test_un_connecteur_en_erreur_degrade(verificateur):
    """Configuré et injoignable : là, il y a bien quelque chose à regarder."""
    get_shared_connector_registry().register(
        _ConnecteurFactice("email_casse", ConnectorStatus.ERROR))

    connecteurs = verificateur.check_health().to_dict()["components"]["connectors"]
    assert connecteurs["status"] == "degraded"


def test_un_connecteur_pret_est_sain(verificateur):
    """Le cas nominal reste sain et compté comme prêt."""
    get_shared_connector_registry().register(
        _ConnecteurFactice("email_ok", ConnectorStatus.READY))

    connecteurs = verificateur.check_health().to_dict()["components"]["connectors"]
    assert connecteurs["status"] == "healthy"
    assert connecteurs["ready"] == 1


def test_un_registre_vide_est_sain(verificateur):
    """Aucun connecteur enregistré n'est pas une panne."""
    connecteurs = verificateur.check_health().to_dict()["components"]["connectors"]
    assert connecteurs["status"] == "healthy"
    assert connecteurs["total"] == 0


def test_la_note_explique_pourquoi_non_configure_est_sain(verificateur):
    """Sans elle, un opérateur cherche une panne qui n'existe pas."""
    connecteurs = verificateur.check_health().to_dict()["components"]["connectors"]
    assert "non configuré" in connecteurs["note"]
