"""
scrapers/goafrica_scraper.py
-------------------------------
Scraper dédié à l'annuaire Go Africa Online :
https://www.goafricaonline.com/tn/annuaire-resultat?type=company&whatWho=Startup&where=country-tn

Particularités observées sur ce site :
  - La page liste les startups avec nom, lien vers une fiche détaillée
    (URL du type /tn/<id>-<slug>-tunisie), adresse, téléphone et
    description, mais PAS le site web externe directement.
  - Le site web (et les réseaux sociaux) se trouve sur la fiche
    détaillée de chaque startup -> ce scraper visite donc chaque fiche.
  - Les résultats sont paginés ("Next ->") : on suit la pagination
    jusqu'à `max_pages` (configurable dans sources.json).

Comme pour thedot, les classes CSS exactes n'ont pas pu être vérifiées
ici (accès réseau restreint), donc l'extraction se base sur des motifs
robustes : les liens de fiches (regex /tn/\\d+-...) et la présence du
mot "Tunisie" dans l'adresse pour délimiter chaque carte.
"""

import re
import config
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from base import BaseScraper, fetch_page, save_debug
from generic_scraper import GenericLLMScraper

DETAIL_URL_RE = re.compile(r"/tn/\d+-[\w\-]+")
CITY_RE = re.compile(
    r"([A-ZÉÈÀÙÂÊÎÔÛÇ][\wÀ-ÿ\-'’ ]{1,30}?)\s*-\s*(?:\d{3,4}\s*-\s*)?Tunisie", re.UNICODE
)
SOCIAL_DOMAINS = {
    "facebook.com": "facebook_url",
    "linkedin.com": "linkedin_url",
    "instagram.com": "instagram_url",
    "twitter.com": "twitter_url",
    "x.com": "twitter_url",
}
MIN_RESULTS_BEFORE_FALLBACK = 2


def find_card_container(link_tag):
    node = link_tag
    for _ in range(6):
        if node.parent is None:
            return None
        node = node.parent
        text = node.get_text(" ", strip=True)
        if "Tunisie" in text and len(text) > 25:
            return node
    return node


def extract_ville(text: str) -> str | None:
    m = CITY_RE.search(text)
    return m.group(1).strip(" -") if m else None


def extract_phone(container) -> str | None:
    tel = container.find("a", href=re.compile(r"^tel:"))
    if tel:
        return tel["href"].replace("tel:", "").strip()
    return None


def extract_logo(container, page_url: str) -> str | None:
    img = container.find("img")
    if img and img.get("src"):
        return urljoin(page_url, img["src"])
    return None


def extract_description(container, exclude: set) -> str | None:
    """Heuristique : la description est généralement le plus long bloc de
    texte de la carte (bien plus long que les libellés d'interface comme
    'Fiche', 'Itinéraire', 'Site web', l'adresse ou le téléphone)."""
    candidates = [
        t.strip() for t in container.stripped_strings
        if t.strip() and t.strip() not in exclude and len(t.strip()) > 25
    ]
    if not candidates:
        return None
    return max(candidates, key=len)


def parse_listing_card(container, link_tag, page_url: str) -> dict:
    nom = link_tag.get_text(strip=True)
    profile_url = urljoin(page_url, link_tag["href"])
    full_text = container.get_text(" ", strip=True)

    ville = extract_ville(full_text)
    telephone = extract_phone(container)
    logo_url = extract_logo(container, page_url)
    ui_noise = {"Fiche", "Itinéraire", "Site web", "Startup", nom}
    description = extract_description(container, ui_noise)

    return {
        "nom": nom,
        "secteur": "Startup",  # catégorie de recherche utilisée pour cette page
        "domaine": None,
        "description": description,
        "site_web": None,  # complété via la fiche détaillée si activé
        "ville": ville,
        "logo_url": logo_url,
        "telephone": telephone,
        "_profile_url": profile_url,  # champ interne, retiré avant export
    }


def extract_listing(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    seen_links, cards = set(), []

    for a in soup.find_all("a", href=True):
        if not DETAIL_URL_RE.search(a["href"]):
            continue
        href = urljoin(page_url, a["href"])
        if href in seen_links:
            continue  # même fiche référencée par 2 liens (image + titre)
        container = find_card_container(a)
        if container is None:
            continue
        seen_links.add(href)
        cards.append(parse_listing_card(container, a, page_url))

    return cards


def extract_external_links(html: str) -> dict:
    """Sur la fiche détaillée : récupère le site web officiel + réseaux
    sociaux en regardant les liens externes (hors goafricaonline.com)."""
    soup = BeautifulSoup(html, "lxml")
    socials = {}
    site_web = None

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue
        domain = urlparse(href).netloc.lower().replace("www.", "")
        if "goafricaonline.com" in domain:
            continue

        matched_social = next((v for d, v in SOCIAL_DOMAINS.items() if d in domain), None)
        if matched_social:
            socials.setdefault(matched_social, href)
        elif site_web is None:
            site_web = href

    result = {"site_web": site_web}
    result.update(socials)
    return result


def find_next_page_url(html: str, current_url: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.find("a", string=re.compile(r"Next|Suivant", re.IGNORECASE))
    if next_link and next_link.get("href"):
        return urljoin(current_url, next_link["href"])
    rel_next = soup.find("a", rel="next")
    if rel_next and rel_next.get("href"):
        return urljoin(current_url, rel_next["href"])
    return None


class GoAfricaScraper(BaseScraper):
    name = "goafrica"

    async def scrape_async(self, url: str, source_config: dict | None = None) -> list[dict]:
        source_config = source_config or {}
        source_name = source_config.get("name", "goafricaonline")
        requested_pages = int(source_config.get("max_pages", config.MAX_PAGES_PER_SOURCE))
        max_pages = min(requested_pages, config.MAX_PAGES_PER_SOURCE)
        fetch_details = source_config.get("fetch_detail_pages", config.FETCH_DETAIL_PAGES)

        all_cards = []
        current_url, page_num = url, 1

        while current_url and page_num <= max_pages:
            result = await fetch_page(current_url)
            if not result.success or not result.html:
                print(f"  [goafrica] Échec récupération page {page_num} : {result.error}")
                break
            save_debug(f"goafrica_p{page_num}", result)

            cards = extract_listing(result.html, current_url)
            print(f"  [goafrica] Page {page_num} : {len(cards)} startup(s) trouvée(s)")
            all_cards.extend(cards)

            current_url = find_next_page_url(result.html, current_url)
            page_num += 1

        if not all_cards:
            print("  [goafrica] Aucun résultat via heuristique HTML -> scraper générique IA")
            return await GenericLLMScraper().scrape_async(url, source_config)

        if fetch_details:
            for card in all_cards:
                profile_url = card.pop("_profile_url", None)
                if not profile_url:
                    continue
                detail = await fetch_page(profile_url)
                if detail.success and detail.html:
                    extra = extract_external_links(detail.html)
                    card.update({k: v for k, v in extra.items() if v})
        else:
            for card in all_cards:
                card.pop("_profile_url", None)

        for card in all_cards:
            card["source"] = source_name
            card["source_url"] = url

        return all_cards
