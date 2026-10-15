"""D22 tests: get_article on a real ingestion of a synthetic digest (live) and on the mock."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from src.legal_retrieval.contract.api import app
from src.legal_retrieval.contract.get_article import get_article
from src.legal_retrieval.corpus.ingest_sections import run

_COMMON = Path(__file__).resolve().parents[2] / "shared" / "schemas" / "common.v0.schema.json"
V0 = "legal_retrieval.v0"


def _section(article: Any, text: str, heading: str, **extra: Any) -> dict[str, Any]:
    return {"source_article": article, "source_heading": heading, "title": heading,
            "content_type": None, "content": text, "paragraphs": [text], **extra}


@pytest.fixture
def live_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ingest a small BTP-like digest with the REAL loader, point the store to it."""
    history = ("أمضيت بتاريخ 16 جانفي 1975 والمصادقة عليها المؤرخ في 12 مارس 1975.\n"
               "- الملحق التعديلي عدد 5 الممضى بتاريخ 24 سبتمبر 1996 والمصادق عليه "
               "المؤرخ في 16 أكتوبر 1996.")
    digest = {"sections": [
        _section(None, history, "النص",
                 content_type="legal_history_reconstructed_from_page_images"),
        *[_section(str(n), f"نص الفصل {n}.", f"الفصل {n}") for n in range(1, 38)],
        _section("37", "نص 37.\nالفصول 38-39-40-41 : (ألغيت بمقتضى الملحق التعديلي عدد 5)",
                 "الفصل 37"),
        _section("42", "منحة جديدة.", "الفصل 42 (جديد): منحة"),
        _section("42 مكرر", "نص مضاف.", "الفصل 42 مكرر"),
    ]}
    raw = tmp_path / "raw"
    raw.mkdir()
    name = "الاتفاقية المشتركة القطاعية للبناء والأشغال العامة.json"
    (raw / name).write_text(json.dumps(digest, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "corpus"
    run(raw, out)
    monkeypatch.setenv("DS2_CORPUS_DIR", str(out))
    return out


def _conforms_to_common(response: dict[str, Any]) -> None:
    if _COMMON.exists():
        common = json.loads(_COMMON.read_text(encoding="utf-8"))
        assert list(Draft202012Validator(common).iter_errors(response)) == []


def test_by_id_returns_the_live_article_with_its_citation(live_corpus: Path) -> None:
    response = get_article({"contract_version": V0, "request_id": "r1",
                            "article_id": "CCS-BTP-ART-42-v1"})
    assert response["status"] == "ok" and response["mode"] == "live"
    [result] = response["results"]
    assert result["text"] == "منحة جديدة." and result["modified"] is True
    assert result["previous_version_available"] is False  # (جديد): old text not in corpus
    assert response["citations"][0]["data_file"].startswith("data/processed/")
    _conforms_to_common(response)


def test_by_source_and_number_and_bis(live_corpus: Path) -> None:
    response = get_article({"contract_version": V0, "source_id": "CCS-BTP", "article": "42BIS"})
    assert [r["article_id"] for r in response["results"]] == ["CCS-BTP-ART-42BIS-v1"]


def test_repealed_article_is_returned_and_announced(live_corpus: Path) -> None:
    """Citation, not silence: the repeal itself is the answer (D17/D18)."""
    [result] = get_article({"contract_version": V0, "article_id": "CCS-BTP-ART-39"})["results"]
    assert result["status"] == "abroge" and result["amended_by"] == "CCS-BTP-AVENANT-5"
    assert result["applicable_at_reference_date"] is False
    assert "ألغيت" in result["text"]


def test_unknown_article_is_a_bilingual_source_manquante(live_corpus: Path) -> None:
    response = get_article({"contract_version": V0, "source_id": "CCS-BTP", "article": "99"})
    assert response["status"] == "refus" and response["refus"]["code"] == "SOURCE_MANQUANTE"
    assert response["refus"]["message_fr"] and response["refus"]["message_ar"]
    _conforms_to_common(response)


def test_gap_checked_by_hand_gives_the_real_reason(live_corpus: Path) -> None:
    """Cadre 5: present in the PDF, missing in the digest (manual_checks.json)."""
    response = get_article({"contract_version": V0, "source_id": "CC-CADRE", "article": "5"})
    assert response["refus"]["code"] == "SOURCE_MANQUANTE"
    assert "PDF original" in response["refus"]["message_fr"]


def test_mock_mode_without_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DS2_CORPUS_DIR", str(tmp_path / "absent"))
    response = get_article({"contract_version": V0, "article_id": "CCS-BTP-ART-50"})
    assert response["mode"] == "mock" and response["status"] == "ok"
    assert [r["version"] for r in response["results"]] == [2, 1]  # all versions (D17)


@pytest.mark.parametrize("bad", [
    {},                                                      # no reference
    {"article_id": "CCS-BTP-ART-39", "source_id": "CCS-BTP", "article": "39"},  # both
    {"source_id": "CCS-BTP"},                                # article missing
    {"article_id": "btp 39"},                                # not an id
    {"source_id": "CCS-BTP", "article": "39 مكرر"},          # Arabic suffix: use 39BIS
])
def test_bad_references_are_contract_refusals(bad: dict[str, Any]) -> None:
    response = get_article({"contract_version": V0, **bad})
    assert response["refus"]["code"] == "PARAM_INVALIDE"
    assert response["computed_by"] == "legal_retrieval.contract"


def test_http_route(live_corpus: Path) -> None:
    client = TestClient(app)
    assert client.get("/health").json()["get_article_mode"] == "live"
    ok = client.post("/legal/article", json={"contract_version": V0, "article_id": "CCS-BTP-ART-1"})
    assert ok.status_code == 200 and ok.json()["status"] == "ok"
    missing = client.post("/legal/article",
                          json={"contract_version": V0, "source_id": "CCS-BTP", "article": "99"})
    assert missing.status_code == 200  # "no such article" is a valid answer
    assert client.post("/legal/article", json={"contract_version": V0}).status_code == 422
