"""D74 côté recherche : un pointeur (citable=False) n'est JAMAIS renvoyé comme citation.

Demande DS1 : le validateur du modèle force citable=False sur un pointeur
(test_legal_document_kinds.py) ; ces tests vérifient que `search` et
`get_article` respectent ce champ. Le schéma v0 impose une citation par résultat,
donc « jamais cité » = jamais dans results NI dans citations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.legal_retrieval.contract.get_article import get_article
from src.legal_retrieval.contract.handler import handle
from src.legal_retrieval.corpus.models import DocumentKind, LegalArticle
from src.legal_retrieval.corpus.normalize import normalize_arabic

V0 = "legal_retrieval.v0"
ARTICLE = "CCS-BTP-ART-2"
NON_CITABLE = "CCS-BTP-ART-3"  # article ordinaire rendu non citable (permis par le modèle)
POINTEUR = "CCS-BTP-PTR-1"
_TITRE_BAREME = "جدول الأجور الدنيا لعمال البناء"


def _doc(article_id: str, text: str, kind: DocumentKind, label: str,
         **extra: Any) -> LegalArticle:
    # pour le pointeur, citable n'est PAS fixé ici : c'est le validateur D74 qui le met à False
    return LegalArticle(
        article_id=f"{article_id}-v1", source_id="CCS-BTP",
        article_number=None if kind is DocumentKind.POINTEUR else int(article_id[-1]),
        article_label=label, text=text, text_normalized=normalize_arabic(text),
        hierarchy_path=f"البناء > {label}", status="en_vigueur", sector="btp",
        doc_kind=kind, **extra)


@pytest.fixture
def corpus_avec_pointeur(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    docs = [
        _doc(ARTICLE, "تصرف منحة النقل شهريا لكل عامل.", DocumentKind.ARTICLE, "الفصل 2"),
        _doc(POINTEUR, _TITRE_BAREME, DocumentKind.POINTEUR, _TITRE_BAREME),
        _doc(NON_CITABLE, "تحدد ساعات العمل الأسبوعية.", DocumentKind.ARTICLE, "الفصل 3",
             citable=False),
    ]
    assert docs[1].citable is False  # prémisse : D74 tient dans le modèle
    out = tmp_path / "corpus"
    out.mkdir()
    (out / "legal_articles.jsonl").write_text(
        "".join(d.model_dump_json() + "\n" for d in docs), encoding="utf-8")
    monkeypatch.setenv("DS2_CORPUS_DIR", str(out))
    return out


def _ask(query: str) -> dict[str, Any]:
    return handle({"contract_version": V0, "request_id": "t", "query": query})


def _jamais_le_pointeur(response: dict[str, Any]) -> None:
    assert all("-PTR-" not in r["article_id"] for r in response["results"])
    assert all(c["article"] != _TITRE_BAREME for c in response["citations"])
    assert len(response["citations"]) == len(response["results"])


def test_search_ne_cite_jamais_un_pointeur_qui_matche(corpus_avec_pointeur: Path) -> None:
    """La requête matche le pointeur ET l'article : seul l'article sort."""
    response = _ask("تصرف منحة النقل شهريا لكل عامل حسب جدول الأجور")
    assert response["status"] == "ok" and response["mode"] == "live"
    _jamais_le_pointeur(response)
    assert [r["version_group"] for r in response["results"]] == [ARTICLE]


def test_search_refuse_quand_seul_un_pointeur_matche(corpus_avec_pointeur: Path) -> None:
    """Citation ou Silence : un pointeur ne suffit pas à répondre."""
    response = _ask("جدول الأجور الدنيا لعمال البناء")
    assert response["status"] == "refus"
    assert response["refus"]["code"] == "SOURCE_MANQUANTE"
    assert response["results"] == [] and response["citations"] == []


def test_get_article_sur_un_pointeur_est_refuse_sans_citation(corpus_avec_pointeur: Path) -> None:
    """Un id -PTR- est déjà refusé par le schéma de requête v0 (motif ART/ANNEXE) :
    refus de contrat PARAM_INVALIDE, avant toute lecture du corpus. Jamais cité."""
    response = get_article({"contract_version": V0, "request_id": "t",
                            "article_id": f"{POINTEUR}-v1"})
    assert response["status"] == "refus"
    assert response["refus"]["code"] == "PARAM_INVALIDE"
    assert response["results"] == [] and response["citations"] == []


def test_get_article_sur_un_document_non_citable_est_source_manquante(
        corpus_avec_pointeur: Path) -> None:
    """Le filtre de get_article._live : citable=False => SOURCE_MANQUANTE, jamais cité."""
    response = get_article({"contract_version": V0, "request_id": "t",
                            "article_id": NON_CITABLE})
    assert response["status"] == "refus" and response["mode"] == "live"
    assert response["refus"]["code"] == "SOURCE_MANQUANTE"
    assert response["results"] == [] and response["citations"] == []


def test_temoin_un_article_normal_reste_trouve_et_cite(corpus_avec_pointeur: Path) -> None:
    by_search = _ask("منحة النقل")
    assert by_search["status"] == "ok"
    assert by_search["results"][0]["version_group"] == ARTICLE
    assert by_search["citations"][0]["article"] == "الفصل 2"

    by_ref = get_article({"contract_version": V0, "request_id": "t", "article_id": ARTICLE})
    assert by_ref["status"] == "ok"
    assert [r["article_id"] for r in by_ref["results"]] == [f"{ARTICLE}-v1"]
    assert by_ref["citations"][0]["article"] == "الفصل 2"
