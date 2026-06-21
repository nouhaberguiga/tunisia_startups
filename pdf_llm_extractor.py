from __future__ import annotations

import fitz
import re
import config


def clean(t: str) -> str:
    t = t.replace("\n", " ")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def is_noise(text: str) -> bool:
    """Filtre les faux résultats"""
    if len(text) < 3:
        return True
    if text.lower() in ["fr", "en", "activity", "activite", "originality"]:
        return True
    if text.isdigit():
        return True
    return False


def run_pdf_llm_extraction():
    pdf = fitz.open(config.PDF_FILE)

    text = ""
    for page in pdf:
        text += page.get_text("text") + "\n"

    # 🔥 1. découpage intelligent par nom + année
    pattern = r"([A-Z][A-Z0-9\s\-\.\&\/]{2,80})\s*\((19\d{2}|20\d{2})\)"
    matches = list(re.finditer(pattern, text))

    print(f"[PDF] startups potentielles détectées: {len(matches)}")

    startups = []

    for i, m in enumerate(matches):

        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        block = text[start:end]
        block = clean(block)

        name = clean(m.group(1))
        year = m.group(2)

        # 🔥 filtre anti bruit
        if is_noise(name):
            continue

        # secteur
        sector = ""
        s = re.search(r"Secteur d’activité\s*/\s*Sector\s*:\s*(.+?)(?:\.|Activity|FR|EN|Fondateur)", block)
        if s:
            sector = clean(s.group(1))

        # website
        website = ""
        w = re.search(r"([a-zA-Z0-9\-]+\.(?:com|tn|io|co|net))", block)
        if w:
            website = w.group(1)

        # email
        email = ""
        e = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", block)
        if e:
            email = e.group(0)

        # description (FR + EN fusion)
        desc = ""
        d = re.search(r"Activité(.*?)(Aspect Technologique|Technological Aspect|Originality|FR|EN)", block)
        if d:
            desc = clean(d.group(1))

        # filtre final (évite les fragments comme "les tests")
        if len(name) < 5 or len(name.split()) > 12:
            continue

        startups.append({
            "nom": name,
            "annee_creation": year,
            "secteur": sector,
            "site_web": website,
            "email": email,
            "description": desc
        })

    print(f"[PDF] startups valides: {len(startups)}")
    return startups