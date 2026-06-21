"""
config.py
----------
Configuration centrale du projet. Charge les variables d'environnement
(.env) et définit tous les chemins et constantes utilisés par les autres
modules. Aucun autre fichier ne doit lire os.environ directement : tout
passe par ce module pour garder une seule source de vérité.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Racine du projet (= dossier contenant ce fichier)
BASE_DIR = Path(__file__).resolve().parent

# Charge le fichier .env s'il existe (sinon les clés resteront vides et
# les modules concernés afficheront un avertissement au lieu de planter)
load_dotenv(BASE_DIR / ".env")

# ----------------------------------------------------------------------
# Dossiers de données
# ----------------------------------------------------------------------
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

SOURCES_FILE = BASE_DIR / "sources.json"
STARTUPS_BASE_FILE = DATA_DIR / "startups_base.json"
STARTUPS_ENRICHED_FILE = DATA_DIR / "startups_enriched.json"
CACHE_FILE = DATA_DIR / "cache.json"
DEBUG_DIR = DATA_DIR / "debug_html"
DEBUG_DIR.mkdir(exist_ok=True)

# ----------------------------------------------------------------------
# OpenRouter (LLM gratuit) — utilisé pour le scraping générique et
# l'enrichissement (normalisation, déduction de champs manquants, etc.)
# ----------------------------------------------------------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ----------------------------------------------------------------------
# Tavily (recherche web pour enrichissement)
# ----------------------------------------------------------------------
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_URL = "https://api.tavily.com/search"

# ----------------------------------------------------------------------
# Hunter.io (recherche d'emails)
# ----------------------------------------------------------------------
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
HUNTER_URL = "https://api.hunter.io/v2/domain-search"

# ----------------------------------------------------------------------
# Paramètres réseau / politesse de scraping
# ----------------------------------------------------------------------
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
SCRAPE_DELAY_SECONDS = float(os.getenv("SCRAPE_DELAY_SECONDS", "2"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "3"))

# Limites globales pour garder le pipeline stable et reproductible.
MAX_PAGES_PER_SOURCE = int(os.getenv("MAX_PAGES_PER_SOURCE", "2"))
FETCH_DETAIL_PAGES = os.getenv("FETCH_DETAIL_PAGES", "false").lower() == "true"
ENRICH_DELAY_SECONDS = float(os.getenv("ENRICH_DELAY_SECONDS", "1.5"))
MAX_ENRICH_STARTUPS = int(os.getenv("MAX_ENRICH_STARTUPS", "30"))
MAX_LLM_CALLS = int(os.getenv("MAX_LLM_CALLS", "10"))
OPENROUTER_RETRY_ATTEMPTS = int(os.getenv("OPENROUTER_RETRY_ATTEMPTS", "1"))

USER_AGENT = (
     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)

# Liste blanche de secteurs/mots-clés utile pour désambiguïser le texte
# brut lors du parsing (ex: distinguer une description d'un libellé de
# secteur dans une page mal structurée). Complétez librement.
KNOWN_SECTOR_HINTS = [
    "fintech", "edtech", "healthtech", "agritech", "greentech", "watertech",
    "legaltech", "proptech", "foodtech", "mobility", "deeptech", "biotech",
    "e-commerce", "e-com", "logistics", "ai", "ia", "saas", "blockchain",
    "robotics", "industry 4.0", "wellness", "traveltech", "construction",
]

PDF_FILE = "data/STARTUPSTECH.pdf"

def check_config(verbose: bool = True) -> dict:
    """Vérifie quelles clés API sont configurées et avertit l'utilisateur.
    Utile à appeler au démarrage de main.py."""
    status = {
        "openrouter": bool(OPENROUTER_API_KEY),
        "tavily": bool(TAVILY_API_KEY),
        "hunter": bool(HUNTER_API_KEY),
    }
    if verbose:
        for name, ok in status.items():
            etat = "OK" if ok else "MANQUANTE (fonctionnalités limitées)"
            print(f"  - Clé {name:<10}: {etat}")
    return status
