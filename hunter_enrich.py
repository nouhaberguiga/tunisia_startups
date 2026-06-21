"""
enrichment/hunter_enrich.py
------------------------------
Utilise l'API Hunter.io (plan gratuit : 25 requêtes/mois) pour trouver
les adresses email professionnelles liées au nom de domaine du site web
d'une startup (ex: contact@startup.tn, founder@startup.tn...).

Nécessite que la startup ait déjà un `site_web` connu (issu du
scraping de base ou de l'enrichissement Tavily) -> à appeler après.
"""

import requests
from urllib.parse import urlparse

import config


class HunterError(Exception):
    pass


def _extract_domain(site_web: str) -> str | None:
    if not site_web:
        return None
    netloc = urlparse(site_web).netloc or urlparse("https://" + site_web).netloc
    return netloc.replace("www.", "").strip() or None


def find_emails(site_web: str, limit: int = 5) -> dict:
    """Retourne {"email_principal": str|None, "emails_supplementaires": [...]}."""
    domain = _extract_domain(site_web)
    if not domain:
        return {"email_principal": None, "emails_supplementaires": []}

    if not config.HUNTER_API_KEY:
        print("  [hunter] HUNTER_API_KEY manquante -> recherche d'emails ignorée")
        return {"email_principal": None, "emails_supplementaires": []}

    try:
        resp = requests.get(
            config.HUNTER_URL,
            params={"domain": domain, "api_key": config.HUNTER_API_KEY, "limit": limit},
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        print(f"  [hunter] Erreur réseau pour {domain} : {e}")
        return {"email_principal": None, "emails_supplementaires": []}

    if resp.status_code == 401:
        print("  [hunter] Clé API invalide")
        return {"email_principal": None, "emails_supplementaires": []}
    if resp.status_code == 429:
        print("  [hunter] Quota gratuit Hunter.io atteint pour ce mois")
        return {"email_principal": None, "emails_supplementaires": []}
    if resp.status_code != 200:
        print(f"  [hunter] Erreur {resp.status_code} pour {domain}")
        return {"email_principal": None, "emails_supplementaires": []}

    data = resp.json().get("data", {})
    emails = [e.get("value") for e in data.get("emails", []) if e.get("value")]
    generic = data.get("pattern")  # ex: "{first}.{last}@domain.tn" (utile pour deviner un email)

    return {
        "email_principal": emails[0] if emails else None,
        "emails_supplementaires": emails[1:] if len(emails) > 1 else [],
        "pattern_email_devine": generic,
    }