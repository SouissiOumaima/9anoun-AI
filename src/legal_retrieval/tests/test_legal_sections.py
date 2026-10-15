"""Sprint 2 tests: reader of the Tradrly sections (D20).

Synthetic digests that reproduce the REAL forms found during the manual
verification (D18) — no confidential article text.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from src.legal_retrieval.corpus.ingest_sections import ingest_json, run
from src.legal_retrieval.corpus.models import ArticleStatus
from src.legal_retrieval.corpus.normalize import normalize_arabic
from src.legal_retrieval.corpus.sections import (
    find_abrogations,
    find_dates,
    find_embedded_headers,
    parse_history,
    parse_source_article,
    read_sections,
)

HISTORY = (
    "الاتفاقية المشتركة القطاعية للبناء والأشغال العامة - أمضيت بتاريخ 16 جانفي 1975 "
    "وتمت المصادقة عليها بقرار وزير الشؤون الاجتماعية المؤرخ في 12 مارس 1975.\n"
    "وتمت مراجعتها بالملحقات التعديليت التاليي:.\n"  # OCR typos kept on purpose
    "- الملحق التعديلي عدد 1 الممضى بتاريخ 8 مارس 1983 والمصادق عليه بقرار وزير "
    "الشؤون الاجتماعية المؤرخ في 14 أفريل 1983.\n"
    "- الملحق التعديلي عدد 5 الممضى بتاريخ 24 سبتمبر 1996 والمصادق عليه بقرار وزير "
    "الشؤون الاجتماعية المؤرخ في 16 أكتوبر 1996.\n"
)


def _section(article: Any, text: str, heading: str = "", **extra: Any) -> dict[str, Any]:
    """A section shaped like the Tradrly digest (content == joined paragraphs)."""
    return {"number": 0, "title": heading, "source_article": article,
            "source_heading": heading, "content_type": "article", "source_pdf_pages": None,
            "content": text, "paragraphs": text.split("\n"), **extra}


def _digest() -> dict[str, Any]:
    return {
        "sector_ar": "البناء", "structure": "...", "quality": {},
        "sections": [
            _section(None, HISTORY, content_type="legal_history_reconstructed_from_page_images",
                     source_pdf_pages=[2, 3]),
            _section(None, "العنوان الأول : أحكام عامة"),                       # preamble
            _section("1", "تنطبق هذه الاتفاقية على المؤسسات.", "الفصل 1"),
            _section("2", "مدة الاتفاقية سنة.", "الفصل2: المدة"),               # R1 heading
            # Cadre case: article 4 holds the header of the missing article 5 (R1 + R4)
            _section("4", "نص الفصل الرابع وفقا لما ورد بالفصل 51 فقرة 2.\n"   # R5 reference
                          "الفصل5 (جديد): الحق النقابي وحرية الرأي\nنص الفصل الخامس.",
                     "الفصل 4"),
            *[_section(str(n), f"نص الفصل {n}.", f"الفصل {n}") for n in range(6, 37)],
            _section("37", "نص الفصل 37.\n"
                           "الفصول 38 – 39 – 40 – 41 : (ألغيت بمقتضى الملحق التعديلي عدد 5)",
                     "الفصل 37"),
            _section("42", "الفصلان 43 و44 (ألغيا بمقتضى الملحق التعديلي عدد 1)", "الفصل 42"),
            _section("45", "(ألغي بمقتضى الملحق التعديلي عدد؟)", "الفصل45:"),  # own abrogation
            _section("46", "منحة جديدة.", "الفصل 46 (جديد) : منحة"),          # R6
            _section("46 مكرر", "نص مضاف.", "الفصل 46 مكرر"),                  # bis, not a reset
            _section("1", "نص ثان يبدأ من جديد.", "الفصل 1"),                   # numbering reset
            _section("2", "تابع النص الثاني.", "الفصل 2"),
        ],
    }


# --- part 1 : history ----------------------------------------------------
def test_dates_use_tunisian_month_names_and_skip_impossible_dates() -> None:
    assert find_dates(normalize_arabic("المؤرخ في 16 أكتوبر 1996")) == [date(1996, 10, 16)]
    assert find_dates(normalize_arabic("بتاريخ 3 جويلية 2017 و 10 أوت 1989")) == [
        date(2017, 7, 3), date(1989, 8, 10)]
    assert find_dates("31 فيفري 2000") == []  # OCR error: never "fixed"


def test_history_gives_convention_and_avenant_dates() -> None:
    history = parse_history(HISTORY, "CCS-BTP")
    assert (history.signed_on, history.approved_on) == (date(1975, 1, 16), date(1975, 3, 12))
    assert [a.avenant_id for a in history.avenants] == ["CCS-BTP-AVENANT-1", "CCS-BTP-AVENANT-5"]
    fifth = history.avenants[1]  # signature first, ministerial approval second
    assert (fifth.signed_on, fifth.approved_on) == (date(1996, 9, 24), date(1996, 10, 16))
    assert history.unparsed_lines == []


def test_history_line_without_dates_is_flagged_not_dropped() -> None:
    history = parse_history("- الملحق التعديلي عدد 7 الممضى بتاريخ ؟؟", "CCS-X")
    assert history.avenants[0].number == 7 and history.avenants[0].signed_on is None
    assert history.unparsed_lines == [0]


# --- part 2 : sections ---------------------------------------------------
@pytest.mark.parametrize(("value", "expected"), [
    ("7 مكرر", (7, True)), ("12", (12, False)), (3, (3, False)),
    ("١٤", (14, False)), (None, (None, False)), ("", (None, False)),
])
def test_source_article_parsing(value: Any, expected: tuple[Any, bool]) -> None:
    assert parse_source_article(value) == expected


def test_text_is_read_once_and_history_is_set_apart() -> None:
    history, articles, preamble = read_sections(_digest())
    assert "عدد 5" in history and len(preamble) == 1
    first = articles[0]
    assert first.text == "تنطبق هذه الاتفاقية على المؤسسات."  # not content + paragraphs


def test_jadid_bis_and_numbering_reset() -> None:
    _, articles, _ = read_sections(_digest())
    by_label = {(a.part, a.label): a for a in articles}
    assert by_label[(1, "الفصل 46")].modified
    assert by_label[(1, "الفصل 46 مكرر")].is_bis and by_label[(1, "الفصل 46 مكرر")].part == 1
    assert by_label[(2, "الفصل 1")].text.startswith("نص ثان")  # second text, not a duplicate


# --- part 3 : rules inside the texts -------------------------------------
def test_embedded_header_r1_r4_but_never_a_reference_r5() -> None:
    text = "وفقا لما ورد بالفصل 51 فقرة 2 ومن الفصل 7 من هذه الاتفاقية.\nالفصل5 (جديد): الحق"
    headers = find_embedded_headers(text)
    assert [(h.number, h.modified) for h in headers] == [(5, True)]
    assert find_embedded_headers("نص ... الفصل 51 (جديد): منح القفة")[0].number == 51  # R4
    # real BTP form: hamza alef written by the OCR, header glued after ")"
    real = "(بالنسبة للعمال القارين والعرضيين) إلفصل 51 (جديد): منح القفة والتنقل"
    assert [(h.number, h.modified) for h in find_embedded_headers(real)] == [(51, True)]
    assert find_embedded_headers("المنصوص عليها بالفصل 51 فقرة (ب)") == []  # R5


@pytest.mark.parametrize(("line", "numbers", "avenant"), [
    ("الفصول 38-39-40-41: (ألغيت بمقتضى الملحق التعديلي عدد 5)", ("38", "39", "40", "41"), 5),
    ("الفصول 38 – 39 – 40 – 41 : (ألغيت بمقتضى الملحق التعديلي عدد 5)",
     ("38", "39", "40", "41"), 5),
    ("الفصلان 52 و53 : (ألغيا بمقتضى الملحق التعديلي عدد 6)", ("52", "53"), 6),   # dual
    ("الفصول 31-32-33 (ألغيت بمقتضى الملحق التعديلي عدد 2)", ("31", "32", "33"), 2),  # no ":"
    ("الفصول 6 و7 و8 و9 و10 و10 مكرر: (ألغيت بمقتضى الملحق التعديلي عدد 4)",
     ("6", "7", "8", "9", "10", "10BIS"), 4),                                        # R3
    ("الفصل55: (ألغي بمقتضى الملحق التعديلي عدد؟)", ("55",), None),                 # OCR lost it
    ("الفصول 31—32—33 (ألغيت بمقتضى الملحق التعديلي عدد 2)", ("31", "32", "33"), 2),  # em dash
    ("الفصول 38—39—40— 41: (ألغيت بمقتضى الملحق التعديلي عدد؟)",
     ("38", "39", "40", "41"), None),                                                 # real form
])
def test_abrogation_lists_r2_r3(line: str, numbers: tuple[str, ...], avenant: int | None) -> None:
    found = find_abrogations("نص سابق\n" + line)
    assert len(found) == 1
    assert found[0].numbers == numbers and found[0].avenant_number == avenant
    assert found[0].line == line  # original line kept for the citation


def test_reference_to_an_article_is_not_an_abrogation() -> None:
    assert find_abrogations("تطبق أحكام الفصل 12 من هذه الاتفاقية") == []


# --- whole file ------------------------------------------------------------
def _write(tmp_path: Path, name: str, data: dict[str, Any]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_ingest_explains_every_gap(tmp_path: Path) -> None:
    path = _write(tmp_path, "الاتفاقية المشتركة القطاعية للبناء والأشغال العامة.json", _digest())
    _, articles, history, report = ingest_json(path)
    by_id = {a.article_id: a for a in articles}

    # article 5 recovered from article 4, article 4 keeps only its own text
    assert by_id["CCS-BTP-ART-5-v1"].origin == "split_from_section"
    assert by_id["CCS-BTP-ART-5-v1"].modified
    assert "الحق النقابي" not in by_id["CCS-BTP-ART-4-v1"].text

    # abrogation lines -> abroge entries linked to the avenant, out of article 37
    art39 = by_id["CCS-BTP-ART-39-v1"]
    assert art39.status == ArticleStatus.ABROGE and art39.amended_by == "CCS-BTP-AVENANT-5"
    assert "ألغيت" not in by_id["CCS-BTP-ART-37-v1"].text
    assert by_id["CCS-BTP-ART-44-v1"].amended_by == "CCS-BTP-AVENANT-1"     # dual form
    assert by_id["CCS-BTP-ART-45-v1"].status == ArticleStatus.ABROGE        # own section
    assert by_id["CCS-BTP-ART-45-v1"].amended_by is None                     # "عدد؟"

    # (جديد): current text, old one not in the corpus -> announced (D17)
    assert by_id["CCS-BTP-ART-46-v1"].previous_version_available is False
    assert by_id["CCS-BTP-ART-46BIS-v1"].status == ArticleStatus.EN_VIGUEUR

    # second text of the file: own ids, no duplicate
    assert "CCS-BTP-P2-ART-1-v1" in by_id and report["duplicate_ids"] == 0
    assert report["parts"] == 2 and len(history.avenants) == 2

    # gap 3 is the only one left (5 split, 38-41/43-44 repealed)
    assert report["missing_unexplained"] == {"1": [3]}
    assert report["abrogation_avenant_unknown"] == ["P1:45"]


def test_manual_checks_silence_verified_gaps(tmp_path: Path) -> None:
    path = _write(tmp_path, "الاتفاقية المشتركة القطاعية للبناء والأشغال العامة.json", _digest())
    check = {"source_id": "CCS-BTP", "part": 1, "articles": ["3"],
             "verdict": "absent_du_pdf_source"}
    _, _, _, report = ingest_json(path, manual=[check])
    assert report["known_gaps"] == ["P1:3 absent_du_pdf_source"]
    assert report["missing_unexplained"] == {}


def test_run_writes_articles_avenants_and_report(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    _write(raw, "البنوك.json", {"sections": [_section("1", "نص.", "الفصل 1")]})
    _write(raw, "الاتفاقية المشتركة القطاعية للبناء والأشغال العامة.json", _digest())
    reports = run(raw, tmp_path / "out")
    assert {r["source_id"] for r in reports} == {"CCS-BANQUES", "CCS-BTP"}
    avenants = json.loads((tmp_path / "out" / "avenants.json").read_text(encoding="utf-8"))
    btp = next(a for a in avenants if a["source_id"] == "CCS-BTP")
    assert btp["signed_on"] == "1975-01-16" and btp["avenants"][1]["approved_on"] == "1996-10-16"
    lines = (tmp_path / "out" / "legal_articles.jsonl").read_text(encoding="utf-8").splitlines()
    assert all(json.loads(line)["text_source"] == "ocr_json_sections" for line in lines)


def test_repeated_or_out_of_order_number_is_not_a_new_part(tmp_path: Path) -> None:
    """Real run 2026-10-10: "46 then 46" made fake parts (up to 7 for Enseignement)."""
    data = {"sections": [_section(str(n), f"نص {n}.", f"الفصل {n}") for n in (1, 2, 3)]
            + [_section("3", "تتمة الفصل 3.", "الفصل 3"),            # same number again
               _section("2", "نص في غير مكانه.", "الفصل 2"),          # out of order
               _section("4", "نص 4.", "الفصل 4"),
               _section("1", "نص آخر.", "الفصل 1")]}                  # real restart at 1
    path = _write(tmp_path, "البنوك.json", data)
    _, articles, _, report = ingest_json(path)
    assert report["parts"] == 2
    assert report["numbering_out_of_order"] == ["P1:3->3", "P1:3->2"]
    assert report["number_sequence"] == {"P1": "1 2 3 3 2 4", "P2": "1"}
    ids = [a.article_id for a in articles]
    assert "CCS-BANQUES-ART-3-DUP2-v1" in ids  # kept, never dropped (D17)
    assert report["missing_unexplained"] == {}


def test_unparsed_repeal_lines_are_reported_with_their_real_form(tmp_path: Path) -> None:
    data = {"sections": [_section("1", "نص.", "الفصل 1"),
                         _section("2", "نص.\nالفصول من 38 إلى 41 ملغاة", "الفصل 2")]}
    _, _, _, report = ingest_json(_write(tmp_path, "البنوك.json", data))
    assert report["abrogation_lines_unparsed"] == ["الفصول من 38 إلى 41 ملغاة"]


def test_absences_and_third_parties_are_not_repeals() -> None:
    """False positives of the real run: "الغيابات" (absences), "الغير" (others)."""
    from src.legal_retrieval.corpus.sections import abrogation_like_lines, self_abrogation

    assert abrogation_like_lines("إن الغيابات بسبب القيام بواجب يفرضه القانون") == []
    assert abrogation_like_lines("لا يمكن إحالة العقد إلى الغير ولا قطع الغيار") == []
    assert self_abrogation("الفصل 20", "الغيابات المرخص فيها ...") is False
    assert self_abrogation("الفصل55:", "(ألغي بمقتضى الملحق التعديلي عدد 3)") == 3


def test_r9_dropped_last_digit_is_corrected_only_between_two_proofs() -> None:
    data = {"sections": [_section(str(n), f"نص {n}.", f"الفصل {n}") for n in (49, 50, 5, 52)]
            + [_section("5", "نص.", "الفصل 5"), _section("60", "نص.", "الفصل 60")]}
    _, articles, _ = read_sections(data)
    assert [a.number for a in articles] == [49, 50, 51, 52, 5, 60]  # 2nd "5": no proof
    assert articles[2].corrected_from == 5 and articles[4].corrected_from is None


def test_manual_check_completes_a_repeal_broken_by_the_ocr(tmp_path: Path) -> None:
    data = {"sections": [_section(str(n), f"نص {n}.", f"الفصل {n}") for n in range(1, 38)]
            + [_section("37", "نص.\nالفصول 38 -39- ()I4 41: (ألغيت بمقتضى الملحق التعديلي عدد 5)",
                        "الفصل 37"),
               _section("42", "نص 42.", "الفصل 42")]}
    check = {"source_id": "CCS-BANQUES", "part": 1, "articles": ["38", "39", "40", "41"],
             "verdict": "abroge", "avenant": 5, "pdf_text": "الفصول 38 – 39 – 40 – 41 : (ألغيت)"}
    _, articles, _, report = ingest_json(_write(tmp_path, "البنوك.json", data), manual=[check])
    by_id = {a.article_id: a for a in articles}
    art40 = by_id["CCS-BANQUES-ART-40-v1"]
    assert art40.status == ArticleStatus.ABROGE and art40.origin == "manual_check"
    assert art40.amended_by == "CCS-BANQUES-AVENANT-5"
    assert report["missing_unexplained"] == {}


# --- forms of the real run (tools/inspect_sections.py, 2026-10-10) ----------
@pytest.mark.parametrize(("heading", "number", "expected"), [
    ("وينص الفصل 46 من هذه الاتفاقي على هذا النظام التكميلي.", 46, True),   # BTP
    ("الفصل 36 من هذه الاتفاقية.", 36, True),                                 # Construction
    ("(الفصل 36 من هذه الاتفاقين:", 36, True),
    ("بالفصل 5 من الأمر المؤرخ في 8 جانفي 1948", 5, True),                    # BTP, not art. 51
    ("مقتضيات الفصل 25 من هذه الاتفاقية:", 25, True),                         # Enseignement
    ("الفصل 46 (جديد): منحة النقل", 46, False),
    ("الفصل 46 - 3: منحة الحضور", 46, False),
    ("الفصل34: الرخص لتأدية الواجبات العسكرية", 34, False),
    ("مجال تطبيق الاتفاقية:", 3, False),                                      # title only
])
def test_r10_reference_headings_are_continuations(heading: str, number: int,
                                                  expected: bool) -> None:
    from src.legal_retrieval.corpus.sections import is_continuation

    assert is_continuation(heading, number) is expected


@pytest.mark.parametrize(("heading", "number", "suffix"), [
    ("الفصل 54 مثلث (جديد): امتيازات", 54, "TER"),          # Enseignement
    ("الفصل 51 ثالثا ( جديد): احكام", 51, "TER"),            # Cadre
    ("الفصل 46 - 3: منحة الحضور", 46, "-3"),                 # Gardiennage
    ("الفصل 54 —5: منحة الحضور", 54, "-5"),                  # Enseignement (em dash)
    ("الفصل 2 - المدة، المراجعة", 2, ""),                     # dash = separator only
    ("الفصل 46 (جديد): منحة النقل", 46, ""),
])
def test_heading_suffixes(heading: str, number: int, suffix: str) -> None:
    from src.legal_retrieval.corpus.sections import heading_suffix

    assert heading_suffix(heading, number) == suffix


def test_real_sequences_give_no_duplicate(tmp_path: Path) -> None:
    """BTP "33 [46 ref] 34 ... 50 [5 ref] 52" and Gardiennage "46 46مكرر 46-3 46-4"."""
    data = {"sections": [
        _section("33", "نص 33.", "الفصل 33"),
        _section("46", "", "الوطي الاجتماعي وينص الفصل 46 من هذه الاتفاقي."),
        _section("34", "نص 34.", "الفصل 34: الرخص"),
        _section("46", "نص 46.", "الفصل 46 (جديد): منحة النقل"),
        _section("46 مكرر", "نص.", "الفصل 46 مكرر"),
        _section("46", "نص.", "الفصل 46 - 3: منحة الحضور"),
        _section("46", "نص.", "الفصل 46 - 4: منحة السلة"),
        _section("50", "نص 50.", "الفصل 50"),
        _section("5", "", "بالفصل 5 من الأمر المؤرخ في 8 جانفي 1948"),
        _section("52", "نص 52.", "الفصل 52"),
    ]}
    _, articles, _ = read_sections(data)
    assert [a.key for a in articles] == ["33", "34", "46", "46BIS", "46-3", "46-4", "50", "52"]
    assert articles[0].text.endswith("وينص الفصل 46 من هذه الاتفاقي.")  # glued, not lost
    assert "1948" in articles[6].text and articles[6].merged_positions == [8]
    assert all(a.corrected_from is None for a in articles)  # R9 did NOT fire (R10 first)
    _, out, _, report = ingest_json(_write(tmp_path, "البنوك.json", data))
    assert report["duplicate_ids"] == 0 and report["numbering_out_of_order"] == []
    assert "CCS-BANQUES-ART-46-3-v1" in {a.article_id for a in out}


def test_text_after_the_last_article_is_an_annex(tmp_path: Path) -> None:
    """Construction: after "الفصل58: تاريخ التطبيق" comes the sanctions list."""
    data = {"sections": [
        _section("57", "نص 57.", "الفصل 57"),
        _section("58", "تدخل هذه الاتفاقية حيز التطبيق.", "الفصل58: تاريخ التطبيق"),
        _section("36", "الانذار الكتابي، التوبيخ.", "(الفصل 36 من هذه الاتفاقين:"),
        _section("15", "ينتدب المترشحون.", "بالفصل 15 من الاتفاقية"),
    ]}
    _, articles, _, report = ingest_json(_write(tmp_path, "البنوك.json", data))
    by_id = {a.article_id: a for a in articles}
    assert by_id["CCS-BANQUES-ART-58-v1"].text == "تدخل هذه الاتفاقية حيز التطبيق."
    annex = by_id["CCS-BANQUES-ANNEXE-1-v1"]
    assert annex.origin == "annex" and annex.article_number is None
    assert "التوبيخ" in annex.text and "ينتدب" in annex.text   # one annex, nothing lost
    assert report["articles"] == 2 and report["annexes"] == [
        "ANNEXE-1 -> art. [15, 36] (pos [2, 3])"]
