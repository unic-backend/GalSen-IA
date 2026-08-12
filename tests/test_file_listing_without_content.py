"""
Lister des fichiers ne charge pas leur contenu (ADR-016).

Le backlog demandait de trancher entre trois façons d'écrire un fichier sur
disque. La mesure a renversé la question : il n'y avait pas trois façons mais
**une conception écrite deux fois**, et la différence entre les deux versions
était un défaut.

`FileItem` porte ses octets, donc `SELECT * FROM files` les lisait tous à chaque
listage — 30 fichiers de 2 Mo faisaient lire 60 Mo pour une réponse qui les jette
(`to_dict(include_data=False)`). Le service `cloud`, lui, séparait déjà les
métadonnées des octets en deux tables.

Ces tests portent sur la règle retenue : **un magasin liste des métadonnées, il
ne lit pas de contenu**, et le type dit ce qu'il contient.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.file.manager import FileManagerImpl  # noqa: E402
from src.services.file.store import InMemoryFileStore  # noqa: E402
from src.services.file.types import FileItem, FileSummary  # noqa: E402
from src.storage.sqlite_file_store import SQLiteFileStore  # noqa: E402


CONTENU = b"x" * (256 * 1024)


@pytest.fixture
def magasin_sqlite(tmp_path):
    """Magasin SQLite isolé."""
    magasin = SQLiteFileStore(str(tmp_path / "files.sqlite"))
    yield magasin
    magasin.close()


def _fichier(nom: str = "rapport.bin", **kwargs) -> FileItem:
    """Construit un fichier avec un contenu non vide."""
    defauts = {
        "name": nom,
        "content_type": "application/octet-stream",
        "size": len(CONTENU),
        "data": CONTENU,
    }
    return FileItem(**{**defauts, **kwargs})


# ----------------------------------------------------------------------
# Le contrat du type
# ----------------------------------------------------------------------

def test_un_listage_rend_des_resumes_pas_des_fichiers(magasin_sqlite):
    """
    Un `FileItem` dont `data` serait vide aurait été plus simple, et faux : un
    `bytes` vide qui veut dire « non chargé » ne se distingue pas d'un `bytes`
    vide qui veut dire « ce fichier est vide ».
    """
    magasin_sqlite.save(_fichier())

    listes = magasin_sqlite.list_files()

    assert isinstance(listes[0], FileSummary)
    assert not hasattr(listes[0], "data")


def test_les_deux_magasins_rendent_le_meme_type(magasin_sqlite):
    """
    En mémoire, ne pas rendre les octets ne fait rien gagner — ils sont déjà là.
    Le contrat doit être le même quand même, sinon le défaut réapparaît le jour
    où l'on change de backend.
    """
    memoire = InMemoryFileStore()
    fichier = _fichier()
    memoire.save(fichier)
    magasin_sqlite.save(fichier)

    assert isinstance(memoire.list_files()[0], FileSummary)
    assert isinstance(magasin_sqlite.list_files()[0], FileSummary)


def test_un_resume_se_serialise_comme_un_fichier_sans_contenu():
    """
    La route rendait `to_dict(include_data=False)`. Ce que reçoit un client HTTP
    ne doit pas changer : c'est ce qui rend ce correctif applicable sur une
    version déjà publiée.
    """
    fichier = _fichier(description="rapport annuel", uploaded_by="awa",
                       tags={"env": "prod"}, metadata={"origine": "test"})

    assert fichier.summary().to_dict() == fichier.to_dict(include_data=False)


# ----------------------------------------------------------------------
# Le contenu reste accessible, et il est le seul à l'être
# ----------------------------------------------------------------------

def test_le_contenu_se_demande_fichier_par_fichier(magasin_sqlite):
    """Le contre-test : la lecture n'a pas été cassée, elle a été déplacée."""
    identifiant = magasin_sqlite.save(_fichier())

    assert magasin_sqlite.get(identifiant).data == CONTENU


def test_les_filtres_de_listage_repondent_comme_avant(magasin_sqlite):
    """Retirer une colonne ne doit pas changer ce que la requête sélectionne."""
    magasin_sqlite.save(_fichier("a.png", content_type="image/png",
                                 uploaded_by="awa", tags={"env": "prod"}))
    magasin_sqlite.save(_fichier("b.bin", uploaded_by="moussa"))
    magasin_sqlite.save(_fichier("c.bin", uploaded_by="awa"))

    assert len(magasin_sqlite.list_files()) == 3
    assert len(magasin_sqlite.list_files(content_type="image/png")) == 1
    assert len(magasin_sqlite.list_files(uploaded_by="awa")) == 2
    assert len(magasin_sqlite.list_files(tags={"env": "prod"})) == 1
    assert len(magasin_sqlite.list_files(limit=2)) == 2


# ----------------------------------------------------------------------
# La mesure
# ----------------------------------------------------------------------

def test_lister_ne_lit_pas_les_octets(tmp_path):
    """
    Le fait qui justifie ADR-016, épinglé.

    Sans seuil arbitraire : la mémoire mobilisée par un listage est comparée au
    volume stocké. Avant le correctif elle l'égalait ; un dixième laisse toute
    la marge nécessaire à un environnement plus lent tout en échouant si les
    octets reviennent.
    """
    import tracemalloc

    magasin = SQLiteFileStore(str(tmp_path / "files.sqlite"))
    try:
        for index in range(20):
            magasin.save(_fichier(f"f{index}.bin"))
        stocke = 20 * len(CONTENU)

        tracemalloc.start()
        resumes = magasin.list_files(limit=100)
        _, pic = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert len(resumes) == 20
        assert pic < stocke / 10, (
            f"{pic} octets mobilisés pour lister {stocke} octets stockés : "
            "le contenu est de nouveau chargé"
        )
    finally:
        magasin.close()


def test_le_service_complet_ne_charge_pas_davantage(tmp_path, monkeypatch):
    """La même propriété par le gestionnaire, qui est ce que la route appelle."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
    gestionnaire = FileManagerImpl()
    gestionnaire.upload_file(name="rapport.bin", content_type="application/octet-stream",
                             data=CONTENU)

    listes = gestionnaire.list_files()

    assert len(listes) == 1
    assert isinstance(listes[0], FileSummary)
    # Et la route sérialise sans avoir à demander l'exclusion du contenu.
    assert "data" not in listes[0].to_dict()
