"""
scrapers/thedot_scraper.py
----------------------------
Scraper dédié à https://thedot.tn/4-nos-staurtups

Particularité de cette page : toutes les startups (~90) sont listées sur
UNE seule page (pas de pagination), sous forme de "cartes" répétées
(logo + nom + description + secteur + site web).

La structure HTML exacte (noms de classes CSS) n'a pas pu être vérifiée
directement depuis cet environnement (accès réseau restreint), donc ce
scraper utilise une heuristique robuste plutôt que des sélecteurs CSS
figés :
  1. Repère toutes les "cartes" en partant des balises <img> (logos) et
     en remontant jusqu'au plus petit conteneur contenant aussi le nom,
     la description, le secteur et le lien du site web.
  2. Récupère aussi les quelques startups SANS logo (ex: "BIM-verse")
     en regardant les autres enfants du même conteneur parent.
  3. Si l'heuristique échoue (trop peu de résultats), bascule
     automatiquement sur le scraper générique IA (voir generic_scraper.py).

-> Si la structure du site change, lancez `python main.py debug thedot`
   pour régénérer un dump HTML dans data/debug_html/ et ajustez la
   fonction `parse_card()` ci-dessous en conséquence.
"""

from urllib.parse import urljoin
from bs4 import BeautifulSoup

from base import BaseScraper, fetch_page, save_debug
from generic_scraper import GenericLLMScraper

MIN_RESULTS_BEFORE_FALLBACK = 5


def normalize_href(href: str) -> str:
    href = href.strip()
    if href and not href.startswith(("http://", "https://", "/", "#", "mailto:", "tel:")):
        # Bug fréquent observé sur thedot.tn : certains liens sont saisis
        # sans "https://" (ex: href="www.inveep.com") -> on corrige.
        href = "https://" + href
    return href


def find_card_container(img_tag):
    """Remonte les parents d'une image jusqu'à un conteneur 'carte' plausible
    (qui contient le nom + au moins une autre info textuelle)."""
    node = img_tag
    for _ in range(6):
        if node.parent is None:
            return None
        node = node.parent
        texts = [t.strip() for t in node.stripped_strings if t.strip()]
        if len(texts) >= 2:
            return node
    return node


def parse_card(card, page_url: str) -> dict | None:
    texts = [t.strip() for t in card.stripped_strings if t.strip()]
    if not texts:
        return None

    nom = texts[0]
    if len(nom) < 2 or len(nom) > 80:
        return None  # probablement pas une vraie carte startup

    # Cherche le lien externe vers le site de la startup
    site_web = None
    for a in card.find_all("a", href=True):
        href = normalize_href(a["href"])
        if href.startswith("http") and "thedot.tn" not in href:
            site_web = href.rstrip("/")
            break

    link_texts = {a.get_text(strip=True) for a in card.find_all("a")}
    body_texts = [t for t in texts[1:] if t not in link_texts and t != nom]

    secteur, description = None, None
    if body_texts:
        secteur = body_texts[-1]
        description = " ".join(body_texts[:-1]).strip() or None

    logo_url = None
    img = card.find("img")
    if img and img.get("src"):
        logo_url = urljoin(page_url, img["src"])

    return {
        "nom": nom,
        "description": description,
        "secteur": secteur,
        "domaine": None,
        "site_web": site_web,
        "ville": None,
        "logo_url": logo_url,
    }


def extract_cards_from_html(html: str, page_url: str) -> list:
    soup = BeautifulSoup(html, "lxml")

    # Étape 1 : repère les conteneurs probables via les logos
    seen_parents = {}
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "logo_the_dot" in src or "favicon" in src:
            continue  # ignore le logo du site lui-même
        container = find_card_container(img)
        if container is None or container.parent is None:
            continue
        seen_parents.setdefault(id(container.parent), container.parent)

    if not seen_parents:
        return []

    # Étape 2 : la vraie liste de startups = le parent qui a le plus
    # d'enfants directs ressemblant à des cartes
    best_parent, best_count = None, 0
    for parent in seen_parents.values():
        count = len(parent.find_all(recursive=False))
        if count > best_count:
            best_parent, best_count = parent, count

    if best_parent is None:
        return []

    cards = []
    for child in best_parent.find_all(recursive=False):
        if child.find("img") is None and len(list(child.stripped_strings)) < 2:
            continue  # ignore le header "Logo / Nom / Description..."
        if "logo" in " ".join(child.stripped_strings).lower()[:15] and "secteur" in str(child).lower()[:200]:
            continue
        cards.append(child)
    return cards


class TheDotScraper(BaseScraper):
    name = "thedot"

    async def scrape_async(self, url: str, source_config: dict | None = None) -> list[dict]:
        source_config = source_config or {}
        source_name = source_config.get("name", "thedot")

        result = await fetch_page(url)
        if not result.success or not result.html:
            print(f"  [thedot] Échec récupération : {result.error}")
            return []

        save_debug("thedot", result)

        cards = extract_cards_from_html(result.html, url)
        startups = []
        for card in cards:
            parsed = parse_card(card, url)
            if parsed:
                parsed["source"] = source_name
                parsed["source_url"] = url
                startups.append(parsed)

        # Dédoublonnage simple par nom (l'heuristique peut parfois capter
        # un conteneur englobant ET ses enfants -> doublons)
        unique, seen_noms = [], set()
        for s in startups:
            key = s["nom"].lower()
            if key not in seen_noms:
                seen_noms.add(key)
                unique.append(s)
        startups = unique

        print(f"  [thedot] {len(startups)} startup(s) extraite(s) via heuristique HTML")

        if len(startups) < MIN_RESULTS_BEFORE_FALLBACK:
            print("  [thedot] Trop peu de résultats -> bascule sur le scraper générique IA")
            fallback = await GenericLLMScraper().scrape_async(url, source_config)
            if len(fallback) > len(startups):
                return fallback

        return startups