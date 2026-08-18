"""
Web Search Tool for GalSen IA.

Provides web search capabilities using multiple search providers with fallback,
caching, rate limiting, and retry mechanisms.
"""

import html
import re
import time
import threading
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from src.tool.base import BaseTool


class RateLimiter:
    """Simple token bucket rate limiter."""

    def __init__(self, rate: float, per: float = 1.0):
        """
        Initialize rate limiter.

        Args:
            rate: Number of requests allowed per `per` seconds.
            per: Time period in seconds.
        """
        self.min_interval = per / rate if rate > 0 else 0.0
        self.last_time = 0.0
        self._lock = threading.Lock()

    def wait(self):
        """Block until the next request is allowed."""
        with self._lock:
            elapsed = time.time() - self.last_time
            wait_time = self.min_interval - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
            self.last_time = time.time()


class TTLCache:
    """Simple in-memory cache with TTL."""

    def __init__(self, ttl_seconds: float = 300.0):
        """
        Initialize cache.

        Args:
            ttl_seconds: Time to live for cache entries in seconds.
        """
        self.ttl = ttl_seconds
        self._cache: Dict[str, tuple[float, Any]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self._lock:
            if key in self._cache:
                expires, value = self._cache[key]
                if time.time() < expires:
                    return value
                else:
                    del self._cache[key]
            return None

    def set(self, key: str, value: Any):
        """Set value in cache with TTL."""
        with self._lock:
            expires = time.time() + self.ttl
            self._cache[key] = (expires, value)

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()


def _parse_duckduckgo_html(html_content: str) -> List[Dict[str, str]]:
    """
    Parse DuckDuckGo HTML search results.

    Args:
        html_content: Raw HTML from DuckDuckGo.

    Returns:
        List of result dictionaries with keys: title, url, snippet.
    """
    results = []
    # Pattern for result containers in DuckDuckGo lite
    # Each result is in a <tr> with class "result"
    # Simplified parsing using regex for demonstration
    # In production, consider using an HTML parser like BeautifulSoup
    pattern = re.compile(
        r'<a[^>]*class="result__url"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>.*?'
        r'<a[^>]*class="result__snippet"[^>]*href="[^"]*"[^>]*>([^<]*)</a>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(html_content):
        url = match.group(1)
        title = html.unescape(match.group(2)).strip()
        snippet = html.unescape(match.group(3)).strip()
        if url and title:
            results.append({"title": title, "url": url, "snippet": snippet})
    # Fallback: look for any links with class "result__url"
    if not results:
        link_pattern = re.compile(
            r'<a[^>]*class="result__url"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>',
            re.IGNORECASE,
        )
        for match in link_pattern.finditer(html_content):
            url = match.group(1)
            title = html.unescape(match.group(2)).strip()
            # Try to find a nearby snippet
            snippet = ""
            # Look for a snippet after the link within a reasonable distance
            start = match.end()
            snippet_match = re.search(
                r'<a[^>]*class="result__snippet"[^>]*>[^<]*</a>',
                html_content[start:start + 500],
                re.IGNORECASE,
            )
            if snippet_match:
                snippet_raw = snippet_match.group(0)
                snippet = re.sub(r"<[^>]+>", "", snippet_raw)
                snippet = html.unescape(snippet).strip()
            results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _enveloppe_de_resultat(resultat: dict) -> dict:
    """
    Ajoute à un résultat de recherche sa forme utilisable dans une invite.

    Un titre et un extrait viennent d'une page que personne n'a relue : ils
    entrent dans la plateforme comme **données externes** (VOLET 36, ch. A.2),
    annoncées avec leur URL. Le résultat lui-même n'est pas réécrit — un outil
    de recherche sert aussi à afficher des liens.
    """
    from src.security.trust import TrustLevel, envelope_fields

    texte = f"{resultat.get('title', '')}\n{resultat.get('snippet', '')}".strip()
    resultat.update(envelope_fields(
        texte, TrustLevel.EXTERNAL, origin=resultat.get("url") or "url inconnue",
    ))
    return resultat


class WebSearchTool(BaseTool):
    """
    Web search tool that provides search capabilities using DuckDuckGo as a fallback
    and supports other providers via configuration.

    The tool supports web, news, image, and video searches.
    """

    def __init__(self, config: dict = None):
        """
        Initialize the web search tool.

        Args:
            config: Configuration dictionary with optional keys:
                - timeout: Request timeout in seconds (default: 10)
                - max_retries: Maximum number of retry attempts (default: 3)
                - backoff_factor: Backoff factor for retries (default: 0.5)
                - rate_limit: Requests per second allowed (default: 1.0)
                - cache_ttl: Cache time-to-live in seconds (default: 300)
                - safe_search: Enable safe search (default: True)
                - region: Region code for results (default: 'wt-wt')
                - lang: Language code (default: 'en')
                - providers: List of provider names to try in order (default: ['duckduckgo'])
        """
        super().__init__(config)
        self.timeout = self.config.get("timeout", 10)
        self.max_retries = self.config.get("max_retries", 3)
        self.backoff_factor = self.config.get("backoff_factor", 0.5)
        self.rate_limiter = RateLimiter(
            rate=self.config.get("rate_limit", 1.0)
        )
        self.cache = TTLCache(ttl_seconds=self.config.get("cache_ttl", 300))
        self.safe_search = self.config.get("safe_search", True)
        self.region = self.config.get("region", "wt-wt")
        self.lang = self.config.get("lang", "en")
        self.providers = self.config.get(
            "providers", ["duckduckgo"]
        )  # Extensible for other providers

        # User-Agent to avoid being blocked
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }

    def _build_url(
        self, query: str, search_type: str = "web", page: int = 1
    ) -> str:
        """
        Build the search URL for DuckDuckGo.

        Args:
            query: Search query string.
            search_type: Type of search ('web', 'news', 'images', 'videos').
            page: Page number (starting at 1).

        Returns:
            URL string for the search request.
        """
        # Map search_type to t parameter value
        t_map = {
            "web": "web",
            "news": "news",
            "images": "images",
            "videos": "videos",
        }
        t_value = t_map.get(search_type, "web")
        params = {
            "q": query,
            "kl": self.region if self.region != "wt-wt" else self.lang,
            "kz": "-1" if self.safe_search else "-2",
            "kp": "-2" if self.safe_search else "-1",
            "kc": "-1",
            "ka": self.region,
            "k1": "-1",
            "p": str(page - 1),  # zero-based page offset
            "t": t_value,        # topic
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        base_url = "https://duckduckgo.com/html/"
        return f"{base_url}?{urlencode(params)}"

    def _fetch_page(self, url: str) -> str:
        """
        Fetch a web page with retry and rate limiting.

        Args:
            url: URL to fetch.

        Returns:
            Page content as string.

        Raises:
            RuntimeError: If the request fails after all retries.
        """
        self.rate_limiter.wait()
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                req = Request(url, headers=self.headers)
                with urlopen(req, timeout=self.timeout) as response:
                    # Try to get charset from headers, default to utf-8
                    charset = (
                        response.headers.get_content_charset()
                        or "utf-8"
                    )
                    return response.read().decode(charset, errors="replace")
            except (URLError, HTTPError, TimeoutError) as e:
                last_error = e
                if attempt < self.max_retries:
                    sleep_time = self.backoff_factor * (2**attempt)
                    time.sleep(sleep_time)
                else:
                    break
        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} retries: {last_error}")

    def _search(
        self, query: str, search_type: str = "web", max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform a search and return results.

        Args:
            query: Search query string.
            search_type: Type of search ('web', 'news', 'images', 'videos').
            max_results: Maximum number of results to return.

        Returns:
            List of result dictionaries.
        """
        # Check cache first
        cache_key = f"{search_type}:{query}:{max_results}:{self.safe_search}:{self.region}:{self.lang}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        all_results = []
        page = 1
        while len(all_results) < max_results:
            url = self._build_url(query, search_type, page)
            try:
                html_content = self._fetch_page(url)
                results = _parse_duckduckgo_html(html_content)
                if not results:
                    break  # No more results
                # Filter duplicates based on URL
                seen_urls = {r["url"] for r in all_results}
                for r in results:
                    if r["url"] not in seen_urls and len(all_results) < max_results:
                        all_results.append(r)
                        seen_urls.add(r["url"])
                if len(results) < 10:  # Assuming fewer than 10 means last page
                    break
                page += 1
            except Exception as e:
                # If we have some results, return them; otherwise raise
                if all_results:
                    break
                else:
                    raise e

        # Trim to requested amount
        final_results = [
            _enveloppe_de_resultat(resultat) for resultat in all_results[:max_results]
        ]
        # Cache the results
        self.cache.set(cache_key, final_results)
        return final_results

    # -----------------------------------------------------------------
    # BaseTool interface implementation
    # -----------------------------------------------------------------
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute the web search tool synchronously.

        Expected arguments:
            query (str): The search query.
            search_type (str, optional): Type of search - 'web', 'news', 'images', 'videos'.
                Defaults to 'web'.
            max_results (int, optional): Maximum number of results to return. Defaults to 10.

        Returns:
            List of dictionaries containing search results.
        """
        if not args:
            raise ValueError("Query argument is required")
        query = args[0]
        search_type = kwargs.get("search_type", "web")
        max_results = kwargs.get("max_results", 10)
        if not isinstance(query, str):
            raise TypeError("Query must be a string")
        if not isinstance(max_results, int) or max_results <= 0:
            raise ValueError("max_results must be a positive integer")
        return self._search(query, search_type, max_results)

    async def async_execute(self, *args, **kwargs) -> Any:
        """
        Execute the web search tool asynchronously.

        This runs the synchronous execute method in a thread pool.
        """
        loop = __import__("asyncio").get_event_loop()
        return await loop.run_in_executor(
            None, self.execute, *args, **kwargs
        )