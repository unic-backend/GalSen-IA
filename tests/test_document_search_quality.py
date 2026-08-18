"""
La recherche documentaire : trouver, et dire pourquoi (phase 54.1).

L'audit du programme rangeait le « moteur de recherche documentaire » parmi les
domaines **absents**. C'est faux, et il faut le dire — comme pour les
notifications au VOLET 50. Le moteur existe : chargeurs (PDF, DOCX, XLSX, PPTX,
OCR, JSON, Markdown, texte), découpage, index inversé **BM25**, versionnement,
détection de doublons, comparaison, extraction de tableaux, et un fournisseur
branché sur la recherche unifiée `/search` avec filtrage par propriétaire.

Ce qui manquait n'était pas le moteur, c'étaient trois défauts précis :

1. **Le titre n'était pas indexé.** Un document intitulé « Rapport agricole
   2024 » dont le corps ne répète pas ces mots était introuvable par son propre
   titre — le défaut le plus visible possible : on tape ce qu'on lit à l'écran,
   et rien ne sort.
2. **Les accents empêchaient de trouver.** « senegal » ne trouvait pas
   « Sénégal ». La correction évidente — replier les accents — est **fausse
   telle quelle pour le wolof**, où `ñ` et `n` distinguent des mots réels.
3. **Ce qui avait fait correspondre n'était pas dit.** Un score sans sa cause
   est, dans ce dépôt, le même défaut qu'une valeur sans provenance.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.document_intelligence_engine.in_memory_indexer import (  # noqa: E402
    POIDS_DU_TITRE,
    InMemoryIndexer,
)
from src.document_intelligence_engine.types import (  # noqa: E402
    DocumentItem,
    DocumentType,
)


def _document(identifiant, titre, contenu):
    """Un document indexable."""
    return DocumentItem(
        document_id=identifiant,
        document_type=DocumentType.TXT,
        title=titre,
        content=contenu,
    )


@pytest.fixture
def index():
    """Un index portant quatre documents distincts."""
    indexeur = InMemoryIndexer()
    indexeur.index(_document(
        "doc-agri", "Rapport agricole 2024",
        "Les rendements observés dans la vallée du fleuve pour la campagne.",
    ))
    indexeur.index(_document(
        "doc-sen", "Note économique",
        "L'économie du Sénégal repose en partie sur la pêche et l'arachide.",
    ))
    indexeur.index(_document(
        "doc-wolof-n", "Note wolof — nit",
        "Nit ku bokk ci mbootaayu askan wi.",
    ))
    indexeur.index(_document(
        "doc-wolof-gn", "Note wolof — ñu",
        "Ñu ngi dem ci marse bi.",
    ))
    return indexeur


def _identifiants(resultats):
    """Les identifiants d'une liste de résultats."""
    return [document.document_id for document, _ in resultats]


# ----------------------------------------------------------------------
# 1. Un document se trouve par son titre
# ----------------------------------------------------------------------

def test_un_document_se_trouve_par_son_titre(index):
    """
    Le défaut le plus visible : on tape ce qu'on lit à l'écran, et rien ne
    sortait. « agricole » n'apparaît que dans le titre.
    """
    resultats = index.search("agricole")

    assert _identifiants(resultats) == ["doc-agri"]


def test_le_titre_pese_sans_ecraser_le_corps(index):
    """
    Assez pour qu'un document se trouve par son titre, pas assez pour qu'un
    titre bien choisi écrase un corps réellement pertinent.
    """
    assert POIDS_DU_TITRE == 3

    index.index(_document("doc-corps", "Divers",
                          "pêche pêche pêche pêche pêche pêche pêche"))
    index.index(_document("doc-titre", "pêche", "Un texte sans rapport."))

    premier = _identifiants(index.search("pêche"))[0]

    assert premier == "doc-corps"


def test_un_document_sans_titre_reste_indexable(index):
    """Un titre vide ne doit pas casser l'indexation."""
    index.index(_document("doc-nu", "", "Un contenu sans titre du tout."))

    assert "doc-nu" in _identifiants(index.search("contenu"))


# ----------------------------------------------------------------------
# 2. Les accents : ajouter, jamais retirer
# ----------------------------------------------------------------------

def test_une_requete_sans_accent_trouve_un_document_accentue(index):
    """« senegal » doit trouver « Sénégal »."""
    assert "doc-sen" in _identifiants(index.search("senegal"))


def test_la_requete_accentuee_trouve_toujours(index):
    """L'expansion ajoute et ne retire jamais : la forme brute marche encore."""
    assert "doc-sen" in _identifiants(index.search("Sénégal"))


def test_une_requete_wolof_avec_gn_trouve_le_bon_document(index):
    """
    `ñ` et `n` distinguent des mots réels en wolof. Détruire la distinction
    dans l'index reviendrait à confondre deux mots pour faire plaisir à une
    requête française.
    """
    resultats = _identifiants(index.search("ñu"))

    assert resultats == ["doc-wolof-gn"]


def test_une_requete_sans_le_signe_elargit_sans_effacer(index):
    """
    Le coût assumé de l'expansion : « nu » atteint aussi le document en `ñu`.
    C'est un élargissement de portée, pas une perte de distinction — la
    requête exacte, elle, reste exacte.
    """
    elargie = _identifiants(index.search("nu"))
    exacte = _identifiants(index.search("ñu"))

    assert "doc-wolof-gn" in elargie
    assert exacte == ["doc-wolof-gn"]


# ----------------------------------------------------------------------
# 3. Dire ce qui a fait correspondre
# ----------------------------------------------------------------------

def test_les_termes_qui_ont_correspondu_sont_nommes(index):
    """Un score sans sa cause est le même défaut qu'une valeur sans provenance."""
    correspondants = index.matched_terms("doc-sen", "économie du Sénégal")

    assert "économie" in correspondants
    assert "sénégal" in correspondants


def test_les_termes_qui_n_ont_rien_touche_sont_dits_aussi(index):
    """Ils expliquent pourquoi un résultat attendu manque."""
    explication = index.explain("économie et bauxite")[0]

    assert "économie" in explication["matched_terms"]
    assert "bauxite" in explication["unmatched_terms"]


def test_l_explication_dit_que_le_score_ne_mesure_pas_le_sens(index):
    """
    Un appelant qui prendrait ce score pour une mesure de sens se tromperait
    exactement le jour où cela compte (ADR-015).
    """
    explication = index.explain("agricole")[0]

    assert explication["method"] == "BM25 lexical"
    assert "pas de sens" in explication["note"]


def test_l_explication_suit_l_ordre_du_classement(index):
    """Expliquer un autre classement que celui qui est rendu serait pire que
    de ne rien expliquer."""
    classement = _identifiants(index.search("wolof"))
    explique = [e["document_id"] for e in index.explain("wolof")]

    assert explique == classement


def test_une_requete_sans_correspondance_n_explique_rien(index):
    """Aucun résultat : aucune explication inventée."""
    assert index.explain("bauxite") == []


def test_l_index_reste_juste_apres_une_reindexation(index):
    """
    Réindexer remplace : un terme retiré du titre ne doit pas continuer à faire
    trouver le document.
    """
    index.index(_document("doc-agri", "Rapport minier 2024", "Autre contenu."))

    assert _identifiants(index.search("agricole")) == []
    assert "doc-agri" in _identifiants(index.search("minier"))


def test_supprimer_un_document_le_retire_de_tous_ses_termes(index):
    """
    Le défaut trouvé en écrivant ce fichier : la suppression **recalculait**
    les termes depuis le contenu au lieu de relire ceux qui avaient été
    indexés. Elle ratait donc le titre et les formes repliées, et un document
    réindexé restait trouvable par son ancien titre.
    """
    index.delete("doc-sen")

    assert _identifiants(index.search("sénégal")) == []
    assert _identifiants(index.search("senegal")) == []
    assert _identifiants(index.search("économique")) == []


def test_vider_l_index_ne_laisse_aucune_trace(index):
    """La même mémoire doit être vidée que celle qui est écrite."""
    index.clear()

    assert index.search("agricole") == []
    assert index.matched_terms("doc-agri", "agricole") == []
