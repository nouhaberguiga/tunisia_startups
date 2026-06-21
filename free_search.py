"""
free_search.py
--------------
Recherche web gratuite sans cle API.

Le projet utilise DuckDuckGo HTML comme solution de secours quand Tavily
est indisponible, sans cle, ou hors quota. Les resultats retournent la
meme forme que Tavily: {title, url, content}.
"""

from __future__ import annotations

from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

import config
from cache_store import get_cached, set_cached


DUCKDUCKGO_HTML_URL = "https://duckduckgo.com/html/"


class FreeSearchError(Exception):
    pass


def _clean_duckduckgo_url(url: str) -> str:
    """Convertit les URLs de redirection DuckDuckGo en URLs finales."""
    if not url:
        return ""

    parsed = urlparse(url)
    if parsed.netloc.endswith("duckduckgo.com"):
        qs = parse_qs(parsed.query)
        if qs.get("uddg"):
            return unquote(qs["uddg"][0])
    return unescape(url)


def _domain_terms(include_domains: list[str] | None) -> str:
    if not include_domains:
        return ""

    terms = []
    for domain in include_domains:
        domain = domain.replace("https://", "").replace("http://", "").strip("/")
        if domain:
            terms.append(f"site:{domain}")
    return " (" + " OR ".join(terms) + ")" if terms else ""


def _allowed_url(url: str, include_domains: list[str] | None) -> bool:
    if not include_domains:
        return True

    normalized_url = url.lower()
    for domain in include_domains:
        domain = domain.replace("https://", "").replace("http://", "").strip("/").lower()
        if domain and domain in normalized_url:
            return True
    return False


def duckduckgo_search(
    query: str,
    max_results: int = 5,
    include_domains: list[str] | None = None,
) -> list[dict]:
    """Retourne une liste de resultats {title, url, content}."""
    cached = get_cached("duckduckgo_search", query, max_results, include_domains)
    if cached is not None:
        return cached

    full_query = query + _domain_terms(include_domains)
    url = f"{DUCKDUCKGO_HTML_URL}?q={quote_plus(full_query)}"

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise FreeSearchError(f"Erreur DuckDuckGo: {exc}") from exc

    soup = BeautifulSoup(resp.text, "lxml")
    results = []

    for result in soup.select(".result"):
        link = result.select_one(".result__a")
        if not link:
            continue

        final_url = _clean_duckduckgo_url(link.get("href", ""))
        if not final_url or not _allowed_url(final_url, include_domains):
            continue

        snippet = result.select_one(".result__snippet")
        results.append({
            "title": link.get_text(" ", strip=True),
            "url": final_url,
            "content": snippet.get_text(" ", strip=True) if snippet else "",
            "source": "duckduckgo",
        })

        if len(results) >= max_results:
            break

    return set_cached("duckduckgo_search", results, query, max_results, include_domains)
