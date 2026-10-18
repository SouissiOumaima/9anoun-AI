"""Sprint 3 tests (D24): legal graph built from a corpus ingested by the REAL loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.legal_retrieval.corpus.ingest_sections import run
from src.legal_retrieval.graph.build import build_graph, external_text_id
from src.legal_retrieval.graph.query import related, texts_for_sector


def _section(article: Any, text: str, heading: str = "", **extra: Any) -> dict[str, Any]:
    return {"source_article": article, "source_heading": heading or f"الفصل {article}",
            "title": "", "content_type": None, "content": text, "paragraphs": [text], **extra}


@pytest.fixture
def graph_data(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    history = ("أمضيت بتاريخ 16 جانفي 1975 والمصادقة عليها المؤرخ في 12 مارس 1975.\n"
               "- الملحق التعديلي عدد 5 الممضى بتاريخ 24 سبتمبر 1996 والمصادق عليه "
               "المؤرخ في 16 أكتوبر 1996.")
    btp = {"sections": [
        _section(None, history, "النص",
                 content_type="legal_history_reconstructed_from_page_images"),
        _section("1", "تطبق أحكام الفصل 2 من هذه الاتفاقية."),
        _section("2", "تنسحب أحكام الفصل 166 جديد من مجل الشغل على الممثلين."),
        _section("3", "مقتضيات مجل الشغل وخاصة الفصل 143 منها."),
        _section("4", "كما نص عليه الملحق التعديلي عدد 7 والأمر عدد 501 لسنة 1982."),
        # real BTP form: the Code is named earlier in the article, not after the number
        _section("5", "حسب مجلة الشغل. مع الإشارة إلى أن أحكام الفصل 138 المقصودة لم تعد سارية."),
        _section("6", "نص.\nالفصول 7-8 : (ألغيت بمقتضى الملحق التعديلي عدد 5)"),
        _section("9", "كما ورد بالفصل 5 من الأمر المؤرخ في 8 جانفي 1948."),
    ]}
    cadre = {"sections": [_section("1", "الفصل 2 من الاتفاقية المشتركة الإطارية."),
                          _section("2", "نص الإطارية.")]}
    raw = tmp_path / "raw"
    raw.mkdir()
    for name, data in (("الاتفاقية المشتركة القطاعية للبناء والأشغال العامة.json", btp),
                       ("الاطارية.json", cadre)):
        (raw / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    run(raw, tmp_path / "corpus")
    graph, report = build_graph(tmp_path / "corpus")
    return graph.to_json(), report


def _edges(graph: dict[str, Any], edge_type: str) -> set[tuple[str, str]]:
    return {(e["from"], e["to"]) for e in graph["edges"] if e["type"] == edge_type}


def test_repeal_edges_come_from_the_dated_avenant(graph_data: tuple) -> None:
    graph, _ = graph_data
    assert ("AVENANT:CCS-BTP-AVENANT-5", "ARTICLE:CCS-BTP-ART-7") in _edges(graph, "ABROGE")
    avenant = next(n for n in graph["nodes"] if n["id"] == "AVENANT:CCS-BTP-AVENANT-5")
    assert avenant["known"] and avenant["approved_on"] == "1996-10-16"


def test_internal_and_code_du_travail_citations(graph_data: tuple) -> None:
    cites = _edges(graph_data[0], "CITE")
    assert ("ARTICLE:CCS-BTP-ART-1", "ARTICLE:CCS-BTP-ART-2") in cites
    assert ("ARTICLE:CCS-BTP-ART-2", "EXTERNAL:CODE-TRAVAIL-ART-166") in cites   # "مجل الشغل"
    assert ("ARTICLE:CCS-BTP-ART-3", "EXTERNAL:CODE-TRAVAIL-ART-143") in cites   # "... منها"
    assert ("ARTICLE:CC-CADRE-ART-1", "ARTICLE:CC-CADRE-ART-2") in cites


def test_inferred_citation_is_flagged(graph_data: tuple) -> None:
    """Article 138 does not exist in BTP, the Code is named in the same article."""
    edge = next(e for e in graph_data[0]["edges"]
                if e["to"] == "EXTERNAL:CODE-TRAVAIL-ART-138")
    assert edge["inferred"] is True


def test_cited_avenant_missing_from_history_is_known_false(graph_data: tuple) -> None:
    graph, report = graph_data
    node = next(n for n in graph["nodes"] if n["id"] == "AVENANT:CCS-BTP-AVENANT-7")
    assert node["known"] is False and report["avenants_cites_hors_historique"] == 1
    assert ("ARTICLE:CCS-BTP-ART-4", "EXTERNAL:DECRET-501-1982") in _edges(graph, "CITE")


def test_texts_for_sector_banques_include_the_cadre_but_not_btp(graph_data: tuple) -> None:
    """Sprint 3 deliverable: all texts applying to a sector."""
    rows = {r["source"]: r for r in texts_for_sector(graph_data[0], "banques")}
    assert rows["CCS-BANQUES"]["scope"] == "secteur"
    assert rows["CC-CADRE"]["scope"] == "tous_secteurs" and rows["CC-CADRE"]["articles"]
    assert "SMIG-GRILLE" in rows and "CCS-BTP" not in rows


def test_related_of_an_article(graph_data: tuple) -> None:
    rel = related(graph_data[0], "CCS-BTP-ART-2")
    assert rel["cite_par"][0]["from"] == "ARTICLE:CCS-BTP-ART-1"
    assert rel["cite"][0]["to"] == "EXTERNAL:CODE-TRAVAIL-ART-166"


@pytest.mark.parametrize(("span", "expected"), [
    ("الامر عدد 501 لسنه 1982", "DECRET-501-1982"), ("القانون عدد 27", "LOI-27"),
    ("مجل الشغل", "CODE-TRAVAIL"), ("المرسوم عدد 11", "DECRET-LOI-11"),
    ("من الامر المؤرخ في 8 جانفي 1948", "DECRET-1948-01-08"),  # the day is not a number
])
def test_external_ids(span: str, expected: str) -> None:
    assert external_text_id(span) == expected


def test_article_of_an_external_decree(graph_data: tuple) -> None:
    graph, report = graph_data
    assert ("ARTICLE:CCS-BTP-ART-9", "EXTERNAL:DECRET-1948-01-08-ART-5") in _edges(graph, "CITE")
    assert report["citations_non_resolues"] == []
