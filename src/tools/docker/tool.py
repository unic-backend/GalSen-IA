"""
Outil Docker pour GalSen IA.

Fournit une interface pour interagir avec Docker (liste des conteneurs,
exécution, arrêt, suppression).
"""

from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

logger = __import__('logging').getLogger(__name__)


class DockerTool(BaseTool):
    """Outil de gestion de conteneurs Docker."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil Docker.

        Args:
            config: Configuration avec les clés optionnelles :
                    Aucune configuration spécifique pour l'instant.
        """
        super().__init__(config)
        self._client = None

    def _get_client(self):
        """Initialise et retourne le client Docker, en levant une erreur si indisponible."""
        if self._client is not None:
            return self._client
        try:
            import docker
            self._client = docker.from_env()
            logger.debug("Client Docker initialisé avec succès.")
        except Exception as e:  # pragma: no cover
            logger.warning(f"Impossible d'initialiser le client Docker : {e}")
            self._client = None
            raise RuntimeError(
                "Le client Docker n'est pas disponible. "
                "Vérifiez que Docker est installé et en cours d'exécution, "
                "et que le package Python 'docker' est installé."
            ) from e
        return self._client

    def _op_list_containers(self, all: bool = False, **kwargs) -> List[Dict[str, Any]]:
        """
        Liste les conteneurs Docker.

        Args:
            all: Si True, liste tous les conteneurs (arrêtés et en cours).
                 Si False, liste uniquement les conteneurs en cours d'exécution.
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Liste de dictionnaires représentant les conteneurs.
        """
        client = self._get_client()
        try:
            containers = client.containers.list(all=all)
            result = []
            for container in containers:
                result.append({
                    "id": container.id,
                    "name": container.name,
                    "status": container.status,
                    "image": ", ".join(container.image.tags) if container.image.tags else "<none>",
                    "ports": container.ports,
                })
            return result
        except Exception as e:  # pragma: no cover
            logger.error(f"Erreur lors de la liste des conteneurs : {e}")
            raise RuntimeError(f"Échec de la liste des conteneurs : {e}")

    def _op_run_container(self, image: str, command: Optional[str] = None,
                          detach: bool = True, **kwargs) -> Dict[str, Any]:
        """
        Exécute un conteneur Docker.

        Args:
            image: Nom de l'image Docker à utiliser (ex: "hello-world").
            command: Commande à exécuter dans le conteneur (optionnel).
            detach: Si True, exécute le conteneur en arrière-plan.
            **kwargs: Options supplémentaires passés à `docker.containers.run`.

        Returns:
            Dictionnaire contenant le statut et l'ID du conteneur créé.
        """
        client = self._get_client()
        try:
            container = client.containers.run(
                image,
                command=command,
                detach=detach,
                **kwargs
            )
            return {
                "status": "success",
                "message": f"Conteneur '{image}' démarré avec succès.",
                "container_id": container.id,
                "container_name": container.name,
            }
        except Exception as e:  # pragma: no cover
            logger.error(f"Erreur lors de l'exécution du conteneur : {e}")
            raise RuntimeError(f"Échec de l'exécution du conteneur : {e}")

    def _op_stop_container(self, container_id: str, **kwargs) -> Dict[str, Any]:
        """
        Arrête un conteneur Docker en cours d'exécution.

        Args:
            container_id: ID ou nom du conteneur à arrêter.
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Dictionnaire contenant le statut de l'arrêt.
        """
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            container.stop()
            return {
                "status": "success",
                "message": f"Conteneur '{container_id}' arrêté avec succès.",
            }
        except Exception as e:  # pragma: no cover
            logger.error(f"Erreur lors de l'arrêt du conteneur : {e}")
            raise RuntimeError(f"Échec de l'arrêt du conteneur : {e}")

    def _op_remove_container(self, container_id: str, force: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Supprime un conteneur Docker.

        Args:
            container_id: ID ou nom du conteneur à supprimer.
            force: Si True, force la suppression même si le conteneur est en cours d'exécution.
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Dictionnaire contenant le statut de la suppression.
        """
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            container.remove(force=force)
            return {
                "status": "success",
                "message": f"Conteneur '{container_id}' supprimé avec succès.",
            }
        except Exception as e:  # pragma: no cover
            logger.error(f"Erreur lors de la suppression du conteneur : {e}")
            raise RuntimeError(f"Échec de la suppression du conteneur : {e}")

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur l'outil Docker.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération.

        Raises:
            ValueError: Opération inconnue.
        """
        if not args:
            raise ValueError("Une opération est requise (list_containers, run_container, "
                             "stop_container, remove_container)")

        operation = str(args[0]).lower()
        operation_args = args[1:]

        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. "
                f"Opérations disponibles: {', '.join(self.available_operations())}"
            )

        return handler(*operation_args, **kwargs)

    def available_operations(self) -> List[str]:
        """Retourne la liste des opérations prises en charge."""
        return ["list_containers", "run_container", "stop_container", "remove_container"]