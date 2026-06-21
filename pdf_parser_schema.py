def adapt_pdf_startup(item: dict):
    return {
        "nom": item.get("name") or item.get("nom"),
        "annee": item.get("year") or item.get("year_establishment"),
        "secteur": item.get("sector") or item.get("activity_sector"),
        "website": item.get("website"),
        "fondateurs": item.get("founders"),
        "email": item.get("email"),
        "adresse": item.get("address"),
        "description_fr": item.get("activity_fr"),
        "description_en": item.get("activity_en"),
        "tech_fr": item.get("tech_fr"),
        "tech_en": item.get("tech_en"),
        "originalite_fr": item.get("originality_fr"),
        "originalite_en": item.get("originality_en"),
        "source": "tunisie_pdf"
    }