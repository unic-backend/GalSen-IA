"""
Exécuteur parallèle pour le moteur de modèles GalSen IA.
"""

from typing import List, Dict, Any, Optional
from .types import ModelItem
from .interfaces import ParallelExecutor
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


class ThreadPoolParallelExecutor(ParallelExecutor):
    """
    Exécuteur parallèle utilisant un pool de threads pour exécuter
    plusieurs modèles simultanément.
    """

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialise l'exécuteur parallèle.

        Args:
            max_workers: Nombre maximal de workers dans le pool (None pour utiliser le nombre de processeurs)
        """
        self._max_workers = max_workers
        self._local = threading.local()

    async def execute_parallel(self, model_items: List[ModelItem],
                              request: Dict[str, Any]) -> List[Any]:
        """
        Exécute une requête sur plusieurs modèles en parallèle.

        Args:
            model_items: Liste des modèles à utiliser
            request: Requête à envoyer aux modèles

        Returns:
            Liste des réponses dans le même ordre que model_items
        """
        loop = asyncio.get_event_loop()

        # Créer une fonction qui exécute une requête sur unese
        async def run_single_model(model_item: ModelItem) -> Any:
            # Dans une implémentation réelle, nous appellerions le modèle ici
            # Pour l'instant, nous simulons l'exécution
            # Nous utilisons run_in_executor pour ne pas bloquer l'événement loop
            return await loop.run_in_executor(
                None,  # Utilise le ThreadPoolExecutor par défaut
                self._execute_single_model,
                model_item,
                request
            )

        # Créer des tâches pour tous les modèles
        tasks = [run_single_model(model) for model in model_items]

        # Attendre que toutes les tâches soient terminées
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Traiter les exceptions - dans une implémentation réelle, nous voudrions peut-être
        # les gérer différemment, mais pour l'instant nous les retournons telles quelles
        return results

    def execute_batch(self, model_items: List[ModelItem],
                     requests: List[Dict[str, Any]]) -> List[Any]:
        """
        Exécute un lot de requêtes sur plusieurs modèles.

        Args:
            model_items: Liste des modèles à utiliser
            requests: Liste des requêtes à envoyer (doit correspondre au nombre de modèles)

        Returns:
            Liste des réponses dans le même ordre que les entrées
        """
        if len(model_items) != len(requests):
            raise ValueError("Le nombre de modèles doit correspondre au nombre de requêtes")

        # Utiliser un ThreadPoolExecutor pour paralléliser l'exécution
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            # Soumettre toutes les tâches
            future_to_index = {
                executor.submit(self._execute_single_model, model, request): i
                for i, (model, request) in enumerate(zip(model_items, requests))
            }

            # Collecter les résultats dans l'ordre original
            results = [None] * len(model_items)
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    results[index] = result
                except Exception as e:
                    # En cas d'erreur, nous stockons l'exception
                    results[index] = e

        return results

    def _execute_single_model(self, model_item: ModelItem,
                             request: Dict[str, Any]) -> Any:
        """
        Exécute une requête sur un seul modèle.

        Args:
            model_item: Modèle à utiliser
            request: Requête à envoyer

        Returns:
            Réponse du modèle
        """
        # Dans une implémentation réelle, nous ferions quelque chose comme:
        # if model_item.provider == "openai":
        #     client = openai.OpenAI(api_key=model_item.metadata.get("api_key"))
        #     response = client.chat.completions.create(
        #         model=model_item.name,
        #         messages=request.get("messages", []),
        #         temperature=request.get("temperature", 0.7),
        #         max_tokens=request.get("max_tokens", 1000)
        #     )
        #     return response.choices[0].message.content
        # elif model_item.provider == "anthropic":
        #     ... etc.

        # Pour l'instant, nous simulons une réponse
        import time
        time.sleep(0.1)  # Simuler un délai de traitement

        return {
            "model_id": model_item.model_id,
            "model_name": model_item.name,
            "response": f"Réponse simulée du modèle {model_item.name}",
            "timestamp": time.time(),
            "request_id": request.get("request_id", "unknown")
        }

    def shutdown(self) -> None:
        """
        Arrête l'exécuteur et libère les ressources.
        """
        # Dans cette implémentation, nous utilisons des context managers
        # donc rien à faire ici, mais nous laissons la méthode pour l'interface
        pass