# Workflow Tunisia Startups

Objectif: collecter un maximum de startups en Tunisie depuis plusieurs sources, nettoyer les donnees, dedupliquer, enrichir, puis stocker une base propre en JSON/MongoDB.

## Pipeline

```text
SEEDS
  -> CRAWLING
  -> CLEANING
  -> FILTERING
  -> EXTRACTION LOCALE
  -> AI EXTRACTION SI NECESSAIRE
  -> ENRICHMENT
  -> DEDUPLICATION
  -> DATABASE
  -> EXPANSION LOOP
```

## Modes

Collecte gratuite sans API externe:

```powershell
venv\Scripts\python.exe main.py --mode free
```

Collecte complete avec les cles disponibles:

```powershell
venv\Scripts\python.exe main.py --mode collect
```

Test rapide:

```powershell
venv\Scripts\python.exe main.py --mode fast
```

URL unique:

```powershell
venv\Scripts\python.exe main.py --url https://startupact.tn/startups
```

## Cles optionnelles

Dans `.env`:

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=mistralai/mistral-7b-instruct:free
TAVILY_API_KEY=
HUNTER_API_KEY=
MONGODB_URI=
```

Sans cle, le mode `free` utilise uniquement:

- seeds dans `sources.py`
- `httpx`
- Playwright/crawl4ai fallback
- extraction HTML structuree
- regex et heuristiques
- deduplication
- stockage JSON/CSV

Avec cles, le mode `collect` ajoute:

- Tavily pour decouvrir de nouvelles pages
- OpenRouter gratuit comme fallback LLM
- Hunter pour emails publics par domaine
- MongoDB si `MONGODB_URI` existe

## Fichiers principaux

- `sources.py`: seeds, annuaires, medias, requetes Tavily/Google indirectes.
- `crawler.py`: crawl httpx, Playwright, crawl4ai, liens internes, DNS, anti-bot doux.
- `filter.py`: garde seulement les pages utiles.
- `extractor.py`: extraction locale HTML/regex puis LLM si necessaire.
- `Enricher.py`: Tavily, OpenRouter, Hunter, heuristiques.
- `Deduplicator.py`: fusion des doublons.
- `Database.py`: JSON/CSV ou MongoDB.
- `main.py`: orchestration des modes.
