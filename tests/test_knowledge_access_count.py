"""
Le seul signal d'usage que la plateforme recueille (VOLET 23, chapitres 01 et 03).

Le manuel demande un moteur d'apprentissage : collecte d'expérience,
reconnaissance de motifs, réentraînement. Rien de tout cela n'existe. Une seule
boucle de rétroaction est câblée — le compteur de consultations d'une
connaissance, qui alimente le critère `popularity` du classement — et elle ne
fonctionnait pas.
"""

import pytest

from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.knowledge_ranker import KnowledgeRankerImpl
from src.knowledge_engine.types import KnowledgeDomain, KnowledgeItem
from src.storage.sqlite_knowledge_store import SQLiteKnowledgeStore


def _connaissance(contenu="Le mil se sème en juin au Sénégal."):
    """Construit une connaissance opérationnelle."""
    return KnowledgeItem(content=contenu, domain=KnowledgeDomain.OPERATIONAL)


@pytest.fixture
def base():
    """Base en mémoire."""
    return KnowledgeManagerImpl()


@pytest.fixture
def base_sqlite():
    """Base SQLite, où le compteur n'a jamais fonctionné."""
    magasin = SQLiteKnowledgeStore(db_path=":memory:")
    yield KnowledgeManagerImpl(store=magasin), magasin
    magasin.close()


def test_consulter_une_connaissance_la_compte(base):
    """Le compteur restait à zéro : la seule mesure d'usage était perdue."""
    identifiant = base.add_knowledge(_connaissance())

    for _ in range(5):
        base.get_knowledge(identifiant)

    assert base.get_store().get(identifiant).metadata["access_count"] == 5


def test_le_compteur_fonctionne_aussi_sur_sqlite(base_sqlite):
    """
    Il n'a jamais fonctionné sur SQLite.

    Le compteur passait par `get()` puis `update()` sans incrémenter la version,
    donc `update()` refusait l'écriture ; en mémoire il survivait par le partage
    de référence du magasin, ce que SQLite ne fait pas — il désérialise.
    """
    base, magasin = base_sqlite
    identifiant = base.add_knowledge(_connaissance())

    for _ in range(3):
        base.get_knowledge(identifiant)

    assert magasin.get(identifiant).metadata["access_count"] == 3


def test_consulter_ne_cree_pas_une_nouvelle_version(base):
    """Une consultation n'est pas une modification de la connaissance."""
    identifiant = base.add_knowledge(_connaissance())
    version_initiale = base.get_store().get(identifiant).version

    for _ in range(4):
        base.get_knowledge(identifiant)

    assert base.get_store().get(identifiant).version == version_initiale


def test_le_cache_suit_le_compteur(base):
    """Un cache en retard sur le magasin ferait rejouer le défaut du VOLET 21."""
    identifiant = base.add_knowledge(_connaissance())

    base.get_knowledge(identifiant)
    base.get_knowledge(identifiant)

    assert base.get_knowledge(identifiant).metadata["access_count"] >= 2


def test_compter_une_connaissance_absente_ne_leve_pas(base):
    """Un compteur ne doit jamais faire échouer la lecture qu'il mesure."""
    assert base.get_store().record_access("inexistant") == 0


def test_le_critere_de_popularite_cesse_d_etre_toujours_nul(base):
    """
    C'est ce que le compteur perdu coûtait vraiment.

    Le classement pondère un critère `popularity` calculé sur le compteur ;
    tant qu'il valait zéro partout, ce critère ne départageait rien.
    """
    consultee = base.add_knowledge(_connaissance("Le mil se sème en juin."))
    ignoree = base.add_knowledge(_connaissance("L'arachide se récolte en octobre."))
    for _ in range(10):
        base.get_knowledge(consultee)

    classement = KnowledgeRankerImpl().rank(
        [base.get_store().get(ignoree), base.get_store().get(consultee)],
        {"popularity": 1.0},
    )

    assert classement[0][0].id == consultee
    assert classement[0][1] > classement[1][1] == 0.0
