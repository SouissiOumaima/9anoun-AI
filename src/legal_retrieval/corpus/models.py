"""Internal corpus models of DS2 (sources and articles).

The contract with OTHER roles is NOT here: it is the JSON Schema in
data/mock_cards/schemas/legal_retrieval_*.v0.schema.json (team convention).
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel


class SourceType(str, Enum):
    """Position of a text in the Tunisian labour-law hierarchy."""

    CODE = "code"  # Code du travail
    DECRET = "decret"  # implementing orders
    CONVENTION_CADRE = "convention_cadre"  # framework collective agreement
    CONVENTION_SECTORIELLE = "convention_sectorielle"  # sectoral agreements
    BAREME_SALAIRE_MINIMUM = "bareme_salaire_minimum"  # SMIG / SMAG grids
    CONVENTION_INTERNATIONALE = "convention_internationale"


class ArticleStatus(str, Enum):
    """Legal status of an article version."""

    EN_VIGUEUR = "en_vigueur"  # in force
    MODIFIE = "modifie"  # replaced by a newer version
    ABROGE = "abroge"  # repealed
    INCONNU = "inconnu"  # not yet annotated (Sprint 1 default)


class LegalSource(BaseModel):
    """One official legal text (a whole code, agreement or wage grid)."""

    source_id: str  # stable slug, e.g. "CCS-BANQUES"
    title_ar: str  # original Arabic title (from file name for now)
    source_type: SourceType
    sector: str | None = None  # None = applies to all sectors
    language: str = "ar"
    official_reference: str | None = None  # JORT reference, filled in Sprint 2
    publication_date: date | None = None  # filled in Sprint 2
    effective_date: date | None = None  # filled in Sprint 2 (≠ publication!)
    file_name: str  # raw file the source was ingested from


class LegalArticle(BaseModel):
    """One article version = the atomic retrieval unit (one chunk)."""

    article_id: str  # stable versioned id, e.g. "CCS-BANQUES-ART-14-v1"
    source_id: str  # parent LegalSource
    article_number: int | None  # None when the label could not be parsed
    article_label: str  # label as written, e.g. "الفصل 14"
    text: str  # exact text as in the source (used for citations)
    text_normalized: str  # normalized text (used for keyword search only)
    hierarchy_path: str  # e.g. "اتفاقية مشتركة قطاعية > البنوك > الفصل 14"
    page_start: int | None = None  # page where the article starts (citations)
    version: int = 1
    effective_from: date | None = None  # temporal filter (Sprint 2/5)
    effective_to: date | None = None  # None = still in force
    status: ArticleStatus = ArticleStatus.INCONNU
    sector: str | None = None  # copied from source for metadata filtering
    language: str = "ar"
    # Where `text` comes from: "ocr_json" (Arabic words OK, digits unreliable,
    # see DECISIONS D1) or "pdf_text_layer" (digits OK, Arabic in PUA glyphs).
    text_source: str = "ocr_json"
    # Numbers of `text` NOT found in the PDF text layer of the same file.
    # Non-empty -> never cite these figures without checking the PDF.
    # None = check not run (no PDF available).
    numbers_unverified: list[str] | None = None
