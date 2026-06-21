"""
storage.py
-----------
Lecture/écriture des fichiers JSON + déduplication des startups.
On garde le stockage volontairement simple (liste de dicts dans un
fichier JSON) comme demandé, mais avec une logique de fusion propre
pour éviter les doublons quand plusieurs sources citent la même startup.
"""

import json
from pathlib import Path
from rapidfuzz import fuzz


def load_json(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


def save_json(path: Path, data: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower().strip() if ch.isalnum())


def find_existing_match(startup: dict, existing: list[dict], threshold: int = 88) -> dict | None:
    """Cherche si `startup` correspond déjà à une entrée existante.
    On compare d'abord le site web (signal le plus fiable), puis le nom
    par similarité floue (utile car les sources orthographient parfois
    différemment : "The Dot" vs "TheDot")."""
    site = (startup.get("site_web") or "").lower().rstrip("/")
    nom_norm = _normalize_name(startup.get("nom", ""))

    for item in existing:
        item_site = (item.get("site_web") or "").lower().rstrip("/")
        if site and item_site and site == item_site:
            return item

    best, best_score = None, 0
    for item in existing:
        score = fuzz.ratio(nom_norm, _normalize_name(item.get("nom", "")))
        if score > best_score:
            best, best_score = item, score
    if best_score >= threshold:
        return best
    return None


def upsert_startup(existing: list[dict], new_startup: dict) -> list[dict]:
    """Insère `new_startup`, ou fusionne avec une entrée existante si elle
    représente probablement la même startup (champs vides complétés par
    les nouvelles données, sans écraser une donnée déjà présente)."""
    match = find_existing_match(new_startup, existing)
    if match is None:
        existing.append(new_startup)
        return existing

    for key, value in new_startup.items():
        if value in (None, "", [], {}):
            continue
        current = match.get(key)
        if current in (None, "", [], {}):
            match[key] = value
        elif isinstance(current, list) and isinstance(value, list):
            for v in value:
                if v not in current:
                    current.append(v)
    # garde une trace de toutes les sources qui ont contribué à la fiche
    sources = set(match.get("sources_contributrices", [match.get("source", "")]))
    sources.add(new_startup.get("source", ""))
    match["sources_contributrices"] = sorted(s for s in sources if s)
    return existing


def merge_all(items: list[dict]) -> list[dict]:
    """Dédoublonne une liste brute de startups (utile en fin de scraping
    multi-sources avant sauvegarde)."""
    result: list[dict] = []
    for item in items:
        result = upsert_startup(result, item)
    return result