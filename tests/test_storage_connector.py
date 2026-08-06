"""
Tests du connecteur de stockage sur disque local (phase 3.4, ADR-007).

Une clé de stockage vient souvent d'une requête : elle doit être traitée comme
une entrée hostile. Le confinement à la racine est donc testé en premier — `..`,
chemin absolu, lien symbolique — avant les opérations elles-mêmes.

Tout se passe dans un répertoire temporaire : rien n'est écrit dans le dépôt.
"""

import os
from unittest.mock import patch

import pytest

from src.connectors import ConnectorKind, ConnectorStatus
from src.connectors.storage_connector import LocalDiskStorageConnector, StorageAccessError


@pytest.fixture(autouse=True)
def environnement_propre(monkeypatch):
    """Retire toute racine héritée de l'environnement réel."""
    monkeypatch.delenv(LocalDiskStorageConnector.ROOT_VARIABLE, raising=False)


@pytest.fixture
def stockage(tmp_path):
    """Connecteur confiné à un répertoire temporaire."""
    return LocalDiskStorageConnector(root=str(tmp_path / "objets"))


class TestConfiguration:
    """Vérifie ce que le connecteur sait dire sans toucher au disque."""

    def test_non_configure_sans_racine(self):
        """Sans racine déclarée, le connecteur se déclare non configuré."""
        assert LocalDiskStorageConnector().is_configured() is False

    def test_configure_par_l_environnement(self, tmp_path, monkeypatch):
        """La variable d'environnement doit suffire."""
        monkeypatch.setenv(LocalDiskStorageConnector.ROOT_VARIABLE, str(tmp_path))
        assert LocalDiskStorageConnector().is_configured() is True

    def test_racine_explicite_prime(self, tmp_path, monkeypatch):
        """La racine passée à la construction doit primer sur l'environnement."""
        monkeypatch.setenv(LocalDiskStorageConnector.ROOT_VARIABLE, str(tmp_path / "env"))
        explicite = str(tmp_path / "explicite")
        assert LocalDiskStorageConnector(root=explicite).root() == os.path.realpath(explicite)

    def test_check_sans_configuration_n_ecrit_rien(self, tmp_path):
        """Non configuré, la vérification ne doit rien créer sur le disque."""
        avant = set(os.listdir(tmp_path))
        resultat = LocalDiskStorageConnector().check()
        assert resultat.status is ConnectorStatus.NOT_CONFIGURED
        assert set(os.listdir(tmp_path)) == avant

    def test_identite(self, stockage):
        """Le connecteur doit s'annoncer comme un connecteur de stockage."""
        assert stockage.connector_id == "storage_local_disk"
        assert stockage.kind is ConnectorKind.STORAGE


class TestVerification:
    """Vérifie que `check` prouve réellement l'écriture."""

    def test_racine_operationnelle(self, stockage):
        """Une racine créable et inscriptible doit donner READY."""
        resultat = stockage.check()
        assert resultat.status is ConnectorStatus.READY
        assert resultat.is_ready is True

    def test_le_temoin_d_ecriture_est_efface(self, stockage):
        """Le fichier témoin ne doit pas subsister après la vérification."""
        stockage.check()
        assert [f for f in os.listdir(stockage.root()) if f.startswith(".galsen")] == []

    def test_racine_en_lecture_seule(self, tmp_path):
        """Un répertoire refusant l'écriture doit donner UNAUTHORIZED."""
        racine = tmp_path / "lecture_seule"
        racine.mkdir()
        racine.chmod(0o500)
        try:
            resultat = LocalDiskStorageConnector(root=str(racine)).check()
            if os.getuid() == 0:  # pragma: no cover - root ignore les permissions
                pytest.skip("Exécuté en root : les permissions ne s'appliquent pas")
            assert resultat.status is ConnectorStatus.UNAUTHORIZED
        finally:
            racine.chmod(0o700)

    def test_ecriture_refusee(self, stockage):
        """Une écriture refusée doit donner UNAUTHORIZED, pas UNREACHABLE.

        Simulé plutôt que joué avec des permissions réelles : la suite tourne en
        root sur la CI, où `chmod` ne protège rien.
        """
        with patch("builtins.open", side_effect=PermissionError("droits insuffisants")):
            resultat = stockage.check()
        assert resultat.status is ConnectorStatus.UNAUTHORIZED
        assert "droits insuffisants" in resultat.detail

    def test_racine_inutilisable(self, stockage):
        """Une racine hors service doit donner UNREACHABLE."""
        with patch("os.makedirs", side_effect=OSError("disque plein")):
            resultat = stockage.check()
        assert resultat.status is ConnectorStatus.UNREACHABLE
        assert "disque plein" in resultat.detail

    def test_latence_mesuree(self, stockage):
        """La vérification doit rapporter sa durée."""
        assert stockage.check().latency_ms >= 0


class TestConfinement:
    """Vérifie qu'une clé ne peut pas sortir du répertoire de stockage."""

    def test_remontee_refusee(self, stockage):
        """Une clé remontant au-dessus de la racine doit être refusée."""
        with pytest.raises(StorageAccessError, match="sort du répertoire"):
            stockage.put("../evade.txt", b"contenu")

    def test_chemin_absolu_refuse(self, stockage, tmp_path):
        """Une clé absolue hors racine doit être refusée."""
        with pytest.raises(StorageAccessError, match="sort du répertoire"):
            stockage.put(str(tmp_path / "ailleurs.txt"), b"contenu")

    def test_lien_symbolique_refuse(self, stockage, tmp_path):
        """Un lien pointant hors de la racine ne doit pas servir de passage."""
        stockage.check()  # crée la racine
        cible = tmp_path / "dehors.txt"
        cible.write_text("secret", encoding="utf-8")
        lien = os.path.join(stockage.root(), "piege.txt")
        try:
            os.symlink(str(cible), lien)
        except (OSError, NotImplementedError):  # pragma: no cover - dépend du système
            pytest.skip("Les liens symboliques ne sont pas disponibles ici")
        with pytest.raises(StorageAccessError, match="sort du répertoire"):
            stockage.get("piege.txt")

    @pytest.mark.parametrize("cle", ["", "   ", None, 42])
    def test_cle_invalide(self, stockage, cle):
        """Une clé vide ou d'un type inattendu doit être refusée."""
        with pytest.raises(StorageAccessError, match="chaîne non vide"):
            stockage.exists(cle)

    def test_operation_sans_configuration(self):
        """Sans racine, toute opération doit dire quoi renseigner."""
        with pytest.raises(StorageAccessError, match="GALSEN_FILE_STORAGE_DIR"):
            LocalDiskStorageConnector().put("cle", b"contenu")


class TestOperations:
    """Vérifie la lecture, l'écriture et la suppression."""

    def test_put_puis_get(self, stockage):
        """Un objet écrit doit être relu à l'identique."""
        stockage.put("rapport.pdf", b"contenu binaire")
        assert stockage.get("rapport.pdf") == b"contenu binaire"

    def test_put_retourne_la_taille(self, stockage):
        """L'écriture doit rapporter la clé et la taille."""
        resultat = stockage.put("note.txt", b"12345")
        assert resultat == {"key": "note.txt", "size": 5}

    def test_sous_repertoires_crees(self, stockage):
        """Une clé arborescente doit créer les répertoires manquants."""
        stockage.put("rapports/2026/aout.pdf", b"x")
        assert stockage.exists("rapports/2026/aout.pdf") is True

    def test_ecriture_ecrase(self, stockage):
        """Réécrire une clé doit remplacer son contenu."""
        stockage.put("note.txt", b"premier")
        stockage.put("note.txt", b"second")
        assert stockage.get("note.txt") == b"second"

    def test_get_objet_absent(self, stockage):
        """Lire un objet absent doit lever, pas retourner un contenu vide."""
        with pytest.raises(StorageAccessError, match="introuvable"):
            stockage.get("jamais-ecrit.txt")

    def test_exists(self, stockage):
        """exists doit répondre sans lire le contenu."""
        assert stockage.exists("absent.txt") is False
        stockage.put("present.txt", b"x")
        assert stockage.exists("present.txt") is True

    def test_delete(self, stockage):
        """La suppression doit fonctionner et signaler l'absence."""
        stockage.put("temporaire.txt", b"x")
        assert stockage.delete("temporaire.txt") is True
        assert stockage.delete("temporaire.txt") is False

    def test_contenu_non_binaire_refuse(self, stockage):
        """Une chaîne doit être refusée : l'encodage est au choix de l'appelant."""
        with pytest.raises(ValueError, match="octets"):
            stockage.put("note.txt", "du texte")


class TestInventaire:
    """Vérifie l'énumération et la place occupée."""

    def test_list_keys_triee(self, stockage):
        """Les clés doivent être triées et exprimées depuis la racine."""
        stockage.put("b.txt", b"x")
        stockage.put("a.txt", b"x")
        stockage.put("dossier/c.txt", b"x")
        assert stockage.list_keys() == ["a.txt", "b.txt", "dossier/c.txt"]

    def test_list_keys_par_prefixe(self, stockage):
        """Le préfixe doit filtrer l'inventaire."""
        stockage.put("rapports/a.pdf", b"x")
        stockage.put("images/b.png", b"x")
        assert stockage.list_keys(prefix="rapports/") == ["rapports/a.pdf"]

    def test_temoin_de_verification_exclu_de_l_inventaire(self, stockage):
        """Un témoin d'écriture oublié ne doit jamais compter comme un objet."""
        stockage.check()
        with open(os.path.join(stockage.root(), ".galsen-ecriture-999"), "wb") as fichier:
            fichier.write(b"residu")
        stockage.put("vrai.txt", b"x")
        assert stockage.list_keys() == ["vrai.txt"]

    def test_usage(self, stockage):
        """L'usage doit compter les objets et les octets."""
        stockage.put("a.txt", b"12345")
        stockage.put("b.txt", b"123")
        usage = stockage.usage()
        assert usage["objects"] == 2
        assert usage["total_bytes"] == 8

    def test_clear_conserve_la_racine(self, stockage):
        """Vider le stockage ne doit pas supprimer le répertoire lui-même."""
        stockage.put("a.txt", b"x")
        stockage.put("dossier/b.txt", b"x")
        assert stockage.clear() == 2
        assert stockage.list_keys() == []
        assert os.path.isdir(stockage.root())


class TestIntegrationAuRegistre:
    """Vérifie que le connecteur s'inventorie comme les autres."""

    def test_enregistrable_et_verifiable(self, stockage):
        """Le registre doit pouvoir l'inventorier et le vérifier."""
        from src.connectors import ConnectorRegistry

        registre = ConnectorRegistry()
        registre.register(stockage)
        rapport = registre.check_all()
        assert rapport["ready"] == 1
        assert rapport["connectors"][0]["connector_id"] == "storage_local_disk"

    def test_description_sans_secret(self, stockage):
        """La description nomme la variable, jamais un chemin de secret."""
        description = stockage.describe().to_dict()
        assert LocalDiskStorageConnector.ROOT_VARIABLE in description["environment_variables"]
        assert "put" in description["operations"]
