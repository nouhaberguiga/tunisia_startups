from __future__ import annotations

import argparse
import asyncio
import time
import json

import config
from enricher import enrich_startup_free
from llm_enriche import enrich_with_llm
from models import StartupBase, StartupEnriched
from registry import get_scraper
from storage import load_json, merge_all, save_json
from pdf_llm_extractor import run_pdf_llm_extraction


# =========================
# SAFE CALL
# =========================
def safe_call(label: str, func, *args, default=None, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[{label}] skipped: {e}")
        return default


# =========================
# LOAD SOURCES
# =========================
def load_sources():
    with open(config.SOURCES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    sources = data.get("sources", data if isinstance(data, list) else [])
    return [s for s in sources if s.get("enabled", True)]


# =========================
# VALIDATION (IMPORTANT FIX 🔥)
# =========================
def validate(item: dict):
    try:
        if not item or not item.get("nom"):
            return None

        return item

    except Exception as e:
        print("[validate skip]", e)
        return None


# =========================
# NORMALIZER
# =========================
def normalize(item: dict, source: str):
    return {
        "nom": item.get("nom") or item.get("name"),
        "website": item.get("website") or item.get("site_web"),
        "description": item.get("description"),
        "secteur": item.get("secteur"),
        "source": source,
    }


# =========================
# SCRAPE ALL SOURCES
# =========================
async def scrape_sources(selected=None):
    selected = set(selected or [])
    sources = load_sources()

    if selected:
        sources = [
            s for s in sources
            if s.get("name") in selected or s.get("scraper") in selected
        ]

    all_data = []

    # =========================
    # PDF EXTRACTION (FIXED 🔥)
    # =========================
    print("\n[source] tunisie_pdf")

    pdf_raw = safe_call(
        "pdf",
        run_pdf_llm_extraction,
        default=[]
    )

    cleaned_pdf = []

    for item in pdf_raw:
        if not isinstance(item, dict):
            continue

        item = normalize(item, "tunisie_pdf")

        v = validate(item)
        if v:
            cleaned_pdf.append(v)

    print(f"  -> {len(cleaned_pdf)} startups (PDF)")
    all_data.extend(cleaned_pdf)

    # =========================
    # WEB SOURCES
    # =========================
    for src in sources:
        name = src.get("name", "source")
        url = src.get("url")

        if not url:
            continue

        print(f"\n[source] {name}")

        scraper = get_scraper(src.get("scraper", "generic"))

        try:
            raw = await scraper.scrape_async(url, src)
        except Exception as e:
            print(f"  [scraper error] {e}")
            continue

        cleaned = []

        for item in raw:
            structured = normalize(item, name)
            v = validate(structured)

            if v:
                cleaned.append(v)

        print(f"  -> {len(cleaned)} startups")

        all_data.extend(cleaned)

        if config.SCRAPE_DELAY_SECONDS > 0:
            await asyncio.sleep(config.SCRAPE_DELAY_SECONDS)

    return merge_all(all_data)


# =========================
# SAVE BASE
# =========================
def save_base(data):
    existing = load_json(config.STARTUPS_BASE_FILE)
    merged = merge_all(existing + data)

    save_json(config.STARTUPS_BASE_FILE, merged)

    print(f"\n[BASE] {len(merged)} startups sauvegardées")
    return merged


# =========================
# ENRICH ONE
# =========================
def enrich_one(startup: dict, use_web: bool, use_llm: bool):
    enriched = StartupEnriched(**startup).model_dump()

    enriched = safe_call(
        "free_enrich",
        enrich_startup_free,
        enriched,
        use_web=use_web,
        default=enriched
    )

    if use_llm and config.OPENROUTER_API_KEY:
        llm = safe_call(
            "llm_enrich",
            enrich_with_llm,
            enriched,
            default={}
        )

        if isinstance(llm, dict):
            enriched.update(llm)

    return StartupEnriched(**enriched).model_dump()


# =========================
# ENRICH ALL
# =========================
def enrich_all(startups, max_startups, delay, use_web, use_llm):
    existing = load_json(config.STARTUPS_ENRICHED_FILE)

    by_id = {x["id"]: x for x in existing if x.get("id")}
    done = set(by_id.keys())

    selected = startups[:max_startups] if max_startups > 0 else startups

    for i, s in enumerate(selected, 1):

        sid = s.get("id") or f"st_{i}_{abs(hash(s.get('nom','')))}"
        s["id"] = sid

        if sid in done:
            print(f"[enrich] {i}/{len(selected)} {s.get('nom')} (cached)")
            continue

        print(f"[enrich] {i}/{len(selected)} {s.get('nom')}")

        try:
            by_id[sid] = enrich_one(s, use_web, use_llm)
            done.add(sid)
        except Exception as e:
            print(f"[error] {e}")

        save_json(config.STARTUPS_ENRICHED_FILE, list(by_id.values()))

        if delay > 0:
            time.sleep(delay)

    result = list(by_id.values())

    save_json(config.STARTUPS_ENRICHED_FILE, result)

    print(f"\n[FINAL] {len(result)} startups enrichies")

    return result


# =========================
# PIPELINE
# =========================
async def run_pipeline(args):
    print("\n=== CONFIG ===")
    config.check_config()

    print(f"\nMODE={args.mode} | web={args.web} | llm={args.llm} | max={args.max}")

    base = load_json(config.STARTUPS_BASE_FILE)

    if args.mode in ("scrape", "all"):
        scraped = await scrape_sources(args.source)
        base = save_base(scraped)

    if args.mode in ("enrich", "all"):
        if not base:
            print("[ERROR] No data found")
            return

        enrich_all(
            base,
            max_startups=args.max,
            delay=args.delay,
            use_web=args.web,
            use_llm=args.llm,
        )


# =========================
# CLI
# =========================
def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--mode", choices=["scrape", "enrich", "all"], default="scrape")
    parser.add_argument("--source", action="append")
    parser.add_argument("--max", type=int, default=30)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--llm", action="store_true")

    return parser.parse_args()


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    asyncio.run(run_pipeline(parse_args()))