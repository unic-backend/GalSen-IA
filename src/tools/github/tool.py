"""
GitHub tool for GalSen IA.

Reads repositories, issues and pull requests through the GitHub REST API.

The authentication token is never stored in code or configuration: it is read
from an environment variable at call time. A missing token is not an error — the
API is queried anonymously, with a lower rate limit — so the tool stays usable
in development without ever inviting a secret into the repository.

Only read operations are implemented. Writing to GitHub (opening issues, merging
pull requests) has consequences outside the project and must remain an explicit
human decision.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

logger = logging.getLogger(__name__)


class GitHubTool(BaseTool):
    """
    Outil de consultation de l'API GitHub.

    Opérations : `repository`, `issues`, `issue`, `pull_requests`, `pull_request`,
    `commits`, `search_repositories`, `rate_limit`, `authenticated`.

    Exemple:
        tool.execute("repository", "anthropics/claude-code")
        tool.execute("issues", "anthropics/claude-code", state="open", limit=10)
    """

    API_BASE_URL = "https://api.github.com"

    # Variables d'environnement consultées, dans l'ordre, pour trouver le jeton
    TOKEN_ENVIRONMENT_VARIABLES = ("GITHUB_TOKEN", "GH_TOKEN", "GALSEN_GITHUB_TOKEN")

    DEFAULT_TIMEOUT_SECONDS = 15
    DEFAULT_PAGE_SIZE = 30

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil.

        Args:
            config: Configuration avec les clés optionnelles :
                - `token_env_var`: nom de la variable d'environnement du jeton
                - `timeout`: délai maximum d'une requête
                - `api_base_url`: URL de l'API (pour GitHub Enterprise)
                - `default_repository`: dépôt utilisé quand l'appelant n'en précise pas
                - `user_agent`: en-tête User-Agent envoyé
        """
        super().__init__(config)

        self.timeout = int(self.config.get("timeout", self.DEFAULT_TIMEOUT_SECONDS))
        self.api_base_url = self.config.get("api_base_url", self.API_BASE_URL).rstrip("/")
        self.default_repository = self.config.get("default_repository")
        self.user_agent = self.config.get("user_agent", "GalSenIA-GitHubTool")
        self._token_env_var = self.config.get("token_env_var")

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération GitHub.

        Args:
            *args: L'opération, puis ses arguments éventuels
            **kwargs: Options propres à l'opération

        Returns:
            Résultat de l'opération

        Raises:
            ValueError: Opération inconnue ou dépôt non précisé
        """
        if not args:
            raise ValueError("Une opération est requise (repository, issues, ...)")

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
        return sorted(
            name[len("_op_"):] for name in dir(self)
            if name.startswith("_op_") and callable(getattr(self, name))
        )

    def has_token(self) -> bool:
        """Indique si un jeton d'authentification est disponible dans l'environnement."""
        return self._read_token() is not None

    # ------------------------------------------------------------------
    # Opérations
    # ------------------------------------------------------------------
    def _op_authenticated(self, **kwargs) -> Dict[str, Any]:
        """
        Retourne l'état d'authentification de l'outil.

        Aucune requête réseau n'est faite : cette opération sert à savoir si un
        jeton est configuré avant d'engager des appels soumis à quota.
        """
        variable = self._token_env_var or next(
            (name for name in self.TOKEN_ENVIRONMENT_VARIABLES if os.environ.get(name)),
            None,
        )
        return {
            "authenticated": self.has_token(),
            "token_environment_variable": variable,
            "checked_variables": list(self.TOKEN_ENVIRONMENT_VARIABLES),
        }

    def _op_rate_limit(self, **kwargs) -> Dict[str, Any]:
        """Retourne le quota d'appels restant."""
        payload = self._request("/rate_limit")
        core = payload.get("resources", {}).get("core", {})
        return {
            "limit": core.get("limit"),
            "remaining": core.get("remaining"),
            "reset_at": core.get("reset"),
            "authenticated": self.has_token(),
        }

    def _op_repository(self, repository: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Retourne les informations d'un dépôt."""
        target = self._resolve_repository(repository)
        payload = self._request(f"/repos/{target}")

        return {
            "full_name": payload.get("full_name"),
            "description": payload.get("description"),
            "default_branch": payload.get("default_branch"),
            "language": payload.get("language"),
            "stars": payload.get("stargazers_count"),
            "forks": payload.get("forks_count"),
            "open_issues": payload.get("open_issues_count"),
            "private": payload.get("private"),
            "url": payload.get("html_url"),
            "updated_at": payload.get("updated_at"),
        }

    def _op_issues(self, repository: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """Liste les tickets d'un dépôt."""
        target = self._resolve_repository(repository)
        query = {
            "state": kwargs.get("state", "open"),
            "per_page": min(int(kwargs.get("limit", self.DEFAULT_PAGE_SIZE)), 100),
        }
        if kwargs.get("labels"):
            query["labels"] = kwargs["labels"]

        payload = self._request(f"/repos/{target}/issues", query)

        # L'API GitHub renvoie les pull requests parmi les issues : on les écarte
        return [
            self._summarize_issue(item)
            for item in payload
            if isinstance(item, dict) and "pull_request" not in item
        ]

    def _op_issue(self, repository: str, number: int, **kwargs) -> Dict[str, Any]:
        """Retourne le détail d'un ticket."""
        target = self._resolve_repository(repository)
        payload = self._request(f"/repos/{target}/issues/{int(number)}")

        summary = self._summarize_issue(payload)
        summary["body"] = payload.get("body")
        return summary

    def _op_pull_requests(self, repository: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """Liste les demandes de fusion d'un dépôt."""
        target = self._resolve_repository(repository)
        query = {
            "state": kwargs.get("state", "open"),
            "per_page": min(int(kwargs.get("limit", self.DEFAULT_PAGE_SIZE)), 100),
        }
        payload = self._request(f"/repos/{target}/pulls", query)
        return [self._summarize_pull_request(item) for item in payload if isinstance(item, dict)]

    def _op_pull_request(self, repository: str, number: int, **kwargs) -> Dict[str, Any]:
        """Retourne le détail d'une demande de fusion."""
        target = self._resolve_repository(repository)
        payload = self._request(f"/repos/{target}/pulls/{int(number)}")

        summary = self._summarize_pull_request(payload)
        summary.update({
            "body": payload.get("body"),
            "mergeable": payload.get("mergeable"),
            "additions": payload.get("additions"),
            "deletions": payload.get("deletions"),
            "changed_files": payload.get("changed_files"),
        })
        return summary

    def _op_commits(self, repository: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """Liste les derniers commits d'un dépôt."""
        target = self._resolve_repository(repository)
        query = {"per_page": min(int(kwargs.get("limit", 10)), 100)}
        if kwargs.get("branch"):
            query["sha"] = kwargs["branch"]

        payload = self._request(f"/repos/{target}/commits", query)

        commits: List[Dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            commit = item.get("commit", {})
            commits.append({
                "sha": item.get("sha"),
                "message": commit.get("message", "").splitlines()[0] if commit.get("message") else "",
                "author": commit.get("author", {}).get("name"),
                "date": commit.get("author", {}).get("date"),
                "url": item.get("html_url"),
            })
        return commits

    def _op_search_repositories(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Recherche des dépôts publics."""
        if not query or not str(query).strip():
            raise ValueError("La requête de recherche ne peut pas être vide")

        parameters = {
            "q": query,
            "per_page": min(int(kwargs.get("limit", 10)), 100),
            "sort": kwargs.get("sort", "stars"),
        }
        payload = self._request("/search/repositories", parameters)

        return [
            {
                "full_name": item.get("full_name"),
                "description": item.get("description"),
                "language": item.get("language"),
                "stars": item.get("stargazers_count"),
                "url": item.get("html_url"),
            }
            for item in payload.get("items", [])
        ]

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _summarize_issue(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Réduit un ticket à ses champs utiles."""
        return {
            "number": payload.get("number"),
            "title": payload.get("title"),
            "state": payload.get("state"),
            "author": (payload.get("user") or {}).get("login"),
            "labels": [label.get("name") for label in payload.get("labels", []) if isinstance(label, dict)],
            "comments": payload.get("comments"),
            "created_at": payload.get("created_at"),
            "url": payload.get("html_url"),
        }

    def _summarize_pull_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Réduit une demande de fusion à ses champs utiles."""
        return {
            "number": payload.get("number"),
            "title": payload.get("title"),
            "state": payload.get("state"),
            "author": (payload.get("user") or {}).get("login"),
            "draft": payload.get("draft"),
            "source_branch": (payload.get("head") or {}).get("ref"),
            "target_branch": (payload.get("base") or {}).get("ref"),
            "created_at": payload.get("created_at"),
            "url": payload.get("html_url"),
        }

    def _resolve_repository(self, repository: Optional[str]) -> str:
        """
        Valide et retourne le dépôt visé, au format `propriétaire/nom`.

        Raises:
            ValueError: Si aucun dépôt n'est disponible ou si le format est invalide
        """
        target = repository or self.default_repository
        if not target:
            raise ValueError(
                "Aucun dépôt indiqué. Passez-le en argument ou configurez 'default_repository'."
            )

        if target.count("/") != 1 or not all(part.strip() for part in target.split("/")):
            raise ValueError(f"Dépôt invalide: '{target}'. Format attendu: propriétaire/nom")

        return target

    def _read_token(self) -> Optional[str]:
        """
        Lit le jeton d'authentification dans l'environnement.

        Le jeton n'est jamais conservé en attribut : il est relu à chaque appel,
        de sorte qu'il ne subsiste pas en mémoire après un changement, et qu'il
        n'apparaisse dans aucun état sérialisable de l'outil.
        """
        if self._token_env_var:
            return os.environ.get(self._token_env_var) or None

        for variable in self.TOKEN_ENVIRONMENT_VARIABLES:
            token = os.environ.get(variable)
            if token:
                return token
        return None

    def _request(self, path: str, query: Optional[Dict[str, Any]] = None) -> Any:
        """
        Appelle l'API GitHub et retourne la réponse décodée.

        Args:
            path: Chemin de l'API, commençant par `/`
            query: Paramètres de requête

        Returns:
            Réponse JSON décodée

        Raises:
            RuntimeError: Erreur HTTP ou réseau, avec un message exploitable
        """
        url = f"{self.api_base_url}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": self.user_agent,
        }

        token = self._read_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise RuntimeError(self._describe_http_error(error, url)) from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"Appel GitHub impossible ({url}): {error.reason}") from error
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Réponse GitHub illisible ({url}): {error}") from error

    def _describe_http_error(self, error: urllib.error.HTTPError, url: str) -> str:
        """Transforme une erreur HTTP GitHub en message actionnable."""
        if error.code == 404:
            return f"Ressource GitHub introuvable: {url}"
        if error.code == 401:
            return "Jeton GitHub invalide ou expiré"
        if error.code == 403:
            # Le dépassement de quota se présente comme un 403 : le distinguer
            # évite de faire chercher un problème de droits inexistant
            reset = error.headers.get("X-RateLimit-Reset") if error.headers else None
            if reset:
                wait_seconds = max(0, int(reset) - int(time.time()))
                hint = (
                    "Définissez GITHUB_TOKEN pour un quota plus élevé."
                    if not self.has_token() else ""
                )
                return f"Quota GitHub dépassé, réinitialisation dans {wait_seconds}s. {hint}".strip()
            return f"Accès GitHub refusé: {url}"
        return f"Erreur GitHub {error.code} sur {url}"
