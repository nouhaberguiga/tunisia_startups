"""
scrapers/generic_scraper.py
-----------------------------
Scraper "fourre-tout" qui permet d'ajouter N'IMPORTE QUELLE nouvelle
source dans sources.json SANS écrire de code Python.

Fonctionnement :
  1. crawl4ai récupère la page (rendu JS inclus) et produit un markdown
     nettoyé (sans menus/scripts).
  2. Ce markdown est envoyé à un LLM gratuit (OpenRouter) avec une
     consigne stricte : renvoyer un tableau JSON de startups respectant
     le schéma du projet (models.StartupBase).
  3. Le JSON renvoyé est validé/nettoyé avant d'être retourné.

C'est le scraper le moins précis (dépend de la qualité du LLM gratuit
et de la longueur de la page) mais c'est lui qui rend le projet
"dynamique" : un futur utilisateur ajoute une URL dans sources.json,
et si aucun scraper spécifique n'existe pour ce domaine, celui-ci
prend automatiquement le relais (voir scrapers/registry.py).
"""

from base import BaseScraper, fetch_page, save_debug
from llm_client import call_openrouter, extract_json, OpenRouterError

MAX_MARKDOWN_CHARS = 18000  # garde-fou pour ne pas dépasser le contexte du LLM gratuit

EXTRACTION_PROMPT_TEMPLATE = """Voici le contenu (format markdown) d'une page web qui liste des startups tunisiennes.

Extrait TOUTES les startups mentionnées sur cette page et renvoie UNIQUEMENT un tableau JSON
(pas de texte avant/après, pas de ```), où chaque élément a exactement cette forme :

{{
  "nom": "nom de la startup",
  "secteur": "secteur d'activité si mentionné, sinon null",
  "domaine": "domaine/catégorie plus large si différent du secteur, sinon null",
  "description": "description courte si disponible, sinon null",
  "site_web": "URL du site web officiel de la startup si présente, sinon null",
  "ville": "ville en Tunisie si mentionnée, sinon null",
  "logo_url": "URL du logo si présente dans le markdown, sinon null"
}}

Règles strictes :
- N'invente AUCUNE information qui n'est pas dans le texte fourni.
- Si une startup n'a pas de site web mentionné, mets "site_web": null (n'invente pas d'URL).
- Ignore les éléments de menu, liens de navigation, partenaires, articles de blog : ne garde que
  les startups elles-mêmes.
- Si aucune startup n'est trouvée, renvoie [].

Contenu de la page :
---
{content}
---

Réponds uniquement avec le tableau JSON.
"""


class GenericLLMScraper(BaseScraper):
    name = "generic"

    async def scrape_async(self, url: str, source_config: dict | None = None) -> list[dict]:
        source_config = source_config or {}
        source_name = source_config.get("name", "generic")

        result = await fetch_page(url)
        if not result.success:
            print(f"  [generic] Échec récupération de {url} : {result.error}")
            return []

        save_debug(f"{source_name}_generic", result)

        # On préfère le markdown (plus court, plus propre pour le LLM).
        # Si crawl4ai n'a pas produit de markdown (repli requests brut),
        # on retombe sur le HTML tronqué -> moins fiable mais mieux que rien.
        content = result.markdown or result.html
        if not content:
            return []
        if len(content) > MAX_MARKDOWN_CHARS:
            content = content[:MAX_MARKDOWN_CHARS]
            print(f"  [generic] Contenu tronqué à {MAX_MARKDOWN_CHARS} caractères pour le LLM")

        prompt = EXTRACTION_PROMPT_TEMPLATE.format(content=content)

        try:
            raw_response = call_openrouter(prompt)
            items = extract_json(raw_response)
        except (OpenRouterError, ValueError) as e:
            print(f"  [generic] Échec extraction LLM pour {url} : {e}")
            return []

        if not isinstance(items, list):
            print(f"  [generic] Réponse LLM inattendue (pas une liste) pour {url}")
            return []

        startups = []
        for item in items:
            if not isinstance(item, dict) or not item.get("nom"):
                continue
            item["source"] = source_name
            item["source_url"] = url
            startups.append(item)

        print(f"  [generic] {len(startups)} startup(s) extraite(s) de {url}")
        return startups