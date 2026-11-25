import pytest
"""Tests de conversion contractuelle DS2 vers DS4."""

from copy import deepcopy

from src.track_a_legal.tools.ds2_to_ds4_adapter import (
    adapt_ds2_to_ds4,
)


def test_adapter_preserves_sources_and_citations(valid_ds2_response):
    """Conserver la traçabilité sans conclure juridiquement."""

    # Utiliser une réponse DS2 synthétique conforme.
    response = deepcopy(valid_ds2_response)

    # Convertir les sources DS2 en structures internes DS4.
    adapted = adapt_ds2_to_ds4(response)

    # Conserver les identifiants exacts des articles.
    assert adapted["legal_sources_used"] == ["TEST-ART-1-v1"]

    # Préserver les citations officielles sans transformation.
    assert adapted["citations"] == response["citations"]

    # Ne jamais autoriser une conclusion juridique automatiquement.
    assert adapted["legal_conclusion"] is None


def test_adapter_rejects_invalid_ds2_responses(valid_ds2_response):
    """Rejeter les contrats incomplets et les r?ponses sans sources."""
    import pytest

    # Tester un article incomplet.
    incomplete = deepcopy(valid_ds2_response)
    del incomplete["results"][0]["source_title"]

    # Tester une r?ponse sans article ni citation.
    empty = deepcopy(valid_ds2_response)
    empty["results"] = []
    empty["citations"] = []

    for response in (incomplete, empty):
        with pytest.raises(ValueError, match="Invalid DS2"):
            adapt_ds2_to_ds4(response)


def test_adapter_rejects_duplicate_article_ids(valid_ds2_response):
    """Rejeter deux articles portant le m?me identifiant."""
    import pytest

    # Dupliquer un article et sa citation.
    response = deepcopy(valid_ds2_response)
    response["results"].append(deepcopy(response["results"][0]))
    response["citations"].append(deepcopy(response["citations"][0]))

    with pytest.raises(ValueError):
        adapt_ds2_to_ds4(response)


def test_adapter_preserves_temporal_metadata(valid_ds2_response):
    """Conserver les m?tadonn?es DS2 sans certifier l'applicabilit?."""

    # Utiliser une copie ind?pendante de la r?ponse DS2.
    response = deepcopy(valid_ds2_response)
    article = response["results"][0]

    # Convertir les donn?es avec l'adaptateur DS4.
    adapted = adapt_ds2_to_ds4(response)

    # V?rifier la conservation des m?tadonn?es officielles.
    expected_fields = (
        "article_id",
        "effective_from",
        "effective_to",
        "status",
        "version_group",
        "version",
        "applicable_at_reference_date",
        "modified",
        "amended_by",
        "previous_version_available",
    )

    temporal_sources = adapted["legal_temporal_sources"]

    assert len(temporal_sources) == 1

    for field in expected_fields:
        assert temporal_sources[0][field] == article[field]

    # La pr?sence de m?tadonn?es ne constitue pas une conclusion.
    assert adapted["legal_conclusion"] is None


def test_adapter_rejects_conflicting_applicable_versions(valid_ds2_response):
    """Refuser deux versions simultan?ment applicables d'un m?me article."""

    # Construire une r?ponse ind?pendante.
    response = deepcopy(valid_ds2_response)

    # Cr?er une deuxi?me version du m?me article.
    second = deepcopy(response["results"][0])
    second["article_id"] = "TEST-ART-1-v2"
    second["version"] = 2

    # Les deux versions revendiquent la m?me applicabilit?.
    second["applicable_at_reference_date"] = True

    # Ajouter la version et sa citation correspondante.
    response["results"].append(second)
    response["citations"].append(deepcopy(second["citation"]))

    # Le contrat structurel ne suffit pas :
    # la validation m?tier doit d?tecter le conflit.
    with pytest.raises(ValueError):
        adapt_ds2_to_ds4(response)


def test_adapter_rejects_inverted_effective_dates(valid_ds2_response):
    """Refuser une p?riode juridique dont les dates sont invers?es."""

    # Cr?er une r?ponse DS2 ind?pendante.
    response = deepcopy(valid_ds2_response)

    # Simuler une p?riode juridiquement incoh?rente.
    article = response["results"][0]
    article["effective_from"] = "2025-01-01"
    article["effective_to"] = "2024-12-31"

    # La validation doit refuser cette incoh?rence.
    with pytest.raises(ValueError):
        adapt_ds2_to_ds4(response)


def test_adapter_rejects_article_outside_reference_date(valid_ds2_response):
    """Refuser une applicabilit? DS2 incompatible avec la date du dossier."""

    # Pr?parer une r?ponse DS2 ind?pendante.
    response = deepcopy(valid_ds2_response)

    # L'article entre en vigueur apr?s la date de r?f?rence.
    response["results"][0]["effective_from"] = "2025-01-01"
    response["results"][0]["effective_to"] = None
    response["results"][0]["applicable_at_reference_date"] = True

    # La date du dossier est ant?rieure ? l'entr?e en vigueur.
    reference_date = "2024-06-01"

    # Le contr?le doit refuser cette incoh?rence.
    with pytest.raises(ValueError):
        adapt_ds2_to_ds4(
            response,
            reference_date=reference_date,
        )


@pytest.mark.parametrize(
    "reference_date",
    [
        20240601,
        "2024-02-30",
        "2024-6-1",
        "not-a-date",
    ],
)
def test_adapter_rejects_invalid_reference_dates(
    valid_ds2_response,
    reference_date,
):
    """Reject invalid or non-strict reference dates."""
    response = deepcopy(valid_ds2_response)

    with pytest.raises(ValueError):
        adapt_ds2_to_ds4(
            response,
            reference_date=reference_date,
        )


def test_adapter_rejects_expired_article_at_reference_date(
    valid_ds2_response,
):
    """Reject an expired article incorrectly declared applicable."""
    from copy import deepcopy
    import pytest
    from src.track_a_legal.tools.ds2_to_ds4_adapter import adapt_ds2_to_ds4

    # Create an independent synthetic DS2 response.
    response = deepcopy(valid_ds2_response)
    article = response["results"][0]

    # The article expires before the case reference date.
    article["effective_from"] = "2024-01-01"
    article["effective_to"] = "2024-12-31"
    article["applicable_at_reference_date"] = True

    # DS4 must reject the inconsistent temporal metadata.
    with pytest.raises(ValueError, match="Article expired"):
        adapt_ds2_to_ds4(
            response,
            reference_date="2025-06-01",
        )


@pytest.mark.parametrize(
    "invalid_data",
    [
        None,
        {},
        {"legal_temporal_sources": [], "legal_sources_used": None},
        {"legal_temporal_sources": [], "legal_sources_used": ["ART-1"]},
        {"legal_temporal_sources": [None], "legal_sources_used": ["ART-1"]},
        {
            "legal_temporal_sources": [{"article_id": "ART-2"}],
            "legal_sources_used": ["ART-1"],
        },
        {
            "legal_temporal_sources": [
                {"article_id": "ART-1"},
                {"article_id": "ART-1"},
            ],
            "legal_sources_used": ["ART-1", "ART-1"],
        },
    ],
)
def test_pillar_assessments_reject_invalid_metadata(invalid_data):
    """Reject inconsistent DS2 metadata before building legal pillars."""
    from src.track_a_legal.tools.ds2_to_ds4_adapter import (
        build_ds2_pillar_assessments,
    )

    # Invalid structures must never produce legal assessments.
    with pytest.raises(ValueError):
        build_ds2_pillar_assessments(invalid_data)

def test_adapter_preserves_historical_and_applicable_versions(valid_ds2_response):
    """Conserver toutes les versions sans certifier une conclusion juridique."""
    response = deepcopy(valid_ds2_response)

    historical = response["results"][0]
    historical["article_id"] = "TEST-ART-1-v1"
    historical["version"] = 1
    historical["version_group"] = "GROUP-1"
    historical["effective_from"] = "2020-01-01"
    historical["effective_to"] = "2024-12-31"
    historical["applicable_at_reference_date"] = False

    current = deepcopy(historical)
    current["article_id"] = "TEST-ART-1-v2"
    current["version"] = 2
    current["effective_from"] = "2025-01-01"
    current["effective_to"] = None
    current["applicable_at_reference_date"] = True

    response["results"].append(current)
    response["citations"].append(deepcopy(current["citation"]))

    adapted = adapt_ds2_to_ds4(
        response,
        reference_date="2026-03-01",
    )

    versions = adapted["legal_temporal_sources"]

    assert len(versions) == 2
    assert [item["version"] for item in versions] == [1, 2]
    assert [item["applicable_at_reference_date"] for item in versions] == [
        False, True,
    ]
    assert adapted["legal_sources_used"] == [
        "TEST-ART-1-v1",
        "TEST-ART-1-v2",
    ]
    assert adapted["legal_conclusion"] is None
