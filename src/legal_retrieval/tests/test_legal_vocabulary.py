"""D21 tests: the vocabulary sent to DS1 stays valid and consistent with the code."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.legal_retrieval.contract.handler import _demo, handle
from src.legal_retrieval.contract.vocabulary import (
    VOCABULARY_PATH,
    load_vocabulary,
    sector_codes,
    worker_category_codes,
)
from src.legal_retrieval.corpus.registry import REGISTRY

_SCHEMA = VOCABULARY_PATH.parent / "schemas" / "legal_retrieval_vocabulary.v0.schema.json"


def test_vocabulary_matches_its_schema() -> None:
    schema = json.loads(Path(_SCHEMA).read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(load_vocabulary())) == []


def test_sectors_are_exactly_the_registry_sectors() -> None:
    """A sector added to the registry must be added to the vocabulary (and back)."""
    registry = {e.sector: e.source_id for e in REGISTRY if e.sector is not None}
    vocabulary = {s["code"]: s["source_id"] for s in load_vocabulary()["sectors"]}
    assert vocabulary == registry


def test_all_sectors_sources_are_the_registry_sources_without_sector() -> None:
    expected = {e.source_id for e in REGISTRY if e.sector is None}
    assert {s["source_id"] for s in load_vocabulary()["all_sectors_sources"]} == expected


def test_codes_are_unique() -> None:
    for codes in (sector_codes(), worker_category_codes()):
        assert len(codes) == len(set(codes))


def test_category_sectors_are_known_sector_codes() -> None:
    known = set(sector_codes())
    for category in load_vocabulary()["worker_categories"]:
        assert set(category.get("sectors", [])) <= known, category["code"]


def test_mock_and_examples_only_use_vocabulary_codes() -> None:
    assert {r["sector"] for r in _demo()["response"]["results"]} <= {*sector_codes(), None}
    for code in [*sector_codes(), *worker_category_codes()]:  # accepted by the contract
        field = "sector" if code in sector_codes() else "worker_category"
        response = handle({**_demo()["request"], field: code})
        assert response["status"] in ("ok", "refus")
        assert not response["refus"] or response["refus"]["code"] != "PARAM_INVALIDE"
