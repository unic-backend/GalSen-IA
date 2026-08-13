"""
Fournisseurs de recherche (VOLET 14, chapitre 04 — enregistrement des sources).

Le service de recherche unifiée fusionne les résultats de fournisseurs
enregistrés. Le dépôt n'en contenait aucun : `POST /search` ne pouvait donc rien
trouver. Ce module a apporté le premier — la base de connaissances — puis la
mémoire, puis les documents.

**La vision reste sans fournisseur, et c'est une mesure, pas un oubli** : le
moteur visuel analyse une image et n'en produit aucun texte indexé, donc il n'y
a rien à chercher. `SearchManagerImpl` le dit dans sa réponse plutôt que de
laisser un appelant croire qu'il a interrogé quatre sources.

Un fournisseur ne ré-implémente pas la recherche : il adapte le moteur qu'il
enveloppe au contrat du service. Toute règle de lecture reste celle du moteur,
contrôle d'accès compris.
"""

import logging
from typing import Any, List, Optional

from .interfaces import SearchProvider
from .types import SearchQuery, SearchResultItem, SearchSource

logger = logging.getLogger(__name__)

#: Valeur de `metadata["visibility"]` qui rend un document lisible par tous.
#: Tout le reste — y compris l'absence de déclaration — reste privé.
VISIBILITE_PUBLIQUE = "public"


class KnowledgeSearchProvider(SearchProvider):
    """
    Expose le moteur de connaissances au service de recherche unifiée.

    Le rôle porté par la requête est transmis au moteur : une recherche ne donne
    pas plus de droits qu'une lecture directe, et sans rôle seule la
    connaissance publique remonte.
    """

    source = SearchSource.KNOWLEDGE

    def __init__(self, knowledge_manager: Any):
        """
        Args:
            knowledge_manager: le gestionnaire de connaissances à exposer
        """
        self._knowledge_manager = knowledge_manager
        self._logger = logging.getLogger(f"{__name__}.KnowledgeSearchProvider")

    def _to_timestamp(self, valeur) -> Optional[float]:
        """Convertit une date en horodatage, ou None si elle est absente."""
        return valeur.timestamp() if valeur is not None else None

    def search(self, query: SearchQuery) -> List[SearchResultItem]:
        """
        Recherche dans la base de connaissances et adapte les résultats.

        Une panne du moteur ne fait pas tomber la recherche unifiée : elle est
        journalisée et cette source ne rend rien, comme le prévoit le
        gestionnaire pour toute source défaillante.
        """
        # `search_knowledge_with_method` plutôt que `..._with_scores` : le
        # moteur sait chercher par le sens depuis ADR-015, et ce fournisseur
        # appelait encore le chemin lexical — `/search` répondait donc par
        # termes communs **même avec un encodeur installé**.
        self.last_method = {"method": "lexical", "reason": "recherche non exécutée"}
        try:
            trouves, self.last_method = self._knowledge_manager.search_knowledge_with_method(
                query.query, limit=query.limit, role=query.role
            )
        except Exception as error:
            self._logger.warning("Recherche de connaissances impossible : %s", error)
            return []

        resultats: List[SearchResultItem] = []
        for item, score in trouves:
            resultats.append(SearchResultItem(
                id=item.id,
                source=SearchSource.KNOWLEDGE,
                content=item.content,
                score=score,
                title=item.summary,
                summary=item.summary,
                source_detail=item.source.location if item.source else None,
                created_at=self._to_timestamp(item.created_at),
                updated_at=self._to_timestamp(item.updated_at),
                # La classification voyage avec le résultat : sans elle,
                # l'appelant ne sait pas si ce qu'il lit est approuvé.
                metadata={
                    "domain": item.domain.value,
                    "status": item.status.value,
                    "sensitivity": item.sensitivity.value,
                    "confidence": item.confidence,
                    "priority": item.priority.value,
                },
            ))
        return resultats


class MemorySearchProvider(SearchProvider):
    """
    Expose le moteur de mémoire au service de recherche unifiée.

    La mémoire est **possédée**, pas seulement classifiée : chaque élément
    appartient à un sujet (ADR-010), et le critère de sortie C2 dit que les
    données d'un utilisateur sont les siennes. Un rôle ne suffit donc pas ici —
    un administrateur a le droit de lire beaucoup de choses, il n'a pas pour
    autant les souvenirs des autres.

    Sans sujet, ce fournisseur **ne cherche pas**. Il ne rend pas non plus
    « aucun résultat » sans rien dire : la source est absente de
    `sources_used`, ce que `/search/status` et la réponse laissent voir.
    """

    source = SearchSource.MEMORY

    def __init__(self, memory_manager: Any):
        """
        Args:
            memory_manager: le gestionnaire de mémoire à exposer
        """
        self._memory_manager = memory_manager
        self._logger = logging.getLogger(f"{__name__}.MemorySearchProvider")

    def search(self, query: SearchQuery) -> List[SearchResultItem]:
        """
        Recherche dans la mémoire du sujet de la requête.

        Une panne du moteur ne fait pas tomber la recherche unifiée : elle est
        journalisée et cette source ne rend rien.
        """
        if not query.subject:
            self._logger.info(
                "Recherche en mémoire ignorée : aucune requête sans sujet ne peut "
                "désigner des souvenirs, et les rendre tous serait une fuite."
            )
            return []

        self.last_method = {"method": "lexical", "reason": "recherche non exécutée"}
        try:
            trouves, self.last_method = self._memory_manager.search_memory_with_method(
                query.query, user_id=query.subject, limit=query.limit,
            )
        except Exception as error:
            self._logger.warning("Recherche en mémoire impossible : %s", error)
            return []

        resultats: List[SearchResultItem] = []
        for item, score in trouves:
            # Une mémoire dont le contenu n'est pas du texte n'a rien à rendre
            # comme résultat de recherche : le récupérateur l'écarte déjà, ce
            # test protège les appelants qui construiraient la liste autrement.
            if not isinstance(item.content, str):
                continue
            resultats.append(SearchResultItem(
                id=item.id,
                source=SearchSource.MEMORY,
                content=item.content,
                score=score,
                created_at=item.created_at,
                updated_at=item.updated_at,
                metadata={
                    "memory_type": item.memory_type.value,
                    "status": item.status.value,
                    # Le propriétaire n'est pas recopié : l'appelant est le
                    # sujet, le lui répéter n'apprend rien et l'écrire dans une
                    # réponse en fait une donnée de plus à protéger.
                    "tags": list(item.tags),
                },
            ))
        return resultats


class DocumentSearchProvider(SearchProvider):
    """
    Expose le moteur documentaire au service de recherche unifiée.

    Le moteur **indexe déjà** ce qu'il charge (`search_documents`), et le
    backlog affirmait pourtant que cette source « attend que son moteur produise
    du texte cherchable ». C'était vrai pour la vision, faux pour les
    documents : le fournisseur manquait, pas l'index.

    Il ne cherche pas lui-même. L'index documentaire est **lexical** — une
    proportion de termes communs — et `last_method` le dit, parce qu'un
    appelant qui prendrait ce score pour une mesure de sens se tromperait
    exactement le jour où cela compte (ADR-015).

    ## Le moteur documentaire n'a pas de propriétaire, et cela se voit ici

    Brancher cette source a fait échouer un test de propriété : la recherche
    d'Awa remontait un document déposé par quelqu'un d'autre. Le défaut n'est
    pas dans le test — le moteur documentaire est un magasin **de plateforme**,
    sans notion de propriétaire, et `/search` est multi-utilisateur (ADR-010).

    Ce fournisseur applique donc la même règle que la mémoire, en plus strict :
    **un document n'est rendu que s'il se déclare**, soit public
    (`metadata["visibility"] == "public"`), soit possédé par le sujet de la
    requête (`metadata["user_id"]`). Un document qui ne déclare rien **n'est
    pas rendu**, et `last_method["withheld"]` compte ceux qui ont été retenus —
    une source qui filtre en silence laisserait croire qu'elle n'a rien trouvé.
    """

    source = SearchSource.DOCUMENT

    def __init__(self, document_manager: Any):
        """
        Args:
            document_manager: le gestionnaire de documents à exposer
        """
        self._document_manager = document_manager
        self._logger = logging.getLogger(f"{__name__}.DocumentSearchProvider")
        self.last_method = {"method": "lexical", "reason": "recherche non exécutée"}

    @staticmethod
    def _visible(document: Any, query: SearchQuery) -> bool:
        """
        Indique si ce document peut être rendu au sujet de la requête.

        Le défaut est **non** : un magasin sans propriétaire déclaré ne peut pas
        prouver qu'un document appartient à qui le lit, et rendre l'ensemble
        transformerait une recherche personnelle en fuite.
        """
        metadonnees = getattr(document, "metadata", None) or {}
        if str(metadonnees.get("visibility") or "").lower() == VISIBILITE_PUBLIQUE:
            return True
        proprietaire = metadonnees.get("user_id") or metadonnees.get("owner")
        # `subject` est le champ que porte une requête (ADR-010) : il dit **de
        # qui** sont les résultats, là où `role` dit ce que l'appelant peut lire.
        return bool(
            proprietaire and query.subject and str(proprietaire) == str(query.subject)
        )

    def search(self, query: SearchQuery) -> List[SearchResultItem]:
        """
        Recherche dans les documents enregistrés et adapte les résultats.

        Une panne du moteur ne fait pas tomber la recherche unifiée : elle est
        journalisée et cette source ne rend rien — même règle que pour les
        autres fournisseurs.
        """
        self.last_method = {
            "method": "lexical",
            "reason": (
                "L'index documentaire compare des termes ; il ne compare pas des sens."
            ),
            "withheld": 0,
        }
        try:
            trouves = self._document_manager.search_documents(query.query, limit=query.limit)
        except Exception as error:
            self._logger.warning("Recherche documentaire impossible : %s", error)
            return []

        resultats: List[SearchResultItem] = []
        for document, score in trouves:
            if not self._visible(document, query):
                # Compté, pas tu : une source qui filtre en silence se lit
                # comme une source qui n'a rien trouvé.
                self.last_method["withheld"] += 1
                continue
            resultats.append(SearchResultItem(
                id=document.document_id,
                source=SearchSource.DOCUMENT,
                content=document.content,
                score=score,
                title=document.title,
                # Aucun résumé n'est fabriqué ici : le moteur sait résumer sur
                # demande, et un extrait tronqué présenté comme un résumé serait
                # une affirmation que personne n'a écrite.
                summary=None,
                source_detail=document.metadata.get("source"),
                created_at=document.created_at,
                updated_at=document.updated_at,
                metadata={
                    "document_type": getattr(document.document_type, "value", None),
                    "status": getattr(document.status, "value", None),
                    "version": document.version,
                    "chunks": len(document.chunks),
                },
            ))
        return resultats
