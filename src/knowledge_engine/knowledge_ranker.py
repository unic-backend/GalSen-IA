"""
Classeur de connaissances pour le moteur de connaissances GalSen IA.
"""

from typing import List, Dict, Any
from .types import KnowledgeItem
from .interfaces import KnowledgeRanker
import math
from datetime import datetime, timezone


class KnowledgeRankerImpl(KnowledgeRanker):
    """Implémentation du classeur de connaissances."""

    def rank(self, knowledge_items: List[KnowledgeItem],
             criteria: Dict[str, Any]) -> List[tuple[KnowledgeItem, float]]:
        """
        Classe les connaissances selon des critères donnés.

        Args:
            knowledge_items: Liste des connaissances à classer
            criteria: Dictionnaire de critères et de leurs poids
                     Exemple: {"confidence": 0.4, "recency": 0.3, "length": 0.2, "popularity": 0.1}
                     Les poids doivent sommer à 1.0 (normalisé interne)

        Returns:
            Liste de tuples (connaissance, score) triée par score décroissant
        """
        if not knowledge_items:
            return []

        # Normaliser les poids
        total_weight = sum(criteria.values())
        if total_weight == 0:
            # Si aucun poids, utiliser la confiance par défaut
            weights = {"confidence": 1.0}
        else:
            weights = {k: v / total_weight for k, v in criteria.items()}

        scored_items: List[tuple[KnowledgeItem, float]] = []

        for item in knowledge_items:
            score = 0.0
            breakdown: Dict[str, float] = {}

            # Critère: confiance
            if "confidence" in weights:
                conf_score = item.confidence  # déjà entre 0 et 1
                weighted = conf_score * weights["confidence"]
                score += weighted
                breakdown["confidence"] = weighted

            # Critère: priorité de fiabilité (P1 = plus fiable, meilleur score)
            if "priority" in weights:
                priority_value = item.priority.value if hasattr(item.priority, "value") else int(item.priority)
                # P1 -> 1.0, P2 -> ~0.667, P3 -> ~0.333, P4 -> 0.0
                priority_score = 1.0 - (priority_value - 1) / 3.0
                weighted = priority_score * weights["priority"]
                score += weighted
                breakdown["priority"] = weighted

            # Critère: récence (plus récent = meilleur)
            if "recency" in weights:
                now = datetime.now(timezone.utc)
                age_seconds = (now - item.updated_at).total_seconds()
                # Décroissance exponentielle avec demi-vie de 30 jours
                half_life = 30 * 24 * 3600  # secondes
                recency_score = math.exp(-0.693 * age_seconds / half_life)
                weighted = recency_score * weights["recency"]
                score += weighted
                breakdown["recency"] = weighted

            # Critère: longueur du contenu (ni trop court ni trop courte ni trop longue)
            if "length" in weights:
                length = len(item.content)
                # Fonction de pertinence basée sur la longueur: optimum autour de 500 caractères
                # Utiliser une courbe en cloche centrée à 500 avec écart-type 300
                optimal_len = 500.0
                sigma = 300.0
                length_score = math.exp(-0.5 * ((length - optimal_len) / sigma) ** 2)
                weighted = length_score * weights["length"]
                score += weighted
                breakdown["length"] = weighted

            # Critère: popularité (basée sur le compteur d'accès)
            if "popularity" in weights:
                access_count = item.metadata.get("access_count", 0)
                # Normaliser par un facteur logarithmique pour éviter l'explosion
                # max attendu disons 1000 accès -> log(1001) ≈ 6.9
                popularity_score = min(1.0, math.log(1 + access_count) / math.log(1001))
                weighted = popularity_score * weights["popularity"]
                score += weighted
                breakdown["popularity"] = weighted

            # Critère: personnalisé (fonction fournie dans critères)
            if "custom_fn" in criteria and callable(criteria["custom_fn"]):
                try:
                    custom_score = criteria["custom_fn"](item)
                    # S'assurer que le score est entre 0 et 1
                    custom_score = max(0.0, min(1.0, float(custom_score)))
                    weighted = custom_score * criteria.get("custom_weight", 0.0)
                    score += weighted
                    breakdown["custom"] = weighted
                except Exception:
                    pass  # Ignorer les erreurs de fonction personnalisée

            # S'assurer que le score final est entre 0 et 1 (approximativement)
            # Comme chaque composante est entre 0 et 1 et les poids somment à 1,
            # le score devrait déjà être dans [0,1]
            score = max(0.0, min(1.0, score))
            scored_items.append((item, score))

        # Trier par score décroissant
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return scored_items

    # Méthodes de commodité pour des classements courants
    def rank_by_confidence(self, knowledge_items: List[KnowledgeItem]) -> List[tuple[KnowledgeItem, float]]:
        """Classe les connaissances par confiance décroissante."""
        return sorted([(item, item.confidence) for item in knowledge_items],
                      key=lambda x: x[1], reverse=True)

    def rank_by_recency(self, knowledge_items: List[KnowledgeItem]) -> List[tuple[KnowledgeItem, float]]:
        """Classe les connaissances par date de mise à jour décroissante (plus récent d'abord)."""
        now = datetime.now(timezone.utc)
        def recency_score(item):
            age = (now - item.updated_at).total_seconds()
            half_life = 30 * 24 * 3600  # 30 jours
            return math.exp(-0.693 * age / half_life)
        return sorted([(item, recency_score(item)) for item in knowledge_items],
                      key=lambda x: x[1], reverse=True)

    def rank_by_popularity(self, knowledge_items: List[KnowledgeItem]) -> List[tuple[KnowledgeItem, float]]:
        """Classe les connaissances par popularité (nombre d'accès)."""
        def popularity_score(item):
            count = item.metadata.get("access_count", 0)
            return min(1.0, math.log(1 + count) / math.log(1001))
        return sorted([(item, popularity_score(item)) for item in knowledge_items],
                      key=lambda x: x[1], reverse=True)

    def rank_by_priority(self, knowledge_items: List[KnowledgeItem]) -> List[tuple[KnowledgeItem, float]]:
        """Classe les connaissances par priorité de fiabilité décroissante (P1 d'abord)."""
        def priority_score(item):
            value = item.priority.value if hasattr(item.priority, "value") else int(item.priority)
            return 1.0 - (value - 1) / 3.0
        return sorted([(item, priority_score(item)) for item in knowledge_items],
                      key=lambda x: x[1], reverse=True)

    def rank_balanced(self, knowledge_items: List[KnowledgeItem]) -> List[tuple[KnowledgeItem, float]]:
        """Classement équilibré avec des poids par défaut (priorité intégrée)."""
        default_criteria = {
            "confidence": 0.35,
            "priority": 0.25,
            "recency": 0.2,
            "length": 0.1,
            "popularity": 0.1
        }
        return self.rank(knowledge_items, default_criteria)