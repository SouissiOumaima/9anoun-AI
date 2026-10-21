"""Tests de la vérification des réponses de Gemini (étape 3 de l'extracteur DS3)."""

from __future__ import annotations

import pytest

from src.document_intelligence.extraction.verify import (
    RawField,
    canon,
    contains_value,
    verify_all,
    verify_field,
)
from src.document_intelligence.intermediate import IntermediateDocument, PageContent, PendingZone, TextLine


def _line(n: int, text: str, confidence: float = 1.0) -> TextLine:
    return TextLine(line_id=f"p1_l{n}", page=1, text=text, bbox=(72, 100 + 20 * n, 400, 115 + 20 * n),
                    confidence=confidence, source="natif", language="fr")


@pytest.fixture
def doc() -> IntermediateDocument:
    """Petite fiche de paie fictive au format intermédiaire."""
    page = PageContent(
        page=1, width=595, height=842, kind="mixte",
        lines=[
            _line(1, "Nom : Ahmed Ben Salah"),
            _line(2, "Salaire de base 424,100"),
            _line(3, "الصنف : 1 ب"),
            _line(4, " "),  # arabe cassé (Private Use), comme le corpus
            _line(5, "Horaire : 208 h"),
        ],
        pending_zones=[PendingZone(zone_id="p1_u1", page=1, bbox=(380, 420, 470, 440), reason="image")],
    )
    return IntermediateDocument(document_id="doc_test", file_name="paie.pdf", page_count=1,
                                reader="test", pages=[page])


def test_value_present_in_cited_line_is_accepted(doc: IntermediateDocument) -> None:
    result = verify_field("base_salary", RawField(raw="424,100", line_id="p1_l2"), doc)
    assert result.raw == "424,100"
    assert result.line is not None and result.line.line_id == "p1_l2"
    assert result.reason is None and result.warnings == []


def test_spaces_and_arabic_digits_do_not_prevent_matching(doc: IntermediateDocument) -> None:
    assert verify_field("base_salary", RawField(raw="٤٢٤٫١٠٠", line_id="p1_l2"), doc).reason is None
    assert verify_field("category", RawField(raw="1ب", line_id="p1_l3"), doc).reason is None


def test_invented_value_is_rejected(doc: IntermediateDocument) -> None:
    """Gemini « corrige » 424,100 en 424,200 : la valeur n'est pas dans la ligne, on la rejette."""
    result = verify_field("base_salary", RawField(raw="424,200", line_id="p1_l2"), doc)
    assert result.raw is None and result.line is None
    assert result.reason == "valeur_incoherente"
    assert "424,200" in result.warnings[0]


def test_value_cited_on_the_wrong_line_is_rejected(doc: IntermediateDocument) -> None:
    assert verify_field("base_salary", RawField(raw="424,100", line_id="p1_l1"), doc).reason == "valeur_incoherente"


def test_nonexistent_line_is_rejected(doc: IntermediateDocument) -> None:
    result = verify_field("base_salary", RawField(raw="424,100", line_id="p9_l99"), doc)
    assert result.reason == "valeur_incoherente" and "n'existe pas" in result.warnings[0]


def test_value_without_source_is_rejected(doc: IntermediateDocument) -> None:
    assert verify_field("base_salary", RawField(raw="424,100", line_id=None), doc).reason == "valeur_incoherente"


def test_null_answer_means_absent(doc: IntermediateDocument) -> None:
    result = verify_field("sub_category", RawField(raw=None, line_id=None), doc)
    assert result.reason == "absent_du_document" and result.warnings == []


def test_empty_string_counts_as_absent(doc: IntermediateDocument) -> None:
    assert verify_field("sub_category", RawField(raw="  ", line_id="p1_l1"), doc).reason == "absent_du_document"


def test_value_in_an_unread_image_zone_is_unreadable(doc: IntermediateDocument) -> None:
    result = verify_field("cnss_employee", RawField(raw=None, line_id="p1_u1"), doc)
    assert result.reason == "zone_illisible" and "zone non lue" in result.warnings[0]


def test_value_on_a_broken_text_line_is_unreadable(doc: IntermediateDocument) -> None:
    result = verify_field("employee_name", RawField(raw="", line_id="p1_l4"), doc)
    assert result.reason == "zone_illisible"


def test_verify_all_fills_missing_fields_and_ignores_unknown_ones(doc: IntermediateDocument) -> None:
    answers = {
        "base_salary": RawField(raw="424,100", line_id="p1_l2"),
        "work_hours_regime": RawField(raw="208 h", line_id="p1_l5"),
        "net_a_payer": RawField(raw="460,000", line_id="p1_l2"),
    }
    results, warnings = verify_all(answers, doc, ["base_salary", "work_hours_regime", "hire_date"])
    assert set(results) == {"base_salary", "work_hours_regime", "hire_date"}
    assert results["base_salary"].reason is None
    assert results["hire_date"].reason == "absent_du_document"
    assert warnings == ["Champ inconnu renvoyé par Gemini, ignoré : net_a_payer."]


def test_canon() -> None:
    assert canon("Salaire  de base ٤٢٤٫١٠٠") == canon("salaire de base 424,100")


@pytest.mark.parametrize(
    ("line", "raw", "expected"),
    [
        ("Catégorie : 3   Échelon : 2", "3", True),
        ("Période : Mars 2023", "3", False),  # le 3 de 2023 n'est pas une catégorie
        ("Salaire de base  1.275,000", "1.275,000", True),
        ("Salaire de base  1.275,000", "275,000", False),  # morceau d'un montant plus grand
        ("Salaire de base  1424,100", "424,100", False),
        ("Total : 424,100.", "424,100", True),  # point final de phrase, pas un séparateur
        ("Nom : Ahmed Ben Salah", "ahmed ben salah", True),
    ],
)
def test_numbers_must_appear_whole(line: str, raw: str, expected: bool) -> None:
    assert contains_value(line, raw) is expected


@pytest.mark.parametrize(
    ("line", "raw", "expected"),
    [
        # Lignes de vraies fiches (évaluation du 21/10) : plusieurs nombres séparés par des espaces.
        ("Retenue CNSS  1329.988  9.18  122.093", "122.093", True),
        ("Total Brut  2549,307  2549,307", "2549,307", True),
        ("2001  Salaire de base Horaire  4,903  97,203  476,586", "476,586", True),
        ("Prime de présence  1  11.571  11.571", "11.571", True),
        ("Heures supplémentaires  16  6.578  200  210.496", "210.496", True),
        ("CONGEE ANNUEL  0  48.901  0", "0", True),
        # Espace des milliers : le nombre entier est accepté, avec ou sans l'espace...
        ("4550  SALAIRE BRUT  1 156,013", "1 156,013", True),
        ("4550  SALAIRE BRUT  1 156,013", "1156,013", True),
        ("Mois  1 156,013  111,902  1 044,111", "111,902", True),
        # ... mais pas un morceau.
        ("4550  SALAIRE BRUT  1 156,013", "156,013", False),
        ("4550  SALAIRE BRUT  1 156,013", "1", False),
        ("Salaire 1 156", "156", False),
        # Deux nombres voisins ne sont jamais collés en un seul.
        ("Retenue CNSS  1329.988  9.18  122.093", "9.18122.093", False),
        ("Heures  200 210.496", "200210.496", False),
        ("Heures  200 210.496", "210.496", True),  # après un point décimal : deux nombres distincts
        ("Base  10 20", "1020", False),
        # Les règles d'avant restent vraies.
        ("Période : Mars 2023", "3", False),
        ("Salaire de base  1424,100", "424,100", False),
        ("Salaire de base  ١٢٧٥٫٠٠٠", "1275,000", True),
    ],
)
def test_numbers_separated_by_spaces(line: str, raw: str, expected: bool) -> None:
    assert contains_value(line, raw) is expected
