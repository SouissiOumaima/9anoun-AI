"""Operation get_article (D22): one article by its reference, ALL its versions.

    from src.legal_retrieval.contract.get_article import get_article
    get_article({"contract_version": "legal_retrieval.v0", "article_id": "CCS-BTP-ART-39"})
    get_article({"contract_version": "legal_retrieval.v0", "source_id": "CCS-BTP", "article": "39"})

Same response format as `search` (legal_retrieval_search_response.v0, common.v0
envelope): DS1 and DS4 parse one format only.
- mode "live": the ingested corpus exists on this machine (corpus/store.py);
- mode "mock": no corpus -> the demo articles, never an invented one.
Unknown reference -> refus SOURCE_MANQUANTE, with the reason when DS2 checked
the gap by hand (manual_checks.json: absent from the PDF / missing in the digest).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from ..corpus.ingest_sections import load_manual_checks
from ..corpus.store import DATA_FILE, CorpusStore, load_store, version_group, version_of
from .handler import _demo, _envelope, _refus, validation_errors

DECISION = "D22"
_CONTRACT = "legal_retrieval.contract"

_MSG_BAD_REQUEST = ("Requête get_article non conforme au contrat legal_retrieval.v0 : {details}",
                    "طلب get_article غير مطابق لعقد legal_retrieval.v0.")
_MSG_NOT_FOUND = ("Aucun article ne correspond à cette référence dans le corpus juridique.",
                  "لا يوجد أي فصل يطابق هذا المرجع في المدونة القانونية.")
# Gaps checked BY HAND in the PDF (R8): the user gets the real reason, not a guess.
_MSG_KNOWN_GAP = {
    "absent_du_pdf_source": (
        "L'article {n} n'existe pas dans le PDF source fourni (vérification manuelle DS2).",
        "الفصل {n} غير موجود في ملف PDF المصدر المقدم (تحقق يدوي)."),
    "present_pdf_absent_digest": (
        ("L'article {n} figure dans le PDF original, mais son texte manque dans le corpus "
         "fourni : il ne peut pas être cité."),
        "الفصل {n} موجود في ملف PDF الأصلي لكن نصه غير متوفر في المدونة، فلا يمكن الاستشهاد به."),
}
_MSG_INTERNAL = ("Incident technique dans le service de recherche juridique.",
                 "خلل تقني في خدمة البحث القانوني.")


def _to_result(article: dict[str, Any], store: CorpusStore) -> dict[str, Any]:
    """LegalArticle (corpus line) -> result item of the response schema."""
    source = store.sources.get(article["source_id"], {})
    pdf = f"data/raw/pdf/{Path(source.get('file_name', article['source_id'])).stem}.pdf"
    citation = {"source_file": pdf, "page": article.get("page_start"),
                "article": article["article_label"], "data_file": DATA_FILE,
                "decision_ref": "D20"}  # the corpus itself comes from the D20 loader
    return {
        "article_id": article["article_id"],
        "source_id": article["source_id"],
        "source_title": source.get("title_ar", article["source_id"]),
        "article_number": article.get("article_number"),
        "hierarchy_path": article["hierarchy_path"],
        "text": article["text"],  # exact text, never the normalized one (D13)
        "page": article.get("page_start"),  # not in the Tradrly digest yet -> null
        "effective_from": article.get("effective_from"),
        "effective_to": article.get("effective_to"),
        "status": article["status"],
        "sector": article.get("sector"),
        "related": [],
        "score": 1.0,  # exact match on the reference
        "version_group": version_group(article["article_id"]),
        "version": version_of(article["article_id"]),
        # v0: the consolidated text in force; dated filter in Sprint 5
        "applicable_at_reference_date": article["status"] == "en_vigueur",
        "modified": bool(article.get("modified")),
        "amended_by": article.get("amended_by"),
        "previous_version_available": (False if article["status"] == "abroge"
                                       else article.get("previous_version_available", True)),
        "citation": citation,
    }


def _wanted(request: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """(version_group, source_id, article) asked by the request."""
    if "article_id" in request:
        return version_group(request["article_id"]), None, None
    return None, request["source_id"], request["article"]


def _live(request: dict[str, Any], store: CorpusStore) -> list[dict[str, Any]]:
    group, source_id, article = _wanted(request)
    if group is not None:
        versions = [store.find_group(group)]
    else:
        assert source_id is not None and article is not None
        versions = store.find_by_number(source_id, article)  # several texts: all parts
    return [_to_result(a, store) for group_versions in versions for a in group_versions]


def _mock(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Demo articles (ids MOCK-CCS-BTP-ART-50-v2 ...): never an invented article."""
    group, source_id, article = _wanted(request)
    results: list[dict[str, Any]] = copy.deepcopy(_demo()["response"]["results"])
    if group is not None:
        return [r for r in results if r["version_group"] in (group, f"MOCK-{group}")]
    return [r for r in results
            if r["source_id"].removeprefix("MOCK-") == source_id
            and r["version_group"].rsplit("-ART-", 1)[1] == article]


def _known_gap(request: dict[str, Any]) -> tuple[str, str] | None:
    """Reason of a gap verified by hand, if this reference is one."""
    group, source_id, article = _wanted(request)
    if group is not None and "-ART-" in group:
        source_id, article = group.split("-ART-", 1)
    for check in load_manual_checks():
        if check["source_id"] == source_id and article in [str(a) for a in check["articles"]]:
            messages = _MSG_KNOWN_GAP.get(check["verdict"])
            if messages:
                return messages[0].format(n=article), messages[1].format(n=article)
    return None


def get_article(request: Any) -> dict[str, Any]:
    """Validate, look the article up, validate the response. Never raises."""
    request_id = request.get("request_id") if isinstance(request, dict) else None
    try:
        errors = validation_errors(request, "get_article_request")
        if errors:  # contract refusal -> HTTP 422
            fr, ar = _MSG_BAD_REQUEST
            return _refus(request_id, "PARAM_INVALIDE", fr.format(details="; ".join(errors)),
                          ar, _CONTRACT)
        store = load_store()
        mode = "live" if store is not None else "mock"
        computed_by = f"legal_retrieval.get_article.{mode}"
        results = _live(request, store) if store is not None else _mock(request)
        if not results:  # Citation or Silence: say WHY when DS2 knows it
            fr, ar = _known_gap(request) or _MSG_NOT_FOUND
            response = _refus(request_id, "SOURCE_MANQUANTE", fr, ar, computed_by)
        else:
            response = _envelope(request_id, "ok", computed_by)
            response["results"] = results
            response["citations"] = [r["citation"] for r in results]
        response["mode"] = mode
        out_errors = validation_errors(response, "search_response")  # same format as search
        if out_errors:  # our own bug: never send an invalid message
            raise RuntimeError(f"invalid get_article response: {out_errors}")
        return response
    except Exception:  # noqa: BLE001 - last-resort guard, no internal detail leaked
        response = _envelope(request_id, "erreur", _CONTRACT)
        response["erreur"] = {"type": "INTERNE", "message_fr": _MSG_INTERNAL[0],
                              "message_ar": _MSG_INTERNAL[1]}
        return response
