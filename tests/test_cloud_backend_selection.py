"""
Choix du magasin du service Cloud (VOLET 24, chapitre 03 étape 4).

Deux implémentations de `CloudStore` étaient livrées, exportées et testées —
disque et S3 — et **aucune configuration ne pouvait les sélectionner** : le
gestionnaire ne connaissait que la mémoire et SQLite. Un connecteur qu'on ne
peut pas configurer n'est pas une intégration, c'est du code que seuls les
tests maintiennent en vie.
"""

import pytest

from src.services.cloud.manager import CloudManagerImpl
from src.services.cloud.store import InMemoryCloudStore
from src.services.cloud.store_fs import FileSystemCloudStore
from src.services.cloud.store_s3 import S3CloudStore


@pytest.fixture(autouse=True)
def repertoire_isole(tmp_path, monkeypatch):
    """Les magasins sur disque écrivent dans un répertoire jetable."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GALSEN_CLOUD_BACKEND", raising=False)
    monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)


def test_le_defaut_reste_la_memoire(monkeypatch):
    """Changer le défaut ferait écrire sur disque des déploiements qui ne l'ont pas demandé."""
    assert isinstance(CloudManagerImpl()._store, InMemoryCloudStore)


def test_le_magasin_disque_devient_atteignable(monkeypatch):
    """Il existait, était testé, et aucun déploiement ne pouvait le choisir."""
    monkeypatch.setenv("GALSEN_CLOUD_BACKEND", "filesystem")

    assert isinstance(CloudManagerImpl()._store, FileSystemCloudStore)


def test_le_magasin_s3_devient_atteignable(monkeypatch):
    """Idem, et sa construction n'exige pas boto3 — l'import est paresseux."""
    monkeypatch.setenv("GALSEN_CLOUD_BACKEND", "s3")

    assert isinstance(CloudManagerImpl()._store, S3CloudStore)


def test_le_magasin_general_reste_respecte(monkeypatch):
    """Sans choix explicite, `GALSEN_STORAGE_BACKEND=sqlite` continue de valoir."""
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
    from src.storage.sqlite_cloud_store import SQLiteCloudStore

    assert isinstance(CloudManagerImpl()._store, SQLiteCloudStore)


def test_le_choix_du_service_prime_sur_le_general(monkeypatch):
    """`filesystem` et `s3` n'ont de sens que pour ce service."""
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("GALSEN_CLOUD_BACKEND", "filesystem")

    assert isinstance(CloudManagerImpl()._store, FileSystemCloudStore)


def test_une_valeur_inconnue_est_signalee_et_non_devinee(monkeypatch, caplog):
    """
    Deviner « filesystem » à partir de « filesytem » écrirait les fichiers
    ailleurs que là où l'opérateur croit. Le défaut s'applique, et il le dit.
    """
    monkeypatch.setenv("GALSEN_CLOUD_BACKEND", "filesytem")

    with caplog.at_level("ERROR"):
        magasin = CloudManagerImpl()._store

    assert isinstance(magasin, InMemoryCloudStore)
    assert "inconnu" in caplog.text
    assert "filesystem" in caplog.text


def test_un_magasin_injecte_prime_sur_toute_configuration(monkeypatch):
    """Le contrat existant ne change pas : un appelant peut toujours imposer le sien."""
    monkeypatch.setenv("GALSEN_CLOUD_BACKEND", "filesystem")
    impose = InMemoryCloudStore()

    assert CloudManagerImpl(store=impose)._store is impose


def test_le_magasin_disque_persiste_reellement(monkeypatch, tmp_path):
    """Rendre un magasin atteignable sans vérifier qu'il stocke n'aurait servi à rien."""
    monkeypatch.setenv("GALSEN_CLOUD_BACKEND", "filesystem")
    service = CloudManagerImpl()

    resultat = service.upload(name="notes.txt", content_type="text/plain",
                              data=b"bonjour")
    assert resultat.success, resultat.message

    # Un second gestionnaire relit le même répertoire : c'est la persistance
    # que le magasin annonce, et elle n'avait jamais été atteinte en usage réel.
    relu = CloudManagerImpl().get_file(resultat.file_id)
    assert relu is not None
    assert relu.name == "notes.txt"
