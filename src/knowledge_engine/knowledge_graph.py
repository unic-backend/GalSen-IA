"""
Graphe de connaissances pour le moteur de connaissances GalSen IA.
"""

from typing import List
from .interfaces import KnowledgeGraph
import threading


class InMemoryKnowledgeGraph(KnowledgeGraph):
    """Implémentation en mémoire du graphe de connaissances."""

    def __init__(self):
        """Initialise le graphe vide."""
        # adjacency list: node_id -> set of (neighbor_id, relation_type)
        self._adjacency: dict[str, set[tuple[str, str]]] = {}
        # reverse index for quick lookup of incoming edges
        self._reverse_adjacency: dict[str, set[tuple[str, str]]] = {}
        self._lock = threading.RLock()

    def add_node(self, knowledge_id: str) -> None:
        """Ajoute un nœud représentant une connaissance."""
        with self._lock:
            if knowledge_id not in self._adjacency:
                self._adjacency[knowledge_id] = set()
                self._reverse_adjacency[knowledge_id] = set()

    def add_edge(self, source_id: str, target_id: str, relation: str = "related") -> None:
        """Ajoute une arête entre deux connaissances."""
        with self._lock:
            # S'assurer que les nœuds existent
            self.add_node(source_id)
            self.add_node(target_id)
            edge = (target_id, relation)
            self._adjacency[source_id].add(edge)
            # Edge inversé pour les requêtes entrantes
            reverse_edge = (source_id, relation)
            self._reverse_adjacency[target_id].add(reverse_edge)

    def remove_node(self, knowledge_id: str) -> None:
        """Supprime un nœud et toutes ses arêtes."""
        with self._lock:
            if knowledge_id not in self._adjacency:
                return
            # Supprimer toutes les arêtes sortantes
            for target_id, relation in list(self._adjacency[knowledge_id]):
                self._remove_edge(knowledge_id, target_id, relation)
            # Supprimer toutes les arêtes entrantes
            for source_id, relation in list(self._reverse_adjacency[knowledge_id]):
                self._remove_edge(source_id, knowledge_id, relation)
            # Supprimer le nœud lui-même
            del self._adjacency[knowledge_id]
            del self._reverse_adjacency[knowledge_id]

    def _remove_edge(self, source_id: str, target_id: str, relation: str) -> None:
        """Helper pour retirer une arête spécifique."""
        edge = (target_id, relation)
        if edge in self._adjacency.get(source_id, set()):
            self._adjacency[source_id].remove(edge)
        reverse_edge = (source_id, relation)
        if reverse_edge in self._reverse_adjacency.get(target_id, set()):
            self._reverse_adjacency[target_id].remove(edge)

    def remove_edge(self, source_id: str, target_id: str, relation: str = "related") -> bool:
        """Retire une arête spécifique. Retourne True si l'arête existait."""
        with self._lock:
            if source_id not in self._adjacency or target_id not in self._adjacency:
                return False
            edge = (target_id, relation)
            if edge in self._adjacency[source_id]:
                self._adjacency[source_id].remove(edge)
                reverse_edge = (source_id, relation)
                if reverse_edge in self._reverse_adjacency[target_id]:
                    self._reverse_adjacency[target_id].remove(reverse_edge)
                return True
            return False

    def get_neighbors(self, knowledge_id: str) -> List[str]:
        """Retourne les IDs des connaissances voisines (destinations des arêtes sortantes)."""
        with self._lock:
            neighbors = set()
            for neighbor_id, _ in self._adjacency.get(knowledge_id, set()):
                neighbors.add(neighbor_id)
            return list(neighbors)

    def get_relations(self, knowledge_id: str) -> List[tuple[str, str]]:
        """Retourne la liste des (voisin, relation) pour un nœud."""
        with self._lock:
            return list(self._adjacency.get(knowledge_id, set()))

    def get_incoming_edges(self, knowledge_id: str) -> List[tuple[str, str]]:
        """Retourne la liste des (source, relation) des arêtes entrantes."""
        with self._lock:
            return list(self._reverse_adjacency.get(knowledge_id, set()))

    def has_edge(self, source_id: str, target_id: str, relation: str = "related") -> bool:
        """Vérifie si une arête spécifique existe."""
        with self._lock:
            if source_id not in self._adjacency:
                return False
            return (target_id, relation) in self._adjacency[source_id]

    def shortest_path(self, source_id: str, target_id: str) -> List[str]:
        """
        Trouve le plus court chemin entre deux connaissances (en nombre d'arêtes).
        Retourne la liste des IDs incluant la source et la cible.
        Retourne une liste vide si aucun chemin n'existe.
        """
        with self._lock:
            if source_id not in self._adjacency or target_id not in self._adjacency:
                return []

            if source_id == target_id:
                return [source_id]

            # BFS simple
            visited = set([source_id])
            queue = [(source_id, [source_id])]

            while queue:
                current_id, path = queue.pop(0)
                for neighbor_id, _ in self._adjacency.get(current_id, set()):
                    if neighbor_id == target_id:
                        return path + [neighbor_id]
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append((neighbor_id, path + [neighbor_id]))
            return []  # Pas de chemin trouvé

    def get_node_count(self) -> int:
        """Retourne le nombre de nœuds dans le graphe."""
        with self._lock:
            return len(self._adjacency)

    def get_edge_count(self) -> int:
        """Retourne le nombre d'arêtes dans le graphe."""
        with self._lock:
            return sum(len(edges) for edges in self._adjacency.values())

    def clear(self) -> None:
        """Efface complètement le graphe."""
        with self._lock:
            self._adjacency.clear()
            self._reverse_adjacency.clear()