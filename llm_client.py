import requests
import config
import json
import re

class OpenRouterError(Exception):
    pass


def call_openrouter(prompt, model=None, max_tokens=500):
    if not config.OPENROUTER_API_KEY:
        raise OpenRouterError("No API key")

    payload = {
        "model": model or config.OPENROUTER_MODEL,
        "messages": [{"role":"user","content":prompt}],
        "max_tokens": max_tokens
    }

    try:
        r = requests.post(
            config.OPENROUTER_URL,
            headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"},
            json=payload,
            timeout=20
        )
    except Exception as e:
        raise OpenRouterError(str(e))

    if r.status_code == 429:
        return ""   # IMPORTANT: fallback silencieux

    if r.status_code != 200:
        return ""

    return r.json()["choices"][0]["message"]["content"]


def extract_json(text: str):
    if not text:
        return {}

    text = text.strip()
    text = re.sub(r"```.*?```", "", text, flags=re.S)

    try:
        return json.loads(text)
    except:
        return {}