"""Tests du mapping DS2 vers les sources DS4 v1."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.track_a_legal.v1_case_analysis import SCHEMA
from src.track_a_legal.tools.ds2_v1_legal_sources import (
    map_ds2_to_v1_legal_sources,
)


def test_mapping_preserves_article_data(valid_ds2_response):
    """Conserver les donn?es et la provenance documentaire DS2."""

    # Copier la r?ponse pour contr?ler son immutabilit?.
    response = deepcopy(valid_ds2_response)
    original = deepcopy(response)

    sources = map_ds2_to_v1_legal_sources(response)

    assert len(sources) == len(response["results"])

    for source, article in zip(sources, response["results"]):
        assert source["article_id"] == article["article_id"]
        assert source["source_id"] == article["article_id"]
        assert source["text"] == article["text"]
        # La citation doit reprendre les donn?es documentaires DS2.
        # Aucun num?ro de page ni extrait ne doit ?tre invent?.
        ds2_citation = article.get("citation") or {}
        citation = source["citation"]

        assert citation is not None
        assert citation["citation_id"] == (
            "DS2-" + article["article_id"]
        )
        assert citation["document"] == ds2_citation["source_file"]
        assert citation["page"] == ds2_citation["page"]
        assert citation["exact_excerpt"] == article["text"]
        assert source["version"] == article["version"]

    assert response == original


def test_mapping_matches_ds4_schema(valid_ds2_response):
    """V?rifier la conformit? au contrat DS4 v1."""

    sources = map_ds2_to_v1_legal_sources(
        deepcopy(valid_ds2_response)
    )

    validator = Draft202012Validator(
        SCHEMA["properties"]["legal_sources"],
        format_checker=FormatChecker(),
    )

    assert validator.is_valid(sources)


def test_mapping_rejects_duplicate_articles(valid_ds2_response):
    """Refuser les identifiants d'articles dupliqu?s."""

    response = deepcopy(valid_ds2_response)

    # Ajouter une deuxi?me occurrence du m?me article.
    response["results"].append(
        deepcopy(response["results"][0])
    )

    with pytest.raises(ValueError):
        map_ds2_to_v1_legal_sources(response)


def test_mapping_rejects_invalid_response():
    """Refuser une r?ponse non conforme au contrat DS2."""

    with pytest.raises(ValueError):
        map_ds2_to_v1_legal_sources({
            "status": "ok",
            "mode": "mock",
        })
