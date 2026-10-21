"""Dispatcher for DS2--DS5 contracts, including the DS3 mock contract."""

from __future__ import annotations

from typing import Any, Mapping

from .mock_specialists import MockSpecialistDispatcher
from .legal_retrieval_adapter import LegalRetrievalAdapter
from .track_a_adapter import TrackAAdapter
from .track_b_adapter import TrackBAdapter
from .document_intelligence_adapter import DocumentIntelligenceAdapter


class HybridSpecialistDispatcher:
    """Use the real DS5 contract while other specialist contracts are pending."""

    def __init__(
        self,
        *,
        mock_dispatcher: MockSpecialistDispatcher | None = None,
        legal_retrieval_adapter: LegalRetrievalAdapter | None = None,
        track_a_adapter: TrackAAdapter | None = None,
        track_b_adapter: TrackBAdapter | None = None,
        document_intelligence_adapter: DocumentIntelligenceAdapter | None = None,
    ) -> None:
        self._mocks = mock_dispatcher or MockSpecialistDispatcher.from_file()
        self._legal_retrieval = legal_retrieval_adapter or LegalRetrievalAdapter()
        self._track_a = track_a_adapter or TrackAAdapter()
        self._track_b = track_b_adapter or TrackBAdapter()
        self._document_intelligence = document_intelligence_adapter or DocumentIntelligenceAdapter()

    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if payload.get("agent") == "legal_retrieval":
            return self._legal_retrieval(payload)
        if payload.get("agent") == "track_a_legal":
            return self._track_a(payload)
        if payload.get("agent") == "track_b_accounting":
            return self._track_b(payload)
        if payload.get("agent") == "document_intelligence":
            return self._document_intelligence(payload)
        return self._mocks(payload)
