"""
Result Aggregator for the Router Engine.

Collects and combines results from multiple agents.
"""

import logging
from typing import List, Dict, Any


class ResultAggregator:
    """Agrège les résultats des agents exécutés."""

    def __init__(self):
        """Initialise l'agrégateur de résultats."""
        self.logger = logging.getLogger(__name__)

    def aggregate(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Agrège une liste de résultats d'agents en un seul résultat.

        Args:
            results: Liste des dictionnaires de résultat retournés par les agents.

        Returns:
            Dictionnaire contenant le résultat agrégé.
        """
        if not results:
            return {
                "status": "success",
                "aggregated_result": None,
                "agent_results": []
            }

        # Séparer les résultats réussis, les erreurs et les actions en attente
        # d'approbation humaine (ADR-006).
        successful_results = [r for r in results if r.get('status') == 'success']
        error_results = [r for r in results if r.get('status') == 'error']
        approval_results = [r for r in results if r.get('status') == 'requires_approval']

        if len(error_results) > 0:
            # Il y a eu des erreurs
            aggregated = {
                "status": "partial_success" if successful_results else "error",
                "agent_results": results,  # Tous les résultats, y compris les erreurs
                "errors": [r.get('error') for r in error_results if r.get('error')],
                "aggregated_result": self._combine_successful_results(successful_results) if successful_results else None
            }
        elif len(approval_results) > 0:
            # Aucune erreur mais au moins une action en attente d'approbation :
            # la requête ne peut pas être considérée comme terminée.
            approval_request_ids = [
                r.get('approval_request_id') for r in approval_results if r.get('approval_request_id')
            ]
            aggregated = {
                "status": "requires_approval",
                "agent_results": results,
                "approval_request_ids": approval_request_ids,
                "aggregated_result": self._combine_successful_results(successful_results)
            }
        else:
            # Toutes les exécutions ont réussi
            aggregated = {
                "status": "success",
                "agent_results": successful_results,
                "aggregated_result": self._combine_successful_results(successful_results)
            }

        return aggregated

    def _combine_successful_results(self, successful_results: List[Dict[str, Any]]) -> Any:
        """
        Combine les résultats réussis des agents.

        Cette implémentation de base concatène les résultats sous forme de liste.
        Une version plus sophistiquée pourrait effectuer une fusion sémantique.

        Args:
            successful_results: Liste des résultats réussis.

        Returns:
            Résultat combiné (liste des résultats individuels).
        """
        # Pour l'instant, on retourne simplement la liste des champs 'result' de chaque agent
        combined = []
        for res in successful_results:
            # Chaque résultat peut avoir un champ 'result' contenant la sortie réelle de l'agent
            if 'result' in res and res['result'] is not None:
                combined.append(res['result'])
            else:
                # Si il n'y a pas de champ 'result', on ajoute tout le résultat (sauf les métadonnées)
                agent_copy = {k: v for k, v in res.items() if k not in ['agent', 'status']}
                combined.append(agent_copy)

        return combined