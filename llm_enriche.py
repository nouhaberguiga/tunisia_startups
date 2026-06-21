from __future__ import annotations

from cache_store import get_cached, set_cached
from llm_client import call_openrouter, extract_json, OpenRouterError

ALLOWED_FIELDS = {"secteur","domaine","description","tags"}

def _clean(data: dict) -> dict:
    return {k:v for k,v in data.items() if k in ALLOWED_FIELDS and v}


PROMPT = """
Ameliore cette fiche startup SANS INVENTER :

{startup}

Retour JSON:
{{
  "secteur": "...",
  "domaine": "...",
  "description": "...",
  "tags": []
}}
"""

def enrich_with_llm(startup: dict) -> dict:
    cache_key = {
        "nom": startup.get("nom"),
        "desc": startup.get("description")
    }

    cached = get_cached("llm", cache_key)
    if cached is not None:
        return cached

    try:
        raw = call_openrouter(PROMPT.format(startup=cache_key))
        data = extract_json(raw)
    except (OpenRouterError, ValueError):
        return set_cached("llm", {}, cache_key)

    if not isinstance(data, dict):
        return set_cached("llm", {}, cache_key)

    return set_cached("llm", _clean(data), cache_key)
