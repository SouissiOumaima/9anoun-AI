import pytest

from src.orchestrator.intent import parse_message
from src.orchestrator.models import Intent


@pytest.mark.parametrize(
    ("message", "expected_intent", "language"),
    [
        ("Quel article du code du travail s'applique ?", Intent.LEGAL_RESEARCH, "fr"),
        ("Calcule le salaire SMIG pour 2024-01-01.", Intent.PAYROLL_CALCULATION, "fr"),
        ("حلل هذه الفاتورة بمبلغ 1500 دينار", Intent.DOCUMENT_ANALYSIS, "ar"),
        ("حلل أدلة هذه القضية", Intent.CASE_ANALYSIS, "ar"),
        ("Rédige un avenant au contrat.", Intent.GENERATE_DELIVERABLE, "fr"),
    ],
)
def test_parser_routes_supported_fr_and_ar_messages(message, expected_intent, language) -> None:
    parsed = parse_message(message)
    assert parsed.intent is expected_intent
    assert parsed.language == language
    assert not parsed.needs_clarification


def test_parser_extracts_explicit_low_risk_entities() -> None:
    parsed = parse_message("Le salaire est 1500.500 TND selon l'article 14 au 2024-06-01.")
    assert parsed.entities == {
        "amounts": ("1500.500 TND",),
        "articles": ("article 14",),
        "dates": ("2024-06-01",),
    }


def test_unknown_message_requires_clarification() -> None:
    parsed = parse_message("Bonjour")
    assert parsed.intent is Intent.CLARIFICATION_REQUIRED
    assert parsed.needs_clarification


def test_blank_message_is_rejected() -> None:
    with pytest.raises(ValueError, match="message is required"):
        parse_message("  ")
