"""
Persistance en conditions de déploiement (chantier 1 de l'audit).

Deux tests par magasin vérifiaient déjà qu'une base rouverte relit ses données.
Aucun ne prouvait ce que le chantier demande : que **l'application** redémarrée
retrouve son état, que la sauvegarde soit sûre pendant que l'application écrit,
et que les fichiers ne soient pas lisibles par tout le monde.
"""

import os
import sqlite3
import stat
import threading
import time
from pathlib import Path

import pytest

from scripts.backup import VERROU, lister, restaurer, sauvegarder
from src.api import instance_lock
from src.storage.paths import declared_backend, prepare_connection, storage_backend


@pytest.fixture
def deploiement(tmp_path, monkeypatch):
    """Un déploiement isolé : répertoire de données, sauvegardes, backend sqlite."""
    donnees = tmp_path / "data"
    donnees.mkdir()
    monkeypatch.setenv("GALSEN_DATA_DIR", str(donnees))
    monkeypatch.setenv("GALSEN_BACKUP_DIR", str(tmp_path / "sauvegardes"))
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
    return donnees


def _ecrire_memoire(contenu: str) -> str:
    """Écrit une mémoire par un gestionnaire neuf et retourne son identifiant."""
    from src.memory_engine.memory_manager import MemoryManager
    from src.memory_engine.types import MemoryItem, MemoryType

    return MemoryManager().save_memory(MemoryItem(
        content=contenu, memory_type=MemoryType.KNOWLEDGE, user_id="awa",
    ))


# ----------------------------------------------------------------------
# TEST 1 — les données survivent à un redémarrage
# ----------------------------------------------------------------------

def test_une_memoire_survit_a_un_redemarrage(deploiement):
    """
    Le gestionnaire est **détruit puis reconstruit**, comme au redémarrage du
    processus. Rouvrir un magasin ne prouvait que le magasin ; c'est le chemin
    complet — configuration comprise — qui compte ici.
    """
    from src.memory_engine.memory_manager import MemoryManager

    identifiant = _ecrire_memoire("La pluviométrie du Sénégal varie.")

    apres_redemarrage = MemoryManager()
    relu = apres_redemarrage.get_memory(identifiant)

    assert relu is not None
    assert relu.content == "La pluviométrie du Sénégal varie."


def test_une_connaissance_survit_a_un_redemarrage(deploiement):
    """Le même contrat, sur un second moteur : la persistance n'est pas locale à un."""
    from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
    from src.knowledge_engine.types import KnowledgeDomain, KnowledgeItem

    identifiant = KnowledgeManagerImpl().add_knowledge(KnowledgeItem(
        content="Le mil se sème en juin.", domain=KnowledgeDomain.OPERATIONAL))

    assert KnowledgeManagerImpl().get_knowledge(identifiant) is not None


def test_sans_sqlite_rien_ne_survit_et_c_est_le_defaut(tmp_path, monkeypatch):
    """
    Le contre-test, et le piège de déploiement n°1 : le défaut du code est
    `in-memory`. Un `docker run` sans configuration perd tout au redémarrage.
    """
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)

    from src.memory_engine.memory_manager import MemoryManager

    identifiant = _ecrire_memoire("volatile")

    assert storage_backend() == "in-memory"
    assert MemoryManager().get_memory(identifiant) is None


# ----------------------------------------------------------------------
# Point de décision unique
# ----------------------------------------------------------------------

def test_le_choix_du_magasin_n_est_decide_qu_a_un_seul_endroit():
    """
    Le test `os.getenv("GALSEN_STORAGE_BACKEND", ...) == "sqlite"` était réécrit
    dans huit gestionnaires. Huit copies d'une règle finissent par diverger, et
    ce dépôt a déjà payé quatre fois ce mode de défaillance.
    """
    racine = Path(__file__).resolve().parent.parent
    lecteurs = [
        chemin.relative_to(racine).as_posix()
        for chemin in (racine / "src").rglob("*.py")
        if 'getenv("GALSEN_STORAGE_BACKEND"' in chemin.read_text(encoding="utf-8")
    ]

    assert lecteurs == ["src/storage/paths.py"], (
        "Le magasin doit être décidé dans src/storage/paths.py seulement — " + ", ".join(lecteurs)
    )


def test_une_valeur_inconnue_ne_persiste_pas_par_accident(monkeypatch):
    """
    Deviner « sqllite » ferait persister des données là où l'opérateur croit
    avoir un magasin volatile. Le défaut s'applique, et `/health` le signale.
    """
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "postgresql")

    assert storage_backend() == "in-memory"
    assert declared_backend() == "postgresql"


def test_le_magasin_de_memoire_suit_le_repertoire_de_donnees(tmp_path, monkeypatch):
    """
    Il était le seul des huit à coder son chemin en dur : déplacer le répertoire
    de données déplaçait sept bases et laissait celle des mémoires derrière.
    """
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path / "ailleurs"))
    from src.storage.sqlite_store import SQLiteMemoryStore

    assert str(tmp_path / "ailleurs") in SQLiteMemoryStore().db_path


# ----------------------------------------------------------------------
# WAL et permissions
# ----------------------------------------------------------------------

def test_les_bases_tournent_en_wal(deploiement):
    """
    Le mode par défaut (`DELETE`) fait que lecteurs et écrivain se bloquent, et
    rend une sauvegarde à chaud impossible. WAL supprime les deux.
    """
    _ecrire_memoire("peu importe")
    base = deploiement / "memory.sqlite"

    with sqlite3.connect(base) as connexion:
        assert connexion.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_une_base_n_est_lisible_que_par_son_proprietaire(deploiement):
    """Une base porte des mémoires et des e-mails ; elle était créée en 0644."""
    _ecrire_memoire("peu importe")
    base = deploiement / "memory.sqlite"

    assert stat.S_IMODE(os.stat(base).st_mode) == 0o600


def test_les_pragma_sont_poses_par_une_seule_fonction():
    """Ils étaient recopiés dans les huit magasins."""
    racine = Path(__file__).resolve().parent.parent / "src" / "storage"
    fautifs = [
        chemin.name for chemin in racine.glob("sqlite_*.py")
        if 'PRAGMA foreign_keys' in chemin.read_text(encoding="utf-8")
    ]

    assert fautifs == [], "PRAGMA recopiés au lieu d'appeler prepare_connection : " + ", ".join(fautifs)


def test_prepare_connection_pose_bien_les_quatre_pragma(tmp_path):
    """Centraliser ne vaut que si le contenu est juste."""
    with sqlite3.connect(tmp_path / "t.sqlite") as connexion:
        prepare_connection(connexion)

        assert connexion.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connexion.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
        assert connexion.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connexion.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


# ----------------------------------------------------------------------
# Sauvegarde et restauration
# ----------------------------------------------------------------------

def test_une_sauvegarde_prise_pendant_des_ecritures_est_valide(deploiement):
    """
    C'est tout l'objet de `VACUUM INTO`. La procédure documentée jusqu'ici —
    `cp -r` du volume — peut produire une base corrompue : l'écriture en cours
    n'est pas atomique pour le copieur, et depuis WAL les écritures récentes
    vivent dans un fichier `-wal` que la copie laisserait derrière.
    """
    from src.memory_engine.memory_manager import MemoryManager
    from src.memory_engine.types import MemoryItem, MemoryType

    gestionnaire = MemoryManager()
    arret = threading.Event()

    def ecrire_sans_arret():
        compteur = 0
        while not arret.is_set():
            gestionnaire.save_memory(MemoryItem(
                content=f"pendant {compteur}", memory_type=MemoryType.KNOWLEDGE, user_id="awa"))
            compteur += 1

    fil = threading.Thread(target=ecrire_sans_arret)
    fil.start()
    time.sleep(0.1)
    try:
        cible, copiees = sauvegarder()
    finally:
        arret.set()
        fil.join()

    assert "memory.sqlite" in copiees
    with sqlite3.connect(cible / "memory.sqlite") as connexion:
        assert connexion.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connexion.execute("SELECT COUNT(*) FROM memories").fetchone()[0] > 0


def test_une_sauvegarde_est_lisible_par_son_seul_proprietaire(deploiement):
    """Une sauvegarde contient ce que contient la base : mêmes permissions."""
    _ecrire_memoire("à sauvegarder")
    cible, _ = sauvegarder()

    assert stat.S_IMODE(os.stat(cible).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(cible / "memory.sqlite").st_mode) == 0o600


def test_la_restauration_remet_l_etat_sauvegarde(deploiement):
    """L'aller-retour complet, qui est ce qu'un retour arrière exécute."""
    from src.memory_engine.memory_manager import MemoryManager

    identifiant = _ecrire_memoire("état d'origine")
    cible, _ = sauvegarder()

    # La base évolue après la sauvegarde.
    perdu = _ecrire_memoire("écrit après la sauvegarde")
    assert MemoryManager().get_memory(perdu) is not None

    restaurer(cible.name)

    apres = MemoryManager()
    assert apres.get_memory(identifiant) is not None
    assert apres.get_memory(perdu) is None, "la restauration n'a pas remplacé la base"


def test_la_restauration_refuse_de_marcher_sur_une_instance_vivante(deploiement):
    """
    Écraser une base ouverte perd ce qu'on voulait sauver.

    L'instance vivante est simulée en **prenant réellement le verrou** : depuis
    le chantier 3, `instance_en_cours()` interroge le verrou et non la présence
    du fichier, pour qu'un fichier laissé par un arrêt brutal ne bloque pas la
    manœuvre qui répare l'incident.
    """
    _ecrire_memoire("état")
    cible, _ = sauvegarder()

    instance_lock.release()
    instance_lock.acquire()
    try:
        assert (deploiement / VERROU).exists()
        with pytest.raises(RuntimeError, match="instance"):
            restaurer(cible.name)
    finally:
        instance_lock.release()


def test_un_verrou_orphelin_ne_bloque_pas_la_restauration(deploiement):
    """
    Le contre-test : un fichier verrou sans instance derrière doit être ignoré.

    Refuser sur la seule présence du fichier interdirait la restauration après
    exactement l'événement qui la rend nécessaire — un arrêt brutal.
    """
    _ecrire_memoire("état")
    cible, _ = sauvegarder()
    (deploiement / VERROU).write_text('{"instance": "morte"}', encoding="utf-8")

    assert restaurer(cible.name) == ["memory.sqlite"]


def test_les_sauvegardes_se_listent_de_la_plus_recente(deploiement):
    """Un opérateur qui restaure cherche la dernière."""
    _ecrire_memoire("un")
    premiere, _ = sauvegarder()
    time.sleep(1.05)  # l'horodatage a une seconde de résolution
    seconde, _ = sauvegarder()

    noms = [chemin.name for chemin in lister()]
    assert noms[:2] == [seconde.name, premiere.name]


def test_sauvegarder_un_repertoire_vide_ne_pretend_rien(tmp_path, monkeypatch):
    """Rendre « sauvegarde effectuée » sans base serait une fausse assurance."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path / "vide"))
    monkeypatch.setenv("GALSEN_BACKUP_DIR", str(tmp_path / "sauvegardes"))
    (tmp_path / "vide").mkdir()

    _, copiees = sauvegarder()

    assert copiees == []
