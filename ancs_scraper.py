"""
scrapers/ancs_scraper.py
---------------------------
Scraper dédié à https://www.ancs.tn/fr/startups-tunisiennes (Agence
Nationale de la Certification ... / annuaire officiel des startups
labellisées en Tunisie).

ATTENTION : au moment de l'écriture de ce projet, le fichier robots.txt
de ce site INTERDIT explicitement le crawling automatisé
(`Disallow`). Avant d'activer ce scraper, l'étudiante doit :
  1. Vérifier elle-même le robots.txt actuel : https://www.ancs.tn/robots.txt
  2. Vérifier les CGU du site.
  3. Idéalement, contacter l'ANCS pour savoir si un export officiel des
     données (CSV/API) est disponible — solution la plus propre pour un
     organisme public.

Ce module fournit donc :
  - check_robots_txt() : avertit si le scraping semble interdit.
  - AncsScraper : un scraper "best effort" (structure non vérifiable
    depuis cet environnement) qui repose surtout sur le moteur générique
    IA, par prudence et par manque de visibilité sur le HTML réel.

Respectez systématiquement source_config["enabled"]=false si vous
préférez ne pas exécuter ce scraper.
"""

import requests
from urllib.parse import urlparse

import config
from base import BaseScraper
from generic_scraper import GenericLLMScraper


def check_robots_txt(url: str) -> bool:
    """Retourne True si le scraping semble autorisé. Affiche un
    avertissement clair sinon. Ne bloque pas l'exécution (c'est à
    l'étudiante de décider, en connaissance de cause), mais le respect
    du robots.txt est fortement recommandé."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=10, headers={"User-Agent": config.USER_AGENT})
        if resp.status_code == 200 and "Disallow: /" in resp.text:
            print(
                "  [ancs] /!\\ ATTENTION : robots.txt de ce site contient des règles "
                "Disallow. Le scraping automatisé n'est probablement pas autorisé.\n"
                "  [ancs] Vérifiez manuellement : " + robots_url
            )
            return False
    except requests.RequestException:
        print("  [ancs] Impossible de vérifier robots.txt (réseau) — soyez prudent.")
    return True


class AncsScraper(BaseScraper):
    name = "ancs"

    async def scrape_async(self, url: str, source_config: dict | None = None) -> list[dict]:
        source_config = source_config or {}
        source_name = source_config.get("name", "ancs")

        allowed = check_robots_txt(url)
        if not allowed and not source_config.get("force_ignore_robots", False):
            print(
                "  [ancs] Scraping annulé par précaution (robots.txt). "
                "Mettez \"force_ignore_robots\": true dans sources.json pour forcer "
                "(à vos risques, après vérification des CGU)."
            )
            return []

        # Structure HTML non vérifiable depuis cet environnement -> on
        # s'appuie directement sur le scraper générique IA, plus robuste
        # face à une structure inconnue qu'un jeu de sélecteurs CSS devinés.
        startups = await GenericLLMScraper().scrape_async(url, {**source_config, "name": source_name})
        return startups