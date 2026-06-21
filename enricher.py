"""
enricher.py
-----------
Enrichissement gratuit, volontairement sobre.

Par defaut, on evite les appels web par startup. Quand `use_web=True`,
on fait au maximum une recherche DuckDuckGo pour trouver un site officiel
manquant, avec cache persistant.
"""

from __future__ import annotations

from urllib.parse import urlparse

from cache_store import get_cached, set_cached
from free_search import FreeSearchError, duckduckgo_search


LOW_QUALITY_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "crunchbase.com",
    "wikipedia.org",
    "goafricaonline.com",
    "thedot.tn",
)


def _is_probable_official_site(url: str) -> bool:
    if not url:
        return False
    domain = urlparse(url).netloc.lower().replace("www.", "")
    return bool(domain) and not any(blocked in domain for blocked in LOW_QUALITY_DOMAINS)


def find_official_site_free(nom: str) -> str | None:
    cached = get_cached("official_site", nom)
    if cached is not None:
        return cached or None

    try:
        results = duckduckgo_search(f"{nom} startup Tunisie site officiel", max_results=4)
    except FreeSearchError as exc:
        print(f"  [free] DuckDuckGo ignore : {exc}")
        return set_cached("official_site", None, nom)

    for result in results:
        url = result.get("url", "")
        if _is_probable_official_site(url):
            return set_cached("official_site", url, nom)

    return set_cached("official_site", None, nom)


def enrich_startup_free(startup: dict, use_web: bool = False) -> dict:
    """Complete uniquement les champs fiables et peu couteux."""
    enriched = dict(startup)

    if not use_web:
        return enriched

    if not enriched.get("site_web") and enriched.get("nom"):
        site_web = find_official_site_free(enriched["nom"])
        if site_web:
            enriched["site_web"] = site_web
            enriched.setdefault("sources_enrichissement", [])
            if "duckduckgo_official_site" not in enriched["sources_enrichissement"]:
                enriched["sources_enrichissement"].append("duckduckgo_official_site")

    return enriched
