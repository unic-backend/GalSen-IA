"""
Browser Tool for GalSen IA.

Provides web browsing capabilities to fetch and interact with web pages.
"""

import re
import html
from typing import Any, List
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from src.tool.base import BaseTool


class BrowserTool(BaseTool):
    """Web browser tool for fetching and interacting with web pages."""

    def __init__(self, config: dict = None):
        """
        Initialize the browser tool.

        Args:
            config: Configuration dictionary with optional keys:
                - timeout: Request timeout in seconds (default: 30)
                - max_retries: Maximum number of retry attempts (default: 3)
                - user_agent: User agent string (default: generic browser)
        """
        super().__init__(config)
        self.timeout = self.config.get("timeout", 30)
        self.max_retries = self.config.get("max_retries", 3)
        self.user_agent = self.config.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
        self.headers = {"User-Agent": self.user_agent}

    def _fetch_page(self, url: str) -> str:
        """
        Fetch a web page with retry logic.

        Args:
            url: URL to fetch

        Returns:
            Page content as string

        Raises:
            RuntimeError: If the request fails after all retries
        """
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                req = Request(url, headers=self.headers)
                with urlopen(req, timeout=self.timeout) as response:
                    # Try to get charset from headers, default to utf-8
                    charset = (
                        response.headers.get_content_charset() or "utf-8"
                    )
                    return response.read().decode(charset, errors="replace")
            except (URLError, HTTPError, TimeoutError) as e:
                last_error = e
                if attempt < self.max_retries:
                    # Simple exponential backoff
                    import time

                    time.sleep(2**attempt)
                else:
                    break
        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} retries: {last_error}")

    def _extract_text(self, html_content: str) -> str:
        """
        Extract readable text from HTML content.

        Args:
            html_content: Raw HTML content

        Returns:
            Cleaned text content
        """
        # Remove script and style elements
        cleaned = re.sub(r"<script\b[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<style\b[^>]*>.*?</style>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", cleaned)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Decode HTML entities
        return html.unescape(text)

    def _extract_links(self, html_content: str, base_url: str) -> List[dict]:
        """
        Extract links from HTML content.

        Args:
            html_content: Raw HTML content
            base_url: Base URL for resolving relative links

        Returns:
            List of dictionaries with 'text' and 'url' keys
        """
        links = []
        # Find all anchor tags with href attributes
        pattern = re.compile(
            r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )

        for match in pattern.finditer(html_content):
            href = match.group(1).strip()
            link_text = self._extract_text(match.group(2))

            # Skip empty links or javascript:/data: URLs
            if not href or href.startswith(("javascript:", "data:", "#")):
                continue

            # Resolve relative URLs
            absolute_url = urljoin(base_url, href)

            links.append({"text": link_text, "url": absolute_url})

        return links

    def _extract_title(self, html_content: str) -> str:
        """
        Extract the title from HTML content.

        Args:
            html_content: Raw HTML content

        Returns:
            Page title or empty string if not found
        """
        # Look for title tag
        title_match = re.search(
            r"<title\b[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL
        )
        if title_match:
            return self._extract_text(title_match.group(1)).strip()
        return ""

    def execute(self, operation: str, *args, **kwargs) -> Any:
        """
        Execute a browser operation.

        Args:
            operation: The operation to perform ('visit', 'get_text', 'get_links', etc.)
            *args: Positional arguments for the operation
            **kwargs: Keyword arguments for the operation

        Returns:
            The result of the operation

        Raises:
            ValueError: If the operation is not supported
        """
        operation = operation.lower()

        if operation == "visit":
            return self.visit(*args, **kwargs)
        elif operation == "get_text":
            return self.get_text(*args, **kwargs)
        elif operation == "get_links":
            return self.get_links(*args, **kwargs)
        elif operation == "get_title":
            return self.get_title(*args, **kwargs)
        else:
            raise ValueError(
                f"Unsupported operation: {operation}. "
                f"Available operations: {', '.join(self.available_operations())}"
            )

    def available_operations(self) -> List[str]:
        """Retourne la liste des opérations prises en charge."""
        # Le dispatch se fait par nom explicite (pas de convention `_op_`),
        # la liste est donc déclarée ici et doit suivre le dispatch d'execute().
        return ["get_links", "get_text", "get_title", "visit"]

    def visit(self, url: str) -> dict:
        """
        Visit a web page and return basic information.

        Args:
            url: URL to visit

        Returns:
            Dictionary containing:
                - url: The visited URL
                - title: Page title
                - text: Extracted text content
                - links: List of links found on the page
                - status: Success status
        """
        try:
            html_content = self._fetch_page(url)
            title = self._extract_title(html_content)
            text = self._extract_text(html_content)
            links = self._extract_links(html_content, url)

            from src.security.trust import TrustLevel, envelope_fields

            resultat = {
                "url": url,
                "title": title,
                "text": text,
                "links": links,
                "status": "success",
            }
            # Une page web est du texte que personne n'a relu : elle entre comme
            # donnée externe, annoncée avec son URL (VOLET 36, ch. A.2). `text`
            # reste brut — l'outil sert aussi à extraire, pas seulement à
            # nourrir une invite.
            resultat.update(envelope_fields(
                f"{title}\n{text}", TrustLevel.EXTERNAL, origin=url,
            ))
            return resultat
        except Exception as e:
            return {
                "url": url,
                "error": str(e),
                "status": "error",
            }

    def get_text(self, url: str) -> str:
        """
        Get the text content of a web page.

        Args:
            url: URL to fetch

        Returns:
            Text content of the page
        """
        result = self.visit(url)
        if result["status"] == "error":
            raise RuntimeError(f"Failed to fetch {url}: {result.get('error', 'Unknown error')}")
        return result["text"]

    def get_links(self, url: str) -> list:
        """
        Get all links from a web page.

        Args:
            url: URL to fetch

        Returns:
            List of link dictionaries with 'text' and 'url' keys
        """
        result = self.visit(url)
        if result["status"] == "error":
            raise RuntimeError(f"Failed to fetch {url}: {result.get('error', 'Unknown error')}")
        return result["links"]

    def get_title(self, url: str) -> str:
        """
        Get the title of a web page.

        Args:
            url: URL to fetch

        Returns:
            Page title
        """
        result = self.visit(url)
        if result["status"] == "error":
            raise RuntimeError(f"Failed to fetch {url}: {result.get('error', 'Unknown error')}")
        return result["title"]