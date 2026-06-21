import pdfplumber

PDF_PATH = "data/STARTUPSTECH.pdf"


def extract_text():
    text = ""

    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    return text


def parse_startups(text: str):
    startups = []

    blocks = text.split("\n\n")  # 🔥 IMPORTANT

    for block in blocks:
        block = block.strip()

        if len(block) < 80:
            continue

        # filtre anti bruit
        if "ministère" in block.lower():
            continue

        startups.append({
            "nom": block[:80],  # temporaire
            "source": "tunisie_pdf",
            "website": None
        })

    return startups
    startups = []

    lines = text.split("\n")

    for line in lines:
        line = line.strip()

        if len(line) < 3:
            continue

        # filtre simple
        if len(line) < 120 and "startup" not in line.lower():

            startups.append({
                "nom": line,          # 🔥 IMPORTANT FIX
                "source": "tunisie_pdf",
                "website": None
            })

    print(f"[PDF] {len(startups)} startups extraites")
    return startups


def run_pdf_scraper():
    text = extract_text()
    return parse_startups(text)