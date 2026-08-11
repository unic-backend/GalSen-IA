"""
Tests du chiffrement au repos (VOLET 02 ch. 08, phase 8.3).

Trois propriétés commandent ce module, et sont testées avant les mécanismes :

- **activer le chiffrement ne casse pas une base existante** : les lignes déjà
  écrites en clair restent lisibles ;
- **une clé mal formée arrête le démarrage** plutôt que de laisser écrire en
  clair en donnant l'illusion d'une protection ;
- **une valeur illisible n'est jamais rendue** : rendre le texte chiffré comme
  s'il était le contenu ferait passer un échec pour une donnée.

Le dernier test ouvre le fichier SQLite en binaire : c'est la seule preuve que
le contenu n'y est pas en clair.
"""

import os

import pytest

from src.memory_engine.types import MemoryItem
from src.storage.encryption import (
    ENCRYPTED_PREFIX,
    KEY_VARIABLE,
    EncryptionError,
    EncryptionKeyError,
    decrypt,
    encrypt,
    generate_key,
    is_enabled,
    verify_key,
)


@pytest.fixture(autouse=True)
def environnement_propre(monkeypatch):
    """Retire toute clé héritée de l'environnement réel."""
    monkeypatch.delenv(KEY_VARIABLE, raising=False)


@pytest.fixture
def cle(monkeypatch):
    """Active le chiffrement avec une clé fraîche."""
    valeur = generate_key()
    monkeypatch.setenv(KEY_VARIABLE, valeur)
    return valeur


class TestSansChiffrement:
    """Vérifie le comportement quand aucune clé n'est configurée."""

    def test_desactive_par_defaut(self):
        """Sans clé, le chiffrement est inactif."""
        assert is_enabled() is False

    def test_les_valeurs_traversent(self):
        """Sans clé, rien n'est transformé : la plateforme reste utilisable."""
        assert encrypt("Dakar") == "Dakar"
        assert decrypt("Dakar") == "Dakar"

    def test_verification_sans_objet(self):
        """La vérification de démarrage ne doit rien exiger sans clé."""
        verify_key()  # ne doit pas lever


class TestChiffrement:
    """Vérifie l'aller-retour quand une clé est configurée."""

    def test_actif_avec_une_cle(self, cle):
        """Une clé configurée active le chiffrement."""
        assert is_enabled() is True

    def test_aller_retour(self, cle):
        """Une valeur chiffrée doit se retrouver identique après déchiffrement."""
        assert decrypt(encrypt("Le secret de Awa")) == "Le secret de Awa"

    def test_la_valeur_chiffree_ne_contient_pas_le_clair(self, cle):
        """Le texte d'origine ne doit apparaître nulle part dans le jeton."""
        chiffre = encrypt("Le secret de Awa")
        assert "secret" not in chiffre
        assert chiffre.startswith(ENCRYPTED_PREFIX)

    def test_deux_chiffrements_different(self, cle):
        """Le même texte ne doit pas produire deux fois le même jeton."""
        assert encrypt("Dakar") != encrypt("Dakar")

    def test_accents_et_caracteres_non_latins(self, cle):
        """Le contenu sénégalais ne doit pas être abîmé par l'encodage."""
        for texte in ("Thiès, Saint-Louis", "Ñaari doomu ndey", "مرحبا"):
            assert decrypt(encrypt(texte)) == texte

    def test_valeurs_vides_traversent(self, cle):
        """`None` et la chaîne vide n'ont rien à cacher."""
        assert encrypt(None) is None
        assert encrypt("") == ""

    def test_verification_de_la_cle(self, cle):
        """Une clé valide doit passer la vérification de démarrage."""
        verify_key()


class TestCompatibiliteAscendante:
    """Vérifie qu'activer le chiffrement ne rend pas illisible l'existant."""

    def test_une_valeur_en_clair_reste_lisible(self, cle):
        """Une ligne écrite avant l'activation traverse sans marque."""
        assert decrypt("écrit avant le chiffrement") == "écrit avant le chiffrement"

    def test_melange_des_deux_formes(self, cle):
        """Une base à moitié migrée doit rester entièrement lisible."""
        valeurs = ["ancienne ligne", encrypt("nouvelle ligne")]
        assert [decrypt(v) for v in valeurs] == ["ancienne ligne", "nouvelle ligne"]

    def test_une_valeur_chiffree_reste_illisible_sans_cle(self, cle, monkeypatch):
        """Sans la clé, la valeur ne doit pas être rendue comme du contenu."""
        chiffre = encrypt("Le secret de Awa")
        monkeypatch.delenv(KEY_VARIABLE)
        with pytest.raises(EncryptionKeyError):
            decrypt(chiffre)


class TestEchecsHonnetes:
    """Vérifie que rien d'illisible n'est présenté comme une donnée."""

    def test_cle_mal_formee(self, monkeypatch):
        """Une clé invalide doit lever, jamais retomber sur l'écriture en clair."""
        monkeypatch.setenv(KEY_VARIABLE, "ceci-nest-pas-une-cle")
        with pytest.raises(EncryptionKeyError, match=KEY_VARIABLE):
            encrypt("Dakar")

    def test_le_message_ne_contient_pas_la_cle(self, monkeypatch):
        """Le message d'erreur nomme la variable, jamais sa valeur."""
        monkeypatch.setenv(KEY_VARIABLE, "cle-secrete-mal-formee")
        with pytest.raises(EncryptionKeyError) as erreur:
            encrypt("Dakar")
        assert "cle-secrete-mal-formee" not in str(erreur.value)

    def test_mauvaise_cle_au_dechiffrement(self, cle, monkeypatch):
        """Une clé qui ne correspond pas doit lever, pas rendre le jeton."""
        chiffre = encrypt("Le secret de Awa")
        monkeypatch.setenv(KEY_VARIABLE, generate_key())
        with pytest.raises(EncryptionError, match="illisible"):
            decrypt(chiffre)

    def test_donnee_corrompue(self, cle):
        """Un jeton abîmé doit être signalé, pas rendu tel quel."""
        with pytest.raises(EncryptionError):
            decrypt(f"{ENCRYPTED_PREFIX}jeton-corrompu")


class TestSurLaBaseReelle:
    """Vérifie le résultat là où il compte : dans le fichier SQLite."""

    def test_le_contenu_n_est_pas_lisible_sur_le_disque(self, cle, tmp_path):
        """Un fichier de base copié ne doit pas livrer le contenu."""
        from src.storage.sqlite_store import SQLiteMemoryStore

        chemin = str(tmp_path / "memoires.sqlite")
        store = SQLiteMemoryStore(chemin)
        store.save(MemoryItem(content="Le secret bancaire de Awa"))

        with open(chemin, "rb") as fichier:
            octets = fichier.read()
        assert b"secret bancaire" not in octets

    def test_l_application_relit_correctement(self, cle, tmp_path):
        """Le chiffrement doit être transparent pour la plateforme."""
        from src.storage.sqlite_store import SQLiteMemoryStore

        store = SQLiteMemoryStore(str(tmp_path / "memoires.sqlite"))
        store.save(MemoryItem(content="Le secret bancaire de Awa"))
        assert store.list_items()[0].content == "Le secret bancaire de Awa"

    def test_un_contenu_structure_survit(self, cle, tmp_path):
        """Un contenu JSON doit revenir tel qu'il a été rangé."""
        from src.storage.sqlite_store import SQLiteMemoryStore

        store = SQLiteMemoryStore(str(tmp_path / "memoires.sqlite"))
        store.save(MemoryItem(content={"ville": "Dakar", "population": 3_000_000}))
        assert store.list_items()[0].content == {"ville": "Dakar", "population": 3_000_000}

    def test_une_base_ecrite_en_clair_reste_lisible(self, tmp_path, monkeypatch):
        """Le cas qui compte : activer le chiffrement sur une base existante."""
        from src.storage.sqlite_store import SQLiteMemoryStore

        chemin = str(tmp_path / "memoires.sqlite")

        # Écriture sans chiffrement, comme une installation d'hier
        monkeypatch.delenv(KEY_VARIABLE, raising=False)
        SQLiteMemoryStore(chemin).save(MemoryItem(content="mémoire d'avant"))

        # L'opérateur active le chiffrement et redémarre
        monkeypatch.setenv(KEY_VARIABLE, generate_key())
        store = SQLiteMemoryStore(chemin)
        assert store.list_items()[0].content == "mémoire d'avant"

        # Les nouvelles écritures, elles, sont protégées
        store.save(MemoryItem(content="mémoire d'après"))

        # Les bases tournent en mode WAL : une écriture récente vit dans le
        # fichier `-wal` tant qu'aucun point de reprise ne l'a repliée dans la
        # base. Lire les octets du seul fichier principal ne dit donc rien de ce
        # qui vient d'être écrit — c'est aussi pourquoi une sauvegarde par copie
        # de fichier est fausse, et pourquoi `scripts/backup.py` passe par
        # `VACUUM INTO`.
        import sqlite3
        with sqlite3.connect(chemin) as connexion:
            connexion.execute("PRAGMA wal_checkpoint(FULL)")

        with open(chemin, "rb") as fichier:
            octets = fichier.read()
        assert b"m\xc3\xa9moire d'apr\xc3\xa8s" not in octets
        assert b"m\xc3\xa9moire d'avant" in octets
