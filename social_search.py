"""
enrichment/social_search.py
-------------------------------
Recherche les profils réseaux sociaux officiels d'une startup
(LinkedIn, Facebook, Instagram, Twitter/X) via Tavily, en limitant la
recherche aux domaines concernés (`include_domains`) pour des résultats
plus fiables que du scraping direct (LinkedIn/Facebook bloquent
fortement le scraping direct et l'interdisent dans leurs CGU).
"""

from urllib.parse import urlparse

from tavily_enrich import tavily_search, TavilyError

PLATEFORMES = {
    "linkedin_url": ["linkedin.com"],
    "facebook_url": ["facebook.com"],
    "instagram_url": ["instagram.com"],
    "twitter_url": ["twitter.com", "x.com"],
}


def _looks_relevant(url: str, nom: str) -> bool:
    """Filtre grossier pour éviter de prendre la page LinkedIn d'une autre
    entreprise homonyme : le nom (ou une partie) doit apparaître dans
    l'URL ou le slug."""
    slug = urlparse(url).path.lower()
    nom_tokens = [t for t in nom.lower().split() if len(t) > 2]
    return any(t.replace("-", "") in slug.replace("-", "") for t in nom_tokens) or not nom_tokens


def find_social_profiles(nom: str, ville: str | None = None) -> dict:
    found = {}
    for field, domains in PLATEFORMES.items():
        query = f"{nom} {ville or ''} Tunisie".strip()
        try:
            results = tavily_search(query, max_results=3, include_domains=domains)
        except TavilyError as e:
            print(f"  [social] {e}")
            continue
        for r in results:
            url = r.get("url", "")
            if url and _looks_relevant(url, nom):
                found[field] = url
                break
    return found