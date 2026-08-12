"""
Classeur de réponses pour le moteur de modèles GalSen IA.
"""

from typing import List, Tuple, Any, Optional, Dict
from .types import ModelItem
from .interfaces import ResponseRanker


class WeightedResponseRanker(ResponseRanker):
    """
    Classeur de réponses qui utilise des poids pour combiner plusieurs critères.
    """

    def __init__(self):
        """Initialise le classeur de réponses."""
        # Poids par défaut pour différents critères
        # La somme des poids devrait idéalement être 1.0, mais ce n'est pas strictement requis
        self._default_weights = {
            "relevance": 0.3,
            "accuracy": 0.25,
            "coherence": 0.2,
            "completeness": 0.15,
            "conciseness": 0.1
        }

    def rank_responses(self, model_items: List[ModelItem],
                      responses: List[Any],
                      criteria: Optional[Dict[str, Any]] = None) -> List[Tuple[ModelItem, Any, float]]:
        """
        Classe les réponses selon des critères donnés.

        Args:
            model_items: Liste des modèles qui ont généré les réponses
            responses: Liste des réponses correspondantes
            criteria: Critères de classement optionnels avec des poids

        Returns:
            Liste de tuples (modèle, réponse, score) triée par score décroissant
        """
        if len(model_items) != len(responses):
            raise ValueError("Le nombre de modèles doit correspondre au nombre de réponses")

        if not model_items:
            return []

        # Calculer le score pour chaque paire (modèle, réponse)
        scored_results = []
        for model_item, response in zip(model_items, responses):
            score = self._compute_score(model_item, response, criteria)
            scored_results.append((model_item, response, score))

        # Trier par score décroissant
        scored_results.sort(key=lambda x: x[2], reverse=True)

        return scored_results

    def _compute_score(self, model_item: ModelItem, response: Any,
                      criteria: Optional[Dict[str, Any]] = None) -> float:
        """
        Calcule un score pour une réponse basée sur plusieurs critères.

        Args:
            model_item: Modèle qui a généré la réponse
            response: Réponse à scorer
            criteria: Critères de score optionnels

        Returns:
            Score de la réponse (plus élevé est meilleur)
        """
        # Normaliser la réponse en chaîne pour l'analyse
        if not isinstance(response, str):
            response_str = str(response)
        else:
            response_str = response

        # Calculer les scores pour chaque critère
        scores = {}

        # Pertinence (mesure approximative basée sur la longueur et la présence de mots-clés)
        scores["relevance"] = self._score_relevance(response_str, criteria)

        # Exactitude (dans une implémentation réelle, ceci nécessiterait une vérification des faits)
        # Pour l'instant, nous utilisons une heuristique simple basée sur la présence de marqueurs d'incertitude
        scores["accuracy"] = self._score_accuracy(response_str, criteria)

        # Cohérence (mesure approximative basée sur la structure et la répétition)
        scores["coherence"] = self._score_coherence(response_str, criteria)

        # Complétude (mesure approximative basée sur la longueur relatif à une attente)
        scores["completeness"] = self._score_completeness(response_str, criteria)

        # Concision (inverse de la verbosité excessive)
        scores["conciseness"] = self._score_conciseness(response_str, criteria)

        # Les poids : ceux du critère fourni, sinon ceux par défaut. Ils étaient
        # lus depuis une variable que cette méthode ne définit pas — `weights`
        # existe dans `rank_responses`, pas ici.
        weights = (criteria or {}).get("weights") or self._default_weights

        # Calculer la moyenne pondérée
        total_score = 0.0
        total_weight = 0.0

        for criterion, score in scores.items():
            weight = weights.get(criterion, 0.0)
            if weight > 0:
                total_score += score * weight
                total_weight += weight

        # Éviter la division par zéro
        if total_weight == 0:
            return 0.0

        return total_score / total_weight

    def _score_relevance(self, response: str, criteria: Optional[Dict[str, Any]]) -> float:
        """Score la pertinence de la réponse."""
        # Dans une implémentation réelle, ceci utiliserait des embeddings sémantiques
        # Pour l'instant, nous utilisons une heuristique très basique

        # Vérifier si la réponse est vide
        if not response or not response.strip():
            return 0.0

        # Réponse très courte pourrait être moins pertinente (sauf si spécifiquement demandé)
        length = len(response.strip())
        if length < 10:
            return 0.3
        elif length < 50:
            return 0.6
        elif length < 200:
            return 0.9
        else:
            # Réponses très longues peuvent être trop verbeuses
            return max(0.5, 1.0 - (length - 200) / 1000)

    def _score_accuracy(self, response: str, criteria: Optional[Dict[str, Any]]) -> float:
        """Score l'exactitude de la réponse."""
        # Dans une implémentation réelle, ceci nécessiterait une vérification des faits
        # Pour l'instant, nous pénalisons les réponses avec des marqueurs d'incertitude excessifs

        uncertainty_markers = [
            "je ne sais pas", "i don't know", "peut-être", "maybe", "possibly",
            "peut être", "could be", "i think", "je pense que", "il semble que",
            "it seems", "apparently", "apparemment", "supposedly", "supposément"
        ]

        score = 1.0
        response_lower = response.lower()

        for marker in uncertainty_markers:
            if marker in response_lower:
                score -= 0.1  # Pénaliser chaque marqueur d'incertitude

        # Limiter le score entre 0 et 1
        return max(0.0, min(1.0, score))

    def _score_coherence(self, response: str, criteria: Optional[Dict[str, Any]]) -> float:
        """Score la cohérence de la réponse."""
        # Mesure approximative basée sur la longueur des phrases et la répétition
        if not response or not response.strip():
            return 0.0

        sentences = [s.strip() for s in response.split('.') if s.strip()]
        if not sentences:
            return 0.5

        # Vérifier la longueur moyenne des phrases
        avg_length = sum(len(s) for s in sentences) / len(sentences)
        # Des phrases extrêmement courtes ou longues peuvent indiquer un manque de cohérence
        length_score = 1.0 - min(1.0, abs(avg_length - 20) / 30)  # Idéal autour de 20 caractères

        # Vérifier les répétitions immédiates (à un niveau très basique)
        words = response.split()
        if len(words) > 3:
            immediate_repeats = 0
            for i in range(len(words) - 1):
                if words[i].lower() == words[i+1].lower():
                    immediate_repeats += 1
            repetition_penalty = min(0.5, immediate_repeats * 0.1)
        else:
            repetition_penalty = 0.0

        return max(0.0, min(1.0, length_score * (1.0 - repetition_penalty)))

    def _score_completeness(self, response: str, criteria: Optional[Dict[str, Any]]) -> float:
        """Score la complétude de la réponse."""
        # Dans une implémentation réelle, ceci comparerait la réponse à une réponse attendue
        # Pour l'instant, nous utilisons la longueur comme proxy très approximatif

        if not response or not response.strip():
            return 0.0

        length = len(response.strip())
        # Supposons qu'une réponse complète soit entre 50 et 500 caractères
        if length < 50:
            return length / 50  # Proportionnel à la longueur courte
        elif length <= 500:
            return 1.0  # Longueur adéquate
        else:
            # Trop long pourrait être verbeux mais pas nécessairement incomplet
            return max(0.7, 1.0 - (length - 500) / 1000)

    def _score_conciseness(self, response: str, criteria: Optional[Dict[str, Any]]) -> float:
        """Score la concision de la réponse."""
        # Inverse de la verbosité - préférer les réponses qui vont droit au but
        if not response or not response.strip():
            return 0.0  # Rien à dire n'est pas concis dans ce contexte

        length = len(response.strip())
        # Idéal: pas trop court (pour éviter les réponses non informatives)
        # et pas trop long (éviter la verbosité)
        if length < 10:
            return length / 10  # Trop court
        elif length <= 100:
            return 1.0  # Bonne longueur concise
        elif length <= 300:
            return 1.0 - (length - 100) / 400  # Dégradation linéaire
        else:
            return 0.2  # Très verbeux