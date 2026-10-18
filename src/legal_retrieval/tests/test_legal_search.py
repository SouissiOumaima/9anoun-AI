"""D26 tests: real search (article reference + BM25) on a synthetic corpus ingested by the REAL loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from src.legal_retrieval.contract.api import app
from src.legal_retrieval.contract.handler import handle, validation_errors
from src.legal_retrieval.corpus.ingest_sections import run
from src.legal_retrieval.search.text import article_refs, stem, terms

_COMMON = Path(__file__).resolve().parents[2] / "shared" / "schemas" / "common.v0.schema.json"
V0 = "legal_retrieval.v0"


def _section(article: str, text: str, heading: str | None = None) -> dict[str, Any]:
    heading = heading or f"الفصل {article}"
    return {"source_article": article, "source_heading": heading, "title": heading,
            "content_type": None, "content": text, "paragraphs": [text]}


# fictitious texts (the real corpus is confidential): three sources, three sectors
_FILES = {
    "الاتفاقية المشتركة القطاعية للبناء والأشغال العامة.json": [
        _section("1", "يتمتع العامل بعطلة سنوية خالصة الأجر مدتها ثمانية عشر يوما."),
        _section("2", "تصرف منحة النقل شهريا لكل عامل."),
        _section("3", "تحدد ساعات العمل بثمان وأربعين ساعة في الأسبوع."),
        _section("42", "تسند منحة الحضور للعمال المواظبين.", "الفصل 42 (جديد): منحة الحضور"),
        _section("42 مكرر", "تضاف منحة خاصة بالعمل الليلي.", "الفصل 42 مكرر"),
    ],
    "الاتفاقية المشتركة الاطارية.json": [
        _section("1", "تطبق هذه الاتفاقية على جميع المؤسسات."),
        _section("2", "مدة التجربة لا تتجاوز ستة أشهر."),
    ],
    "الاتفاقية المشتركة القطاعية لقطاع البنوك.json": [
        _section("1", "تسند منحة الموازنة لأعوان البنوك."),
        _section("2", "العطلة السنوية للأعوان شهر كامل."),
    ],
}


@pytest.fixture
def live_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    for name, sections in _FILES.items():
        (raw / name).write_text(json.dumps({"sections": sections}, ensure_ascii=False),
                                encoding="utf-8")
    out = tmp_path / "corpus"
    run(raw, out)
    monkeypatch.setenv("DS2_CORPUS_DIR", str(out))
    return out


def _ask(query: str, **extra: Any) -> dict[str, Any]:
    return handle({"contract_version": V0, "request_id": "t", "query": query, **extra})


def _groups(response: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for r in response["results"]:
        if r["version_group"] not in seen:
            seen.append(r["version_group"])
    return seen


# --- text: the same cutting for the corpus and the question ----------------------
def test_stemming_joins_singular_plural_and_article_forms() -> None:
    assert stem("الاجازات") == stem("اجازه") == "اجاز"
    assert terms("العطلة السنوية للعامل") == terms("عطلة سنوية عامل")
    assert terms("في من على") == []  # function words only


@pytest.mark.parametrize(("question", "refs"), [
    ("ماذا ينص الفصل 42؟", [("42", "")]),
    ("بالفصل 42 مكرر", [("42", "BIS")]),
    ("الفصل 46 - 3", [("46-3", "")]),
    ("que dit l'article 14 bis ?", [("14", "BIS")]),
    ("منحة النقل", []),
])
def test_article_references_in_the_question(question: str, refs: list[tuple[str, str]]) -> None:
    assert article_refs(question) == refs


# --- live search ------------------------------------------------------------------
def test_topic_question_finds_the_right_article_first(live_corpus: Path) -> None:
    response = _ask("ما هي منحة النقل؟", sector="btp")
    assert response["status"] == "ok" and response["mode"] == "live"
    assert response["computed_by"] == "legal_retrieval.search.live"
    assert _groups(response)[0] == "CCS-BTP-ART-2"
    assert response["results"][0]["score"] == 1.0  # best BM25 score, normalized


def test_article_number_is_answered_first_with_score_1(live_corpus: Path) -> None:
    response = _ask("ماذا ينص الفصل 42 مكرر؟", sector="btp")
    assert _groups(response)[0] == "CCS-BTP-ART-42BIS"
    assert response["results"][0]["score"] == 1.0


def test_sector_filter_keeps_sector_texts_and_general_ones(live_corpus: Path) -> None:
    groups = _groups(_ask("العطلة السنوية", sector="banques"))
    assert "CCS-BANQUES-ART-2" in groups
    assert not any(g.startswith("CCS-BTP") for g in groups)  # another sector: excluded
    # the convention cadre applies to every sector: kept when it matches
    assert "CC-CADRE-ART-2" in _groups(_ask("مدة التجربة", sector="banques"))


def test_number_question_gives_sectoral_article_before_the_cadre(live_corpus: Path) -> None:
    groups = _groups(_ask("الفصل 2", sector="banques"))
    assert groups[:2] == ["CCS-BANQUES-ART-2", "CC-CADRE-ART-2"]


def test_top_k_counts_articles(live_corpus: Path) -> None:
    assert len(_groups(_ask("منحة", top_k=2))) == 2


def test_no_common_word_gives_source_manquante(live_corpus: Path) -> None:
    """Citation ou Silence: nothing in common with the corpus -> explicit refusal."""
    response = _ask("ما هي عاصمة فرنسا؟")
    assert response["status"] == "refus" and response["refus"]["code"] == "SOURCE_MANQUANTE"
    assert response["mode"] == "live" and response["citations"] == []


def test_same_question_same_order(live_corpus: Path) -> None:
    assert _groups(_ask("منحة")) == _groups(_ask("منحة"))


def test_live_responses_conform_to_both_schemas(live_corpus: Path) -> None:
    for response in (_ask("منحة النقل"), _ask("الفصل 42"), _ask("عاصمة فرنسا")):
        assert validation_errors(response, "search_response") == []
        if _COMMON.exists():
            common = json.loads(_COMMON.read_text(encoding="utf-8"))
            assert list(Draft202012Validator(common).iter_errors(response)) == []


def test_exact_text_never_normalized(live_corpus: Path) -> None:
    [first, *_] = _ask("منحة النقل", sector="btp")["results"]
    assert first["text"] == "تصرف منحة النقل شهريا لكل عامل."


def test_http_search_and_health_are_live(live_corpus: Path) -> None:
    client = TestClient(app)
    assert client.get("/health").json()["mode"] == "live"
    response = client.post("/legal/search", json={"contract_version": V0, "query": "منحة النقل"})
    assert response.status_code == 200 and response.json()["mode"] == "live"
    refused = client.post("/legal/search", json={"contract_version": V0, "query": "عاصمة فرنسا"})
    assert refused.status_code == 200  # business refusal, not a contract error


def test_live_false_forces_the_mock(live_corpus: Path) -> None:
    """The demo file shared with DS1 must not change when the corpus is present."""
    assert _ask("منحة")["mode"] == "live"
    response = handle({"contract_version": V0, "query": "منحة", "sector": "btp"}, live=False)
    assert response["mode"] == "mock"


def test_named_convention_keeps_only_its_article(live_corpus: Path) -> None:
    """« الفصل 2 من الاتفاقية الإطارية » : the cadre article only, not the sectoral 2s."""
    groups = _groups(_ask("ماذا يقول الفصل 2 من الاتفاقية الإطارية؟"))
    assert groups[0] == "CC-CADRE-ART-2"  # BM25 may add other articles AFTER it
    assert "CCS-BTP-ART-2" not in groups and "CCS-BANQUES-ART-2" not in groups


def test_one_letter_preposition_gives_both_forms() -> None:
    assert "عطل" in terms("بعطلة")  # finds "عطلة"
    assert "بطاق" in terms("بطاقة")  # the card stays a card


def test_weak_and_partial_match_is_refused_short_complete_is_kept(live_corpus: Path) -> None:
    """D27 abstention: one shared word in a long off-topic question -> refusal."""
    off_topic = _ask("ما هي نسبة الضريبة على السيارات المستوردة والمنحة؟")
    assert off_topic["status"] == "refus" and off_topic["refus"]["code"] == "SOURCE_MANQUANTE"
    # short question, every word found: kept even if its raw score is low
    assert _ask("منحة النقل", sector="btp")["status"] == "ok"
