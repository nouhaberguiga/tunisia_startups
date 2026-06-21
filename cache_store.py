"""
cache_store.py
--------------
Petit cache JSON persistant pour eviter de refaire les memes recherches,
appels LLM et enrichissements a chaque execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import config


def _load_cache() -> dict:
    path = Path(config.CACHE_FILE)
    if not path.exists():
        return {}
    try:
        content = path.read_text(encoding="utf-8").strip()
        return json.loads(content) if content else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    path = Path(config.CACHE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def make_cache_key(namespace: str, *parts: Any) -> str:
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


def get_cached(namespace: str, *parts: Any):
    cache = _load_cache()
    return cache.get(make_cache_key(namespace, *parts))


def set_cached(namespace: str, value, *parts: Any):
    cache = _load_cache()
    cache[make_cache_key(namespace, *parts)] = value
    _save_cache(cache)
    return value
