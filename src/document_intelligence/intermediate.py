"""Représentation intermédiaire DS3 : le format commun entre la partie A (OCR) et la partie B.

Tout document, quelle que soit sa source, est converti dans ce format avant l'extraction
des champs par Gemini 3 :
- texte natif d'un PDF, d'un DOCX, d'un XLSX ou d'un CSV  -> lu par la partie B (source "natif") ;
- images et pages scannées                                -> lues par l'OCR de la partie A (source "ocr").

Chaque ligne garde sa page, sa position (bbox) et sa confiance, pour pouvoir citer
« page 2, zone [x0, y0, x1, y1] » dans la réponse finale.

Conventions :
- pages numérotées à partir de 1 ;
- bbox = [x0, y0, x1, y1] en points PDF, origine en haut à gauche ;
- confiance = 1.0 pour le texte natif (lu tel quel), valeur de l'OCR sinon.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

Source = Literal["natif", "ocr"]
LineLanguage = Literal["ar", "fr", "mixte", "inconnu"]
BBox = tuple[float, float, float, float]

INTERMEDIATE_VERSION: Final = "ds3.inter.v1"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextLine(_Strict):
    """Une ligne de texte lue dans le document."""

    line_id: str = Field(description="Identifiant unique, ex. 'p2_l5'.")
    page: int = Field(ge=1)
    text: str
    bbox: BBox
    confidence: float = Field(ge=0.0, le=1.0)
    source: Source
    language: LineLanguage


class TableCell(_Strict):
    row: int = Field(ge=0)
    col: int = Field(ge=0)
    text: str | None = Field(description="None si la case est illisible : on ne devine pas.")
    bbox: BBox
    confidence: float = Field(ge=0.0, le=1.0)


class Table(_Strict):
    table_id: str
    page: int = Field(ge=1)
    bbox: BBox
    n_rows: int = Field(ge=0)
    n_cols: int = Field(ge=0)
    source: Source
    cells: list[TableCell]


ZoneReason = Literal["image", "texte_illisible"]


class PendingZone(_Strict):
    """Zone repérée mais pas encore lue : à passer à l'OCR (partie A).

    - reason = "image" : une image (tableau collé en image, scan) ;
    - reason = "texte_illisible" : du texte natif inutilisable, par exemple de l'arabe stocké
      en caractères Unicode « Private Use » (U+F2xx), comme dans les PDF du corpus Tradrly.
    """

    zone_id: str
    page: int = Field(ge=1)
    bbox: BBox
    reason: ZoneReason = "image"


class PageContent(_Strict):
    page: int = Field(ge=1)
    width: float
    height: float
    kind: Literal["texte", "mixte", "image", "vide"]
    lines: list[TextLine] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    pending_zones: list[PendingZone] = Field(default_factory=list)


class IntermediateDocument(_Strict):
    version: Literal["ds3.inter.v1"] = INTERMEDIATE_VERSION
    document_id: str
    file_name: str
    page_count: int = Field(ge=0)
    reader: str = Field(description="Lecteur qui a produit le document, ex. 'pdf_natif-0.1'.")
    pages: list[PageContent]
    warnings: list[str] = Field(default_factory=list)

    def full_text(self) -> str:
        """Texte complet, page par page, avec l'identifiant de chaque ligne.

        C'est ce texte qui est envoyé à Gemini 3 : les identifiants [p1_l3] lui permettent
        de dire d'où vient chaque valeur, et nous de retrouver la page et la bbox.
        """
        parts: list[str] = []
        for page in self.pages:
            parts.append(f"=== Page {page.page} ===")
            parts.extend(f"[{line.line_id}] {line.text}" for line in page.lines)
            for zone in page.pending_zones:
                what = "zone image non lue" if zone.reason == "image" else "texte natif illisible"
                parts.append(f"[{zone.zone_id}] <{what}, en attente d'OCR>")
        return "\n".join(parts)

    def find_line(self, line_id: str) -> TextLine | None:
        """Retrouve une ligne par son identifiant (pour construire les citations)."""
        for page in self.pages:
            for line in page.lines:
                if line.line_id == line_id:
                    return line
        return None


def detect_language(text: str) -> LineLanguage:
    """Langue d'une ligne, d'après la proportion de lettres arabes et latines."""
    arabic = sum(1 for c in text if "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ")
    latin = sum(1 for c in text if c.isascii() and c.isalpha() or "À" <= c <= "ſ")
    total = arabic + latin
    if total == 0:
        return "inconnu"
    if arabic / total >= 0.8:
        return "ar"
    if latin / total >= 0.8:
        return "fr"
    return "mixte"


def is_unreadable_char(c: str) -> bool:
    """Caractère qui montre une couche texte cassée.

    - zones Unicode « Private Use » (U+E000–U+F8FF et plans 15–16) : glyphes sans vrai code,
      comme l'arabe des PDF du corpus (U+F2xx) ;
    - U+FFFD (caractère de remplacement) ;
    - caractères de contrôle (ex. U+0000), produits quand un glyphe n'a pas de code.
    """
    code = ord(c)
    if 0xE000 <= code <= 0xF8FF or code >= 0xF0000:
        return True
    if code == 0xFFFD:
        return True
    return code < 0x20 and c not in "\t\n\r"


UNREADABLE_LINE_RATIO = 0.2
"""Une ligne est illisible si au moins 20 % de ses caractères (hors espaces) sont cassés."""


def is_unreadable_line(text: str) -> bool:
    """True si la ligne ne peut pas être utilisée comme texte natif fiable."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    bad = sum(1 for c in chars if is_unreadable_char(c))
    return bad / len(chars) >= UNREADABLE_LINE_RATIO
