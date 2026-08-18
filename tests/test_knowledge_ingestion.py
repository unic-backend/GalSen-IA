"""
Ingestion de documents et citation des sources (VOLET 28 — ch. 01 et 03).

Deux moteurs existaient sans se rencontrer : `TextFileLoader` versait **un
fichier entier en un seul élément de connaissance**, pendant que le découpeur du
moteur documentaire dormait à côté. Un document de cinquante pages devenait un
bloc que la recherche notait une fois et qu'une citation désignait en entier —
c'est-à-dire pas du tout.

Et `retrieve_reliable()` rendait des connaissances sans jamais dire d'où elles
venaient : une réponse enrichie par la base était indiscernable d'une réponse
inventée par le modèle.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.citations import (  # noqa: E402
    build_citations,
    citation_coverage,
)
from src.knowledge_engine.ingestion import DocumentIngestor  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.knowledge_engine.types import (  # noqa: E402
    KnowledgeItem,
    KnowledgeSource,
    KnowledgeStatus,
    SourceCategory,
)

# Assez long pour produire plusieurs blocs avec la taille par défaut (1000).
LONG_DOCUMENT = (
    "L'irrigation goutte à goutte réduit la consommation d'eau. " * 40
    + "\n\n"
    + "La rotation des cultures limite l'appauvrissement des sols. " * 40
)


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Base de connaissances isolée, en mémoire."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "in-memory")
    return KnowledgeManagerImpl()


@pytest.fixture
def document(tmp_path):
    """Un document assez long pour être découpé."""
    chemin = tmp_path / "guide-agricole.md"
    chemin.write_text(LONG_DOCUMENT, encoding="utf-8")
    return str(chemin)


# ----------------------------------------------------------------------
# L'ingestion découpe, au lieu de verser un pavé
# ----------------------------------------------------------------------

def test_un_document_long_devient_plusieurs_blocs(base, document):
    """
    Le fait qui justifie le chapitre.

    Avant : un fichier = un élément. Une citation désignait alors le document
    entier, ce qui revient à ne rien citer.
    """
    rapport = DocumentIngestor(base).ingest_file(
        document, title="Guide agricole", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert rapport.chunks > 1, "Le document n'a pas été découpé"
    assert len(rapport.knowledge_ids) == rapport.chunks
    assert rapport.errors == []


def test_chaque_bloc_porte_sa_provenance(base, document):
    """Une connaissance sans source est une affirmation sans auteur."""
    rapport = DocumentIngestor(base).ingest_file(
        document, title="Guide agricole", source_category=SourceCategory.INSTITUTIONAL,
        author="Institut de recherche", url="https://exemple.sn/guide",
    )

    item = base.get_knowledge(rapport.knowledge_ids[0])

    assert item.source.title == "Guide agricole"
    assert item.source.author == "Institut de recherche"
    assert item.source.url == "https://exemple.sn/guide"
    assert item.source.source_category is SourceCategory.INSTITUTIONAL
    # La citation situe le passage dans le document, pas seulement le document.
    assert "passage 1/" in item.source.citation
    assert item.metadata["chunk_index"] == 0
    assert item.metadata["file_hash"]


def test_reingerer_le_meme_fichier_ne_duplique_pas(base, document):
    """Rejouer une ingestion doit mettre à jour, jamais empiler."""
    ingestor = DocumentIngestor(base)
    premier = ingestor.ingest_file(
        document, title="Guide agricole", source_category=SourceCategory.INSTITUTIONAL,
    )
    apres_une_fois = len(base.get_store().list_items())

    second = ingestor.ingest_file(
        document, title="Guide agricole", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert second.knowledge_ids == premier.knowledge_ids
    assert len(base.get_store().list_items()) == apres_une_fois


def test_un_document_entre_en_brouillon(base, document):
    """
    Ingérer n'est pas approuver.

    Faire entrer un document externe directement en `APPROVED` viderait de son
    sens le cycle de vie du VOLET 05.
    """
    rapport = DocumentIngestor(base).ingest_file(
        document, title="Guide agricole", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert base.get_knowledge(rapport.knowledge_ids[0]).status is KnowledgeStatus.DRAFT


def test_un_titre_vide_est_refuse(base, document):
    """Le titre finira dans une citation : l'exiger est le sens du chapitre."""
    with pytest.raises(ValueError, match="titre"):
        DocumentIngestor(base).ingest_file(
            document, title="  ", source_category=SourceCategory.INSTITUTIONAL,
        )


def test_un_fichier_absent_est_refuse_clairement(base):
    """Une erreur de chemin doit se dire, pas se deviner."""
    with pytest.raises(FileNotFoundError):
        DocumentIngestor(base).ingest_file(
            "/inexistant/nulle-part.md", title="X",
            source_category=SourceCategory.INSTITUTIONAL,
        )


def test_un_format_non_pris_en_charge_est_signale_et_non_ignore(base, tmp_path):
    """
    Une bibliothèque optionnelle absente est une information, pas une panne.

    Le rapport doit le dire : une ingestion silencieusement vide ferait croire
    que le document est entré.
    """
    fichier = tmp_path / "rapport.pdf"
    fichier.write_bytes(b"%PDF-1.4 pas un vrai PDF")

    rapport = DocumentIngestor(base).ingest_file(
        str(fichier), title="Rapport", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert rapport.knowledge_ids == []
    assert rapport.errors, "Un format non lisible doit être rapporté"


def test_le_decoupage_reutilise_celui_du_moteur_documentaire(base, document):
    """
    Le motif que ce dépôt a trouvé huit fois : deux implémentations d'une idée.

    Ce test échouera si quelqu'un réécrit un découpeur ici.
    """
    import src.knowledge_engine.ingestion as ingestion

    assert ingestion.SimpleChunker.__module__ == (
        "src.document_intelligence_engine.simple_chunker"
    )


# ----------------------------------------------------------------------
# La citation des sources
# ----------------------------------------------------------------------

def test_une_reponse_porte_ses_sources(base, document):
    """`retrieve_reliable` doit dire d'où vient ce qu'elle rend."""
    DocumentIngestor(base).ingest_file(
        document, title="Guide agricole", source_category=SourceCategory.INSTITUTIONAL,
        author="Institut", status=KnowledgeStatus.APPROVED,
    )

    reponse = base.retrieve_reliable("irrigation goutte à goutte", max_items=3, role="admin")

    assert reponse["items"], "La recherche ne rend rien : le test ne prouverait rien"
    assert reponse["sources"], "Une réponse sans source est indiscernable d'une invention"
    assert reponse["sources"][0]["title"] == "Guide agricole"
    assert reponse["citation_coverage"]["coverage"] == 1.0


def test_les_passages_d_un_meme_document_sont_regroupes():
    """Cinq blocs d'un rapport font une source à cinq passages, pas cinq sources."""
    source = KnowledgeSource(
        id="s", type="file", location="/docs/guide.md", hash="abc123",
        title="Guide", source_category=SourceCategory.INSTITUTIONAL,
    )
    items = []
    for position in range(3):
        item = KnowledgeItem(content=f"bloc {position}", source=KnowledgeSource(
            **{**source.__dict__, "citation": f"Guide, passage {position + 1}/3"}
        ))
        items.append(item)

    citations = build_citations(items)

    assert len(citations) == 1
    assert len(citations[0]["passages"]) == 3


def test_une_provenance_inconnue_est_signalee_et_non_maquillee():
    """
    Une source vide ne doit pas ressembler à une source.

    Rendre une entrée sans titre ni emplacement la ferait passer pour une
    référence auprès de n'importe quel affichage.
    """
    item = KnowledgeItem(content="Une affirmation sans origine")

    citations = build_citations([item])

    assert citations[0]["known"] is False
    assert "vérifi" in citations[0]["detail"]


def test_la_couverture_de_citation_se_mesure():
    """
    Le chiffre qui rend la règle exécutable.

    Une base dont la moitié des éléments ne sont pas citables rend la moitié de
    ses réponses invérifiables — mieux vaut le savoir que le découvrir.
    """
    sourcee = KnowledgeItem(content="a", source=KnowledgeSource(
        id="s", type="file", location="/docs/a.md", title="A",
    ))
    orpheline = KnowledgeItem(content="b")

    couverture = citation_coverage([sourcee, orpheline])

    assert couverture == {"items": 2, "with_source": 1, "coverage": 0.5}


def test_une_base_vide_ne_rend_pas_une_couverture_parfaite():
    """Zéro sur zéro n'est pas 100 % : ce serait le pire des faux positifs."""
    assert citation_coverage([])["coverage"] == 0.0


# ----------------------------------------------------------------------
# Le corpus de départ
# ----------------------------------------------------------------------

def test_le_script_de_remplissage_verse_la_documentation(base, monkeypatch):
    """
    La base contenait 0 élément. Le script doit la remplir avec du vérifiable.

    Ce qui est versé, c'est la documentation du dépôt : elle existe, elle est
    relue, elle se vérifie ligne à ligne.
    """
    from scripts.seed_knowledge import etat, semer_documentation

    rapports = semer_documentation(base, DocumentIngestor(base))

    assert rapports, "Aucun document ingéré"
    assert etat(base)["total_items"] > 50
    # Chaque bloc est citable : c'est ce qui distingue un corpus d'un tas de texte.
    items = base.get_store().list_items()
    assert citation_coverage(items)["coverage"] == 1.0


def test_le_manifeste_refuse_un_document_sans_provenance(base, tmp_path, capsys):
    """Un document sans titre ni catégorie n'entre pas : c'est la règle du chapitre."""
    from scripts.seed_knowledge import semer_manifeste

    fichier = tmp_path / "sans-source.md"
    fichier.write_text("Un texte quelconque", encoding="utf-8")
    manifeste = tmp_path / "corpus.yaml"
    manifeste.write_text(
        f"documents:\n  - path: {fichier}\n    title: ''\n", encoding="utf-8"
    )

    rapports = semer_manifeste(base, DocumentIngestor(base), str(manifeste))

    assert rapports == []
    assert "refusé" in capsys.readouterr().out
