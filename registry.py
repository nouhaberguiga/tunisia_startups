"""
scrapers/registry.py
-----------------------
Cœur du système "dynamique" : associe un nom de scraper (champ
"scraper" dans sources.json) à une classe Python.

Si une source ajoutée dans sources.json référence un scraper qui
n'existe PAS dans ce registre (ex: nouveau site ajouté par un futur
utilisateur sans toucher au code), on bascule automatiquement sur
GenericLLMScraper. C'est ce mécanisme qui permet d'ajouter de nouvelles
URLs sans écrire de code.
"""

from thedot_scraper import TheDotScraper
from ancs_scraper import AncsScraper
from goafrica_scraper import GoAfricaScraper
from generic_scraper import GenericLLMScraper

REGISTRY = {
    "thedot": TheDotScraper,
    "ancs": AncsScraper,
    "goafrica": GoAfricaScraper,
    "generic": GenericLLMScraper,
}


def get_scraper(scraper_key: str):
    """Retourne une INSTANCE du scraper demandé. Repli silencieux (avec
    message d'info) sur le scraper générique si la clé est inconnue."""
    cls = REGISTRY.get(scraper_key)
    if cls is None:
        print(
            f"  [registry] Aucun scraper spécifique pour '{scraper_key}' "
            f"-> utilisation du scraper générique IA."
        )
        cls = GenericLLMScraper
    return cls()


def register_scraper(key: str, scraper_class) -> None:
    """Permet d'ajouter un nouveau scraper spécifique par code, si un
    jour vous voulez en écrire un pour un site précis sans modifier ce
    fichier (ex: depuis un script externe)."""
    REGISTRY[key] = scraper_class