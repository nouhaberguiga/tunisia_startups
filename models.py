"""
models.py
----------
Schéma de données unique pour une startup, utilisé à toutes les étapes
du pipeline (scraping de base -> enrichissement -> export final).

On utilise Pydantic pour :
  - valider/normaliser les champs (ex: site web toujours en minuscule,
    sans espace, avec https://)
  - avoir un seul endroit où la "forme" d'une startup est définie
  - faciliter l'ajout de nouveaux champs plus tard sans casser le reste
"""

from __future__ import annotations
import re
import hashlib
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


def slugify(text: str) -> str:
    """Transforme un nom de startup en identifiant stable (utilisé comme id)."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def make_id(nom: str, source: str = "") -> str:
    """Identifiant déterministe basé sur le nom (+ source en secours si nom vide)."""
    base = nom or source or "unknown"
    h = hashlib.sha1(base.lower().encode("utf-8")).hexdigest()[:8]
    return f"{slugify(base)}-{h}"


class JobOffer(BaseModel):
    titre: Optional[str] = None
    source: Optional[str] = None       # ex: "tanitjobs", "indeed"
    url: Optional[str] = None
    date_publication: Optional[str] = None


class StartupBase(BaseModel):
    """Champs collectés lors de la PREMIERE passe (scraping des annuaires)."""

    id: str = ""
    nom: str
    secteur: Optional[str] = None
    domaine: Optional[str] = None          # catégorie large / sous-secteur
    description: Optional[str] = None
    site_web: Optional[str] = None
    ville: Optional[str] = None
    adresse: Optional[str] = None
    telephone: Optional[str] = None

    source: str = ""                       # nom de la source (ex: "thedot")
    source_url: str = ""                   # URL de la fiche/page d'origine
    date_collecte: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @field_validator("site_web")
    @classmethod
    def normalize_url(cls, v):
        if not v:
            return v
        v = v.strip()
        if not re.match(r"^https?://", v):
            v = "https://" + v
        return v.rstrip("/")

    @field_validator("nom")
    @classmethod
    def clean_nom(cls, v):
        return " ".join(v.split()).strip()

    def model_post_init(self, __context__) -> None:
        if not self.id:
            self.id = make_id(self.nom, self.source)


class StartupEnriched(StartupBase):
    """Champs ajoutés lors de la passe d'ENRICHISSEMENT."""

    email: Optional[str] = None
    emails_supplementaires: list[str] = Field(default_factory=list)
    linkedin_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    twitter_url: Optional[str] = None

    fondateurs: list[str] = Field(default_factory=list)
    annee_creation: Optional[str] = None
    nb_employes_estime: Optional[str] = None
    levee_de_fonds: Optional[str] = None

    offres_emploi: list[JobOffer] = Field(default_factory=list)

    tags: list[str] = Field(default_factory=list)
    notes_llm: Optional[str] = None
    sources_enrichissement: list[str] = Field(default_factory=list)
    date_enrichissement: Optional[str] = None

    def mark_enriched(self):
        self.date_enrichissement = datetime.utcnow().isoformat()