"""
Outil API pour GalSen IA.

Fournit des capacités de client HTTP pour effectuer des appels d'API REST.
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List, Optional, Union
from src.tool.base import BaseTool


class APITool(BaseTool):
    """Outil client HTTP pour effectuer des appels d'API REST."""

    def __init__(self, config: dict = None):
        """
        Initialiser l'outil API.

        Args:
            config: Dictionnaire de configuration avec les clésoptionnelles :
                - timeout : Délai d'attente de la requête en secondes (défaut : 30)
                - user_agent : Chaîne d'utilisateur-agent (défaut : GalSen IA API Tool/1.0)
                - max_retries : Nombre maximal de tentatives de nouvelle tentative (défaut : 3)
        """
        super().__init__(config)
        self.timeout = self.config.get("timeout", 30)
        self.user_agent = self.config.get(
            "user_agent", "GalSen IA API Tool/1.0"
        )
        self.max_retries = self.config.get("max_retries", 3)
        self.headers = {"User-Agent": self.user_agent}

    def _prepare_request(
        self,
        url: str,
        method: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
    ) -> urllib.request.Request:
        """
        Préparer une requête HTTP.

        Args:
            url: URL cible
            method: Méthode HTTP (GET, POST, PUT, DELETE, etc.)
            headers: En-têtes supplémentaires à inclure
            data: Données du corps de la requête (pour POST/PUT)

        Returns:
            Objet Request préparé
        """
        # Préparer les en-têtes
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        # Préparer les données
        data_bytes = None
        if data is not None:
            if isinstance(data, dict):
                # Convertir le dictionnaire en JSON
                data_bytes = json.dumps(data).encode("utf-8")
                # Définir Content-Type s'il n'est pas déjà défini
                if "Content-Type" not in request_headers:
                    request_headers["Content-Type"] = "application/json"
            elif isinstance(data, str):
                data_bytes = data.encode("utf-8")
            else:
                data_bytes = str(data).encode("utf-8")

        # Créer la requête
        request = urllib.request.Request(
            url, data=data_bytes, headers=request_headers, method=method
        )
        return request

    def _fetch_url(
        self, request: urllib.request.Request
    ) -> tuple[int, dict, bytes]:
        """
        Récupérer une URL avec logique de nouvelle tentative.

        Args:
            request: Objet Request préparé

        Returns:
            Tuple (code_status, en-têtes, corps_de_la_réponse)

        Raises:
            RuntimeError: Si la requête échoue après toutes les tentatives
        """
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout
                ) as response:
                    headers = dict(response.getheaders())
                    body = response.read()
                    return response.status, headers, body
            except urllib.error.HTTPError as e:
                # Pour les erreurs HTTP, nous retournons toujours les détails de la réponse
                # mais nous ne réessayons pas sur les erreurs client (4xx) ou serveur (5xx)
                # sauf s'il s'agit d'une erreur temporaire du serveur
                if 400 <= e.code < 500 or e.code in [500, 502, 503, 504]:
                    if attempt < self.max_retries and e.code in [
                        502,
                        503,
                        504,
                    ]:  # Réessayer uniquement sur les erreurs de serveur spécifiques
                        import time

                        time.sleep(2**attempt)  # Backoff exponentiel
                        last_error = e
                        continue
                return e.code, dict(e.headers), e.read()
            except urllib.error.URLError as e:
                last_error = e
                if attempt < self.max_retries:
                    import time

                    time.sleep(2**attempt)  # Backoff exponentiel
                else:
                    break
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    import time

                    time.sleep(2**attempt)  # Backoff exponentiel
                else:
                    break

        raise RuntimeError(
            f"Échec de la récupération de {request.full_url} après {self.max_retries} tentatives : {last_error}"
        )

    def execute(
        self,
        operation: str,
        *args,
        **kwargs,
    ) -> Any:
        """
        Exécuter une opération API.

        Args:
            operation: L'opération à effectuer ('get', 'post', 'put', 'delete', 'patch', 'request')
            *args: Arguments positionnels (URL pour la plupart des opérations)
            **kwargs: Arguments nommés (en-têtes, données, json, etc.)

        Returns:
            Dictionnaire contenant les informations de réponse :
                - status : Code de statut HTTP
                - headers : En-têtes de réponse
                - body : Corps de la réponse (décodé si possible)
                - json : JSON analysé si applicable
                - text : Représentation textuelle du corps

        Raises:
            ValueError: Si l'opération n'est pas soutenue
        """
        operation = operation.lower()

        if operation == "get":
            return self.get(*args, **kwargs)
        elif operation == "post":
            return self.post(*args, **kwargs)
        elif operation == "put":
            return self.put(*args, **kwargs)
        elif operation == "delete":
            return self.delete(*args, **kwargs)
        elif operation == "patch":
            return self.patch(*args, **kwargs)
        elif operation == "request":
            return self.request(*args, **kwargs)
        else:
            raise ValueError(
                f"Opération non prise en charge : {operation}. "
                f"Opérations disponibles : {', '.join(self.available_operations())}"
            )

    def available_operations(self) -> List[str]:
        """Retourne la liste des opérations prises en charge."""
        # Le dispatch se fait par nom explicite (pas de convention `_op_`),
        # la liste est donc déclarée ici et doit suivre le dispatch d'execute().
        return ["delete", "get", "patch", "post", "put", "request"]

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Effectuer une requête GET.

        Args:
            url: URL cible
            headers: En-têtes supplémentaires à inclure
            **kwargs: Options supplémentaires

        Returns:
            Dictionnaire de réponse
        """
        request = self._prepare_request(url, "GET", headers, None)
        status, headers, body = self._fetch_url(request)
        return self._process_response(status, headers, body)

    def post(
        self,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Effectuer une requête POST.

        Args:
            url: URL cible
            data: Données du corps de la requête (données de formulaire ou chaîne brute)
            json: Données JSON à envoyer (mutuellement exclusives avec data)
            headers: En-têtes supplémentaires à inclure
            **kwargs: Options supplémentaires

        Returns:
            Dictionnaire de réponse
        """
        # Gérer le paramètre json
        if json is not None:
            if data is not None:
                raise ValueError("Impossible de spécifier à la fois 'data' et 'json' paramètres")
            data = json
            if headers is None:
                headers = {}
            headers["Content-Type"] = "application/json"

        request = self._prepare_request(url, "POST", headers, data)
        status, headers, body = self._fetch_url(request)
        return self._process_response(status, headers, body)

    def put(
        self,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Effectuer une requête PUT.

        Args:
            url: URL cible
            data: Données du corps de la requête (données de formulaire ou chaîne brute)
            json: Données JSON à envoyer (mutuellement exclusives avec data)
            headers: En-têtes supplémentaires à inclure
            **kwargs: Options supplémentaires

        Returns:
            Dictionnaire de réponse
        """
        # Gérer le paramètre json
        if json is not None:
            if data is not None:
                raise ValueError("Impossible de spécifier à la fois 'data' et 'json' paramètres")
            data = json
            if headers is None:
                headers = {}
            headers["Content-Type"] = "application/json"

        request = self._prepare_request(url, "PUT", headers, data)
        status, headers, body = self._fetch_url(request)
        return self._process_response(status, headers, body)

    def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Effectuer une requête DELETE.

        Args:
            url: URL cible
            headers: En-têtes supplémentaires à inclure
            **kwargs: Options supplémentaires

        Returns:
            Dictionnaire de réponse
        """
        request = self._prepare_request(url, "DELETE", headers, None)
        status, headers, body = self._fetch_url(request)
        return self._process_response(status, headers, body)

    def patch(
        self,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Effectuer une requête PATCH.

        Args:
            url: URL cible
            data: Données du corps de la requête (données de formulaire ou chaîne brute)
            json: Données JSON à envoyer (mutuellement exclusives avec data)
            headers: En-têtes supplémentaires à inclure
            **kwargs: Options supplémentaires

        Returns:
            Dictionnaire de réponse
        """
        # Gérer le paramètre json
        if json is not None:
            if data is not None:
                raise ValueError("Impossible de spécifier à la fois 'data' et 'json' paramètres")
            data = json
            if headers is None:
                headers = {}
            headers["Content-Type"] = "application/json"

        request = self._prepare_request(url, "PATCH", headers, data)
        status, headers, body = self._fetch_url(request)
        return self._process_response(status, headers, body)

    def request(
        self,
        method: str,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Effectuer une requête HTTP personnalisée.

        Args:
            method: Méthode HTTP (GET, POST, PUT, DELETE, PATCH, etc.)
            url: URL cible
            data: Données du corps de la requête (données de formulaire ou chaîne brute)
            json: Données JSON à envoyer (mutuellement exclusives avec data)
            headers: En-têtes supplémentaires à inclure
            **kwargs: Options supplémentaires

        Returns:
            Dictionnaire de réponse
        """
        # Gérer le paramètre json
        if json is not None:
            if data is not None:
                raise ValueError("Impossible de spécifier à la fois 'data' et 'json' paramètres")
            data = json
            if headers is None:
                headers = {}
            headers["Content-Type"] = "application/json"

        request = self._prepare_request(
            method.upper(), url, headers, data
        )  # Note : method.upper() pour la cohérence
        status, headers, body = self._fetch_url(request)
        return self._process_response(status, headers, body)

    def _process_response(
        self, status: int, headers: Dict[str, str], body: bytes
    ) -> Dict[str, Any]:
        """
        Traiter la réponse HTTP dans un format standardisé.

        Args:
            status: Code de statut HTTP
            headers: En-têtes de réponse
            body: Corps de la réponse sous forme d'octets

        Returns:
            Dictionnaire de réponse traité
        """
        # Essayer de décoder le corps en texte UTF-8
        text_body = ""
        try:
            text_body = body.decode("utf-8")
        except UnicodeDecodeError:
            # Si nous ne pouvons pas décoder en UTF-8, laisser une chaîne vide
            # Les données binaires peuvent être accessibles via le champ 'body'
            pass

        # Essayer d'analyser le JSON si le Content-Type indique du JSON
        json_data = None
        content_type = headers.get("Content-Type", "").lower()
        if "application/json" in content_type and text_body:
            try:
                json_data = json.loads(text_body)
            except (json.JSONDecodeError, TypeError):
                # Si l'analyse JSON échoue, laisser json_data à None
                pass

        return {
            "status": status,
            "headers": headers,
            "body": body,
            "text": text_body,
            "json": json_data,
        }