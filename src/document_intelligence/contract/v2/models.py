"""Contrat d'interface DS3 (Document Intelligence) <-> DS1 (Orchestrateur), version ds3.v2.

La v2 aligne l'enveloppe de réponse sur le schéma commun (common.v0 / common.v1 en préparation) :
- statuts ok / refus / erreur (un résultat partiel est un « ok » avec result.complete = false) ;
- refus { code, message_fr, message_ar } et erreur { type, message_fr, message_ar } ;
- citations de document à plat (document_citation), en attendant leur ajout dans common.v1 ;
- mode ("mock" / "live") à la racine et computed_by obligatoire.

Règles inchangées depuis la v1 :
- tous les montants sont des chaînes à 3 décimales ("424.100"), à lire en Decimal ;
- chaque champ extrait porte sa confiance et l'identifiant de sa citation ;
- une valeur illisible vaut null avec une raison : DS3 ne devine jamais un chiffre ;
- tout résultat porte le card_id : un document n'est jamais servi hors de sa carte.
"""

from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION: Final = "ds3.v2"

Operation = Literal["analyze_document", "extract_wage_grid"]
Status = Literal["ok", "refus", "erreur"]
Language = Literal["ar", "fr"]
Mode = Literal["mock", "live"]
ComputedBy = Literal["document_intelligence.mock", "document_intelligence.service"]
CardType = Literal["company", "client", "case"]
DocumentType = Literal[
    "fiche_de_paie",
    "facture",
    "contrat_travail",
    "convention_collective",
    "piece_dossier",
    "inconnu",
]
# Codes de refus de common.v0, plus ACCES_REFUSE (accepté par l'équipe, à ajouter dans common.v1).
RefusCode = Literal["SOURCE_MANQUANTE", "HORS_SCOPE", "PARAM_INVALIDE", "ACCES_REFUSE"]
# Code DS3 détaillé, gardé pour le diagnostic (champ d'extension ds3_code). Mêmes noms qu'en v1.
DS3Code = Literal[
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
ValueType = Literal["montant", "date", "entier", "enum", "texte"]
UnreadableReason = Literal["zone_illisible", "valeur_incoherente", "absent_du_document"]

MONTANT_PATTERN: Final = r"^-?[0-9]+\.[0-9]{3}$"
DATE_PATTERN: Final = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
_VALUE_PATTERNS: Final[dict[str, str]] = {
    "montant": MONTANT_PATTERN,
    "date": DATE_PATTERN,
    "entier": r"^-?[0-9]+$",
}


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
    contract_version: Literal["ds3.v2"] = CONTRACT_VERSION
    request_id: str = Field(min_length=1, max_length=128)
    case_id: str | None = Field(
        default=None, min_length=1, max_length=128, description="Dossier en cours, si la carte est une Case Card."
    )
    lang: Language = Field(description="Langue de la réponse attendue (résumé, messages).")
    operation: Operation
    context: RequestContext
    document: DocumentRef
    options: RequestOptions = Field(default_factory=RequestOptions)


# ---------------------------------------------------------------- réponse


class DocumentCitation(_Strict):
    """Source d'une valeur lue dans un document de carte (proposée pour common.v1)."""

    citation_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    bbox: list[float] | None = Field(
        min_length=4, max_length=4, description="[x0, y0, x1, y1] en points PDF, origine en haut à gauche."
    )
    excerpt: str = Field(description="Texte exact lu à cet endroit, pour la vérification DS6.")


class ExtractedField(_Strict):
    value: str | None
    value_type: ValueType
    confidence: float = Field(ge=0.0, le=1.0, description="Sans objet (0.0) quand le champ est absent.")
    citation_id: str | None
    unreadable_reason: UnreadableReason | None = None
    currency: Literal["TND"] | None = None

    @model_validator(mode="after")
    def _check_value(self) -> ExtractedField:
        if self.value is None:
            if self.unreadable_reason is None:
                raise ValueError("value = null exige une unreadable_reason")
            return self
        if self.unreadable_reason is not None:
            raise ValueError("unreadable_reason n'est permis que si value = null")
        pattern = _VALUE_PATTERNS.get(self.value_type)
        if pattern and not re.match(pattern, self.value):
            raise ValueError(f"valeur {self.value!r} non conforme au type {self.value_type}")
        return self


class PayLine(_Strict):
    """Ligne de prime ou d'indemnité imprimée sur la fiche de paie, telle quelle."""

    label: str
    amount: str | None = Field(pattern=MONTANT_PATTERN)
    confidence: float = Field(ge=0.0, le=1.0)
    citation_id: str | None
    unreadable_reason: UnreadableReason | None = None


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
    complete: bool = Field(
        description="False si au moins une valeur présente sur le document n'a pas pu être lue "
        "(zone_illisible ou valeur_incoherente). Un champ absent du document ne rend pas le résultat incomplet."
    )
    summary: str = Field(description="Résumé factuel, sans interprétation juridique.")
    fields: dict[str, ExtractedField]
    pay_lines: list[PayLine] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)


class GradeInfo(_Strict):
    grade: int
    duration_years: int
    seniority: str


class WageValue(_Strict):
    category: int
    grade: int
    amount: str | None = Field(pattern=MONTANT_PATTERN)
    confidence: float = Field(ge=0.0, le=1.0)
    unreadable_reason: UnreadableReason | None = None


class WageGrid(_Strict):
    title: str
    sector_ar: str
    sector_code: str | None = Field(
        default=None, description="Code de secteur du vocabulaire D21 ; null tant que la table n'est pas fixée."
    )
    effective_date: str = Field(pattern=DATE_PATTERN, description="Date d'effet ISO (AAAA-MM-JJ).")
    unit: Literal["TND/mois"]
    legal_basis: str
    citation_id: str
    complete: bool = Field(description="False si toutes les cases n'ont pas été extraites.")
    grades: list[GradeInfo]
    values: list[WageValue]
    note: str | None = None


class Refus(_Strict):
    code: RefusCode
    message_fr: str = Field(min_length=1)
    message_ar: str = Field(min_length=1)


class Erreur(_Strict):
    type: str
    message_fr: str = Field(min_length=1)
    message_ar: str = Field(min_length=1)


class ResponseMeta(_Strict):
    pipeline_version: str
    processing_ms: int


class DS3Response(_Strict):
    contract_version: Literal["ds3.v2"] = CONTRACT_VERSION
    request_id: str | None
    case_id: str | None = Field(default=None, description="Absent de la réponse JSON quand il n'y a pas de dossier.")
    status: Status
    refus: Refus | None
    erreur: Erreur | None = Field(default=None, description="Présent seulement si status = erreur.")
    computed_by: ComputedBy
    mode: Mode
    operation: str
    card_id: str | None
    document_id: str | None
    citations: list[DocumentCitation]
    result: DocumentAnalysis | WageGrid | None
    warnings: list[str] = Field(default_factory=list)
    ds3_code: DS3Code | None = Field(default=None, description="Code DS3 détaillé, pour le diagnostic.")
    retryable: bool | None = Field(default=None, description="Présent seulement si status = erreur.")
    meta: ResponseMeta

    @model_validator(mode="after")
    def _check_status(self) -> DS3Response:
        """Mêmes règles que l'enveloppe common.v0 (« Citation ou silence »)."""
        if self.status == "ok":
            ok = self.result is not None and bool(self.citations) and self.refus is None and self.erreur is None
            if not ok:
                raise ValueError("status ok : result et au moins une citation, ni refus ni erreur")
        elif self.status == "refus":
            if self.refus is None or self.erreur is not None or self.result is not None or self.citations:
                raise ValueError("status refus : refus seul, sans result, citation ni erreur")
        elif self.erreur is None or self.refus is not None or self.result is not None or self.citations:
            raise ValueError("status erreur : erreur seule, sans result, citation ni refus")
        if (self.retryable is not None) != (self.status == "erreur"):
            raise ValueError("retryable est présent si et seulement si status = erreur")
        return self

    def to_json(self) -> dict[str, object]:
        """JSON à renvoyer : sans les clés erreur / retryable / case_id quand elles ne s'appliquent pas."""
        data = self.model_dump(mode="json")
        for key in ("erreur", "retryable", "case_id"):
            if data[key] is None:
                del data[key]
        return data
