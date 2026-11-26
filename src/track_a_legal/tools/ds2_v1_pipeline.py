"""Orchestration locale DS2 ? DS4 Lawyer Track v1."""

from copy import deepcopy
from typing import Any

from src.legal_retrieval.contract.handler import handle as ds2_handle
from src.track_a_legal.tools.ds2_v1_legal_sources import (
    map_ds2_to_v1_legal_sources,
)
from src.track_a_legal.v1_handler import handle_v1


def run_ds2_ds4_v1_pipeline(
    ds4_request: dict[str, Any],
    ds2_request: dict[str, Any],
    *,
    pdf_root: str | None = None,
) -> dict[str, Any]:
    """Ex?cuter DS2 LIVE puis DS4 v1 sans conclusion juridique."""

    # V?rifier les types avant tout traitement.
    if not isinstance(ds4_request, dict):
        raise ValueError("Invalid DS4 request.")

    if not isinstance(ds2_request, dict):
        raise ValueError("Invalid DS2 request.")

    # Travailler sur des copies pour pr?server les entr?es.
    prepared_request = deepcopy(ds4_request)
    retrieval_request = deepcopy(ds2_request)

    # Interdire l'?crasement silencieux de sources pr?existantes.
    if prepared_request.get("legal_sources"):
        raise ValueError(
            "DS4 request already contains legal sources."
        )

    # Ex?cuter le moteur de recherche juridique DS2 local.
    ds2_response = ds2_handle(retrieval_request, live=True)

    # Le mapping valide le contrat et le statut DS2.
    legal_sources = map_ds2_to_v1_legal_sources(ds2_response)

    # Transmettre les sources ? l'analyse officielle DS4.
    prepared_request["legal_sources"] = legal_sources

    # Ne pas inventer reference_date : conserver la valeur initiale.
    if pdf_root is None:
        return handle_v1(prepared_request)
    return handle_v1(prepared_request, pdf_root=pdf_root)
