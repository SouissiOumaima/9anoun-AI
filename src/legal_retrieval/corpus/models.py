"""Internal corpus models of DS2 (sources and articles).

The contract with OTHER roles is NOT here: it is the JSON Schema in
data/mock_cards/schemas/legal_retrieval_*.v0.schema.json (team convention).
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, model_validator


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


class DocumentKind(str, Enum):
    """Nature d'un document du corpus (D74).

    Un POINTEUR n'est pas du droit : c'est le renvoi vers une grille de salaires
    que la livraison ne transcrit pas. Il est indexable pour etre TROUVE, jamais
    citable comme source d'un montant.
    """

    ARTICLE = "article"    # الفصل
    ANNEXE = "annexe"      # الملحق : meme forme qu'un article, espace -ANX-
    SECTION = "section"    # other_sections retenue, espace -SEC-
    POINTEUR = "pointeur"  # excluded_salary_tables, espace -PTR-


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
    # --- Sprint 2 (reader of the Tradrly sections, D20) ---
    part: int = 1  # >1 when the numbering restarts inside one file (Assurance)
    modified: bool = False  # "(جديد)": consolidated text of a modified article
    amended_by: str | None = None  # avenant id, e.g. "CCS-BTP-AVENANT-5"
    # False when the text before modification is NOT in the corpus (R6, D17)
    previous_version_available: bool = True
    # how the article was found: "section" | "split_from_section" | "abrogation_line"
    origin: str = "section"
    # --- Sprint 5 (lecteur de l'archive Tradrly, D73 et D74) ---
    doc_kind: DocumentKind = DocumentKind.ARTICLE
    # False interdit de presenter ce document comme la source d'un contenu.
    # Toujours force a False pour un pointeur, voir le validateur plus bas.
    citable: bool = True
    # Derniere page quand le document en couvre plusieurs (CC-CADRE-ART-2 : 3 et 4).
    page_end: int | None = None
    # D'ou vient effective_from : "convention", "avenant:<n>" ou "avenant:<n>:jort".
    # Permet de dire « depuis le 1er mai 2011, par l'avenant n° 7 » plutot qu'une
    # date sans origine.
    effective_from_origin: str | None = None
    # SHA-256 du condense dont ce document est issu. L'archive est confidentielle
    # et n'est pas versee au depot : cette empreinte est ce qui reste pour verifier
    # qu'un corpus committe correspond bien a une livraison donnee (D75).
    source_digest_sha256: str | None = None

    @model_validator(mode="after")
    def _un_pointeur_n_est_jamais_citable(self) -> "LegalArticle":
        """Interdit structurellement de citer un pointeur comme source de contenu.

        La regle vit ici et non chez l'appelant : un consommateur qui oublierait
        de regarder doc_kind trouvera quand meme citable = False.
        """
        if self.doc_kind is DocumentKind.POINTEUR:
            self.citable = False
        return self
