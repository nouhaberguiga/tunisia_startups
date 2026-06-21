"""
tavily_enrich.py
----------------
Recherche web pour enrichir les startups.

Ordre utilise:
  1. Tavily si TAVILY_API_KEY est configuree et le quota disponible.
  2. DuckDuckGo HTML gratuit si Tavily manque, est hors quota, ou doit
     etre evite pour continuer le pipeline sans bloquer.
"""

from __future__ import annotations

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

import config
from free_search import FreeSearchError, duckduckgo_search


class TavilyError(Exception):
    pass


class TavilyQuotaError(TavilyError):
    pass


def fallback_search(
    query: str,
    max_results: int = 5,
    include_domains: list[str] | None = None,
    reason: str = "",
) -> list[dict]:
    """Recherche gratuite utilisee quand Tavily n'est pas disponible."""
    prefix = f"{reason} -> " if reason else ""
    try:
        print(f"  [search] {prefix}DuckDuckGo")
        return duckduckgo_search(query, max_results=max_results, include_domains=include_domains)
    except FreeSearchError as exc:
        print(f"  [search] DuckDuckGo ignore : {exc}")
        return []


def _should_retry_tavily_error(exc: BaseException) -> bool:
    """Retente les erreurs temporaires, mais jamais les quotas."""
    return isinstance(exc, TavilyError) and not isinstance(exc, TavilyQuotaError)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception(_should_retry_tavily_error),
    reraise=True,
)
def _tavily_api_search(
    query: str,
    max_results: int = 5,
    include_domains: list[str] | None = None,
    search_depth: str = "basic",
) -> list[dict]:
    payload = {
        "api_key": config.TAVILY_API_KEY,
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
    }
    if include_domains:
        payload["include_domains"] = include_domains

    try:
        resp = requests.post(config.TAVILY_URL, json=payload, timeout=config.REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise TavilyError(f"Erreur reseau Tavily: {exc}") from exc

    if resp.status_code in (429, 432):
        raise TavilyQuotaError(f"Quota Tavily depasse ({resp.status_code})")
    if resp.status_code != 200:
        raise TavilyError(f"Erreur Tavily {resp.status_code}: {resp.text[:300]}")

    return resp.json().get("results", [])


def tavily_search(
    query: str,
    max_results: int = 5,
    include_domains: list[str] | None = None,
    search_depth: str = "basic",
) -> list[dict]:
    """Retourne une liste de resultats {title, url, content}.

    Le nom reste tavily_search pour ne pas casser les imports existants,
    mais la fonction sait maintenant basculer sur DuckDuckGo gratuitement.
    """
    if not config.TAVILY_API_KEY:
        return fallback_search(
            query,
            max_results=max_results,
            include_domains=include_domains,
            reason="TAVILY_API_KEY manquante",
        )

    try:
        return _tavily_api_search(
            query,
            max_results=max_results,
            include_domains=include_domains,
            search_depth=search_depth,
        )
    except TavilyQuotaError as exc:
        return fallback_search(
            query,
            max_results=max_results,
            include_domains=include_domains,
            reason=str(exc),
        )
    except TavilyError as exc:
        return fallback_search(
            query,
            max_results=max_results,
            include_domains=include_domains,
            reason=str(exc),
        )


def enrich_startup_context(nom: str, ville: str | None = None) -> list[dict]:
    """Recherche generale: site officiel, presse, LinkedIn, fondateurs."""
    queries = [
        f"{nom} startup Tunisie",
        f"{nom} {ville or ''} startup tunisienne fondateur".strip(),
    ]
    all_results, seen_urls = [], set()
    for q in queries:
        try:
            results = tavily_search(q, max_results=5)
        except TavilyError as exc:
            print(f"  [tavily] {exc}")
            continue
        for result in results:
            url = result.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(result)
    return all_results
