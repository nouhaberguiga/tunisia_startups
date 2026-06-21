"""
enrichment/jobs_search.py
-----------------------------
Recherche les offres d'emploi publiées par une startup sur des sites
d'emploi tunisiens/internationaux (Tanitjobs, Indeed...), via Tavily
restreint à ces domaines. Permet d'estimer si la startup recrute
activement (signal de croissance) et de lister quelques offres.

NOTE : vérifiez le nom de domaine exact de Tanitjobs (tanitjobs.com)
au moment de l'exécution, certains annuaires d'emploi tunisiens changent
occasionnellement de domaine.
"""

from tavily_enrich import tavily_search, TavilyError

JOB_SITES = ["tanitjobs.com", "indeed.com", "linkedin.com/jobs"]


def find_job_offers(nom: str, max_results: int = 5) -> list[dict]:
    """Retourne une liste de dicts {titre, source, url}."""
    query = f"{nom} recrutement emploi Tunisie"
    try:
        results = tavily_search(query, max_results=max_results, include_domains=JOB_SITES)
    except TavilyError as e:
        print(f"  [jobs] {e}")
        return []

    offers = []
    for r in results:
        url = r.get("url", "")
        source = next((s.split(".")[0] for s in JOB_SITES if s.split(".")[0] in url), "autre")
        offers.append({
            "titre": r.get("title"),
            "source": source,
            "url": url,
        })
    return offers