"""Tests du pipeline DS2 ? DS4 v1."""

from copy import deepcopy

import pytest

from src.track_a_legal.tools import ds2_v1_pipeline
from src.track_a_legal.tests.test_v1_case_analysis import (
    make_valid_request,
)


def test_pipeline_success(monkeypatch, valid_ds2_response):
    """V?rifier le pipeline et pr?server les entr?es originales."""

    # Simuler DS2 pour rendre le test ind?pendant du corpus LIVE.
    def fake_ds2_handle(request, *, live=True):
        assert live is True
        return deepcopy(valid_ds2_response)

    monkeypatch.setattr(
        ds2_v1_pipeline, "ds2_handle", fake_ds2_handle
    )

    ds4_request = make_valid_request()
    ds2_request = {"query": "test"}
    original_ds4 = deepcopy(ds4_request)
    original_ds2 = deepcopy(ds2_request)

    response = ds2_v1_pipeline.run_ds2_ds4_v1_pipeline(
        ds4_request, ds2_request
    )

    expected_ids = [
        article["article_id"]
        for article in valid_ds2_response["results"]
    ]

    assert response["status"] == "ok"
    assert response["result"]["legal_sources_used"] == expected_ids
    assert response["result"]["legal_conclusion"] is None
    assert response["citations"] == []
    assert ds4_request == original_ds4
    assert ds2_request == original_ds2


def test_pipeline_rejects_existing_sources(monkeypatch):
    """Emp?cher le remplacement silencieux de sources existantes."""

    # DS2 ne doit pas ?tre appel? si des sources existent d?j?.
    def forbidden_ds2_handle(*args, **kwargs):
        raise AssertionError("DS2 should not be called.")

    monkeypatch.setattr(
        ds2_v1_pipeline, "ds2_handle", forbidden_ds2_handle
    )

    request = make_valid_request()
    request["legal_sources"] = [{"article_id": "EXISTING"}]

    with pytest.raises(ValueError, match="already contains"):
        ds2_v1_pipeline.run_ds2_ds4_v1_pipeline(
            request, {"query": "test"}
        )


def test_pipeline_rejects_invalid_ds2_response(monkeypatch):
    """Refuser une r?ponse DS2 invalide sans produire d'analyse."""

    # Simuler une r?ponse de recherche juridiquement inexploitable.
    def fake_ds2_handle(request, *, live=True):
        return {"status": "erreur", "results": []}

    monkeypatch.setattr(
        ds2_v1_pipeline, "ds2_handle", fake_ds2_handle
    )

    with pytest.raises(ValueError, match="Invalid DS2 response"):
        ds2_v1_pipeline.run_ds2_ds4_v1_pipeline(
            make_valid_request(), {"query": "test"}
        )


def test_pipeline_forwards_pdf_root(
    monkeypatch, valid_ds2_response, tmp_path
):
    calls = []
    real_handler = ds2_v1_pipeline.handle_v1

    def fake_ds2_handle(request, *, live=True):
        assert live is True
        return deepcopy(valid_ds2_response)

    def tracked_handler(request, *, pdf_root):
        calls.append(pdf_root)
        return real_handler(request, pdf_root=pdf_root)

    monkeypatch.setattr(
        ds2_v1_pipeline, "ds2_handle", fake_ds2_handle
    )
    monkeypatch.setattr(
        ds2_v1_pipeline, "handle_v1", tracked_handler
    )

    ds4_request = make_valid_request()
    ds2_request = {"query": "test"}
    original_ds4 = deepcopy(ds4_request)
    original_ds2 = deepcopy(ds2_request)

    response = ds2_v1_pipeline.run_ds2_ds4_v1_pipeline(
        ds4_request, ds2_request, pdf_root=str(tmp_path)
    )

    assert calls == [str(tmp_path)]
    assert response["status"] == "ok"
    assert response["result"]["legal_conclusion"] is None
    assert response["citations"] == []
    assert ds4_request == original_ds4
    assert ds2_request == original_ds2


def test_pipeline_pdf_mode_rejects_existing_sources(
    monkeypatch, tmp_path
):
    def forbidden_ds2_handle(*args, **kwargs):
        raise AssertionError("DS2 must not be called.")

    monkeypatch.setattr(
        ds2_v1_pipeline, "ds2_handle", forbidden_ds2_handle
    )

    request = make_valid_request()
    request["legal_sources"] = [{"article_id": "EXISTING"}]

    with pytest.raises(ValueError, match="already contains"):
        ds2_v1_pipeline.run_ds2_ds4_v1_pipeline(
            request, {"query": "test"}, pdf_root=str(tmp_path)
        )
