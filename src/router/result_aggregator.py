"""
Result Aggregator for the Router Engine.

Collects and combines results from multiple agents.

L'agrégation ne filtre plus les résultats qu'elle ne reconnaît pas : elle les
valide (`output_validation`). Trier sur trois statuts alors que quatre sont
déclarés faisait **disparaître** de la réponse tout agent rendant `skipped`, un
statut absent des trois listes, tout en laissant le statut global à `success`.
Le statut global lui-même est calculé par `overall_status()`, la même fonction
que celle du routeur : les deux le déduisaient séparément et ne rendaient pas la
même chose.
"""

import logging
from typing import List, Dict, Any

from .output_validation import (
    EMPTY_PIPELINE_ERROR,
    STATUS_ERROR,
    STATUS_REQUIRES_APPROVAL,
    STATUS_SUCCESS,
    overall_status,
    validated,
)


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
            Dictionnaire contenant le résultat agrégé. `agent_results` porte
            **tous** les résultats, quel que soit leur statut : un agent qui a
            tourné doit apparaître dans la réponse, même — surtout — quand ce
            qu'il a rendu ne respecte pas le contrat.
        """
        if not results:
            # Rien n'a tourné : la requête n'a pas été traitée. Rendre `success`
            # ici déclarait servie toute requête d'une plateforme dont les
            # agents seraient tous désactivés.
            self.logger.warning(EMPTY_PIPELINE_ERROR)
            return {
                "status": STATUS_ERROR,
                "aggregated_result": None,
                "agent_results": [],
                "errors": [EMPTY_PIPELINE_ERROR],
            }

        # Une sortie non conforme devient une erreur qui nomme sa clause, au
        # lieu de sortir silencieusement de l'agrégation.
        checked = [validated(resultat) for resultat in results]
        for original, verifie in zip(results, checked):
            if verifie is not original:
                self.logger.error(
                    "Sortie d'agent rejetée : %s", verifie["error"],
                )

        successful_results = [r for r in checked if r["status"] == STATUS_SUCCESS]
        error_results = [r for r in checked if r["status"] == STATUS_ERROR]
        approval_results = [
            r for r in checked if r["status"] == STATUS_REQUIRES_APPROVAL
        ]

        aggregated: Dict[str, Any] = {
            "status": overall_status(checked),
            "agent_results": checked,
            # Toujours une liste, éventuellement vide : « aucune contribution
            # réussie » et « rien à combiner » se distinguaient auparavant selon
            # la branche, `None` d'un côté et `[]` de l'autre, pour le même fait.
            "aggregated_result": self._combine_successful_results(successful_results),
        }

        if error_results:
            aggregated["errors"] = [
                r.get("error") for r in error_results if r.get("error")
            ]
        if approval_results:
            aggregated["approval_request_ids"] = [
                r["approval_request_id"] for r in approval_results
            ]

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