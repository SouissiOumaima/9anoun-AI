"""Contrat d'interface DS3 (Document Intelligence) <-> DS1 (Orchestrateur), version ds3.v1.

Le contrat est indépendant du transport : les mêmes objets JSON circulent
aujourd'hui par appel Python direct, et pourront circuler demain par HTTP.

Règles du contrat :
- tous les montants sont des chaînes à 3 décimales ("344.500"), à lire en Decimal ;
- chaque champ extrait porte sa confiance, sa position et un identifiant de citation ;
- une valeur illisible vaut null avec une raison : DS3 ne devine jamais un chiffre ;
- tout résultat porte le card_id : un document n'est jamais servi hors de sa carte.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION: Final = "ds3.v1"

Operation = Literal["analyze_document", "extract_wage_grid"]
Status = Literal["success", "partial", "error"]
Language = Literal["ar", "fr"]
CardType = Literal["company", "client", "case"]
DocumentType = Literal[
    "fiche_de_paie",
    "facture",
    "contrat_travail",
    "convention_collective",
    "piece_dossier",
    "inconnu",
]
ErrorCode = Literal[
    "INVALID_REQUEST",
    "UNSUPPORTED_OPERATION",
    "UNSUPPORTED_FORMAT",
    "FILE_EMPTY_OR_CORRUPTED",
    "FILE_TOO_LARGE",
    "ACCESS_DENIED",
    "UNREADABLE_DOCUMENT",
    "NO_TABLE_FOUND",
    "TIMEOUT",
    "INTERNAL_ERROR",
]
UnreadableReason = Literal["zone_illisible", "valeur_incoherente", "absent_du_document"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- requête


class RequestContext(_Strict):
    """Contexte imposé par le backend (DS1). DS3 ne l'invente jamais."""

    organization_id: str
    user_id: str
    role: Literal["lawyer", "accountant", "admin"]
    card_id: str
    card_type: CardType


class DocumentRef(_Strict):
    document_id: str
    card_id: str = Field(description="Carte à laquelle appartient le document.")
    file_name: str
    mime_type: str
    storage_ref: str = Field(description="Chemin ou clé de stockage Tradrly, jamais le contenu.")


class RequestOptions(_Strict):
    language_hint: list[Language] = Field(default_factory=lambda: list[Language](["ar", "fr"]))
    expected_type: DocumentType | None = None
    pages: list[int] | None = Field(default=None, description="Pages à traiter (1-based).")
    min_confidence: float = Field(default=0.80, ge=0.0, le=1.0)


class DS3Request(_Strict):
    contract_version: Literal["ds3.v1"] = CONTRACT_VERSION
    request_id: str
    operation: Operation
    context: RequestContext
    document: DocumentRef
    options: RequestOptions = Field(default_factory=RequestOptions)


# ---------------------------------------------------------------- réponse


class Position(_Strict):
    page: int = Field(ge=1)
    bbox: list[float] | None = Field(
        default=None, description="[x0, y0, x1, y1] en points PDF, origine en haut à gauche."
    )


class Citation(_Strict):
    citation_id: str
    document_id: str
    position: Position
    excerpt: str = Field(description="Texte exact lu à cet endroit, pour la vérification DS6.")


class ExtractedField(_Strict):
    value: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    citation_id: str | None
    unreadable_reason: UnreadableReason | None = None
    currency: Literal["TND"] | None = None


class TableCell(_Strict):
    row: int
    col: int
    value: str | None
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedTable(_Strict):
    table_id: str
    title: str | None
    citation_id: str
    n_rows: int
    n_cols: int
    cells: list[TableCell]


class DocumentAnalysis(_Strict):
    document_type: DocumentType
    document_type_confidence: float = Field(ge=0.0, le=1.0)
    languages: list[Language]
    page_count: int
    summary: str = Field(description="Résumé factuel, sans interprétation juridique.")
    fields: dict[str, ExtractedField]
    tables: list[ExtractedTable] = Field(default_factory=list)


class GradeInfo(_Strict):
    grade: int
    duration_years: int
    seniority: str


class WageValue(_Strict):
    category: int
    grade: int
    amount: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    unreadable_reason: UnreadableReason | None = None


class WageGrid(_Strict):
    title: str
    sector_ar: str
    effective_date: str = Field(description="Date d'effet ISO (AAAA-MM-JJ).")
    unit: Literal["TND/mois"]
    legal_basis: str
    citation_id: str
    complete: bool = Field(description="False si toutes les cases n'ont pas été extraites.")
    grades: list[GradeInfo]
    values: list[WageValue]
    note: str | None = None


class DS3Error(_Strict):
    code: ErrorCode
    message_fr: str
    message_ar: str
    retryable: bool


class ResponseMeta(_Strict):
    pipeline_version: str
    mode: Literal["mock", "real"]
    processing_ms: int


class DS3Response(_Strict):
    contract_version: Literal["ds3.v1"] = CONTRACT_VERSION
    request_id: str
    operation: str
    status: Status
    card_id: str | None
    document_id: str | None
    result: DocumentAnalysis | WageGrid | None
    citations: list[Citation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: DS3Error | None = None
    meta: ResponseMeta
