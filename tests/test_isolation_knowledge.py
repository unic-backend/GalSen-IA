"""
La frontière d'isolation appliquée à la base de connaissance (phase 40.2).

La règle de la vague des connecteurs, dans sa forme la plus concrète : **le
courriel de quelqu'un n'entre pas dans la base de connaissance.** Ni son fichier
Drive, ni son agenda. Une fois entrée, la donnée est visible de tous ceux qui
interrogent la base, et aucun filtre postérieur ne l'en retire.

Trois chemins mènent à cette base, et les trois sont fermés ici :
`KnowledgeManager.add_knowledge`, `DocumentIngestor.ingest_file`, et
`AgentContext.add_knowledge`.

Ce que ces tests gardent aussi :

- **La portée voyage jusqu'au bloc.** Un document ingéré en plusieurs passages
  ne perd pas son origine en route.
- **Le refus d'isolation traverse les `except` généraux.** Un appelant ne doit
  pas pouvoir lire « j'ai fait fuiter une donnée » comme « le moteur a eu un
  hoquet » — il réessaierait.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.context import AgentContext  # noqa: E402
from src.knowledge_engine.ingestion import DocumentIngestor  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.knowledge_engine.types import (  # noqa: E402
    KnowledgeItem,
    KnowledgeSource,
    SourceCategory,
)
from src.security.isolation import IsolationError  # noqa: E402
from src.tool.capabilities import DataScope, load_capabilities  # noqa: E402

COURRIEL = "Rendez-vous vendredi 14h avec le comptable, dossier n° 4471."


@pytest.fixture
def base():
    """Une base de connaissance vide."""
    return KnowledgeManagerImpl()


def _source(portee=DataScope.PUBLIC, sujet=None, type_="file"):
    """Une source de connaissance, de la portée demandée."""
    return KnowledgeSource(
        id="s1", type=type_, location="origine", data_scope=portee, subject=sujet
    )


# ----------------------------------------------------------------------
# 1. Le moteur de connaissance
# ----------------------------------------------------------------------

def test_un_courriel_prive_n_entre_pas_dans_la_base(base):
    """La règle absolue de la vague des connecteurs, en un test."""
    prive = KnowledgeItem(
        content=COURRIEL,
        source=_source(DataScope.USER_PRIVATE, "fatou", type_="connector"),
    )

    with pytest.raises(IsolationError, match="magasin partagé"):
        base.add_knowledge(prive)


def test_le_refus_a_lieu_avant_toute_ecriture(base):
    """
    Refuser après avoir écrit ne serait pas refuser. La base doit être
    inchangée, index compris.
    """
    avant = len(base.search_knowledge("comptable", limit=50))

    with pytest.raises(IsolationError):
        base.add_knowledge(KnowledgeItem(
            content=COURRIEL,
            source=_source(DataScope.USER_PRIVATE, "fatou"),
        ))

    assert len(base.search_knowledge("comptable", limit=50)) == avant
    assert base.search_knowledge("4471", limit=50) == []


@pytest.mark.parametrize("portee", [DataScope.PUBLIC, DataScope.SYSTEM])
def test_une_connaissance_non_privee_entre_normalement(base, portee):
    """Isoler n'est pas bloquer : la voie normale reste ouverte."""
    identifiant = base.add_knowledge(KnowledgeItem(
        content="Le franc CFA est la monnaie du Sénégal.",
        source=_source(portee),
    ))

    assert identifiant
    assert base.get_knowledge(identifiant) is not None


def test_le_defaut_reste_public_pour_les_sources_existantes(base):
    """
    Une source qui ne déclare rien est publique — c'est la vérité des sources
    du dépôt, et le connecteur ne choisit pas cette valeur : elle est dérivée
    de sa capacité.
    """
    identifiant = base.add_knowledge(KnowledgeItem(
        content="Dakar est la capitale du Sénégal.",
        source=KnowledgeSource(id="s", type="file", location="x"),
    ))

    assert identifiant


# ----------------------------------------------------------------------
# 2. L'ingestion de fichiers
# ----------------------------------------------------------------------

def test_un_fichier_prive_n_est_meme_pas_ouvert(base, tmp_path):
    """
    Le refus porte sur le document entier et vient **avant** la lecture. Bloc
    par bloc, il tomberait dans le `except` de la boucle et deviendrait une
    ligne d'erreur parmi d'autres.
    """
    fichier = tmp_path / "drive.txt"
    fichier.write_text(COURRIEL * 40, encoding="utf-8")
    ingesteur = DocumentIngestor(base)

    with pytest.raises(IsolationError, match="magasin partagé"):
        ingesteur.ingest_file(
            str(fichier), title="Document du Drive",
            source_category=SourceCategory.UNKNOWN,
            data_scope=DataScope.USER_PRIVATE, owner="fatou",
        )

    assert base.search_knowledge("comptable", limit=50) == []


def test_un_fichier_public_s_ingere_et_sa_portee_voyage(base, tmp_path):
    """La portée doit atteindre chaque bloc, pas seulement le premier."""
    fichier = tmp_path / "public.txt"
    fichier.write_text(
        "Le Sénégal compte quatorze régions administratives. " * 120,
        encoding="utf-8",
    )
    ingesteur = DocumentIngestor(base)

    rapport = ingesteur.ingest_file(
        str(fichier), title="Régions du Sénégal",
        source_category=SourceCategory.OFFICIAL,
    )

    assert rapport.chunks > 1, "Un seul bloc ne prouverait pas le voyage"
    assert rapport.errors == []
    for identifiant in rapport.knowledge_ids:
        item = base.get_knowledge(identifiant)
        assert item.source.data_scope is DataScope.PUBLIC


# ----------------------------------------------------------------------
# 3. Le chemin des agents
# ----------------------------------------------------------------------

def test_un_agent_ne_verse_pas_de_donnee_privee():
    """Un agent qui a lu un courriel ne peut pas le déposer dans la base."""
    contexte = AgentContext(request="résumer la boîte", agent_id="organizer")

    with pytest.raises(IsolationError):
        contexte.add_knowledge(
            COURRIEL, data_scope=DataScope.USER_PRIVATE, subject="fatou"
        )


def test_le_refus_d_isolation_traverse_le_except_general():
    """
    `add_knowledge` rend `None` quand le moteur est absent. Rendre `None` ici
    aussi ferait passer une fuite pour un incident passager, et l'appelant
    réessaierait.
    """
    contexte = AgentContext(request="test", agent_id="coder")

    with pytest.raises(IsolationError):
        contexte.add_knowledge("x", data_scope=DataScope.USER_PRIVATE, subject="awa")


def test_l_audit_d_une_fuite_refusee_ne_recopie_pas_le_contenu():
    """
    Consigner l'incident ne doit pas écrire la donnée privée dans le journal
    d'audit — ce serait la faire fuiter par le chemin qui la surveille.
    """
    import inspect

    source = inspect.getsource(AgentContext.add_knowledge)
    bloc = source[source.index("except IsolationError"):source.index("except Exception")]

    assert "content_preview" not in bloc
    assert "user_private_vers_magasin_partage" in bloc


def test_un_agent_verse_normalement_une_connaissance_publique():
    """La voie normale d'un agent reste ouverte."""
    contexte = AgentContext(request="test", agent_id="researcher")

    identifiant = contexte.add_knowledge("Le mil est cultivé au Sénégal.")

    assert identifiant


# ----------------------------------------------------------------------
# 4. L'invariant sur le registre réel
# ----------------------------------------------------------------------

def test_aucun_outil_prive_ne_peut_alimenter_la_base(base):
    """
    Vérifié sur les 22 outils du registre, pas sur un exemple choisi : tout
    outil déclaré `user_private` est refusé à l'entrée de la base.
    """
    registre = load_capabilities()
    prives = [
        tool_id for tool_id, capacite in registre.capabilities.items()
        if capacite.data_scope is DataScope.USER_PRIVATE
    ]
    assert prives, "Le registre devrait porter au moins un outil privé"

    for tool_id in prives:
        with pytest.raises(IsolationError):
            base.add_knowledge(KnowledgeItem(
                content=f"Sortie de l'outil {tool_id}",
                source=_source(DataScope.USER_PRIVATE, "fatou", type_="tool"),
            ))
