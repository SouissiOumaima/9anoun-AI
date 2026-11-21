"""Réglages communs aux tests DS3."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "real_ocr: test qui utilise le vrai PaddleOCR s'il est installé")


@pytest.fixture(autouse=True)
def _no_real_ocr_by_default(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Le pipeline et le service font comme si PaddleOCR n'était pas installé, sauf test marqué `real_ocr`.

    Les tests restent ainsi identiques et rapides sur tous les postes, avec ou sans requirements-ocr.txt.
    Un test qui veut l'OCR passe un faux moteur (`ocr_engine=...`) : il est toujours utilisé.
    """
    if request.node.get_closest_marker("real_ocr") is None:
        monkeypatch.setattr("src.document_intelligence.extraction.pipeline.paddle_installed", lambda: False)
