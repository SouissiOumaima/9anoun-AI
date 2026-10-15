"""Registry of the legal sources provided by Tradrly.

Files are matched by a keyword contained in their (normalized) name, so the
long Arabic file names do not need to be typed exactly.
Dates / JORT references are None until Sprint 2 (metadata schema).
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import SourceType
from .normalize import normalize_arabic


@dataclass(frozen=True)
class SourceEntry:
    """Static metadata for one source file."""

    source_id: str
    keyword: str  # keyword WITHOUT "ال": "للتأمين" does not contain "التامين"
    source_type: SourceType
    sector: str | None
    hierarchy_label: str  # human label used in hierarchy_path


_SECTORAL = SourceType.CONVENTION_SECTORIELLE
_CCS = "اتفاقية مشتركة قطاعية"

# ORDER MATTERS: the first matching keyword wins.
REGISTRY: tuple[SourceEntry, ...] = (
    SourceEntry("SMIG-GRILLE", "الأجر الأدنى", SourceType.BAREME_SALAIRE_MINIMUM,
                None, "الأجر الأدنى المضمون"),
    SourceEntry("CC-CADRE", "الاطارية", SourceType.CONVENTION_CADRE,
                None, "الاتفاقية المشتركة الإطارية"),
    SourceEntry("CCS-GARDIENNAGE", "حراسة", _SECTORAL,
                "gardiennage_securite_transport_fonds", _CCS),
    SourceEntry("CCS-CONSTRUCTION-METALLIQUE", "بناء المعدني", _SECTORAL,
                "construction_metallique", _CCS),
    SourceEntry("CCS-BTP", "بناء والاشغال", _SECTORAL, "btp", _CCS),
    SourceEntry("CCS-ASSOCIATIONS", "جمعيات", _SECTORAL, "associations", _CCS),
    SourceEntry("CCS-ASSURANCE", "تامين", _SECTORAL, "assurance", _CCS),
    SourceEntry("CCS-ENSEIGNEMENT-PRIVE", "تعليم", _SECTORAL,
                "enseignement_prive", _CCS),
    SourceEntry("CCS-BANQUES", "البنوك", _SECTORAL, "banques", _CCS),
)


def match_source(file_name: str) -> SourceEntry | None:
    """Return the registry entry whose keyword appears in `file_name`."""
    name = normalize_arabic(file_name)  # handles تأمـين / اتفاقيّة variants
    for entry in REGISTRY:
        if normalize_arabic(entry.keyword) in name:
            return entry
    return None
