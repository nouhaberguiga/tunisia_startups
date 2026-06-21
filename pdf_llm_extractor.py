from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import fitz

import config


SOURCE_NAME = "tunisie_pdf"

NAME_RE = re.compile(r"^(.+?)\s*\(((?:19|20)\d{2})\)$")
SECTOR_RE = re.compile(r"Secteur d.?activit[eé]\s*/\s*Sector\s*:\s*(.+)", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
DOMAIN_RE = re.compile(
    r"\b(?:https?://)?(?:www\.)?[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+/?\b"
)

LIGATURES = str.maketrans(
    {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
    }
)


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text.translate(LIGATURES))
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def clean_inline(text: str | None) -> str:
    return re.sub(r"\s+", " ", clean(text)).strip(" -")


def is_catalog_noise(text: str) -> bool:
    value = clean_inline(text).lower()
    if not value:
        return True
    noise_exact = {
        "fr",
        "en",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
        "catalogue des startups tech tunisiennes",
        "tunisian tech startups catalog",
        "apii / cidt - september 2022",
    }
    if value in noise_exact or value.isdigit():
        return True
    return "catalogue des" in value or "startupstech" in value


def is_name_line(text: str) -> bool:
    line = clean_inline(text.splitlines()[0] if text else "")
    if is_catalog_noise(line):
        return False
    return bool(NAME_RE.match(line))


def parse_name_year(text: str) -> tuple[str, str | None]:
    line = clean_inline(text.splitlines()[0])
    match = NAME_RE.match(line)
    if not match:
        return line, None
    return clean_inline(match.group(1)), match.group(2)


def page_blocks(page) -> list[dict]:
    blocks = []
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
        text = clean(text)
        if not text or is_catalog_noise(text):
            continue
        blocks.append(
            {
                "x0": float(x0),
                "y0": float(y0),
                "x1": float(x1),
                "y1": float(y1),
                "text": text,
            }
        )
    return blocks


def extract_sector(text: str) -> str:
    for line in clean(text).splitlines():
        match = SECTOR_RE.search(clean_inline(line))
        if match:
            return clean_inline(match.group(1))
    return ""


def website_from_text(text: str) -> str:
    ignored_domains = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com"}

    for match in DOMAIN_RE.finditer(clean_inline(text)):
        site = match.group(0).strip(".").lower()
        if "@" in site:
            continue
        if site in ignored_domains:
            continue
        if site.endswith(
            (
                ".ai",
                ".co",
                ".com",
                ".digital",
                ".healthcare",
                ".io",
                ".net",
                ".org",
                ".pro",
                ".tech",
                ".tn",
            )
        ):
            return site
    return ""


def extract_website(row_blocks: list[dict]) -> str:
    ignored_words = (
        "Activité",
        "Activity",
        "Fondateur",
        "Founder",
        "Adresse",
        "Address",
    )

    for block in sorted(row_blocks, key=lambda b: (b["y0"], b["x0"])):
        text = block["text"]
        if EMAIL_RE.search(text) or any(word in text for word in ignored_words):
            continue
        site = website_from_text(text)
        if site:
            return site
    return ""


def split_contact(text: str) -> tuple[list[str], str, str]:
    lines = [clean_inline(line) for line in text.splitlines() if clean_inline(line)]
    email = ""
    email_index = -1

    for index, line in enumerate(lines):
        match = EMAIL_RE.search(line)
        if match:
            email = match.group(0)
            email_index = index
            break

    if email_index < 0:
        return [], "", ""

    founder_text = " ".join(lines[:email_index])
    address = " ".join(lines[email_index + 1 :])
    founders = [
        clean_inline(part)
        for part in re.split(r"\s*/\s*|\s+&\s+|\s+ et \s+", founder_text)
        if clean_inline(part)
    ]
    return founders, email, address


def strip_section_label(text: str, labels: tuple[str, ...]) -> str:
    value = clean_inline(text)
    for label in labels:
        value = re.sub(
            rf"(^|[.!?]\s+|-\s+){re.escape(label)}\s+",
            r"\1",
            value,
            flags=re.IGNORECASE,
        )
    return clean_inline(value)


def extract_description(row_blocks: list[dict], english: bool = False) -> str:
    if english:
        labels = ("Activity", "Technological Aspect", "Originality")
        candidates = [b for b in row_blocks if b["x0"] >= 205 and "Activity" in b["text"]]
    else:
        labels = ("Activité", "Aspect Technologique", "Originalité")
        candidates = [b for b in row_blocks if b["x0"] < 205 and "Activité" in b["text"]]

    if not candidates:
        return ""

    block = sorted(candidates, key=lambda b: (b["y0"], b["x0"]))[0]
    return strip_section_label(block["text"], labels)


def extract_startup_from_row(row_blocks: list[dict], name_block: dict) -> dict | None:
    name, year = parse_name_year(name_block["text"])
    row_text = "\n".join(block["text"] for block in row_blocks)

    sector = extract_sector(row_text)
    founders, email, address = [], "", ""

    contact_blocks = [block for block in row_blocks if EMAIL_RE.search(block["text"])]
    if contact_blocks:
        contact_block = sorted(contact_blocks, key=lambda b: (b["y0"], b["x0"]))[0]
        founders, email, address = split_contact(contact_block["text"])

    website = extract_website(row_blocks)
    description_fr = extract_description(row_blocks, english=False)
    description_en = extract_description(row_blocks, english=True)

    if not name or not sector:
        return None

    return {
        "nom": name,
        "annee_creation": year,
        "secteur": sector,
        "website": website or None,
        "site_web": website or None,
        "email": email or None,
        "adresse": address or None,
        "fondateurs": founders,
        "description": description_fr or description_en,
        "description_fr": description_fr,
        "description_en": description_en,
        "source": SOURCE_NAME,
    }


def extract_page_startups(page) -> list[dict]:
    blocks = page_blocks(page)
    name_blocks = sorted(
        [block for block in blocks if is_name_line(block["text"])],
        key=lambda block: block["y0"],
    )

    startups = []
    for index, name_block in enumerate(name_blocks):
        start_y = name_block["y0"] - 1
        end_y = name_blocks[index + 1]["y0"] - 1 if index + 1 < len(name_blocks) else 10_000
        row_blocks = [
            block
            for block in blocks
            if start_y <= block["y0"] < end_y and block["x0"] >= 25
        ]
        startup = extract_startup_from_row(row_blocks, name_block)
        if startup:
            startups.append(startup)

    return startups


def dedupe_by_name(items: list[dict]) -> list[dict]:
    result = []
    seen = set()
    for item in items:
        key = re.sub(r"[^a-z0-9]+", "", item["nom"].lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def run_pdf_llm_extraction() -> list[dict]:
    pdf_path = Path(config.PDF_FILE)
    if not pdf_path.is_absolute():
        pdf_path = Path(config.BASE_DIR) / pdf_path

    startups: list[dict] = []
    with fitz.open(pdf_path) as pdf:
        for page in pdf:
            startups.extend(extract_page_startups(page))

    startups = dedupe_by_name(startups)
    print(f"[PDF] startups extraites: {len(startups)}")
    return startups
