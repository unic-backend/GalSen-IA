"""
Tests de l'inventaire d'état local au processus (VOLET 02 ch. 10, ADR-009).

Ces tests protègent une affirmation, pas un mécanisme : la plateforme dit
qu'elle ne tourne qu'en une seule instance, et nomme ce qui casserait s'il y en
avait deux. Le risque n'est pas que le code se trompe — c'est qu'il devienne
faux en silence, le jour où un magasin partagé apparaît sans que le rapport soit
mis à jour, ou l'inverse.

Un test va plus loin que l'inventaire : il **démontre** le point dangereux, une
clé révoquée sur une instance qui continue d'ouvrir la porte sur une autre.
Cette démonstration est la raison d'être de l'ADR-009 ; si elle cessait un jour
d'être vraie, ce test échouerait et l'ADR devrait être revu.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.rbac import RBACManager, hash_api_key  # noqa: E402
from src.api.scaling import (  # noqa: E402
    INSTANCE_ID_VARIABLE,
    SCOPE_INSTANCE,
    SCOPE_SHARED,
    STORAGE_BACKEND_VARIABLE,
    instance_id,
    scaling_report,
    state_inventory,
)
from src.api.server import app  # noqa: E402


@pytest.fixture
def client():
    """Client HTTP sur l'application réelle."""
    with TestClient(app) as instance:
        yield instance


@pytest.fixture
def sans_variables(monkeypatch):
    """Environnement neutre : ni identifiant d'instance, ni backend imposé."""
    monkeypatch.delenv(INSTANCE_ID_VARIABLE, raising=False)
    monkeypatch.delenv(STORAGE_BACKEND_VARIABLE, raising=False)


class TestIdentiteDInstance:
    """L'instance qui répond doit pouvoir être nommée."""

    def test_valeur_declaree_utilisee(self, monkeypatch):
        """Un identifiant fourni par le déploiement prime sur tout le reste."""
        monkeypatch.setenv(INSTANCE_ID_VARIABLE, "dakar-01")
        assert instance_id() == "dakar-01"

    def test_valeur_vide_ignoree(self, monkeypatch):
        """Une variable définie mais vide ne doit pas produire un nom vide."""
        monkeypatch.setenv(INSTANCE_ID_VARIABLE, "   ")
        assert instance_id() != ""
        assert str(os.getpid()) in instance_id()

    def test_repli_distingue_deux_processus(self, sans_variables):
        """Sans déclaration, `<hôte>:<pid>` suffit à séparer deux processus."""
        identifiant = instance_id()
        assert ":" in identifiant
        assert identifiant.endswith(f":{os.getpid()}")


class TestInventaire:
    """L'inventaire doit décrire l'état réel, pas une liste figée."""

    def test_sous_systemes_connus_presents(self, sans_variables):
        """Retirer un sous-système de l'inventaire doit faire échouer un test."""
        noms = {composant.name for composant in state_inventory()}
        assert {
            "api_key_revocations",
            "rate_limit_counters",
            "uploaded_files",
            "notifications",
            "engine_state",
            "connector_registry",
            "engine_registry",
        } <= noms

    def test_chaque_composant_est_documente(self, sans_variables):
        """Un composant sans conséquence énoncée n'apprend rien à un opérateur."""
        for composant in state_inventory():
            assert composant.detail.strip(), composant.name
            assert composant.consequence.strip(), composant.name
            assert composant.scope in (SCOPE_INSTANCE, SCOPE_SHARED), composant.name

    def test_les_bloquants_viennent_en_premier(self, sans_variables):
        """L'ordre porte la gravité : lire le premier élément doit suffire."""
        bloquants = [composant.blocking for composant in state_inventory()]
        assert bloquants[0] is True
        # Une fois passé au non bloquant, on n'y revient pas.
        assert bloquants == sorted(bloquants, reverse=True)

    def test_revocation_bloquante_et_locale(self, sans_variables):
        """C'est le point dangereux : il ne doit jamais être classé anodin."""
        revocations = next(
            composant
            for composant in state_inventory()
            if composant.name == "api_key_revocations"
        )
        assert revocations.scope == SCOPE_INSTANCE
        assert revocations.blocking is True

    def test_registres_non_bloquants(self, sans_variables):
        """Un registre reconstruit à l'identique ne casse rien : ne pas l'alarmer."""
        for nom in ("connector_registry", "engine_registry"):
            composant = next(c for c in state_inventory() if c.name == nom)
            assert composant.blocking is False

    def test_sqlite_partage_l_etat_des_moteurs(self, monkeypatch):
        """Avec ADR-005 actif, l'état des moteurs cesse d'être local au processus."""
        monkeypatch.setenv(STORAGE_BACKEND_VARIABLE, "SQLite")
        moteurs = next(c for c in state_inventory() if c.name == "engine_state")
        assert moteurs.scope == SCOPE_SHARED
        assert moteurs.blocking is False
        # La réserve doit rester visible : SQLite suppose un disque local.
        assert moteurs.caveat

    def test_en_memoire_bloque_l_etat_des_moteurs(self, sans_variables):
        """Backend par défaut : deux instances mémorisent chacune de leur côté."""
        moteurs = next(c for c in state_inventory() if c.name == "engine_state")
        assert moteurs.scope == SCOPE_INSTANCE
        assert moteurs.blocking is True

    def test_serialisation_sans_champ_vide(self, sans_variables):
        """Un `caveat` vide ne doit pas encombrer la réponse."""
        for composant in state_inventory():
            donnees = composant.to_dict()
            assert ("caveat" in donnees) == bool(composant.caveat)


class TestRapport:
    """Le rapport doit répondre à une question, pas énumérer des faits."""

    def test_verdict_negatif_aujourd_hui(self, sans_variables):
        """Tant qu'un sous-système bloquant existe, la réponse est non."""
        rapport = scaling_report()
        assert rapport["multi_instance_ready"] is False
        assert rapport["deployment_model"] == "single-instance"

    def test_les_bloquants_sont_nommes(self, sans_variables):
        """Un verdict négatif sans raison n'est pas actionnable."""
        rapport = scaling_report()
        assert "api_key_revocations" in rapport["blocking"]
        assert rapport["blocking"]

    def test_verdict_coherent_avec_l_inventaire(self, sans_variables):
        """Le verdict est dérivé, jamais écrit à la main."""
        rapport = scaling_report()
        attendus = [c.name for c in state_inventory() if c.blocking]
        assert rapport["blocking"] == attendus

    def test_le_rapport_designe_son_adr(self, sans_variables):
        """Un opérateur doit pouvoir remonter au raisonnement."""
        assert scaling_report()["reference"] == "ADR-009"

    def test_le_rapport_nomme_l_instance(self, monkeypatch):
        """Deux rapports contradictoires doivent être attribuables."""
        monkeypatch.setenv(INSTANCE_ID_VARIABLE, "dakar-02")
        assert scaling_report()["instance"] == "dakar-02"


class TestRevocationLocaleDemontree:
    """Démontre le trou que l'ADR-009 documente, plutôt que de l'affirmer."""

    def test_une_cle_revoquee_ouvre_encore_une_autre_instance(self, monkeypatch):
        """Deux instances, une révocation : la clé compromise passe encore.

        C'est le fait qui justifie l'ADR. S'il cessait d'être vrai, ce test
        échouerait — et ce serait le signal que l'ADR doit être révisé.
        """
        monkeypatch.setenv("GALSEN_API_KEYS", "cle-compromise:admin")

        instance_a = RBACManager()
        instance_b = RBACManager()

        empreinte = hash_api_key("cle-compromise")[:12]
        assert instance_a.revoke(empreinte) is True

        # L'instance où la révocation a été posée refuse la clé…
        with pytest.raises(PermissionError):
            instance_a.authenticate("cle-compromise")

        # …et l'autre l'accepte toujours, avec les droits d'administration.
        assert instance_b.authenticate("cle-compromise") is not None


class TestExpositionParLApi:
    """La contrainte doit être lisible là où elle peut faire du mal."""

    def test_la_sante_porte_le_rapport(self, client):
        """`/health` est le seul endroit qu'un opérateur consulte avant de dupliquer."""
        sante = client.get("/health").json()
        assert "scaling" in sante
        assert sante["scaling"]["multi_instance_ready"] is False
        assert sante["scaling"]["components"]

    def test_le_rapport_ne_divulgue_aucun_secret(self, client):
        """`/health` n'est pas authentifiée : elle ne doit nommer ni clé ni chemin."""
        import json

        contenu = json.dumps(client.get("/health").json()["scaling"])
        for interdit in ("GALSEN_API_KEYS=", "X-API-Key", "password", "token"):
            assert interdit not in contenu

    def test_la_sante_reste_lisible_sans_cle(self, client):
        """Ajouter une section ne doit pas rendre `/health` authentifiée."""
        assert client.get("/health").status_code == 200
