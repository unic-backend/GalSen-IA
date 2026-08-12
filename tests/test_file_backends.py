"""
Les backends `filesystem` et `s3` sous le service de fichiers (ADR-016, étape 1).

ADR-016 a décidé qu'un appelant utilise le **service de fichiers**. Cette étape
lui donne ce que seul le service `cloud` savait faire : écrire sur le disque, et
écrire sur S3.

Le port n'est pas une recopie. Les deux magasins d'origine partageaient une
structure — un index JSON de métadonnées, un dépôt d'octets à côté — et ne
différaient que par le second ; les porter en deux classes complètes aurait
écrit une troisième et une quatrième fois la logique d'index, exactement ce
qu'ADR-016 reproche à l'existant. `IndexedFileStore` la tient une fois.

Trois défauts de l'implémentation d'origine sont corrigés, et chacun a son test
ici : un index tronqué faisait disparaître tous les fichiers en silence, l'index
était réécrit en place (donc produisait ce fichier tronqué), et un identifiant
servait de nom de fichier sans contrôle.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.file.manager import FileManagerImpl  # noqa: E402
from src.services.file.store_fs import FileSystemFileStore  # noqa: E402
from src.services.file.store_indexed import IndexCorrompu, IndexedFileStore  # noqa: E402
from src.services.file.types import FileItem, FileSummary  # noqa: E402


@pytest.fixture
def magasin(tmp_path):
    """Magasin sur disque, dans un répertoire isolé."""
    return FileSystemFileStore(str(tmp_path / "files"))


def _fichier(nom: str = "rapport.pdf", contenu: bytes = b"hello", **kwargs) -> FileItem:
    """Construit un fichier."""
    defauts = {
        "name": nom,
        "content_type": "application/pdf",
        "size": len(contenu),
        "data": contenu,
    }
    return FileItem(**{**defauts, **kwargs})


class FauxSeau(IndexedFileStore):
    """
    Dépôt d'octets en mémoire, pour éprouver la base sans réseau.

    C'est ce que S3 fournit : trois opérations. Le tester ainsi vérifie la
    logique partagée sans prétendre avoir joint un seau — ce que le test ne
    ferait pas et n'a pas à faire croire.
    """

    def __init__(self, data_dir: str) -> None:
        self.blobs = {}
        self.supprimes = []
        super().__init__(data_dir)

    def _write_blob(self, file_id, data, content_type):
        self.blobs[file_id] = data

    def _read_blob(self, file_id):
        return self.blobs.get(file_id)

    def _delete_blob(self, file_id):
        self.supprimes.append(file_id)
        self.blobs.pop(file_id, None)


# ----------------------------------------------------------------------
# Le contrat, identique aux autres magasins de fichiers
# ----------------------------------------------------------------------

def test_un_fichier_survit_a_un_redemarrage(tmp_path):
    """C'est la raison d'être d'un backend sur disque."""
    chemin = str(tmp_path / "files")
    identifiant = FileSystemFileStore(chemin).save(_fichier(contenu=b"des octets"))

    rouvert = FileSystemFileStore(chemin)

    assert rouvert.count() == 1
    assert rouvert.get(identifiant).data == b"des octets"


def test_un_listage_rend_des_resumes_sans_contenu(magasin):
    """Le même contrat que les magasins mémoire et SQLite (ADR-016)."""
    magasin.save(_fichier())

    listes = magasin.list_files()

    assert isinstance(listes[0], FileSummary)
    assert not hasattr(listes[0], "data")


def test_les_filtres_repondent_comme_les_autres_magasins(magasin):
    """Deux magasins d'un même contrat qui filtrent différemment divergeraient."""
    magasin.save(_fichier("a.png", content_type="image/png", uploaded_by="awa",
                          tags={"env": "prod"}))
    magasin.save(_fichier("b.pdf", uploaded_by="moussa"))
    magasin.save(_fichier("c.pdf", uploaded_by="awa"))

    assert len(magasin.list_files()) == 3
    assert len(magasin.list_files(content_type="image/png")) == 1
    assert len(magasin.list_files(uploaded_by="awa")) == 2
    assert len(magasin.list_files(tags={"env": "prod"})) == 1
    assert len(magasin.list_files(limit=2)) == 2


def test_le_plus_recent_vient_en_premier(magasin):
    """L'ordre des autres magasins."""
    magasin.save(_fichier("vieux.pdf"))
    magasin.save(_fichier("recent.pdf"))

    assert [r.name for r in magasin.list_files()] == ["recent.pdf", "vieux.pdf"]


def test_supprimer_retire_aussi_les_octets(magasin, tmp_path):
    """Une suppression qui laisse les octets n'est pas une suppression."""
    identifiant = magasin.save(_fichier())
    blobs = os.path.join(str(tmp_path / "files"), "blobs")
    assert os.listdir(blobs) == [identifiant]

    assert magasin.delete(identifiant) is True

    assert os.listdir(blobs) == []
    assert magasin.get(identifiant) is None


def test_vider_supprime_les_octets_de_tous_les_fichiers(tmp_path):
    """
    Le magasin S3 d'origine ne vidait que son index local : il rapportait N
    fichiers supprimés pendant que N objets restaient dans le seau, facturés et
    lisibles. « Supprimé » doit vouloir dire supprimé.
    """
    faux = FauxSeau(str(tmp_path / "s3"))
    faux.save(_fichier("a.pdf"))
    faux.save(_fichier("b.pdf"))

    assert faux.clear() == 2

    assert faux.blobs == {}
    assert len(faux.supprimes) == 2


# ----------------------------------------------------------------------
# Les trois défauts corrigés
# ----------------------------------------------------------------------

def test_un_index_illisible_arrete_l_ouverture(magasin, tmp_path):
    """
    Le défaut le plus coûteux, mesuré sur `FileSystemCloudStore` : un index
    tronqué faisait rapporter « 0 fichier » alors que les octets étaient
    toujours là. Un appelant les aurait re-téléversés, et la réparation serait
    devenue impossible.
    """
    magasin.save(_fichier())
    index = tmp_path / "files" / "index.json"
    index.write_text('{"order": ["x"], "items": [{"name": "rap', encoding="utf-8")

    with pytest.raises(IndexCorrompu):
        FileSystemFileStore(str(tmp_path / "files"))

    # L'index fautif est conservé : c'est la seule trace de ce qui a été stocké.
    assert index.exists()


def test_l_index_est_ecrit_de_facon_atomique(magasin, tmp_path):
    """
    L'écriture en place laissait une fenêtre — coupure, disque plein — où
    l'index était tronqué, c'est-à-dire le défaut précédent. Écrire à côté puis
    renommer supprime la fenêtre.
    """
    magasin.save(_fichier())
    repertoire = tmp_path / "files"

    # Aucun fichier temporaire ne subsiste, et l'index relu est complet.
    assert not any(f.name.endswith(".tmp") for f in repertoire.iterdir())
    contenu = json.loads((repertoire / "index.json").read_text(encoding="utf-8"))
    assert len(contenu["items"]) == 1 and len(contenu["order"]) == 1


def test_les_octets_sont_ecrits_de_facon_atomique(magasin, tmp_path):
    """Un fichier écrit à moitié serait rendu tel quel par `get`."""
    magasin.save(_fichier(contenu=b"contenu complet"))
    blobs = tmp_path / "files" / "blobs"

    assert not any(f.name.endswith(".tmp") for f in blobs.iterdir())


@pytest.mark.parametrize("identifiant", ["../evade", "a/b", "", "x" * 200])
def test_un_identifiant_ne_peut_pas_sortir_du_repertoire(magasin, identifiant):
    """Un identifiant sert de nom de fichier et de clé d'objet."""
    with pytest.raises(ValueError):
        magasin.save(_fichier(id=identifiant))


def test_un_fichier_dont_les_octets_ont_disparu_ne_rend_pas_du_vide(magasin, tmp_path):
    """
    L'index est local et le dépôt est ailleurs : ils peuvent diverger. Rendre un
    fichier de zéro octet serait rendre un mensonge plausible.
    """
    identifiant = magasin.save(_fichier())
    os.remove(os.path.join(str(tmp_path / "files"), "blobs", identifiant))

    assert magasin.get(identifiant) is None


def test_les_octets_sont_ecrits_avant_l_index(magasin, monkeypatch):
    """
    L'ordre inverse laisserait une entrée d'index pointant vers rien — un
    fichier que la plateforme listerait et ne pourrait pas rendre.
    """
    def echec(*args, **kwargs):
        raise IOError("disque plein")

    monkeypatch.setattr(magasin, "_write_blob", echec)

    with pytest.raises(IOError):
        magasin.save(_fichier())

    assert magasin.count() == 0
    assert magasin.list_files() == []


# ----------------------------------------------------------------------
# La sélection par configuration
# ----------------------------------------------------------------------

@pytest.mark.parametrize("declare,attendu", [
    ("filesystem", "FileSystemFileStore"),
    ("sqlite", "SQLiteFileStore"),
    ("in-memory", "InMemoryFileStore"),
])
def test_le_backend_se_choisit_par_configuration(tmp_path, monkeypatch, declare, attendu):
    """`GALSEN_FILE_BACKEND` prime sur le magasin général, comme pour le cloud."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_FILE_BACKEND", declare)

    assert type(FileManagerImpl()._store).__name__ == attendu


def test_une_valeur_inconnue_n_est_pas_devinee(tmp_path, monkeypatch, caplog):
    """
    Deviner « filesytem » ferait écrire les fichiers ailleurs que là où
    l'opérateur croit — et il ne le verrait qu'en les cherchant.
    """
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_FILE_BACKEND", "filesytem")
    monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)

    with caplog.at_level("ERROR"):
        gestionnaire = FileManagerImpl()

    assert type(gestionnaire._store).__name__ == "InMemoryFileStore"
    assert "filesytem" in caplog.text


def test_sans_variable_dediee_le_magasin_general_s_applique(tmp_path, monkeypatch):
    """Le contre-test : la nouvelle variable n'annule pas ADR-005."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GALSEN_FILE_BACKEND", raising=False)
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")

    assert type(FileManagerImpl()._store).__name__ == "SQLiteFileStore"


def test_le_service_complet_ecrit_et_relit_sur_disque(tmp_path, monkeypatch):
    """Bout en bout, par le gestionnaire — ce que la route appelle."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_FILE_BACKEND", "filesystem")
    gestionnaire = FileManagerImpl()

    resultat = gestionnaire.upload_file(name="note.txt", content_type="text/plain",
                                        data=b"bonjour", uploaded_by="awa")

    assert resultat.success is True
    relu = FileManagerImpl().get_file(resultat.file_id)
    assert relu.data == b"bonjour"


def test_le_meme_identifiant_ne_s_ecrase_pas(magasin):
    """Écraser en silence perdrait le fichier d'origine sans le dire."""
    fichier = _fichier()
    magasin.save(fichier)

    with pytest.raises(ValueError, match="existe déjà"):
        magasin.save(fichier)


def test_la_pagination_est_appliquee(magasin):
    """`offset` et `limit` doivent découper la liste, pas seulement la tronquer."""
    for index in range(5):
        magasin.save(_fichier(f"f{index}.pdf"))

    page = magasin.list_files(limit=2, offset=1)

    # Du plus récent au plus ancien : f4, f3, f2, f1, f0 → offset 1, limite 2.
    assert [r.name for r in page] == ["f3.pdf", "f2.pdf"]


def test_le_magasin_s3_se_construit_sans_boto3(tmp_path, monkeypatch):
    """
    Sa construction ne doit pas exiger `boto3` : la plateforme démarre sans, et
    un magasin qui refuserait d'exister empêcherait de lire la configuration.
    """
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_FILE_BACKEND", "s3")

    assert type(FileManagerImpl()._store).__name__ == "S3FileStore"


def test_un_envoi_s3_sans_boto3_echoue_franchement(tmp_path, monkeypatch):
    """
    Un fichier « déposé » alors que rien ne l'a reçu serait pire que l'échec.
    L'import paresseux doit donc lever à l'écriture, pas retomber en silence.
    """
    from src.services.file.store_s3 import S3FileStore

    magasin = S3FileStore(bucket="seau-de-test", data_directory=str(tmp_path / "s3"))
    monkeypatch.setattr(magasin, "_client", lambda: (_ for _ in ()).throw(
        ImportError("No module named 'boto3'")))

    with pytest.raises(IOError, match="seau-de-test"):
        magasin.save(_fichier())

    assert magasin.count() == 0
