"""
scrapers/base.py
------------------
Classe de base commune à tous les scrapers + fonction utilitaire pour
récupérer une page avec crawl4ai (HTML rendu + markdown nettoyé).

NOTE IMPORTANTE SUR crawl4ai :
crawl4ai évolue vite et son API change parfois entre versions
(ex: paramètres de AsyncWebCrawler.arun()). La fonction fetch_page()
ci-dessous essaie plusieurs façons d'appeler l'API pour rester robuste.
Si elle échoue avec votre version installée, faites :
    pip show crawl4ai
et consultez https://docs.crawl4ai.com pour adapter les 2-3 lignes
marquées "ADAPTER SI BESOIN".
"""

import abc
import asyncio
from pathlib import Path
from dataclasses import dataclass, field

import config


@dataclass
class FetchResult:
    url: str
    html: str = ""
    markdown: str = ""
    success: bool = False
    error: str = ""


async def fetch_page(url: str, wait_for_js: bool = True) -> FetchResult:
    """Récupère une page web avec crawl4ai (navigateur headless), avec
    repli automatique sur un simple GET requests si crawl4ai échoue
    (ex: page 100% statique, pas besoin de JS)."""
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler(verbose=False, user_agent=config.USER_AGENT) as crawler:
            # ADAPTER SI BESOIN : selon la version de crawl4ai installée,
            # arun() peut accepter directement ces kwargs, ou nécessiter
            # un objet CrawlerRunConfig. On essaie la forme simple d'abord.
            try:
                result = await crawler.arun(url=url, bypass_cache=True)
            except TypeError:
                result = await crawler.arun(url=url)

            html = getattr(result, "html", "") or getattr(result, "cleaned_html", "")
            md = getattr(result, "markdown", "")
            # Dans certaines versions, .markdown est un objet avec .raw_markdown
            if md and not isinstance(md, str):
                md = getattr(md, "raw_markdown", "") or getattr(md, "markdown", "") or str(md)

            return FetchResult(url=url, html=html or "", markdown=md or "", success=True)

    except Exception as e:
        # Repli : requête HTTP simple (ne marche pas pour les sites 100% JS)
        try:
            import requests
            resp = requests.get(
                url,
                headers={"User-Agent": config.USER_AGENT},
                timeout=config.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return FetchResult(url=url, html=resp.text, markdown="", success=True,
                                error=f"crawl4ai indisponible ({e}), repli sur requests")
        except Exception as e2:
            return FetchResult(url=url, success=False, error=f"crawl4ai: {e} | requests: {e2}")


def save_debug(name: str, result: FetchResult) -> None:
    """Sauvegarde le HTML et le markdown bruts pour inspection manuelle.
    Très utile pour ajuster les sélecteurs CSS d'un scraper spécifique :
    lancez le scraper une fois, puis ouvrez le fichier .html généré dans
    data/debug_html/ pour voir la vraie structure de la page."""
    safe = "".join(c if c.isalnum() else "_" for c in name)[:60]
    if result.html:
        (config.DEBUG_DIR / f"{safe}.html").write_text(result.html, encoding="utf-8")
    if result.markdown:
        (config.DEBUG_DIR / f"{safe}.md").write_text(result.markdown, encoding="utf-8")


class BaseScraper(abc.ABC):
    """Interface commune. Chaque scraper spécifique (thedot, ancs,
    goafrica...) ou générique doit implémenter `scrape_async`."""

    name: str = "base"

    @abc.abstractmethod
    async def scrape_async(self, url: str, source_config: dict | None = None) -> list[dict]:
        """Doit retourner une liste de dicts compatibles avec
        models.StartupBase (au minimum le champ 'nom')."""
        raise NotImplementedError

    def scrape(self, url: str, source_config: dict | None = None) -> list[dict]:
        """Wrapper synchrone pratique pour main.py / scripts simples."""
        return asyncio.run(self.scrape_async(url, source_config))