"""
Memory Ranker for GalSen IA.

Simple ranker based on priority, recency, and status.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from .types import MemoryItem
from .interfaces import MemoryRanker


class SimpleMemoryRanker(MemoryRanker):
    """Simple ranker based on priority, recency, and status."""

    def __init__(self):
        """Initialize the ranker with weights."""
        # Weights for the different factors (must sum to 1.0)
        self._priority_weight = 0.4
        self._recency_weight = 0.4
        self._status_weight = 0.2

    def rank(self,
             items: List[MemoryItem],
             context: Optional[Dict[str, Any]] = None) -> List[Tuple[MemoryItem, float]]:
        """
        Rank a list of memory items.

        Args:
            items: List of memory items to rank.
            context: Optional context (e.g., current query, user intent) to influence ranking.

        Returns:
            List of tuples (memory_item, score) sorted by score descending.
        """
        scored_items = []
        for item in items:
            score = self.compute_score(item, context)
            scored_items.append((item, score))
        # Sort by score descending
        sorted_items = sorted(scored_items, key=lambda x: x[1], reverse=True)
        return sorted_items

    def compute_score(self,
                      item: MemoryItem,
                      context: Optional[Dict[str, Any]] = None) -> float:
        """
        Compute a score for a single memory item.

        Args:
            item: The memory item to score.
            context: Optional context to influence scoring.

        Returns:
            A score between 0.0 and 1.0.
        """
        # Normalize priority to 0-1 (Priority has values 0,1,2,3)
        p = item.priority.value
        priority_score = p / 3.0  # 3 is the max value

        # Recency score: newer is better
        now = time.time()
        age_in_seconds = now - item.created_at
        # We consider items from the last 30 days as fresh (score 1.0)
        # and older than 90 days as stale (score 0.0)
        max_age = 30 * 24 * 3600  # 30 days in seconds
        old_age = 90 * 24 * 3600  # 90 days in seconds
        if age_in_seconds < 0:
            # Future timestamp, treat as very recent
            recency_score = 1.0
        elif age_in_seconds > old_age:
            recency_score = 0.0
        else:
            # Linear decay between 30 and 90 days
            if age_in_seconds <= max_age:
                recency_score = 1.0
            else:
                # Scale from 1.0 at 30 days to 0.0 at 90 days
                recency_score = max(0.0, 1.0 - ( (age_in_seconds - max_age) / (old_age - max_age) ))

        # Status score
        status_scores = {
            'active': 1.0,
            'archived': 0.5,
            'deleted': 0.0,
            'expired': 0.0
        }
        status_score = status_scores.get(item.status.value, 0.0)

        # Weighted sum
        score = (
            self._priority_weight * priority_score +
            self._recency_weight * recency_score +
            self._status_weight * status_score
        )
        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))