"""
Le service cloud est un adaptateur, il ne stocke plus rien (ADR-016, étape 3).

Dernière étape : `CloudFileItem` n'est plus un type stocké et les quatre
magasins cloud — mémoire, SQLite, disque, S3 — sont supprimés. Les routes
`/cloud/*`, dépréciées, sont servies par le service de fichiers.

Ce fichier remplace `test_cloud_backend_selection.py` et `test_services_cloud_fs.py`,
dont le sujet a disparu ; la couverture du contrat de magasin (persistance,
filtres, pagination, suppression des octets, absence de boto3) vit maintenant
dans `test_file_backends.py`, qui porte sur le magasin réellement utilisé.

Le fait qui justifie de retirer `CloudFileItem` est mesuré ici : son champ
`provider` était **une déclaration de l'appelant**, jamais vérifiée.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.cloud.manager import ANCIENNE_VARIABLE, CloudManagerImpl  # noqa: E402
from src.services.cloud.types import CloudProvider  # noqa: E402
from src.services.file.manager import FileManagerImpl  # noqa: E402


@pytest.fixture
def cloud(tmp_path, monkeypatch):
    """Service cloud servi par un service de fichiers en mémoire."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GALSEN_FILE_BACKEND", raising=False)
    monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv(ANCIENNE_VARIABLE, raising=False)
    return CloudManagerImpl()


# ----------------------------------------------------------------------
# `provider` cesse d'enregistrer une croyance
# ----------------------------------------------------------------------

def test_le_fournisseur_demande_par_l_appelant_est_ignore(cloud):
    """
    Le fait qui justifie cette étape. Avant : téléverser avec `provider="s3"`
    sur une plateforme en mémoire enregistrait `s3`, et `/cloud/stats` rapportait
    `by_provider: {"s3": 1}` pour un fichier qui vivait en RAM.

    Le magasin qui détient les octets est décidé par la configuration, pas par
    l'appelant. Enregistrer sa demande revenait à enregistrer une croyance.
    """
    resultat = cloud.upload(name="rapport.pdf", content_type="application/pdf",
                            data=b"x" * 10, provider=CloudProvider.S3)

    assert cloud.get_file(resultat.file_id).provider is CloudProvider.LOCAL


def test_le_fournisseur_annonce_suit_le_magasin_reel(tmp_path, monkeypatch):
    """Le contre-test : sur un magasin S3, la réponse dit bien `s3`."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_FILE_BACKEND", "s3")

    assert CloudManagerImpl().provider is CloudProvider.S3


def test_les_statistiques_ne_comptent_plus_des_declarations(cloud):
    """`by_provider` comptait ce que les appelants avaient cru."""
    cloud.upload(name="a.pdf", content_type="application/pdf", data=b"x",
                 provider=CloudProvider.S3)
    cloud.upload(name="b.png", content_type="image/png", data=b"y",
                 provider=CloudProvider.AZURE)

    etat = cloud.stats()

    assert etat["total"] == 2
    assert etat["by_provider"] == {"local": 2}
    assert etat["by_category"] == {"document": 1, "image": 1}


def test_un_etat_vide_n_annonce_aucun_fournisseur(cloud):
    """Annoncer `{"local": 0}` laisserait croire à un magasin qui a servi."""
    assert cloud.stats()["by_provider"] == {}


# ----------------------------------------------------------------------
# Le service ne stocke plus : les deux façades voient les mêmes fichiers
# ----------------------------------------------------------------------

def test_un_fichier_depose_par_cloud_se_lit_par_le_service_de_fichiers(tmp_path, monkeypatch):
    """
    C'est la fin de la duplication : deux services, un seul stockage. Avant,
    un fichier déposé sur `/cloud/*` était invisible de `/file/*`.
    """
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_FILE_BACKEND", "filesystem")
    fichiers = FileManagerImpl()
    cloud = CloudManagerImpl(files=fichiers)

    resultat = cloud.upload(name="note.txt", content_type="text/plain", data=b"bonjour")

    assert fichiers.get_file(resultat.file_id).data == b"bonjour"
    assert cloud.download(resultat.file_id) == b"bonjour"


def test_les_operations_de_base_repondent_comme_avant(cloud):
    """Les routes dépréciées gardent leur comportement : elles sont annoncées, pas modifiées."""
    identifiant = cloud.upload(name="a.pdf", content_type="application/pdf",
                               data=b"contenu").file_id

    assert cloud.get_file(identifiant).name == "a.pdf"
    assert cloud.download(identifiant) == b"contenu"
    assert cloud.update_metadata(identifiant, {"revu": True}) is True
    assert cloud.get_file(identifiant).metadata["revu"] is True
    assert [e.name for e in cloud.list_files()] == ["a.pdf"]
    assert cloud.delete(identifiant) is True
    assert cloud.get_file(identifiant) is None


def test_un_fichier_absent_ne_se_telecharge_pas(cloud):
    """Rendre des octets vides serait rendre un mensonge plausible."""
    assert cloud.download("cloud_inexistant") is None
    assert cloud.delete("cloud_inexistant") is False
    assert cloud.update_metadata("cloud_inexistant", {"x": 1}) is False


@pytest.mark.parametrize("nom,type_mime,taille,attendu", [
    ("", "text/plain", 10, "nom"),
    ("a.txt", "text/plain", 0, "vide"),
])
def test_les_refus_de_televersement_restent(cloud, nom, type_mime, taille, attendu):
    """La validation ne doit pas s'être perdue dans la délégation."""
    resultat = cloud.upload(name=nom, content_type=type_mime, data=b"x" * taille)

    assert resultat.success is False
    assert attendu in resultat.message.lower()


def test_un_fichier_trop_gros_est_refuse(cloud):
    """La limite de taille est portée par le service de fichiers, et s'applique."""
    resultat = cloud.upload(name="gros.bin", content_type="application/octet-stream",
                            data=b"x" * 100, max_size=10)

    assert resultat.success is False


def test_le_filtre_par_fournisseur_ne_rend_rien_pour_un_autre_magasin(cloud):
    """
    Tous les fichiers sont dans le magasin actif : le filtre y répond tout ou
    rien, au lieu de trier des déclarations.
    """
    cloud.upload(name="a.pdf", content_type="application/pdf", data=b"x")

    assert len(cloud.list_files(provider="local")) == 1
    assert cloud.list_files(provider="s3") == []


def test_vider_le_service_vide_le_stockage_partage(cloud):
    """Un seul stockage : le vider par une façade le vide pour l'autre."""
    cloud.upload(name="a.pdf", content_type="application/pdf", data=b"x")

    assert cloud.clear() == 1
    assert cloud.stats()["total"] == 0


# ----------------------------------------------------------------------
# L'ancienne variable ne disparaît pas en silence
# ----------------------------------------------------------------------

def test_l_ancienne_variable_de_magasin_est_signalee(tmp_path, monkeypatch, caplog):
    """
    L'ignorer en silence serait le défaut que ce dépôt traque partout ailleurs :
    un opérateur ayant écrit `filesystem` là croirait ses fichiers sur disque
    alors qu'ils seraient en mémoire.
    """
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv(ANCIENNE_VARIABLE, "filesystem")
    monkeypatch.delenv("GALSEN_FILE_BACKEND", raising=False)

    with caplog.at_level("ERROR"):
        CloudManagerImpl()

    assert ANCIENNE_VARIABLE in caplog.text
    assert "GALSEN_FILE_BACKEND" in caplog.text


def test_les_magasins_cloud_n_existent_plus():
    """
    Les quatre magasins supprimés ne doivent pas revenir par un import oublié :
    c'est la moitié dupliquée qu'ADR-016 retire.
    """
    import importlib

    for module in ("src.services.cloud.store", "src.services.cloud.store_fs",
                   "src.services.cloud.store_s3", "src.storage.sqlite_cloud_store"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module)


# ----------------------------------------------------------------------
# Une route dépréciée n'est pas une porte dérobée (ADR-010)
# ----------------------------------------------------------------------

@pytest.fixture
def deux_sujets(tmp_path, monkeypatch):
    """Deux porteurs de clé distincts, sur une API partageant un seul stockage."""
    from fastapi.testclient import TestClient

    import src.api.server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GALSEN_FILE_BACKEND", raising=False)
    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:user:awa,cle-moussa:user:moussa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    # Le service de fichiers de l'API est construit à l'import : sans ce vidage,
    # les fichiers d'un test précédent seraient comptés par le suivant.
    server_module.file_manager.clear()
    yield TestClient(server_module.app), {"X-API-Key": "cle-awa"}, {"X-API-Key": "cle-moussa"}
    server_module.file_manager.clear()
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def _deposer(client, entetes, nom="prive.txt", contenu=b"secret"):
    """Dépose un fichier par `/file/upload` et retourne son identifiant."""
    import base64

    reponse = client.post("/file/upload", headers=entetes, json={
        "name": nom, "content_type": "text/plain",
        "data": base64.b64encode(contenu).decode(),
    })
    assert reponse.status_code == 200, reponse.text
    return reponse.json()["file_id"]


def test_les_routes_depreciees_ne_montrent_pas_les_fichiers_d_autrui(deux_sujets):
    """
    Le défaut le plus grave de cette étape, mesuré avant correction : les routes
    `/cloud/*` n'appliquaient aucune règle de propriété. Tant qu'elles avaient
    leur propre magasin, la fuite se limitait à leurs fichiers ; en partageant
    le stockage du service de fichiers, elles **contournaient le contrôle de la
    route qui les remplace**.
    """
    client, awa, moussa = deux_sujets
    identifiant = _deposer(client, awa)

    assert client.post("/file/list", headers=moussa, json={}).json()["total"] == 0
    assert client.post("/cloud/list", headers=moussa, json={}).json()["total"] == 0
    assert client.get(f"/cloud/{identifiant}", headers=moussa).status_code == 404


def test_le_telechargement_deprecie_ne_rend_pas_les_octets_d_autrui(deux_sujets):
    """C'est la route qui rend le **contenu**, pas seulement les métadonnées."""
    client, awa, moussa = deux_sujets
    identifiant = _deposer(client, awa, contenu=b"secret d'awa")

    assert client.get(f"/cloud/{identifiant}/download", headers=moussa).status_code == 404
    assert client.get(f"/cloud/{identifiant}/download", headers=awa).content == b"secret d'awa"


def test_une_suppression_ne_touche_pas_le_fichier_d_autrui(deux_sujets):
    """
    La permission dit qu'un sujet peut supprimer **ses** fichiers. `DELETE
    /file/{id}` ne vérifiait pas la propriété non plus : deux sujets d'un même
    rôle pouvaient se supprimer mutuellement leurs fichiers.
    """
    client, awa, moussa = deux_sujets
    identifiant = _deposer(client, awa)

    for chemin in (f"/file/{identifiant}", f"/cloud/{identifiant}"):
        assert client.delete(chemin, headers=moussa).status_code in (403, 404)

    # Le fichier est toujours là pour son propriétaire.
    assert client.get(f"/file/{identifiant}", headers=awa).status_code == 200


def test_le_proprietaire_garde_l_acces_par_les_deux_facades(deux_sujets):
    """Le contre-test : fermer la fuite ne doit pas fermer l'usage légitime."""
    client, awa, _ = deux_sujets
    identifiant = _deposer(client, awa)

    assert client.get(f"/file/{identifiant}", headers=awa).status_code == 200
    assert client.get(f"/cloud/{identifiant}", headers=awa).status_code == 200
    assert client.post("/cloud/list", headers=awa, json={}).json()["total"] == 1


def test_un_depot_par_la_route_depreciee_appartient_a_son_auteur(deux_sujets):
    """
    `/cloud/upload` n'attribuait le fichier à personne : il aurait déposé des
    fichiers sans propriétaire au milieu de ceux des autres.
    """
    import base64

    client, awa, moussa = deux_sujets
    identifiant = client.post("/cloud/upload", headers=awa, json={
        "name": "note.txt", "content_type": "text/plain",
        "data": base64.b64encode(b"a moi").decode(),
    }).json()["file_id"]

    assert client.get(f"/file/{identifiant}", headers=awa).status_code == 200
    assert client.get(f"/file/{identifiant}", headers=moussa).status_code == 404


def test_les_deux_facades_partagent_le_meme_service(deux_sujets):
    """
    Deux `FileManagerImpl` sur un même répertoire tiendraient chacun son index
    en mémoire : un fichier déposé par une façade resterait invisible de
    l'autre. Mesuré avant que le registre partage l'instance.
    """
    import src.api.server as server_module

    assert server_module.cloud_manager._files is server_module.file_manager
