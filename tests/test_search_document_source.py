"""
La troisième source de recherche, et la quatrième qui n'existera pas
(2026-08-13).

Le backlog disait : *« deux sources de quatre n'ont pas de fournisseur
(document, vision) ; toutes deux attendent que leur moteur produise du texte
cherchable, ce que ni l'une ni l'autre ne fait aujourd'hui »*.

**C'était vrai pour la vision et faux pour les documents.** Le moteur
documentaire indexe déjà ce qu'il charge (`search_documents`) : il manquait le
fournisseur, pas l'index. Ces tests épinglent la source branchée, et l'aveu
mesuré pour celle qui ne peut pas l'être.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.document_intelligence_engine.document_manager import DocumentManagerImpl  # noqa: E402
from src.document_intelligence_engine.types import DocumentItem, DocumentType  # noqa: E402
from src.services.search.manager import RAISONS_D_ABSENCE, SearchManagerImpl  # noqa: E402
from src.services.search.providers import DocumentSearchProvider  # noqa: E402
from src.services.search.types import SearchQuery, SearchSource  # noqa: E402


@pytest.fixture
def moteur():
    """
    Un moteur documentaire portant trois documents indexés.

    Les trois déclarations qui comptent : public, possédé, et **rien du tout**.
    """
    moteur = DocumentManagerImpl()
    for identifiant, titre, contenu, metadonnees in (
        ("doc-mil", "Guide du mil",
         "Le semis du mil suit les premières pluies de l'hivernage à Kaolack.",
         {"visibility": "public"}),
        ("doc-awa", "Notes d'Awa sur le mil",
         "Awa note que le mil a levé tard cette année.",
         {"user_id": "awa"}),
        ("doc-prive", "Notes de Moussa sur le mil",
         "Moussa note un mil semé en juillet.",
         {}),
    ):
        moteur.register_document(DocumentItem(
            document_id=identifiant, document_type=DocumentType.TXT,
            title=titre, content=contenu, metadata=metadonnees,
        ))
        moteur.index_document(identifiant)
    return moteur


def test_la_source_document_rend_enfin_des_resultats(moteur):
    """
    Le défaut réparé : l'index existait, le fournisseur manquait.
    """
    resultats = DocumentSearchProvider(moteur).search(SearchQuery(query="mil hivernage"))

    assert resultats, "La source documentaire ne rend toujours rien"
    assert resultats[0].id == "doc-mil"
    assert resultats[0].source is SearchSource.DOCUMENT
    assert resultats[0].title == "Guide du mil"


def test_un_document_qui_ne_declare_rien_n_est_pas_rendu(moteur):
    """
    Le défaut que le branchement a révélé, et qui n'était pas dans le test.

    Le moteur documentaire est un magasin **de plateforme** : il n'a pas de
    propriétaire, et `/search` est multi-utilisateur (ADR-010). Rendre tout ce
    qu'il contient transformerait une recherche personnelle en fuite.
    """
    rendus = {
        resultat.id
        for resultat in DocumentSearchProvider(moteur).search(
            SearchQuery(query="mil", subject="awa")
        )
    }

    assert "doc-prive" not in rendus, "Un document sans déclaration a été servi"
    assert "doc-awa" in rendus, "Le document du sujet n'est pas rendu à son sujet"
    assert "doc-mil" in rendus, "Un document public devrait rester lisible"


def test_le_document_d_un_autre_n_est_pas_rendu(moteur):
    """La même règle, vue depuis l'autre sujet."""
    rendus = {
        resultat.id
        for resultat in DocumentSearchProvider(moteur).search(
            SearchQuery(query="mil", subject="moussa")
        )
    }

    assert "doc-awa" not in rendus
    assert rendus == {"doc-mil"}


def test_les_documents_retenus_sont_comptes(moteur):
    """
    Une source qui filtre en silence se lit comme une source qui n'a rien
    trouvé. `withheld` distingue les deux.
    """
    fournisseur = DocumentSearchProvider(moteur)
    fournisseur.search(SearchQuery(query="mil", subject="moussa"))

    assert fournisseur.last_method["withheld"] >= 1


def test_le_fournisseur_dit_que_son_classement_est_lexical(moteur):
    """
    Un appelant qui prendrait ce score pour une mesure de sens se tromperait
    exactement le jour où cela compte (ADR-015).
    """
    fournisseur = DocumentSearchProvider(moteur)
    fournisseur.search(SearchQuery(query="mil"))

    assert fournisseur.last_method["method"] == "lexical"
    assert fournisseur.last_method["reason"]


def test_aucun_resume_n_est_fabrique(moteur):
    """
    Un extrait tronqué présenté comme un résumé serait une affirmation que
    personne n'a écrite. Le moteur sait résumer, mais sur demande.
    """
    resultat = DocumentSearchProvider(moteur).search(SearchQuery(query="mil"))[0]

    assert resultat.summary is None
    assert resultat.content.startswith("Le semis du mil")


def test_une_panne_du_moteur_ne_fait_pas_tomber_la_recherche():
    """Même règle que pour les autres fournisseurs : la source ne rend rien."""
    class MoteurEnPanne:
        """Moteur qui lève à chaque recherche."""

        def search_documents(self, query, limit=10):
            """Lève, comme le ferait un moteur cassé."""
            raise RuntimeError("index corrompu")

    assert DocumentSearchProvider(MoteurEnPanne()).search(SearchQuery(query="mil")) == []


# ----------------------------------------------------------------------
# Ce qui n'existera pas, et qui le dit
# ----------------------------------------------------------------------

def test_une_source_sans_fournisseur_est_rapportee_avec_sa_raison(moteur):
    """
    Le cœur de l'aveu : `sources_used` seul laisse croire qu'on a interrogé
    quatre sources et qu'une n'avait rien, alors qu'elle n'a pas été interrogée.
    """
    service = SearchManagerImpl()
    service.register_provider(DocumentSearchProvider(moteur))

    reponse = service.search(SearchQuery(query="mil"))

    assert reponse.sources_used == [SearchSource.DOCUMENT.value]
    assert SearchSource.VISION.value in reponse.sources_unavailable
    assert "rien à chercher" in reponse.sources_unavailable[SearchSource.VISION.value]


def test_la_raison_de_la_vision_dit_que_ce_n_est_pas_le_code_qui_manque():
    """
    La distinction qui évite d'écrire un fournisseur inutile : il n'y a pas de
    texte à indexer, donc il n'y a rien à brancher.
    """
    raison = RAISONS_D_ABSENCE[SearchSource.VISION]

    assert "aucun texte indexé" in raison
    assert "Ce n'est pas un fournisseur qui manque" in raison


def test_la_reponse_serialisee_porte_les_deux_listes(moteur):
    """Un client HTTP doit voir la même chose qu'un appelant Python."""
    service = SearchManagerImpl()
    service.register_provider(DocumentSearchProvider(moteur))

    corps = service.search(SearchQuery(query="mil")).to_dict()

    assert corps["sources_used"] == [SearchSource.DOCUMENT.value]
    assert corps["sources_unavailable"], "L'absence disparaît à la sérialisation"


def test_les_trois_sources_branchees_sont_enregistrees_par_l_api():
    """
    Un fournisseur écrit et jamais enregistré ne sert à rien — c'est le défaut
    que ce travail répare, et il se reproduirait en silence.
    """
    from src.api.server import search_manager

    enregistrees = {source.value for source in search_manager.registered_sources()}

    assert {"knowledge", "memory", "document"} <= enregistrees
    assert "vision" not in enregistrees
