"""Réglages communs aux tests DS3."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_real_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le pipeline et le service font comme si PaddleOCR n'était pas installé ni activé.

    Les tests restent ainsi identiques et rapides sur tous les postes, avec ou sans requirements-ocr.txt.
    Un test qui veut l'OCR passe un faux moteur (`ocr_engine=...`) : il est toujours utilisé. Les tests du
    vrai PaddleOCR sont dans test_document_intelligence_ocr.py (ignorés sans PaddleOCR).
    """
    monkeypatch.setattr("src.document_intelligence.extraction.pipeline.paddle_installed", lambda: False)
    monkeypatch.delenv("DS3_OCR_INPROCESS", raising=False)
