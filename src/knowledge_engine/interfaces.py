"""
Interfaces pour le moteur de connaissances GalSen IA.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Iterable
from .types import KnowledgeItem, KnowledgeSource, KnowledgePriority, KnowledgeStatus


class KnowledgeStore(ABC):
    """Interface pour le stockage des connaissances."""

    @abstractmethod
    def save(self, knowledge: KnowledgeItem) -> str:
        """Sauvegarde une connaissance et retourne son ID."""
        pass

    @abstractmethod
    def get(self, knowledge_id: str) -> Optional[KnowledgeItem]:
        """Récupère une connaissance par son ID."""
        pass

    @abstractmethod
    def update(self, knowledge: KnowledgeItem) -> bool:
        """Met à jour une connaissance existante."""
        pass

    @abstractmethod
    def delete(self, knowledge_id: str) -> bool:
        """Supprime une connaissance."""
        pass

    @abstractmethod
    def list_items(self, limit: int = 100, **filters) -> List[KnowledgeItem]:
        """Liste les connaissances avec filtres optionnels."""
        pass

    @abstractmethod
    def count(self, **filters) -> int:
        """Compte les connaissances correspondant aux filtres."""
        pass

    @abstractmethod
    def cleanup_old_versions(self, keep_latest: int = 1) -> int:
        """Nettoie les anciennes versions, en gardant seulement les plus récentes."""
        pass

    @abstractmethod
    def record_access(self, knowledge_id: str) -> int:
        """Compte une consultation et retourne le nouveau total.

        Une méthode dédiée plutôt qu'un `update()` : consulter une connaissance
        n'en produit pas une nouvelle version, et `update()` refuse à juste
        titre une écriture dont la version n'a pas avancé. Le compteur passait
        par là et ne s'incrémentait donc jamais ailleurs que par le partage de
        référence du magasin en mémoire — c'est-à-dire nulle part sur SQLite.

        Returns:
            Le nombre de consultations après incrément, ou 0 si la connaissance
            n'existe pas.
        """
        pass


class KnowledgeLoader(ABC):
    """Interface pour le chargement de connaissances depuis diverses sources."""

    @abstractmethod
    def load_from_source(self, source: KnowledgeSource) -> List[KnowledgeItem]:
        """Charge des connaissances depuis une source spécifiée."""
        pass

    @abstractmethod
    def supports_type(self, content_type: str) -> bool:
        """Vérifie si ce chargeur supporte un type de contenu."""
        pass


class KnowledgeIndexer(ABC):
    """Interface pour l'indexation des connaissances pour la recherche."""

    @abstractmethod
    def add_to_index(self, knowledge: KnowledgeItem) -> None:
        """Ajoute une connaissance à l'index."""
        pass

    @abstractmethod
    def remove_from_index(self, knowledge_id: str) -> None:
        """Retire une connaissance de l'index."""
        pass

    @abstractmethod
    def update_index(self, knowledge: KnowledgeItem) -> None:
        """Met à jour l'index pour une connaissance modifiée."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[tuple[KnowledgeItem, float]]:
        """Recherche dans l'index, retourne liste de (connaissance, score)."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Vide l'index."""
        pass


class KnowledgeRetriever(ABC):
    """Interface pour la récupération de connaissances (RAG)."""

    @abstractmethod
    def retrieve_relevant(self, query: str, knowledge_items: List[KnowledgeItem],
                          limit: int = 5) -> List[tuple[KnowledgeItem, float]]:
        """Récupère les connaissances les plus pertinentes pour une requête."""
        pass

    @abstractmethod
    def retrieve_by_ids(self, knowledge_ids: List[str]) -> List[KnowledgeItem]:
        """Récupère des connaissances par leurs IDs."""
        pass


class KnowledgeValidator(ABC):
    """Interface pour la validation des connaissances."""

    @abstractmethod
    def validate(self, knowledge: KnowledgeItem) -> tuple[bool, List[str]]:
        """Valide une connaissance. Retourne (est_valide, liste_des_erreurs)."""
        pass

    @abstractmethod
    def check_consistency(self, knowledge: KnowledgeItem,
                          existing: List[KnowledgeItem]) -> List[str]:
        """Vérifie la cohérence avec les connaissances existantes."""
        pass


class KnowledgeGraph(ABC):
    """Interface pour le graphe de connaissances."""

    @abstractmethod
    def add_node(self, knowledge_id: str) -> None:
        """Ajoute un nœud représentant une connaissance."""
        pass

    @abstractmethod
    def add_edge(self, source_id: str, target_id: str, relation: str) -> None:
        """Ajoute une arête entre deux connaissances."""
        pass

    @abstractmethod
    def remove_node(self, knowledge_id: str) -> None:
        """Supprime un nœud."""
        pass

    @abstractmethod
    def get_neighbors(self, knowledge_id: str) -> List[str]:
        """Retourne les IDs des connaissances voisines."""
        pass

    @abstractmethod
    def get_relations(self, knowledge_id: str) -> List[tuple[str, str]]:
        """Retourne la liste des (voisin, relation) pour un nœud."""
        pass

    @abstractmethod
    def shortest_path(self, source_id: str, target_id: str) -> List[str]:
        """Trouve le plus court chemin entre deux connaissances."""
        pass


class KnowledgeCache(ABC):
    """Interface pour le cache de connaissances fréquemment utilisées."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Récupère une valeur du cache."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Stocke une valeur dans le cache avec une durée de vie optionnelle."""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Supprime une clé du cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Vide le cache."""
        pass


class KnowledgeRanker(ABC):
    """Interface pour le classement des connaissances."""

    @abstractmethod
    def rank(self, knowledge_items: List[KnowledgeItem],
             criteria: Dict[str, Any]) -> List[tuple[KnowledgeItem, float]]:
        """Classe les connaissances selon des critères donnés."""
        pass

    @abstractmethod
    def rank_by_priority(self, knowledge_items: List[KnowledgeItem]) -> List[tuple[KnowledgeItem, float]]:
        """Classe les connaissances par priorité de fiabilité décroissante (P1 d'abord)."""
        pass


class KnowledgeManager(ABC):
    """Interface principale du gestionnaire de connaissances."""

    @abstractmethod
    def add_knowledge(self, knowledge: KnowledgeItem) -> str:
        """Ajoute une connaissance à la base."""
        pass

    @abstractmethod
    def get_knowledge(self, knowledge_id: str) -> Optional[KnowledgeItem]:
        """Récupère une connaissance par son ID."""
        pass

    @abstractmethod
    def update_knowledge(self, knowledge: KnowledgeItem) -> bool:
        """Met à jour une connaissance."""
        pass

    @abstractmethod
    def delete_knowledge(self, knowledge_id: str) -> bool:
        """Supprime une connaissance."""
        pass

    @abstractmethod
    def search_knowledge(self, query: str, limit: int = 10,
                         role: Optional[str] = None) -> List[KnowledgeItem]:
        """Recherche des connaissances par texte.

        `role` filtre par sensibilité (chapitre 07) : sans rôle, seules les
        connaissances publiques sont retournées.
        """
        pass

    @abstractmethod
    def search_knowledge_with_scores(
        self, query: str, limit: int = 10, role: Optional[str] = None
    ) -> List[Tuple[KnowledgeItem, float]]:
        """
        Recherche des connaissances en conservant leur score de pertinence.

        L'indexeur calcule un score réel (proportion des termes de la requête
        présents dans le document) ; `search_knowledge` le jette. Un appelant qui
        doit classer ou filtrer par pertinence a besoin de ce score, et
        l'inventer à partir du rang produirait un classement faux.

        Returns:
            Les couples (connaissance, score), du plus pertinent au moins pertinent.
        """
        pass

    @abstractmethod
    def retrieve_for_prompt(self, prompt: str, max_items: int = 5,
                            statuses: Optional[Iterable[KnowledgeStatus]] = None,
                            role: Optional[str] = None) -> List[KnowledgeItem]:
        """Récupère des connaissances pertinentes pour enrichir un prompt (RAG).

        `statuses` restreint les statuts acceptés ; par défaut, les connaissances
        retirées de l'usage (archivées, dépréciées) sont écartées.
        """
        pass

    @abstractmethod
    def retrieve_reliable(self, prompt: str, max_items: int = 5,
                          min_priority: Optional[KnowledgePriority] = None,
                          min_confidence: float = 0.5,
                          statuses: Optional[Iterable[KnowledgeStatus]] = None,
                          role: Optional[str] = None) -> Dict[str, Any]:
        """Récupère uniquement des connaissances fiables.

        Si aucune connaissance ne satisfait les seuils de priorité et de
        confiance, retourne un résultat indiquant que GalSen IA doit
        préférer dire « Je ne sais pas » plutôt que de générer une
        information trompeuse (chapitre 04 de la Constitution).
        """
        pass

    @abstractmethod
    def get_related(self, knowledge_id: str) -> List[KnowledgeItem]:
        """Récupère les connaissances liées."""
        pass

    @abstractmethod
    def validate_knowledge(self, knowledge: KnowledgeItem) -> tuple[bool, List[str]]:
        """Valide une connaissance avant ajout/mise à jour."""
        pass

    @abstractmethod
    def load_from_source(self, source: KnowledgeSource) -> List[str]:
        """Charge des connaissances depuis une source externe."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Retourne des statistiques sur la base de connaissances."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Nettoie les ressources."""
        pass