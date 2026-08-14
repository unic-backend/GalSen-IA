"""
Tests unitaires de la couche de connecteurs externes (ADR-007).

La couche démarre sans aucun connecteur concret : ce qui est testé ici est le
contrat lui-même — un connecteur doit pouvoir dire ce qu'il est, s'il est
configuré et s'il répond, sans jamais lever ni exposer un secret — et le
registre qui les inventorie.

Aucun appel réseau n'est fait : les connecteurs de test sont écrits pour ça.
"""


import pytest

from src.connectors.contract import DataContract
from src.tool.capabilities import DataScope, Effect
from src.connectors import (
    Connector,
    ConnectorCheck,
    ConnectorDescription,
    ConnectorKind,
    ConnectorRegistry,
    ConnectorStatus,
    get_shared_connector_registry,
    reset_shared_connector_registry,
)


class ConnecteurFactice(Connector):
    """Connecteur de test : lit une variable d'environnement, ne joint rien."""

    VARIABLES = ["GALSEN_TEST_CONNECTOR_KEY"]

    def __init__(self, identifiant="factice", kind=ConnectorKind.EMAIL):
        self._identifiant = identifiant
        self._kind = kind

    @property
    def connector_id(self) -> str:
        return self._identifiant

    @property
    def kind(self) -> ConnectorKind:
        return self._kind

    @property
    def data_contract(self) -> DataContract:
        """
        Un double déclare son contrat, comme un vrai connecteur.

        Sans cette déclaration le registre le refuserait — et il aurait raison :
        « non déclaré » n'est pas « inoffensif », y compris pour un double.
        """
        return DataContract(
            data_scope=DataScope.SYSTEM,
            per_subject=False,
            effects=frozenset({Effect.READ}),
            retention="Rien.",
            rationale="Connecteur de test, sans effet réel.",
        )

    def describe(self) -> ConnectorDescription:
        return ConnectorDescription(
            connector_id=self._identifiant,
            kind=self._kind,
            summary="Connecteur de test, sans effet",
            environment_variables=list(self.VARIABLES),
            operations=["check"],
            owner="équipe plateforme",
        )

    def is_configured(self) -> bool:
        return not self._missing_variables(self.VARIABLES)

    def check(self) -> ConnectorCheck:
        manquantes = self._missing_variables(self.VARIABLES)
        if manquantes:
            return self._not_configured(manquantes)
        return ConnectorCheck(
            connector_id=self._identifiant,
            kind=self._kind,
            status=ConnectorStatus.READY,
            detail="Connecteur de test opérationnel",
        )


class ConnecteurCasse(Connector):
    """Connecteur volontairement défectueux : sa vérification lève."""

    @property
    def connector_id(self) -> str:
        return "casse"

    @property
    def kind(self) -> ConnectorKind:
        return ConnectorKind.STORAGE

    @property
    def data_contract(self) -> DataContract:
        """
        Un double déclare son contrat, comme un vrai connecteur.

        Sans cette déclaration le registre le refuserait — et il aurait raison :
        « non déclaré » n'est pas « inoffensif », y compris pour un double.
        """
        return DataContract(
            data_scope=DataScope.SYSTEM,
            per_subject=False,
            effects=frozenset({Effect.READ}),
            retention="Rien.",
            rationale="Connecteur de test, sans effet réel.",
        )

    def describe(self) -> ConnectorDescription:
        return ConnectorDescription(
            connector_id="casse", kind=ConnectorKind.STORAGE, summary="Défectueux",
        )

    def is_configured(self) -> bool:
        return True

    def check(self) -> ConnectorCheck:
        raise RuntimeError("le système externe a explosé")


@pytest.fixture
def registre():
    """Registre neuf pour chaque test."""
    return ConnectorRegistry()


@pytest.fixture(autouse=True)
def environnement_propre(monkeypatch):
    """Retire la variable de test héritée de l'environnement réel."""
    monkeypatch.delenv("GALSEN_TEST_CONNECTOR_KEY", raising=False)


class TestContratConnecteur:
    """Vérifie ce qu'un connecteur doit savoir répondre."""

    def test_non_configure_sans_variable(self):
        """Sans variable d'environnement, le connecteur se déclare non configuré."""
        assert ConnecteurFactice().is_configured() is False

    def test_configure_avec_variable(self, monkeypatch):
        """La variable présente suffit à déclarer le connecteur configuré."""
        monkeypatch.setenv("GALSEN_TEST_CONNECTOR_KEY", "valeur")
        assert ConnecteurFactice().is_configured() is True

    def test_variable_vide_vaut_absente(self, monkeypatch):
        """Une variable définie mais vide ne doit pas compter comme configurée."""
        monkeypatch.setenv("GALSEN_TEST_CONNECTOR_KEY", "")
        assert ConnecteurFactice().is_configured() is False

    def test_check_sans_configuration(self):
        """La vérification signale l'absence de configuration et les variables manquantes."""
        resultat = ConnecteurFactice().check()
        assert resultat.status is ConnectorStatus.NOT_CONFIGURED
        assert resultat.is_ready is False
        assert "GALSEN_TEST_CONNECTOR_KEY" in resultat.detail

    def test_check_configure(self, monkeypatch):
        """Configuré, le connecteur se déclare prêt."""
        monkeypatch.setenv("GALSEN_TEST_CONNECTOR_KEY", "valeur")
        resultat = ConnecteurFactice().check()
        assert resultat.status is ConnectorStatus.READY
        assert resultat.is_ready is True

    def test_describe_n_expose_aucun_secret(self, monkeypatch):
        """La description nomme les variables, jamais leur valeur (ADR-004)."""
        monkeypatch.setenv("GALSEN_TEST_CONNECTOR_KEY", "secret-tres-confidentiel")
        description = ConnecteurFactice().describe().to_dict()
        assert "GALSEN_TEST_CONNECTOR_KEY" in description["environment_variables"]
        assert "secret-tres-confidentiel" not in str(description)

    def test_le_secret_n_est_pas_conserve_en_attribut(self, monkeypatch):
        """Le connecteur relit l'environnement et ne garde pas le secret."""
        monkeypatch.setenv("GALSEN_TEST_CONNECTOR_KEY", "secret-tres-confidentiel")
        connecteur = ConnecteurFactice()
        connecteur.is_configured()
        assert "secret-tres-confidentiel" not in str(vars(connecteur))

    def test_describe_serialise_les_champs_utiles(self):
        """La description doit porter le rôle, les opérations et le propriétaire."""
        description = ConnecteurFactice().describe().to_dict()
        assert description["connector_id"] == "factice"
        assert description["kind"] == "email"
        assert description["operations"] == ["check"]
        assert description["owner"] == "équipe plateforme"


class TestSerialisationDesResultats:
    """Vérifie la forme des résultats de vérification."""

    def test_to_dict_horodate_en_iso(self):
        """L'horodatage doit être sérialisé en ISO UTC."""
        resultat = ConnectorCheck(
            connector_id="x", kind=ConnectorKind.EMAIL, status=ConnectorStatus.READY,
            checked_at=1785900000.0,
        )
        assert resultat.to_dict()["checked_at"].startswith("2026-")

    def test_to_dict_omet_les_champs_vides(self):
        """Sans détail ni latence, ces champs ne doivent pas apparaître."""
        resultat = ConnectorCheck(
            connector_id="x", kind=ConnectorKind.EMAIL, status=ConnectorStatus.READY,
        )
        assert "detail" not in resultat.to_dict()
        assert "latency_ms" not in resultat.to_dict()

    def test_latence_arrondie(self):
        """La latence doit être arrondie pour rester lisible."""
        resultat = ConnectorCheck(
            connector_id="x", kind=ConnectorKind.EMAIL, status=ConnectorStatus.READY,
            latency_ms=12.34567,
        )
        assert resultat.to_dict()["latency_ms"] == 12.35


class TestRegistre:
    """Vérifie l'inventaire des connecteurs."""

    def test_enregistrer_et_retrouver(self, registre):
        """Un connecteur enregistré doit être retrouvable par identifiant."""
        connecteur = ConnecteurFactice()
        registre.register(connecteur)
        assert registre.get("factice") is connecteur
        assert registre.count() == 1

    def test_identifiant_inconnu(self, registre):
        """Un identifiant inconnu retourne None."""
        assert registre.get("absent") is None

    def test_doublon_refuse(self, registre):
        """Deux connecteurs de même identifiant : le second est refusé."""
        registre.register(ConnecteurFactice())
        with pytest.raises(ValueError, match="déjà enregistré"):
            registre.register(ConnecteurFactice())

    def test_reenregistrer_la_meme_instance_est_permis(self, registre):
        """Réenregistrer exactement la même instance ne doit pas lever."""
        connecteur = ConnecteurFactice()
        registre.register(connecteur)
        registre.register(connecteur)
        assert registre.count() == 1

    def test_identifiant_vide_refuse(self, registre):
        """Un identifiant vide doit être refusé."""
        with pytest.raises(ValueError, match="identifiant non vide"):
            registre.register(ConnecteurFactice(identifiant="   "))

    def test_liste_triee(self, registre):
        """La liste doit être triée par identifiant, pour être stable."""
        registre.register(ConnecteurFactice(identifiant="zeta"))
        registre.register(ConnecteurFactice(identifiant="alpha"))
        assert [c.connector_id for c in registre.list_connectors()] == ["alpha", "zeta"]

    def test_filtre_par_categorie(self, registre):
        """Le filtre par catégorie ne doit retourner que celle demandée."""
        registre.register(ConnecteurFactice(identifiant="courriel", kind=ConnectorKind.EMAIL))
        registre.register(ConnecteurFactice(identifiant="agenda", kind=ConnectorKind.CALENDAR))
        resultats = registre.list_connectors(kind=ConnectorKind.CALENDAR)
        assert [c.connector_id for c in resultats] == ["agenda"]

    def test_categories_couvertes(self, registre):
        """Le registre doit savoir dire quelles catégories sont couvertes."""
        registre.register(ConnecteurFactice(identifiant="courriel", kind=ConnectorKind.EMAIL))
        registre.register(ConnecteurFactice(identifiant="fichiers", kind=ConnectorKind.STORAGE))
        assert registre.kinds() == [ConnectorKind.EMAIL, ConnectorKind.STORAGE]

    def test_retirer_un_connecteur(self, registre):
        """Le retrait doit fonctionner et signaler l'absence."""
        registre.register(ConnecteurFactice())
        assert registre.unregister("factice") is True
        assert registre.unregister("factice") is False
        assert registre.count() == 0

    def test_describe_all_sans_appel_reseau(self, registre):
        """L'inventaire descriptif ne doit dépendre d'aucun système externe."""
        registre.register(ConnecteurFactice())
        descriptions = registre.describe_all()
        assert len(descriptions) == 1
        assert descriptions[0]["connector_id"] == "factice"

    def test_describe_all_ignore_un_connecteur_indescriptible(self, registre):
        """Une description en échec ne doit pas priver l'opérateur des autres."""
        casse = ConnecteurFactice(identifiant="indescriptible")

        def description_impossible():
            raise RuntimeError("description impossible")

        casse.describe = description_impossible  # remplace la méthode de cette instance
        registre.register(casse)
        registre.register(ConnecteurFactice(identifiant="sain"))
        descriptions = registre.describe_all()
        assert [d["connector_id"] for d in descriptions] == ["sain"]


class TestVerificationAgregee:
    """Vérifie le rapport global, celui destiné à /health et aux opérateurs."""

    def test_rapport_vide(self, registre):
        """Sans connecteur, le rapport doit rester valide."""
        rapport = registre.check_all()
        assert rapport == {"total": 0, "ready": 0, "by_status": {}, "connectors": []}

    def test_rapport_compte_les_prets(self, registre, monkeypatch):
        """Le rapport doit compter les connecteurs prêts."""
        monkeypatch.setenv("GALSEN_TEST_CONNECTOR_KEY", "valeur")
        registre.register(ConnecteurFactice())
        rapport = registre.check_all()
        assert rapport["total"] == 1
        assert rapport["ready"] == 1
        assert rapport["by_status"] == {"ready": 1}

    def test_rapport_distingue_les_statuts(self, registre):
        """Non configuré et en erreur doivent être comptés séparément."""
        registre.register(ConnecteurFactice())
        registre.register(ConnecteurCasse())
        rapport = registre.check_all()
        assert rapport["ready"] == 0
        assert rapport["by_status"] == {"not_configured": 1, "error": 1}

    def test_connecteur_defectueux_ne_casse_pas_le_rapport(self, registre):
        """Un connecteur qui lève devient un statut, pas une exception."""
        registre.register(ConnecteurCasse())
        rapport = registre.check_all()
        detail = rapport["connectors"][0]
        assert detail["status"] == "error"
        assert "le système externe a explosé" in detail["detail"]

    def test_latence_renseignee_automatiquement(self, registre):
        """Le registre doit mesurer la latence quand le connecteur ne le fait pas."""
        registre.register(ConnecteurFactice())
        assert registre.check_all()["connectors"][0]["latency_ms"] >= 0

    def test_verification_unitaire(self, registre):
        """La vérification d'un connecteur précis doit être possible."""
        registre.register(ConnecteurFactice())
        assert registre.check("factice").status is ConnectorStatus.NOT_CONFIGURED
        assert registre.check("absent") is None


class TestRegistrePartage:
    """Vérifie le registre partagé par toute la plateforme."""

    def test_meme_instance(self):
        """Deux appels doivent retourner le même registre."""
        reset_shared_connector_registry()
        try:
            assert get_shared_connector_registry() is get_shared_connector_registry()
        finally:
            reset_shared_connector_registry()

    def test_reinitialisation(self):
        """La réinitialisation doit vider l'inventaire, pour l'isolation des tests."""
        reset_shared_connector_registry()
        try:
            get_shared_connector_registry().register(ConnecteurFactice())
            assert get_shared_connector_registry().count() == 1
            reset_shared_connector_registry()
            assert get_shared_connector_registry().count() == 0
        finally:
            reset_shared_connector_registry()
